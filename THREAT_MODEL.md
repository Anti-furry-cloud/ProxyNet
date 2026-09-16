**Türkçe** · [English](THREAT_MODEL.en.md)

# ProxyNet — Tehdit Modeli

> **Yayın notu (2026-09-16):** ProxyNet'in kaynak kodu **henüz açık değil** ve
> yazılım hiçbir bağımsız güvenlik denetiminden geçmedi. Herkese açık bir
> sürüm de yok. **Şu an hiç kimse bu yazılıma güvenmemeli.** Bu belge, üzerine
> daha fazlası inşa edilmeden önce tasarımın eleştirilebilmesi için
> yayınlanıyor; hata bulursanız duymak isterim. Metindeki dosya yolları
> (`core/server.py` gibi) şu an görünmüyor — kod açıldığında buradaki her
> iddianın nereden doğrulanacağını göstermek için bilerek bırakıldı.

> **Kapsam:** Bu belge **ProxyNull**'ın (`apps/proxynull/`) hedefini tanımlar.
> ProxyChat (`apps/proxychat/`) günlük kullanım için optimize edilmiştir ve
> T5 rakibine karşı koruma **iddia etmez**; onun için 4. bölümdeki güvenceler
> geçerlidir, 5. bölümdeki açıklar kalıcıdır.

Bu belge ProxyNet'in **neden** var olduğunu ve hangi ölçüye göre değerlendirildiğini
tanımlar. Amaç yalnızca bir arkadaş grubunun sohbet etmesi değildir; amaç
**mesajların hiç kimse tarafından — sunucuyu işleten kişi ve devlet ölçeğinde
bir rakip dahil — okunamamasıdır.**

Her yeni özellik bu belgeye karşı ölçülür. Belgedeki ilkeleri ihlal eden bir
özellik, ne kadar kullanışlı olursa olsun reddedilir.

> **Bugünkü durum, tek cümleyle:** ProxyNet mesaj içeriğini sunucuya ve odaya
> giremeyen üçüncü kişilere karşı koruyor; ancak **devlet ölçeğinde bir rakibe
> karşı koruma sağlamıyor.** Aradaki fark bu belgenin 5. ve 6. bölümlerinde
> açıkça listelenmiştir. Bunlar kapanmadan aksi iddia edilmemelidir.

---

## 1. Korunan varlıklar

| Öncelik | Varlık | Bugünkü durum |
| --- | --- | --- |
| 1 | Mesaj içeriği | Uçtan uca şifreli |
| 2 | Geçmiş mesajların gizliliği (parola sonradan ele geçerse) | **Korunmuyor** |
| 3 | Kiminle konuşulduğu (metadata) | **Korunmuyor** |
| 4 | Kullanıcı adları, oda adları | **Korunmuyor** |
| 5 | Ne zaman çevrimiçi olunduğu | **Korunmuyor** |

---

## 2. Rakip modeli

| # | Rakip | Yeteneği | Bugünkü durumumuz |
| --- | --- | --- | --- |
| T1 | Aynı yerel ağdaki meraklı kişi | Porta bağlanabilir, trafiği dinleyebilir | **Kısmi** — içeriği okuyamaz ama odaya girebilir |
| T2 | Sunucuyu işleten kişi (host) | Sunucudan geçen her şeyi görür | **İyi** — düz metni asla görmez |
| T3 | Yol üzerindeki pasif dinleyici (ISP, VPN sağlayıcısı) | Trafiği kaydeder | **Kısmi** — içerik güvenli, metadata açık |
| T4 | Aktif ağ saldırganı | Paket enjekte eder, düşürür, değiştirir | **Zayıf** — mesajlar sahte üretilemez ama zarf paketleri (hata, kullanıcı listesi) sahtelenebilir |
| T5 | Devlet ölçeğinde rakip | Trafiği yıllarca saklar, cihaza el koyar, hukuki zorlama uygular | **Karşılamıyor** — ileri gizlilik yok |

**T5 belgenin varlık sebebidir ve şu an karşılanmıyor.** Bunu bilerek yazıyorum;
proje amacına ulaşmış sayılmaz.

---

## 3. Kapsam dışı

Bu tehditler ProxyNet tarafından çözülemez ve çözülüyormuş gibi davranılmamalıdır:

- **Uç cihazın ele geçirilmesi.** Keylogger, ekran görüntüsü, bellek dökümü,
  arkadaşınızın omzunun üstünden bakan kişi. Şifreleme mesajı ağda korur,
  ekranda değil.
- **Oda parolasının paylaşım kanalı.** Parolayı WhatsApp'tan gönderirseniz
  zincir orada kırılır. Parola yüz yüze veya ayrı bir güvenli kanaldan
  paylaşılmalıdır.
- **Kullanıcının parola seçimi.** Deterministik anahtar türetmesi nedeniyle
  tahmin edilebilir parola, tüm modeli çökertir.
- **Alt katman (işletim sistemi, VPN istemcisi, donanım) güvenliği.**

---

## 4. Bugün verilen güvenceler

Bunların hepsi test edilmiştir (`tests/test_crypto.py`, `tests/test_hardening.py`):

- **Sunucu düz metni asla görmez.** Şifreleme ve çözme yalnızca istemcide olur.
  Sunucu zincirinde (`core/server.py`, `core/hub.py`, `core/transport.py`,
  `core/protocol.py`, `core/server_state.py`) `cryptography` bile import edilmez — sunucunun çözme
  yeteneği yoktur, olmaması tasarım gereğidir.
- **Sunucu belleğindeki geçmiş şifrelidir.**
- **Yanlış parolayla içerik açılamaz**; kullanıcı düz metin yerine yer tutucu görür.
- **Değiştirilmiş şifreli metin reddedilir.** Fernet kimlik doğrulamalı şifreleme
  kullanır (AES-128-CBC + HMAC-SHA256), yani rakip mesaj içeriğini sessizce
  değiştiremez.
- **Sunucu tarafında üçüncü parti bağımlılık yoktur** — saldırı yüzeyi ve
  tedarik zinciri riski küçüktür.
- Kaynak tükenmesine karşı sınırlar: paket 64 KiB, içerik 8 KiB, 10 saniyede
  20 mesaj, en fazla 50 istemci, boşta kalma 120 saniye.

---

## 5. Bugün verilmeyen güvenceler

Bunlar bilinen ve kabul edilmiş açıklardır. Kapanana kadar ProxyNet'in
"devlet okuyamaz" seviyesinde olduğu **söylenmemelidir.**

### 5.1 İleri gizlilik (forward secrecy) yok — en büyük açık

Anahtar, (oda adı + parola) ikilisinden deterministik türetilir ve hiç değişmez.
Sonuç: bugün kaydedilen şifreli trafik, parola gelecekte herhangi bir yolla ele
geçerse **geriye dönük olarak tamamen okunur**.

Devlet ölçeğinde rakiplerin standart yöntemi tam olarak budur: *şimdi kaydet,
sonra çöz*. Signal'in Double Ratchet'i bu senaryo için vardır. ProxyNet'te
karşılığı yoktur.

### 5.2 Geçmiş, kimlik doğrulaması olmadan dağıtılıyor

Sunucu, odaya katılan **herkese** son 100 mesajı gönderir
(`core/server.py` → `_send_room_history`) ve odaya katılmak için parola gerekmez.
Parolayı bilmeyen biri odaya girip 100 şifreli mesajı toplayıp çevrimdışı
saldırıya alabilir. 5.1 ile birleştiğinde ciddi bir kombinasyondur.

### 5.3 Metadata tamamen açık

Kullanıcı adları, oda adları, zaman damgaları, mesaj boyutları ve kimin ne zaman
çevrimiçi olduğu düz metin taşınır. Bu ölçekte bir rakip için metadata çoğu zaman
içerikten değerlidir.

Ayrıca sunucu konsoluna basılan olay kayıtları şifreli metnin **uzunluğunu**
yazar (`core/server_state.py` → `content_length`), yani host'un ekranında/logunda
mesaj uzunlukları birikir.

### 5.4 Taşıma katmanı şifresiz

Paket zarfı (`type`, `room`, `user`, `ts`, `enc`) ağda açık gider. Aktif bir
saldırgan mesaj içeriğini sahteleyemez ama sahte kullanıcı listesi veya hata
paketi enjekte edebilir, paket düşürebilir.

### 5.5 Odaya giriş serbest

Sunucuda kimlik doğrulama yoktur; port erişilebilir olan herkes odaya girer,
kullanıcı listesini ve trafik ritmini görür. Bu bilinçli bir karardır
(bkz. 7. bölüm) ama sunucunun halka açık bir adrese taşınması hâlinde
**yeniden değerlendirilmelidir.**

### 5.6 Sunucu tüm ağ arayüzlerini dinliyordu — kapatıldı (1.6.2)

Host modu eskiden `0.0.0.0`'a bağlanıyordu; yani yalnızca VPN arayüzünü değil,
ev/kafe ağını ve sanal adaptörleri de dinliyordu. VPN kullanmak bunu
düzeltmiyordu.

1.6.2'den itibaren dinlenecek ağ her Host başlatışında **listeden elle
seçilir**; varsayılan yoktur ve seçim saklanmaz. "Bütün ağlar" hâlâ
seçilebilir, ama bilinçli bir tercih olarak. Demo modu yalnızca `127.0.0.1`'i
dinler.

1.6.3'ten itibaren port Windows'ta sunucuya **özel olarak ayrılır**
(`SO_EXCLUSIVEADDRUSE`). Eskiden kullanılan `SO_REUSEADDR`, aynı porta ikinci
bir sunucunun hatasız açılmasına ve Host "Bütün ağlar"ı dinlerken başka bir
programın `127.0.0.1:<port>`'u dinleyip Host'un kendi bağlantısını üzerine
almasına izin veriyordu.

Kalan sınır: seçim bir IP adresine bağlıdır, ağ bağdaştırıcısına değil. O adres
bilgisayardan kalkarsa (örneğin VPN kapatılırsa) Host yeniden
başlatılmalıdır.

### 5.7 Mesaj uzunluğu sızar

Fernet çıktısının uzunluğu düz metnin uzunluğuyla korelasyonludur (16 baytlık
blok hassasiyetinde). Dolgu (padding) uygulanmıyor.

### 5.8 PBKDF2, Argon2id değil

240.000 turluk PBKDF2-HMAC-SHA256 tüketici seviyesinde makul, ancak GPU'da
paralelleşir. Argon2id bellek-zor olduğu için özel donanımla saldırıyı çok daha
pahalı yapar ve kurulu `cryptography` sürümünde **kullanılabilir durumdadır**.

### 5.9 Dağıtım zinciri korumasız

Dağıtılan `.exe` imzasızdır ve bulut linkiyle paylaşılır. Rakip, kullanıcıya
değiştirilmiş bir binary ulaştırabilir. Yeniden üretilebilir derleme ve imzalama
yoktur.

---

## 6. Tasarım ilkeleri

Yeni her özellik bunlara karşı ölçülür.

1. **Sunucu asla düz metin görmez.** Sunucuya çözme yeteneği veren hiçbir özellik
   kabul edilmez — ne kadar kullanışlı olursa olsun.
2. **Kalıcılık varsayılan olarak kapalıdır.** Saklanan her bayt, el konulabilecek
   veya talep edilebilecek bir yığındır. Saklama gerekiyorsa gerekçesi bu belgeye
   yazılır.
3. **Metadata da veridir.** Yeni bir paket alanı eklerken "bu alan kimin kiminle
   konuştuğunu ele veriyor mu?" sorusu sorulur.
4. **Anahtar malzemesi diske düz yazılmaz.** Parola hatırlama gibi kolaylıklar
   ancak işletim sistemi koruması (Windows DPAPI) ile ve isteğe bağlı olarak eklenir.
5. **Kolaylık güvenliği ezmez.** Çatışma hâlinde varsayılan güvenli taraftır;
   kolaylık açıkça seçilir (opt-in).
6. **Bu belgede yazmayan garanti, garanti değildir.** README ve arayüz, buradaki
   listeden fazlasını vaat edemez.

---

## 7. Reddedilen ve ertelenen tasarımlar

Karar kaydı — aynı fikirlerin tekrar gündeme gelmemesi için.

| Tasarım | Karar | Gerekçe |
| --- | --- | --- |
| VPS'te 7/24 sunucu + diske yazan kalıcı geçmiş | **Reddedildi** | Kalıcılık el konulabilir bir yığın yaratır; İlke 2'yi ihlal eder |
| Sesli sohbette sunucuda ses karıştırma (mixing) | **Reddedildi** | Sunucunun sesi çözmesini gerektirir; İlke 1'i ihlal eder |
| Sunucu erişim parolası | **Ertelendi** | Yerel/VPN senaryosunda gereksiz. Sunucu halka açık bir adrese taşınırsa yeniden değerlendirilecek (bkz. 5.5) |
| Tek üründe oda başına güvenlik modu | **Reddedildi** | İki ayrı ürün tercih edildi. Az özellik güvenlikte başlı başına bir özelliktir; ayrı ürün, ProxyChat'in özellik baskısının ProxyNull'ı kirletmemesini garanti eder |
| Güvenlik kodunun iki ürüne kopyalanması | **Reddedildi** | Kopyalanan kodda açık bir tarafta düzeltilip diğerinde unutulur. `core/` ortaktır; ProxyNull saldırı yüzeyini daha az import ederek küçültür |
| Ses için sunucu üzerinden aktarma (SFU, çözmeden) | **Kabul edildi (2026-09-16)** | Baştan aktarma; "yalnızca 4 kişiyi aşan odalar için" koşulu kaldırıldı. Alternatifi olan mesh, odadaki herkesin IP'sini herkese dağıtacaktı (İlke 3); aktarmada Host zaten gördüğü IP'leri görmeye devam eder. İçerik şifreli kaldığı için İlke 1 ihlal edilmiyor. Aktarmanın kendi çözülmemiş sorunları (gönderen kimliği ataması, Host'a kimlik doğrulaması) sesli sohbet planının 9. bölümünde |

---

## 8. Açıkların kapatılma sırası

| Sıra | İş | Etki | Büyüklük |
| --- | --- | --- | --- |
| 1 | Geçmişi kaldırmak / varsayılan kapatmak (5.2) | Yüksek | Küçük |
| 2 | ~~Host'un dinlediği arayüzü seçilebilir yapmak (5.6)~~ **Yapıldı (1.6.2)** | Orta | Küçük |
| 3 | Olay kayıtlarından `content_length`'i çıkarmak (5.3) | Düşük | Küçük |
| 4 | Argon2id'ye geçiş (5.8) | Orta | Orta |
| 5 | Taşıma katmanı şifrelemesi / kimlik doğrulama (5.4) | Yüksek | Orta |
| 6 | **İleri gizlilik: anahtar ilerletme (5.1)** | **En yüksek** | **Büyük** — protokol değişikliği |
| 7 | Mesaj dolgusu (5.7) | Düşük | Küçük |
| 8 | İmzalı / yeniden üretilebilir derleme (5.9) | Orta | Orta |

---

## 9. Engellenme direnci

Bu belgenin 1–8. bölümleri tek bir soruyu ele alıyor: **mesajlar okunabilir
mi?** Bu bölüm farklı bir soruyu soruyor: **uygulama çalışabilir mi?**

İkisi ayrı eksen. Şifreleme mükemmel olsa bile bağlantı kurulamıyorsa
uygulama işe yaramaz. Bugün bu eksende projede fiilen **hiçbir koruma yok**
ve bu bilinçli değil, sadece hiç ele alınmamış.

### 9.1 Engellenebilecekler, en kolaydan en zora

| # | Hedef | Neden kolay | Bizim durumumuz |
| --- | --- | --- | --- |
| 1 | **VPN altyapısı** | Hamachi, Tailscale, ZeroTier üçü de merkezî bir buluşma sunucusuna bağımlı | Eşler birbirini bulamaz; kriptografiye dokunmaya gerek kalmaz |
| 2 | **Dağıtım kanalı** | Bulut linkleri ve kod deposu erişime kapatılabilir | İndirilemeyen program yayılamaz |
| 3 | **Protokol parmak izi** | İlk paket düz metin ve tanınması önemsiz | Aşağıya bakınız — bu bizim kendi açığımız |
| 4 | **Ev bağlantısı** | ISP gelen bağlantıları kapatabilir, CGNAT'a geçebilir | Host modu ve "hazır sunucu" fikri çalışmaz |
| 5 | **Sunucunun kendisi** | Fiziksel makine, hukuki süreç | Doğrudan kapatma |

### 9.2 Protokol parmak izi — somut açık

İstemcinin gönderdiği ilk paket şudur:

```
{"type":"join","room":"general","user":"ayse"}
```

Düz metin, sabit alan adları, sabit sıra. Derin paket incelemesi (DPI) için
tanınması dakikalar sürer. Varsayılan port da sabit (5555). Yani "bu trafiği
düşür" kuralı yazmak neredeyse bedava.

Şifreli sohbet araçlarının kendilerini TLS gibi göstermesinin sebebi tam
olarak budur. Bizde böyle bir örtme yok.

### 9.3 Engellenemeyecekler

- **Yerel ağ kullanımı.** Uygulama internet olmadan çalışıyor; aynı fiziksel
  ağdaki iki makine arasındaki trafiği engelleyecek bir merci yok. Mimarinin
  en dayanıklı yanı budur.
- **Matematiğin kendisi.** Şifreleme engellenemez; kullanımı düzenlenebilir,
  ki bu teknik değil hukuki bir konudur.

### 9.4 Ölçek uyarısı

Dürüst olmak gerekirse: **birkaç kişilik bir arkadaş grubu bu ölçekte bir
engelleme çekmez.** Engelleme ölçekle gelir. Bu bölüm proje büyürse
anlamlıdır; bugünün önceliği değildir ve buraya bugün harcanacak emek yanlış
yere gider.

En olası gerçek senaryo hedefli değil, yan hasardır: VPN'lere yönelik genel
bir engel bizi de vurur.

### 9.5 Direnç istenirse maliyeti

| İş | Kapattığı madde | Büyüklük |
| --- | --- | --- |
| Sabit portu terk etmek | 9.1/3 kısmen | Küçük |
| Protokolü TLS içine sarmak veya örtmek | 9.1/3 | Büyük — zarf şifreleme işiyle örtüşür |
| Dağıtımı çoğaltmak, imzalı binary | 9.1/2 | Orta — 5.9 ile örtüşür |
| Merkezî koordinasyondan kurtulmak | 9.1/1 | Çok büyük; her eşler-arası sistem bir buluşma noktası ister |

---

## 10. Bu belge ne zaman güncellenir

- Protokole yeni bir paket tipi veya alan eklendiğinde.
- Herhangi bir veri diske yazılmaya başlandığında.
- Şifreleme ile ilgili her değişiklikte.
- Protokolün ağdaki görünümü değiştiğinde (bkz. 9. bölüm).
- 5. bölümdeki bir açık kapandığında — kapanan madde 4. bölüme taşınır ve
  hangi testin garanti ettiği yazılır.
