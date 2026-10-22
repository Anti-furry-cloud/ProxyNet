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

"""One person's voice chat session: encryption, ordering, mixing.

It knows NOTHING about the sound card or the socket. The input is a PCM
frame from the microphone and the output is a datagram to send, or the other
way round. That is what lets this layer be tested without hardware.

How it differs from the prototype (`tools/ses_prototip.py`): this is product
code and it carries **more than one person**. Every sender has their own
jitter buffer, their own decoder and their own counters; on playback they
are all summed and handed to the sound card as a single frame.

The timing extra: a fixed 10-byte addition goes into the **encrypted** part
of every frame (whose stamp it echoes, the stamp, and the time elapsed since
that stamp). The round-trip time comes out of this; because there is no
separate measurement packet and every packet stays the same size, an
outside observer cannot see that any measuring is going on. The method is
the same as RTCP's LSR/DLSR.
"""

from __future__ import annotations

import struct
import time
from typing import Callable

from core.voice_codec import (
    CODEC_MULAW,
    FRAME_PCM_BYTES,
    FrameCodec,
    faded_repeat,
    silence,
)
from core.voice_crypto import VoiceDecryptionError, make_voice_cipher
from core.voice_jitter import JitterBuffer
from core.voice_packet import FRAME_MS, HEADER_BYTES, VoicePacketError, decode_header

#: The timing extra: the echoed sender id, their stamp (ms), and the time
#: elapsed since that packet arrived (ms).
TIMING = struct.Struct("!IIH")
#: Sent in place of an id when there is no packet to echo.
NO_ECHO = 0

#: The audio device's share added to the mouth-to-ear delay; the same
#: definition as the Phase 0 v2 evaluation (RTT/2 + buffer + 40 ms).
DEVICE_ALLOWANCE_MS = 40

#: After this many consecutive missing frames, concealment is abandoned and
#: it falls to silence.
MAX_CONCEALED = 3

#: The upper bound for the measurements (ms).
HISTOGRAM_MAX_MS = 5000


class Distribution:
    """The distribution of millisecond measurements counted into 1 ms bins.

    An hour of conversation produces 180,000 measurements; rather than keep
    them all, the bin counts are enough and a percentile still comes out at
    1 ms resolution.
    """

    def __init__(self) -> None:
        self._bins = [0] * (HISTOGRAM_MAX_MS + 1)
        self.count = 0

    def add(self, ms: float) -> None:
        self._bins[min(max(int(round(ms)), 0), HISTOGRAM_MAX_MS)] += 1
        self.count += 1

    def percentile(self, ratio: float) -> int | None:
        if not self.count:
            return None
        target = max(1, -(-self.count * ratio // 1))
        total = 0
        for ms, bin_count in enumerate(self._bins):
            total += bin_count
            if total >= target:
                return ms
        return HISTOGRAM_MAX_MS

    def summary(self) -> dict:
        return {"median": self.percentile(0.5), "p95": self.percentile(0.95), "count": self.count}


class _Peer:
    """One sender's buffer, decoder and counters."""

    def __init__(self, codec: str) -> None:
        self.buffer = JitterBuffer()
        self.codec = FrameCodec(codec)
        self.last_pcm: bytes | None = None
        self.concealed_run = 0
        self.received = 0
        self.undecryptable = 0
        #: For echoing our own stamp back: (stamp, arrival time).
        self.last_seen: tuple[int, float] | None = None

    def close(self) -> None:
        self.codec.close()


class VoiceSession:
    """One user's session in voice chat."""

    def __init__(
        self,
        room: str,
        password: str | None,
        sender_id: int,
        codec: str = CODEC_MULAW,
        clock: Callable[[], float] = time.monotonic,
        own_sender_key: bytes | None = None,
        allow_password_scheme: bool = False,
    ) -> None:
        # In a session with a password, `make_voice_cipher` raises if no key is
        # supplied: we do not want to fall silently out of forward secrecy.
        # Only callers that deliberately ask for the password-derived scheme
        # pass the flag.
        self.cipher = make_voice_cipher(
            room, password, sender_id, own_sender_key, allow_password_scheme=allow_password_scheme
        )
        self.sender_id = sender_id
        self.codec_name = codec
        self._encoder = FrameCodec(codec)
        self._peers: dict[int, _Peer] = {}
        self._clock = clock
        self._started = clock()
        self._sequence = 0
        #: The last packet to echo: (sender, stamp, arrival time).
        self._echo: tuple[int, int, float] | None = None
        self._last_rtt: float | None = None
        self.sent = 0
        self.received = 0
        self.concealed = 0
        self.silent = 0
        self.undecryptable = 0
        self.malformed = 0
        self.rtt = Distribution()
        self.mouth_to_ear = Distribution()

    # --- participants ---------------------------------------------------

    @property
    def encrypted(self) -> bool:
        return self.cipher.enabled

    @property
    def session_salt(self) -> bytes:
        return self.cipher.session_salt

    def add_peer(
        self, sender_id: int, session_salt: bytes, sender_key: bytes | None = None
    ) -> None:
        """A new sender: the decryption key is derived from their salt (and, under forward secrecy, their key)."""
        if sender_id == self.sender_id:
            return
        self.cipher.add_sender(sender_id, session_salt, sender_key)
        if sender_id not in self._peers:
            self._peers[sender_id] = _Peer(self.codec_name)

    def remove_peer(self, sender_id: int) -> None:
        peer = self._peers.pop(sender_id, None)
        if peer is not None:
            peer.close()
        self.cipher.forget(sender_id)

    def peers(self) -> list[int]:
        return sorted(self._peers)

    def close(self) -> None:
        self._encoder.close()
        for peer in self._peers.values():
            peer.close()
        self._peers.clear()

    # --- outgoing -------------------------------------------------------

    def outgoing(self, pcm: bytes) -> bytes:
        """Turns a 20 ms frame from the microphone into a datagram to send."""
        now = self._clock()
        self._sequence += 1
        body = self._encoder.encode(pcm) + self._timing(now)
        datagram = self.cipher.seal(body, self._sequence, self._ms(now))
        self.sent += 1
        return datagram

    def _ms(self, moment: float) -> int:
        return round((moment - self._started) * 1000) & 0xFFFFFFFF

    def _timing(self, now: float) -> bytes:
        if self._echo is None:
            return TIMING.pack(NO_ECHO, 0, 0)
        sender_id, stamp, arrived = self._echo
        return TIMING.pack(sender_id, stamp, min(round((now - arrived) * 1000), 0xFFFF))

    # --- incoming -------------------------------------------------------

    def incoming(self, datagram: bytes) -> None:
        """Puts a datagram from the network into the right sender's buffer."""
        if len(datagram) < HEADER_BYTES:
            self.malformed += 1
            return
        try:
            preview = decode_header(datagram)
        except VoicePacketError:
            self.malformed += 1
            return
        if preview.sender_id == self.sender_id:
            # Our own packet came back from the relay: we do not hear ourselves.
            return
        peer = self._peers.get(preview.sender_id)
        if peer is None:
            return
        try:
            header, body = self.cipher.open(datagram)
        except VoiceDecryptionError:
            peer.undecryptable += 1
            self.undecryptable += 1
            return
        if len(body) != peer.codec.frame_bytes + TIMING.size:
            # A different codec or a different version; the handshake should
            # have prevented this.
            self.malformed += 1
            return
        now = self._clock()
        peer.buffer.push(header.sequence, body[: peer.codec.frame_bytes])
        self._read_timing(body[peer.codec.frame_bytes :], now)
        peer.last_seen = (header.timestamp_ms, now)
        self._echo = (header.sender_id, header.timestamp_ms, now)
        peer.received += 1
        self.received += 1

    def _read_timing(self, extra: bytes, now: float) -> None:
        """Derives the round-trip time from the stamp the other side echoed back."""
        echo_sender, stamp, waited = TIMING.unpack(extra)
        if echo_sender != self.sender_id:
            return
        rtt = ((self._ms(now) - stamp) & 0xFFFFFFFF) - waited
        if 0 <= rtt < 60_000:
            self._last_rtt = rtt
            self.rtt.add(rtt)

    # --- playback -------------------------------------------------------

    def play(self) -> bytes:
        """The 20 ms PCM to hand the sound card; silence when nobody is speaking.

        When more than one person speaks, the frames are summed.
        """
        import audioop

        mixed: bytes | None = None
        for sender_id, peer in self._peers.items():
            frame = peer.buffer.pop()
            if frame is not None:
                pcm = peer.codec.decode(frame)
                peer.last_pcm = pcm
                peer.concealed_run = 0
                if self._last_rtt is not None:
                    self.mouth_to_ear.add(
                        self._last_rtt / 2 + peer.buffer.buffered_ms + DEVICE_ALLOWANCE_MS
                    )
            else:
                pcm = self._conceal(peer)
            mixed = pcm if mixed is None else audioop.add(mixed, pcm, 2)
        if mixed is None:
            self.silent += 1
            return silence()
        return mixed

    def _conceal(self, peer: _Peer) -> bytes:
        """Concealment in place of a frame that did not arrive.

        With Opus the codec does the concealing and this call is MANDATORY:
        unless the decoder is called once per frame, its internal state falls
        behind the stream.
        """
        peer.concealed_run += 1
        native = peer.codec.conceal()
        if native is not None:
            if peer.last_pcm is None or peer.concealed_run > MAX_CONCEALED:
                self.silent += 1
            else:
                self.concealed += 1
            return native
        if peer.last_pcm is None or peer.concealed_run > MAX_CONCEALED:
            self.silent += 1
            return silence()
        self.concealed += 1
        return faded_repeat(peer.last_pcm, 1.0 - peer.concealed_run * 0.25)

    # --- the numbers ----------------------------------------------------

    def stats(self) -> dict:
        """The numbers shown in the interface and written to the record (no IP, no audio)."""
        peers = {}
        for sender_id, peer in sorted(self._peers.items()):
            peers[str(sender_id)] = {
                "received": peer.received,
                "buffered_ms": peer.buffer.buffered_ms,
                "lost": peer.buffer.lost,
                "late": peer.buffer.late,
                "underrun": peer.buffer.underrun,
                "dropped": peer.buffer.dropped,
                "undecryptable": peer.undecryptable,
            }
        return {
            "codec": self.codec_name,
            "encrypted": self.encrypted,
            "sent": self.sent,
            "received": self.received,
            "concealed": self.concealed,
            "silent": self.silent,
            "undecryptable": self.undecryptable,
            "malformed": self.malformed,
            "rtt_ms": self.rtt.summary(),
            "mouth_to_ear_ms": self.mouth_to_ear.summary(),
            "peers": peers,
        }

    def frame_ms(self) -> int:  # pragma: no cover - convenience
        return FRAME_MS

    def pcm_frame_bytes(self) -> int:  # pragma: no cover - convenience
        return FRAME_PCM_BYTES
