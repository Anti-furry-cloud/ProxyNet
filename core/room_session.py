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

"""Forward-secret room session: the encryption layer of text chat (since 1.9.0).

Before this there was `core/crypto.py` -> `RoomCipher` (deleted in 1.10.1):
the key was derived from the password and never changed, so recorded traffic
could be opened retroactively if the password leaked later
(THREAT_MODEL.en.md 5.1). Here the key is born anew every session
(`core/key_agreement.py`) and dropped when the session ends; the password's
only job is to authenticate the other side. Since 1.10.0 the voice side uses
the sender key from here as well (`core/voice_crypto.py`).

This class **knows nothing about the network.** The caller decides which
packet travels how; all that lives here is state and encryption. That keeps
the tests running without opening a socket, and keeps anything from leaking
into the server side.

## Whose key will decrypt it: the key id

Everyone in the room has their own sender key, so a receiver has to know
which key to decrypt an incoming message with. The username in the envelope
cannot serve that purpose: the name is not authenticated, anyone can write
whatever name they like.

The answer is to put a 4-byte **key id** at the front of the message. The id
is derived from the sender key with HKDF; it reveals nothing about the key but
tells the receiver which key to try. Authentication is not the id's job but
the AES-GCM tag's: only someone who knows that sender key can produce a valid
tag.

Four bytes is short, so two participants' ids can collide (by the birthday
bound, a negligible probability in a room of eight). Each id has exactly one
holder: a key whose id is already held by someone else is refused rather than
allowed to replace theirs (`accept_sender_key`). That also refuses a
participant who announces **another participant's** key as their own --
everyone in the room receives everyone's key, so this is possible from the
inside.

## Who wrote it: the id names the holder

The name on a message envelope is written by the server and travels in the
clear, so on its own it proves nothing. After a message opens, `key_owner`
says whose key opened it, and the client accepts the message only if the two
agree (`core/client.py` -> `_check_origin`). Neither half is enough alone: the
name can be relabelled on the path, and the key can be used by any member,
since every member holds every other member's key.

`first_sight` keeps a message from being shown twice: a recorded message sent
again opens again, because nothing in AES-GCM remembers what it has seen.

## Token format

    base64url( key_id[4] || nonce[12] || encrypted_payload )

The normalised form of the room name goes in as AAD, so a message cannot be
carried over to another room.

What gets encrypted is not the plaintext itself but the **padded payload**
(`core/padding.py`): because AES-GCM is a stream mode the ciphertext would be
exactly as long as the plaintext, and although the server cannot read the
content it would see the length. Since 1.12.0 the payload is rounded onto a
fixed bucket ladder, so what the server sees is not a length but a bucket
(THREAT_MODEL.en.md 5.7).

## An unknown key is a passing state, not an error

Just after joining a room, a peer's sender key may not have arrived yet. A
message that comes in during that window cannot be decrypted -- but the
reason is not a wrong password. To keep the two apart there is a separate
exception: `UnknownSenderKey`. The interface must not present it as "the
password differs".
"""

from __future__ import annotations

import base64
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .crypto import DecryptionError, derive_master_key, normalize_room
from .key_agreement import (
    EphemeralKey,
    SenderKeyError,
    new_sender_key,
    unwrap_sender_key,
    verify_offer,
    wrap_sender_key,
)
from .padding import pad, unpad

#: The name written into the `scheme` field. Older clients do not recognise it
#: and mark the message as "a different version" -- better that than breaking
#: silently.
#: v1 -> v2 (1.12.0): the payload now travels padded. There is no negotiation,
#: it is a clean break; talking to a client without padding would make the
#: padding pointless.
SCHEME = "aesgcm-x25519-v2"

#: The key id at the front of a message.
KEY_ID_BYTES = 4
#: The AES-GCM nonce; a fresh one per message.
NONCE_BYTES = 12
#: How many recent messages `first_sight` remembers. A session's sender key
#: dies with the connection, and the server's rate limit bounds how many
#: messages one session can carry, so this covers a long session; the cost is
#: 16 bytes per entry.
SEEN_MESSAGES_LIMIT = 8192

_KEY_ID_INFO = b"proxynet-key-id-v1"
_MESSAGE_AAD = b"proxynet-msg-v1"


class UnknownSenderKey(DecryptionError):
    """We do not hold the sender key of whoever wrote this message yet."""


def _head(token: str) -> bytes | None:
    """A message's key id and nonce: what names it. None if it is malformed."""
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
    except (ValueError, TypeError, AttributeError):
        return None
    if len(raw) <= KEY_ID_BYTES + NONCE_BYTES:
        return None
    return raw[: KEY_ID_BYTES + NONCE_BYTES]


def key_id(sender_key: bytes) -> bytes:
    """The sender key's 4-byte id; it does not give the key away."""
    return HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_ID_BYTES,
        salt=None,
        info=_KEY_ID_INFO,
    ).derive(sender_key)


class RoomSession:
    """The end-to-end state of a session in one room.

    Its lifetime is the session's: when the connection drops the object is
    released and the ephemeral keys go with it. Nothing is written to disk.
    """

    scheme = SCHEME

    def __init__(
        self,
        room: str,
        password: str,
        *,
        ephemeral: EphemeralKey | None = None,
        sender_key: bytes | None = None,
    ) -> None:
        self.room = room
        self._aad = _MESSAGE_AAD + normalize_room(room).encode("utf-8")
        self._master = derive_master_key(room, password)
        self._own = ephemeral if ephemeral is not None else EphemeralKey()
        self._sender_key = sender_key if sender_key is not None else new_sender_key()
        #: Verified peers: public key -> pair key.
        self._pairs: dict[bytes, bytes] = {}
        #: The keys we hold for decryption: id -> sender key.
        #: Our own key is here too; we can decrypt our own messages as well.
        own_id = key_id(self._sender_key)
        self._by_id: dict[bytes, bytes] = {own_id: self._sender_key}
        #: Which id belongs to whom, so a peer's key can be dropped when they leave.
        self._peer_ids: dict[bytes, bytes] = {}
        #: The reverse: id -> the public key of its one holder (ours included).
        self._holders: dict[bytes, bytes] = {own_id: self._own.public_key}
        #: Messages already shown: key id + nonce. A dict keeps insertion order,
        #: so the oldest is dropped first when it fills.
        self._seen: dict[bytes, None] = {}

    @property
    def enabled(self) -> bool:
        return True

    @property
    def public_key(self) -> bytes:
        return self._own.public_key

    def offer(self) -> tuple[bytes, bytes]:
        """The offer to announce: (public key, tag)."""
        return self._own.public_key, self._own.offer(self._master, self.room)

    def accept_offer(self, peer_public: bytes, mac: bytes) -> bytes:
        """Verifies a peer's offer and returns the wrapped key to send them.

        If the offer is invalid `OfferError` is raised; the caller drops the
        packet.
        """
        verify_offer(peer_public, mac, self._master, self.room)
        pair = self._own.pair_key(peer_public)
        self._pairs[bytes(peer_public)] = pair
        return wrap_sender_key(pair, self._sender_key)

    def accept_sender_key(self, peer_public: bytes, wrapped: bytes) -> bytes:
        """Unwraps and stores a peer's sender key; returns its id.

        The peer's offer must have been verified first: without the pair key
        the wrapped packet cannot be opened.
        """
        peer = bytes(peer_public)
        pair = self._pairs.get(peer)
        if pair is None:
            raise UnknownSenderKey("there is no key agreement with this peer yet")
        key = unwrap_sender_key(pair, wrapped)
        ident = key_id(key)
        holder = self._holders.get(ident)
        if holder is not None and holder != peer:
            # Either a 1-in-4-billion accident or someone announcing a key
            # they received from another member. Replacing the holder would
            # pin that member's messages on this peer, so the newcomer loses.
            raise SenderKeyError("this key id is already held by someone else")
        previous = self._peer_ids.get(peer)
        if previous is not None and previous != ident:
            self._by_id.pop(previous, None)
            self._holders.pop(previous, None)
        self._by_id[ident] = key
        self._holders[ident] = peer
        self._peer_ids[peer] = ident
        return ident

    def forget_peer(self, peer_public: bytes) -> None:
        """Drops a peer's keys when they leave the room.

        Holding on to a key that is not needed needlessly reduces what forward
        secrecy buys: as long as that key stays in memory, that peer's older
        messages remain decryptable. If the peer comes back a fresh exchange
        happens; the old key does not return.
        """
        peer = bytes(peer_public)
        self._pairs.pop(peer, None)
        ident = self._peer_ids.pop(peer, None)
        if ident is not None:
            self._by_id.pop(ident, None)
            self._holders.pop(ident, None)

    def knows(self, sender_key_id: bytes) -> bool:
        return bytes(sender_key_id) in self._by_id

    def keyed_peers(self) -> set[bytes]:
        """The peers whose sender key we were able to obtain.

        Verifying an offer means seeing an HMAC derived from the password --
        but a recorded offer can be replayed (see `core/key_agreement.py`).
        Having **opened** the wrapped key is stronger: that requires the peer
        to hold the private key matching the public key in the offer. This set
        is the answer to "does this person really belong in the room".
        """
        return set(self._peer_ids)

    def own_sender_key(self) -> bytes:
        """Our own broadcast key.

        The voice side uses this: the voice session key is derived from here
        and not from the password (`core/voice_crypto.py` ->
        `derive_voice_session_key`). That way voice inherits the forward
        secrecy of text.
        """
        return self._sender_key

    def sender_key_of(self, peer_public: bytes) -> bytes | None:
        """A peer's broadcast key; None if the handshake is not complete.

        Peers are matched by public key rather than by username: the name is
        something the server told us, the public key is something verified by a
        signature derived from the password.
        """
        ident = self._peer_ids.get(bytes(peer_public))
        return None if ident is None else self._by_id.get(ident)

    def can_read(self, token: str) -> bool:
        """Do we hold the key for this message?

        For the holding queue: it answers by looking only at the key id,
        without attempting to decrypt.
        """
        head = _head(token)
        return head is not None and head[:KEY_ID_BYTES] in self._by_id

    def key_owner(self, token: str) -> bytes | None:
        """The public key of whoever holds the key this message names.

        Our own key gives our own public key. The id is only a hint until the
        message has opened, so call this after `decrypt` succeeded: from then
        on the id is known to name the key that produced the tag.
        """
        head = _head(token)
        return None if head is None else self._holders.get(head[:KEY_ID_BYTES])

    def first_sight(self, token: str) -> bool:
        """True the first time a message is seen, False when it comes again.

        Call it only for a message that opened: recording a forgery would let
        it block the real message carrying the same nonce.
        """
        head = _head(token)
        if head is None:
            return False
        if head in self._seen:
            return False
        self._seen[head] = None
        if len(self._seen) > SEEN_MESSAGES_LIMIT:
            del self._seen[next(iter(self._seen))]
        return True

    @property
    def peer_count(self) -> int:
        """The number of peers whose key agreement is complete."""
        return len(self._pairs)

    def encrypt(self, plaintext: str) -> str:
        """Encrypts the message; the payload travels padded (`core/padding.py`).

        If the plaintext does not fit the largest rung `MessageTooLong` is
        raised -- the server would have refused that message on its length
        limit anyway.
        """
        nonce = secrets.token_bytes(NONCE_BYTES)
        ciphertext = AESGCM(self._sender_key).encrypt(
            nonce, pad(plaintext.encode("utf-8")), self._aad
        )
        ident = key_id(self._sender_key)
        return base64.urlsafe_b64encode(ident + nonce + ciphertext).decode("ascii")

    def decrypt(self, token: str) -> str:
        try:
            raw = base64.urlsafe_b64decode(token.encode("ascii"))
        except (ValueError, TypeError) as error:
            raise DecryptionError("the message could not be read") from error
        if len(raw) <= KEY_ID_BYTES + NONCE_BYTES:
            raise DecryptionError("the message is too short")
        ident = raw[:KEY_ID_BYTES]
        nonce = raw[KEY_ID_BYTES : KEY_ID_BYTES + NONCE_BYTES]
        ciphertext = raw[KEY_ID_BYTES + NONCE_BYTES :]
        key = self._by_id.get(ident)
        if key is None:
            raise UnknownSenderKey("we do not hold the key for this message")
        try:
            payload = AESGCM(key).decrypt(nonce, ciphertext, self._aad)
            return unpad(payload).decode("utf-8")
        except (InvalidTag, UnicodeDecodeError, ValueError) as error:
            raise DecryptionError("the message did not decrypt with this key") from error
