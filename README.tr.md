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
| Durum | Çalışıyor. 1.7.0 derlendi ve test edildi, henüz dağıtılmadı | Henüz kod yok, yalnızca sınırları yazılı |
| Hedefi | Kullanışlı olmak, içeriği korumak | Tehdit modelindeki T5 rakibini karşılamak |

Ayrı iki ürün olmasının sebebi şu: az özellik, güvenlikte başlı başına bir
özelliktir. ProxyChat'in "şunu da ekleyelim" baskısının ProxyNull'ı
kirletmemesi için ikisi bilerek ayrıldı.

### ProxyChat bugün ne yapıyor

- Sunucuyu **sen çalıştırıyorsun.** Kimsenin bulutu yok, kimsenin hesabı yok.
  Kayıt olmak, e-posta vermek, telefon numarası vermek yok.
- Mesajlar **istemcide** şifreleniyor. Sunucu düz metni hiçbir zaman görmüyor;
  sunucu kodunda şifre çözme yeteneği bilerek **yok.**
- Anahtar, oda parolasından Argon2id ile türüyor (1.7.0'dan itibaren).
  Parolayı bilmeyen içeriği okuyamıyor.
- Oda geçmişi varsayılan olarak **kapalı** (1.7.0'dan itibaren). Host açarsa
  yalnızca bellekte tutulur, diske yazılmaz, sunucu kapanınca gider.
- Başka odaya geçip dönünce o odada gördüğün mesajlar geri gelir. Yalnızca
  bellekte tutulur, bağlantı kesilince silinir.
- Oda parolası ekranda gösterilmeden kopyalanabilir. Kopya Windows pano
  geçmişine girmez ve 30 saniye sonra panodan silinir.
- Tanılama kaydı varsayılan olarak **kapalı.**
- Türkçe ve İngilizce arayüz.

### ProxyChat bugün ne yapmıyor

Bunları saklamıyorum; saklarsam belge bir pazarlama metnine dönüşür:

- **İleri gizlilik yok.** Anahtar hiç değişmiyor. Bugün kaydedilen şifreli
  trafik, parola gelecekte ele geçerse geriye dönük olarak okunabilir. En
  büyük açık bu.
- **Metadata tamamen açık.** Kim, kiminle, ne zaman, ne uzunlukta — hepsi
  görünüyor.
- **Odaya girmek için parola gerekmiyor.** Sunucuya ulaşabilen herkes
  kullanıcı listesini ve trafiğin ritmini görür. Host oda geçmişini açarsa
  şifreli geçmişi de toplayabilir.
- **Zayıf bir parola hâlâ çevrimdışı kırılabilir.** Argon2id her denemeyi
  pahalı yapar, imkânsız yapmaz; aynı oda adı ve parola her yerde aynı
  anahtarı verir.
- **Taşıma katmanı şifresiz.** Aktif bir saldırgan mesaj içeriğini
  sahteleyemez ama zarf paketlerini sahteleyebilir.
- **Dağıtılan dosya imzasız.**

Hepsinin ayrıntısı, neden böyle olduğu ve kapatılma sırası burada:
**[THREAT_MODEL.md](THREAT_MODEL.md)**

### Sırada ne var

Sesli sohbet üzerinde çalışılıyor. Çekirdeği yazıldı ve bir prototip, ayrı
internet bağlantılarındaki iki bilgisayar arasında canlı konuşmayı taşıdı; o
prototip ayrı bir araç, kurulan programın parçası değil. Bağlantı
kalitesinin yeterli olup olmadığına, kuralları ölçüm yapılmadan önce
yayınlanmış ölçümlerle karar verildi: 2026-09-24'te sonuç **kabul
edilebilir** çıktı, yani ağ tarafına devam edilebilir. Sesli sohbetin ürüne
varsayılan olarak girmesi, kuralları yine önceden yazılmış canlı kullanım
testine de bağlı. Tasarımı — topoloji kararı, ikili
paket biçimi, AES-GCM şeması ve **henüz çözülmemiş güvenlik soruları** —
prototipin ve ölçümlerin şimdiye kadar gösterdikleriyle birlikte burada:
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
| [THREAT_MODEL.md](THREAT_MODEL.md) | Neyi koruduğu, neyi korumadığı, rakip modeli, tasarım ilkeleri, açıkların kapatılma sırası |
| [THREAT_MODEL.en.md](THREAT_MODEL.en.md) | Aynısının İngilizcesi |
| [VOICE_CHAT_PLAN.md](VOICE_CHAT_PLAN.md) | Sesli sohbetin tasarım planı — topoloji, paket biçimi, şifreleme şeması, açık güvenlik soruları |
| [VOICE_CHAT_PLAN.en.md](VOICE_CHAT_PLAN.en.md) | Aynısının İngilizcesi |
| [listening/](listening/LISTENING.tr.md) | Kör dinleme testi: simüle ağ kesintileri konuşmada nasıl duyuluyor |
| [LICENSE](LICENSE) | GNU GPL v3 metni |

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
SHA-256 özetleri bu depoda yayınlanacak; elinizdeki dosyanın özeti orada
yazanla aynı değilse, o dosya bizim dağıttığımız dosya değildir.

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
