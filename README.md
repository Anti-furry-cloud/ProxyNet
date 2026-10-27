[Türkçe](README.tr.md) · **English**

# ProxyNet

End-to-end encrypted chat that runs on your own server. The goal is not merely
for a group of friends to talk — the goal is that **messages cannot be read by
anyone**, including the person running the server and a state-level adversary.

## Quick start

**[Download ProxyChat 1.13.0 for Windows 10/11](../../releases/latest)**. Get `ProxyChat-Setup.exe` from that page.

1. **Install.** The file has no Authenticode signature, so Windows SmartScreen
   warns: *More info → Run anyway*. To check the file first:
   [VERIFYING.en.md](VERIFYING.en.md).
2. **Be on the same network.** Everyone must reach the host's computer: the
   same local network, or a virtual LAN such as Hamachi.
3. **One person hosts.** Choose **Host**, pick the network to listen on, enter
   a room password and connect. Share the address and the password with your
   friends — face to face or over an encrypted messenger.
4. **The others join.** Choose **Join**, enter the address, the same room and
   the same password. Without the same password nobody can read the messages.

> **Before you rely on it:** an early release by one person, with **no
> independent security audit**. It protects **what you write, not who you
> are** — the server sees who is in the room and when. Read
> [what it does not do](#what-proxychat-does-not-do-today) and
> [what it is for, and what it is not](#what-it-is-for-and-what-it-is-not).

> **⚠ A fake "ProxyChat.exe" is in circulation (2026-10).** A file named
> `ProxyChat.exe` is being offered elsewhere on the internet. **It is not
> ProxyChat; it is malware** — a remote-access trojan. I examined it without
> running it: about 14 MB, unsigned, SHA-256
> `6f2b3816fa61328de13496b47c787f768b6634ec7cb68a4a3c370be74e45c94e`.
> The real files come **only** from this repository's
> [Releases](../../releases) page, with their checksums in the signed
> `SHA256SUMS.txt` ([VERIFYING.en.md](VERIFYING.en.md)). If you ran the fake,
> treat that computer as compromised: disconnect it from the network, scan
> it, and change your passwords from another device.

---

## What it is

ProxyNet is not one program but two products. They share the same core but make
different promises.

| | **ProxyChat** | **ProxyNull** |
| --- | --- | --- |
| For whom | Everyday use, a group of friends | Situations where encryption is the priority |
| Status | Working. Latest release 1.13.0 ([download](../../releases/latest)), first public release 1.12.8; voice chat and forward secrecy (text 1.9.0, voice 1.10.0) included | ProxyNull has no code yet; its [limits](apps/proxynull/README.en.md) and [protocol design](apps/proxynull/PROTOCOL.en.md) are written down |
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
  gate silences the microphone while nobody speaks. It has been tried
  between two separate computers and works. Still, it is **not offered as a
  default** yet: it will not be described that way until the live-use test
  passes.
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
- **Only partly quantum-resistant.** Since 1.13.0 the session key also
  depends on the room password, so someone who records traffic today and
  later breaks X25519 with a quantum computer still needs the password. A
  weak password does not protect this, and full resistance (a hybrid key
  exchange with ML-KEM) is still to come:
  [THREAT_MODEL.en.md](THREAT_MODEL.en.md) 5.10.
- **The transport layer is unencrypted.** An active attacker cannot forge
  message content but can forge envelope packets.
- **The distributed file has no Authenticode signature.** Windows SmartScreen
  warns. Instead, the checksum list is signed with GPG; how to check it is in
  [VERIFYING.en.md](VERIFYING.en.md).

The detail of each, why it is that way, and the order in which they will be
closed: **[THREAT_MODEL.en.md](THREAT_MODEL.en.md)**

### What is next

**Voice chat has been tried between two separate computers and works.** The
next job is the **live-use test**. Offering voice chat as a default depends on
it. It has not started, for a concrete reason: sessions only count once the
product itself writes the record file, and today only the voice prototype
writes one. The rule was written that way so that "does this work?" attempts
do not go on record as bad results.

The two items left in the list in section 8 of
[THREAT_MODEL.en.md](THREAT_MODEL.en.md) are **deferred on purpose**, with the
reasoning written there: Authenticode signing (8-B) and transport-layer
encryption (9).

#### Recently closed

**Recorded traffic against a future quantum computer** (1.13.0). The session
key came from the X25519 exchange alone, so traffic recorded today could be
opened later, without the password, by a quantum computer able to break
X25519. Now a key derived from the password enters the session key too;
text and voice are covered together. This changes the keys, so 1.13.0
**cannot talk encrypted with 1.12.x**: everyone in a room needs to update.

**The address on screen** (1.12.8). Anyone streaming their screen or recording
a video gave away their IP address without noticing: it was on the chat
screen's "Connected: …" line, in the Host's list of addresses to share, in the
connect screen's IP field and in its network list. Addresses are now masked by
default; holding **Show address** reveals them, and **Copy address** copies
them without showing them and without entering the clipboard history. This is
about the **screen** only: your friends still know the address, since they
connect to it, and so does anyone who connects to the server. Hiding the
address from the network is not what this version does.

**A security pass** (1.12.7). A night spent attacking the program turned up
eleven holes; all are closed and each has a test that fails on the old code.
The worst needed no password. When someone left voice chat, Windows could make
the host's audio relay stop **for everyone**; one made-up packet could drop
another person's connection; a client that joined a room and never read could
stall everyone's messages. The name above a message was not checked against
the key that encrypted it, so it could be relabelled on the way; it now has to
match. A recorded message sent again no longer shows twice. A room name
carrying an image tag could make the program open a network address on
Windows, giving away the IP and a password hash; names are plain text now.
And a notification from an encrypted room no longer carries the message,
since Windows keeps notifications on disk. **What is still open** is written
down too: sender keys carry no signature, so someone who knows the password
and can also inject packets can still write under another member's name
([THREAT_MODEL.en.md](THREAT_MODEL.en.md) 5.4-B).

**Reproducible builds and the supply chain** (1.12.3–1.12.4). Two builds from
the same source produced different files, so a published checksum could say
"this file is not corrupted" but not "this file came from the source you
named". The build is now reproducible bit for bit, and someone building from a
different directory gets the same result. Dependencies are no longer ranges but
exact versions pinned to wheel hashes — an install now refuses a package that
has been changed. The audio codec used to be a binary built by another project
and is now compiled from the source archive Xiph publishes. The checksum list
is signed; how to check it, and **the limit of that check**, are in
[VERIFYING.en.md](VERIFYING.en.md).

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
gate and a threshold control. It was first tried with two copies on one machine; later it
was also tried between two separate computers and worked.

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

## What it is for, and what it is not

ProxyChat is for **small groups of people who know each other**: friends, a
gaming team, a family. Someone in the group runs the server on their own
computer; the conversation does not sit on another company's server.

What it is **not**:

- **Not an anonymity tool.** The server you connect to sees your IP address;
  whoever runs the server sees who is in the room and when. It does not hide
  who you are, only what you write.
- **Not designed for hiding from anyone.** The code is open, its design and
  its limits are written down; there is no hidden distribution and no hidden
  audience.
- **Not a central service.** There is no server run by me. I do not see or
  keep any user's name, address or messages, and the program sends me
  nothing.
- **Not made for illegal use**, and I do not support such use.

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
| [VOICE_CHAT_PLAN.en.md](VOICE_CHAT_PLAN.en.md) | Voice chat's design and development log — topology, packet format, encryption scheme, open security questions |
| [apps/proxynull/README.en.md](apps/proxynull/README.en.md) | ProxyNull's limits: what it must do, what it refuses, why it is separate from ProxyChat |
| [apps/proxynull/PROTOCOL.en.md](apps/proxynull/PROTOCOL.en.md) | ProxyNull's protocol design — the rendezvous code, the Noise handshake, the verification code, padding; decided and undecided items marked apart |
| [listening/](listening/LISTENING.md) | A blind listening test: how simulated network interruptions sound in speech |
| [MANUAL.en.md](MANUAL.en.md) | Installation, usage and building from source |
| [SECURITY.en.md](SECURITY.en.md) | How to report a security hole |
| [VERIFYING.en.md](VERIFYING.en.md) | How to verify what you downloaded, how to rebuild it from source, and the limit of that check |
| [THIRD-PARTY.en.md](THIRD-PARTY.en.md) | Third-party components in the package, their licences and where they come from |
| [LICENSE](LICENSE) | The GNU GPL v3 text |

Every document has a Turkish/English switcher at the top; the counterparts are
not listed separately.

The source code itself: the application in [apps/proxychat/](apps/proxychat/README.en.md),
the shared core in `core/`, the tests in `tests/`; the build scripts are in the
root folder. Development runs in a separate repository; this one is a
**snapshot** of it, updated with each release, not its history. Detail in
[VERIFYING.en.md](VERIFYING.en.md).

---

## The official source, and copies

The only official source of this project is
**https://github.com/Anti-furry-cloud/ProxyNet**. A copy of ProxyChat or
ProxyNet circulating elsewhere may not have come from here; check this
place before downloading.

The project's only official channels elsewhere are
**https://www.youtube.com/@ProxyNet_dev** and
**https://www.tiktok.com/@proxynet.dev**. They distribute no files: every
download comes from this repository, with its signed checksum list. An account
under a similar name that offers a download — in a link, a comment or a
message — is not this project.

The project is released under the **GNU GPL v3**. That does not forbid
copying — it permits it. There are only three conditions:

- Anyone distributing a modified version must also provide **its source**.
- The licence and copyright notices stay; who wrote it cannot be erased.
- Derived work is distributed under the same licence.

So taking the code into a closed-source product, or changing whose work it
is, is a licence violation.

Releases are published on the [Releases](../../releases) page. Each one comes
with the SHA-256 checksums of its files and a **signature** of that list; if
the checksum of your file does not match the one listed there, that file is
not the one I distributed.

The signing key's fingerprint:

```
23DC 905B 569A 80BD D243  525B 80DA 0356 E47B B37C
```

How to check it, and the **limit** of that check:
[VERIFYING.en.md](VERIFYING.en.md). The build is also reproducible, so instead
of trusting the checksum you can rebuild from source and compare.

---

## Feedback

If you see a mistake in the threat model, a missing adversary, or a claim that
is too optimistic, **open an issue.** The most useful feedback I can get is:
*"here is a gap that exists but is not listed in section 5."*

If you would rather not use GitHub, write to **proxynet.dev@protonmail.com**.
**For a security hole, do not open a public issue** — use that address, and
in the first message say only what the problem is; we will choose together
how to pass on the details.

The code is here now, so the claims can be tested against it. That does not
stand in for an audit: nobody but me has reviewed the code end to end.

**You can also help without reading any code:** listen to a few short
recordings and say how the interruptions sound to you. Instructions and
questions: **[listening/LISTENING.md](listening/LISTENING.md)**. Answers go in
the [Listening test](https://github.com/Anti-furry-cloud/ProxyNet/discussions/1) discussion.

---

## License

The project is under the GNU GPL v3 (or, at your option, a later version); the
full text is in [LICENSE](LICENSE). These documents are part of it.
