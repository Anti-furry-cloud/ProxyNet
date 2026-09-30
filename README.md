[Türkçe](README.tr.md) · **English**

# ProxyNet

End-to-end encrypted chat that runs on your own server. The goal is not merely
for a group of friends to talk — the goal is that **messages cannot be read by
anyone**, including the person running the server and a state-level adversary.

> **This repository currently contains documents only.** The source code is not
> open yet, there is no downloadable release, and the software has had no
> independent audit. **Nobody should rely on this today.** I am publishing the
> documents early because I would rather hear about a design mistake now than
> after months of code have been written on top of it.

---

## What it is

ProxyNet is not one program but two products. They share the same core but make
different promises.

| | **ProxyChat** | **ProxyNull** |
| --- | --- | --- |
| For whom | Everyday use, a group of friends | Situations where encryption is the priority |
| Status | Working. 1.12.4 is built and tested but not yet distributed; voice chat and forward secrecy (text 1.9.0, voice 1.10.0) landed in the app | No code yet; its [limits](apps/proxynull/README.en.md) and [protocol design](apps/proxynull/PROTOCOL.en.md) are written down |
| Goal | Be usable, protect content | Meet the T5 adversary in the threat model |
| Platform | **Windows 10/11 (64-bit)** | Platform-neutral by design (Rust, command line) |

The reason they are separate: fewer features is itself a security feature. They
were split deliberately so that ProxyChat's "let's add this too" pressure never
contaminates ProxyNull.

### What ProxyChat does today

- **You run the server.** Nobody's cloud, nobody's account. No sign-up, no
  email, no phone number.
- Messages are encrypted **on the client.** The server never sees plaintext;
  the ability to decrypt is deliberately **absent** from the server code.
- In text chat the encryption key is **born again every session** (from 1.9.0):
  ephemeral X25519 keys are exchanged and dropped when the session ends. The
  password's job is not to encrypt but to **authenticate** that the other side
  belongs to the room; the key of that signature is derived from the password
  with Argon2id (from 1.7.0). Without the password, content is unreadable.
- Room history is **off** by default (from 1.7.0) and is **never kept at all**
  in encrypted rooms (from 1.9.0): with forward secrecy a later joiner cannot
  decrypt it anyway. In rooms without a password, if the host turns it on, it
  lives in memory only, never on disk, and is gone when the server stops.
- Messages you have seen come back when you return to a room. They are kept
  in memory only and dropped when you disconnect.
- The room password can be copied without showing it on screen. The copy is
  kept out of Windows clipboard history and cleared after 30 seconds.
- Diagnostic logging is **off** by default.
- **Voice chat** (1.8.0): people in the same room can talk. The audio is
  encrypted with a key derived from the room session and, like text, **has
  forward secrecy** (1.10.0); the server relays it without decrypting and cannot
  tell who is speaking. A noise
  gate silences the microphone while nobody speaks. It is **not offered
  as a default** yet: it will not be described that way until the
  live-use test passes.
- Turkish and English interface.
- **Windows 10/11 (64-bit) only.** The core — encryption, protocol, transport,
  voice — is platform-neutral Python; what ties the product to Windows is three
  OS integration points: reserving the port exclusively for the server
  (`SO_EXCLUSIVEADDRUSE`, THREAT_MODEL.en.md 5.6), storing the password with
  DPAPI, and keeping the copied password out of the clipboard history. All
  three are **security** features rather than conveniences, so porting is not a
  packaging job: each one needs a written account of how that guarantee changes
  on the other platform. Platform-independent use where encryption is the
  priority is ProxyNull's job.

### What ProxyChat does not do today

I am not hiding these; hiding them would turn this document into marketing
copy:

- **Metadata is exposed.** Who, with whom, when — all visible. Message
  **length** has been the exception since 1.12.0: the payload is rounded to a
  bucket, so every short message goes out at the same size on the wire and
  what shows is one of nine steps rather than a length.
- **No password is needed to enter a room.** Anyone who can reach the server
  sees the user list and the rhythm of the traffic. Without the password they
  cannot read content, and in an encrypted room there is no longer a history for
  them to collect.
- **A weak password can still be cracked offline.** Argon2id makes every guess
  expensive, not impossible. Someone who finds the password can impersonate the
  key exchange of a **live** session and get in between; they cannot open
  recorded traffic, which forward secrecy closes. The real fix is a PAKE.
- **The transport layer is unencrypted.** An active attacker cannot forge
  message content but can forge envelope packets.
- **The distributed file is unsigned.**

The detail of each, why it is that way, and the order in which they will be
closed: **[THREAT_MODEL.en.md](THREAT_MODEL.en.md)**

### What is next

**The next job is signed and reproducible builds.** The distributed program is
unsigned; whoever downloads it has no way to verify that what they hold is what
we built. The order and the reasoning are in section 8 of
[THREAT_MODEL.en.md](THREAT_MODEL.en.md).

The other thing still pending is the **live-use test**: offering voice chat as a
default depends on it, and that test has not started.

#### Recently closed

**Message padding** (1.12.0). The length of the ciphertext gave away the length
of the plaintext exactly: the server could not read the content, but it could
tell "this is a three-character reply, that is a four-hundred-character
paragraph". What gets encrypted is now not the plaintext but a payload rounded
up to a fixed bucket ladder starting at 32 bytes — "ok", "no", "on my way" all
go out at exactly the same size on the wire. What is left to leak is one of
nine steps. The common alternative, Padmé, was not chosen: it applies no
padding at all to short inputs (2 → 2, 20 → 20), and the overwhelming majority
of chat messages sit below that threshold. Voice needs no padding (frames are
a fixed size), but the Opus setting that keeps them that way — VBR and DTX off
— is now pinned by a test.

**Forward secrecy** (text 1.9.0, voice 1.10.0). The key no longer comes from the
password: ephemeral X25519 keys are exchanged every session and dropped when it
ends, and the password's job is not to encrypt but to authenticate that the
other side belongs to the room. The result: even if the password leaks months
later, recorded traffic cannot be opened. This was the biggest gap.

**Voice chat now lives inside the application** (2026-09-25). The server
relays audio without decrypting it, the client speaks over a separate UDP
path, and the interface has join/leave, a participant list, mute and a noise
gate and a threshold control. It was tried with two copies on one machine and the audio was heard;
two separate computers are still untried.

Whether the connection quality is good enough was decided by measurements
whose rules were published before the measuring started; on 2026-09-24 the
result came out **acceptable**.

The design — the topology decision, the binary packet format, the AES-GCM
scheme, identity and address checks, and the **security questions that are
not yet solved** — is here, together with what the measurements showed:
**[VOICE_CHAT_PLAN.en.md](VOICE_CHAT_PLAN.en.md)**

The reason I publish that document at this stage: I would rather hear about a
mistake in the encryption design now than after months of code have been
written on top of it. Section 9 states plainly the two problems I have not
solved.

You could read that list and ask "so what is this good for?" The answer: it
protects your content against the person running the server and against third
parties who cannot enter the room. It does not protect against a state-level
adversary, and I do not claim it does. I would rather write the difference down
than conceal it.

---

## Who develops it

**[Anti-furry-cloud](https://github.com/Anti-furry-cloud)** — a one-person
project. No company, no team, no funding behind it.

I state this for a reason: cryptography is one of the areas most likely to go
wrong when one person writes it without review. That is also why the threat
model is published this openly — instead of asserting that it is correct, I am
putting it in front of you so you can show me where it is not.

Development runs in Turkish; all documents are published in Turkish and
English. Where the two disagree, **the Turkish one is correct.**

---

## What is in this repository

| File | Content |
| --- | --- |
| [CHANGELOG.en.md](CHANGELOG.en.md) | What was wrong and what changed, version by version |
| [THREAT_MODEL.en.md](THREAT_MODEL.en.md) | What it protects, what it does not, the adversary model, design principles, the order gaps get closed |
| [VOICE_CHAT_PLAN.en.md](VOICE_CHAT_PLAN.en.md) | The voice chat design plan — topology, packet format, encryption scheme, open security questions |
| [apps/proxynull/README.en.md](apps/proxynull/README.en.md) | ProxyNull's limits: what it must do, what it refuses, why it is separate from ProxyChat |
| [apps/proxynull/PROTOCOL.en.md](apps/proxynull/PROTOCOL.en.md) | ProxyNull's protocol design — the rendezvous code, the Noise handshake, the verification code, padding; decided and undecided items marked apart |
| [listening/](listening/LISTENING.md) | A blind listening test: how simulated network interruptions sound in speech |
| [THIRD-PARTY.en.md](THIRD-PARTY.en.md) | Third-party components in the package, their licences and where they come from |
| [LICENSE](LICENSE) | The GNU GPL v3 text |

Every document has a Turkish/English switcher at the top; the counterparts are
not listed separately.

The code will be added to this repository when it opens; the documents will
stay where they are.

---

## The official source, and copies

The only official source of this project is
**https://github.com/Anti-furry-cloud/ProxyNet**. A copy of ProxyChat or
ProxyNet circulating elsewhere may not have come from here; check this
place before downloading.

The project is released under the **GNU GPL v3**. That does not forbid
copying — it permits it. There are only three conditions:

- Anyone distributing a modified version must also provide **its source**.
- The licence and copyright notices stay; who wrote it cannot be erased.
- Derived work is distributed under the same licence.

So taking the code into a closed-source product, or changing whose work it
is, is a licence violation.

There is no public release yet. When one is distributed, the SHA-256
checksums of the files will be published in this repository; if the checksum
of your file does not match the one listed there, that file is not the one
we distributed.

---

## Feedback

If you see a mistake in the threat model, a missing adversary, or a claim that
is too optimistic, **open an issue.** The most useful feedback I can get is:
*"here is a gap that exists but is not listed in section 5."*

A security claim cannot be audited without code — I am aware of that. This
repository is not evidence; it is a statement of intent and a design draft.

**You can also help without reading any code:** listen to a few short
recordings and say how the interruptions sound to you. Instructions and
questions: **[listening/LISTENING.md](listening/LISTENING.md)**. Answers go in
the [Listening test](https://github.com/Anti-furry-cloud/ProxyNet/discussions/1) discussion.

---

## License

The project is under the GNU GPL v3 (or, at your option, a later version); the
full text is in [LICENSE](LICENSE). These documents are part of it.
