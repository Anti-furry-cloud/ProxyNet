**Türkçe** · [English](THREAT_MODEL.en.md)

# ProxyNet — Tehdit Modeli

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
> karşı koruma sağlamıyor.** Aradaki fark bu belgenin 5. bölümünde açıkça
> listelenmiştir, kapatılma sırası 8. bölümdedir. Bunlar kapanmadan aksi
> iddia edilmemelidir.

---

## 1. Korunan varlıklar

| Öncelik | Varlık | Bugünkü durum |
| --- | --- | --- |
| 1 | Mesaj içeriği | Uçtan uca şifreli |
| 2 | Geçmiş mesajların gizliliği (parola sonradan ele geçerse) | **Korunuyor** — metin 1.9.0, ses 1.10.0 |
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
| T5 | Devlet ölçeğinde rakip | Trafiği yıllarca saklar, cihaza el koyar, hukuki zorlama uygular | **Karşılamıyor** — ileri gizlilik var (metin 1.9.0, ses 1.10.0) ama üstveri ve taşıma katmanı açık |

**T5 belgenin varlık sebebidir ve şu an karşılanmıyor.** Bunu bilerek yazıyoruz;
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
- **Kullanıcının parola seçimi.** Parola 1.9.0'dan beri metni şifreleyen
  anahtar değil (5.1), ama karşı tarafın odaya ait olduğunu doğrulayan imzanın
  anahtarı — ve ses anahtarı hâlâ ondan türüyor. Tahmin edilebilir bir parola
  hem çevrimdışı sözlük saldırısına hem de araya girmeye kapı açar.
- **Alt katman (işletim sistemi, VPN istemcisi, donanım) güvenliği.**

---

## 4. Bugün verilen güvenceler

Bunların hepsi test edilmiştir (`tests/test_crypto.py`, `tests/test_hardening.py`):

- **Sunucu düz metni asla görmez.** Şifreleme ve çözme yalnızca istemcide olur.
  Sunucu zincirinde (`core/server.py`, `core/hub.py`, `core/transport.py`,
  `core/protocol.py`, `core/server_state.py`) `cryptography` bile import edilmez — sunucunun çözme
  yeteneği yoktur, olmaması tasarım gereğidir.
- **Şifreli odada sunucu geçmiş tutmuyor** (1.9.0). Parolasız odada geçmiş
  yalnızca bellekte tutulur, diske yazılmaz.
- **Yanlış parolayla içerik açılamaz**; kullanıcı düz metin yerine yer tutucu görür.
- **Değiştirilmiş şifreli metin reddedilir.** Metin sohbeti 1.9.0'dan beri
  AES-256-GCM kullanıyor (öncesinde Fernet, yani AES-128-CBC + HMAC-SHA256);
  ikisi de kimlik doğrulamalı şifreleme, yani rakip mesaj içeriğini sessizce
  değiştiremez.
- **Sunucu tarafında üçüncü parti bağımlılık yoktur** — saldırı yüzeyi ve
  tedarik zinciri riski küçüktür.
- Kaynak tükenmesine karşı sınırlar: paket 64 KiB, içerik 8 KiB, 10 saniyede
  20 mesaj, en fazla 50 istemci, boşta kalma 120 saniye.

Kapanan açıklar (ayrıntısı ve kalan sınırları 5. bölümde duruyor):

- **İleri gizlilik: anahtar her oturumda yeniden doğuyor** (5.1; metin 1.9.0,
  ses 1.10.0) — `tests/test_key_agreement.py`, `tests/test_room_session.py`,
  `tests/test_forward_secrecy.py`, `tests/test_voice_forward_secrecy.py`,
  `tests/test_crypto.py` → `ForwardSecrecyTests`.
- **Üye listesi kanıtla doğrulanıyor; sunucunun iddiasına güvenilmiyor**
  (5.4-B, 1.9.0) — `tests/test_verified_users.py`.
- **Şifreli odada geçmiş hiç tutulmuyor** (5.2, 1.9.0) —
  `tests/test_forward_secrecy.py`.
- **Oda geçmişi varsayılan olarak kapalı** (5.2, 1.7.0) —
  `tests/test_settings.py` → `HistoryDefaultTests`.
- **Anahtar Argon2id ile türetiliyor** (5.8, 1.7.0) —
  `tests/test_crypto.py` → `Argon2idTests`.
- **Host'un dinlediği ağ her başlatışta elle seçiliyor** (5.6, 1.6.2) —
  `tests/test_listen_address.py`.
- **Olay kaydı mesaj uzunluğunu yazmıyor** (5.3, 1.5.0) —
  `tests/test_logging_and_scroll.py`.

---

## 5. Bugün verilmeyen güvenceler

Bunlar bilinen ve kabul edilmiş açıklardır. Kapanana kadar ProxyNet'in
"devlet okuyamaz" seviyesinde olduğu **söylenmemelidir.**

### 5.1 İleri gizlilik (forward secrecy) — kapandı (metin 1.9.0, ses 1.10.0)

**Eskiden:** anahtar (oda adı + parola) ikilisinden deterministik türetiliyor ve
hiç değişmiyordu. Kaydedilen şifreli trafik, parola gelecekte herhangi bir yolla
ele geçerse **geriye dönük olarak tamamen** okunuyordu. Devlet ölçeğinde
rakiplerin standart yöntemi tam olarak budur: *şimdi kaydet, sonra çöz*.

**Metin sohbetinde kapatıldı (1.9.0).** Şifreleme anahtarı artık paroladan
türemiyor: her oturumda geçici bir X25519 anahtar çifti üretiliyor, açık
anahtarlar uçlar arasında takas ediliyor ve oturum kapanınca gizli anahtarlar
bırakılıyor. Parolanın yeni işi şifrelemek değil, karşı tarafın odaya ait
olduğunu **doğrulamak**: açık anahtarın yanında paroladan türetilmiş bir HMAC
gidiyor, oda adı da imzaya giriyor. Grup için gönderen anahtarı deseni
kullanılıyor — her katılımcı oturum başına bir yayın anahtarı üretip her eşine
ikili anahtarla sarılı gönderiyor; Signal ve WhatsApp'ın grup sohbetinde
yaptığının aynısı.

Sonuç: parola aylar sonra sızsa bile kaydedilmiş **metin** trafiği açılamaz.
Sunucu bu paketleri yalnızca taşır, içine bakmaz; Diffie-Hellman'ın tamamı
uçlarda olduğu için sunucunun ortak sırrı hesaplama yeteneği **yoktur** ve
sunucu zincirinin `cryptography` import etmeme kuralı bozulmamıştır (bir test
bunu AST ile kilitliyor).

Kod: `core/key_agreement.py`, `core/room_session.py`. Testler:
`tests/test_key_agreement.py`, `tests/test_room_session.py`,
`tests/test_forward_secrecy.py`, `tests/test_crypto.py` → `ForwardSecrecyTests`.

**Seste de kapatıldı (1.10.0).** Ses oturum anahtarı da artık oda oturumunun
gönderen anahtarından türüyor; paroladan değil. Metin tarafında yapılan iş
bunun provasıydı ve aynı malzeme kullanıldı — tek fark HKDF'nin `info` alanı,
ki aynı anahtardan metin ve ses için aynı şey çıkmasın.

Ses anahtarının kimden türetileceği **kullanıcı adıyla değil** o kişinin geçici
açık anahtarıyla eşleşiyor: ad sunucunun söylediği bir şey, açık anahtar ise
paroladan türetilmiş imzayla doğrulanmış bir şey. Bunun için `voice_join` ve
`voice_peers` paketlerine açık anahtar alanı eklendi; sunucu onu yalnızca
taşıyor, anlamını bilmiyor.

Sıra sorunu da çözüldü: metin el sıkışması ses katılımından sonra bitebiliyor.
O durumda eş sessizce atlanıyor ve anahtar gelince katılımcı listesi yeniden
işleniyor — eksik anahtar bir hata değil, geçici bir durum. Şema etiketi
`aesgcm-x25519-v3`; eski `aesgcm-hkdf-v2` ile bilerek uyumsuz. Kod:
`core/voice_crypto.py` → `derive_voice_session_key`, `ForwardSecretVoiceCipher`.
Testler: `tests/test_voice_forward_secrecy.py`.

**Kalan açık — zayıf parola.** Teklifin HMAC'ini gören biri çevrimdışı sözlük
saldırısı yapabilir; parolayı bulursa o oturumun takasını taklit edebilir.
Öncesine göre gerileme değil (şifreli metinden aynı saldırı yapılıyordu) ama
düzelme de değil. Asıl çözüm bir PAKE'tir (bkz. `apps/proxynull/PROTOKOL.md` 3).

**Kalan açık — parolayı bilen aktif ortadaki adam.** Parola paylaşılan bir sır
olduğu için onu bilen biri geçerli HMAC üretir, yani araya girebilir. Odaya
girmesi de zaten serbest (5.5). ProxyNull bunu her oturumda karşılaştırılan
kısa doğrulama koduyla çözüyor; ProxyChat çözmüyor.

**Kalan açık — bellek.** Python'da `bytes` değişmez ve güvenilir şekilde
sıfırlanamaz. Matematik mükemmel ileri gizlilik veriyor, çalışma zamanı
vermiyor: cihazın belleğine el konmasına karşı koruma **kısmi**.

**Bilerek yok — kendi kendine iyileşme.** Signal'in Double Ratchet'i ileri
gizliliğin üstüne post-compromise security koyar: cihaz bir kez ele geçse bile
sonraki mesajların iyileşmesi. ProxyNet'te karşılığı yok ve grup sohbetinde
gönderen anahtarları bunu zaten vermiyor. "Şimdi kaydet, sonra çöz" tehdidi
için gerekli değil; bu yüzden ertelendi — gizlenmiyor.

### 5.2 Geçmiş, kimlik doğrulaması olmadan dağıtılıyor — varsayılan kapatıldı (1.7.0)

Geçmiş açıkken sunucu, odaya katılan **herkese** son 100 mesaja kadar gönderir
(`core/server.py` → `_send_room_history`) ve odaya katılmak için parola gerekmez.
Parolayı bilmeyen biri odaya girip 100 şifreli mesajı toplayıp çevrimdışı
saldırıya alabilir. 5.1 ile birleştiğinde ciddi bir kombinasyondur.

1.7.0'dan itibaren geçmiş **varsayılan olarak kapalı**: sunucu hiçbir mesajı
bellekte tutmaz ve odaya girene geçmiş paketi göndermez. Eski sürüm varsayılan
değeri her bağlantıda kayda yazdığı için yalnızca varsayılanı değiştirmek
mevcut hiçbir kullanıcıyı etkilemezdi; güncellemede kayıtlı değer bir kez
silinir (`apps/proxychat/settings.py` → `_migrate_privacy_defaults`). Testler:
`tests/test_settings.py` → `HistoryDefaultTests`.

Geçmiş kapalıyken istemci, kullanıcının bu oturumda **zaten gördüğü**
mesajları odaya geri döndüğünde gösterebilmek için yalnızca bellekte tutar
(oda başına en fazla 200; diske yazılmaz, oturum bitince silinir). Bu yeni bir
alıcı yaratmaz: aynı mesajlar zaten o cihazın ekranındaydı ve uç cihazın ele
geçirilmesi kapsam dışı (3. bölüm). Testler: `tests/test_proxychat_ui.py` →
`RoomMemoryTests`.

**Şifreli odalarda tamamen kapandı (1.9.0).** İleri gizlilikle birlikte şifreli
mesajlar geçmişe **hiç yazılmıyor**: sonradan bağlanan — mesajın sahibi bile —
onu zaten çözemez, saklamak ise parolayı bilmeyen birinin odaya girip 100
şifreli mesajı toplayıp çevrimdışı saldırıya almasına kapı açardı. Parolasız
odalarda geçmiş aynen çalışmaya devam ediyor; orada gizlenecek bir şey yok.
Karar 2026-09-27, proje sahibinin tercihi. Test: `tests/test_forward_secrecy.py`.

Kalan sınır: Host geçmişi **bilerek açarsa** açık aynen sürer. Kapatmanın tek
yolu geçmişi yalnızca oda parolasını bildiğini kanıtlayan istemcilere
göndermek; bu da odaya giriş için kimlik doğrulaması gerektirir (5.4, 5.5).

### 5.3 Metadata tamamen açık

Kullanıcı adları, oda adları, zaman damgaları, mesaj boyutları ve kimin ne zaman
çevrimiçi olduğu düz metin taşınır. Bu ölçekte bir rakip için metadata çoğu zaman
içerikten değerlidir.

~~Ayrıca sunucunun olay kayıtları şifreli metnin **uzunluğunu** yazar.~~
**Kapatıldı (1.5.0).** Sunucu o sürümden beri olay kaydına mesaj içeriğini
vermiyor; gerçek bir oturumun logunda uzunluk olmadığını doğrulayan test:
`tests/test_logging_and_scroll.py`. Bu belge o sırada güncellenmemişti. Kayıt
aracının kendisi içerik verilirse uzunluğu yazma yeteneğini 1.7.0'a kadar
koruyordu; o da kaldırıldı ki bir çağrı yeniden içerik verdiğinde sızıntı geri
gelmesin (`tests/test_core.py` → `test_anonymous_logger_masks_user_identity`).
Ağdaki paket boyutları ise hâlâ açık (5.7).

**Sesli sohbet üstverisi (Faz 1b, 2026-09-24).** Sunucu artık kimin sesli
sohbete katıldığını ve ne zaman ayrıldığını biliyor; bunu odadakilere
`voice_peers` ile duyuruyor (kullanıcı adı, gönderen kimliği ve oturum tuzu —
**IP yok**). Aktarma yaptığı için katılımcıların IP'lerini de görüyor, ama
metin sohbetinde zaten görüyordu. **Kimin konuştuğunu göremiyor:** ses akışı
konuşulmasa da sabit hızda ve sabit boyda gidiyor. Ses içeriği sunucuda
çözülmüyor; aktarma kodu `cryptography` import etmiyor ve bir test bunu
kilitliyor (`tests/test_voice_relay.py`). Ses paketinin başlığı (sürüm, tip,
gönderen kimliği, sıra numarası, zaman damgası) yolda açık gidiyor;
yönlendirme için gerekli ve zaten kimlik doğrulama verisi olduğu için
değiştirilemiyor.

**Gürültü kapısı üstveriye bir şey eklemiyor (1.8.0).** Konuşma yokken
mikrofonu sessize çeviren gürültü kapısı akışı durdurmuyor: çerçeve yine
gönderiliyor, yalnızca içeriği sessizlik oluyor. Paket boyu içerikten
bağımsızdır — Opus'ta her çerçeve 60 bayt, µ-law'da 320 bayt; dijital sessizlik
de aynı boyda çıkar. Sabit bit hızı ve kapalı DTX tam bu yüzden seçildi. Sonuç:
**susturmayla kapının kapanması ağdan ayırt edilemez**, ikisi de aynı boyda
sessizlik gönderir. Kelimelerin başını kurtaran iki çerçevelik ön bakış paket
sayısını da değiştirmez: her çerçeveye bir paket. Arayüzdeki seviye çubuğu ve
eşik kaydırıcısı yereldir; ölçülen seviye ağa gitmez, eşik yalnızca
kullanıcının kendi makinesinde saklanır. Testler:
`tests/test_voice_opus.py` → `test_paket_boyu_sese_gore_degismiyor`,
`tests/test_voice_gate.py` → `OnBakisTests`.

1.7.0'da bir üstveri **eklendi:** biri odadan başka bir odaya geçerek
ayrılınca sunucu bunu odada kalanlara ayrıca bildirir, arayüz de "başka bir
odaya geçti" diye gösterir. Hangi odaya geçtiği gönderilmez. Böylece
odadakiler, ayrılan kişinin bağlantıyı kesmediğini ve sunucuda kaldığını
öğrenir; bu önceden yalnızca bazen, oda listesindeki değişimden
çıkarılabiliyordu. Bilerek kabul edildi: tek tek "ayrıldı/katıldı"
satırları oda değiştiren birini sürekli bağlanıp kopuyor gibi gösteriyordu.
Testler: `tests/test_hardening.py` → `RoomMoveSnapshotTests`.

### 5.4 Taşıma katmanı şifresiz — iki ayrı problem

Paket zarfı (`type`, `room`, `user`, `ts`, `enc`) ağda açık gider. Bunun içinde
çözümü, maliyeti ve kimden koruduğu farklı **iki** problem var; tek madde olarak
yazıldığı sürece ikisi de yanlış fiyatlanıyordu.

**A — Gizlilik: zarf yolda okunuyor.** Oda adı, kullanıcı adları ve zamanlar
yol üzerindeki pasif dinleyiciye (T3) ve aynı yerel ağdaki birine (T1) görünür.
Kapatmanın tek yolu istemci ile sunucu arasında şifreli bir kanaldır.
**Ertelendi**, gerekçesi 8. bölümde: kanal sunucunun kriptografi yapmasını
zorunlu kılıyor, yani 4. bölümdeki iki somut güvence (sunucu zincirinde
`cryptography` import edilmez; sunucu tarafında üçüncü parti bağımlılık yok)
gider. Kazancının bir kısmını ise hedeflenen senaryo zaten kapatıyor: bağlantı
bir VPN'in içinden geçtiğinde yol üzerindeki dinleyici düz JSON değil şifreli
VPN trafiği görür. **Kanal kurulsa bile Host her şeyi görmeye devam eder** —
üstveri açığı (5.3) bundan bağımsızdır.

**B — Bütünlük: zarf sahtelenebilir.** Aktif bir saldırgan mesaj içeriğini
sahteleyemez (içerik kimlik doğrulamalı şifrelemeyle korunuyor) ama sahte
kullanıcı listesi ya da hata paketi enjekte edebilir, paket düşürebilir. Ve bu
paketlerin asıl kaynağı zaten sunucudur; yani "sunucu yalan söylerse" durumu
kanalla kapanmaz, kanal yalnızca ağı dışarıda bırakır.

B'nin en önemli yarısı 1.9.0'da **sunucuya hiç dokunmadan kapatıldı.** Artık
kullanıcı adı, o kişinin geçici açık anahtarına bağlı: bir isim yanında
"doğrulandı" görünüyorsa o kişi paroladan türetilmiş geçerli bir imza üretmiş
**ve** o imzadaki açık anahtara karşılık gelen gizli anahtarı elinde tuttuğunu
göstermiştir (sarılı gönderen anahtarını açılabilir halde göndererek). Sunucunun
uydurduğu ya da ağa enjekte edilen bir isim bunu yapamaz ve arayüzde
"doğrulanmadı" diye görünür. Kanıt sunucudan değil anahtar takasından geliyor;
yani sunucu artık kimin odada olduğu konusunda **son söz sahibi değil.**
Kod: `core/client.py` → `verified_users`, `core/room_session.py` →
`keyed_peers`. Testler: `tests/test_verified_users.py`. Testlerin yaninda
**elle de denendi** (2026-09-27, iki pencere): ayni parolali eslerde isaret
cikmiyor, farkli/eksik parolali este "dogrulanmadi" cikiyor ve cozulemeyen
mesaj beklemeden yer tutucuyla geliyor.

Kalan sınır: sunucu hâlâ paket düşürebilir ve sahte bir `room_snapshot` ile
istemcileri anahtarlarını bırakmaya zorlayabilir. Bu bir hizmet engellemedir,
sızıntı değil, ve kendini onarıyor: aynı paket yeni bir anahtar duyurusunu da
tetiklediği için takas hemen yeniden kuruluyor.

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
bilgisayardan kalkarsa (örneğin Hamachi kapatılırsa) Host yeniden
başlatılmalıdır.

### 5.7 Mesaj uzunluğu sızar

Şifreli metnin uzunluğu düz metnin uzunluğuyla korelasyonludur. 1.9.0'dan beri
ilişki **bayt hassasiyetinde**: AES-GCM bir akış kipi, yani uzunluğu birebir
taşıyor. Öncesinde Fernet'in 16 baytlık blok hassasiyeti vardı, yani bu açık bir
miktar **büyüdü** — ileri gizlilik kazanırken ödenen küçük bir bedel, ve
kapatılması dolguya bağlı olduğu için ayrıca kapanacak. Dolgu (padding)
uygulanmıyor. Ses tarafında bu sorun yok: çerçeveler sabit boyda gidiyor.

### 5.8 PBKDF2, Argon2id değil — kapatıldı (1.7.0)

240.000 turluk PBKDF2-HMAC-SHA256 tüketici seviyesinde makul, ancak GPU'da
paralelleşir. Argon2id bellek-zor olduğu için özel donanımla saldırıyı çok daha
pahalı yapar.

1.7.0'dan itibaren anahtar **Argon2id** ile türetiliyor: RFC 9106'nın bellek
kısıtlı ortamlar için önerdiği ikinci seçenek, 3 tur, 4 şerit, 64 MiB
(`core/crypto.py`). Her parola denemesi 64 MiB bellek ister; GPU'yu PBKDF2'ye
karşı etkili yapan binlerce paralel deneme bununla çöker. Parametreleri, tuzu ve
oda adı normalleştirmesini bilinen bir cevap vektörü kilitliyor
(`tests/test_crypto.py` → `Argon2idTests`).

Argon2id'nin **işi 1.9.0'da değişti**: türettiği anahtar artık mesajları
şifrelemiyor, karşı tarafın odaya ait olduğunu doğrulayan imzanın anahtarı oluyor
(ve ses anahtarı ondan türüyor, 5.1). Metin sohbetinin şema etiketi bu yüzden
`aesgcm-x25519-v1`; `fernet-argon2id-v1` etiketi 1.8.0 ve öncesine ait.

Daha yüksek bellek bilerek seçilmedi: tuz deterministik olduğu için
parametreleri değiştirmek yine uyumluluğu bozar, ve ileride başka bir
platformdaki istemci birebir aynı parametreleri kullanmak zorunda.

Bedeli uyumluluk: 1.7.0 şifreli odalarda 1.6.x ile konuşamaz. Kalan sınır:
Argon2id denemeyi pahalı yapar, imkânsız yapmaz. Tuz oda adından geldiği için
aynı oda adı ve parola her yerde aynı anahtarı verir; zayıf bir parola hâlâ
çevrimdışı kırılabilir (bkz. 3. bölüm, 5.1).

### 5.9 Dağıtım zinciri korumasız

Dağıtılan `.exe` imzasızdır ve bulut linkiyle paylaşılır. Rakip, kullanıcıya
değiştirilmiş bir binary ulaştırabilir. Yeniden üretilebilir derleme ve imzalama
yoktur.

Bir adim atildi (2026-09-25): dagitilan dosyalarin SHA-256 ozetleri
yayinlaniyor (`tools/surum_ozetleri.py` uretiyor). Indiren kisi kendi
dosyasinin ozetini karsilastirabilir. Bu, imzalamanin yerini TUTMAZ:
dagitim linkini ele geciren biri ozet listesini de degistirebilirse
dogrulama coker. Asil cozum yeniden uretilebilir ve imzali derleme.

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
| Yalnızca sesli konuşma yapan ayrı CLI programı | **Ertelendi** | Tester'ın önerisi (2026-09-17): prototip gibi komut satırından çalışan, yalnızca sesi taşıyan ayrı bir program; anlaması ve kullanması kolay, saldırı yüzeyi küçük (Qt arayüzü, oda listesi, geçmiş, bildirim yok). Lehinde: prototip zaten bu şekilde çalışıyor ve iyi çalıştı; ProxyNull'ın "az özellik güvenliktir" ilkesiyle de uyumlu. Aleyhinde: parola ve karşı tarafın adresi hâlâ program dışından paylaşılmak zorunda, iki ayrı program iki ayrı bakım yükü demek ve metin sohbetiyle aynı odada olmak avantajı kaybedilir. Faz 1b'den sonra, gerçek kullanım görüldüğünde karara bağlanacak |

---

## 8. Açıkların kapatılma sırası

| Sıra | İş | Etki | Büyüklük |
| --- | --- | --- | --- |
| 1 | ~~Geçmişi kaldırmak / varsayılan kapatmak (5.2)~~ **Varsayılan kapatıldı (1.7.0)**; şifreli odalarda tamamen kaldırıldı (1.9.0) | Yüksek | Küçük |
| 2 | ~~Host'un dinlediği arayüzü seçilebilir yapmak (5.6)~~ **Yapıldı (1.6.2)** | Orta | Küçük |
| 3 | ~~Olay kayıtlarından `content_length`'i çıkarmak (5.3)~~ **Yapıldı (1.5.0; yetenek 1.7.0'da kaldırıldı)** | Düşük | Küçük |
| 4 | ~~Argon2id'ye geçiş (5.8)~~ **Yapıldı (1.7.0)** | Orta | Orta |
| 5 | ~~İleri gizlilik (5.1)~~ **Yapıldı — metin 1.9.0, ses 1.10.0** | **En yüksek** | Büyük — protokol değişikliği |
| 6 | ~~Sunucunun üye listesine güvenmeyi bırakmak (5.4-B)~~ **Yapıldı (1.9.0)** | Orta | Küçük |
| 7 | **Mesaj dolgusu (5.7)** — sıradaki iş | Orta | Küçük |
| 8 | İmzalı / yeniden üretilebilir derleme (5.9) | Orta | Orta |
| 9 | Taşıma katmanı şifrelemesi (5.4-A) — **ertelendi** | Düşük–Orta | Büyük |

**5.4-A neden en sona düştü.** Eskiden 5. sıradaydı ve "yüksek etki" yazıyordu;
ikisi de yanlıştı. Üç gerekçe:

1. **Kazancının önemli yarısı zaten alındı.** 5.4'ün gerçek zararı bütünlük
   tarafındaydı (B) ve o, sunucuya kriptografi vermeden kapatıldı.
2. **Kalan yarısının etkisi hedeflenen senaryoda küçük.** Bağlantı bir VPN'in
   içinden geçiyor; yol üzerindeki dinleyici zaten şifreli trafik görüyor.
   Gerçekten açık kalan taraf aynı yerel ağdaki biri (T1) — ve Host, ki kanal
   onu hiç kapatmıyor.
3. **Bedeli, sunucunun bugün verdiği en somut iki güvence.** Kanal, sunucunun
   kriptografi yapmasını zorunlu kılar: `cryptography` import etmeyen sunucu
   zinciri ve sıfır üçüncü parti bağımlılık biter. Küçük ve denetlenebilir bir
   sunucu güvenlikte başlı başına bir özellikti.

Bunun yerine A'nın cevabı **programın dışında**: bağlantı bir tünelden
(WireGuard, SSH tüneli, Tor) geçirilir. Bu karar 9. bölümle de tutarlı: orada
protokolün düz metin parmak izi (9.2) ve onu örtmenin maliyeti (9.5) zaten
yazılı, ve o tablo örtme işinin zarf şifrelemesiyle örtüştüğünü söylüyor.
İkisini birlikte ertelemek, ikisini ayrı ayrı yarım yapmaktan iyidir. ProxyNet zaten "ağı sen getir"
varsayımıyla çalışıyor ve bu işi, tam bu iş için yapılmış araçlara devretmek
kendi taşıma katmanımızı yazmaktan güçlüdür. Uçtan uca şifreli bir kanalın
tasarımdan itibaren içinde olduğu ürün ProxyNull'dır: orada sunucu **hiç yok**,
Noise el sıkışması protokolünde yazılı ve bağlantı Tor onion servisinden
geçiyor (`apps/proxynull/PROTOKOL.md`). ProxyChat'in aynı şeyi taklit etmesi
ikinci bir yarım implementasyon olurdu.

Karar 2026-09-27. Yeniden değerlendirme koşulu: sunucu halka açık bir adrese
taşınırsa (bkz. 5.5) A tekrar yukarı çıkar, çünkü o durumda VPN varsayımı düşer.

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
| Bağlantıyı bir tünelden geçirmek (WireGuard, SSH, Tor) | 9.1/3 kısmen | Küçük — program değişmez, belgelenmesi ve denenmesi gerekir |
| Merkezî koordinasyondan kurtulmak | 9.1/1 | Çok büyük; her eşler-arası sistem bir buluşma noktası ister |

---

## 10. Bu belge ne zaman güncellenir

- Protokole yeni bir paket tipi veya alan eklendiğinde.
- Herhangi bir veri diske yazılmaya başlandığında.
- Şifreleme ile ilgili her değişiklikte.
- Protokolün ağdaki görünümü değiştiğinde (bkz. 9. bölüm).
- 5. bölümdeki bir açık kapandığında — kapanan madde 4. bölüme taşınır ve
  hangi testin garanti ettiği yazılır.
