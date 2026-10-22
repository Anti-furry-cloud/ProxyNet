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

"""Binding straight to libopus with ctypes (FOR THE PROTOTYPE).

Why not a ready-made Python package: the packages that drive Opus pull in
the whole of FFmpeg, tens of megabytes including video codecs. Here the only
code that decodes an untrusted packet off the network is libopus.

The settings and their reasoning (see VOICE_CHAT_PLAN.en.md, "Opus
arastirmasi"):

- **Constant bit rate (CBR).** At a variable bit rate the packet size varies
  with the audio and gives silence away; recovering part of what was said
  from packet sizes in encrypted VoIP is a published attack (Wright,
  Ballard, Coull, Monrose and Masson: "Spot Me if You Can: Uncovering Spoken
  Phrases in Encrypted VoIP Conversations", IEEE Symposium on Security and
  Privacy 2008 -- an average accuracy of 50% at identifying phrases, above
  90% for some of them).
- **DTX off.** Not sending packets during silence tells the network who
  spoke when. The price is continuous bandwidth use; that price was accepted.
- **FEC on.** A lost frame can be rebuilt from the redundant copy inside the
  next packet; for that, the buffer has to stay at least one frame ahead.

Where the DLL is looked for, in order: the PROXYCHAT_OPUS_DLL environment
variable, the folder beside the program, the operating system's library
path. In a distributed build the DLL must be compiled by us from Xiph's
source archive; shipping a binary built by another project means trusting
that project's build pipeline.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys
from pathlib import Path

#: The mode tuned for speech (opus_defines.h: OPUS_APPLICATION_VOIP).
OPUS_APPLICATION_VOIP = 2048

# opus_encoder_ctl requests (opus_defines.h).
_SET_BITRATE = 4002
_SET_VBR = 4006
_SET_COMPLEXITY = 4010
_SET_INBAND_FEC = 4012
_SET_PACKET_LOSS_PERC = 4014
_SET_DTX = 4016

#: The largest space reserved for one frame before the encryption overhead.
MAX_PACKET_BYTES = 400

#: The expected loss: the codec places its FEC redundancy (LBRR) according to
#: this. Even though real losses sit in the 1-2% band, this is 10, because we
#: measured it (2026-09-24): at a constant 24 kbit/s, libopus places NO
#: redundant frame at 5% and does place one from 10% upwards. At 16 kbit/s it
#: places none at any value; choosing that bit rate means giving up on FEC.
DEFAULT_EXPECTED_LOSS = 10

DEFAULT_BITRATE = 24000


class OpusError(RuntimeError):
    """libopus returned an error, or the library could not be found."""


def dll_path() -> str | None:
    """The path of the libopus DLL; None if it cannot be found."""
    env_path = os.environ.get("PROXYCHAT_OPUS_DLL")
    if env_path and Path(env_path).is_file():
        return env_path
    names = ("opus.dll", "libopus.dll", "libopus-0.dll")
    # In a frozen exe, the copy embedded in the bundle first (_MEIPASS), then
    # beside the exe; when running from source, the repository root.
    if getattr(sys, "frozen", False):
        folders = [Path(getattr(sys, "_MEIPASS", "")), Path(sys.executable).parent]
    else:
        folders = [Path(__file__).resolve().parent.parent]
    for folder in folders:
        for name in names:
            candidate = folder / name
            if candidate.is_file():
                return str(candidate)
    found = ctypes.util.find_library("opus")
    return found


def _load() -> ctypes.CDLL:
    path = dll_path()
    if path is None:
        raise OpusError(
            "libopus was not found. Set the PROXYCHAT_OPUS_DLL environment variable to "
            "the DLL's path, or put the DLL next to the program."
        )
    try:
        library = ctypes.CDLL(path)
    except OSError as error:  # pragma: no cover - platform dependent
        raise OpusError(f"libopus could not be loaded ({path}): {error}") from error
    _signatures(library)
    return library


def _signatures(lib: ctypes.CDLL) -> None:
    """The ctypes defaults are 32-bit, so pointers must be declared explicitly."""
    lib.opus_encoder_create.restype = ctypes.c_void_p
    lib.opus_encoder_create.argtypes = [
        ctypes.c_int32,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int),
    ]
    lib.opus_encoder_ctl.restype = ctypes.c_int
    lib.opus_encode.restype = ctypes.c_int32
    lib.opus_encode.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_int16),
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int32,
    ]
    lib.opus_encoder_destroy.argtypes = [ctypes.c_void_p]
    lib.opus_decoder_create.restype = ctypes.c_void_p
    lib.opus_decoder_create.argtypes = [ctypes.c_int32, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
    lib.opus_decode.restype = ctypes.c_int
    lib.opus_decode.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_int32,
        ctypes.POINTER(ctypes.c_int16),
        ctypes.c_int,
        ctypes.c_int,
    ]
    lib.opus_decoder_destroy.argtypes = [ctypes.c_void_p]
    lib.opus_strerror.restype = ctypes.c_char_p
    lib.opus_strerror.argtypes = [ctypes.c_int]
    lib.opus_get_version_string.restype = ctypes.c_char_p


_library: ctypes.CDLL | None = None


def library() -> ctypes.CDLL:
    """The loaded libopus; it is loaded on the first call."""
    global _library
    if _library is None:
        _library = _load()
    return _library


def opus_available() -> bool:
    """Can the DLL be found and loaded (the tests and the interface ask this)."""
    try:
        library()
    except OpusError:
        return False
    return True


def library_version() -> str:
    return library().opus_get_version_string().decode("ascii", "replace")


def _error(code: int) -> OpusError:
    return OpusError(library().opus_strerror(code).decode("ascii", "replace"))


class OpusEncoder:
    """Turns 20 ms PCM frames into fixed-size Opus packets."""

    def __init__(
        self,
        sample_rate: int,
        frame_ms: int,
        bitrate: int = DEFAULT_BITRATE,
        fec: bool = True,
        expected_loss: int = DEFAULT_EXPECTED_LOSS,
    ) -> None:
        self.sample_rate = sample_rate
        self.frame_samples = sample_rate * frame_ms // 1000
        self.bitrate = bitrate
        lib = library()
        error = ctypes.c_int()
        self._state = lib.opus_encoder_create(
            sample_rate, 1, OPUS_APPLICATION_VOIP, ctypes.byref(error)
        )
        if error.value != 0 or not self._state:
            raise _error(error.value)
        self._set(_SET_BITRATE, bitrate)
        self._set(_SET_VBR, 0)  # constant bit rate
        self._set(_SET_DTX, 0)  # send during silence as well
        self._set(_SET_INBAND_FEC, 1 if fec else 0)
        self._set(_SET_PACKET_LOSS_PERC, expected_loss if fec else 0)
        # Complexity defaults to 10; lowering it reduces CPU but also reduces
        # quality. The prototype leaves the default, and it does not change
        # without a measurement.

    def _set(self, request: int, value: int) -> None:
        code = library().opus_encoder_ctl(
            ctypes.c_void_p(self._state), ctypes.c_int(request), ctypes.c_int32(value)
        )
        if code < 0:
            raise _error(code)

    def encode(self, pcm: bytes) -> bytes:
        """Packetises a 16-bit mono PCM frame."""
        expected = self.frame_samples * 2
        if len(pcm) != expected:
            raise ValueError(f"a frame must be {expected} bytes, got {len(pcm)} bytes")
        output = ctypes.create_string_buffer(MAX_PACKET_BYTES)
        length = library().opus_encode(
            ctypes.c_void_p(self._state),
            ctypes.cast(ctypes.c_char_p(pcm), ctypes.POINTER(ctypes.c_int16)),
            self.frame_samples,
            output,
            MAX_PACKET_BYTES,
        )
        if length < 0:
            raise _error(length)
        return output.raw[:length]

    def close(self) -> None:
        if getattr(self, "_state", None):
            library().opus_encoder_destroy(ctypes.c_void_p(self._state))
            self._state = None

    __del__ = close


class OpusDecoder:
    """Turns Opus packets into PCM; conceals a lost frame or rebuilds it with FEC."""

    def __init__(self, sample_rate: int, frame_ms: int) -> None:
        self.sample_rate = sample_rate
        self.frame_samples = sample_rate * frame_ms // 1000
        lib = library()
        error = ctypes.c_int()
        self._state = lib.opus_decoder_create(sample_rate, 1, ctypes.byref(error))
        if error.value != 0 or not self._state:
            raise _error(error.value)

    def decode(self, packet: bytes | None, fec: bool = False) -> bytes:
        """Decodes the packet. If ``packet`` is None, a lost frame is concealed (PLC).

        ``fec=True`` is called with the NEXT packet: the lost frame is rebuilt
        from the redundancy inside that packet.
        """
        if packet is None and fec:
            raise ValueError("FEC needs the following packet")
        buffer = (ctypes.c_int16 * self.frame_samples)()
        decoded_samples = library().opus_decode(
            ctypes.c_void_p(self._state),
            packet if packet is not None else None,
            len(packet) if packet is not None else 0,
            buffer,
            self.frame_samples,
            1 if fec else 0,
        )
        if decoded_samples < 0:
            raise _error(decoded_samples)
        return bytes(memoryview(buffer).cast("B"))[: decoded_samples * 2]

    def close(self) -> None:
        if getattr(self, "_state", None):
            library().opus_decoder_destroy(ctypes.c_void_p(self._state))
            self._state = None

    __del__ = close


if __name__ == "__main__":  # manual check: python -m core.voice_opus
    if not opus_available():
        raise SystemExit("libopus was not found (PROXYCHAT_OPUS_DLL).")
    encoder = OpusEncoder(16000, 20)
    decoder = OpusDecoder(16000, 20)
    silence = b"\x00" * (encoder.frame_samples * 2)
    packet = encoder.encode(silence)
    print(f"libopus {library_version()}")
    print(f"{encoder.bitrate} bit/s -> packet {len(packet)} bytes, decoded {len(decoder.decode(packet))} bytes")
