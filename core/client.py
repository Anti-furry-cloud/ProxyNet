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

import base64
import socket
import threading
import time
from dataclasses import dataclass
from typing import Callable, Any

from .crypto import (
    DECRYPT_REASON_SENDER,
    DecryptionError,
    NullCipher,
    decrypt_packet_content,
    mark_undecryptable,
    normalize_room,
)
from .key_agreement import OfferError, SenderKeyError
from .protocol import MAX_CONTENT_BYTES, MalformedPacketError, PacketTooLargeError, ProtocolError
from .padding import MessageTooLong
from .room_session import RoomSession, UnknownSenderKey
from .transport import LineSocket


#: The server drops idle connections, so the client pings regularly.
#: This must stay clearly below the server's IDLE_TIMEOUT_SECONDS.
KEEPALIVE_INTERVAL_SECONDS = 30.0


#: A message whose key has not arrived yet is held for this long and then
#: shown with the placeholder. Because the key exchange happens AFTER the
#: connection under forward secrecy, we may not hold the key for a message
#: that arrives right after joining a room; showing it as "the password
#: differs" would be wrong.
#: The wait only lasts one round trip: three seconds is ample, and if
#: something goes wrong the user is not left staring at an empty screen.
DEFERRED_MESSAGE_SECONDS = 3.0

#: The limit of the holding queue. When it fills, the oldest is delivered
#: with the placeholder; swallowing a message silently would be a loss the
#: user never learns about.
MAX_DEFERRED_MESSAGES = 50

#: How often the held messages are polled.
DEFERRED_TICK_SECONDS = 0.5

#: The most public keys the client tracks for peers it has no agreement with
#: (wrapped keys waiting for an offer, offers that failed to verify). Anyone
#: can send these packets with a fresh made-up key each time -- no password
#: needed -- and the server's rate limit only slows that down. Far more than a
#: room of fifty ever needs.
MAX_TRACKED_STRANGERS = 256


def _to_b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _from_b64(value: Any) -> bytes | None:
    """A base64 field from a packet; None if it is malformed. A packet is never trusted."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return base64.urlsafe_b64decode(value.encode("ascii"))
    except (ValueError, TypeError):
        return None


@dataclass
class ClientState:
    connected: bool
    host: str
    port: int
    room: str
    username: str


class ChatClient:
    def __init__(
        self,
        on_packet: Callable[[dict[str, Any]], None] | None = None,
        on_status: Callable[[str, dict[str, Any]], None] | None = None,
        room_password: str = "",
    ) -> None:
        self.on_packet = on_packet
        self.on_status = on_status
        self._socket: socket.socket | None = None
        self._transport: LineSocket | None = None
        self._listen_thread: threading.Thread | None = None
        self._keepalive_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self.room = "general"
        self.username = "guest"
        self.host = ""
        self.port = 5555
        # A session is set up per room and **dies with the connection**: that
        # is exactly what forward secrecy buys, ephemeral keys not outliving
        # the session. The price is that reconnecting pays for Argon2id
        # again; accepted because it is rare. Nothing is derived here, no key
        # is needed before a connection exists.
        self.room_password = room_password
        self._ciphers: dict[str, RoomSession | NullCipher] = {}
        self._cipher: RoomSession | NullCipher = NullCipher()
        #: Which public key belongs to whom, so a leaver's key can be dropped.
        self._peer_users: dict[bytes, str] = {}
        #: Peers whose offer could not be verified. If this is not empty, the
        #: passwords in the room disagree; that is not a guess but direct proof.
        self._mismatched: set[bytes] = set()
        #: Messages waiting for a key: (arrival time, packet). Two threads
        #: touch it -- the listen loop adds, the tick loop delivers whatever
        #: has timed out -- hence the lock.
        self._deferred: list[tuple[float, dict[str, Any]]] = []
        self._deferred_lock = threading.Lock()
        #: Wrapped keys not usable yet: public key -> wrapped key.
        #: A peer's wrapped key can arrive BEFORE their offer (the two packets
        #: set out independently). Had we dropped it, the peer would not send
        #: it again and the exchange would stay half done; so we hold it and
        #: retry once the offer arrives.
        self._pending_keys: dict[bytes, bytes] = {}

    @property
    def connected(self) -> bool:
        return self._transport is not None and not self._stop_event.is_set()

    @property
    def encrypted(self) -> bool:
        return bool(self.room_password)

    def _cipher_for(self, room: str) -> RoomSession | NullCipher:
        key = normalize_room(room)
        cipher = self._ciphers.get(key)
        if cipher is None:
            cipher = self._ciphers[key] = (
                RoomSession(room, self.room_password) if self.room_password else NullCipher()
            )
        return cipher

    def connect(self, host: str, port: int, room: str, username: str, timeout: float = 8.0) -> None:
        if self.connected:
            self.disconnect()

        # The client's state changes only after the connection is up. It used
        # to write room/name/key first; a failed attempt (which happens over
        # and over in Host mode until the server comes up) left the client
        # half-set with the key of a room it never joined.
        cipher = self._cipher_for(room)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        transport = LineSocket(sock)
        try:
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.settimeout(None)
            transport.send_packet({"type": "join", "room": room, "user": username})
        except BaseException:
            transport.close()
            raise

        # Every connection has its own stop flag, so the listen thread of an
        # old connection cannot clear the flag of a new one as it shuts down.
        stop_event = threading.Event()
        self.host = host
        self.port = port
        self.room = room
        self.username = username
        self._cipher = cipher
        self._socket = sock
        self._transport = transport
        self._stop_event = stop_event
        self._listen_thread = threading.Thread(
            target=self._listen_loop, args=(transport, stop_event), name="ProxyNetClientListen", daemon=True
        )
        self._listen_thread.start()
        self._keepalive_thread = threading.Thread(
            target=self._keepalive_loop, args=(transport, stop_event), name="ProxyNetClientKeepalive", daemon=True
        )
        self._keepalive_thread.start()
        self._emit_status("connected", {"host": host, "port": port, "room": room, "username": username})

    def join_room(self, room: str) -> None:
        transport = self._transport
        if transport is None:
            return
        self.room = room
        self._cipher = self._cipher_for(room)
        transport.send_packet({"type": "join", "room": room, "user": self.username})

    def send_packet(self, packet: dict[str, Any]) -> None:
        """Sends a signalling packet (for voice chat, for example).

        Not a message: the content is not encrypted, because there is no
        content here. Voice packets do NOT travel on this channel, they go
        over UDP.
        """
        transport = self._transport
        if transport is None:
            raise ConnectionError("not connected")
        transport.send_packet(packet)

    def send_message(self, content: str) -> None:
        transport = self._transport
        if transport is None:
            raise ConnectionError("not connected")
        packet: dict[str, Any] = {
            "type": "message",
            "room": self.room,
            "user": self.username,
            "content": self._cipher.encrypt(content),
        }
        if self._cipher.scheme is not None:
            packet["enc"] = self._cipher.scheme
        transport.send_packet(packet)

    def message_too_long(self, content: str) -> bool:
        """Would the server refuse this message on its length limit?

        The limit applies to the size of the encrypted form, so the measuring
        is done after encrypting too; the same plaintext counts as longer in a
        room with a password -- padding (1.12.0) widened that difference a
        little further.

        Padding raises `MessageTooLong` for text that exceeds the largest
        rung. That is precisely what "too long" means, so the error does not
        escape: it is turned into the answer here.
        """
        try:
            ciphertext = self._cipher.encrypt(content)
        except MessageTooLong:
            return True
        return len(ciphertext.encode("utf-8")) > MAX_CONTENT_BYTES

    def ping(self) -> None:
        transport = self._transport
        if transport is not None:
            transport.send_packet({"type": "ping"})

    def disconnect(self) -> None:
        # The flag must be raised BEFORE the socket closes, so that the listen
        # thread reads the OSError from the closing socket as a deliberate
        # shutdown rather than a failure.
        self._stop_event.set()
        transport, self._transport = self._transport, None
        self._socket = None
        # Ephemeral keys do not outlive the connection: that is exactly what
        # forward secrecy buys. Reconnecting is a new session, which means new
        # keys (and paying for Argon2id again).
        self._drop_all_peers()
        self._ciphers.clear()
        self._cipher = NullCipher()
        if transport is not None:
            transport.close()

    def _listen_loop(self, transport: LineSocket, stop_event: threading.Event) -> None:
        # The thread uses only its own connection. Had it read
        # self._transport, another thread's disconnect() could set it to None
        # between the check and the use, raising AttributeError.
        try:
            while not stop_event.is_set():
                try:
                    packet = transport.recv_packet()
                except MalformedPacketError:
                    # One malformed line must not bring the listen thread down.
                    continue
                if packet is None:
                    break
                self._absorb_session_state(packet)
                if self._handle_key_exchange(packet):
                    continue
                self._flush_deferred()
                if self._defer_if_unreadable(packet):
                    continue
                self._deliver(packet)
        except (PacketTooLargeError, ProtocolError, OSError) as error:
            # When a deliberate disconnect() closes the socket, recv raises
            # OSError. That is not a failure; it used to show up on the
            # connection screen as raw Windows error text.
            if not stop_event.is_set():
                self._emit_status("error", {"error": str(error)})
        finally:
            stop_event.set()
            self._emit_status("disconnected", {"room": self.room})

    def _absorb_session_state(self, packet: dict[str, Any]) -> None:
        """Adopts the room and username the server settled on.

        If a user with the same name is already in the room, the server
        appends a number; the client writes that value into its own state so
        that later messages go out under the right name.
        """
        if packet.get("type") == "room_snapshot":
            # The member list changed: a newcomer has to learn our key, and
            # the key of whoever left has to be dropped.
            self._forget_absent_peers(packet.get("users"))
            self._send_offer()
            return
        if packet.get("type") != "joined":
            return
        user = packet.get("user")
        if isinstance(user, str) and user:
            self.username = user
        room = packet.get("room")
        if isinstance(room, str) and room and room != self.room:
            # We are leaving the room, so we drop the keys of the peers here.
            # The session object is cached per room (Argon2id is expensive),
            # but keeping old neighbours' keys inside it would waste what
            # forward secrecy buys.
            self._drop_all_peers()
            self.room = room
            self._cipher = self._cipher_for(room)
        # We joined the room, so announce our ephemeral public key. We send it
        # even when the room is empty; whoever arrives later gets a fresh
        # announcement when the member list changes.
        self._send_offer()

    # --- key exchange (forward secrecy) --------------------------------

    def _send_offer(self) -> None:
        """Announces our own ephemeral public key to the room.

        It is resent whenever someone joins or leaves: the server keeps no key
        state (keeping it would create another pile of metadata), and a
        newcomer has no other way to learn our key. The price is one small
        packet per person in the room each time the member list changes.
        """
        session = self._cipher
        if not isinstance(session, RoomSession):
            return
        public_key, tag = session.offer()
        self._send_key_packet("key_offer", {"pub": _to_b64(public_key), "mac": _to_b64(tag)})

    def _send_key_packet(self, packet_type: str, payload: dict[str, str]) -> None:
        transport = self._transport
        if transport is None:
            return
        try:
            transport.send_packet({"type": packet_type, "room": self.room, **payload})
        except OSError:
            # If the connection dropped meanwhile the exchange is pointless;
            # the listen loop reports the drop through its own path.
            pass

    def _handle_key_exchange(self, packet: dict[str, Any]) -> bool:
        """Handles a key-exchange packet. Returning True means it ended here.

        These packets are **not passed on** to the interface: there is nothing
        in them for the user to see, and showing them in the chat flow would
        only be confusing.
        """
        packet_type = packet.get("type")
        if packet_type not in ("key_offer", "sender_key"):
            return False
        session = self._cipher
        if not isinstance(session, RoomSession):
            return True
        public_key = _from_b64(packet.get("pub"))
        if public_key is None or public_key == session.public_key:
            # Our own announcement came back from the server, or the packet is malformed.
            return True
        if packet_type == "key_offer":
            self._accept_offer(session, public_key, packet)
        else:
            self._accept_sender_key(session, public_key, packet)
        return True

    def _accept_offer(self, session: RoomSession, public_key: bytes, packet: dict[str, Any]) -> None:
        tag = _from_b64(packet.get("mac"))
        if tag is None:
            return
        try:
            wrapped = session.accept_offer(public_key, tag)
        except OfferError:
            # Either someone with a different password, or a tampered packet.
            # We send nothing back to the network: a reply would be a signal
            # telling them whether the password was right. But we do note it
            # for ourselves -- it is direct proof that the passwords in the
            # room disagree, and in that case holding messages back is
            # pointless (see _defer_if_unreadable). Only whether the set is
            # empty matters, so it stops growing at the cap.
            if len(self._mismatched) < MAX_TRACKED_STRANGERS:
                self._mismatched.add(public_key)
            return
        self._peer_users[public_key] = str(packet.get("user") or "")
        self._send_key_packet(
            "sender_key",
            {
                "pub": _to_b64(session.public_key),
                "key": _to_b64(wrapped),
                "to": _to_b64(public_key),
            },
        )
        pending = self._pending_keys.pop(public_key, None)
        if pending is not None:
            try:
                session.accept_sender_key(public_key, pending)
            except (SenderKeyError, OfferError):
                return
            self._flush_deferred()
            self._publish_verified()

    def _accept_sender_key(self, session: RoomSession, public_key: bytes, packet: dict[str, Any]) -> None:
        if _from_b64(packet.get("to")) != session.public_key:
            return  # another peer's key; everyone in the room sees this packet
        wrapped = _from_b64(packet.get("key"))
        if wrapped is None:
            return
        try:
            session.accept_sender_key(public_key, wrapped)
        except UnknownSenderKey:
            # Their offer has not arrived yet: we hold the key and retry it
            # together with the offer. At the cap the oldest goes: a real
            # peer's offer follows within a round trip.
            #
            # This used to catch SenderKeyError, which is not what
            # RoomSession raises here: the exception escaped the listen loop
            # and closed the connection. Anyone in the room could do that to
            # anyone, password or not, with one made-up packet addressed to
            # the victim's public key.
            if public_key not in self._pending_keys and len(self._pending_keys) >= MAX_TRACKED_STRANGERS:
                del self._pending_keys[next(iter(self._pending_keys))]
            self._pending_keys[public_key] = wrapped
            return
        except (SenderKeyError, OfferError):
            # The agreement exists but the key did not open, or it is someone
            # else's: retrying with the offer would change nothing.
            return
        # A new key arrived: the messages waiting on it are readable now, and
        # the peer counts as verified.
        self._flush_deferred()
        self._publish_verified()

    def verified_users(self) -> set[str]:
        """The usernames that have **proved** they know the room password.

        The member list the server sends is a claim: envelope packets travel
        in plaintext so they can be forged, and the server itself can make the
        list up anyway (THREAT_MODEL.en.md 5.4). This set is proof rather than
        a claim: everyone in it produced a valid signature derived from the
        password **and** showed that they hold the private key matching the
        public key in that signature, by sending a wrapped sender key that
        actually opened.

        Someone on the list but not in here can be explained two ways: either
        the handshake has not finished yet (temporary), or they do not know the
        password. The interface shows both as "not verified", because there is
        no safe way to tell them apart.
        """
        session = self._cipher
        if not isinstance(session, RoomSession):
            return set()
        keyed = session.keyed_peers()
        return {name for public_key, name in self._peer_users.items() if name and public_key in keyed}

    def _publish_verified(self) -> None:
        """Tells the interface when the verified set changes.

        It goes through the packet flow rather than a separate callback: the
        interface already updates from packets, and this is information that
        belongs side by side with the member list as the server sent it.
        """
        if self.on_packet is None:
            return
        self.on_packet(
            {
                "type": "peers_verified",
                "room": self.room,
                "users": sorted(self.verified_users()),
            }
        )

    def _defer_if_unreadable(self, packet: dict[str, Any]) -> bool:
        """Queues a message whose key has not arrived yet.

        Under forward secrecy the key exchange happens after the connection:
        we may not hold the key for a message that arrives right after joining
        a room. Such a message used to be shown with the "different password"
        placeholder; yet the password is right, the key is merely still on its
        way.
        """
        if packet.get("type") != "message":
            return False
        session = self._cipher
        if not isinstance(session, RoomSession):
            return False
        body = packet.get("content")
        if not isinstance(body, str):
            return False
        try:
            session.decrypt(body)
        except UnknownSenderKey:
            if self._mismatched:
                # The passwords disagree; the key will never arrive. Holding
                # it back would do nothing but make the user wait at an empty
                # screen.
                return False
            with self._deferred_lock:
                self._deferred.append((time.monotonic(), packet))
            self._flush_deferred()
            return True
        except DecryptionError:
            # A real decryption failure: show the placeholder, there is no
            # point in holding it back.
            return False
        return False

    def _flush_deferred(self) -> None:
        """Delivers messages that became readable or that have timed out.

        Delivery happens OUTSIDE the lock: `on_packet` goes to the interface
        and we do not know how long it will take; holding the lock would stall
        the listen loop.
        """
        session = self._cipher
        now = time.monotonic()
        to_deliver: list[dict[str, Any]] = []
        with self._deferred_lock:
            if not self._deferred:
                return
            overflow = max(0, len(self._deferred) - MAX_DEFERRED_MESSAGES)
            remaining: list[tuple[float, dict[str, Any]]] = []
            for index, (arrived, held) in enumerate(self._deferred):
                readable = False
                if isinstance(session, RoomSession):
                    body = held.get("content")
                    readable = isinstance(body, str) and session.can_read(body)
                if readable or now - arrived >= DEFERRED_MESSAGE_SECONDS or index < overflow:
                    to_deliver.append(held)
                else:
                    remaining.append((arrived, held))
            self._deferred = remaining
        for held in to_deliver:
            self._deliver(held)

    def _drop_all_peers(self) -> None:
        """Drops the keys of every peer in the room we are in."""
        session = self._cipher
        if isinstance(session, RoomSession):
            for public_key in self._peer_users:
                session.forget_peer(public_key)
        self._peer_users.clear()
        self._pending_keys.clear()
        self._mismatched.clear()
        with self._deferred_lock:
            self._deferred.clear()

    def _forget_absent_peers(self, users: Any) -> None:
        """Drops the key of whoever left the room.

        A key is matched by public key rather than by room membership, which
        is why we do the matching through usernames here: the key of a peer
        who is absent from the member list the server sent gets dropped.
        """
        session = self._cipher
        if not isinstance(session, RoomSession) or not isinstance(users, list):
            return
        still_present = {entry for entry in users if isinstance(entry, str)}
        dropped = False
        for public_key, name in list(self._peer_users.items()):
            if name and name not in still_present:
                session.forget_peer(public_key)
                self._peer_users.pop(public_key, None)
                self._pending_keys.pop(public_key, None)
                dropped = True
        if dropped:
            self._publish_verified()

    def _keepalive_loop(self, transport: LineSocket, stop_event: threading.Event) -> None:
        """The regular ping, plus a frequent tick for the held messages.

        The ping is infrequent (below the server's idle-drop time), the tick
        frequent. The tick is necessary because nothing else would decide that
        a held message has timed out: if no packet arrives the listen loop
        never wakes, and the message would never appear on screen.
        """
        last_ping = time.monotonic()
        while not stop_event.wait(DEFERRED_TICK_SECONDS):
            self._flush_deferred()
            if time.monotonic() - last_ping < KEEPALIVE_INTERVAL_SECONDS:
                continue
            try:
                transport.send_packet({"type": "ping"})
            except OSError:
                break
            last_ping = time.monotonic()

    def _deliver(self, packet: dict[str, Any]) -> None:
        """Hands a packet to the interface; a replayed message goes nowhere."""
        if self.on_packet is None:
            return
        delivered = self._decrypt_incoming(packet)
        if delivered is not None:
            self.on_packet(delivered)

    def _decrypt_incoming(self, packet: dict[str, Any]) -> dict[str, Any] | None:
        """Decrypts at the network edge, so the layers above see plaintext.

        None means the packet is a replay and must not be shown.
        """
        packet_type = packet.get("type")
        if packet_type == "message":
            return self._open_message(packet)

        if packet_type == "history":
            messages = packet.get("messages")
            if isinstance(messages, list):
                opened = (self._open_message(m) if isinstance(m, dict) else m for m in messages)
                packet["messages"] = [m for m in opened if m is not None]
        return packet

    def _open_message(self, packet: dict[str, Any]) -> dict[str, Any] | None:
        token = packet.get("content")
        decrypt_packet_content(packet, self._cipher)
        return self._check_origin(packet, token)

    def _check_origin(self, packet: dict[str, Any], token: Any) -> dict[str, Any] | None:
        """Is the name on the envelope the name of whoever holds the key?

        The envelope's `user` is written by the server and travels in the
        clear: on the path, Ayse's message can be relabelled as Veli's. The
        key alone is no better -- every member holds every other member's
        sender key, so any of them can encrypt under Veli's. Only when the
        two agree is the message shown as its sender's; otherwise its content
        is withheld, since a forged name is exactly what it would be used for.

        The same message arriving a second time is dropped (None): AES-GCM
        opens a recorded message again without complaint.

        A message that did not open is left alone; it already carries its
        placeholder. So is plaintext: a room without a password has nothing
        to bind a name to.
        """
        session = self._cipher
        if (
            not isinstance(session, RoomSession)
            or packet.get("decrypt_failed")
            or packet.get("enc") is None
            or not isinstance(token, str)
        ):
            return packet
        owner = session.key_owner(token)
        if owner == session.public_key:
            expected: str | None = self.username
        else:
            expected = self._peer_users.get(owner) if owner is not None else None
        if not expected or packet.get("user") != expected:
            return mark_undecryptable(packet, DECRYPT_REASON_SENDER)
        if not session.first_sight(token):
            return None
        return packet

    def _emit_status(self, state: str, payload: dict[str, Any]) -> None:
        if self.on_status is not None:
            self.on_status(state, payload)
