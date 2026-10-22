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

"""The client's voice connection: the UDP socket and the hello packets.

Voice is relayed through the Host, so a client knows only the Host's
address; it never sees the IP of anyone else in the room (that was the
reason for choosing relaying over a mesh).

The first job is to tell the Host "this address is mine": the token that
arrived with `voice_joined` is sent back in a **hello** packet along with a
voice packet header. The Host verifies the token and the source IP and binds
the address to the id (`core/voice_relay.py`). The hello is refreshed at
intervals, so the connection recovers by itself if NAT changes the port or
the Host restarts.

It knows nothing about Qt and nothing about the sound card: it takes frames
from outside and hands what arrives to the session. That is what lets the
network path be tested without hardware.
"""

from __future__ import annotations

import socket
import threading
import time
from typing import Callable

from core.voice_packet import MAX_DATAGRAM_BYTES, TYPE_HELLO, encode_header
from core.voice_session import VoiceSession

#: The hello is refreshed at this interval (seconds).
HELLO_INTERVAL = 5.0

#: The socket's timeout; a stop is noticed after at most this delay.
_POLL_INTERVAL = 0.5


def hello_packet(sender_id: int, token: bytes) -> bytes:
    """The packet that introduces the address to the Host. Not encrypted, never forwarded to recipients."""
    return encode_header(sender_id, 0, 0, TYPE_HELLO) + token


class VoiceLink:
    """The network side of a voice session: sending, receiving and refreshing the hello."""

    def __init__(
        self,
        host: str,
        port: int,
        session: VoiceSession,
        token: bytes,
        clock: Callable[[], float] = time.monotonic,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self.address = (host, port)
        self.session = session
        self.token = token
        self._clock = clock
        self._on_error = on_error
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.settimeout(_POLL_INTERVAL)
        self._running = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_hello = 0.0
        self.sent_datagrams = 0
        self.send_errors = 0

    @property
    def local_port(self) -> int:  # pragma: no cover - diagnostics
        return self._socket.getsockname()[1]

    def start(self) -> None:
        if self._running.is_set():
            return
        self._running.set()
        self.say_hello()
        self._thread = threading.Thread(target=self._receive_loop, name="ProxyNetVoiceLink", daemon=True)
        self._thread.start()

    def say_hello(self) -> None:
        """Introduces the address to the Host; it also recovers if the port changes."""
        self._last_hello = self._clock()
        self._send(hello_packet(self.session.sender_id, self.token))

    def send_frame(self, pcm: bytes) -> None:
        """Mikrofon cercevesini sifreleyip Host'a yollar."""
        if not self._running.is_set():
            return
        if self._clock() - self._last_hello >= HELLO_INTERVAL:
            self.say_hello()
        self._send(self.session.outgoing(pcm))

    def _send(self, datagram: bytes) -> None:
        try:
            self._socket.sendto(datagram, self.address)
            self.sent_datagrams += 1
        except OSError as hata:
            self.send_errors += 1
            if self._on_error is not None:
                self._on_error(hata)

    def _receive_loop(self) -> None:
        while self._running.is_set():
            try:
                data, _address = self._socket.recvfrom(MAX_DATAGRAM_BYTES)
            except socket.timeout:
                continue
            except ConnectionResetError:
                # Windows: an earlier send hit a closed port (the server was
                # restarting, say) and the NEXT recvfrom reports it. The socket
                # still works; ending here left the call sending but deaf.
                continue
            except OSError:
                break
            self.session.incoming(data)

    def stop(self) -> None:
        """Closes the socket; it is safe to call twice."""
        if not self._running.is_set():
            return
        self._running.clear()
        try:
            self._socket.close()
        except OSError:
            pass
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self._thread = None
