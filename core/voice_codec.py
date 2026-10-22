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

"""The audio codec: Opus where it is available, otherwise G.711 µ-law.

Both codecs produce **fixed-size** frames. That is not a preference but a
requirement: at a variable bit rate the packet size varies with the audio
and tells the network who spoke when (Wright et al., 2008 -- the full
citation is in `core/voice_opus.py`). DTX is off for the same reason; a
packet of the same size goes out even when nobody speaks.

The codec is agreed between the two sides during the **handshake**
(`choose_codec`): Opus if both have libopus, µ-law otherwise. That way
someone without the library can still talk, the packets merely get bigger.

µ-law is temporary: the `audioop` module it rests on was removed in Python
3.13. Once Opus is established this path will go as well.
"""

from __future__ import annotations

import array
import sys
import warnings

with warnings.catch_warnings():
    # audioop goes away in Python 3.13; once Opus is established it will not
    # be needed anyway.
    warnings.simplefilter("ignore", DeprecationWarning)
    import audioop

from core.voice_opus import DEFAULT_BITRATE, OpusDecoder, OpusEncoder, opus_available
from core.voice_packet import FRAME_MS

#: 16 kHz: at 8 kHz it sounded like a telephone (tried on 2026-09-17).
SAMPLE_RATE = 16000
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
#: The format spoken with the sound card: 16-bit mono PCM.
FRAME_PCM_BYTES = FRAME_SAMPLES * 2

CODEC_MULAW = "ulaw"
CODEC_OPUS = "opus"

#: The bit rate chosen (2026-09-24). At 16 kbit/s libopus places no FEC
#: redundancy at all; at 24 it does, with an expected loss of 10% or more.
OPUS_BITRATE = DEFAULT_BITRATE

#: Frame size before encryption, per codec (bytes).
FRAME_BYTES = {
    CODEC_MULAW: FRAME_SAMPLES,
    CODEC_OPUS: OPUS_BITRATE * FRAME_MS // 8000,
}


def available_codec() -> str:
    """The best codec this machine supports."""
    return CODEC_OPUS if opus_available() else CODEC_MULAW


def choose_codec(ours: str, theirs: str | None) -> str:
    """The codec both sides share; if either cannot say Opus, they meet on µ-law."""
    if ours == CODEC_OPUS and theirs == CODEC_OPUS:
        return CODEC_OPUS
    return CODEC_MULAW


def silence() -> bytes:
    return b"\x00" * FRAME_PCM_BYTES


def faded_repeat(pcm: bytes, factor: float) -> bytes:
    """An attenuated copy of the previous frame in place of a lost one (for µ-law).

    Flat silence clicks; a frame repeated at a lower level is less
    distracting across short losses. Opus does not need this, the codec does
    its own concealment.
    """
    if factor <= 0:
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


class FrameCodec:
    """The encoder/decoder for one direction. Each sender needs its own decoder.

    The Opus decoder must be called **once per frame**: unless `decode(None)`
    is called when no packet arrives, the decoder's internal state falls
    behind the stream.
    """

    def __init__(self, codec: str) -> None:
        if codec not in (CODEC_MULAW, CODEC_OPUS):
            raise ValueError(f"bilinmeyen kodek: {codec}")
        self.codec = codec
        self.frame_bytes = FRAME_BYTES[codec]
        self._encoder: OpusEncoder | None = None
        self._decoder: OpusDecoder | None = None
        if codec == CODEC_OPUS:
            # FEC is off in the encoder: using the redundancy would require
            # reading the packet AFTER the lost frame out of the buffer, and
            # the playback order does not allow that. Leaving it on would
            # steal bits for nothing.
            self._encoder = OpusEncoder(SAMPLE_RATE, FRAME_MS, bitrate=OPUS_BITRATE, fec=False)
            self._decoder = OpusDecoder(SAMPLE_RATE, FRAME_MS)

    def encode(self, pcm: bytes) -> bytes:
        if len(pcm) != FRAME_PCM_BYTES:
            raise ValueError(f"a frame must be {FRAME_PCM_BYTES} bytes, got {len(pcm)}")
        if self._encoder is not None:
            return self._encoder.encode(pcm)
        return audioop.lin2ulaw(pcm, 2)

    def decode(self, frame: bytes) -> bytes:
        if self._decoder is not None:
            return self._decoder.decode(frame)
        return audioop.ulaw2lin(frame, 2)

    def conceal(self) -> bytes | None:
        """A frame if the codec can do its own concealment, None if it cannot."""
        if self._decoder is not None:
            return self._decoder.decode(None)
        return None

    def close(self) -> None:
        for part in (self._encoder, self._decoder):
            if part is not None:
                part.close()
        self._encoder = self._decoder = None
