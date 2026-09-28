[Türkçe](README.md) · **English**

# ProxyNull

**Status: no code written yet.** This folder defines the product's boundaries.
The protocol design: **[PROTOCOL.en.md](PROTOCOL.en.md)**.

ProxyNull is the **encryption-focused** edition of the ProxyNet family. What
separates it from ProxyChat is not a lack of features but the **refusal** of
them: here every feature is treated as a candidate attack surface and metadata
leak, and the default answer is no.

The name comes from that — nothing is left behind.

## Why this product exists

Protection against the **T5** adversary in `../../THREAT_MODEL.en.md`: one that
stores traffic for years, can seize the server, and can apply legal compulsion.
ProxyChat does not carry that goal; ProxyNull does.

## Requirements

- **Forward secrecy.** Session keys are ephemeral and destroyed. Even if the
  password later leaks, recorded traffic cannot be opened.
- **Two people only.** No group chat; forward secrecy in group encryption is a
  separate and large problem.
- **No persistent identity, verification in every session.** Forward secrecy is
  useless against an active MITM without verification. A persistent identity
  key was rejected because it would have to be written to disk; instead a short
  code specific to each session is compared by voice, and no message can be
  sent before both sides confirm it.
- **Rendezvous through a one-time code.** There is no server: both sides enter
  the same short code, the meeting address is computed from it, and the
  connection is made over a Tor onion service.
- **Zero persistence.** No message history, no settings file, no log. Nothing
  is written to disk.
- **Envelope encryption and padding.** Room name and username live inside the
  encrypted payload; messages are padded into fixed-size buckets.
- **No mode negotiation.** The security level is not negotiated in the
  protocol; that opens the door to a downgrade attack.

## Prohibitions

The following belong to ProxyChat and will **not** be added here:

| Prohibited | Rationale |
| --- | --- |
| Message history | Persistence creates a seizable pile |
| Remembering settings/passwords/identity | Key material is not written to disk |
| Notifications with content previews | Leaks on screen and in notification history |
| Typing indicator | Keystroke timing tells something about the text and who is active |
| Group chat, the notion of rooms | The two-person scope was chosen deliberately |
| Voice chat | A continuous stream gives away the timing of speech; the reasoning is in section 10 of [PROTOCOL.en.md](PROTOCOL.en.md) |
| File transfer, themes, emoji | Attack surface with no payoff |

Permitted: re-establishing a dropped connection (does not conflict with
security) and a contentless "new message" alert.

## What using it will feel like

One consequence of this design is unavoidable: **every session starts with a
ritual.** With no persistent identity there is nothing to remember, so on every
connection the short verification code has to be compared out of band and
confirmed by both sides. Until it is confirmed, not a single message can be
sent.

That is not a shortcoming; it is the price of the decision. But the consequence
belongs in writing here: ProxyNull will be a tool used **rarely and
deliberately.** Everyday chat stays in ProxyChat; ProxyNull does not replace
it, which is why both products exist. So that "why isn't it used all the time"
never looks like a failure later — the answer is inside the design.

## Relationship with ProxyChat

**No code is shared.** ProxyNull will be written in a different language (Rust)
and its protocol will deliberately diverge. Where that divergence sits has
narrowed since 1.9.0: forward secrecy and the absence of history in encrypted
rooms **landed in ProxyChat too**, so they no longer separate the two. The real
remaining differences are **envelope encryption** (the room and username are
inside the ciphertext as well), **having no server at all**, the Tor onion
service, and moving from a password to a PAKE. The `core/` package therefore
belongs to ProxyChat and is not used from here.

The unavoidable cost of this is two independent implementations. What prevents
divergence is not shared code but **shared written references**:
[THREAT_MODEL.en.md](../../THREAT_MODEL.en.md) and
[VOICE_CHAT_PLAN.en.md](../../VOICE_CHAT_PLAN.en.md). When protocol work
begins, a normative specification document should be added here as well.

Users of the two products **cannot talk to each other**; this is the accepted
consequence of the split.

## Target platforms

**Windows and Linux together**, from the first release.

The reason is not user count but the right audience: ProxyNull targets not end
users but people who need protection from the T5 adversary, and that group is
concentrated on Linux (Tails, Qubes, Whonix). There are also the security
researchers who would review the code — they do not examine what they cannot
run.

The cost is low, because none of the three things binding ProxyChat to Windows
has a counterpart here:

| In ProxyChat | In ProxyNull |
| --- | --- |
| Qt interface | A command line, platform independent |
| Password storage via DPAPI | Storing passwords is already prohibited |
| NSIS installer | Rust produces a single static binary |

The remaining core (sockets, Noise, ratchet) is platform-neutral.

An additional gain: reproducible builds are both easier and more meaningful on
Linux (see THREAT_MODEL.md 5.9).

**macOS is out of scope for now.** The Rust side is free, but Apple's signing
and notarisation process requires a paid developer account. To be reconsidered
if there is demand.

**Adding a GUI is where the cost rises** — Rust's cross-platform GUI ecosystem
is not as mature as Qt. That is one more argument for the command-line
decision.

## Roadmap

Order and rationale are in section 8 of `../../THREAT_MODEL.en.md`.

1. ~~**Protocol design** — a language-independent, normative document.~~ A
   draft is written: [PROTOCOL.en.md](PROTOCOL.en.md). Settled items and open
   ones are marked separately inside it.
2. **Rust implementation** — as a Cargo project in this folder. There is no
   Python prototype stage: `snow` (Noise), `zeroize` and a static, reproducible
   binary are requirements of this product and cannot be met with Python.
3. The interface is a command line; there is no graphical interface.

No code will be written until the decisions are settled.

---

*The Turkish [README.md](README.md) is the source of truth. If the two
disagree, the Turkish one is correct.*
