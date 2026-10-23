[Türkçe](README.md) · **English**

# ProxyChat — Scope

ProxyChat is the **everyday** edition of the ProxyNet family. For the
encryption-focused edition see `../proxynull/README.en.md`; for the threat model
see `../../THREAT_MODEL.en.md`.

This document exists to answer a single question: **which features get added
and which do not?** So that a shiny idea does not restart the argument every
time one comes up.

---

## 1. Why it exists

ProxyChat is not being written to be a copy of Discord. Discord has hundreds of
developers, mobile clients and a far more mature voice stack; we have no chance
of winning a feature race, and entering it makes no sense.

ProxyChat exists because of four things Discord **cannot** do:

1. **The server is yours.** There is no company in the middle; nobody can shut
   it down, change the rules, or suspend your account.
2. **End-to-end encryption via a room password.** Not even the person running
   the server can read the messages. Discord has never had this.
3. **No account.** No email, phone number, verification or data collection.
4. **No internet required.** It works on a local network without ever leaving
   it.

If a feature does not strengthen one of these four, it adds nothing to the
reason for choosing ProxyChat over Discord.

---

## 2. Acceptance test

When a new feature is proposed, three questions in order:

**Q1. Does it reduce friction, or does it grow the feature list?**
Things that make the application *less annoying* are accepted. "Discord has it
too" is not a justification.

**Q2. Which of the four reasons above does it strengthen, and which does it
weaken?**
If it strengthens none and weakens one, the answer is no.

**Q3. What does it cost?**
Attack surface, leaked metadata, maintenance burden, build size. No feature is
accepted until the cost is written down.

---

## 3. Accepted so far

All of these passed Q1 — none was added because "Discord has it":

| Feature | Why it passed |
| --- | --- |
| Reconnecting after a dropped connection | Having to close and reopen the app |
| Remembering settings | Filling in five fields by hand on every launch |
| Background notification | The app only worked while you were looking at it |
| Join/leave lines | There was no way to tell who had arrived |
| Distinguishing your own message | Losing yourself in the stream |
| Room list coming from the server | The other side never saw a newly opened channel |
| Generate and show password buttons | People picked short, guessable passwords; a hidden password also could not be read out to share in person |
| Interface language (English / Turkish) | A Turkish-only interface shut out friends who don't read Turkish |

---

## 4. Currently out of scope

These are **not forbidden**, but none has yet passed the three questions in
section 2. If someone wants one added, those questions must be answered first
and the rationale written here.

| Feature | Why it is waiting |
| --- | --- |
| Roles and permissions | Solves no problem at the scale of a group of friends |
| Emoji **reactions** (attached to a message), profile pictures, themes | Pure appearance; touches none of the four reasons. **Writing** emoji arrived in 1.11.0 (a picker, plus emoji-only messages drawn large): that is display only, what goes on the wire is still plain text |
| File transfer, GIFs | Requires rebuilding the protocol, the encryption and the size limits. A GIF also means an image decoder (a classic source of remote code execution) and, if markup were allowed, an unescaped `<img>` could leak credentials over SMB on Windows |
| Bots, webhooks | Serious attack surface, no payoff |
| Invite links, server discovery | Requires a central directory; conflicts with reason 1 |
| Editing/deleting messages | Complicates history management; clashes with the persistence decisions |

Voice chat was evaluated separately and has been in the app since 1.8.0. Its
design, the decision gate it passed and its development log are in
[VOICE_CHAT_PLAN.en.md](../../VOICE_CHAT_PLAN.en.md).

---

## 5. Visual identity

The interface palette is currently **exactly Discord's dark theme** (`#313338`,
`#2b2d31`, `#f2f3f5`, `#ed4245`) and the layout is the same too: channels on
the left, messages in the middle, users on the right.

Within a group of friends this is not a problem. But if the application is
distributed publicly the palette needs to become its own — brand similarity is
an unnecessary risk, and the impression of being a "Discord clone" overshadows
what we actually want to say.

Low priority, but written here so it is not forgotten.

---

## 6. Decision record

| Decision | Outcome | Rationale |
| --- | --- | --- |
| Growing ProxyChat against Discord's feature list | **Rejected** | The feature race is unwinnable; the value lies in the four differences |
| Convenience features (reconnect, notification, settings) | **Accepted** | Passed Q1, does not conflict with the four reasons |
| A VPS for persistent history | **Rejected** | `THREAT_MODEL.md` principle 2 |
| Changing the colour palette | **Deferred** | To be addressed before public distribution |

---

*The Turkish [README.md](README.md) is the source of truth. If the two
disagree, the Turkish one is correct.*
