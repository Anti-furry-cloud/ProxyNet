[Türkçe](VERIFYING.md) · **English**

---

# Verifying what you downloaded

The distributed program is **unsigned**, so Windows warns when you open it.
That is expected, and why it is that way is written down:
[THREAT_MODEL.en.md](THREAT_MODEL.en.md) 5.9.

What stands in for that warning is this: every release publishes a list of the
files' SHA-256 checksums (`SHA256SUMS.txt`) and a **signature** of that list
(`SHA256SUMS.txt.asc`). Check both and you can establish for yourself that the
file you hold is the file we produced.

---

## The signing key

```
Anti-furry-cloud <287824178+Anti-furry-cloud@users.noreply.github.com>
ed25519 · 2026-09-30 · expires 2028-09-29

Fingerprint:  23DC 905B 569A 80BD D243  525B 80DA 0356 E47B B37C
```

The key itself: [ProxyNet-imza-anahtari.asc](ProxyNet-imza-anahtari.asc)

---

## Three steps

You need GPG. On Windows it ships with Git for Windows
(`C:\Program Files\Git\usr\bin\gpg.exe`); open Git Bash and `gpg` just works.

**1. Import the key and check the fingerprint.**

```bash
gpg --import ProxyNet-imza-anahtari.asc
gpg --fingerprint 23DC905B569A80BDD243525B80DA0356E47BB37C
```

The fingerprint it prints must match the one above **exactly**.

**2. Verify the signature on the checksum list.**

```bash
gpg --verify SHA256SUMS.txt.asc SHA256SUMS.txt
```

You should see `Good signature from "Anti-furry-cloud ..."`.

> A `WARNING: This key is not certified with a trusted signature` is normal.
> We have not tied the key into anyone's web of trust; the warning means "I
> could not find someone who vouches for this key", not "the signature is
> invalid". What matters is that the fingerprint matches.

**3. Compare the files' checksums.**

```bash
sha256sum -c SHA256SUMS.txt
```

Every line should say `OK`. To check a single file by hand:

```powershell
Get-FileHash ProxyChat.exe -Algorithm SHA256
```

---

## If it does not match

**Do not install it.** In order:

1. Download the file again from the
   [official source](https://github.com/Anti-furry-cloud/ProxyNet) — a partial
   download will not match either.
2. If it still does not match, **tell us**. What you hold is not what we
   distributed.

---

## The limit of this, honestly

**On your first download this does not fully protect you.** Someone who takes
over the repository could change the program, the checksum list, the signature
*and* the public key together, and a first-time downloader could not tell.
This is the trust-on-first-use problem, and a signature does not solve it.

Where the signature genuinely helps:

- **Later releases.** Once you have the key, a change of key becomes
  *visible*. Quietly taking our place gets harder.
- **Verification from outside the repository.** If you got the fingerprint
  through another channel — in person, over the phone, written down somewhere
  else — an attacker has to change all of them at once.
- **If the distribution link is taken over.** When a copy is circulating
  elsewhere, the signature shows whether it came from us.

The same reasoning applies to the room password: sharing it face to face is
the same move as checking this fingerprint out of band.

---

## Building it yourself

The build is **reproducible** (since 1.12.4): anyone building from the same
commit gets a bit-for-bit identical file. So you do not have to trust the
checksum — you can rebuild and compare. Each release publishes a build
manifest saying which inputs were used. Detail:
[THREAT_MODEL.en.md](THREAT_MODEL.en.md) 5.9.
