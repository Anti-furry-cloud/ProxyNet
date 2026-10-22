**Türkçe** · [English](VERIFYING.en.md)

---

# İndirdiğiniz dosyayı doğrulama

Dağıtılan program **imzasızdır**, yani Windows açarken uyarı verir. Bu normal
ve burada neden öyle olduğu yazılı: [THREAT_MODEL.md](THREAT_MODEL.md) 5.9.

Uyarının yerini tutan şey şu: her sürümle birlikte dosyaların SHA-256
özetlerini içeren bir liste (`SHA256SUMS.txt`) ve o listenin **imzası**
(`SHA256SUMS.txt.asc`) yayınlanıyor. İkisini kontrol ederseniz, elinizdeki
dosyanın benim ürettiğim dosya olduğunu kendiniz doğrulayabilirsiniz.

---

## İmza anahtarı

```
Anti-furry-cloud <287824178+Anti-furry-cloud@users.noreply.github.com>
ed25519 · 2026-09-30 · 2028-09-29'da doluyor

Parmak izi:  23DC 905B 569A 80BD D243  525B 80DA 0356 E47B B37C
```

Anahtarın kendisi: [ProxyNet-imza-anahtari.asc](ProxyNet-imza-anahtari.asc)

---

## Üç adım

GPG gerekiyor. Windows'ta Git for Windows ile birlikte geliyor
(`C:\Program Files\Git\usr\bin\gpg.exe`); Git Bash açarsanız `gpg` doğrudan
çalışır.

**1. Anahtarı içe alın ve parmak izini kontrol edin.**

```bash
gpg --import ProxyNet-imza-anahtari.asc
gpg --fingerprint 23DC905B569A80BDD243525B80DA0356E47BB37C
```

Çıkan parmak izi yukarıdakiyle **birebir** aynı olmalı.

**2. Özet listesinin imzasını doğrulayın.**

```bash
gpg --verify SHA256SUMS.txt.asc SHA256SUMS.txt
```

`Good signature from "Anti-furry-cloud ..."` görmelisiniz.

> `WARNING: This key is not certified with a trusted signature` uyarısı
> normaldir. Anahtarı kimsenin tanıdığı bir ağa bağlamadım; uyarı "bu anahtarı
> tanıyan birini bulamadım" demek, "imza geçersiz" demek değil. Önemli olan
> parmak izinin eşleşmesi.

**3. Dosyaların özetini karşılaştırın.**

```bash
sha256sum -c SHA256SUMS.txt
```

Her satırda `OK` görmelisiniz. Tek bir dosyayı elle kontrol etmek isterseniz:

```powershell
Get-FileHash ProxyChat.exe -Algorithm SHA256
```

---

## Eşleşmezse

**Kurmayın.** Sırayla:

1. Dosyayı [resmî kaynaktan](https://github.com/Anti-furry-cloud/ProxyNet)
   yeniden indirin — yarım inen bir dosya da özeti tutturmaz.
2. Yine tutmuyorsa **bana bildirin** ([SECURITY.md](SECURITY.md)). Elinizdeki
   dosya benim dağıttığım dosya değil.

---

## Bunun sınırı, dürüstçe

**İlk indirmenizde bu sizi tam korumaz.** Depoyu ele geçiren biri programı,
özet listesini, imzayı *ve* açık anahtarı birlikte değiştirebilir; ilk kez
indiren biri farkı anlayamaz. Buna "ilk karşılaşmada güven" problemi deniyor
ve imza onu çözmez.

İmzanın gerçekten işe yaradığı yerler:

- **Sonraki sürümler.** Anahtarı bir kez aldıysanız, ileride anahtarın
  değişmesi *görünür* olur. Sessizce başka birinin yerime geçmesi zorlaşır.
- **Depo dışından doğrulama.** Parmak izini başka bir kanaldan — yüz yüze,
  telefonda, ayrı bir yerde yazılı olarak — aldıysanız, saldırganın hepsini
  aynı anda değiştirmesi gerekir.
- **Dağıtım linki ele geçerse.** Program başka bir yerden dolaşıyorsa, imza
  onun benden çıkıp çıkmadığını gösterir.

Aynı mantık oda parolasında da geçerli: parolayı yüz yüze paylaşmak, bu
belgede parmak izini ayrıca doğrulamakla aynı şeydir.

---

## Kaynaktan kendiniz derlemek

Derleme **yeniden üretilebilir** (1.12.4): aynı kaynaktan derleyen herkes bit
bit aynı dosyayı elde eder. Yani özete güvenmek zorunda değilsiniz — kendiniz
derleyip karşılaştırabilirsiniz. Ayrıntı: [THREAT_MODEL.md](THREAT_MODEL.md) 5.9.

Her sürümle birlikte bir **derleme künyesi** (`DERLEME-KUNYESI.txt`)
yayınlanıyor: hangi Python, hangi PyInstaller, hangi paketler ve hangi
`SOURCE_DATE_EPOCH` ile derlendiğini yazıyor.

**Gerekenler:** Windows 10/11 (64-bit), Python 3.11 (künyedeki sürüm), NSIS
(kurulum dosyası için; künyedeki sürüm) ve libopus.dll.

**1. Kaynağı alın** — sürümün etiketinden (ör. `v1.12.8`), ya `git clone` ile
ya da GitHub'dan ZIP olarak. Derleme betiği git deposu olmayan bir klasörde de
çalışır.

**2. Paketleri kilitli sürümleriyle kurun.**

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.lock
```

`--require-hashes`, PyPI'daki bir dosya sonradan değiştirilmişse kurulumu
reddeder.

**3. libopus.dll.** Depoda durmuyor. Ya [THIRD-PARTY.md](THIRD-PARTY.md)
içindeki tarifle kaynağından derleyin, ya da sürümle yayınlanan DLL'i alıp
özetini `SHA256SUMS.txt` ile karşılaştırın.

**4. Künyedeki zaman damgasını verip derleyin.**

```powershell
$env:SOURCE_DATE_EPOCH = "<künyedeki SOURCE_DATE_EPOCH>"
$env:PROXYCHAT_OPUS_DLL = "C:\yol\libopus.dll"
.uild_exe.ps1
.uild_installer.ps1
Get-FileHash dist\ProxyChat.exe, dist\ProxyChat-Setup.exe -Algorithm SHA256
```

Çıkan özetler `SHA256SUMS.txt` ile aynı olmalı.

**Neden zaman damgasını elle veriyorsunuz:** Geliştirme ayrı bir depoda
sürüyor; bu depo onun bir **kopyası**, geçmişi değil. Ölçüm ve prototip
araçları dışında bırakıldı ([VOICE_CHAT_PLAN.md](VOICE_CHAT_PLAN.md));
programın derlemesine girmiyorlar. Künyedeki commit kimliği o geliştirme
deposuna ait ve burada bulunmaz. Derleme betiği zaman damgasını normalde son
commit'in zamanından alıyor; bu deponun commit'leri farklı zamanlarda olduğu
için künyedeki değeri sizin vermeniz gerekiyor. Ortamda verilen değer
korunuyor.
