[Türkçe](CHANGELOG.md) · **English**

---

# Changelog

Nothing here says "fixed several issues". Every entry says **what was wrong**,
not how it was fixed. If you want the how, [THREAT_MODEL.en.md](THREAT_MODEL.en.md)
and the commit messages do that job.

**⚠ wire break** in a heading means that version cannot exchange encrypted
messages with older ones; both sides see "different version". That is
deliberate: with no negotiation, nobody can force two clients down to an older
scheme.

No public release has been distributed yet.

---

## 1.12.4

- **Two builds from the same source produced different files.** So nobody
  could verify "is this the executable you built?" — even someone holding the
  source could not reproduce the output. The build is now **reproducible bit
  for bit**; three settings were enough, and a build from a different
  directory produces the same checksum.
- **Dependencies were written as ranges** (`PySide6>=6.6`), so anyone
  building a month later got a different Qt. `requirements.lock` pins every
  package to an exact version and wheel hash. The gain is larger than the
  build itself: an install now **refuses** a file on PyPI that has been
  changed since.
- Every build produces a **manifest**: which commit, whether the working tree
  was clean, which tool versions, which package hashes, which outputs. The
  manifest is not a signature — its job is to let someone who wants to
  reproduce the build compare the result.

## 1.12.3

- **The audio codec was a binary built by another project.** `libopus.dll` had
  been taken out of the PyAV package, so distributing it meant trusting that
  project's build pipeline — and since 1.12.2 packed the codec inside the
  executable, that binary was part of the file whose checksum we publish. It is
  now built from the source archive Xiph publishes. The archive's checksum was
  verified against a value written into this project's documents on
  **2026-09-18**.
- A trap found while building: with default settings the DLL comes out
  depending on `VCRUNTIME140.dll`, so on a machine without the Visual C++
  redistributable it would fail to load and drop voice to µ-law **silently**.
  Built with a static runtime it needs only `KERNEL32.dll`.
- The **copyright holders line** missing from the third-party licence file was
  filled in, copied verbatim from the source archive's `COPYING`. Written from
  memory it would have been wrong (the line runs to 2023 and lists Mozilla and
  Amazon as well).

## 1.12.2

- **The audio codec (`libopus.dll`) was a separate file that had to sit next
  to the executable.** Without it the sound silently fell back to µ-law: 320
  bytes per frame instead of 60, roughly four times as much on the wire. Worse,
  if someone with Opus entered the room first, a copy without the DLL could not
  join voice at all. The codec now lives inside the executable; sending the one
  file is enough.
- Third-party licences are collected in [THIRD-PARTY.en.md](THIRD-PARTY.en.md).
  libopus comes under BSD 3-clause, which requires the licence text to be
  **provided with the distribution**; it was not written down anywhere before.

## 1.12.1

- **The "Generate" button sat next to the password field in Join mode as
  well.** In Join the password comes from whoever created the room; pressing
  that button replaced theirs with one of your own invention, and the result
  was "could not decrypt — the room password is different". The button now
  appears only in Host and Demo, and what you typed survives a change of mode.
- Generating a password in Host mode and then switching to Join left the
  "password generated" notice on screen, where it no longer meant anything.

## 1.12.0 — ⚠ wire break

- **The length of an encrypted message was exactly the length of the
  plaintext.** The server could not read a message, but it could look at the
  size and tell "this is a three-character reply, that is a
  four-hundred-character paragraph". The payload is now rounded up to fixed
  steps: "ok", "no", "on my way" all go out at **exactly the same size** on
  the wire.
- The price is two bytes: the longest message you can send went from 6112 to
  **6110 bytes**. The field carrying the real length comes out of there.
- **Voice packets being a size independent of the speech rested on a setting,
  and nothing protected that setting.** The test that measures it was skipped
  on a machine without the audio library — so on most machines it never ran at
  all. If someone had turned variable bitrate on, packet size would follow the
  audio and the rhythm of speech could be read off the network. It is now
  pinned without the library too.

## 1.11.0

- A picker for writing emoji appeared to the right of the message box. Short
  messages made only of emoji are drawn large — `test👍` stays small, a lone
  `👍` grows. (There are no GIFs and there will not be: a GIF means an image
  decoder, allowing markup, and file transfer — three new attack surfaces.
  Emoji need none of them; what goes on the wire is still plain text.)
- **When someone who could not prove they knew the room password entered, a
  "joined" line appeared in the chat.** Anyone generating fake users could
  have filled the conversation with those lines. They are not shown at all
  now; the user list counts them on a single row that expands to names when
  clicked. Above 100 it reads ">100".
- Messages had no colon after the name, so the name ran into the text. The
  colon is there now, drawn in a darker shade of the name's own colour.
- Names in the user list sat flush against each other; a thin separator line
  now runs between them.
- The right-hand side was one long column; users and voice chat are now two
  separate cards.

## 1.10.1

- **Most of `core/crypto.py` was the old Fernet path that nothing called any
  more.** Nobody was using it, but a reader could conclude that ProxyChat
  still encrypts with a fixed password-derived key — and an unused encryption
  path is a path something could be wired back into by accident one day. It
  was deleted.
- **The voice cipher silently fell back to the old password-derived scheme
  when it was handed no key.** A silent downgrade is the thing that must not
  happen: it now raises unless the fallback is asked for explicitly.

## 1.10.0 — ⚠ wire break (voice)

- **The voice key still came from the password.** Text had become forward
  secret one version earlier; voice had not, so if the password leaked months
  later, recorded audio could be opened. The voice session key is now derived
  from the room session, so voice inherits text's forward secrecy.

## 1.9.0 — ⚠ wire break

- **The key that encrypted messages came from the password and never
  changed.** If the password leaked months later, all traffic recorded up to
  that day could be opened retroactively. The key is now born again every
  session and dropped when it ends; the password's job is not to encrypt but
  to prove the other side belongs to the room.
- **Someone joining a room later received messages written while they were
  not there.** History was removed entirely in encrypted rooms — with forward
  secrecy a later joiner could not have opened it anyway. Rooms without a
  password keep their history.
- **The user list was whatever the server said it was.** The server could put
  any name on it. The list is now a proof: only people who can complete the
  key exchange appear by name.

## 1.8.0

- **Voice chat moved inside the application.** The server relays audio without
  decrypting it; the interface has join/leave, a participant list and mute.
- **The microphone carried keystrokes and idle hiss while nobody was
  speaking.** A noise gate arrived: the microphone is silenced when there is
  no speech. The stream itself does not stop — if it did, who spoke when would
  be visible on the network.
- **Trying to join voice through an older server waited forever**, because
  older servers never answer that request. It now gives up after five seconds
  and says why.
- When the two sides used different audio codecs the sound broke silently; it
  now reports an explicit error.

## 1.7.0

- **Room history was on by default.** Everyone entering a room received
  everything written before they arrived. The default is off now, and even
  when on it lives only in memory, never on disk, and is gone when the server
  stops.
- **The password was derived with PBKDF2, and a graphics card could run
  thousands of guesses at once.** Argon2id replaced it: every guess now costs
  64 MiB of memory as well, so the cost of guessing in parallel is multiplied
  by memory.
- **The "generate password" button showed the password on screen.** It can now
  be copied without being shown; the copy is kept out of the Windows clipboard
  history and the cloud clipboard, and is cleared after 30 seconds.
- **With history off, switching rooms wiped the view.** Messages you have seen
  are now kept in memory and come back when you return, with a note for the
  time you were away.
- **Re-entering the same room showed you yourself as having joined.**
- Someone moving between rooms appeared twice, as "left" and "joined"; it is
  one line now, and which room they moved to is not written.
- The logging helper still had the ability to write message length if it was
  handed content (the leak itself was closed in 1.5.0). That ability was
  removed too, so the leak cannot come back if some call passes content again.

## 1.6.3

- **A second server could open on the same port without an error.** Worse,
  while Host was listening on "all networks", another program could listen on
  the same port on `127.0.0.1` and take over Host's own connection. The port
  is now reserved exclusively for the server.

## 1.6.2

- **Host mode listened on every network interface.** That meant not only the
  VPN adapter but also the home or café network you were connected to, and
  virtual adapters. Using a VPN did not fix it. The network to listen on is
  now picked by hand from a list at every start; there is no default and the
  choice is not remembered.

## 1.5.0

- **The server's event log recorded the length of the ciphertext.** The
  content never entered the log, but the length tells you something on its
  own. It was removed.

---

Earlier versions were never distributed and are not listed here.
