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

import socket
import struct
import sys
import threading
from typing import Any

from .protocol import PacketTooLargeError, decode_packet, encode_packet


#: The largest size a single line (packet) may take. Without a limit, a
#: client that never sends a newline could inflate the other side's memory.
MAX_LINE_BYTES = 64 * 1024

_RECV_CHUNK = 4096


class LineSocket:
    def __init__(self, sock: socket.socket, max_line_bytes: int = MAX_LINE_BYTES):
        self.sock = sock
        self.max_line_bytes = max_line_bytes
        self._lock = threading.Lock()
        self._buffer = b""

    def send_packet(self, packet: dict[str, Any]) -> None:
        data = encode_packet(packet)
        with self._lock:
            try:
                self.sock.sendall(data)
            except socket.timeout:
                # The peer stopped reading and its buffers are full. Half a
                # line may already be on the wire, so the stream cannot
                # recover -- and while it stayed open, every broadcast to it
                # waited out the timeout: one client that joined and never
                # read slowed a whole room to a crawl and lost messages.
                self._abort()
                raise

    def _abort(self) -> None:
        """Drops the connection at once (RST), unsent data and all.

        A plain shutdown is not enough on Windows: with data still queued it
        waits for a graceful close that a peer which does not read never
        completes, the owner's recv never wakes, and the next send waits out
        the timeout again. close() does wake the owner's recv, which then
        fails and its thread leaves the room as usual. Linger zero is on top
        of that: without it the OS keeps the queued data and goes on trying
        to deliver it to a peer that does not read; with it the data is
        discarded and the peer gets a reset.
        """
        layout = "hh" if sys.platform == "win32" else "ii"
        try:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack(layout, 1, 0))
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass

    def recv_packet(self) -> dict[str, Any] | None:
        """Reads one packet. Returns None if the connection closed.

        Raises MalformedPacketError on a malformed line and
        PacketTooLargeError when the size is exceeded (see core/protocol.py).
        """
        while True:
            while b"\n" not in self._buffer:
                if len(self._buffer) > self.max_line_bytes:
                    # The stream cannot be salvaged, because we cannot see the line boundary.
                    self._buffer = b""
                    raise PacketTooLargeError(
                        f"the packet exceeded the {self.max_line_bytes} byte limit"
                    )

                chunk = self.sock.recv(_RECV_CHUNK)
                if not chunk:
                    if self._buffer:
                        line, self._buffer = self._buffer, b""
                        return decode_packet(line)
                    return None
                self._buffer += chunk

            line, self._buffer = self._buffer.split(b"\n", 1)
            if len(line) > self.max_line_bytes:
                raise PacketTooLargeError(
                    f"the packet exceeded the {self.max_line_bytes} byte limit"
                )
            if not line.strip():
                # An empty line: carry on waiting for the next one (no
                # recursion, so that many empty lines cannot overflow the stack).
                continue
            return decode_packet(line)

    def close(self) -> None:
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass
