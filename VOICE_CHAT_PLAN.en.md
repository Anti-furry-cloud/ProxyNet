[Türkçe](VOICE_CHAT_PLAN.md) · **English**

# Voice chat — design plan

> **Publication note (2026-09-16):** The source code is not open yet; the file
> paths in the text (such as `core/voice_crypto.py`) are not visible and were
> deliberately kept so that, once the code opens, every claim here can be
> checked at its source. **This plan is not a finished design.** In particular,
> the encryption scheme in section 3 has had no independent review. That is
> exactly why it is published early: so its mistakes are found before more code
> is written on top of it. **Update (2026-09-16):** after publication a serious
> bug was found in the scheme in section 3 and fixed. What it was, how it was
> found and the fix are written out plainly in section 3.

Status: **Phase 1 started, the core is written, and the prototype has carried
a conversation between two computers.** The audio packet format, encryption and
jitter buffer live under `core/` and are tested. Audio hardware and networking
now exist, but only in a command-line tool that is not distributed; the UI side
does not exist yet. Phase 0's decision gate is **still open**: three of the v2
measurements are done and two are missing.

Goal: letting a group of 2–5 friends talk over a virtual LAN (VPN) or a local
network. Not replacing Discord.

---

## 1. Why the existing protocol cannot be used directly

Today's transport is newline-delimited JSON over **TCP**. It has two problems
for audio:

- **Head-of-line blocking.** TCP holds everything behind a lost packet until it
  is retransmitted. Correct for text, disastrous for audio: delay accumulates
  and speech becomes choppy.
- **A late audio packet is garbage.** Audio is real-time; there is no value in
  correctly delivering a packet that is 300 ms late — it should be dropped. TCP
  cannot do that, UDP can.

Decision: **UDP for audio, the existing TCP channel for signalling.** The two
work together; the TCP channel already holds the answer to "who is where".

There is an advantage in this scenario: because a virtual LAN is already set
up, NAT traversal (STUN/TURN, ICE) is not needed. That is the most expensive
part of voice chat in the real world, and here it comes for free. The price is
depending on that virtual network.

---

## 2. Architecture

### 2.1 Topology

| Option | Pro | Con |
| --- | --- | --- |
| **Mesh** (everyone to everyone) | Zero server CPU, end-to-end encryption is natural | N-1 times the upstream; painful beyond 5 people |
| **Server-side mixing** | Client sends a single stream | The server must **decrypt** the audio → end-to-end encryption dies |
| **Relay (SFU, no mixing)** | Client sends one stream, server forwards without seeing the plaintext | Bandwidth on the server, slightly more complex |

**Decision (2026-09-16): relay through the host.** In a mesh, the `voice_peers`
packet would hand every participant's IP address to everyone in the room — a
new leak against [THREAT_MODEL.en.md](THREAT_MODEL.en.md) principle 3
("metadata is data too"). With a relay the host keeps seeing the IPs it already
sees, and participants do not see each other's.

The cost of relaying is affordable:

| | Mesh | Relay through the host |
| --- | --- | --- |
| One-way latency | direct | one extra hop, roughly double — the "good" threshold is 150 ms |
| Host upstream (4 people, Opus) | 0 | ~0.6 Mbit/s — everyone sends all the time (§4, silence suppression off); far below an ordinary home connection |
| IP leak | everyone sees everyone | only the host (same as in text chat) |
| Firewall permission | on every participant | only on the host |

Mixing is still **never**: a server that can hear the audio throws away this
project's encryption promise. A relay never touches the encrypted bytes.

This is a prototype decision. If the participant count grows or the host's
upstream becomes the bottleneck, mesh gets reconsidered; the packet format
supports both.

### 2.2 Signalling (over the existing TCP channel)

New packet types:

| Packet | Direction | Content |
| --- | --- | --- |
| `voice_join` | client → server | UDP port, session salt (16 bytes) |
| `voice_leave` | client → server | — |
| `voice_peers` | server → client | voice participants in the room: `user`, `sender_id`, session salt — **no IP** |

The server never touches audio data; it only knows who is in voice chat and
where to forward the packets. **It does not know who is speaking or who has
muted their microphone** (2026-09-19): the `voice_state` packet of the first
draft (`muted`, `speaking`) was dropped. The reason is in the Opus research in
§4: the audio stream flows at a constant rate whether anyone speaks or not,
and handing that information to the server separately would undo it.

### 2.3 Audio packet format (UDP)

Binary, not JSON. 20 ms frames. Written: `core/voice_packet.py`.

```
[ 1 byte  ] version
[ 1 byte  ] type
[ 4 bytes ] sender id              ] cleartext, and at the same time
[ 8 bytes ] sequence number        ] additional authenticated data (AAD)
[ 4 bytes ] timestamp (ms)         ]
[ N bytes ] encrypted audio + 16-byte GCM tag
```

The header is 18 bytes. Two differences from the first draft:

- **The nonce is not transmitted.** Both sides derive it from the header (§3
  below), saving 12 bytes per packet.
- **The sequence number is 8 bytes.** At 4 bytes, wrapping would have required
  rotating the session key; 8 bytes never wrap in practice at 50 packets per
  second, so that mechanism is not needed.

The header being cleartext follows from the relay decision: the host must be
able to read who sent a packet in order to forward it. Because the header is
also the AAD, the host **cannot change it** — if it does, the receiver's
decryption fails. Total encryption overhead is 16 bytes per frame (just the GCM
tag).

---

## 3. Encryption — use the existing room password, but not with Fernet

Audio must also be encrypted with a key derived from the room password;
otherwise text would be encrypted while audio is in the clear, and the promise
becomes inconsistent.

However, the **Fernet used on the text side is the wrong tool for audio**:

- ~57 bytes of fixed overhead per token **plus** base64 (33% inflation). With a
  20 ms frame at 640 bytes, that is unacceptable.
- Fernet carries a timestamp and leaves replay protection to the caller.

Decision: **AES-GCM, with a separate key for every sender in every voice
session.** Written: `core/voice_crypto.py`, scheme label `aesgcm-hkdf-v2`.

```
room password ──Argon2id──▶ master key ──HKDF──▶ voice key
voice key + session salt + sender id ──HKDF──▶ session key
```

- The **master key** is shared with the text side: the text key is its
  base64 form, and a test verifies it. Since 1.7.0 the master key is derived
  with Argon2id.
- The **voice key** is derived with `HKDF(info=b"proxynet-voice-v1")`. It is
  not the same as the text key, and nothing is encrypted with it directly.
- **Session salt:** every time a sender joins voice chat, it generates a
  random 16-byte salt and announces it with `voice_join`. The salt is not
  secret; the host sees it too, but without the password it does not yield the
  key.
- **Session key:** `HKDF(salt=session salt, info=b"proxynet-voice-session-v1"
  + sender id)`. Packets are encrypted with it.
- **Nonce** = 4 bytes of sender id + 8 bytes of sequence number. It is not sent
  on the wire; both sides derive it from the header.
- On the sending side the sequence number must be **strictly increasing**. An
  attempt to seal with the same or a smaller number is not passed over
  silently; it raises an error.
- **Replay protection:** a 64-packet sliding window (the RFC 3711 approach),
  kept per sender. Registering the same salt again does not reset the window;
  if it did, a repeated `voice_peers` packet would let old packets be accepted
  again.
- If our own id is registered **with a different salt**, an error is raised.
  That means the host gave the same id to two people.
- In passwordless rooms audio is not encrypted either — the same choice as on
  the text side. The wire format and session rules do not change.

### Bug found: nonce reuse across sessions (2026-09-16, fixed)

The first version (`aesgcm-hkdf-v1`) had no session key; every packet was
encrypted directly with the voice key. Because the voice key is derived from
the room name and password, **it never changes.** The consequence:

1. Today Ayşe gets `sender_id = 1` and her sequence number counts from 0.
2. Tomorrow the host restarts; same room, same password. Ayşe gets
   `sender_id = 1` again and her sequence starts from 0 again.
3. **Same key, same nonce.** In AES-GCM this reveals the XOR of the two frames'
   plaintexts. If one of the frames is predictable (such as silence, which is
   common in speech), the other can be read directly. The authentication key
   also leaks, which allows forged packets.

The same happened within a single session: the sequence number of someone who
left and rejoined started from zero, and the first version of this document
described that as the normal flow. The requirement that "the sender id must be
unique within a session" did not protect across sessions.

- **How it was found:** while reviewing DAVE, Discord's end-to-end encryption
  for voice. DAVE derives a separate key for each sender and renews keys when
  membership changes; our design had no equivalent.
- **Verification:** before the fix the scenario was tried with a script. Text
  from a frame of the earlier session was recovered with the help of a silent
  frame from the later session. After the fix the same script produces
  meaningless bytes.
- **Impact:** the voice code does not yet run connected to a network anywhere;
  no real traffic was affected. But the design had been published in this
  document.
- **Fix:** the session salt above. Nonce reuse now requires two sessions to draw
  the same 128-bit salt. Confidentiality no longer depends on the sender id
  being unique, and a packet recorded from an earlier session cannot be
  decrypted with a new session's key.
- **Tests:** `OturumAyrimiTests` in `tests/test_voice.py`, including the attack
  scenario itself.

**What this design does not solve:** anyone who knows the room password can
derive any sender's session key, so room members can forge packets in each
other's name. The text side is the same. DAVE solves this with authenticated
group key exchange through MLS; that is outside the project's current scope.

**Warning:** this scheme was designed by one person and has not been reviewed
from outside. The bug in its first version shows why that matters. If you see
another mistake, I want to hear it.

---

## 4. Audio capture and playback

Qt's audio interfaces (`QAudioSource` / `QAudioSink`) will be used. They ship
with the existing UI library, so no new dependency is needed.

**Careful — this affects packaging:** Qt's multimedia modules are currently
excluded from the application bundle **on purpose** (part of a choice that cut
the executable's size substantially). If voice chat happens, that must be
reversed and the resulting growth **measured**, not guessed.

### Codec

| Stage | Codec | Bandwidth (mono) | Why |
| --- | --- | --- | --- |
| Prototype | G.711 µ-law 16 kHz | ~128 kbit/s | No new binary dependency, proves the path |
| Release | Opus, constant bitrate | 24 kbit/s | ~4× smaller datagrams, better quality for speech, FEC that rebuilds a lost packet |

The prototype uses a codec that needs no external library, which keeps codec
problems from getting mixed up with network problems. The first run used 8 kHz
and sounded like a telephone, so it was raised to 16 kHz. µ-law is temporary:
the standard library module it relies on (`audioop`) was removed in Python
3.13.

### Opus research (2026-09-18)

The trials used the public-domain recording from the listening test; the
loss was generated at random, not taken from a real line. What follows are
proposed decisions, not final ones.

- **Binding: libopus directly.** The ready-made Python packages that run
  Opus bring the whole of FFmpeg, video codecs included, tens of MB. `libopus`
  on its own is a small library that can be called directly with `ctypes`;
  the only code decoding untrusted packets from the network is then libopus.
  Its licence is BSD 3-clause, compatible with the project's GPLv3.
- **Constant bitrate (CBR), silence suppression (DTX) off.** With variable
  bitrate the packet size follows the speech and gives silence away plainly.
  Recovering parts of what was said from packet sizes in encrypted VoIP is a
  published attack (Wright et al., 2008). With CBR every packet came out
  the same size. DTX stays off for the same reason: not sending packets
  during silence tells the network who speaks when. The cost is that
  everyone uses bandwidth all the time, speaking or not (§2.1).
- **FEC works.** A lost frame can be rebuilt from the copy carried in the
  next packet; for that the buffer has to stay at least one frame ahead.
- **Supply chain.** The library that gets distributed should be built by us
  from the source archive Xiph publishes; distributing a binary another
  project built means trusting that project's build pipeline.

| Codec | Frame (20 ms) | Datagram (header + GCM tag included) |
| --- | --- | --- |
| µ-law 16 kHz (prototype) | 320 bytes | 354 bytes |
| Opus 24 kbit/s CBR | 60 bytes | 94 bytes |
| Opus 16 kbit/s CBR | 40 bytes | 74 bytes |

Open: 24 or 16 kbit/s (to be decided by listening); stay at 16 kHz or move
to 48 kHz; what FEC gains on a real line, where losses come in bursts.
Because the jitter buffer's code stays unchanged until the Phase 0 v2 gate
is decided, Opus goes into the prototype first.

---

## 5. Jitter buffer — not optional

UDP packets arrive out of order, at irregular intervals, and some never arrive
at all. Writing them straight to the speaker produces harsh audio.

Written: `core/voice_jitter.py`. It contains no clock, no socket and no Qt;
input is a sequence number and a byte string, output is an ordered run of
frames. `pop()` is called as the audio device consumes (about every 20 ms)
and silence or loss concealment is played for that frame when it returns
`None`. The sound card, not a timer, sets the pace of those calls; the
measurements behind that are in the prototype section.

- Target buffer **60 ms**. The adaptive version does not exist yet.
- Reordering by sequence number.
- Packets that fall behind the buffer are dropped.
- Missing frames are replaced with silence. The faded repeat does not exist yet.
- **If the buffer empties completely, it goes back to filling.** Continuing to
  consume an empty buffer would run the sequence counter ahead, and every frame
  would be counted as "late" once the other side started speaking again.
- If the sender restarts (a sequence number absurdly far away in either
  direction), the stream is reset.

### Weakness found: accumulating delay (2026-09-16, fixed)

The first version of the buffer played the frames that piled up after a
latency spike exactly as they came. When the buffer emptied during a spike and
refilled, it started from the oldest frame, and because nothing melted the
excess above the target, **every spike was added to the delay permanently.**
None of the 54 unit tests at the time caught it: they verified individual
behaviours, not accumulation over a long stream.

**How it was found:** `tools/ses_simulasyonu.py` runs a speech recording
through a synthetic network trace fitted to the statistics of a real
measurement (~1.3% loss, with 100–280 ms stalls in between) and through this
buffer, and writes the result as a `.wav`. Tracking the delay second by second
showed it starting at 80 ms, rising at every stall and staying at 300 ms.

**Fix — catching up:** when the buffer rises 40 ms above its target, it melts
the excess bit by bit and stops once it is back at the target.

- If the next slot is already empty (a lost packet), it is skipped instead of
  playing silence there.
- A real frame is dropped at most once every 5 frames, and only if the empty
  slots in the buffer do not already cover the excess. 200 ms of build-up melts
  in about a second, and the loss is spread into 20 ms pieces instead of one
  long gap.
- WebRTC's NetEq does the same job by compressing decoded audio in time
  without changing pitch. This buffer works with encrypted or encoded bytes, so
  that route is closed at this layer.

**The cost, honestly.** Same network trace, averaged over three random seeds,
43 seconds of speech:

| | No catching up (first version) | Catching up (40 ms slack, every 5 frames) |
| --- | --- | --- |
| Median delay (network + buffer) | 280 ms | 80 ms |
| Time above 150 ms | 35.9 s | 3.2 s |
| Gaps within speech | 0.89 s | 1.95 s |
| Speech dropped to catch up | 0 | 1.25 s |

Because the first version accumulated delay, it had unintentionally turned into
a large 300 ms buffer that swallowed later stalls without gaps. The new buffer
returns to its target, so it empties at every stall. A larger slack reduces the
gaps somewhat but brings the delay back (100 ms slack, every 10 frames: median
127 ms, gaps 1.56 s). No setting wins on both; if the line really stalls, this
layer can only wait or skip. Delay is more damaging than interruption in a
conversation, so the default sits on the low-delay side.

What would reduce the remaining gaps lives outside this layer: an **adaptive
target** that grows temporarily on a line that stalls often and shrinks again
once it calms down, **time compression** of decoded audio (an unnoticeable
speed-up instead of dropping speech), and **Opus FEC** to rebuild the odd lost
packet.

---

## 6. Interface

- A "Voice chat" section in the left sidebar, with a join/leave button.
- A list of participants; the speaker's name is highlighted (simple RMS
  threshold; each receiver computes it from the audio it decrypts, nothing
  about it comes over the network).
- Mute and push-to-talk do not stop the outgoing stream: while the key is
  not pressed or the microphone is muted, silence frames keep going, so no
  difference shows from outside.
- Mute (microphone) and deafen (speaker) buttons.
- A **push-to-talk** option — on by default.

### The echo problem, honestly

Qt has no acoustic echo cancellation (AEC). Sound from the speaker re-enters
the microphone and the other side hears themselves. A real solution is
WebRTC-level work and far outside this project's scale.

The realistic approach: **headphones are recommended** and push-to-talk is on
by default. Every small project solves it this way; it must be stated openly in
the documentation.

---

## 7. Testability

The existing test suite must not rot when audio is added. The only way to
achieve that is to **put the audio hardware behind an interface**:

- An `AudioDevice` protocol: `read_frame()` / `write_frame()`. The real
  implementation uses Qt; tests use a fake one (a synthetic wave). **Not
  written yet.**
- ✅ Jitter buffer unit tests: feed out-of-order, duplicated and missing
  packets, assert the resulting frame order. Also that delay returns to the target after
  a latency spike and that catching up stays rate-limited.
- ✅ Crypto tests: AES-GCM round trip, wrong password cannot decrypt, a repeated
  packet is rejected, a tampered header cannot be decrypted, two sessions with
  the same id do not produce the same keystream (the regression test for the
  bug in §3).
- ✅ End-to-end test: synthetic audio → encrypt → a broken network (loss,
  reordering, duplicates) → decrypt → buffer → the correct frame order.

All of it is in `tests/test_voice.py`, 76 tests. They use no audio hardware, no
sockets and no Qt, so they run in CI. No test that requires audio hardware
should run in CI.

---

## 8. Phases

| Phase | Work | Output |
| --- | --- | --- |
| **0. Measurement** | A small tool measuring UDP latency, jitter and loss | **Decision gate**: if the numbers are bad, the plan stops here — v1: BAD; v2: three of five measurements done, two pending |
| **1a. Core** ✅ | Packet format, AES-GCM + HKDF, jitter buffer, tests | A tested core that works without audio hardware |
| **1b. Skeleton** | Signalling packets, UDP socket, relaying on the host, µ-law 16 kHz, one direction | One person speaks, the other hears |
| **2. Two-way** | Audio device interface, Qt integration, both directions | Two people talk to each other |
| **3. Usability** | Opus, push-to-talk, speaking indicator, mute | Four people can use it |
| **4. Packaging** | Put Qt's audio modules back in the bundle, measure the size, UDP firewall rule, documentation | A distributable release |

Phase 1a did not wait for Phase 0 because none of the three modules written
depend on the network measurement. What a bad result would stop is 1b onwards.

**Phase 0 must be taken seriously.** On some connections virtual-LAN software
cannot establish a direct peer-to-peer tunnel and routes traffic through its
own relay servers; in that case latency may not be good enough for voice.
Starting Phase 1b without measuring this means, in the worst case, weeks of
work turning out to be unusable.

### Phase 0 measurement tool (v1)

> This subsection describes v1. The measurements under the v1 rules came out
> BAD; the rules in force are below, under **Phase 0 v2**.

`tools/ses_olcum.py` — standard library only, runs standalone.

- One side picks **Wait**, the other picks **Measure** and types the other
  side's address. The measuring side needs no firewall permission; the waiting
  side is asked to allow a UDP port.
- Two measurements at 20 ms intervals (one audio frame), 30 seconds each:
  Opus-like ~120-byte packets and raw-PCM-sized ~700-byte packets.
- Measured: round-trip latency (median, 95th percentile, maximum), loss **in
  each direction separately**, out-of-order packets, RFC 3550 jitter, and the
  share of packets that miss a 60 ms buffer. The two computers' clocks differ,
  so one-way figures are computed in a way that the clock offset cancels out.
- The result is printed and saved to a text file. The file contains no IP
  address.

Verdict thresholds (one-way latency estimate = round-trip median / 2;
effective loss = loss + packets missing the buffer, worse direction):

| Verdict | One-way latency | Effective loss |
| --- | --- | --- |
| **Good** | ≤ 150 ms | ≤ 1% |
| **Acceptable** | ≤ 300 ms | ≤ 3% |
| **Bad** — the plan stops here | more | more |

Latency thresholds follow ITU-T G.114. **The verdict follows the Opus
measurement**; the PCM measurement only shows whether the prototype stage will
work.

Known limits: a fixed 60 ms buffer is stricter than the planned adaptive buffer
(results may be pessimistic); the fastest packet's transit time is used as the
baseline; a measurement is a snapshot and should be repeated at different times
of day.

### Phase 0 v2 — rules written before measuring (2026-09-17)

**This section was written and committed before the v2 measurements; the commit
date is the evidence.** The rules below will not be changed after the results
are seen.

#### The v1 result

Three measurements were made under the v1 rules between two separate internet
connections, and all three came out **BAD**. Latency was not the problem; loss
and momentary stalls were. That result stays on record and is not
reinterpreted. It does not feed into the v2 decision either; it could not,
because v1 kept no per-packet record.

#### Why v2, and the weakness of that

v1 asked: can this line carry voice with a fixed 60 ms buffer and no loss
concealment? The plan had called for a catching-up buffer and loss concealment
from the start, and the possibility that v1 would be pessimistic was written
down before measuring (above, "Known limits"). **But the wish to write v2 arose
after seeing the bad result.** I am not hiding that; the rules below exist to
keep that weakness from bending the decision.

#### Method

1. The measurement tool (`tools/ses_olcum.py`, record version 2) records the
   send and arrival time of **every packet** in both directions. The protocol
   version changed so it cannot mix with the v1 tool; the two versions ignore
   each other's packets.
2. The decision is not made in the tool. `tools/ses_degerlendir.py` runs the
   record through **the real jitter buffer code** (`core/voice_jitter.py`),
   simulating an audio device that asks for a frame every 20 ms.
3. That playback loop is **the same function** the simulation tool uses to
   produce audio. When the simulation was moved onto this function, all of the
   previously produced audio files came out byte-for-byte identical.
4. Because the two computers' clocks differ, the fastest packet's one-way time
   is taken as half of the shortest round trip. The sender's timing deviation is
   left out; in a real voice application the sound card's clock produces frames
   at a steady rate.
5. **No credit is given for FEC:** the listening the threshold rests on had no
   FEC.

#### Metrics and thresholds

- **Interruption rate:** the share of frames that could not be played during
  speech: gaps, frames dropped to catch up, and empty slots skipped.
- **Mouth-to-ear delay, 95th percentile:** network + buffer + a 40 ms audio
  device allowance. v1 used the median; the 95th percentile is stricter and does
  not hide a buffer accumulating delay.
- For each measurement **the worse of the two directions** counts. As in v1, the
  decision is made on the Opus-like small-packet phase.

| Verdict | Interruption rate | Mouth-to-ear 95th pct. |
| --- | --- | --- |
| **Good** | ≤ 1% | ≤ 150 ms |
| **Acceptable** | ≤ 5.8% | ≤ 300 ms |
| **Bad** | more | more |

The Good thresholds are the same as in v1. The latency thresholds follow
ITU-T G.114.

**The Acceptable interruption threshold (5.8%) rests on a listening.** The
product owner listened to a speech recording produced from a synthetic network
trace fitted to the statistics of a measurement on 16 September, with the
catching-up buffer and faded repeat, and found the interruptions on the same
level as the occasional interruptions on Discord. The threshold is that
recording's interruption rate as measured by this evaluation: 75 gaps, 46
dropped frames and 3 skipped empty slots in 2137 frames. The reference
recording's SHA-256 is `060f1138…0e39`; a test recomputes the threshold
(`tests/test_ses_degerlendir.py`).

The weaknesses of this threshold:

- a single listener;
- a robotic text-to-speech voice;
- delay cannot be heard in a recording played on its own, so the latency
  threshold stays a number;
- the judgement was made **after** the v1 results were seen.

#### How many measurements, and which count

- Measurements are counted in date order. **At most 3** count from one calendar
  day, and the **first 5** counted measurements decide. Later ones are ignored:
  continuing to measure until a good result shows up achieves nothing.
- **The worst measurement is left out;** the worst of the remaining four is the
  gate decision.
- Before each measurement the tool asks a short checklist (downloads,
  connection type, screen sharing). The answers go into the record before the
  result is seen, but they are notes only.
- **No measurement is removed afterwards.** Even if a disturbing condition is
  discovered later, the measurement counts. The tolerance for a single outlier
  is the "worst one left out" rule.
- A measurement whose per-packet record from the other side could not be
  retrieved counts as **BAD**, so that it cannot become an excuse to measure
  again.
- Wireless connections are allowed; the target audience is mostly on wireless
  networks.

#### Decisions bound in advance

- **Good or Acceptable:** Phase 1b starts.
- **Bad: no v3 will be written.** These rules will not be changed again. The
  only step allowed is to change the infrastructure (another VPN, a cable,
  another counterpart) and measure again **under the same v2 rules**.
- If the buffer code is changed after the v2 records are seen, **the same
  records are not evaluated again;** new measurements are needed. Otherwise the
  code would have been fitted to the measured data.

#### Status: first day (2026-09-17)

Three counted measurements were made and all three stayed within the
**acceptable** thresholds. The remaining two fall on another day; at most
three count from one day. The gate decision comes when five are complete: the
worst is left out and the worst of the remaining four decides. The numbers are
not published here; when the decision is announced, its reasoning will be
written down with it.

---

### Voice chat prototype (2026-09-17)

The end-to-end audio path was tried on a real line for the first time:
microphone → 20 ms frame → encryption → UDP → jitter buffer → loss
concealment → speaker. Two computers on two separate internet connections
**held a live conversation and the speech came through intelligibly.**

The prototype is not part of the distributed program: it is a separate
command-line tool and is not wired into the interface. Its purpose is to try
the networking side.

Two bugs were found by doing it, and both were fixed:

- **No packets were being received at all.** The network socket was created
  before Qt's application object, and the "data has arrived" notification is
  never connected in that case. The program was sending and receiving
  nothing. The first tests missed this because they created the application
  object themselves beforehand; the new test runs in a separate process.
- **Delay grew for nothing.** Playback hung off a 20 ms timer. Windows timer
  resolution is ~15.6 ms, so playback fell behind what the microphone
  produced and the difference piled up in the buffer: the target was 60 ms
  but the buffer sat at 80-100 ms. There was no loss, only delay. Pull mode
  (`QIODevice`) was tried and came out worse: the sound card asks for several
  frames at once, so the buffer swung between 0 and 460 ms. The chosen way is
  to look at the card's free space and write at most one frame at a time, so
  the sound card sets the pace. Measured locally: the buffer holds at 40 ms,
  with zero underruns and zero dropped frames over 30 seconds.

The jitter buffer's code was **deliberately left alone.** Under the Phase 0 v2
rules, if that code changes after the measurement records are seen the same
records cannot be re-evaluated; loss concealment therefore lives in the
prototype rather than in the buffer.

### Real-use trial (2026-09-18) — does not count toward the gate

The prototype carried a real, uninterrupted, encrypted conversation of more
than an hour between two separate internet connections. The impression of
the people talking: "it feels like using Discord."

- By the Phase 0 v2 definition, the interruption rate stayed below 1.5% in
  both directions.
- After a few short spikes and one stall of a few seconds, the buffer
  recovered on its own every time.
- The frames missing during that stall were **not counted as lost**,
  because there was no gap in the sequence numbers. A stall on the sending
  side (the microphone not producing frames) does not show up in the
  prototype's current counters; the next version will count it separately.

**Why it does not count toward the gate:** Phase 0 v2 is measured with the
measurement tool and small Opus-like packets, while this used 354-byte
µ-law packets; mouth-to-ear p95 was never measured; and choosing which data
counts after seeing the result is exactly the mistake the pre-registration
is meant to prevent. This session stands as separate evidence.

---

## 9. Open security questions

These are known, well-defined problems that must be solved before 1b. They are
written down here to prevent anyone treating them as solved.

- **How will `sender_id` be assigned?** The host should assign it and must
  not give the same id to two people within a session: the id decides where a
  packet is forwarded and which replay window it falls into.
  **Confidentiality no longer depends on it** (the session salt in §3), but a
  collision would mix up voices. A client notices when its own id is
  registered with a different salt and raises an error; the host-side
  assignment rule will be written in 1b.
- **There is no authentication for the relaying host.** The host decides where
  to forward an audio packet from its `sender_id`. If someone who is not in the
  room sends the host a UDP packet, the host cannot decrypt it but could still
  forward it. This will need rate limiting and some form of authentication.

Closed questions:

- ~~Mesh or relay?~~ → **Relay through the host** (2026-09-16, §2.1).
- ~~Nonce reuse across sessions~~ → **session salt** (2026-09-16, §3). This
  was not found as a question but as a bug in the published design.
- ~~Switch to relay automatically beyond 4 participants?~~ → Relay from the start.

---

*The Turkish [VOICE_CHAT_PLAN.md](VOICE_CHAT_PLAN.md) is the source of truth.
If the two disagree, the Turkish one is correct.*
