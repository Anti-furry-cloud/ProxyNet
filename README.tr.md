**Türkçe** · [English](README.md)

# ProxyNet

Kendi sunucunda çalışan, uçtan uca şifreli sohbet. Amaç bir arkadaş grubunun
konuşabilmesi değil yalnızca — amaç **mesajların hiç kimse tarafından
okunamaması**, sunucuyu işleten kişi ve devlet ölçeğinde bir rakip dahil.

> **Bu depoda şu an yalnızca belgeler var.** Kaynak kodu henüz açık değil,
> indirilebilir bir sürüm yok ve yazılım hiçbir bağımsız denetimden geçmedi.
> **Kimse bugün buna güvenmemeli.** Belgeleri erken yayınlıyorum çünkü
> tasarımdaki bir hatayı, üzerine aylarca kod yazdıktan sonra değil, şimdi
> duymak istiyorum.

---

## Ne olduğu

ProxyNet tek bir program değil, iki üründen oluşuyor. İkisi de aynı çekirdeği
paylaşıyor ama farklı sözler veriyor.

| | **ProxyChat** | **ProxyNull** |
| --- | --- | --- |
| Kime | Günlük kullanım, arkadaş grubu | Şifrelemenin öncelik olduğu durumlar |
| Durum | Çalışıyor. 1.12.4 derlendi ve test edildi, henüz dağıtılmadı; sesli sohbet ve ileri gizlilik (metin 1.9.0, ses 1.10.0) uygulamaya girdi | Henüz kod yok; [sınırları](apps/proxynull/README.md) ve [protokol tasarımı](apps/proxynull/PROTOKOL.md) yazılı |
| Hedefi | Kullanışlı olmak, içeriği korumak | Tehdit modelindeki T5 rakibini karşılamak |
| Platform | **Windows 10/11 (64-bit)** | Baştan platform-nötr (Rust, komut satırı) |

Ayrı iki ürün olmasının sebebi şu: az özellik, güvenlikte başlı başına bir
özelliktir. ProxyChat'in "şunu da ekleyelim" baskısının ProxyNull'ı
kirletmemesi için ikisi bilerek ayrıldı.

### ProxyChat bugün ne yapıyor

- Sunucuyu **sen çalıştırıyorsun.** Kimsenin bulutu yok, kimsenin hesabı yok.
  Kayıt olmak, e-posta vermek, telefon numarası vermek yok.
- Mesajlar **istemcide** şifreleniyor. Sunucu düz metni hiçbir zaman görmüyor;
  sunucu kodunda şifre çözme yeteneği bilerek **yok.**
- Metin sohbetinde şifreleme anahtarı **her oturumda yeniden doğuyor**
  (1.9.0'dan itibaren): geçici X25519 anahtarları takas ediliyor ve oturum
  kapanınca bırakılıyor. Parolanın işi şifrelemek değil, karşı tarafın odaya
  ait olduğunu **doğrulamak**; o imzanın anahtarı paroladan Argon2id ile
  türüyor (1.7.0'dan itibaren). Parolayı bilmeyen odaya anahtar veremiyor ve
  içeriği okuyamıyor.
- Oda geçmişi varsayılan olarak **kapalı** (1.7.0'dan itibaren) ve şifreli
  odalarda **hiç tutulmuyor** (1.9.0'dan itibaren): ileri gizlilikte sonradan
  bağlanan onu zaten çözemez. Parolasız odalarda Host açarsa yalnızca bellekte
  tutulur, diske yazılmaz, sunucu kapanınca gider.
- Başka odaya geçip dönünce o odada gördüğün mesajlar geri gelir. Yalnızca
  bellekte tutulur, bağlantı kesilince silinir.
- Oda parolası ekranda gösterilmeden kopyalanabilir. Kopya Windows pano
  geçmişine girmez ve 30 saniye sonra panodan silinir.
- Tanılama kaydı varsayılan olarak **kapalı.**
- **Sesli sohbet** (1.8.0): aynı odadakiler konuşabilir. Ses, oda oturumunun
  anahtarından türeyen anahtarla şifreleniyor ve metin gibi **ileri gizliliği
  var** (1.10.0); sunucu onu çözmeden aktarıyor ve kimin konuştuğunu göremiyor. Konuşma yokken mikrofonu
  sessizleştiren bir gürültü kapısı var. Henüz **varsayılan olarak
  sunulmuyor**: canlı kullanım testi geçilmeden öyle anlatılmayacak.
- Türkçe ve İngilizce arayüz.
- **Yalnızca Windows 10/11 (64-bit).** Çekirdek — şifreleme, protokol, taşıma,
  ses — platform-nötr Python'dur; ürünü Windows'a bağlayan şey üç işletim
  sistemi bağlantısıdır: portun sunucuya özel ayrılması (`SO_EXCLUSIVEADDRUSE`,
  THREAT_MODEL.md 5.6), parolanın DPAPI ile saklanması, ve kopyalanan parolanın
  pano geçmişinden hariç tutulması. Üçü de kolaylık değil **güvenlik**
  özelliği, o yüzden başka bir platforma taşımak bir paketleme işi değil:
  her biri için "o platformda bu güvence şöyle değişiyor" yazmak gerekir.
  Şifrelemenin öncelik olduğu, platform bağımsız kullanım ProxyNull'ın işidir.

### ProxyChat bugün ne yapmıyor

Bunları saklamıyorum; saklarsam belge bir pazarlama metnine dönüşür:

- **Metadata açık.** Kim, kiminle, ne zaman — hepsi görünüyor. Mesajın
  **uzunluğu** 1.12.0'dan beri istisna: yük kovaya yuvarlandığı için kısa
  mesajların hepsi telde aynı boyda gidiyor, uzunluk yerine dokuz basamaktan
  biri görünüyor.
- **Odaya girmek için parola gerekmiyor.** Sunucuya ulaşabilen herkes
  kullanıcı listesini ve trafiğin ritmini görür. Parolayı bilmediği için
  içeriği okuyamaz ve şifreli odada toplayacağı bir geçmiş de artık yok.
- **Zayıf bir parola hâlâ çevrimdışı kırılabilir.** Argon2id her denemeyi
  pahalı yapar, imkânsız yapmaz. Parolayı bulan biri **canlı** bir oturumun
  anahtar takasını taklit edip araya girebilir; kaydedilmiş trafiği açamaz,
  ileri gizlilik onu kapatıyor. Asıl çözüm bir PAKE.
- **Taşıma katmanı şifresiz.** Aktif bir saldırgan mesaj içeriğini
  sahteleyemez ama zarf paketlerini sahteleyebilir.
- **Dağıtılan dosya imzasız.**

Hepsinin ayrıntısı, neden böyle olduğu ve kapatılma sırası burada:
**[THREAT_MODEL.md](THREAT_MODEL.md)**

### Sırada ne var

**Sıradaki iş: imzalı ve yeniden üretilebilir derleme.** Dağıtılan program
imzasız; indiren kişinin elindekinin bizim derlediğimiz şey olduğunu
doğrulamasının bir yolu yok. Sırası ve gerekçesi
[THREAT_MODEL.md](THREAT_MODEL.md) 8. bölümde.

Bekleyen diğer şey **canlı kullanım testi**: sesli sohbetin varsayılan olarak
sunulması ona bağlı ve o test henüz başlamadı.

#### Son kapananlar

**Mesaj dolgusu** (1.12.0). Şifreli metnin uzunluğu düz metnin uzunluğunu
birebir ele veriyordu: sunucu içeriği okuyamıyor ama "bu üç karakterlik bir
cevap, bu dört yüz karakterlik bir paragraf" diyebiliyordu. Artık şifrelenen
şey düz metin değil, 32 bayttan başlayan sabit bir kova merdivenine
yuvarlanmış yük — "ok", "hayır", "geliyorum" telde tıpatıp aynı boyda gidiyor.
Kalan sızıntı en fazla dokuz basamaktan biri. Yaygın alternatif Padmé
seçilmedi, çünkü kısa girdide hiç dolgu yapmıyor (2 → 2, 20 → 20) ve sohbet
mesajlarının ezici çoğunluğu o eşiğin altında. Ses tarafında dolguya gerek
yok (çerçeveler sabit boyda) ama o sabitliği koruyan Opus ayarı — VBR ve DTX
kapalı — artık teste bağlı.

**İleri gizlilik** (metin 1.9.0, ses 1.10.0). Anahtar artık paroladan
türemiyor: her oturumda geçici X25519 anahtarları takas ediliyor ve oturum
kapanınca bırakılıyor; parolanın işi şifrelemek değil, karşı tarafın odaya ait
olduğunu doğrulamak. Sonuç: parola aylar sonra sızsa bile kaydedilmiş trafik
açılamaz. En büyük açık buydu.

**Sesli sohbet artık uygulamanın içinde** (2026-09-25). Sunucu sesi
çözmeden aktarıyor, istemci ayrı bir UDP yolundan konuşuyor, arayüzde
katıl/ayrıl, katılımcı listesi, sustur, gürültü kapısı ve eşik ayarı var. Aynı makinede
iki kopyayla denendi ve ses duyuldu; iki ayrı bilgisayarla henüz
denenmedi.

Bağlantı kalitesinin yeterli olup olmadığına, kuralları ölçüm yapılmadan
önce yayınlanmış ölçümlerle karar verildi: 2026-09-24'te sonuç **kabul
edilebilir** çıktı.

Tasarımı — topoloji kararı, ikili paket biçimi, AES-GCM şeması, kimlik ve
adres doğrulaması ve **henüz çözülmemiş güvenlik soruları** — ölçümlerin
gösterdikleriyle birlikte burada:
**[VOICE_CHAT_PLAN.md](VOICE_CHAT_PLAN.md)**

O belgeyi bu aşamada yayınlamamın sebebi şu: şifreleme tasarımındaki bir
hatayı, üzerine aylarca kod yazdıktan sonra değil şimdi duymak istiyorum.
9. bölümde henüz çözmediğim iki sorunu açıkça yazdım.

Bu listeyi okuyup "o zaman bu ne işe yarıyor?" diye sorabilirsin. Cevap:
sunucuyu işleten kişiye ve odaya giremeyen üçüncü kişilere karşı içeriğini
koruyor. Devlet ölçeğinde bir rakibe karşı korumuyor ve bunu iddia etmiyorum.
Aradaki farkı gizlemek yerine yazmayı tercih ediyorum.

---

## Kim geliştiriyor

**[Anti-furry-cloud](https://github.com/Anti-furry-cloud)** — tek kişilik bir
proje. Arkasında şirket, ekip ya da fon yok.

Bunu şunun için yazıyorum: kriptografi, tek kişinin denetimsiz yazdığında
yanlış gitmeye en müsait alanlardan biridir. Tehdit modelini bu kadar açık
yayınlamamın sebebi de bu — doğru olduğunu iddia etmek yerine, yanlışını
gösterebilesin diye önüne koyuyorum.

Geliştirme Türkçe yürüyor; belgelerin hepsi Türkçe ve İngilizce yayınlanıyor.
İkisi çelişirse **Türkçe olan doğrudur.**

---

## Bu depoda ne var

| Dosya | İçerik |
| --- | --- |
| [CHANGELOG.md](CHANGELOG.md) | Sürüm sürüm neyin yanlış olduğu ve ne değiştiği |
| [THREAT_MODEL.md](THREAT_MODEL.md) | Neyi koruduğu, neyi korumadığı, rakip modeli, tasarım ilkeleri, açıkların kapatılma sırası |
| [VOICE_CHAT_PLAN.md](VOICE_CHAT_PLAN.md) | Sesli sohbetin tasarım planı — topoloji, paket biçimi, şifreleme şeması, açık güvenlik soruları |
| [apps/proxynull/README.md](apps/proxynull/README.md) | ProxyNull'ın sınırları: zorunluluklar, yasaklar, ProxyChat'ten neden ayrı |
| [apps/proxynull/PROTOKOL.md](apps/proxynull/PROTOKOL.md) | ProxyNull'ın protokol tasarımı — buluşma kodu, Noise el sıkışması, doğrulama kodu, dolgu; kararı verilmiş ve verilmemiş maddeler ayrı işaretli |
| [listening/](listening/LISTENING.tr.md) | Kör dinleme testi: simüle ağ kesintileri konuşmada nasıl duyuluyor |
| [VERIFYING.md](VERIFYING.md) | İndirdiğiniz dosyayı nasıl doğrularsınız, ve bu doğrulamanın sınırı |
| [THIRD-PARTY.md](THIRD-PARTY.md) | Pakete giren üçüncü parti bileşenler, lisansları ve kaynakları |
| [LICENSE](LICENSE) | GNU GPL v3 metni |

Her belgenin en üstünde Türkçe/English geçişi var; ayrıca listelenmedi.

Kod açıldığında bu depoya eklenecek; belgeler yerinde kalacak.

---

## Resmî kaynak ve kopyalar

Bu projenin tek resmî kaynağı **https://github.com/Anti-furry-cloud/ProxyNet**
adresidir. Başka bir yerde dolaşan bir ProxyChat/ProxyNet kopyası buradan
çıkmamış olabilir; indirmeden önce buraya bakın.

Proje **GNU GPL v3** ile yayınlanıyor. Bu, kopyalamayı yasaklamıyor — tam
tersi, serbest bırakıyor. Yalnızca üç şart var:

- Değiştirilmiş sürümü dağıtan, **kaynak kodunu da** vermek zorunda.
- Lisans ve telif notları korunur; kim yazdı sorusu silinemez.
- Türev iş de aynı lisansla dağıtılır.

Yani kodu alıp kapalı kaynak bir ürüne çevirmek ya da yazarını değiştirmek
lisans ihlalidir.

Henüz herkese açık bir sürüm yok. Bir sürüm dağıtıldığında dosyaların
SHA-256 özetleri bu depoda yayınlanacak ve o liste **imzalanacak**; elinizdeki
dosyanın özeti orada yazanla aynı değilse, o dosya bizim dağıttığımız dosya
değildir.

İmza anahtarının parmak izi:

```
23DC 905B 569A 80BD D243  525B 80DA 0356 E47B B37C
```

Nasıl doğrulanacağı ve bu doğrulamanın **sınırı**:
[VERIFYING.md](VERIFYING.md). Derleme ayrıca yeniden üretilebilir, yani
isterseniz özete güvenmek yerine kaynaktan derleyip karşılaştırabilirsiniz.

---

## Geri bildirim

Tehdit modelinde bir hata, eksik bir rakip ya da fazla iyimser bir iddia
görürsen **issue aç.** En çok işime yarayacak geri bildirim şu: *"5. bölümde
yazmadığın ama var olan bir açık şu."*

Kod olmadan güvenlik iddiası denetlenemez — bunun farkındayım. Bu depo bir
kanıt değil, bir niyet beyanı ve bir tasarım taslağıdır.

**Kod okumadan da yardım edebilirsin:** birkaç kısa kaydı dinleyip
kesintilerin sana nasıl geldiğini söyle. Yönerge ve sorular:
**[listening/LISTENING.tr.md](listening/LISTENING.tr.md)**. Cevaplar
[Listening test](https://github.com/Anti-furry-cloud/ProxyNet/discussions/1) tartışmasına.

---

## Lisans

Proje GNU GPL v3 (ya da tercihe göre sonraki bir sürüm) altında; tam metin
[LICENSE](LICENSE) dosyasında. Bu belgeler de projenin parçası.
