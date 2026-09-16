[Türkçe](THREAT_MODEL.md) · **English**

# ProxyNet — Threat Model

> **Publication note (2026-09-16):** ProxyNet's source code is **not open yet**
> and the software has had no independent security audit. There is no public
> release either. **Nobody should rely on this software today.** This document
> is published so that the design can be criticised before more is built on top
> of it; if you find a mistake, I want to hear it. The file paths in the text
> (such as `core/server.py`) are not visible yet — they were deliberately kept
> so that, once the code opens, every claim here can be checked at its source.

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
> listed explicitly in sections 5 and 6. Until those are closed, no claim to
> the contrary should be made.

---

## 1. Assets being protected

| Priority | Asset | Today's status |
| --- | --- | --- |
| 1 | Message content | End-to-end encrypted |
| 2 | Confidentiality of past messages (if the password later leaks) | **Not protected** |
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
| T5 | State-level adversary | Stores traffic for years, seizes devices, applies legal compulsion | **Not met** — no forward secrecy |

**T5 is the reason this document exists, and it is not currently met.** I write
this knowingly; the project has not reached its goal.

---

## 3. Out of scope

These threats cannot be solved by ProxyNet and must not be pretended otherwise:

- **Compromise of the endpoint.** Keyloggers, screenshots, memory dumps, the
  person looking over your friend's shoulder. Encryption protects the message
  on the network, not on the screen.
- **The channel used to share the room password.** If you send the password
  over WhatsApp, the chain breaks there. It should be shared face to face or
  through a separate secure channel.
- **The user's choice of password.** Because key derivation is deterministic, a
  guessable password collapses the entire model.
- **Security of the layers below** (operating system, VPN client, hardware).

---

## 4. Guarantees given today

All of these are tested (`tests/test_crypto.py`, `tests/test_hardening.py`):

- **The server never sees plaintext.** Encryption and decryption happen only on
  the client. The server chain (`core/server.py`, `core/hub.py`,
  `core/transport.py`, `core/protocol.py`, `core/server_state.py`) does not even
  import `cryptography` — the server has no ability to decrypt, and that
  absence is by design.
- **History held in server memory is encrypted.**
- **Content cannot be opened with the wrong password**; the user sees a
  placeholder instead of plaintext.
- **Tampered ciphertext is rejected.** Fernet is authenticated encryption
  (AES-128-CBC + HMAC-SHA256), so an adversary cannot silently alter message
  content.
- **No third-party dependency on the server side** — attack surface and supply
  chain risk are small.
- Limits against resource exhaustion: 64 KiB per packet, 8 KiB per message,
  20 messages per 10 seconds, at most 50 clients, 120-second idle timeout.

---

## 5. Guarantees NOT given today

These are known and accepted gaps. Until they are closed, it **must not** be
said that ProxyNet is at a "the state cannot read it" level.

### 5.1 No forward secrecy — the largest gap

The key is derived deterministically from the (room name + password) pair and
never changes. Consequence: encrypted traffic recorded today can be **fully
decrypted retroactively** if the password is obtained by any means in the
future.

This is precisely the standard method of state-level adversaries: *record now,
decrypt later*. Signal's Double Ratchet exists for this scenario. ProxyNet has
no equivalent.

### 5.2 History is handed out without authentication

The server sends the last 100 messages to **everyone** who joins a room
(`core/server.py` → `_send_room_history`), and no password is required to join.
Someone who does not know the password can enter a room, collect 100 encrypted
messages and take them away for an offline attack. Combined with 5.1 this is a
serious combination.

### 5.3 Metadata is fully exposed

Usernames, room names, timestamps, message sizes and who is online at what time
travel in plaintext. For an adversary at this scale, metadata is often more
valuable than content.

In addition, the event log written to the server console records the **length**
of the ciphertext (`core/server_state.py` → `content_length`), so message
lengths accumulate on the host's screen or log.

### 5.4 The transport layer is unencrypted

The packet envelope (`type`, `room`, `user`, `ts`, `enc`) travels in the clear.
An active attacker cannot forge message content but can inject a fake user list
or error packet, and can drop packets.

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
If that address disappears from the computer (for example, the VPN is turned
off), Host has to be started again.

### 5.7 Message length leaks

The length of Fernet output correlates with the length of the plaintext (at
16-byte block granularity). No padding is applied.

### 5.8 PBKDF2, not Argon2id

240,000 iterations of PBKDF2-HMAC-SHA256 is reasonable at a consumer level but
parallelises on GPUs. Argon2id is memory-hard and makes attacks with dedicated
hardware far more expensive, and it **is available** in the installed version of
`cryptography`.

### 5.9 The distribution chain is unprotected

The distributed `.exe` is unsigned and shared via a cloud link. An adversary
could deliver a modified binary to a user. There are no reproducible builds and
no signing.

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

---

## 8. Order in which the gaps get closed

| Order | Work | Impact | Size |
| --- | --- | --- | --- |
| 1 | Remove history / turn it off by default (5.2) | High | Small |
| 2 | ~~Make the host's listening interface selectable (5.6)~~ **Done (1.6.2)** | Medium | Small |
| 3 | Remove `content_length` from the event log (5.3) | Low | Small |
| 4 | Move to Argon2id (5.8) | Medium | Medium |
| 5 | Transport-layer encryption / authentication (5.4) | High | Medium |
| 6 | **Forward secrecy: key ratcheting (5.1)** | **Highest** | **Large** — protocol change |
| 7 | Message padding (5.7) | Low | Small |
| 8 | Signed / reproducible builds (5.9) | Medium | Medium |

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
{"type":"join","room":"general","user":"alice"}
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
