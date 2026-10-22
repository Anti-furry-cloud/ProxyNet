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

"""Message padding: the ciphertext length must not give away the plaintext length.

AES-GCM is a stream mode, so the ciphertext is **exactly as long** as the
plaintext. The server cannot read the content, but it can look at the
`content` field and say "that one is a three-character reply, that one is a
four-hundred-character paragraph". Since 1.9.0 this has been accurate to the
byte: the Fernet scheme before it had 16-byte block granularity, so moving to
forward secrecy widened this gap somewhat and closing it was left to padding
(THREAT_MODEL.en.md 5.7).

What happens here: before the plaintext is sent, it is grown to the next rung
of a fixed **bucket ladder**. The server no longer sees a length, it sees a
bucket.

## Why a bucket ladder and not Padme

The usual answer in the literature is Padme, from the PURB paper (Nikitin,
Barman, Lueks, Underwood, Hubaux and Ford: "Reducing Metadata Leakage from
Encrypted Files and Communication with PURBs", PoPETs 2019, issue 4,
pages 6-33). It holds leakage to O(log log M) bits and adds at most 12%
overhead. That is the right tool when the size distribution is wide, but it
does not suit chat -- because on short input it applies **no padding at all**:

    2 -> 2      20 -> 20      100 -> 104

Padme only begins padding once the input grows, and the overwhelming majority
of chat messages sit below that threshold. Padding that leaves "ok"
distinguishable from "no" does not close the very thing we mean to close.

The bucket ladder does the opposite: its lowest rung acts as a **floor**.
Every message under 30 bytes -- "ok", "no", "on my way", "give me 5
minutes" -- appears on the wire at exactly the same size as every other.

## How much still leaks

The ladder has nine rungs, so the residual leak is at most log2(9) ~ 3.2
bits. In practice it is less than that, because the real distribution is
skewed: nearly all chat lands on the first rung.

The price paid: the worst case is landing just past a rung. A 31-byte message
grows to 64 bytes -- large in proportion, 33 bytes in absolute terms.
Negligible at chat sizes.

## Format

The padded payload is assembled into this shape **before** encryption:

    [ 2 bytes ] real length (big-endian)
    [ N bytes ] plaintext
    [ ? bytes ] zero padding

The length field comes first so that unpadding is O(1): there is no trailing
marker to hunt for and no zeros to count (and counting would mislead if the
plaintext itself ended in a zero byte). The field sits **inside** the
ciphertext, so it is invisible as it crosses the wire, and it is under the
AES-GCM tag, so it cannot be tampered with.

The padding is zeros rather than random bytes: it ends up inside data that is
encrypted anyway, and AES-GCM output is indistinguishable from random. Random
padding would add nothing and would only cost something.

## Where the top rung comes from

The server enforces a `MAX_CONTENT_BYTES` limit on the `content` field, and
that field is base64. The top rung was chosen so that the token of a full
message fills that limit **exactly**; the same calculation also backs
`max_plaintext_bytes`, so the interface can decide "too long" without having
to encrypt first.
"""

from __future__ import annotations

from .protocol import MAX_CONTENT_BYTES

#: Size of the prefix that carries the real length. Two bytes, comfortably
#: enough for the largest rung (65535 >> 6112).
LENGTH_BYTES = 2

#: The cleartext overhead `core/room_session.py` adds to the token:
#: key id (4) + nonce (12) + AES-GCM tag (16).
#: It is restated here because of a circular import: room_session takes its
#: padding from this module. A test keeps the two in step
#: (tests/test_padding.py).
ENVELOPE_BYTES = 4 + 12 + 16


def _top_bucket() -> int:
    """Top rung, chosen so the base64 token fills `MAX_CONTENT_BYTES` exactly."""
    # base64 turns three bytes into four characters; raw bytes that fit the limit:
    raw = (MAX_CONTENT_BYTES // 4) * 3
    return raw - ENVELOPE_BYTES


#: The padding rungs (the size of the padded payload, not of the plaintext).
#: The first rung is the floor: every short message goes out at that size.
BUCKETS = (32, 64, 128, 256, 512, 1024, 2048, 4096, _top_bucket())


class MessageTooLong(ValueError):
    """The plaintext does not fit the largest rung; the server would refuse it anyway."""


def max_plaintext_bytes() -> int:
    """Longest plaintext (in bytes) that fits the server's limit once padded."""
    return BUCKETS[-1] - LENGTH_BYTES


def bucket_for(length: int) -> int:
    """Padded payload size for a plaintext of `length` bytes."""
    needed = length + LENGTH_BYTES
    for rung in BUCKETS:
        if needed <= rung:
            return rung
    raise MessageTooLong(f"{length} bytes, the maximum is {max_plaintext_bytes()}")


def pad(plaintext: bytes) -> bytes:
    """Grows the plaintext up to the next rung.

    The result is always one of the sizes in `BUCKETS`; two messages of the
    same length also come out at the same length.
    """
    rung = bucket_for(len(plaintext))
    return len(plaintext).to_bytes(LENGTH_BYTES, "big") + plaintext + bytes(rung - len(plaintext) - LENGTH_BYTES)


def unpad(payload: bytes) -> bytes:
    """Extracts the plaintext from a padded payload.

    `ValueError` is raised only if the format is broken. Since the payload
    arrives already verified by the AES-GCM tag, in practice that means either
    a bug of ours or the format of a version we do not know; the caller should
    present both as "could not decrypt".
    """
    if len(payload) < LENGTH_BYTES:
        raise ValueError("padded payload is shorter than the length field")
    length = int.from_bytes(payload[:LENGTH_BYTES], "big")
    if length > len(payload) - LENGTH_BYTES:
        raise ValueError("declared length does not fit the payload")
    return payload[LENGTH_BYTES : LENGTH_BYTES + length]
