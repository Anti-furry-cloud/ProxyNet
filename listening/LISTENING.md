[Türkçe](LISTENING.tr.md) · **English**

# Listening test: how do network interruptions sound?

ProxyChat does not have voice chat yet. Before building it, I want to know how
much interruption people will put up with in a conversation. The recordings in
this folder are **simulations, not real calls.** I would like to hear what you
think of them.

## What is in the folder

| File | What it is |
| --- | --- |
| `reference.wav` | The original recording, untouched |
| `sample-A.wav` | The same recording after passing through a simulated network |
| `sample-B.wav` | Same |
| `sample-C.wav` | Same |

All three samples went through **the same** simulated network: the same lost
and late packets at the same moments. They differ only in how the receiving
side handles those packets. I am not saying which is which yet, so that the
names do not influence what you hear.

The simulated network is synthetic. Its statistics were fitted to a measurement
between two home internet connections. It is not a recording of a real call.

## How to listen

1. Listen to `reference.wav` first.
2. Then listen to the three samples in any order. Relisten as often as you like.
3. If you can, use headphones.

The samples may also differ in delay. Delay cannot be heard in a recording
played on its own, so please judge only what you hear.

## Questions

1. For each sample, how disturbing were the interruptions?
   1 = I did not notice any, 5 = I could not follow the speech.
2. If this were a real conversation, which sample would you prefer? Why?
3. Compared with voice apps you use (Discord, WhatsApp calls, a phone call and
   so on), how were the interruptions in each sample: less, about the same, or
   more?
4. Did you listen with headphones or speakers?
5. Anything else you want to say.

Please answer in the **[Listening test](https://github.com/Anti-furry-cloud/ProxyNet/discussions/1)** discussion.
Answering in Turkish is fine too.

## What your answers will and will not change

- **They will not change the Phase 0 v2 decision.** Those rules were written and
  published before any v2 measurement; changing them after seeing opinions
  would defeat the purpose. See `VOICE_CHAT_PLAN.en.md`.
- They will inform later design choices: how the receiving side should trade
  interruptions against delay.
- This is a small, self-selected group of listeners. I will read the answers as
  notes, not as statistics.

## Revealing which sample is which

I wrote down which letter belongs to which variant in a separate file and am
keeping it private until the discussion closes. Its SHA-256 is:

```
892abdc6fe8fad450ac32eb5f0fa4469060a47d8b1fc72f6ad8d92e38c61f817
```

When I publish the file, you can check that it hashes to this value, which
shows that the assignment was not changed after the answers came in.

## Source recording

The speech is from the LibriVox recording of *The Gift of the Magi* by O. Henry,
read by Betsie Bush. LibriVox recordings are in the public domain. I used
roughly 43 seconds from the beginning of the story, converted to 16 kHz mono.
Thanks to the reader.
