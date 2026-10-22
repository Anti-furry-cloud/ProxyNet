# ProxyChat — kendi sunucunda, uçtan uca şifreli sohbet
# Copyright (C) 2026 Anti-furry-cloud
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""The jitter buffer: turns irregularly arriving packets into a steady frame stream.

UDP packets do not arrive at even intervals. Even if the sender emits one
exactly every 20 ms, the network pushes packets together, pulls them apart,
reorders them and never delivers some of them. Writing an incoming packet
straight to the speaker produces harsh, broken audio.

The answer is to delay playback deliberately: ``target_ms`` worth of audio is
collected first, then consumed in order every 20 ms. That gives late packets
a chance to catch up. The price is constant delay, so the larger the buffer
the safer the audio and the later it is heard.

This class is **entirely independent of the audio hardware**: there is no
clock in it, no socket, no Qt. The input is a sequence number and a byte
string, the output is a frame order. It decides only from the frames it
holds, which is why packet loss and reordering can be produced directly in
tests.

Usage: the audio device calls ``pop`` every 20 ms. If it returns ``None``,
silence is played for that frame.

**Catch-up (against accumulating delay):** in the first version the frames
that piled up after a delay spike were played as they were. When the buffer
drained and refilled during a spike it started from the oldest frame, and
because there was no mechanism to melt away the excess above the target,
**every spike was added permanently to the delay.** In a simulation driven by
a measured network trace, the delay rose from 80 ms to 300 ms and stayed
there until the conversation ended (tools/ses_simulasyonu.py).

WebRTC's NetEq does this by time-compressing decoded audio. That route is
closed here because this buffer works on encrypted or encoded bytes; the only
thing this layer can do is skip frames. We make that as harmless as possible:

1. Catch-up begins when the buffer rises ``catchup_slack_ms`` above the
   target and stops once it is back at the target. Normal jitter does not
   trigger it.
2. The free ones first: if the next slot is already empty (a lost packet) it
   is skipped rather than playing silence there.
3. A real frame is dropped only once every ``catchup_interval`` frames, and
   only if the empty slots in the buffer are not enough to melt the excess.
   With 5, a 200 ms build-up melts in about a second, and the loss is split
   into scattered 20 ms pieces instead of one long gap.
"""

from __future__ import annotations

from core.voice_packet import FRAME_MS


#: The default target buffer. The middle of the 40-100 ms range in the plan
#: document; because the Phase 0 measurement tool uses the same value, the
#: measured "packets that missed the buffer" rate corresponds directly to
#: this buffer.
DEFAULT_TARGET_MS = 60

#: The most frames the buffer can hold (one second of audio). If more than
#: that piles up, the consuming side is not running; there is no value in
#: keeping the old frames.
DEFAULT_CAPACITY = 50

#: Catch-up starts when the buffer rises this far above the target. 40 ms is
#: above the normal jitter that was measured (a few ms) and above reordering
#: (25-45 ms).
DEFAULT_CATCHUP_SLACK_MS = 40

#: While catching up, a real frame is dropped at most once every this many frames.
DEFAULT_CATCHUP_INTERVAL = 5


class JitterBuffer:
    """A reordering buffer for one sender's audio stream.

    A separate instance is kept per speaker: sequence numbers are specific to
    a sender, and the streams are delayed independently of each other.
    """

    def __init__(
        self,
        target_ms: int = DEFAULT_TARGET_MS,
        frame_ms: int = FRAME_MS,
        capacity: int = DEFAULT_CAPACITY,
        catchup_slack_ms: int = DEFAULT_CATCHUP_SLACK_MS,
        catchup_interval: int | None = DEFAULT_CATCHUP_INTERVAL,
    ) -> None:
        """``catchup_interval=None`` turns catch-up off.

        It exists only for measurement and comparison (to simulate the old
        behaviour); it must not be turned off in real use.
        """
        if frame_ms < 1:
            raise ValueError("the frame duration must be at least 1 ms")
        if target_ms < 0:
            raise ValueError("the target buffer cannot be negative")
        if capacity < 1:
            raise ValueError("the capacity must be at least 1 frame")
        if catchup_slack_ms < 0:
            raise ValueError("the catch-up slack cannot be negative")
        if catchup_interval is not None and catchup_interval < 1:
            raise ValueError("the catch-up interval must be at least 1 frame")

        self.target_ms = target_ms
        self.frame_ms = frame_ms
        self.capacity = capacity
        #: How many frames are needed before playback starts. At least 1: even
        #: with a target of 0 there is nothing to play without one frame in hand.
        self.target_frames = max(1, -(-target_ms // frame_ms))
        self.catchup_slack_frames = -(-catchup_slack_ms // frame_ms)
        self.catchup_interval = catchup_interval

        self._frames: dict[int, bytes] = {}
        self._next = 0
        self._playing = False
        self._catching_up = False
        # Starts at the interval so that the first drop is allowed immediately.
        self._pops_since_drop = catchup_interval or 0

        self.lost = 0
        self.late = 0
        self.duplicate = 0
        self.overflow = 0
        self.resync = 0
        self.underrun = 0
        #: Real frames dropped while catching up.
        self.dropped = 0
        #: Empty slots skipped while catching up, without playing silence.
        self.skipped = 0

    @property
    def filling(self) -> bool:
        """The buffer has not reached the target yet, so playback has not started."""
        return not self._playing

    @property
    def buffered_frames(self) -> int:
        return len(self._frames)

    @property
    def buffered_ms(self) -> int:
        return len(self._frames) * self.frame_ms

    @property
    def depth_frames(self) -> int:
        """The span from the next slot to the newest frame, gaps included.

        This is what shows how far behind playback really is;
        ``buffered_frames`` understates the delay because it does not count
        the lost slots.
        """
        if not self._frames:
            return 0
        start = self._next if self._playing else min(self._frames)
        return max(self._frames) - start + 1

    @property
    def catching_up(self) -> bool:
        return self._catching_up

    def push(self, sequence: int, payload: bytes) -> bool:
        """Puts an incoming frame into the buffer.

        Returns True if the frame was accepted, False if it was dropped. The
        reason for a drop can be read from the counters: ``late``,
        ``duplicate``, ``overflow``.
        """
        if sequence < 0:
            raise ValueError("a sequence number cannot be negative")

        if self._playing and abs(sequence - self._next) > self.capacity:
            # The number is absurdly far away in either direction: the sender
            # has restarted, or no packet arrived for a long time. Rather than
            # judging against the old stream we rebuild from scratch.
            self._restart(sequence, payload)
            return True

        if self._playing and sequence < self._next:
            # The frame's turn has passed, it cannot be played. This is exactly
            # what the Phase 0 measurement counts as a "packet that missed the
            # buffer".
            self.late += 1
            return False

        if sequence in self._frames:
            self.duplicate += 1
            return False

        if len(self._frames) >= self.capacity:
            self.overflow += 1
            return False

        self._frames[sequence] = payload
        return True

    def pop(self) -> bytes | None:
        """Returns the frame whose turn it is.

        ``None`` comes back in two cases: the buffer has not filled yet
        (``filling`` is True), or the frame with that sequence number never
        arrived. In both the caller plays silence; the difference shows up
        only in the statistics.
        """
        if self._playing and not self._frames:
            # The buffer drained completely: either the other side went quiet
            # or the network broke. If we keep consuming an empty buffer,
            # _next runs ahead and every frame counts as "late" once speech
            # resumes. The right thing is to fill from the start again.
            self.underrun += 1
            self._playing = False
            return None

        if not self._playing:
            if len(self._frames) < self.target_frames:
                return None
            self._playing = True
            self._next = min(self._frames)

        self._catch_up()

        frame = self._frames.pop(self._next, None)
        self._next += 1
        self._pops_since_drop += 1
        if frame is None:
            self.lost += 1
        return frame

    def reset(self) -> None:
        """Restarts the stream from scratch (when a sender leaves and rejoins)."""
        self._frames.clear()
        self._next = 0
        self._playing = False
        self._catching_up = False

    def _catch_up(self) -> None:
        """Melts the excess away bit by bit when the buffer sits well above the target."""
        if self.catchup_interval is None:
            return

        depth = self.depth_frames
        if depth > self.target_frames + self.catchup_slack_frames:
            self._catching_up = True
        elif depth <= self.target_frames:
            self._catching_up = False
        if not self._catching_up:
            return

        depth = self._skip_missing_head(depth)

        excess = depth - self.target_frames
        holes = depth - len(self._frames)
        if (
            excess > 0
            and holes < excess
            and self._pops_since_drop >= self.catchup_interval
        ):
            # The empty slots in the buffer are not enough to melt the
            # excess, so drop the oldest real frame. When the empty slots do
            # suffice, waiting costs nothing.
            del self._frames[self._next]
            self._next += 1
            self.dropped += 1
            self._pops_since_drop = 0
            self._skip_missing_head(depth - 1)

    def _skip_missing_head(self, depth: int) -> int:
        """Skips without playing silence while the next slot is empty and excess remains."""
        while depth > self.target_frames and self._next not in self._frames:
            self._next += 1
            self.skipped += 1
            depth -= 1
        return depth

    def _restart(self, sequence: int, payload: bytes) -> None:
        self.resync += 1
        self._frames = {sequence: payload}
        self._next = sequence
        self._playing = False
        self._catching_up = False
