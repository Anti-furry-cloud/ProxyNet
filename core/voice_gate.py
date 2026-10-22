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

"""The noise gate: silences the microphone while nobody is speaking.

The problem: the microphone picks up everything -- keystrokes, the fan, idle
hiss. All of it was going to the other side.

The answer is to silence the frame while speech is below a threshold. **The
frame is still sent**, only its content becomes silence: stopping the stream
would tell the network who spoke when, and that is exactly why we turned
discontinuous transmission (DTX) off (see the plan, section 4, the Opus
research).

The method is an RMS threshold, chosen to be simple and predictable:

- **Two thresholds (hysteresis).** The threshold that opens the gate is
  higher than the one that closes it. With a single threshold, a sound right
  at the boundary opens and closes the gate continuously and speech gets
  clipped.
- **A hold time.** After the gate opens it stays open for a while even if
  the sound drops, so that short pauses between words do not cut speech off.
- **Closing with a fade.** Falling to silence abruptly is heard as a click;
  the close is spread over a few frames.

This is NOT (spectral) noise suppression: background hiss stays audible
while someone speaks. That would need a separate library; this cuts the
sound that arrives when nobody is speaking.
"""

from __future__ import annotations

import array
import sys
from collections import deque

from core.voice_codec import FRAME_PCM_BYTES, silence
from core.voice_packet import FRAME_MS

#: The RMS threshold that opens the gate (16-bit samples, 0-32767). In a
#: quiet room a microphone's own noise is usually below 100, while normal
#: speech is above 1000. 600 sits between the two.
DEFAULT_OPEN_RMS = 600
#: The threshold that closes the gate. Lower than the opening one: see
#: hysteresis.
DEFAULT_CLOSE_RMS = 300
#: Once open, the gate stays open for at least this long (ms).
DEFAULT_HOLD_MS = 300
#: The close fades out over this long (ms).
DEFAULT_RELEASE_MS = 60
#: Look-ahead: when the gate opens, this many earlier frames are sent too.
#: The soft beginnings of words ("s", "f", "h") fell below the threshold and
#: were being clipped. The price is constant delay: 2 frames = 40 ms. The
#: stream is still 50 frames/s.
DEFAULT_LOOKAHEAD_FRAMES = 2
#: The closing threshold is this multiple of the opening one (the user sets a
#: single number).
CLOSE_RATIO = 0.5


def frame_rms(pcm: bytes) -> float:
    """The RMS of a frame (16-bit mono)."""
    if not pcm:
        return 0.0
    samples = array.array("h")
    samples.frombytes(pcm)
    if sys.byteorder == "big":
        samples.byteswap()
    total = 0
    for value in samples:
        total += value * value
    return (total / len(samples)) ** 0.5


def scaled(pcm: bytes, factor: float) -> bytes:
    """Attenuates a frame by the given factor."""
    if factor >= 1.0:
        return pcm
    if factor <= 0.0:
        return silence()
    samples = array.array("h")
    samples.frombytes(pcm)
    if sys.byteorder == "big":
        samples.byteswap()
    for i, value in enumerate(samples):
        samples[i] = int(value * factor)
    if sys.byteorder == "big":
        samples.byteswap()
    return samples.tobytes()


class NoiseGate:
    """Silences a frame while nobody speaks; it never stops the stream."""

    def __init__(
        self,
        open_rms: float = DEFAULT_OPEN_RMS,
        close_rms: float = DEFAULT_CLOSE_RMS,
        hold_ms: int = DEFAULT_HOLD_MS,
        release_ms: int = DEFAULT_RELEASE_MS,
        frame_ms: int = FRAME_MS,
        lookahead_frames: int = DEFAULT_LOOKAHEAD_FRAMES,
    ) -> None:
        if close_rms > open_rms:
            raise ValueError("the closing threshold cannot be above the opening one")
        self.open_rms = open_rms
        self.close_rms = close_rms
        self.frame_ms = frame_ms
        self.lookahead_frames = max(0, lookahead_frames)
        #: Frames waiting to be sent (the look-ahead queue).
        self._queue: deque[bytes] = deque()
        #: How many of the queued frames are to be sent (filled in
        #: retroactively when the gate opens).
        self._flush_left = 0
        #: The level measured most recently; the bar in the interface shows this.
        self.level = 0.0
        self.hold_frames = max(0, round(hold_ms / frame_ms))
        self.release_frames = max(1, round(release_ms / frame_ms))
        self.enabled = True
        self._open = False
        self._hold_left = 0
        self._release_left = 0
        #: Diagnostics: how many frames were silenced.
        self.silenced = 0
        self.passed = 0

    @property
    def is_open(self) -> bool:
        """True while the gate is open (it still counts as open during the fade)."""
        return self._open or self._release_left > 0

    def set_threshold(self, open_rms: float) -> None:
        """The user's threshold: the closing threshold becomes a fixed ratio of it."""
        self.open_rms = max(0.0, open_rms)
        self.close_rms = self.open_rms * CLOSE_RATIO

    def process(self, pcm: bytes) -> bytes:
        """Passes a frame through, attenuates it, or silences it.

        While look-ahead is on the output is **delayed**: the frame handed in
        goes onto a queue, and the frame handed back is the one given
        `lookahead_frames` earlier. That is what makes it possible to send the
        start of a word that fell below the threshold once the gate opens. The
        stream rate does not change: one frame per call.
        """
        if len(pcm) != FRAME_PCM_BYTES:
            raise ValueError(f"a frame must be {FRAME_PCM_BYTES} bytes, got {len(pcm)}")
        self.level = frame_rms(pcm)
        if not self.enabled:
            self.passed += 1
            return self._delayed(pcm, passthrough=True)
        rms = self.level
        if rms >= self.open_rms:
            if not self._open:
                # The gate has just opened: send the queued frames too (the
                # ones that stayed below the threshold), so the start of the
                # word is not clipped.
                self._flush_left = len(self._queue) + 1
            self._open = True
            self._hold_left = self.hold_frames
            self._release_left = 0
        elif self._open:
            if rms >= self.close_rms:
                # Still speaking, only more quietly: the hold time is renewed.
                self._hold_left = self.hold_frames
            elif self._hold_left > 0:
                self._hold_left -= 1
            else:
                # Begin closing: cutting off abruptly is heard as a click.
                self._open = False
                self._release_left = self.release_frames
        return self._delayed(pcm, passthrough=self._open)

    def _delayed(self, pcm: bytes, passthrough: bool) -> bytes:
        """Puts a frame on the queue and yields the one at its head."""
        if self.lookahead_frames <= 0:
            return self._emit(pcm, passthrough)
        self._queue.append(pcm)
        if len(self._queue) <= self.lookahead_frames:
            # The queue has not filled yet: silence goes out (only for the
            # first 40 ms, at the very start of speech).
            return silence()
        outgoing = self._queue.popleft()
        if self._flush_left > 0:
            self._flush_left -= 1
            self.passed += 1
            return outgoing
        return self._emit(outgoing, passthrough)

    def _emit(self, pcm: bytes, passthrough: bool) -> bytes:
        if passthrough:
            self.passed += 1
            return pcm
        if self._release_left > 0:
            self._release_left -= 1
            self.passed += 1
            return scaled(pcm, (self._release_left + 1) / (self.release_frames + 1))
        self.silenced += 1
        return silence()

    def reset(self) -> None:
        self._open = False
        self._hold_left = 0
        self._release_left = 0
        self._flush_left = 0
        self._queue.clear()
