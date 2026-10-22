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

"""The binary format of the UDP voice packet.

The text protocol uses newline-delimited JSON; that does not suit voice. A
20 ms frame is about 80 bytes under Opus, and JSON + base64 would double it.
The voice packet therefore travels with a fixed-size binary header.

The header is **cleartext**, the body encrypted. That follows from the
topology decision: voice is relayed through the Host (see
VOICE_CHAT_PLAN.en.md), so the Host has to read who sent a packet in order
to distribute it to the others. The Host reads only the header and cannot
touch the body.

To keep the header from being tampered with, it is used as **additional
authenticated data (AAD)** in the encryption: if whoever relays the packet
changes the sender id or the sequence number, decryption fails.

The header (18 bytes, big-endian):

    [ 1 byte  ] version
    [ 1 byte  ] type
    [ 4 bytes ] sender id (unique within the session)
    [ 8 bytes ] sequence number
    [ 4 bytes ] timestamp (ms, the sender's sampling clock)
"""

from __future__ import annotations

import struct
from typing import NamedTuple


#: Incremented if the header format changes; an older client drops a version
#: it does not recognise.
VOICE_PROTOCOL_VERSION = 1

#: Packet types. State information such as muted/speaking does not travel on
#: the voice path; it was removed from the design on 2026-09-19 (so that the
#: server does not learn who spoke when, see the plan, section 2.2).
TYPE_AUDIO = 1
#: The first UDP packet: it carries the token that tells the Host "this
#: address is mine". It is not encrypted and is never forwarded to the
#: recipients; it is consumed at the Host (see `core/voice_relay.py`).
TYPE_HELLO = 2

_KNOWN_TYPES = frozenset({TYPE_AUDIO, TYPE_HELLO})

#: version, type, sender, sequence, timestamp
HEADER = struct.Struct("!BBIQI")
HEADER_BYTES = HEADER.size

#: The duration of one voice frame. The jitter buffer uses the same value.
FRAME_MS = 20

#: The upper bound of a single datagram. The room that stays safe after the
#: IP/UDP headers and Hamachi's own encapsulation are subtracted from a
#: typical 1500-byte MTU. A packet that exceeds it gets fragmented, and a
#: fragmented UDP packet is likely to be lost in its entirety, so we refuse
#: it deliberately.
MAX_DATAGRAM_BYTES = 1200

#: The sender id must fit in 4 bytes (it is also the first half of the nonce).
MAX_SENDER_ID = 0xFFFFFFFF
MAX_SEQUENCE = 0xFFFFFFFFFFFFFFFF
#: The timestamp is 4 bytes, so it wraps about every 49.7 days. Because the
#: delay calculations work on differences, wrapping is not a problem.
TIMESTAMP_MODULO = 0x100000000


class VoicePacketError(Exception):
    """The incoming datagram could not be parsed as a voice packet."""


class VoiceHeader(NamedTuple):
    """A decoded voice packet header."""

    version: int
    type: int
    sender_id: int
    sequence: int
    timestamp_ms: int


def encode_header(
    sender_id: int,
    sequence: int,
    timestamp_ms: int,
    packet_type: int = TYPE_AUDIO,
) -> bytes:
    """Produces the header bytes.

    The result is both prepended to the datagram and handed to the encryption
    as AAD.
    """
    if not 0 <= sender_id <= MAX_SENDER_ID:
        raise VoicePacketError(f"the sender id does not fit in 4 bytes: {sender_id}")
    if not 0 <= sequence <= MAX_SEQUENCE:
        raise VoicePacketError(f"the sequence number does not fit in 8 bytes: {sequence}")
    return HEADER.pack(
        VOICE_PROTOCOL_VERSION,
        packet_type,
        sender_id,
        sequence,
        timestamp_ms % TIMESTAMP_MODULO,
    )


def decode_header(raw: bytes) -> VoiceHeader:
    """Turns the datagram's first 18 bytes into a header.

    The whole datagram may be passed in; the remainder is ignored.
    """
    if len(raw) < HEADER_BYTES:
        raise VoicePacketError(f"the datagram is shorter than the header: {len(raw)} bytes")

    header = VoiceHeader(*HEADER.unpack(raw[:HEADER_BYTES]))
    if header.version != VOICE_PROTOCOL_VERSION:
        raise VoicePacketError(f"bilinmeyen ses protokolu surumu: {header.version}")
    if header.type not in _KNOWN_TYPES:
        raise VoicePacketError(f"bilinmeyen ses paketi tipi: {header.type}")
    return header


def read_sender_id(raw: bytes) -> int:
    """The only field whoever relays the packet needs.

    When the Host receives a voice datagram it reads just this and forwards
    the packet unchanged to the other participants in the room. It cannot
    decrypt the body, and does not need to.
    """
    return decode_header(raw).sender_id


def pack(header: bytes, body: bytes) -> bytes:
    """Joins the header and the encrypted body into a single datagram."""
    datagram = header + body
    if len(datagram) > MAX_DATAGRAM_BYTES:
        raise VoicePacketError(
            f"the datagram is too large: {len(datagram)} bytes (upper bound {MAX_DATAGRAM_BYTES})"
        )
    return datagram


def unpack(datagram: bytes) -> tuple[VoiceHeader, bytes]:
    """Splits a datagram into a (header, encrypted body) pair."""
    if len(datagram) > MAX_DATAGRAM_BYTES:
        raise VoicePacketError(
            f"the datagram is too large: {len(datagram)} bytes (upper bound {MAX_DATAGRAM_BYTES})"
        )
    header = decode_header(datagram)
    body = datagram[HEADER_BYTES:]
    if not body:
        raise VoicePacketError("ses paketinin govdesi bos")
    return header, body
