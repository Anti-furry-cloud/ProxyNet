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

**The file we ship — built from source (1.12.3).**

```
SHA-256  1d5fcc90b31e982a066db1e1e3128d8673fce5c5adaab11d1cd808d54a3ee66c
size     625,664 bytes
```

Before this, the file had been taken out of the PyAV package and its
provenance was unverified. It is now built from the source archive Xiph
publishes:

| | |
| --- | --- |
| Source archive | `opus-1.6.1.tar.gz` |
| SHA-256 of the archive | `6ffcb593207be92584df15b32466ed64bbec99109f007c82205f0194572411a1` |
| Compiler | MSVC 14.51.36231 (Visual Studio 2026), x64 |
| Configuration | CMake 4.4.3, `Visual Studio 18 2026` generator |
| Options | `BUILD_SHARED_LIBS=ON`, `OPUS_BUILD_SHARED_LIBRARY=ON`, `OPUS_STATIC_RUNTIME=ON`, `OPUS_BUILD_TESTING=OFF`, `OPUS_BUILD_PROGRAMS=OFF` |

The archive's checksum was written into `docs/sesli-sohbet-plani.en.md` on
**2026-09-18**; the downloaded file was verified against that value, so
against something recorded months ago rather than something produced today.

**`OPUS_STATIC_RUNTIME=ON` is deliberate.** Without it the DLL comes out
depending on `VCRUNTIME140.dll`; on a machine without the Visual C++
redistributable it would fail to load and voice would silently fall back to
µ-law. The static build needs only `KERNEL32.dll` — cleaner even than the file
from PyAV, which also wanted `msvcrt.dll`. The cost is about 150 KB.

Verification: all 19 tests in `tests/test_voice_opus.py` run against this DLL
(11 of them were skipped when libopus was absent). Among them is the one that
measures packet size not varying with the audio.

### Licence text

The copyright notice and conditions below are reproduced verbatim from the
`COPYING` file of the source archive.

```
Copyright 2001-2023 Xiph.Org, Skype Limited, Octasic,
                    Jean-Marc Valin, Timothy B. Terriberry,
                    CSIRO, Gregory Maxwell, Mark Borgerding,
                    Erik de Castro Lopo, Mozilla, Amazon
```

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
