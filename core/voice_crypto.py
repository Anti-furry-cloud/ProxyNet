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

"""End-to-end encryption of voice frames.

The Fernet we use for text is the wrong tool for voice: about 57 bytes of
fixed overhead per token, plus base64's 33% inflation on top. A 20 ms frame is
only 80-640 bytes to begin with, so that overhead is unacceptable. Fernet is
also not meant for binary data.

Voice is therefore encrypted with AES-GCM. The key chain **changed in
1.10.0** -- the password was taken out of its root for forward secrecy:

    (since 1.10.0, ForwardSecretVoiceCipher)
    room session's sender key + session salt + sender id
        --HKDF--> voice session key

    (1.9.x and earlier, VoiceCipher -- no longer on the product path)
    room password --Argon2id--> master key --HKDF--> voice key
    voice key + session salt + sender id --HKDF--> session key

Because the sender key is born anew each session and dropped when the session
ends, recorded audio cannot be opened even if the password leaks later
(THREAT_MODEL.en.md 5.1). Text and voice use the same material but do not
share a key, because HKDF's ``info`` field differs.

**Why there is a session key (the bug in v1):** in the first version every
packet was encrypted directly with the voice key and the nonce was "sender id
+ sequence number". The voice key never changed, because it was derived from
the room name and the password. When the Host restarted and handed out the
same id again, or when someone left and rejoined, the sequence number started
from zero and **the same nonce was reused with the same key.** Under AES-GCM
that reveals the XOR of the two frames' plaintexts (if one of them is a
predictable frame such as silence, the other can be read directly) and it
allows forged packets. Covered by: tests/test_voice.py, OturumAyrimiTests.

The fix: every sender generates a random 16-byte salt for each voice session
and announces it through signalling. Packets are encrypted with a key specific
to that session. Even if the sequence number resets, even if an id is handed
out again, a nonce repeat would require two sessions to draw the same salt
(1 in 2^128). Confidentiality no longer depends on sender ids being unique.
The idea comes from the per-sender keys in Discord's DAVE protocol, which are
also rotated as membership changes; this is the plain version of it.

What this design does not solve: everyone who knows the room password can
derive any sender's session key, so members of a room can forge packets in
each other's name. The situation is the same on the text side.

The nonce is never transmitted; both sides build it from the header:

    nonce = sender id (4 bytes) + sequence number (8 bytes)

The header is included in the encryption as additional authenticated data
(AAD): the Host that relays the audio can read who sent a packet but cannot
change it. The salt is not secret; the Host sees it too, but knowing the salt
does not yield the key without the password.
"""

from __future__ import annotations

import secrets
import struct
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from core.crypto import derive_master_key
from core.voice_packet import (
    HEADER_BYTES,
    MAX_SENDER_ID,
    TYPE_AUDIO,
    VoiceHeader,
    encode_header,
    pack,
    unpack,
)


#: The label of the voice encryption scheme. It names the scheme for the code
#: and the documents; it is **not** sent on the wire (an older note here said it
#: was -- checked 2026-10-24, it is not). What keeps two incompatible clients
#: apart is the key itself: a peer whose key does not open is skipped. The v1
#: version (the one without a session key) is deliberately incompatible,
#: because it was open to nonce reuse.
VOICE_ENCRYPTION_SCHEME = "aesgcm-hkdf-v2"

#: The forward-secret voice scheme (1.9.x). The key is derived not from the
#: password but from the room session's sender key; because that key is born
#: anew each session, recorded audio cannot be opened even if the password
#: leaks later (THREAT_MODEL 5.1). Deliberately incompatible with v2: the same
#: wire format but a different key source.
#: v3 -> v4 (1.13.0): nothing in this module changed, but the sender keys it
#: derives from now come out of a pair key that also depends on the password
#: (core/key_agreement.py). The label moves so the record says which keys
#: these are; in practice an older client's sender key does not open, so its
#: audio is skipped, while its text shows as "a different version".
VOICE_FORWARD_SECRET_SCHEME = "aesgcm-x25519-v4"

#: HKDF separations. If these strings change, the keys change with them.
_VOICE_KEY_INFO = b"proxynet-voice-v1"
_SESSION_KEY_INFO = b"proxynet-voice-session-v1"
_FS_SESSION_KEY_INFO = b"proxynet-voice-session-v3"

#: Length of the session salt. 128 bits: the chance of two sessions drawing
#: the same salt is zero in practice.
SESSION_SALT_BYTES = 16

#: AES-GCM's authentication tag.
GCM_TAG_BYTES = 16

#: The replay window: packets are remembered down to this far behind the
#: highest sequence number, and anything older is dropped unconditionally.
#: With 20 ms frames, 64 packets means 1.28 seconds of history -- far beyond
#: the jitter buffer's 60 ms target.
REPLAY_WINDOW_SIZE = 64

_NONCE = struct.Struct("!IQ")


class VoiceDecryptionError(Exception):
    """The voice packet did not decrypt with this room password."""


class ReplayError(VoiceDecryptionError):
    """The packet was seen before, or is old enough to fall outside the window.

    The caller should drop it silently: it may be a malicious replay, or the
    network duplicating a packet. The thing to do is the same in both cases.
    """


class UnknownSenderError(VoiceDecryptionError):
    """The session salt of the packet's sender is not known yet.

    The signalling packet may not have arrived before the voice packet; the
    caller drops the packet.
    """


class SequenceReuseError(ValueError):
    """A sequence number was about to be sealed twice in the same session.

    This is a programming error and must not pass silently: were it allowed,
    the same nonce would be reused with the same key.
    """


def derive_voice_key(room: str, password: str) -> bytes:
    """Derives a 32-byte voice key from the room password.

    It comes from the same master key as the text key, but the result differs
    because HKDF's ``info`` field does. No encryption is done with this key
    directly; it is only the source of the session keys.
    """
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=_VOICE_KEY_INFO,
    ).derive(derive_master_key(room, password))


def derive_session_key(voice_key: bytes, session_salt: bytes, sender_id: int) -> bytes:
    """A 32-byte AES-GCM key specific to one sender in one voice session."""
    _check_salt(session_salt)
    if not 0 <= sender_id <= MAX_SENDER_ID:
        raise ValueError(f"the sender id does not fit in 4 bytes: {sender_id}")
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=session_salt,
        info=_SESSION_KEY_INFO + sender_id.to_bytes(4, "big"),
    ).derive(voice_key)


def derive_voice_session_key(sender_key: bytes, session_salt: bytes, sender_id: int) -> bytes:
    """Derives a voice session key from the room session's sender key.

    The only differences from `derive_session_key` are the source and HKDF's
    ``info`` field -- but the source is what matters: there the chain has the
    password at its root, here it has a key that is regenerated every session
    and dropped when the session ends. That single change is what gives voice
    its forward secrecy.

    A separate ``info`` is essential: the same material must not yield the
    same key for text and for voice.
    """
    _check_salt(session_salt)
    if len(sender_key) != 32:
        raise ValueError("the sender key must be 32 bytes")
    if not 0 <= sender_id <= MAX_SENDER_ID:
        raise ValueError(f"the sender id does not fit in 4 bytes: {sender_id}")
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=session_salt,
        info=_FS_SESSION_KEY_INFO + sender_id.to_bytes(4, "big"),
    ).derive(sender_key)


def _check_salt(session_salt: bytes) -> None:
    if not isinstance(session_salt, (bytes, bytearray)) or len(session_salt) != SESSION_SALT_BYTES:
        raise ValueError(f"the session salt must be {SESSION_SALT_BYTES} bytes")


class ReplayWindow:
    """Sequence-number tracking with a sliding window (the approach in RFC 3711).

    ``check`` returns True for a fresh number and marks it as seen; it returns
    False for a repeated or too-old number.
    """

    def __init__(self, size: int = REPLAY_WINDOW_SIZE) -> None:
        if size < 1:
            raise ValueError("the window must be at least 1 packet")
        self._size = size
        self._mask = (1 << size) - 1
        self._highest = -1
        #: Bit i says whether packet number (_highest - i) has been seen.
        self._seen = 0

    @property
    def highest(self) -> int:
        """The highest sequence number accepted so far (-1 if there is none)."""
        return self._highest

    def check(self, sequence: int) -> bool:
        if sequence < 0:
            raise ValueError("a sequence number cannot be negative")

        if self._highest < 0:
            self._highest = sequence
            self._seen = 1
            return True

        if sequence > self._highest:
            shift = sequence - self._highest
            if shift >= self._size:
                # The jump is larger than the window: all of the old history
                # would count as "too old" anyway, so rebuilding the bitmap
                # from scratch is enough.
                self._seen = 1
            else:
                self._seen = ((self._seen << shift) | 1) & self._mask
            self._highest = sequence
            return True

        offset = self._highest - sequence
        if offset >= self._size:
            return False
        if self._seen >> offset & 1:
            return False
        self._seen |= 1 << offset
        return True

    def reset(self) -> None:
        self._highest = -1
        self._seen = 0


@dataclass
class _Sender:
    session_salt: bytes
    window: ReplayWindow
    aead: AESGCM | None


class _VoiceCipherBase:
    """The shared skeleton of the encrypting and non-encrypting versions.

    Both versions use the same wire format and the same session rules; the
    only difference is whether the body is encrypted. That way a room without
    a password behaves on the voice path exactly as it does on the text path.

    Every instance is a new voice session: it generates a random session salt
    the moment it is created. An instance must never be used for two sessions;
    someone who leaves and rejoins gets a new instance.
    """

    scheme: str | None = None

    def __init__(self, sender_id: int) -> None:
        if not 0 <= sender_id <= MAX_SENDER_ID:
            raise ValueError(f"the sender id does not fit in 4 bytes: {sender_id}")
        self.sender_id = sender_id
        #: Announced to the others through signalling (voice_join). Not secret.
        self.session_salt = secrets.token_bytes(SESSION_SALT_BYTES)
        self._last_sequence = -1
        self._own_aead = self._session_aead(sender_id, self.session_salt)
        self._senders: dict[int, _Sender] = {}
        # So that our own packet can still be decrypted if the relay loop
        # sends it back to us.
        self._senders[sender_id] = _Sender(self.session_salt, ReplayWindow(), self._own_aead)

    def add_sender(
        self, sender_id: int, session_salt: bytes, sender_key: bytes | None = None
    ) -> None:
        """Records a sender's session salt (when voice_peers arrives).

        If the same sender turns up with a new salt, that is a new session: the
        old key and replay window are discarded. Recorded packets from the old
        session cannot be decrypted with the new key.

        ``sender_key`` is used only by the forward-secret version: it is that
        sender's broadcast key in the room session. It is ignored by the
        password-derived version, where it is meaningless.
        """
        _check_salt(session_salt)
        self._remember_key(sender_id, sender_key)
        session_salt = bytes(session_salt)
        if sender_id == self.sender_id:
            if session_salt != self.session_salt:
                raise ValueError(
                    f"{sender_id} is our own sender id; it cannot be recorded with "
                    "another salt (there may be an id collision)"
                )
            return
        current = self._senders.get(sender_id)
        if current is not None and current.session_salt == session_salt:
            return
        self._senders[sender_id] = _Sender(
            session_salt, ReplayWindow(), self._session_aead(sender_id, session_salt)
        )

    def _remember_key(self, sender_id: int, sender_key: bytes | None) -> None:
        """Outside the forward-secret version no key material is kept."""

    def forget(self, sender_id: int) -> None:
        """Discards a sender's key and replay window when they leave the room."""
        if sender_id != self.sender_id:
            self._senders.pop(sender_id, None)

    def seal(self, audio: bytes, sequence: int, timestamp_ms: int) -> bytes:
        """Turns a voice frame into a datagram ready to send.

        Sequence numbers must be strictly increasing within this session; the
        same or a lower number raises ``SequenceReuseError``.
        """
        if sequence <= self._last_sequence:
            raise SequenceReuseError(
                f"sequence number {sequence} cannot be used in this session "
                f"(the last one used was {self._last_sequence}); the nonce would repeat"
            )
        header = encode_header(self.sender_id, sequence, timestamp_ms, TYPE_AUDIO)
        body = self._protect(self._own_aead, sequence, header, audio)
        datagram = pack(header, body)
        self._last_sequence = sequence
        return datagram

    def open(self, datagram: bytes) -> tuple[VoiceHeader, bytes]:
        """Turns an incoming datagram into a (header, voice frame) pair.

        A packet we sent ourselves is still decrypted if it comes back (the
        relay loop); filtering it out is the caller's job.
        """
        header, body = unpack(datagram)
        sender = self._senders.get(header.sender_id)
        if sender is None:
            raise UnknownSenderError(
                f"the session salt of sender {header.sender_id} is not known"
            )
        # Decrypt first, update the window afterwards: a forged packet must not
        # advance the window and cause real packets to be dropped.
        audio = self._unprotect(sender.aead, header, datagram[:HEADER_BYTES], body)
        if not sender.window.check(header.sequence):
            raise ReplayError(
                f"packet {header.sequence} from sender {header.sender_id} "
                "has been seen before"
            )
        return header, audio

    def _session_aead(self, sender_id: int, session_salt: bytes) -> AESGCM | None:
        raise NotImplementedError

    def _protect(self, aead: AESGCM | None, sequence: int, header: bytes, audio: bytes) -> bytes:
        raise NotImplementedError

    def _unprotect(
        self, aead: AESGCM | None, decoded: VoiceHeader, header: bytes, body: bytes
    ) -> bytes:
        raise NotImplementedError


class VoiceCipher(_VoiceCipherBase):
    """Encrypts with session keys derived from the password -- **the prototype path**.

    The product does not use this class; since 1.10.0 the product's voice
    cipher is `ForwardSecretVoiceCipher`. This class stays for
    `tools/ses_prototip.py`: the measurement tool works with the
    password-derived scheme and has to stay compatible with the five records
    of Phase 0 v2, so it cannot be changed.

    **It has no forward secrecy:** because the key is derived from the
    password, anyone who obtains the password later can open audio they
    recorded (THREAT_MODEL.en.md 5.1). The prototype is not distributed and is
    not used for real conversations.
    """

    scheme = VOICE_ENCRYPTION_SCHEME

    def __init__(self, room: str, password: str, sender_id: int) -> None:
        self.room = room
        self._voice_key = derive_voice_key(room, password)
        super().__init__(sender_id)

    @property
    def enabled(self) -> bool:
        return True

    def _session_aead(self, sender_id: int, session_salt: bytes) -> AESGCM:
        return AESGCM(derive_session_key(self._voice_key, session_salt, sender_id))

    def _protect(self, aead: AESGCM | None, sequence: int, header: bytes, audio: bytes) -> bytes:
        return aead.encrypt(_NONCE.pack(self.sender_id, sequence), audio, header)

    def _unprotect(
        self, aead: AESGCM | None, decoded: VoiceHeader, header: bytes, body: bytes
    ) -> bytes:
        try:
            return aead.decrypt(_NONCE.pack(decoded.sender_id, decoded.sequence), body, header)
        except InvalidTag as error:
            raise VoiceDecryptionError(
                "the voice packet did not decrypt: a different room password, a stale "
                "session salt, or a modified header"
            ) from error


class SenderKeyMissingError(ValueError):
    """We do not hold that sender's room session key yet.

    The handshake on the text side may finish after they join voice; this is a
    passing state, not an error. The caller should retry once the key arrives.
    """


class ForwardSecretVoiceCipher(_VoiceCipherBase):
    """Derives the voice session key from the room session's sender key.

    It uses the same wire format as `VoiceCipher`; the only difference is where
    the key comes from. There the chain had the password at its root, so
    recorded audio could be opened if the password leaked later
    (THREAT_MODEL 5.1). Here the root is a key that is regenerated every
    session and dropped when the session ends.

    Whose key to use is matched **not by username** but by that person's
    ephemeral public key; the name is something the server told us, while the
    public key is something verified by a signature derived from the password.
    The caller does the matching and hands the key to `add_sender`.
    """

    scheme = VOICE_FORWARD_SECRET_SCHEME

    def __init__(self, own_sender_key: bytes, sender_id: int) -> None:
        if len(own_sender_key) != 32:
            raise ValueError("the sender key must be 32 bytes")
        self._own_key = bytes(own_sender_key)
        self._keys: dict[int, bytes] = {}
        super().__init__(sender_id)

    @property
    def enabled(self) -> bool:
        return True

    def _remember_key(self, sender_id: int, sender_key: bytes | None) -> None:
        if sender_id == self.sender_id:
            return
        if sender_key is None:
            raise SenderKeyMissingError(
                f"no room session key for {sender_id}; waiting for the text handshake"
            )
        if len(sender_key) != 32:
            raise ValueError("the sender key must be 32 bytes")
        self._keys[sender_id] = bytes(sender_key)

    def forget(self, sender_id: int) -> None:
        super().forget(sender_id)
        if sender_id != self.sender_id:
            self._keys.pop(sender_id, None)

    def _session_aead(self, sender_id: int, session_salt: bytes) -> AESGCM:
        key = self._own_key if sender_id == self.sender_id else self._keys.get(sender_id)
        if key is None:
            raise SenderKeyMissingError(f"no room session key for {sender_id}")
        return AESGCM(derive_voice_session_key(key, session_salt, sender_id))

    def _protect(self, aead: AESGCM | None, sequence: int, header: bytes, audio: bytes) -> bytes:
        return aead.encrypt(_NONCE.pack(self.sender_id, sequence), audio, header)

    def _unprotect(
        self, aead: AESGCM | None, decoded: VoiceHeader, header: bytes, body: bytes
    ) -> bytes:
        try:
            return aead.decrypt(_NONCE.pack(decoded.sender_id, decoded.sequence), body, header)
        except InvalidTag as error:
            raise VoiceDecryptionError(
                "the voice packet did not decrypt: the sender's session key differs, "
                "the session salt is stale, or the header was modified"
            ) from error


class NullVoiceCipher(_VoiceCipherBase):
    """The pass-through version used in rooms without a password.

    The same choice as ``NullCipher`` on the text side: no password, no
    encryption. Because the wire format and the session rules do not change,
    the jitter buffer, the signalling and the relay code stay the same.
    """

    scheme = None

    @property
    def enabled(self) -> bool:
        return False

    def _session_aead(self, sender_id: int, session_salt: bytes) -> None:
        return None

    def _protect(self, aead: AESGCM | None, sequence: int, header: bytes, audio: bytes) -> bytes:
        return audio

    def _unprotect(
        self, aead: AESGCM | None, decoded: VoiceHeader, header: bytes, body: bytes
    ) -> bytes:
        return body


def make_voice_cipher(
    room: str,
    password: str | None,
    sender_id: int,
    own_sender_key: bytes | None = None,
    *,
    allow_password_scheme: bool = False,
) -> ForwardSecretVoiceCipher | VoiceCipher | NullVoiceCipher:
    """Picks the voice cipher that suits the session.

    - No password, no encryption (`NullVoiceCipher`).
    - If the room session's sender key is supplied, the **forward-secret**
      version (`ForwardSecretVoiceCipher`) -- this is the product's path.
    - A password but no key is an **error**, unless `allow_password_scheme` is
      given explicitly.

    The last point is deliberate: silently falling back to the
    password-derived version whenever the key happens to be unavailable would
    mean switching forward secrecy off without telling anyone. Such a fallback
    is exactly what we reject (see ProxyNull's "no mode negotiation"
    decision). The only caller that passes the flag is
    `tools/ses_prototip.py`: there is no room session there, the measurement
    tool works with the password-derived scheme, and it has to stay compatible
    with the Phase 0 records.
    """
    if not password:
        return NullVoiceCipher(sender_id)
    if own_sender_key is not None:
        return ForwardSecretVoiceCipher(own_sender_key, sender_id)
    if not allow_password_scheme:
        raise SenderKeyMissingError(
            "the room session's sender key was not supplied; falling back to the "
            "password-derived scheme requires allow_password_scheme=True"
        )
    return VoiceCipher(room, password, sender_id)
