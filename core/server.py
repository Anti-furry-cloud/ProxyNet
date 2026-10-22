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

import logging
import socket
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

from .hub import MessageHub
from .protocol import MAX_CONTENT_BYTES, MalformedPacketError, PacketTooLargeError, encode_packet
from .server_state import AnonymousLogger
from .voice_relay import DEFAULT_VOICE_PORT, VoiceRelay
from .transport import MAX_LINE_BYTES, LineSocket


#: The core only emits events; where that record is written is decided by
#: the application layer (see apps/proxychat/logging_setup.py). That is how
#: the rule "the core does not write to disk" is kept.
_log = logging.getLogger("proxychat.server")


#: The maximum number of clients accepted at once.
MAX_CLIENTS = 50

#: MAX_CONTENT_BYTES is defined in core/protocol.py (the client uses it too).

#: The maximum number of history messages sent to someone joining a room.
MAX_HISTORY_MESSAGES = 100

#: How far the history packet stays below the client's line limit.
_HISTORY_PACKET_MARGIN = 1024

#: The maximum number of rooms whose history is kept in memory.
MAX_HISTORY_ROOMS = 50

#: Upper limits for room names and usernames.
MAX_NAME_CHARS = 64

#: If nothing arrives from a client for this long, the connection is dropped.
#: Because the client pings every 30 seconds, quiet but live sessions are
#: unaffected; half-open connections get cleaned up.
IDLE_TIMEOUT_SECONDS = 120.0

#: A separate (short) deadline for the first "join" packet.
HANDSHAKE_TIMEOUT_SECONDS = 15.0

#: Rate limit: at most RATE_LIMIT_MESSAGES messages per RATE_LIMIT_WINDOW seconds.
RATE_LIMIT_MESSAGES = 20
RATE_LIMIT_WINDOW = 10.0

#: A separate, wider limit for key-exchange packets. They cannot share a
#: counter with the message limit: when someone joins a room everyone sends
#: an offer plus a wrapped key per peer, so a short burst is normal, and it
#: would be absurd for chat to hit its rate limit because of that. They
#: cannot be left unlimited either: because these packets are broadcast to
#: the room, a single client can multiply the traffic.
KEY_EXCHANGE_RATE_LIMIT = 60

#: Packets the server carries but does NOT look inside. All of the key
#: agreement happens at the ends (core/key_agreement.py); the server has no
#: ability to compute the shared secret, and not having it is by design
#: (THREAT_MODEL.en.md 4).
KEY_EXCHANGE_TYPES = frozenset({"key_offer", "sender_key"})

#: The fields carried in key packets; all of them base64 text. A field that
#: is not on the list does not go out in the broadcast -- we do not want an
#: arbitrary field sent by a client distributed to the room.
_KEY_EXCHANGE_FIELDS = ("pub", "mac", "key", "to")

#: How often the socket wakes up; it bounds how long after stop() the
#: threads take to exit.
_POLL_INTERVAL = 1.0


def _reserve_port(server_socket: socket.socket) -> None:
    """Reserves the listening port for this server.

    On Windows, SO_REUSEADDR lets another socket bind to the same port. It
    used to be used here and caused two problems: a second server could open
    on the same port without getting a "port in use" error, and while the
    Host listened on 0.0.0.0 another program on the machine could listen on
    127.0.0.1:<port> and take over the connection of the Host's own client.
    SO_EXCLUSIVEADDRUSE refuses both; it was measured not to prevent a closed
    server from reopening on the same port straight away (the Host
    reconnecting).

    On other systems SO_REUSEADDR does not permit that hijack and does allow
    rebinding to a port in TIME_WAIT, so it is kept there.
    """
    exclusive = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
    if sys.platform == "win32" and exclusive is not None:
        server_socket.setsockopt(socket.SOL_SOCKET, exclusive, 1)
    else:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


class RateLimiter:
    """A simple message rate limit with a sliding window."""

    def __init__(self, max_events: int = RATE_LIMIT_MESSAGES, window: float = RATE_LIMIT_WINDOW) -> None:
        self.max_events = max_events
        self.window = window
        self._events: deque[float] = deque()

    def allow(self, now: float | None = None) -> bool:
        moment = time.monotonic() if now is None else now
        while self._events and moment - self._events[0] > self.window:
            self._events.popleft()
        if len(self._events) >= self.max_events:
            return False
        self._events.append(moment)
        return True


@dataclass
class ServerStatus:
    running: bool
    host: str
    port: int
    client_count: int
    rooms: list[str]


class ChatServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 5555, keep_history: bool = False) -> None:
        self.host = host
        self.port = port
        # OFF by default (since 1.7.0). When on, the server sends the recent
        # messages in encrypted form to everyone who joins the room -- even
        # to someone who does not know the room password; a weak password can
        # then be attacked offline (THREAT_MODEL.en.md 5.2). With it off, no
        # message is kept in memory and there is no pile to take from the
        # running machine (principle 2).
        self.keep_history = keep_history
        self.hub = MessageHub()
        self.logger = AnonymousLogger()
        self._server_socket: socket.socket | None = None
        self._running = threading.Event()
        self._accept_thread: threading.Thread | None = None
        self._client_threads: list[threading.Thread] = []
        self._transports: dict[str, LineSocket] = {}
        self._lock = threading.Lock()
        self._history: dict[str, list[dict[str, Any]]] = {}
        # Voice chat (Phase 1b): signalling over this TCP channel, audio over
        # a separate UDP socket. The relay does NOT decrypt the audio, it only
        # forwards it.
        self.voice = VoiceRelay()
        self._voice_socket: socket.socket | None = None
        self._voice_thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._running.is_set()

    def start(self) -> None:
        if self.running:
            return

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _reserve_port(server_socket)
        server_socket.bind((self.host, self.port))
        server_socket.listen(20)
        server_socket.settimeout(0.5)

        self._server_socket = server_socket
        self._running.set()
        self._accept_thread = threading.Thread(target=self._accept_loop, name="ProxyNetAcceptLoop", daemon=True)
        self._accept_thread.start()
        self._start_voice_socket()

    def _start_voice_socket(self) -> None:
        """The UDP socket for voice. If it cannot be opened, chat keeps working.

        The port number is the same as TCP's (the protocols are separate), so
        the user is asked for a single firewall permission. Failing to open
        this socket makes voice chat inoperative but does not break text
        chat: the server still starts, only nobody who joins voice gets audio.
        """
        voice_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            voice_socket.bind((self.host, self.port))
        except OSError as hata:
            voice_socket.close()
            _log.warning(
                self.logger.format_event("voice_socket_failed", "-", details={"status": str(hata.errno)})
            )
            return
        voice_socket.settimeout(_POLL_INTERVAL)
        self._voice_socket = voice_socket
        self._voice_thread = threading.Thread(target=self._voice_loop, name="ProxyNetVoiceLoop", daemon=True)
        self._voice_thread.start()

    def _voice_loop(self) -> None:
        """Hands incoming voice datagrams to the relay and sends the result on.

        The voice packet is not touched: the relay says which address it goes
        to, and this code only sends the same bytes.
        """
        while self.running:
            voice_socket = self._voice_socket
            if voice_socket is None:
                break
            try:
                data, address = voice_socket.recvfrom(MAX_LINE_BYTES)
            except socket.timeout:
                continue
            except ConnectionResetError:
                # Windows reports an earlier sendto that hit a closed port
                # (ICMP port unreachable) on the NEXT recvfrom, as WSAECONNRESET.
                # The socket is fine. Treating it as a closed socket stopped the
                # relay for everyone the moment one participant's port went
                # away -- a closed app, a crash, or on purpose.
                continue
            except OSError:
                break
            with self._lock:
                to_send = self.voice.handle(data, address)
            for datagram, target in to_send:
                try:
                    voice_socket.sendto(datagram, target)
                except OSError:
                    continue

    def stop(self, timeout: float = 3.0) -> None:
        """Stops the server and really closes the open client connections.

        It used to close only the listening socket; because the client threads
        stayed blocked on recv, connections remained up even after the server
        was reported as "stopped".
        """
        self._running.clear()
        if self._voice_socket is not None:
            try:
                self._voice_socket.close()
            except OSError:
                pass
            self._voice_socket = None
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None

        with self._lock:
            transports = list(self._transports.values())
            threads = list(self._client_threads)
        for transport in transports:
            transport.close()

        deadline = time.monotonic() + timeout
        for thread in threads:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))
        if self._accept_thread is not None:
            self._accept_thread.join(timeout=max(0.0, deadline - time.monotonic()))
        if self._voice_thread is not None:
            self._voice_thread.join(timeout=max(0.0, deadline - time.monotonic()))
            self._voice_thread = None

        with self._lock:
            self._transports.clear()
            self._client_threads = [thread for thread in self._client_threads if thread.is_alive()]

    def status(self) -> ServerStatus:
        return ServerStatus(
            running=self.running,
            host=self.host,
            port=self.port,
            client_count=len(self._transports),
            rooms=self.hub.registry.rooms(),
        )

    def _accept_loop(self) -> None:
        while self.running:
            try:
                if self._server_socket is None:
                    break
                conn, _addr = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            with self._lock:
                # Without pruning finished threads the list grew for the whole session.
                self._client_threads = [thread for thread in self._client_threads if thread.is_alive()]
                too_many = len(self._transports) >= MAX_CLIENTS

            if too_many:
                self._reject_connection(conn, "server_full", f"server full (at most {MAX_CLIENTS} clients)")
                continue

            thread = threading.Thread(target=self._client_loop, args=(conn,), daemon=True)
            with self._lock:
                self._client_threads.append(thread)
            thread.start()

    # In error packets "code" is for machines and "message" for humans:
    # current clients render the code in the user's chosen language, while
    # older clients that do not know the code keep showing the message.
    # The messages are in English: six were Turkish and one English, so an
    # older client showed a non-Turkish user a mix of both.
    def _reject_connection(self, conn: socket.socket, code: str, reason: str) -> None:
        transport = LineSocket(conn)
        try:
            transport.send_packet({"type": "error", "code": code, "message": reason})
        except OSError:
            pass
        transport.close()

    def _send_room_snapshot(self, room: str, moved: str | None = None) -> None:
        # We use the hub's own broadcast method rather than reaching into its
        # internal dictionary; the body was identical to broadcast_packet anyway.
        snapshot = self.hub.room_snapshot(room)
        packet = {"type": "room_snapshot", **snapshot}
        if moved is not None:
            # Whoever left did not drop the connection, they moved to another
            # room. Which room is not written down; the client shows "moved to
            # another room". Older clients ignore this field.
            packet["moved"] = [moved]
        self.hub.broadcast_packet(room, packet)

    def _broadcast_voice_peers(self, room: str) -> None:
        """Tells the room who the voice participants are. There is **no IP** in the packet.

        This is where everyone learns the others' session salts; the
        decryption key is derived from the salt and the room password, and the
        server cannot put the two together.
        """
        with self._lock:
            participants = self.voice.peers(room)
        self.hub.broadcast_packet(room, {"type": "voice_peers", "room": room, "peers": participants})

    def _broadcast_room_list(self) -> None:
        """Sends the list of open rooms to ALL connected clients.

        The room list used to live only in each client's own interface: when
        someone opened a new room the others never learned of it, and closed
        rooms never dropped off the list. The list is now based on the
        membership the server knows -- a room with no members left falls off
        by itself.
        """
        payload = {"type": "room_list", "rooms": self.hub.registry.rooms()}
        with self._lock:
            transports = list(self._transports.values())
        for transport in transports:
            try:
                transport.send_packet(dict(payload))
            except OSError:
                continue

    def _send_room_history(self, room: str, transport: LineSocket) -> None:
        if not self.keep_history:
            return
        transport.send_packet(self._history_packet(room))

    def _history_packet(self, room: str) -> dict[str, Any]:
        """The newest messages from a room's history that fit the client's line limit.

        History travels as a single-line packet and the client refuses a line
        longer than MAX_LINE_BYTES. All of the last 100 messages used to be
        sent: anyone joining a room where a few long messages had been written
        was thrown out with a "packet limit exceeded" error, and reconnecting
        fetched the same packet and failed again. The oldest messages that do
        not fit are skipped; new and old clients understand the same packet.
        """
        empty = {"type": "history", "room": room, "messages": []}
        budget = MAX_LINE_BYTES - _HISTORY_PACKET_MARGIN - len(encode_packet(empty))
        selected: list[dict[str, Any]] = []
        for message in reversed(self._history.get(room, [])[-MAX_HISTORY_MESSAGES:]):
            # The newline byte encode_packet adds stands in for the comma
            # that will separate the messages inside the packet.
            cost = len(encode_packet(message))
            if cost > budget:
                break
            budget -= cost
            selected.append(message)
        selected.reverse()
        return {**empty, "messages": selected}

    def _append_history(self, room: str, packet: dict[str, Any]) -> None:
        if not self.keep_history:
            return
        if packet.get("enc"):
            # An encrypted message is NOT written to history (the forward
            # secrecy decision, 1.9.0). Under forward secrecy the key dies
            # with the session: whoever connects later -- even the author of
            # the message -- cannot decrypt an old one. Keeping it gives
            # nobody anything, while keeping the gap in THREAT_MODEL.en.md 5.2
            # open (someone who does not know the password could join a room,
            # collect 100 encrypted messages and attack them offline). So it
            # is not kept. In rooms without a password history works exactly
            # as before: there is nothing to hide there anyway.
            return
        # We do NOT delete a room's history when it empties: we do not want
        # the conversation to vanish because somebody stepped out briefly and
        # came back. Unbounded growth is prevented by limiting the number of
        # rooms instead -- the rooms that most recently received a message are
        # kept, the oldest are dropped.
        history = self._history.pop(room, [])
        history.append(packet)
        del history[:-MAX_HISTORY_MESSAGES]
        self._history[room] = history

        while len(self._history) > MAX_HISTORY_ROOMS:
            oldest = next(iter(self._history))
            self._history.pop(oldest)

    @staticmethod
    def _clean_name(raw: Any, fallback: str) -> str:
        """Trims a room name or username and strips characters such as line breaks."""
        name = " ".join(str(raw if raw is not None else "").split())
        if not name:
            return fallback
        return name[:MAX_NAME_CHARS]

    def _unique_username(self, room: str, requested: str, client_id: str) -> str:
        """Appends a number if somebody else in the room has the same name."""
        taken = {
            name.casefold()
            for name in self.hub.registry.usernames(room, exclude_client_id=client_id)
        }
        if requested.casefold() not in taken:
            return requested
        for suffix in range(2, 100):
            candidate = f"{requested}-{suffix}"
            if candidate.casefold() not in taken:
                return candidate
        return f"{requested}-{client_id[-4:]}"

    def _client_loop(self, conn: socket.socket) -> None:
        transport = LineSocket(conn)
        client_id = f"client-{id(conn):x}"
        # The source IP of voice packets is compared against this: the owner
        # of the audio must be the same machine as who they are over TCP.
        try:
            peer_ip = conn.getpeername()[0]
        except OSError:
            peer_ip = ""
        room = None
        limiter = RateLimiter()
        key_limiter = RateLimiter(max_events=KEY_EXCHANGE_RATE_LIMIT)
        rate_limit_warned = False
        last_seen = time.monotonic()

        with self._lock:
            self._transports[client_id] = transport

        try:
            # A short deadline for the handshake, so that sockets which
            # connect and send nothing do not hold a thread indefinitely.
            conn.settimeout(HANDSHAKE_TIMEOUT_SECONDS)
            try:
                join_packet = transport.recv_packet()
            except socket.timeout:
                transport.send_packet(
                    {"type": "error", "code": "join_timeout", "message": "the join packet did not arrive in time"}
                )
                return
            except (MalformedPacketError, PacketTooLargeError) as error:
                code = "packet_too_large" if isinstance(error, PacketTooLargeError) else "malformed_packet"
                transport.send_packet({"type": "error", "code": code, "message": str(error)})
                return

            if not join_packet or join_packet.get("type") != "join":
                transport.send_packet({"type": "error", "code": "join_required", "message": "join required"})
                return

            room = self._clean_name(join_packet.get("room"), "general")
            username = self._unique_username(
                room, self._clean_name(join_packet.get("user"), client_id), client_id
            )

            self.hub.attach_client(client_id)
            self.hub.bind_transport(client_id, transport)
            snapshot = self.hub.join_room(room, client_id, username)
            transport.send_packet({"type": "joined", "room": room, "user": username, "snapshot": snapshot})
            self._send_room_history(room, transport)
            self._send_room_snapshot(room)
            self._broadcast_room_list()
            _log.info(self.logger.format_event("client_joined", room, details={"status": "ok"}))

            # A short poll interval: when stop() is called the loop shuts
            # itself down within a second instead of hanging on recv.
            conn.settimeout(_POLL_INTERVAL)

            while self.running:
                try:
                    packet = transport.recv_packet()
                except socket.timeout:
                    if time.monotonic() - last_seen > IDLE_TIMEOUT_SECONDS:
                        transport.send_packet(
                            {"type": "error", "code": "idle_timeout", "message": "the connection was idle for too long"}
                        )
                        break
                    continue
                except MalformedPacketError:
                    # Because the line boundary is known the session can be
                    # salvaged: we drop the malformed line and carry on.
                    transport.send_packet(
                        {"type": "error", "code": "malformed_packet_ignored", "message": "malformed packet ignored"}
                    )
                    _log.info(self.logger.format_event("malformed_packet", room or "-", details={"status": "ignored"}))
                    continue
                except PacketTooLargeError as error:
                    transport.send_packet({"type": "error", "code": "packet_too_large", "message": str(error)})
                    _log.info(self.logger.format_event("packet_too_large", room or "-", details={"status": "closed"}))
                    break

                if packet is None:
                    break
                last_seen = time.monotonic()

                packet_type = packet.get("type")
                if not isinstance(packet_type, str):
                    # A list here is unhashable: the set lookup further down
                    # raised TypeError and ended the thread with a traceback.
                    continue
                if packet_type == "message":
                    content = str(packet.get("content", "")).strip()
                    if not content:
                        continue
                    if len(content.encode("utf-8")) > MAX_CONTENT_BYTES:
                        transport.send_packet(
                            {"type": "error", "code": "message_too_long", "message": "message too long"}
                        )
                        continue
                    if not limiter.allow():
                        if not rate_limit_warned:
                            transport.send_packet(
                                {
                                    "type": "error",
                                    "code": "rate_limited",
                                    "message": "sending messages too fast, wait a moment",
                                }
                            )
                            rate_limit_warned = True
                        _log.info(self.logger.format_event("rate_limited", room, details={"status": "dropped"}))
                        continue
                    rate_limit_warned = False
                    timestamp = time.time()
                    # Exactly the packet that is broadcast gets written to
                    # history, so history and the live stream come from one
                    # source. The write must happen BEFORE the broadcast:
                    # otherwise a client that received the message and joined
                    # the room immediately would not find it in history.
                    outgoing = self.hub.build_message_packet(
                        room,
                        client_id,
                        content,
                        timestamp=timestamp,
                        enc=packet.get("enc"),
                    )
                    self._append_history(room, outgoing)
                    self.hub.broadcast_packet(room, outgoing)
                    self._send_room_snapshot(room)
                    _log.info(self.logger.format_event("message_received", room, details={"status": "broadcast"}))
                    continue

                if packet_type == "join":
                    new_room = self._clean_name(packet.get("room"), room)
                    requested_username = self._clean_name(packet.get("user"), username)
                    old_room = room
                    if new_room != old_room:
                        self.hub.leave_room(client_id)
                        self._send_room_snapshot(old_room, moved=username)
                        room = new_room
                    username = self._unique_username(room, requested_username, client_id)
                    snapshot = self.hub.join_room(room, client_id, username)
                    # Voice moves with the person as well: the old room no
                    # longer hears them, the new room does.
                    with self._lock:
                        self.voice.move(client_id, room)
                        self.voice.rename(client_id, username)
                    if new_room != old_room:
                        self._broadcast_voice_peers(old_room)
                    self._broadcast_voice_peers(room)
                    transport.send_packet({"type": "joined", "room": room, "user": username, "snapshot": snapshot})
                    self._send_room_history(room, transport)
                    self._send_room_snapshot(room)
                    self._broadcast_room_list()
                    _log.info(self.logger.format_event("room_changed", room, details={"status": "ok"}))
                    continue

                if packet_type == "voice_join":
                    # The Host assigns the id and the token; a client cannot
                    # choose its own. The salt is the client's own creation,
                    # the server only announces it.
                    salt = str(packet.get("salt") or "")[:64]
                    requested_codec = str(packet.get("codec") or "")[:16]
                    # The client's ephemeral public key: a meaningless string
                    # as far as the server is concerned, merely announced to
                    # the room. It is how receivers work out whose key to
                    # derive the voice key from.
                    public_key = str(packet.get("pub") or "")[:128]
                    with self._lock:
                        katilimci = self.voice.join(
                            client_id, username, room, peer_ip, salt, requested_codec, public_key
                        )
                    transport.send_packet(
                        {
                            "type": "voice_joined",
                            "sender_id": katilimci.sender_id,
                            "token": katilimci.token.hex(),
                            "port": self.port,
                            # The first to join sets the room's codec; those
                            # who follow use that rather than their own
                            # suggestion.
                            "codec": katilimci.codec,
                        }
                    )
                    self._broadcast_voice_peers(room)
                    _log.info(self.logger.format_event("voice_joined", room, details={"status": "ok"}))
                    continue

                if packet_type == "voice_salt":
                    # The salt is generated after the id; this is that second step.
                    with self._lock:
                        known = self.voice.set_salt(client_id, str(packet.get("salt") or ""))
                    if known:
                        self._broadcast_voice_peers(room)
                    continue

                if packet_type == "voice_leave":
                    with self._lock:
                        left_voice = self.voice.leave(client_id)
                    if left_voice is not None:
                        self._broadcast_voice_peers(room)
                        _log.info(self.logger.format_event("voice_left", room, details={"status": "ok"}))
                    continue

                if packet_type in KEY_EXCHANGE_TYPES:
                    # The server is a carrier, not a party: it broadcasts the
                    # packet to the room and does not open its content. The
                    # sender name is written from the name the server settled
                    # on, not from what the client wrote.
                    if room is None or not key_limiter.allow():
                        continue
                    broadcast = {"type": packet_type, "room": room, "user": username}
                    for field in _KEY_EXCHANGE_FIELDS:
                        value = packet.get(field)
                        if isinstance(value, str):
                            broadcast[field] = value
                    self.hub.broadcast_packet(room, broadcast)
                    continue

                if packet_type == "ping":
                    transport.send_packet({"type": "pong", "ts": time.time()})
        except OSError:
            pass
        except (MalformedPacketError, PacketTooLargeError):
            # A malformed packet on a path other than recv: end the connection silently.
            pass
        finally:
            with self._lock:
                self._transports.pop(client_id, None)
            with self._lock:
                voice_left = self.voice.leave(client_id) is not None
            if room is not None:
                if voice_left:
                    self._broadcast_voice_peers(room)
                self.hub.leave_room(client_id)
                self.hub.detach_client(client_id)
                self._send_room_snapshot(room)
                self._broadcast_room_list()
                _log.info(self.logger.format_event("client_left", room, details={"status": "ok"}))
            transport.close()
