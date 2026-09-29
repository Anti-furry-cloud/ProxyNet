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

**Dağıtılan dosya.** Şu an elimizdeki `libopus.dll`:

```
SHA-256  4369edc456631a3cc933d7918747e5d2d111056dbc8a85b01330b5a53c062d44
boyut    482.816 bayt
```

**Bu ikilinin kaynağı doğrulanmadı.** PyAV paketinin içinden çıkarıldı;
Xiph'in yayımladığı kaynak arşivinden bizim derlediğimiz bir dosya değil.
THREAT_MODEL.md 5.9 ve `docs/sesli-sohbet-plani.md` bunu açık bir madde olarak
taşıyor: gerçek bir sürümde kaynaktan derlenmeli. Ayrı bir dosya olarak elden
verilirken bu daha küçük bir sorundu; DLL pakete gömüldükten sonra, özetini
yayınladığımız exe'nin **içinde** kaynağı doğrulanmamış bir ikili taşınıyor
demektir.

**Eksik olan şey.** BSD 3 madde, ikili dağıtımın "yukarıdaki telif
bildirimini" de yeniden üretmesini şart koşuyor. Aşağıdaki koşul metni
opus-codec.org'dan birebir alındı, ama **telif sahipleri satırı buraya henüz
yazılmadı**: o satırın doğrusu kaynak arşivinin `COPYING` dosyasındadır ve
bu yazıldığı sırada doğrulanamadı. Ezberden yazmak yerine boş bırakıldı.
DLL kaynaktan derlendiğinde (yukarıdaki açık madde) `COPYING` elimize
geçecek ve satır oradan **birebir kopyalanacak.** İkisi tek iştir; biri
yapılmadan sürüm dağıtılmamalı.

### Lisans metni

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
