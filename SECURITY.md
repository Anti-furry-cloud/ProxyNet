**Türkçe** · [English](SECURITY.en.md)

# Güvenlik

## Önce bilinmesi gerekenler

Bu yazılım **bağımsız denetimden geçmemiştir.** Tek kişi tarafından yazıldı ve
kriptografisi profesyonel olarak incelenmedi.

Bilinen ve **kabul edilmiş** eksikler [THREAT_MODEL.md](THREAT_MODEL.md) 5.
bölümde tek tek yazılıdır. Bunları açık olarak bildirmenize gerek yok — zaten
biliyoruz:

- Metadata korunmuyor (kullanıcı adı, oda adı, zaman düz gider; mesaj boyu
  1.12.0'dan beri kovaya yuvarlanıyor)
- Taşıma katmanı şifresiz; zarf paketleri sahtelenebilir
- Sunucuda kimlik doğrulama yok, odaya girmek için parola gerekmiyor
- Zayıf bir parola Argon2id'ye rağmen çevrimdışı denenebilir; parolayı bulan
  biri **canlı** bir oturumun anahtar takasını taklit edebilir
- Belleğe el konulmasına karşı koruma kısmi (Python'da anahtar güvenilir
  şekilde sıfırlanamıyor)
- Post-compromise security yok (Double Ratchet karşılığı)
- Kuantuma karşı yalnızca kısmen dayanıklı: hibrit anahtar değişimi (ML-KEM)
  henüz yok, 1.13.0'daki koruma da ancak oda parolası kadar güçlü (5.10)
- Dağıtılan binary'nin Authenticode imzası yok (özet listesi GPG ile imzalı;
  [VERIFYING.md](VERIFYING.md))

Kapanmış olanlar — bunları eksik diye bildirmeye gerek yok, ama **kapanmadığını
gösteren bir bulgu çok değerlidir:**

- **İleri gizlilik var** (metin 1.9.0, ses 1.10.0): anahtar her oturumda
  yeniden doğuyor
- **Yalnızca X25519'u kırmak kaydedilmiş trafiği açmıyor** (1.13.0): paroladan
  türetilen bir anahtar da oturum anahtarına giriyor
- **Şifreli odada geçmiş hiç tutulmuyor** (1.9.0)
- **Mesaj uzunluğu dolguyla gizleniyor** (1.12.0): yük 32 bayttan başlayan
  kovalara yuvarlanıyor, kısa mesajların hepsi telde aynı boyda gidiyor
- **Üye listesi kanıtla doğrulanıyor**, sunucunun iddiasına güvenilmiyor (1.9.0)

**Devlet ölçeğinde bir rakibe karşı koruma sağladığı iddia edilmemektedir.**

## Neyi bildirmelisiniz

Yukarıdaki listede olmayan her şey. Özellikle:

- Mesaj içeriğinin şifrelenmemesine ya da yanlış şifrelenmesine yol açan bir hata
- Sunucunun düz metne erişmesini sağlayan bir yol
- Oda parolasını bilmeden mesaj okumaya izin veren bir açık
- Uzaktan çökertme, bellek tüketimi, sonsuz döngü
- Parolanın ya da anahtarın diske düz yazılmasına yol açan bir durum
- Kaynak koddan derlenen binary ile yayınlanan binary arasında fark

## Nasıl bildirmelisiniz

**Herkese açık issue açmayın.** Bunun yerine:

> GitHub → bu deponun **Security** sekmesi → **Report a vulnerability**
> (Privately report a security vulnerability)

Bu, bildirimi yalnızca depo sahibinin görebileceği şekilde iletir.

GitHub hesabınız yoksa ya da bu yolu kullanmak istemiyorsanız:
**proxynet.dev@protonmail.com**. Bir şeyi bilin: e-posta ancak Proton'dan
Proton'a uçtan uca şifreli gider; başka bir sağlayıcıdan gönderilen e-posta
yolda okunabilir. Kavram kanıtını göndermeden önce ilk mesajda yalnızca
sorunun ne olduğunu yazın, ayrıntıyı nasıl ileteceğimizi birlikte seçelim.

Bildiriminize şunları eklerseniz çok işe yarar:

1. Etkilenen sürüm (uygulamanın üst çubuğunda yazıyor)
2. Sorunu tetikleyen adımlar
3. Beklenen ve gerçekleşen davranış
4. Varsa kavram kanıtı

## Ne bekleyebilirsiniz

Bu bir hobi projesidir, arkasında şirket yoktur. Söz verebileceğim tek şey
dürüstlük:

- Bildiriminizi okuyacağım ve aldığımı bildireceğim
- Geçerliyse `THREAT_MODEL.md` dosyasına işleyeceğim — düzeltemesem bile
- Düzeltme çıkarsa [CHANGELOG.md](CHANGELOG.md) içinde belirteceğim
- İsterseniz adınızı anarım, istemezseniz anmam

**Sabit bir yanıt süresi taahhüt edemem.** Tek kişilik bir projede bunu vaat
etmek yalan olur.

## Desteklenen sürümler

Yalnızca **en son sürüm.** Eski sürümlere geriye dönük düzeltme yapılmaz;
güncelleyin.

## Kapsam dışı

- Uç cihazın ele geçirilmesi (keylogger, ekran görüntüsü, bellek dökümü)
- Oda parolasının paylaşım kanalı — parolayı güvensiz bir yerden paylaşırsanız
  zincir orada kırılır
- Tahmin edilebilir parola seçimi
- İşletim sistemi, VPN istemcisi ya da donanım açıkları
- SmartScreen uyarısı — binary imzasız, biliniyor
