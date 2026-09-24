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
| Status | Working. 1.7.0 is built and tested but not yet distributed | No code yet, only its limits written down |
| Goal | Be usable, protect content | Meet the T5 adversary in the threat model |

The reason they are separate: fewer features is itself a security feature. They
were split deliberately so that ProxyChat's "let's add this too" pressure never
contaminates ProxyNull.

### What ProxyChat does today

- **You run the server.** Nobody's cloud, nobody's account. No sign-up, no
  email, no phone number.
- Messages are encrypted **on the client.** The server never sees plaintext;
  the ability to decrypt is deliberately **absent** from the server code.
- The key is derived from the room password with Argon2id (from 1.7.0).
  Without the password, content is unreadable.
- Room history is **off** by default (from 1.7.0). If the host turns it on, it
  lives in memory only, never on disk, and is gone when the server stops.
- Messages you have seen come back when you return to a room. They are kept
  in memory only and dropped when you disconnect.
- The room password can be copied without showing it on screen. The copy is
  kept out of Windows clipboard history and cleared after 30 seconds.
- Diagnostic logging is **off** by default.
- Turkish and English interface.

### What ProxyChat does not do today

I am not hiding these; hiding them would turn this document into marketing
copy:

- **No forward secrecy.** The key never changes. Encrypted traffic recorded
  today can be read retroactively if the password is ever compromised. This is
  the biggest gap.
- **Metadata is fully exposed.** Who, with whom, when, at what length — all
  visible.
- **No password is needed to enter a room.** Anyone who can reach the server
  sees the user list and the rhythm of the traffic. If the host turns room
  history on, they can also collect the encrypted history.
- **A weak password can still be cracked offline.** Argon2id makes every guess
  expensive, not impossible, and the same room name and password give the same
  key everywhere.
- **The transport layer is unencrypted.** An active attacker cannot forge
  message content but can forge envelope packets.
- **The distributed file is unsigned.**

The detail of each, why it is that way, and the order in which they will be
closed: **[THREAT_MODEL.en.md](THREAT_MODEL.en.md)**

### What is next

Voice chat is being worked on. Its core is written, and a prototype has now
carried a live conversation between two computers on separate internet
connections; that prototype is a separate command-line tool, not part of the
program people install. Whether the connection quality is good enough was
decided by measurements whose rules were published before the measuring
started; on 2026-09-24 the result came out **acceptable**, so the network
work may continue. Shipping voice chat as a default also depends on a
live-use test whose rules were likewise written in advance. The design — the topology decision, the binary packet format,
the AES-GCM scheme and the **security questions that are not yet solved** — is
here, together with what the prototype and the measurements have shown so
far: **[VOICE_CHAT_PLAN.en.md](VOICE_CHAT_PLAN.en.md)**

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
| [THREAT_MODEL.en.md](THREAT_MODEL.en.md) | What it protects, what it does not, the adversary model, design principles, the order gaps get closed |
| [THREAT_MODEL.md](THREAT_MODEL.md) | The Turkish original |
| [VOICE_CHAT_PLAN.en.md](VOICE_CHAT_PLAN.en.md) | The voice chat design plan — topology, packet format, encryption scheme, open security questions |
| [VOICE_CHAT_PLAN.md](VOICE_CHAT_PLAN.md) | The Turkish original |
| [listening/](listening/LISTENING.md) | A blind listening test: how simulated network interruptions sound in speech |
| [LICENSE](LICENSE) | The GNU GPL v3 text |

The code will be added to this repository when it opens; the documents will
stay where they are.

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
