[Türkçe](SECURITY.md) · **English**

# Security

## What to know first

This software **has not been independently audited.** It was written by one
person and its cryptography has not been professionally reviewed.

The known and **accepted** gaps are listed one by one in section 5 of
[THREAT_MODEL.en.md](THREAT_MODEL.en.md). You do not need to report these — we
already know:

- Metadata is not protected (username, room name and timestamp travel in the
  clear; message size has been rounded to a bucket since 1.12.0)
- The transport layer is unencrypted; envelope packets can be forged
- No authentication on the server, and no password is needed to enter a room
- A weak password can still be attacked offline despite Argon2id; someone who
  finds it can impersonate the key exchange of a **live** session
- Protection against memory seizure is partial (keys cannot be zeroed
  reliably in Python)
- No post-compromise security (the Double Ratchet equivalent)
- The distributed binary is unsigned

Gaps that have been closed — no need to report these as missing, but **a finding
showing they are not actually closed would be very valuable:**

- **Forward secrecy is in place** (text 1.9.0, voice 1.10.0): the key is born
  again every session, the password only authenticates
- **No history at all is kept in an encrypted room** (1.9.0)
- **Message length is hidden by padding** (1.12.0): the payload is rounded up
  to buckets starting at 32 bytes, so all short messages go out at the same
  size on the wire
- **The user list is verified by proof**, the server's claim is not trusted (1.9.0)

**No protection against a state-level adversary is claimed.**

## What you should report

Anything not on the list above. In particular:

- A bug that causes message content to go unencrypted or to be encrypted
  incorrectly
- Any path that gives the server access to plaintext
- A flaw that allows reading messages without knowing the room password
- Remote crash, memory exhaustion, infinite loop
- Any situation where a password or key ends up written to disk in the clear
- A difference between the binary built from source and the published binary

## How to report

**Do not open a public issue.** Instead:

> GitHub → the **Security** tab of this repository → **Report a vulnerability**
> (Privately report a security vulnerability)

This delivers the report so that only the repository owner can see it.

If you have no GitHub account, or would rather not use that route:
**proxynet.dev@protonmail.com**. One thing to know: email is end-to-end
encrypted only from Proton to Proton; mail sent from another provider can be
read on the way. Before sending a proof of concept, say in the first message
only what the problem is, and we will choose together how to pass on the
details.

It helps a great deal if your report includes:

1. The affected version (shown in the application's title bar)
2. The steps that trigger the problem
3. Expected versus actual behaviour
4. A proof of concept, if you have one

## What you can expect

This is a hobby project with no company behind it. The only thing I can promise
is honesty:

- I will read your report and acknowledge receipt
- If it is valid I will record it in `THREAT_MODEL.md` — even if I cannot fix it
- If a fix ships, I will say so in [CHANGELOG.en.md](CHANGELOG.en.md)
- I will credit you if you want, and not if you don't

**I cannot commit to a fixed response time.** Promising one on a one-person
project would be a lie.

## Supported versions

Only the **latest release.** Older versions do not receive backported fixes;
please update.

## Out of scope

- Compromise of the endpoint (keylogger, screenshots, memory dump)
- The channel used to share the room password — if you share it somewhere
  insecure, the chain breaks there
- Choosing a guessable password
- Vulnerabilities in the operating system, the VPN client or the hardware
- The SmartScreen warning — the binary is unsigned, this is known

---

*The Turkish [SECURITY.md](SECURITY.md) is the source of truth. If the two
disagree, the Turkish one is correct.*
