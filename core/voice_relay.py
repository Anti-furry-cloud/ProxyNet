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

"""Voice relaying on the Host: routes a packet to the right people WITHOUT decrypting it.

The core of Phase 1b. The design and its reasoning are in the "Faz 1b
tasarimi" section of `VOICE_CHAT_PLAN.md`; in summary:

- **The Host assigns the sender id.** One counter per server process,
  starting at 1, and a number is **never reused**. The number of someone who
  left stays idle; had it been handed to a newcomer, the old member's packets
  still in flight would mix into the new one's stream and replay window.
- **Address binding.** The Host cannot decrypt the audio (Principle 1:
  `cryptography` is not imported in the server chain, and not here either),
  so it cannot verify cryptographically that a packet really came from that
  person. Instead: the 16-byte token handed out over TCP comes back in the
  first UDP packet, and the packet's source IP must be the same as the IP of
  that person's TCP connection. On a match, (IP, port) is bound to that id;
  later voice packets are accepted only from that address. If the port
  changes (NAT) the client sends hello again with the same token.
- **Silent refusal.** A packet that breaks the rules is dropped without a
  reply; replying would turn the Host into a tool for sending traffic at
  someone else using spoofed source addresses.
- **A rate limit** of 60 packets per second per sender (the normal stream is 50).
- A packet goes only to people who joined voice in the same room, and never
  back to the sender.

What it does not solve: the token travels over TCP in the clear (the
transport layer is unencrypted, THREAT_MODEL 5.4). An active attacker on the
path could read the token and spoof the source address. The cost of that is
not content but the Host's bandwidth; the content is protected by AES-GCM.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Callable

from core.voice_packet import (
    HEADER_BYTES,
    MAX_DATAGRAM_BYTES,
    TYPE_AUDIO,
    TYPE_HELLO,
    VOICE_PROTOCOL_VERSION,
    VoicePacketError,
    decode_header,
)

#: The UDP port for voice. The same number as the TCP chat: the user is
#: asked for a single firewall permission and there is no need to explain two
#: separate numbers. Sharing the number is not a problem, the protocols are
#: separate (TCP/UDP).
DEFAULT_VOICE_PORT = 5555

#: The token's length (bytes). It comes back verbatim in the first UDP packet.
TOKEN_BYTES = 16

#: The rate limit per sender: with 20 ms frames the normal stream is 50/s,
#: leaving 20% of headroom. It tolerates packets that arrive late and in a
#: burst, while cutting off a sender that floods.
RATE_LIMIT_PACKETS = 60
RATE_LIMIT_WINDOW = 1.0

#: The sender id is 4 bytes; once this number is reached new joins are
#: refused (unreachable in practice, but the counter must not wrap).
MAX_SENDER_ID = 0xFFFFFFFF


@dataclass
class VoiceParticipant:
    """A client that has joined voice."""

    client_id: str
    username: str
    room: str
    sender_id: int
    token: bytes
    #: The IP of the TCP connection; the UDP packets must come from it too.
    ip: str
    #: The client's own session salt (hex). The server does not use it, it
    #: only announces it to the others; they derive the decryption key from it.
    session_salt: str = ""
    #: The room's codec; the first to join sets it (see VoiceRelay.room_codec).
    codec: str = ""
    #: The client's ephemeral public key in the room session (base64). The
    #: server does not use it, it only announces it. It is **this** that lets
    #: the others work out whose key to derive the voice key from: the
    #: username is something the server said, the public key is something
    #: verified by a signature derived from the password.
    public_key: str = ""
    #: The (ip, port) bound after the hello was verified.
    address: tuple[str, int] | None = None
    #: The rate-limit window: (window start, packets received in that window).
    _window: tuple[float, int] = field(default=(0.0, 0), repr=False)

    def public(self) -> dict:
        """The fields that go into the `voice_peers` packet. **No IP.**"""
        return {
            "user": self.username,
            "sender_id": self.sender_id,
            "salt": self.session_salt,
            "pub": self.public_key,
        }


class VoiceRelay:
    """Keeps the voice participants and routes incoming datagrams.

    It knows nothing about sockets: `handle` returns what should be sent and
    the caller does the sending. That is how the tests run without a network.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._next_sender_id = 1
        self._by_client: dict[str, VoiceParticipant] = {}
        self._by_sender: dict[int, VoiceParticipant] = {}
        #: A counter of unverified or rule-breaking packets (for diagnostics).
        self.rejected = 0

    # --- signalling (called from the TCP side) -------------------------

    def room_codec(self, room: str, proposed: str = "") -> str:
        """The room's codec: the first to join sets it, the rest follow.

        Everyone must speak the same codec, because the Host relays packets
        without decrypting them and cannot look at who uses which codec. If
        the room empties after the first joiner leaves, the next one to join
        sets it again.
        """
        for peer in self._by_client.values():
            if peer.room == room and peer.codec:
                return peer.codec
        return proposed

    def join(
        self,
        client_id: str,
        username: str,
        room: str,
        ip: str,
        session_salt: str = "",
        codec: str = "",
        public_key: str = "",
    ) -> VoiceParticipant:
        """Joins voice and produces an id plus a token. Renews an existing entry."""
        self.leave(client_id)
        codec = self.room_codec(room, codec)
        if self._next_sender_id > MAX_SENDER_ID:
            raise RuntimeError("the sender ids are exhausted")
        peer = VoiceParticipant(
            client_id=client_id,
            username=username,
            room=room,
            sender_id=self._next_sender_id,
            token=secrets.token_bytes(TOKEN_BYTES),
            ip=ip,
            session_salt=session_salt,
            codec=codec,
            public_key=public_key,
        )
        self._next_sender_id += 1
        self._by_client[client_id] = peer
        self._by_sender[peer.sender_id] = peer
        return peer

    def leave(self, client_id: str) -> VoiceParticipant | None:
        """Removes someone from voice. The id is retired and never handed out again."""
        peer = self._by_client.pop(client_id, None)
        if peer is not None:
            self._by_sender.pop(peer.sender_id, None)
        return peer

    def move(self, client_id: str, room: str) -> None:
        """Voice follows whoever changes room; the old room no longer hears them."""
        peer = self._by_client.get(client_id)
        if peer is not None:
            peer.room = room

    def set_salt(self, client_id: str, session_salt: str) -> bool:
        """Records a client's session salt; only after that do they appear in the list.

        The salt is generated after the id (the decryption key is derived from
        both at once), which is why joining takes two steps: first the id and
        the token, then the salt. Even if someone without a salt appeared in
        the list, nobody could decrypt them.
        """
        peer = self._by_client.get(client_id)
        if peer is None:
            return False
        peer.session_salt = session_salt[:64]
        return True

    def rename(self, client_id: str, username: str) -> None:
        peer = self._by_client.get(client_id)
        if peer is not None:
            peer.username = username

    def participant(self, client_id: str) -> VoiceParticipant | None:
        return self._by_client.get(client_id)

    def peers(self, room: str) -> list[dict]:
        """The voice participants in a room; the body of the `voice_peers` packet."""
        return [
            member.public() for member in self._by_client.values() if member.room == room and member.session_salt
        ]

    def rooms_of(self, client_ids: list[str]) -> set[str]:  # pragma: no cover - convenience
        return {member.room for cid in client_ids if (member := self._by_client.get(cid)) is not None}

    # --- the voice path (called from the UDP side) ---------------------

    def handle(self, data: bytes, address: tuple[str, int]) -> list[tuple[bytes, tuple[str, int]]]:
        """Evaluates an incoming datagram and returns what to forward.

        For a packet that breaks the rules it returns an empty list: NO reply.
        """
        if len(data) < HEADER_BYTES or len(data) > MAX_DATAGRAM_BYTES:
            return self._reject()
        try:
            header = decode_header(data)
        except VoicePacketError:
            return self._reject()
        if header.version != VOICE_PROTOCOL_VERSION:
            return self._reject()
        peer = self._by_sender.get(header.sender_id)
        if peer is None or peer.ip != address[0]:
            return self._reject()
        if header.type == TYPE_HELLO:
            return self._hello(peer, data, address)
        if header.type != TYPE_AUDIO:
            return self._reject()
        if peer.address != address:
            # Not bound, or from a different port: a hello must come first.
            return self._reject()
        if not self._within_rate_limit(peer):
            return self._reject()
        return [
            (data, target.address)
            for target in self._by_client.values()
            if target.room == peer.room
            and target.sender_id != peer.sender_id
            and target.address is not None
        ]

    def _hello(self, peer: VoiceParticipant, data: bytes, address: tuple[str, int]) -> list:
        claimed_token = data[HEADER_BYTES : HEADER_BYTES + TOKEN_BYTES]
        if len(claimed_token) != TOKEN_BYTES or not secrets.compare_digest(claimed_token, peer.token):
            return self._reject()
        # The port may have changed (NAT, or the client restarted): as long as
        # the same token arrives from the same IP, it binds to the new address.
        peer.address = address
        return []

    def _within_rate_limit(self, peer: VoiceParticipant) -> bool:
        now = self._clock()
        start, count = peer._window
        if now - start >= RATE_LIMIT_WINDOW:
            peer._window = (now, 1)
            return True
        if count >= RATE_LIMIT_PACKETS:
            return False
        peer._window = (start, count + 1)
        return True

    def _reject(self) -> list:
        self.rejected += 1
        return []
