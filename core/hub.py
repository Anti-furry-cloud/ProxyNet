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

from dataclasses import dataclass, field
import time
from typing import Any

from .protocol import encode_packet
from .server_state import RoomRegistry


@dataclass
class AttachedClient:
    client_id: str
    sent_packets: list[dict[str, Any]] = field(default_factory=list)

    def send_packet(self, packet: dict[str, Any]) -> None:
        self.sent_packets.append(packet)


class MessageHub:
    def __init__(self) -> None:
        self.registry = RoomRegistry()
        self._clients: dict[str, Any] = {}
        self._client_rooms: dict[str, str] = {}
        self._client_usernames: dict[str, str] = {}

    def attach_client(self, client_id: str) -> AttachedClient:
        client = self._clients.get(client_id)
        if client is None:
            client = AttachedClient(client_id=client_id)
            self._clients[client_id] = client
        return client

    def bind_transport(self, client_id: str, transport: Any) -> None:
        self._clients[client_id] = transport

    def detach_client(self, client_id: str) -> None:
        self._clients.pop(client_id, None)

    def join_room(self, room: str, client_id: str, username: str) -> dict[str, Any]:
        self.attach_client(client_id)
        previous_room = self._client_rooms.get(client_id)
        if previous_room and previous_room != room:
            self.registry.leave(previous_room, client_id)

        self._client_rooms[client_id] = room
        self._client_usernames[client_id] = username
        self.registry.join(room, client_id, username)

        return self.room_snapshot(room)

    def leave_room(self, client_id: str) -> None:
        room = self._client_rooms.pop(client_id, None)
        self._client_usernames.pop(client_id, None)
        if room is not None:
            self.registry.leave(room, client_id)

    def build_message_packet(
        self,
        room: str,
        sender_client_id: str,
        content: str,
        timestamp: float | None = None,
        enc: str | None = None,
    ) -> dict[str, Any]:
        """Builds the message packet to broadcast.

        ``content`` may be encrypted; the server does not interpret it and
        carries it as it is. ``enc`` tells the recipients which scheme to
        decrypt it with.
        """
        ts = time.time() if timestamp is None else timestamp
        sender_username = self._client_usernames.get(sender_client_id, sender_client_id)
        packet = {
            "type": "message",
            "room": room,
            "user": sender_username,
            "content": content,
            "ts": ts,
        }
        if enc is not None:
            packet["enc"] = enc
        return packet

    def broadcast_packet(self, room: str, packet: dict[str, Any]) -> None:
        """Sends a ready-made packet to all clients in the room."""
        for target_client_id in self.registry.broadcast_targets(room, exclude_client_id=None):
            client = self._clients.get(target_client_id)
            if client is not None and hasattr(client, "send_packet"):
                try:
                    client.send_packet(packet.copy())
                except OSError:
                    continue

    def broadcast_message(
        self,
        room: str,
        sender_client_id: str,
        content: str,
        timestamp: float | None = None,
        enc: str | None = None,
    ) -> dict[str, Any]:
        """Builds the message, broadcasts it to the room and returns what was sent."""
        packet = self.build_message_packet(room, sender_client_id, content, timestamp=timestamp, enc=enc)
        self.broadcast_packet(room, packet)
        return packet

    def room_snapshot(self, room: str) -> dict[str, Any]:
        members = self.registry.usernames(room)
        return {"room": room, "users": members, "count": len(members)}

    def serialize_packet(self, packet: dict[str, Any]) -> bytes:
        return encode_packet(packet)
