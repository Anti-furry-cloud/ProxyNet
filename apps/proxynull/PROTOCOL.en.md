[Türkçe](PROTOKOL.md) · **English**

# ProxyNull — protocol design

> **Status: draft, no code written.** This document is language-independent and
> aims to be normative: it says "must be", not "could be". Items that are
> settled are marked **Decided**, the rest **Open**.
>
> It has had no independent review. It is written early so that anyone who sees
> a mistake can point at the place where it lives.

What ProxyNull is, what it will not do and which adversary it targets is in
[README.en.md](README.en.md). This document answers **how**.

---

## 1. Scope

**Decided — two people.** ProxyNull does not do group chat. Two people only.
Forward secrecy and membership consistency in group encryption are not
something a one-person project should write for itself; with two people the
problem reduces to pairwise encryption and stays solvable.

**Decided — no server.** No relay server, no rendezvous server, no account
server. The two ends talk directly.

**Decided — no persistent identity.** Nothing is written to disk, including an
identity key. Every session is built from its own ephemeral keys. The price is
that verification has to be done again in every conversation (see section 5),
and it is a price knowingly paid: in ProxyNull privacy comes before
convenience.

**Decided — the interface is a command line.** No graphical interface. Less
code, less attack surface.

The target adversary is **T5** in
[../../THREAT_MODEL.en.md](../../THREAT_MODEL.en.md): one that stores traffic
for years, can seize a device and can apply legal pressure.

---

## 2. Rendezvous: the one-time code

Because there is no server and no persistent identity, exactly one piece of
information is shared for the two sides to find each other: a **one-time
code.**

**Decided — the shape of the code.** Words drawn at random from a word list,
separated by hyphens:

```
seven-sand-lamp-tray-savanna
```

- The words are drawn from a cryptographic source of randomness.
- **At least 55 bits of entropy** is required. With a 2048-word list, five
  words give 55 bits. If the list shrinks, the word count grows; the
  calculation is not hard-coded but done at run time, and the program refuses
  to run if it falls below the floor.
- The code is shown on screen and **written nowhere.**
- The code must be **readable aloud**: the word list is built from short,
  distinguishable words with one spelling each.

**Decided — two things are derived from the code,** each from a separate
domain of the same code:

| Derived | For | Domain label |
| --- | --- | --- |
| Rendezvous key | The onion service's address | `proxynull:rendezvous:v1` |
| Shared secret | Authentication in the handshake | `proxynull:handshake:v1` |

Derivation uses **Argon2id**. The parameters are written in this document and
are not negotiated (see section 7). Without domain labels the same key would
serve two jobs, and use in one could weaken the other.

**Decided — the address is computed, not transmitted.** The waiting side
publishes an onion service from the rendezvous key; the connecting side
computes the same address from the same code and connects. The only thing
handed over is therefore the code: nobody has to read a 56-character address
aloud.

**Decided — a Tor onion service.** Reasons: neither side sees the other's IP
address, no port has to be opened on a router, and reachability does not depend
on a VPN company. The price is added latency (acceptable for text) and Tor
being blocked in some countries.

**Decided — the code is one-time.**

- After the first successful session the code is void.
- It is also void after a failed handshake attempt: somebody who arrives with
  the wrong code gets no second try, the program stops and a new code is
  required.
- A code lives at most **10 minutes**. When the time is up the service closes.

**Open — the balance between code length and saying it out loud.** Can five
words be read over the phone comfortably, or are four words plus a larger list
better? To be settled by real use.

---

## 3. Handshake

**Decided — Noise, without static keys.** Since there is no persistent
identity, neither side has a static key. The pattern used:

```
Noise_NNpsk0_25519_ChaChaPoly_BLAKE2s
```

- `NN`: both sides generate only ephemeral keys.
- `psk0`: the shared secret derived from the code enters the mix in the first
  handshake message. Somebody who does not know the code cannot complete the
  handshake.
- Key exchange X25519, encryption ChaCha20-Poly1305, hash BLAKE2s.

**Why not a proper PAKE (CPace, OPAQUE):** a PAKE builds a session that is
closed to offline dictionary attack even from a low-entropy password. Here the
code is not low-entropy (at least 55 bits) and derivation goes through
Argon2id, which makes offline guessing against a recorded handshake infeasible
in practice. Noise, on the other hand, has implementations that have been used
and reviewed. This is a **trade-off**: a PAKE gives the stronger guarantee,
Noise means less new code. If the code entropy is ever lowered below 55 bits,
this decision is void and a PAKE becomes mandatory.

**Decided — no mode negotiation.** The cipher suite, the Noise pattern and the
Argon2id parameters are baked into the protocol version. If the two sides are
not on the same version, no connection is made; there is no room for a
downgrade attack.

**Decided — forward secrecy.** Session keys come from the ephemeral keys and
are destroyed when the session ends (in memory too: `zeroize`). Even if the
code is compromised later, recorded traffic cannot be opened, because the code
only authenticates the handshake; it does not determine the session key by
itself.

**Open — reconnecting after a drop.** This is an allowed convenience, but the
code is one-time. The options: mint a "reconnect ticket" during the handshake
(never persisted, memory only), or require a new code after a drop. The second
is simpler and safer, the first is more usable.

---

## 4. Rekeying, and its limit

**Decided — regular rekeying.** The session key is refreshed with Noise's own
rekey after **1000 messages or 15 minutes**, whichever comes first. The old key
is destroyed.

**Known limit — no post-compromise security.** If the memory of one end is
seized at a moment in time, messages after the following rekeys can also be
read; Signal's double ratchet solves this with fresh ephemeral key exchanges.
ProxyNull v1 does not have that and **this document does not claim otherwise.**
Reasons: sessions are short, there is no persistent identity, and writing a
two-ended ratchet correctly on one's own is above this project's scale.

**Open — will fresh ephemeral key exchange inside a session (a simple ratchet)
be added?** If it is, the limit closes; the cost is protocol complexity.

---

## 5. Verification: the short authentication code

Without a persistent identity a "safety number" cannot stay the same from
session to session. Instead each session uses a code specific to that session.

**Decided — the code is derived from the handshake hash.** Four words are
derived from the `h` value at the end of the Noise handshake, with a domain
label (`proxynull:sas:v1`). Because somebody in the middle runs a separate
handshake with each side, the two sides get different codes.

**Decided — verification is mandatory.** No message can be sent until both
sides confirm "the code matches". Optional verification is, in practice,
verification that never happens.

**Decided — the comparison happens outside the program:** in person or by
voice. The program does not automate it; automating it would put verification
back inside the channel that may be broken.

The method is not new: ZRTP has used a short authentication string in voice
encryption for years.

**Open — words or digits?** Which is compared more reliably, four words or six
digits? Either way they are tuned to the same entropy.

---

## 6. Message format

**Decided — no envelope.** In ProxyChat's packets fields like `type`, `room`
and `user` travel in plaintext. In ProxyNull every byte on the wire is
encrypted; the type information lives inside the encrypted payload too.

**Decided — padding.** Messages are padded into fixed buckets: **256, 512,
1024, 2048, 4096 bytes.** A message larger than a bucket is split. The purpose
is to stop the length from telling anything about the content (in ProxyChat
this is an open gap, see THREAT_MODEL 5.7).

**Decided — no typing indicator.** Keystroke timing tells something about the
text being written and reveals who is active when.

**Open — cover traffic.** Sending packets while silent hides the rhythm of a
conversation, but costs battery and bandwidth and loads the Tor network. Not to
be decided without measuring.

---

## 7. Cryptographic parameters

All of them are baked into the protocol version; none are negotiated.

| Job | Choice |
| --- | --- |
| Key derivation from the code | Argon2id, RFC 9106 second option: 3 passes, 4 lanes, 64 MiB |
| Key exchange | X25519 (Noise `NNpsk0`) |
| Encryption | ChaCha20-Poly1305 |
| Hash | BLAKE2s |
| Subkey derivation | HKDF-BLAKE2s, with domain labels |

The Argon2id parameters are deliberately the same as ProxyChat 1.7.0: they were
chosen for the same reason (being memory-hard makes special hardware
expensive), and there is no benefit in keeping different parameters in the two
products.

**Decided — the salt.** In ProxyChat the salt comes from the room name, so it
is deterministic. In ProxyNull the salt is derived from **the code itself**, and
since the code is new in every session the salt is new as well; because a code
is never used twice, the same key is never produced twice.

---

## 8. Zero persistence

**Decided — nothing is written to disk.** No messages, no code, no settings, no
log, no crash dump.

- Key material is wiped from memory after use (`zeroize`).
- The program disables crash dumps.
- Messages printed to the terminal are not outside the record: **if the user's
  own terminal keeps scrollback, the messages land there.** The program cannot
  close that; it is stated plainly in this document and on first run.

**Open — swap.** A key in memory can reach the disk if the operating system
pages memory out. On Linux pages can be locked with `mlock`; on Windows the
equivalent is limited. How much can be guaranteed is to be investigated and
written down.

---

## 9. Metadata: what is hidden and what is not

**Hidden:**

- Each side's IP address, from the other side and from a listener on the
  network (Tor).
- The content, the length (padding) and the type of messages.
- Identity: there is no persistent identifier at all.

**Not hidden:**

- **That you use Tor.** An ISP sees the connection to Tor. Bridges hide that to
  a degree; whether they are in scope is open.
- **The time and the rhythm of the conversation.** Without cover traffic,
  packet timing shows the tempo of the exchange.
- **The channel where the code was shared.** If the code was said over the
  phone, a recording of that call shows two people preparing to talk. This is
  the limit that lies outside the protocol and cannot be closed by it.

---

## 10. Rejected designs

| Design | Reason |
| --- | --- |
| A persistent identity key (in a file, encrypted with a password) | Anything written to disk can be seized. Privacy is not traded for convenience (the product owner's decision, 2026-09-17) |
| Deriving the identity from a password (a brain key) | The password becomes the identity; a weak one is cracked offline, and changing it changes who you are |
| Group chat | Forward secrecy in group encryption is a separate and large problem; the two-person scope was chosen deliberately |
| A rendezvous server (as Magic Wormhole has) | A server sees who meets whom and can be shut down; a Tor onion service does the same job without one |
| Offline messages | They require storage, which contradicts zero persistence. Both sides will be online |
| Voice chat | A constant-rate audio stream tells the network that one side is speaking and when; that works against the padding in section 6 — padding hides size, a continuous stream opens up timing. ProxyChat has voice (over a relay, at a constant bit rate); this product will not. Reading the verification code aloud is not an exception: that happens outside the program |
| Message history, a settings file, notification previews | The bans table in [README.en.md](README.en.md) |

---

## 11. What the implementation will have to prove

When code is written, every claim in this document needs a test behind it:

- The same code produces the **same** onion address and the same shared secret
  on both sides.
- Different codes produce different addresses; changing a single word changes
  the address completely.
- Generating a code below 55 bits is **refused.**
- A side arriving with the wrong code cannot complete the handshake and gets no
  second attempt.
- Somebody in the middle produces **different** verification codes at the two
  ends.
- No message can be sent before verification is confirmed.
- Messages of the same size look the same size on the wire (padding).
- No key material remains in memory once the session ends.
- No file is written to disk (watched on the file system while running).

---

## 12. When this document is updated

- When an **Open** item is settled.
- When the cipher suite, the Noise pattern or the Argon2id parameters change —
  those also raise the protocol version.
- When the byte order on the wire or the padding buckets change.
- When a rejected design comes up again: the point is not to change the
  decision but to update the reason.
