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

from __future__ import annotations

import json
from typing import Any


#: The upper bound for a message's ``content`` field (the server refuses
#: anything longer). Because ciphertext is base64 it grows about 1.4 times
#: against the plaintext; this limit corresponds to roughly 5800 characters
#: of plaintext. It is defined here rather than in the server so that the
#: client can check the same limit before sending.
MAX_CONTENT_BYTES = 8192


class ProtocolError(Exception):
    """Something that does not follow the protocol arrived from the other side."""


class MalformedPacketError(ProtocolError):
    """The line could not be parsed (broken JSON, a non-object body, invalid UTF-8).

    Because the line boundary is known the connection can be salvaged: this
    line can be dropped and the next one carried on from.
    """


class PacketTooLargeError(ProtocolError):
    """The line exceeded the permitted size.

    In this case we cannot find the line boundary, so the stream cannot be
    salvaged; the connection has to be closed.
    """


def encode_packet(packet: dict[str, Any]) -> bytes:
    """Serialize a packet to newline-delimited JSON bytes."""
    return (json.dumps(packet, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def decode_packet(raw: bytes | str) -> dict[str, Any]:
    """Deserialize a packet previously produced by encode_packet.

    Raises MalformedPacketError on malformed input, so that the caller does
    not lose its thread to an unexpected JSONDecodeError.
    """
    try:
        if isinstance(raw, bytes):
            text = raw.decode("utf-8")
        else:
            text = raw
        packet = json.loads(text.strip())
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise MalformedPacketError(f"the packet could not be parsed: {error}") from error

    if not isinstance(packet, dict):
        raise MalformedPacketError(f"a packet must be a JSON object, got {type(packet).__name__}")
    return packet
