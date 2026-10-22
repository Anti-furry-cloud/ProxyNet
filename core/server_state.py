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
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class RoomMember:
    client_id: str
    username: str
    joined_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RoomRegistry:
    def __init__(self) -> None:
        self._rooms: dict[str, dict[str, RoomMember]] = {}

    def join(self, room: str, client_id: str, username: str) -> None:
        self._rooms.setdefault(room, {})[client_id] = RoomMember(client_id=client_id, username=username)

    def leave(self, room: str, client_id: str) -> None:
        members = self._rooms.get(room)
        if not members:
            return
        members.pop(client_id, None)
        if not members:
            self._rooms.pop(room, None)

    def member_count(self, room: str) -> int:
        return len(self._rooms.get(room, {}))

    def usernames(self, room: str, exclude_client_id: str | None = None) -> list[str]:
        members = self._rooms.get(room, {})
        return [
            member.username
            for client_id, member in members.items()
            if client_id != exclude_client_id
        ]

    def broadcast_targets(self, room: str, exclude_client_id: str | None = None) -> list[str]:
        members = self._rooms.get(room, {})
        return [client_id for client_id in members if client_id != exclude_client_id]

    def rooms(self) -> list[str]:
        return sorted(self._rooms.keys())


class AnonymousLogger:
    """Produces event lines with no identity and no content information.

    Message content is never written in any form, nor is its length. The
    length of whatever content was passed used to be added to the line as
    ``content_length``; since the length of a ciphertext is related to the
    length of the plaintext, that was a leak too (THREAT_MODEL.en.md 5.3).
    The server had stopped passing content here as of 1.5.0, but the
    capability remained; it was removed in 1.7.0 so that the leak cannot come
    back the moment some call passes content again.
    """

    def format_event(self, event: str, room: str, sender: str | None = None, details: dict[str, Any] | None = None) -> str:
        details = details or {}
        parts = [f"event={event}", f"room={room}"]

        if "status" in details:
            parts.append(f"status={details['status']}")

        for key in sorted(details):
            # "status" was already written above; leaving it here made it
            # appear twice on the line (noticed once it reached the log file).
            if key in {"content", "status", "client_id", "ip", "sender", "username"}:
                continue
            value = details[key]
            parts.append(f"{key}={value}")

        return " ".join(parts)

