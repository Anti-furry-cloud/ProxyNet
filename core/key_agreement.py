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

"""Ephemeral key agreement: the crypto layer of forward secrecy.

The root of the earlier design was this: the encryption key was a function of
the password (`core/crypto.py` -> `derive_master_key`). Because the password
is fixed, so was the key; recorded traffic could be opened retroactively if
the password leaked in the future (THREAT_MODEL.en.md 5.1).

This module makes the trade:

- The **encryption key** is born from **ephemeral** X25519 keys regenerated
  every session. It is never written to disk and is dropped when the session
  ends.
- The **password** is no longer the encryption key but an **authenticator**:
  an HMAC derived from the password is placed alongside the public key.
  Nobody who does not know the password can produce a valid offer.

So even if the password is captured later, old traffic stays closed: what the
adversary needs is the ephemeral private keys, and those are gone.

## The flow

1. Each client generates an ephemeral key pair at the start of a session.
2. It announces its public key together with the HMAC derived from the
   password (`offer`).
3. It verifies the other side's offer (`verify_offer`) and computes the
   **pair key** with Diffie-Hellman (`pair_key`). Both sides arrive at the
   same value.
4. Each client generates a random **sender key** once per session
   (`new_sender_key`), wraps it for every peer with the pair key
   (`wrap_sender_key`) and broadcasts its messages under that key.

The fourth step is what makes a group work: with pair keys alone, every
message would have to be encrypted once per recipient. The sender-key pattern
(the one Signal and WhatsApp use for group chat) brings that down to once.

The server only carries these packets. Because all of the Diffie-Hellman
happens on the clients, the server has **no** ability to compute the shared
secret; the rule that the server chain does not import `cryptography` is not
broken.

## What it does not solve -- the honest limits

- **A weak password.** Anyone who sees an offer's HMAC can mount an offline
  dictionary attack; if they find the password they can impersonate that
  session's agreement. This is not a regression against the earlier state
  (the same attack works from the ciphertext) but it is not an improvement
  either. The real answer is PAKE (see `apps/proxynull/PROTOCOL.en.md` 3).
- **An active man in the middle who knows the password.** Because the
  password is a shared secret, anyone who knows it can produce a valid HMAC
  and therefore interpose. They are free to enter the room anyway
  (THREAT_MODEL.en.md 5.5). ProxyNull solves this with a short verification
  code compared on every session; ProxyChat does not.
- **Memory.** In Python `bytes` are immutable and cannot be reliably zeroed.
  The mathematics gives perfect forward secrecy, the runtime does not:
  protection against someone seizing the device's memory is **partial.**
- **Replay of an old offer.** An adversary can resend an offer they recorded,
  and the HMAC will be valid. But they do not hold the matching private key,
  so what comes out is a key nobody can use -- at worst denial of service,
  not a leak.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)

#: An X25519 public key is always 32 bytes.
PUBLIC_KEY_BYTES = 32
#: The offer's HMAC-SHA256 tag.
OFFER_MAC_BYTES = 32
#: The sender key (for AES-256-GCM).
SENDER_KEY_BYTES = 32
#: The AES-GCM nonce. Wrapping generates a fresh one every time.
WRAP_NONCE_BYTES = 12

_OFFER_MAC_CONTEXT = b"proxynet-offer-v1"
_PAIR_KEY_INFO = b"proxynet-pair-v1"
_SENDER_KEY_WRAP_INFO = b"proxynet-sender-key-v1"


class OfferError(Exception):
    """The offer could not be verified: a different password, or a corrupt packet."""


class SenderKeyError(Exception):
    """The sender key could not be unwrapped."""


def offer_mac(public_key: bytes, master_key: bytes, room: str) -> bytes:
    """Signs the public key with the key derived from the password.

    The room name goes into the signature too, so that an offer derived from
    the same password cannot be carried over to another room.
    """
    _check_public(public_key)
    message = _OFFER_MAC_CONTEXT + room.encode("utf-8") + b"\x00" + public_key
    return hmac.new(master_key, message, hashlib.sha256).digest()


def verify_offer(public_key: bytes, mac: bytes, master_key: bytes, room: str) -> None:
    """Verifies the offer; raises `OfferError` if it is invalid.

    The comparison is constant time: `hmac.compare_digest`.
    """
    if len(public_key) != PUBLIC_KEY_BYTES:
        raise OfferError(f"the public key must be {PUBLIC_KEY_BYTES} bytes")
    if len(mac) != OFFER_MAC_BYTES:
        raise OfferError(f"the tag must be {OFFER_MAC_BYTES} bytes")
    if not hmac.compare_digest(mac, offer_mac(public_key, master_key, room)):
        raise OfferError("the offer could not be verified with this room password")


def new_sender_key() -> bytes:
    """The broadcast key, generated once per session."""
    return secrets.token_bytes(SENDER_KEY_BYTES)


def wrap_sender_key(pair_key: bytes, sender_key: bytes) -> bytes:
    """Wraps the sender key with the pair key: nonce + ciphertext."""
    if len(sender_key) != SENDER_KEY_BYTES:
        raise ValueError(f"the sender key must be {SENDER_KEY_BYTES} bytes")
    nonce = secrets.token_bytes(WRAP_NONCE_BYTES)
    return nonce + AESGCM(pair_key).encrypt(nonce, sender_key, _SENDER_KEY_WRAP_INFO)


def unwrap_sender_key(pair_key: bytes, wrapped: bytes) -> bytes:
    """Unwraps a wrapped sender key; raises `SenderKeyError` if it is broken."""
    if len(wrapped) <= WRAP_NONCE_BYTES:
        raise SenderKeyError("the wrapped key is too short")
    nonce, ciphertext = wrapped[:WRAP_NONCE_BYTES], wrapped[WRAP_NONCE_BYTES:]
    try:
        opened = AESGCM(pair_key).decrypt(nonce, ciphertext, _SENDER_KEY_WRAP_INFO)
    except InvalidTag as error:
        raise SenderKeyError("the sender key did not open with this pair key") from error
    if len(opened) != SENDER_KEY_BYTES:
        raise SenderKeyError("the sender key has an unexpected length")
    return opened


class EphemeralKey:
    """The session's ephemeral X25519 key pair.

    It lives in memory only. When the object is dropped the private key goes
    with it; since Python offers no zeroing guarantee we claim no more than
    that (see the limits at the top of this module).
    """

    def __init__(self, private_key: X25519PrivateKey | None = None) -> None:
        self._private = private_key if private_key is not None else X25519PrivateKey.generate()
        self.public_key = self._private.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )

    def offer(self, master_key: bytes, room: str) -> bytes:
        """The tag for our own public key."""
        return offer_mac(self.public_key, master_key, room)

    def pair_key(self, peer_public: bytes) -> bytes:
        """The pair key shared with the other side.

        Both sides must arrive at the same value, which is why the two public
        keys enter the HKDF salt **sorted**. Without sorting, each side would
        put its own key first and use a different salt.
        """
        _check_public(peer_public)
        if peer_public == self.public_key:
            raise OfferError("cannot agree with our own public key")
        try:
            shared = self._private.exchange(X25519PublicKey.from_public_bytes(peer_public))
        except ValueError as error:
            # A low-order point gives an all-zero secret, which the library
            # refuses with ValueError. Left as it was, it escaped the client's
            # handlers and closed the connection of whoever received it.
            raise OfferError("the public key does not give a usable shared secret") from error
        salt = b"".join(sorted((self.public_key, peer_public)))
        return HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=_PAIR_KEY_INFO,
        ).derive(shared)


def _check_public(public_key: bytes) -> None:
    if not isinstance(public_key, (bytes, bytearray)) or len(public_key) != PUBLIC_KEY_BYTES:
        raise OfferError(f"the public key must be {PUBLIC_KEY_BYTES} bytes")
