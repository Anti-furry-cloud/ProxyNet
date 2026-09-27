[Türkçe](THREAT_MODEL.md) · **English**

# ProxyNet — Threat Model

> **Scope:** This document defines the goal of **ProxyNull**
> (`apps/proxynull/`). ProxyChat (`apps/proxychat/`) is optimised for everyday
> use and makes **no claim** of protection against the T5 adversary; for it,
> the guarantees in section 4 apply and the gaps in section 5 are permanent.

This document defines **why** ProxyNet exists and the standard it is measured
against. The goal is not merely for a group of friends to chat; the goal is
that **messages cannot be read by anyone — including the person running the
server and a state-level adversary.**

Every new feature is measured against this document. A feature that violates
its principles is rejected, however useful it may be.

> **Today's status, in one sentence:** ProxyNet protects message content
> against the server and against third parties who cannot enter the room; it
> **does not protect against a state-level adversary.** The difference is
> listed explicitly in section 5, and the order in which it gets closed in
> section 8. Until those gaps are closed, no claim to the contrary should be
> made.

---

## 1. Assets being protected

| Priority | Asset | Today's status |
| --- | --- | --- |
| 1 | Message content | End-to-end encrypted |
| 2 | Confidentiality of past messages (if the password later leaks) | **Protected** — text 1.9.0, voice 1.10.0 |
| 3 | Who talks to whom (metadata) | **Not protected** |
| 4 | Usernames, room names | **Not protected** |
| 5 | When someone is online | **Not protected** |

---

## 2. Adversary model

| # | Adversary | Capability | Where we stand |
| --- | --- | --- | --- |
| T1 | A curious person on the same local network | Can connect to the port, can sniff traffic | **Partial** — cannot read content but can join the room |
| T2 | The person running the server (host) | Sees everything passing through the server | **Good** — never sees plaintext |
| T3 | Passive on-path observer (ISP, VPN provider) | Records traffic | **Partial** — content safe, metadata exposed |
| T4 | Active network attacker | Injects, drops, alters packets | **Weak** — messages cannot be forged, but envelope packets (errors, user lists) can be |
| T5 | State-level adversary | Stores traffic for years, seizes devices, applies legal compulsion | **Not met** — forward secrecy is in place (text 1.9.0, voice 1.10.0) but metadata and the transport are still exposed |

**T5 is the reason this document exists, and it is not currently met.** We
write this knowingly; the project has not reached its goal.

---

## 3. Out of scope

These threats cannot be solved by ProxyNet and must not be pretended otherwise:

- **Compromise of the endpoint.** Keyloggers, screenshots, memory dumps, the
  person looking over your friend's shoulder. Encryption protects the message
  on the network, not on the screen.
- **The channel used to share the room password.** If you send the password
  over WhatsApp, the chain breaks there. It should be shared face to face or
  through a separate secure channel.
- **The user's choice of password.** Since 1.9.0 the password is not the key
  that encrypts text (5.1), but it is the key of the signature that proves the
  other side belongs to the room — and the voice key is still derived from it. A
  guessable password opens the door both to an offline dictionary attack and to
  getting in between.
- **Security of the layers below** (operating system, VPN client, hardware).

---

## 4. Guarantees given today

All of these are tested (`tests/test_crypto.py`, `tests/test_hardening.py`):

- **The server never sees plaintext.** Encryption and decryption happen only on
  the client. The server chain (`core/server.py`, `core/hub.py`,
  `core/transport.py`, `core/protocol.py`, `core/server_state.py`) does not even
  import `cryptography` — the server has no ability to decrypt, and that
  absence is by design.
- **The server keeps no history in an encrypted room** (1.9.0). In a room
  without a password, history lives in memory only and never on disk.
- **Content cannot be opened with the wrong password**; the user sees a
  placeholder instead of plaintext.
- **Tampered ciphertext is rejected.** Since 1.9.0 text chat uses AES-256-GCM
  (before that Fernet, i.e. AES-128-CBC + HMAC-SHA256); both are authenticated
  encryption, so an adversary cannot silently alter message content.
- **No third-party dependency on the server side** — attack surface and supply
  chain risk are small.
- Limits against resource exhaustion: 64 KiB per packet, 8 KiB per message,
  20 messages per 10 seconds, at most 50 clients, 120-second idle timeout.

Gaps from section 5 that have been closed (the detail and the remaining
limits stay there):

- **Forward secrecy: the key is born again every session** (5.1; text 1.9.0,
  voice 1.10.0) — `tests/test_key_agreement.py`, `tests/test_room_session.py`,
  `tests/test_forward_secrecy.py`, `tests/test_voice_forward_secrecy.py`,
  `tests/test_crypto.py` → `ForwardSecrecyTests`.
- **The user list is verified by proof; the server's claim is not trusted**
  (5.4-B, 1.9.0) — `tests/test_verified_users.py`.
- **No history is kept at all in an encrypted room** (5.2, 1.9.0) —
  `tests/test_forward_secrecy.py`.
- **Room history is off by default** (5.2, 1.7.0) —
  `tests/test_settings.py` → `HistoryDefaultTests`.
- **The key is derived with Argon2id** (5.8, 1.7.0) —
  `tests/test_crypto.py` → `Argon2idTests`.
- **The network the host listens on is picked by hand at every start**
  (5.6, 1.6.2) — `tests/test_listen_address.py`.
- **The event log does not record message length** (5.3, 1.5.0) —
  `tests/test_logging_and_scroll.py`.

---

## 5. Guarantees NOT given today

These are known and accepted gaps. Until they are closed, it **must not** be
said that ProxyNet is at a "the state cannot read it" level.

### 5.1 Forward secrecy — closed (text 1.9.0, voice 1.10.0)

**Before:** the key was derived deterministically from the (room name +
password) pair and never changed. Recorded encrypted traffic could be **fully
decrypted retroactively** if the password was obtained by any means in the
future. This is precisely the standard method of state-level adversaries:
*record now, decrypt later*.

**Closed for text chat (1.9.0).** The encryption key no longer comes from the
password: every session generates an ephemeral X25519 key pair, the public keys
are exchanged between the endpoints, and the private keys are dropped when the
session ends. The password's new job is not to encrypt but to **authenticate**
the other side: an HMAC derived from it travels next to the public key, and the
room name goes into that signature too. Groups use the sender-key pattern — each
participant generates one broadcast key per session and sends it to every peer
wrapped under the pairwise key, exactly as Signal and WhatsApp do for group chat.

The result: even if the password leaks months later, recorded **text** traffic
cannot be opened. The server only carries these packets and never looks inside;
because all of the Diffie-Hellman happens at the endpoints, the server **has no
ability** to compute the shared secret, and the rule that the server chain does
not import `cryptography` is unbroken (a test locks that down with the AST).

Code: `core/key_agreement.py`, `core/room_session.py`. Tests:
`tests/test_key_agreement.py`, `tests/test_room_session.py`,
`tests/test_forward_secrecy.py`, `tests/test_crypto.py` → `ForwardSecrecyTests`.

**Closed for voice too (1.10.0).** The voice session key is now also derived
from the room session's sender key rather than from the password. The text-side
work was the rehearsal, and the same material is used — the only difference is
HKDF's `info` field, so that the same key material does not yield the same key
for text and for voice.

Whose key a voice stream is derived from is matched **not by username** but by
that person's ephemeral public key: the name is something the server says, the
public key is something proved by a signature derived from the password. A
public-key field was added to the `voice_join` and `voice_peers` packets for
this; the server merely carries it and does not know what it means.

The ordering problem is handled too: the text handshake can finish after the
voice join. In that case the peer is skipped silently and the participant list
is processed again once the key arrives — a missing key is a transient state,
not an error. The scheme label is `aesgcm-x25519-v3`, deliberately incompatible
with the old `aesgcm-hkdf-v2`. Code: `core/voice_crypto.py` →
`derive_voice_session_key`, `ForwardSecretVoiceCipher`. Tests:
`tests/test_voice_forward_secrecy.py`.

**Still open — weak passwords.** Anyone who sees the offer's HMAC can mount an
offline dictionary attack; if they find the password they can impersonate that
session's exchange. This is not a regression (the same attack was available
against the ciphertext) but it is not an improvement either. The real fix is a
PAKE (see section 3 of `apps/proxynull/PROTOCOL.en.md`).

**Still open — an active man in the middle who knows the password.** Because the
password is a shared secret, anyone holding it can produce a valid HMAC and
therefore get in between. Joining the room is free anyway (5.5). ProxyNull solves
this with a short verification code compared on every session; ProxyChat does not.

**Still open — memory.** In Python `bytes` are immutable and cannot be zeroed
reliably. The mathematics gives perfect forward secrecy, the runtime does not:
protection against seizure of the device's memory is **partial**.

**Absent by choice — self-healing.** Signal's Double Ratchet adds
post-compromise security on top of forward secrecy: even after a device is
compromised once, later messages recover. ProxyNet has no equivalent, and in
group chat sender keys do not provide it anyway. It is not required for the
"record now, decrypt later" threat, which is why it is deferred — not hidden.

### 5.2 History is handed out without authentication — off by default (1.7.0)

While history is on, the server sends up to the last 100 messages to **everyone** who
joins a room (`core/server.py` → `_send_room_history`), and no password is
required to join. Someone who does not know the password can enter a room,
collect 100 encrypted messages and take them away for an offline attack.
Combined with 5.1 this is a serious combination.

Since 1.7.0 history is **off by default**: the server keeps no messages in
memory and sends no history packet to people who join. Because the older version
wrote the default value to the settings on every connection, changing the
default alone would not have affected any existing user; on upgrade the stored
value is deleted once (`apps/proxychat/settings.py` →
`_migrate_privacy_defaults`). Tests: `tests/test_settings.py` →
`HistoryDefaultTests`.

With history off, the client keeps the messages the user **has already seen**
in this session in memory only, so they come back when the user returns to a
room (at most 200 per room; not written to disk, dropped when the session
ends). This creates no new recipient: the same messages were already on that
device's screen, and compromise of the endpoint is out of scope (section 3).
Tests: `tests/test_proxychat_ui.py` → `RoomMemoryTests`.

**Closed completely for encrypted rooms (1.9.0).** With forward secrecy,
encrypted messages are **never written** to history: a later joiner — even the
message's own author — cannot decrypt them anyway, while keeping them would leave
the door open for someone without the password to enter the room, collect 100
ciphertexts and take them offline. History keeps working unchanged in rooms
without a password; there is nothing to hide there. Decided 2026-09-27, the
product owner's choice. Test: `tests/test_forward_secrecy.py`.

Remaining limit: if the host **deliberately turns history on**, the gap is
exactly as before. The only way to close it is to send history only to clients
that prove they know the room password, which requires authentication for
entering a room (5.4, 5.5).

### 5.3 Metadata is fully exposed

Usernames, room names, timestamps, message sizes and who is online at what time
travel in plaintext. For an adversary at this scale, metadata is often more
valuable than content.

~~In addition, the server's event log records the **length** of the
ciphertext.~~ **Closed (1.5.0).** Since that version the server does not pass
message content to the event log; a test verifies that the log of a real
session contains no length: `tests/test_logging_and_scroll.py`. This document
was not updated at the time. The logging helper itself kept the ability to
write the length if given content until 1.7.0; that was removed too, so the
leak cannot come back if a call passes content again
(`tests/test_core.py` → `test_anonymous_logger_masks_user_identity`). Packet
sizes on the wire are still exposed (5.7).

**Voice chat metadata (Phase 1b, 2026-09-24).** The server now knows who
joined voice chat and when they left, and announces it to the room with
`voice_peers` (username, sender id and session salt — **no IP**). Because it
relays, it also sees participants' IPs, but it already saw those in text
chat. **It cannot see who is speaking:** the audio stream goes out at a
constant rate and a constant size whether anyone speaks or not. Audio content
is not decrypted on the server; the relay code does not import
`cryptography`, and a test locks that down (`tests/test_voice_relay.py`). The
audio packet's header (version, type, sender id, sequence number, timestamp)
travels in the clear; it is needed for routing and cannot be altered, since
it is also the authentication data.

**The noise gate adds no metadata (1.8.0).** The noise gate mutes the
microphone when nobody is speaking, but it does not stop the stream: the frame
still goes out, only its contents become silence. Packet size is independent of
content — 60 bytes per Opus frame, 320 for µ-law; digital silence comes out the
same size. Constant bit rate and disabled DTX were chosen for exactly this
reason. The result: **muting and the gate closing are indistinguishable on the
wire** — both send silence of the same size. The two-frame lookahead that saves
the beginnings of words does not change the packet count either: one packet per
frame. The level meter and threshold slider in the interface are local; the
measured level never goes to the network, and the threshold is stored only on
the user's own machine. Tests: `tests/test_voice_opus.py` →
`test_paket_boyu_sese_gore_degismiyor`, `tests/test_voice_gate.py` →
`OnBakisTests`.

1.7.0 **added** one piece of metadata: when someone leaves a room by switching
to another room, the server tells the people who stay, and the interface shows
"went to another room". The destination room is not sent. Those in the room
therefore learn that the person did not disconnect and is still on the server;
before, this could only sometimes be inferred from changes in the room list.
This was accepted deliberately: separate "left/joined" lines made someone
switching rooms look as if they kept dropping and reconnecting. Tests:
`tests/test_hardening.py` → `RoomMoveSnapshotTests`.

### 5.4 The transport layer is unencrypted — two separate problems

The packet envelope (`type`, `room`, `user`, `ts`, `enc`) travels in the clear.
Inside that sit **two** problems with different fixes, different costs and
different adversaries; as long as they were written as one item, both were
mispriced.

**A — Confidentiality: the envelope is readable on the path.** The room name,
usernames and timestamps are visible to a passive listener on the path (T3) and
to someone on the same local network (T1). The only way to close this is an
encrypted channel between client and server. **Deferred**, for the reasons in
section 8: a channel forces the server to do cryptography, which costs two
concrete guarantees from section 4 (the server chain imports no `cryptography`;
there is no third-party dependency on the server side). And part of its benefit
is already covered by the intended deployment: when the connection runs inside a
VPN, a listener on the path sees encrypted VPN traffic rather than plain JSON.
**Even with a channel the host still sees everything** — the metadata gap (5.3)
is independent of this.

**B — Integrity: the envelope can be forged.** An active attacker cannot forge
message content (content is protected by authenticated encryption) but can
inject a fake user list or error packet, and can drop packets. And the real
source of those packets is the server anyway: "what if the server lies" is not
closed by a channel, which only keeps the network out.

The more important half of B was closed in 1.9.0 **without touching the
server.** A username is now bound to that person's ephemeral public key: if a
name shows as verified, that person produced a valid signature derived from the
password **and** demonstrated they hold the private key matching the public key
in it (by sending their wrapped sender key in a form that opens). A name the
server invents, or one injected into the network, cannot do that and appears as
unverified in the interface. The proof comes from the key exchange, not from the
server — the server no longer has **the last word** on who is in the room.
Code: `core/client.py` → `verified_users`, `core/room_session.py` →
`keyed_peers`. Tests: `tests/test_verified_users.py`. Beyond the tests it was
also **checked by hand** (2026-09-27, two windows): peers with the same
password carry no marker, a peer with a different or missing password shows as
unverified, and an undecryptable message arrives as a placeholder without any
wait.

Remaining limit: the server can still drop packets, and a forged
`room_snapshot` can push clients into dropping their keys. That is denial of
service, not a leak, and it heals itself: the same packet also triggers a fresh
key announcement, so the exchange is re-established immediately.

### 5.5 Room entry is open

There is no authentication on the server; anyone who can reach the port joins a
room and sees the user list and the rhythm of the traffic. This is a deliberate
decision (see section 7) but **must be re-evaluated** if the server is moved to
a publicly reachable address.

### 5.6 The server listened on all network interfaces — closed (1.6.2)

Host mode used to bind to `0.0.0.0`, meaning it listened not only on the VPN
interface but also on the home/café network and on virtual adapters. Using a
VPN did not fix this.

Since 1.6.2 the network to listen on is **picked by hand from a list** every
time Host is started; there is no default and the choice is not stored. "All
networks" can still be picked, but as a deliberate choice. Demo mode listens on
`127.0.0.1` only.

Since 1.6.3 the port is **reserved exclusively** for the server on Windows
(`SO_EXCLUSIVEADDRUSE`). The `SO_REUSEADDR` used before let a second server
open on the same port without an error, and, while Host listened on "All
networks", let another program listen on `127.0.0.1:<port>` and take over
Host's own connection.

Remaining limit: the choice is tied to an IP address, not to a network adapter.
If that address disappears from the computer (for example, Hamachi is turned
off), Host has to be started again.

### 5.7 Message length leaks

The length of the ciphertext correlates with the length of the plaintext. Since
1.9.0 the relation is at **byte granularity**: AES-GCM is a stream mode, so it
carries the length exactly. Before that, Fernet's 16-byte block granularity
applied, which means this gap has in fact **grown** a little — a small price paid
for forward secrecy, and one that closes separately, with padding. No padding is
applied. Voice does not have this problem: frames go out at a fixed size.

### 5.8 PBKDF2, not Argon2id — closed (1.7.0)

240,000 iterations of PBKDF2-HMAC-SHA256 is reasonable at a consumer level but
parallelises on GPUs. Argon2id is memory-hard and makes attacks with dedicated
hardware far more expensive.

Since 1.7.0 the key is derived with **Argon2id**: the second option RFC 9106
recommends for memory-constrained environments, 3 passes, 4 lanes, 64 MiB
(`core/crypto.py`). Every password guess needs 64 MiB of memory, which breaks the
thousands of parallel guesses that make GPUs effective against PBKDF2. A
known-answer vector locks the parameters, the salt and the room name
normalisation (`tests/test_crypto.py` → `Argon2idTests`).

Argon2id's **job changed in 1.9.0**: the key it derives no longer encrypts
messages, it is the key of the signature that proves the other side belongs to
the room (and the voice key is derived from it, 5.1). That is why text chat's
scheme label is now `aesgcm-x25519-v1`; the label `fernet-argon2id-v1` belongs to
1.8.0 and earlier.

Higher memory was deliberately not chosen: because the salt is deterministic,
changing the parameters breaks compatibility again, and a future client on
another platform has to use exactly the same parameters.

The cost is compatibility: 1.7.0 cannot talk to 1.6.x in encrypted rooms.
Remaining limit: Argon2id makes guessing expensive, not impossible. Because the
salt comes from the room name, the same room name and password yield the same
key everywhere; a weak password can still be cracked offline (see section 3,
5.1).

### 5.9 The distribution chain is unprotected

The distributed `.exe` is unsigned and shared via a cloud link. An adversary
could deliver a modified binary to a user. There are no reproducible builds and
no signing.

One step was taken (2026-09-25): the SHA-256 checksums of the distributed
files are published (`tools/surum_ozetleri.py` produces them). Whoever
downloads can compare the checksum of their file. This does NOT replace
signing: if someone who takes over the distribution link can also change the
checksum list, the check collapses. The real fix is a reproducible, signed
build.

---

## 6. Design principles

Every new feature is measured against these.

1. **The server never sees plaintext.** No feature that gives the server the
   ability to decrypt is accepted — however useful it may be.
2. **Persistence is off by default.** Every stored byte is a pile that can be
   seized or demanded. If storage is necessary, the justification is written
   into this document.
3. **Metadata is data too.** When adding a new packet field, ask: "does this
   field reveal who is talking to whom?"
4. **Key material is never written to disk in the clear.** Conveniences such as
   remembering a password are added only with operating-system protection
   (Windows DPAPI) and only as an opt-in.
5. **Convenience does not override security.** In a conflict the default is the
   safe side; convenience is chosen explicitly (opt-in).
6. **A guarantee not written in this document is not a guarantee.** The README
   and the interface cannot promise more than the list here.

---

## 7. Rejected and deferred designs

A decision record, so the same ideas are not re-litigated.

| Design | Decision | Rationale |
| --- | --- | --- |
| 24/7 server on a VPS + persistent history written to disk | **Rejected** | Persistence creates a seizable pile; violates Principle 2 |
| Mixing audio on the server for voice chat | **Rejected** | Would require the server to decrypt audio; violates Principle 1 |
| Server access password | **Deferred** | Unnecessary in a local/VPN scenario. To be re-evaluated if the server moves to a public address (see 5.5) |
| Per-room security mode within a single product | **Rejected** | Two separate products preferred. Fewer features is itself a security property; a separate product guarantees ProxyChat's feature pressure does not contaminate ProxyNull |
| Copying the security code into both products | **Rejected** | In copied code a flaw gets fixed on one side and forgotten on the other. `core/` is shared; ProxyNull shrinks its attack surface by importing less of it |
| Relaying voice through the server (SFU, without decrypting) | **Accepted (2026-09-16)** | Relay from the start; the "only for rooms larger than 4 people" condition was dropped. The alternative, mesh, would have handed every participant's IP to everyone in the room (Principle 3); with a relay the host keeps seeing the IPs it already sees. Content stays encrypted, so Principle 1 is not violated. The relay's own unsolved problems (sender id assignment, authentication towards the host) are in section 9 of the voice chat plan |
| A separate CLI program that only carries voice | **Deferred** | The tester's suggestion (2026-09-17): a separate program that runs from the command line like the prototype and carries nothing but audio; easy to understand and use, with a small attack surface (no Qt interface, room list, history or notifications). For: the prototype already works this way and worked well; it also fits ProxyNull's "fewer features is security" principle. Against: the password and the other side's address still have to be shared outside the program, two programs mean two maintenance burdens, and being in the same room as the text chat is lost. To be decided after Phase 1b, once real use has been seen |

---

## 8. Order in which the gaps get closed

| Order | Work | Impact | Size |
| --- | --- | --- | --- |
| 1 | ~~Remove history / turn it off by default (5.2)~~ **Off by default (1.7.0)**; removed entirely in encrypted rooms (1.9.0) | High | Small |
| 2 | ~~Make the interface the host listens on selectable (5.6)~~ **Done (1.6.2)** | Medium | Small |
| 3 | ~~Remove `content_length` from the event log (5.3)~~ **Done (1.5.0; the capability removed in 1.7.0)** | Low | Small |
| 4 | ~~Move to Argon2id (5.8)~~ **Done (1.7.0)** | Medium | Medium |
| 5 | ~~Forward secrecy (5.1)~~ **Done — text 1.9.0, voice 1.10.0** | **Highest** | Large — a protocol change |
| 6 | ~~Stop trusting the server's user list (5.4-B)~~ **Done (1.9.0)** | Medium | Small |
| 7 | **Message padding (5.7)** — the next job | Medium | Small |
| 8 | Signed / reproducible builds (5.9) | Medium | Medium |
| 9 | Transport-layer encryption (5.4-A) — **deferred** | Low–Medium | Large |

**Why 5.4-A dropped to the bottom.** It used to be 5th and marked "high
impact"; both were wrong. Three reasons:

1. **The important half of its benefit has already been taken.** The real harm
   in 5.4 was on the integrity side (B), and that was closed without giving the
   server any cryptography.
2. **The remaining half has little impact in the intended deployment.** The
   connection runs inside a VPN, so a listener on the path already sees
   encrypted traffic. What genuinely remains exposed is someone on the same
   local network (T1) — and the host, which a channel does not cover at all.
3. **Its cost is the two most concrete guarantees the server gives today.** A
   channel forces the server to do cryptography: the server chain that imports
   no `cryptography` and the zero third-party dependencies both end. A small,
   auditable server was a security feature in its own right.

The answer to A lies **outside the program** instead: run the connection
through a tunnel (WireGuard, an SSH tunnel, Tor). This is also consistent with
section 9, where the protocol's plaintext fingerprint (9.2) and the cost of
covering it (9.5) are already written down, and where that table says covering
overlaps with envelope encryption. Deferring both together beats doing each of
them halfway. ProxyNet already assumes you
bring your own network, and delegating this to tools built precisely for it is
stronger than writing our own transport layer. The product that has an
end-to-end encrypted channel in its design from the start is ProxyNull: there is
**no server at all** there, the Noise handshake is written into its protocol and
the connection runs over a Tor onion service (`apps/proxynull/PROTOCOL.en.md`).
Having ProxyChat imitate that would be a second half-implementation.

Decided 2026-09-27. Condition for revisiting: if the server moves to a publicly
reachable address (see 5.5), A rises again, because the VPN assumption falls
away there.

---

## 9. Resistance to blocking

Sections 1–8 of this document address a single question: **can the messages be
read?** This section asks a different one: **can the application run at all?**

These are separate axes. Even with perfect encryption, an application that
cannot establish a connection is useless. Today there is effectively **no
protection** on this axis — not by choice, it simply was never addressed.

### 9.1 What can be blocked, easiest first

| # | Target | Why it is easy | Where we stand |
| --- | --- | --- | --- |
| 1 | **VPN infrastructure** | Hamachi, Tailscale and ZeroTier all depend on a central rendezvous server | Peers cannot find each other; no need to touch the cryptography |
| 2 | **The distribution channel** | Cloud links and code hosting can be blocked | A program that cannot be downloaded cannot spread |
| 3 | **Protocol fingerprint** | The first packet is plaintext and trivial to recognise | See below — this one is our own fault |
| 4 | **The home connection** | An ISP can close inbound connections or move to CGNAT | Host mode and the "ready-made server" idea stop working |
| 5 | **The server itself** | A physical machine, a legal process | Direct shutdown |

### 9.2 Protocol fingerprint — a concrete gap

The first packet a client sends is this:

```
{"type":"join","room":"general","user":"ayse"}
```

Plaintext, fixed field names, fixed order. Recognising it with deep packet
inspection (DPI) takes minutes. The default port is fixed too (5555). Writing a
"drop this traffic" rule is almost free.

This is exactly why encrypted chat tools disguise themselves as TLS. We have no
such camouflage.

### 9.3 What cannot be blocked

- **Local network use.** The application works without the internet; no
  authority can block traffic between two machines on the same physical
  network. This is the most resilient part of the architecture.
- **The mathematics itself.** Encryption cannot be blocked; its use can be
  regulated, which is a legal rather than a technical matter.

### 9.4 A note on scale

To be honest: **a group of a few friends will not attract blocking at this
scale.** Blocking comes with scale. This section becomes meaningful if the
project grows; it is not today's priority, and effort spent here today goes to
the wrong place.

The most likely real scenario is not targeted but collateral: a general block
aimed at VPNs would hit us too.

### 9.5 What resistance would cost

| Work | Which item it closes | Size |
| --- | --- | --- |
| Abandon the fixed port | 9.1/3 partly | Small |
| Wrap or disguise the protocol inside TLS | 9.1/3 | Large — overlaps with envelope encryption |
| Multiply distribution, signed binaries | 9.1/2 | Medium — overlaps with 5.9 |
| Run the connection through a tunnel (WireGuard, SSH, Tor) | 9.1/3 partly | Small — the program does not change; it needs documenting and testing |
| Remove the dependence on central coordination | 9.1/1 | Very large; every peer-to-peer system needs a rendezvous point |

---

## 10. When this document gets updated

- When a new packet type or field is added to the protocol.
- When any data begins to be written to disk.
- On every change related to encryption.
- When the protocol's appearance on the network changes (see section 9).
- When a gap in section 5 is closed — the closed item moves to section 4, along
  with a note on which test guarantees it.

---

*The Turkish [THREAT_MODEL.md](THREAT_MODEL.md) is the source of truth. If the
two disagree, the Turkish one is correct.*
