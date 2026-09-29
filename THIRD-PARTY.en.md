[Türkçe](THIRD-PARTY.md) · **English**

---

# Third-party components

ProxyChat is distributed under GPLv3 ([LICENSE](LICENSE)). What follows is
other people's work; it comes with its own licences, and their terms bind us
too.

Only components that end up **inside the distributed file** are listed here.
Tools used while developing but not packaged (pytest, PyInstaller itself) are
not.

---

## libopus

| | |
| --- | --- |
| What it does | Compresses speech in voice chat: 20 ms of raw audio goes from 640 bytes to 60. If it is missing the program falls back to µ-law and keeps working (320 bytes), so it is **not required** |
| Version | `libopus 1.6.1` — the string the library reports itself (`opus_get_version_string`) |
| Licence | BSD 3-clause — compatible with GPLv3 |
| Source | https://opus-codec.org |
| Code | `core/voice_opus.py` (bound directly with ctypes, no wrapper package) |

**The file we ship.** The `libopus.dll` currently in hand:

```
SHA-256  4369edc456631a3cc933d7918747e5d2d111056dbc8a85b01330b5a53c062d44
size     482,816 bytes
```

**The provenance of this binary has not been verified.** It was taken out of
the PyAV package; it is not a file we built from the source archive Xiph
publishes. THREAT_MODEL.en.md 5.9 and `docs/sesli-sohbet-plani.en.md` carry
this as an open item: a real release must build it from source. As a loose
file handed over by hand this mattered less; once the DLL is packed into the
executable, a binary of unverified origin travels **inside** the artifact
whose checksum we publish.

**What is missing.** BSD 3-clause requires a binary distribution to reproduce
"the above copyright notice" as well. The conditions below are reproduced
verbatim from opus-codec.org, but **the line naming the copyright holders is
not written here yet**: the authoritative version of it lives in the `COPYING`
file of the source archive and could not be verified when this was written.
Rather than write it from memory, it was left out. When the DLL is built from
source (the open item above) `COPYING` comes with it and the line will be
copied from there **verbatim**. The two are one job; no release should be
distributed before it is done.

### Licence text

> Redistribution and use in source and binary forms, with or without
> modification, are permitted provided that the following conditions are met:
>
> - Redistributions of source code must retain the above copyright notice,
>   this list of conditions and the following disclaimer.
>
> - Redistributions in binary form must reproduce the above copyright notice,
>   this list of conditions and the following disclaimer in the documentation
>   and/or other materials provided with the distribution.
>
> - Neither the name of Internet Society, IETF or IETF Trust, nor the names of
>   specific contributors, may be used to endorse or promote products derived
>   from this software without specific prior written permission.
>
> THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS ``AS
> IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
> THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
> PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
> CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
> EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
> PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
> OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
> WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
> OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
> ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

Opus is also covered by several patents, which are granted under
open-source-compatible, royalty-free licences. The detail is at the address
above.

---

## Qt / PySide6

| | |
| --- | --- |
| What it does | The interface, the audio device layer, storing settings |
| Licence | **LGPLv3** |
| Source | https://www.qt.io — PySide6: https://pypi.org/project/PySide6/ |

LGPL asks that if the library itself is modified its source is provided, and
that the user be able to **relink it with a modified version**. Qt is not
modified; it is packaged as it comes.

This is also one of the reasons a closed-source or obfuscated distribution
would be a problem: honouring that obligation inside a single-file bundle gets
needlessly hard.

## cryptography

| | |
| --- | --- |
| What it does | AES-GCM, X25519, HKDF, Argon2id |
| Licence | Apache 2.0 **or** BSD 3-clause (either may be chosen) — compatible with GPLv3 |
| Source | https://pypi.org/project/cryptography/ |

---

This file has to stay current: when a new third-party component enters the
package, a row belongs here too. `tests/test_lisans_basliklari.py` locks part
of that.
