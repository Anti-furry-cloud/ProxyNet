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

"""Key derivation from a password, and marking a packet that cannot be decrypted.

**This module does not encrypt messages.** Messages are encrypted in
`core/room_session.py`: the key is derived from ephemeral X25519 keys that are
born anew each session and dropped when the session ends (forward secrecy,
THREAT_MODEL.en.md 5.1).

The job of the password-derived key today is **not to encrypt but to
authenticate**:

- `core/key_agreement.py` uses it to put an HMAC alongside the public key, so
  nobody who does not know the password can produce a valid key offer.
- The prototype path in `core/voice_crypto.py` derives its voice key from it.

The third job that stays here is to try to decrypt an incoming packet's
`content` field and, if that fails, mark it with a placeholder
(`decrypt_packet_content`). The object that does the actual cipher work is
passed in from outside; this module does not know what it is.

**What was deleted (1.10.1):** the Fernet path of 1.8.0 and earlier --
`ENCRYPTION_SCHEME` ("fernet-argon2id-v1"), `derive_room_key`, `RoomCipher`,
`make_cipher` -- was removed from this file. They had left the product path in
1.9.0 and had not been called from anywhere since; they took up most of the
file and gave the impression that "ProxyChat still encrypts with a fixed key
derived from the password". The reason for removing them is not merely
appearance: an unused encryption path is a path that may one day get wired
back in by accident. Because the scheme changed with a clean break, old
packets could not be decrypted anyway, so no capability was lost. What was
dropped, and why, is written in THREAT_MODEL.en.md 5.1.

**Why Argon2id (1.7.0):** up to 1.6.x this used PBKDF2-HMAC-SHA256. PBKDF2
only makes time expensive, and a GPU runs thousands of guesses at once.
Argon2id demands memory for each guess as well; the cost of guessing in
parallel is multiplied by that memory (THREAT_MODEL.en.md 5.8).

The parameters are the second option RFC 9106 recommends for memory-
constrained environments: t=3, p=4, m=64 MiB. Anything higher was deliberately
not chosen: the salt is derived deterministically from the room name, so
changing the parameters later breaks compatibility, and a client on some other
platform in the future (a weak computer, a phone) has to use exactly the same
parameters.
"""

from __future__ import annotations

from typing import Protocol

from cryptography.hazmat.primitives.kdf.argon2 import Argon2id


#: RFC 9106, section 4, the second recommended option.
ARGON2_ITERATIONS = 3
ARGON2_LANES = 4
ARGON2_MEMORY_KIB = 64 * 1024

#: Different from the prefix in the PBKDF2 version, so that two schemes never
#: use the same salt for the same room.
_SALT_PREFIX = b"proxynet:argon2id:room:"

#: Shown in place of a message that could not be decrypted. Internal only:
#: the interface blanks the content and writes its own localised text from
#: ``decrypt_reason``, so this string never reaches the user.
UNDECRYPTABLE_PLACEHOLDER = "[could not decrypt - different room password]"

#: Values of ``decrypt_reason`` in ``decrypt_failed`` packets.
DECRYPT_REASON_PASSWORD = "password"
DECRYPT_REASON_SCHEME = "scheme"
#: The message opened, but the name on the envelope is not the name of whoever
#: holds the key that opened it (`core/client.py` -> `_check_origin`).
DECRYPT_REASON_SENDER = "sender"


class DecryptionError(Exception):
    """The ciphertext could not be decrypted with this key."""


class Cipher(Protocol):
    """Only as much of the caller's object as `decrypt_packet_content` needs.

    Not depending on the concrete type is not merely elegance: importing
    `core/room_session.py` from this module would create a cycle (that module
    takes its key derivation from here).
    """

    #: The scheme label carried in a packet's ``enc`` field; None when there is
    #: no encryption.
    scheme: str | None

    def decrypt(self, token: str) -> str: ...


def derive_master_key(room: str, password: str) -> bytes:
    """Produces a 32-byte raw master key from a room name and password.

    This key is **not used to encrypt messages**; what is derived from it is
    the source of the signature that authenticates the other side (text) and
    of the prototype's voice key.
    """
    kdf = Argon2id(
        salt=_SALT_PREFIX + normalize_room(room).encode("utf-8"),
        length=32,
        iterations=ARGON2_ITERATIONS,
        lanes=ARGON2_LANES,
        memory_cost=ARGON2_MEMORY_KIB,
    )
    return kdf.derive(password.encode("utf-8"))


def normalize_room(room: str) -> str:
    """The form of the room name compared for the key: trimmed, case-insensitive."""
    return room.strip().casefold()


class NullCipher:
    """The pass-through (plaintext) cipher used when no password is given."""

    scheme: str | None = None

    @property
    def enabled(self) -> bool:
        return False

    def encrypt(self, plaintext: str) -> str:
        return plaintext

    def decrypt(self, token: str) -> str:
        return token


def decrypt_packet_content(packet: dict, cipher: Cipher) -> dict:
    """Decrypts an incoming packet's ``content`` field in place.

    If it cannot be decrypted, the content is replaced by the placeholder and
    ``decrypt_failed`` plus ``decrypt_reason`` are added; that way the
    interface can display something in every case, and gets a text that states
    the right reason:

    - ``scheme``: both sides encrypt, but with different schemes. It cannot be
      decrypted even when the password is the same; telling the user "the
      password differs" would be wrong.
    - ``password``: the password differs, or this side has no password at all.
    """
    content = packet.get("content")
    if not isinstance(content, str):
        return packet

    scheme = packet.get("enc")
    if scheme is None:
        # The sender sent plaintext; there is nothing to decrypt.
        return packet

    if scheme != cipher.scheme:
        reason = DECRYPT_REASON_SCHEME if cipher.scheme is not None else DECRYPT_REASON_PASSWORD
        return mark_undecryptable(packet, reason)

    try:
        packet["content"] = cipher.decrypt(content)
    except DecryptionError:
        mark_undecryptable(packet, DECRYPT_REASON_PASSWORD)
    return packet


def mark_undecryptable(packet: dict, reason: str) -> dict:
    """Replaces the content with the placeholder and records why."""
    packet["content"] = UNDECRYPTABLE_PLACEHOLDER
    packet["decrypt_failed"] = True
    packet["decrypt_reason"] = reason
    return packet
