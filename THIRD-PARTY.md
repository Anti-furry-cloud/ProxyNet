**Türkçe** · [English](THIRD-PARTY.en.md)

---

# Üçüncü parti bileşenler

ProxyChat GPLv3 ile dağıtılıyor ([LICENSE](LICENSE)). Aşağıdakiler başkalarının
işi; kendi lisanslarıyla geliyorlar ve o lisansların şartları bizi de bağlıyor.

Burada yalnızca **dağıtılan dosyanın içine giren** bileşenler var. Geliştirme
sırasında kullanılan ama pakete girmeyen araçlar (pytest, PyInstaller'ın
kendisi) listelenmiyor.

---

## libopus

| | |
| --- | --- |
| Ne işe yarıyor | Sesli sohbette konuşmayı sıkıştırıyor: 20 ms'lik ham ses 640 bayttan 60 bayta iniyor. Bulunamazsa program µ-law'a düşüyor ve çalışmaya devam ediyor (320 bayt), yani **zorunlu değil** |
| Sürüm | `libopus 1.6.1` — kütüphanenin kendi bildirdiği dizgi (`opus_get_version_string`) |
| Lisans | BSD 3 madde — GPLv3 ile uyumlu |
| Kaynak | https://opus-codec.org |
| Kod | `core/voice_opus.py` (ctypes ile doğrudan bağlanıyor, sarmalayıcı paket yok) |

**Dağıtılan dosya — kaynaktan derlendi (1.12.3).**

```
SHA-256  1d5fcc90b31e982a066db1e1e3128d8673fce5c5adaab11d1cd808d54a3ee66c
boyut    625.664 bayt
```

Öncesinde bu dosya PyAV paketinin içinden çıkarılmıştı ve kaynağı
doğrulanmamıştı. Artık Xiph'in yayımladığı kaynak arşivinden derleniyor:

| | |
| --- | --- |
| Kaynak arşivi | `opus-1.6.1.tar.gz` |
| Arşivin SHA-256'sı | `6ffcb593207be92584df15b32466ed64bbec99109f007c82205f0194572411a1` |
| Derleyici | MSVC 14.51.36231 (Visual Studio 2026), x64 |
| Yapılandırma | CMake 4.4.3, `Visual Studio 18 2026` üreteci |
| Seçenekler | `BUILD_SHARED_LIBS=ON`, `OPUS_BUILD_SHARED_LIBRARY=ON`, `OPUS_STATIC_RUNTIME=ON`, `OPUS_BUILD_TESTING=OFF`, `OPUS_BUILD_PROGRAMS=OFF` |

Arşivin özeti **2026-09-18'de** `docs/sesli-sohbet-plani.md` içine yazılmıştı;
indirilen dosya o değere karşı doğrulandı, yani bugün üretilmiş bir değere
değil, aylar önce kayda geçmiş bir değere karşı.

**`OPUS_STATIC_RUNTIME=ON` bilinçli.** Onsuz derlenen DLL `VCRUNTIME140.dll`'e
bağımlı çıkıyor; Visual C++ yeniden dağıtılabilir paketi kurulu olmayan bir
makinede yüklenemez ve ses sessizce µ-law'a düşerdi. Statik hâli yalnızca
`KERNEL32.dll` istiyor — PyAV'den gelen dosyadan bile temiz (o `msvcrt.dll`
de istiyordu). Bedeli ~150 KB.

Doğrulama: `tests/test_voice_opus.py` içindeki 19 testin tamamı bu DLL ile
çalışıyor (libopus yokken 11'i atlanıyordu). Aralarında paket boyunun sese
göre değişmediğini ölçen test de var.

### Lisans metni

Aşağıdaki telif bildirimi ve koşullar, kaynak arşivinin `COPYING` dosyasından
birebir alındı.

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

Opus ayrıca patentlerle kapsanıyor; patentler açık kaynakla uyumlu, telifsiz
lisanslarla veriliyor. Ayrıntısı yukarıdaki adreste.

---

## Qt / PySide6

| | |
| --- | --- |
| Ne işe yarıyor | Arayüz, ses cihazı katmanı, ayarların saklanması |
| Lisans | **LGPLv3** |
| Kaynak | https://www.qt.io — PySide6: https://pypi.org/project/PySide6/ |

LGPL, kütüphanenin kendisi değiştirilirse kaynağının verilmesini ve
kullanıcının onu **değiştirilmiş bir sürümle yeniden bağlayabilmesini**
istiyor. Qt değiştirilmedi; olduğu gibi paketleniyor.

Bu, kapalı kaynak ya da gizlenmiş (obfuscated) bir dağıtımın neden sorun
olacağının da sebeplerinden biri: tek dosyalık bir pakette bu yükümlülüğü
yerine getirmek gereksiz yere zorlaşır.

## cryptography

| | |
| --- | --- |
| Ne işe yarıyor | AES-GCM, X25519, HKDF, Argon2id |
| Lisans | Apache 2.0 **veya** BSD 3 madde (ikisinden biri seçilebilir) — GPLv3 ile uyumlu |
| Kaynak | https://pypi.org/project/cryptography/ |

---

Bu dosyanın güncel kalması gerekiyor: pakete yeni bir üçüncü parti bileşen
girdiğinde buraya da satırı eklenmeli. `tests/test_lisans_basliklari.py`
bunun bir kısmını kilitliyor.
