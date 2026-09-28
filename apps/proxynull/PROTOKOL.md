**Türkçe** · [English](PROTOCOL.en.md)

# ProxyNull — protokol tasarımı

> **Durum: taslak, kod yazılmadı.** Bu belge dilden bağımsızdır ve normatif
> olmayı hedefler: "şöyle olmalı" der, "şöyle olabilir" demez. Kararı verilmiş
> maddeler **Karar** ile, verilmemiş olanlar **Açık** ile işaretli.
>
> Hiçbir bağımsız inceleme geçmedi. Bir hata görürsen bu belgeye bakarak
> söyleyebilmen için erken yazıldı.

ProxyNull'ın ne olduğu, neyi yapmayacağı ve hangi rakibi hedeflediği
[README.md](README.md) içinde. Bu belge **nasıl** sorusunu cevaplıyor.

---

## 1. Kapsam

**Karar — iki kişi.** ProxyNull grup sohbeti yapmaz. Yalnızca iki kişi
arasında. Grup şifrelemesinde ileri gizlilik ve üyelik tutarlılığı, tek
kişilik bir projenin kendi kendine yazabileceği bir şey değil; iki kişide
sorun birebir şifrelemeye indiği için çözülebilir kalıyor.

**Karar — sunucu yok.** Aktarma sunucusu, buluşma sunucusu, hesap sunucusu
yok. İki uç doğrudan konuşur.

**Karar — kalıcı kimlik yok.** Diske hiçbir şey yazılmaz; kimlik anahtarı da
yazılmaz. Her oturum kendi geçici anahtarlarıyla kurulur. Bunun bedeli, her
konuşmada doğrulamanın yeniden yapılması (bkz. 5. bölüm) ve kabul edilmiş
bedeldir: ProxyNull'da gizlilik, kolaylıktan önce gelir.

**Karar — arayüz komut satırı.** Grafik arayüz yok. Az kod, az saldırı
yüzeyi.

Hedef rakip [../../THREAT_MODEL.md](../../THREAT_MODEL.md) içindeki **T5**:
trafiği yıllarca saklayan, cihaza el koyabilen, hukuki zorlama uygulayan
rakip.

---

## 2. Buluşma: tek kullanımlık kod

Sunucu ve kalıcı kimlik olmadığı için iki tarafın birbirini bulması için tek
bir bilgi paylaşılır: **tek kullanımlık kod.**

**Karar — kod biçimi.** Kelime listesinden rastgele seçilmiş, tirelerle
ayrılmış kelimeler:

```
yedi-kum-lamba-tepsi-savan
```

- Kelimeler `secrets` benzeri kriptografik bir kaynaktan seçilir.
- **En az 55 bit entropi** zorunlu. 2048 kelimelik bir listeyle beş kelime
  55 bit verir. Liste küçülürse kelime sayısı artar; hesap koda gömülmez,
  çalışma anında yapılır ve sınırın altındaysa program çalışmayı reddeder.
- Kod ekranda gösterilir, **hiçbir yere yazılmaz.**
- Kod **sesle okunabilir** olmalı: kelime listesi kısa, ayırt edilebilir ve
  aynı dilde yazılışı tek olan kelimelerden kurulur.

**Karar — koddan iki şey türetilir,** ikisi de aynı kodun ayrı alanlarından:

| Türetilen | Ne için | Alan etiketi |
| --- | --- | --- |
| Buluşma anahtarı | Onion servisinin adresi | `proxynull:rendezvous:v1` |
| Ortak sır | El sıkışmada kimlik doğrulama | `proxynull:handshake:v1` |

Türetme **Argon2id** ile yapılır. Parametreler belgeye yazılır ve pazarlık
edilmez (bkz. 7. bölüm). Alan etiketleri olmadan aynı anahtar iki işte
kullanılırdı; bir işteki kullanım diğerini zayıflatabilir.

**Karar — adres iletilmez, hesaplanır.** Bekleyen taraf buluşma anahtarından
bir onion servisi yayınlar, bağlanan taraf aynı koddan aynı adresi hesaplayıp
bağlanır. Böylece elden iletilecek tek şey kod olur; 56 karakterlik bir adresi
sesle okumak gerekmez.

**Karar — Tor onion servisi.** Gerekçe: iki taraf da birbirinin IP adresini
görmez, modemde port açmak gerekmez ve ulaşılabilirlik bir VPN şirketine
bağlı kalmaz. Bedeli gecikmenin artması (metin için kabul edilebilir) ve
Tor'un bazı ülkelerde engellenmesi.

**Karar — kod tek kullanımlıktır.**

- İlk başarılı oturumdan sonra kod geçersizdir.
- Başarısız bir el sıkışma denemesinden sonra da geçersizdir: yanlış kodla
  gelen biri ikinci denemeyi yapamaz, program kapanır ve yeni kod istenir.
- Kodun ömrü en fazla **10 dakika**. Süre dolunca servis kapanır.

**Açık — kod uzunluğu ile konuşma kolaylığı arasındaki denge.** Beş kelime
telefonda okunabiliyor mu, yoksa dört kelime + daha büyük liste mi daha
iyi? Gerçek kullanımla ölçülecek.

---

## 3. El sıkışma

**Karar — Noise ile, statik anahtar olmadan.** Kalıcı kimlik olmadığı için
her iki tarafın statik anahtarı da yok. Kullanılan kalıp:

```
Noise_NNpsk0_25519_ChaChaPoly_BLAKE2s
```

- `NN`: iki taraf da yalnızca geçici (ephemeral) anahtar üretir.
- `psk0`: koddan türetilen ortak sır, el sıkışmanın ilk mesajında karışıma
  girer. Kodu bilmeyen biri el sıkışmayı tamamlayamaz.
- Anahtar değişimi X25519, şifreleme ChaCha20-Poly1305, özet BLAKE2s.

**Neden düzgün bir PAKE (CPace, OPAQUE) değil:** PAKE, düşük entropili bir
paroladan bile çevrimdışı sözlük saldırısına kapalı bir oturum kurar. Burada
kod düşük entropili değil (en az 55 bit) ve türetme Argon2id'den geçiyor;
saldırganın kaydettiği el sıkışmaya karşı çevrimdışı deneme yapması
pratikte imkânsız hâle geliyor. Buna karşılık Noise'un denenmiş, incelenmiş
uygulamaları var. Bu bir **denge kararı**: PAKE daha güçlü bir garanti verir,
Noise daha az yeni kod demektir. Kod entropisi 55 bitin altına düşürülürse bu
karar geçersizdir ve PAKE zorunlu olur.

**Karar — mod pazarlığı yok.** Şifre paketi, Noise kalıbı ve Argon2id
parametreleri protokol sürümüne gömülür. İki taraf aynı sürümde değilse
bağlantı kurulmaz; düşürme saldırısına yer yok.

**Karar — ileri gizlilik.** Oturum anahtarları geçici anahtarlardan doğar ve
oturum bitince silinir (bellekten de: `zeroize`). Kod sonradan ele geçse bile
kaydedilmiş trafik açılamaz, çünkü kod yalnızca el sıkışmaya kimlik
doğruluyor, oturum anahtarını tek başına belirlemiyor.

**Açık — kopan bağlantının yeniden kurulması.** İzin verilen bir kolaylık ama
kod tek kullanımlık. Seçenekler: el sıkışmada bir "yeniden bağlanma bileti"
üretmek (kalıcı olmayan, yalnızca bellekte), ya da kopan bağlantıda yeni kod
istemek. İkincisi daha basit ve daha güvenli, birincisi daha kullanışlı.

---

## 4. Anahtar yenileme ve sınırı

**Karar — düzenli yenileme.** Oturum anahtarı her **1000 mesajda ya da 15
dakikada** (hangisi önce gelirse) Noise'un kendi yenileme işlemiyle
tazelenir. Eski anahtar silinir.

**Bilinen sınır — kopan anahtarın iyileşmesi (post-compromise security)
yok.** Bir uçtaki bellek o an ele geçerse, yenileme zincirinden sonraki
mesajlar da okunabilir; Signal'in çift ratchet'ı bunu yeni geçici anahtar
değişimleriyle çözüyor. ProxyNull v1'de bu yok ve **bu belge aksini iddia
etmiyor.** Gerekçe: oturumlar kısa, kalıcı kimlik yok ve iki uçlu bir
ratchet'ı kendi başına doğru yazmak bu projenin ölçeğinin üstünde.

**Açık — oturum içinde yeni geçici anahtar değişimi (basit ratchet)
eklenecek mi?** Eklenirse sınır kapanır; maliyeti protokolün karmaşıklığı.

---

## 5. Doğrulama: kısa doğrulama kodu

Kalıcı kimlik olmadığı için "güvenlik numarası" oturumdan oturuma aynı
kalamaz. Yerine her oturumda o oturuma özel bir kod kullanılır.

**Karar — kod el sıkışma özetinden türetilir.** Noise el sıkışmasının
sonundaki `h` değerinden, alan etiketiyle (`proxynull:sas:v1`) dört kelime
üretilir. Aradaki biri iki tarafa ayrı el sıkışma yaptığı için iki tarafta
farklı kod çıkar.

**Karar — doğrulama zorunludur.** İki taraf da "kod aynı" onayını vermeden
mesaj gönderilemez. İsteğe bağlı doğrulama, pratikte hiç yapılmayan
doğrulamadır.

**Karar — karşılaştırma program dışından yapılır:** yüz yüze ya da sesli
olarak. Program bunu otomatikleştirmez; otomatikleştirmek, doğrulamayı
kırılan kanalın içine geri koymak olurdu.

Yöntem yeni değil: sesli görüşme şifrelemesinde ZRTP yıllardır kısa
doğrulama dizisi (SAS) kullanıyor.

**Açık — kelime mi rakam mı?** Dört kelime mi, altı hane mi daha güvenilir
karşılaştırılıyor? İkisinin de karşılığı aynı entropi olacak şekilde
ayarlanır.

---

## 6. Mesaj biçimi

**Karar — zarf yok.** ProxyChat'in paketlerinde `type`, `room`, `user` gibi
alanlar düz metin gider. ProxyNull'da ağda giden her bayt şifrelidir; tip
bilgisi de şifreli yükün içinde.

**Karar — dolgu.** Mesajlar sabit boyut kovalarına doldurulur: **256, 512,
1024, 2048, 4096 bayt.** Kovadan büyük mesaj parçalanır. Amaç, mesaj
uzunluğunun içerik hakkında bilgi vermesini engellemek. ProxyChat aynı işi
1.12.0'dan beri yapıyor (bkz. THREAT_MODEL 5.7) ama merdiveni 32 bayttan
başlıyor: orada zarf şifrelenmediği için kullanıcı ve oda adı zaten açık,
dolayısıyla taban mesajı kısa tutmanın maliyeti yok. Burada zarf da şifreli
olduğu için taban 256 bayt: dolgulanan şey mesajla birlikte kimin hangi odaya
yazdığı.

**Karar — yazıyor göstergesi yok.** Tuş vuruşu zamanlaması yazılan metin
hakkında bilgi verir ve kimin ne zaman aktif olduğunu ele verir.

**Açık — kapak trafiği (cover traffic).** Sessizken de paket göndermek,
konuşma ritmini gizler ama pil ve bant tüketir, Tor ağına da yük olur.
Ölçülmeden karar verilmeyecek.

---

## 7. Kriptografik parametreler

Hepsi protokol sürümüne gömülüdür; pazarlık edilmez.

| İş | Seçim |
| --- | --- |
| Koddan anahtar türetme | Argon2id, RFC 9106 ikinci seçenek: 3 tur, 4 şerit, 64 MiB |
| Anahtar değişimi | X25519 (Noise `NNpsk0`) |
| Şifreleme | ChaCha20-Poly1305 |
| Özet | BLAKE2s |
| Alt anahtar türetme | HKDF-BLAKE2s, alan etiketleriyle |

Argon2id parametreleri ProxyChat 1.7.0 ile aynı bilerek: aynı gerekçeyle
seçildi (bellek-zor olması özel donanımı pahalılaştırıyor) ve iki üründe
farklı parametre tutmanın bir faydası yok.

**Karar — tuz.** ProxyChat'te tuz oda adından türüyor, yani deterministik.
ProxyNull'da tuz **kodun kendisinden** türer ve kod her oturumda yeni olduğu
için tuz de yenidir; aynı kod iki kez kullanılmadığından aynı anahtar iki kez
üretilmez.

---

## 8. Sıfır kalıcılık

**Karar — diske hiçbir şey yazılmaz.** Ne mesaj, ne kod, ne ayar, ne log, ne
çökme dökümü.

- Anahtar malzemesi kullanıldıktan sonra bellekten silinir (`zeroize`).
- Program çökme dökümü üretmeyi kapatır.
- Terminale basılan mesajlar kaydın dışında değil: **kullanıcının kendi
  terminali geçmiş tutuyorsa mesajlar oraya düşer.** Bu programın
  kapatamayacağı bir şey; belgede ve ilk çalıştırmada açıkça söylenir.

**Açık — takas alanı (swap).** Bellekteki anahtar, işletim sistemi belleği
diske taşırsa diske düşebilir. Linux'ta `mlock` ile sayfalar kilitlenebilir;
Windows'ta karşılığı sınırlı. Ne kadarının garanti edilebileceği araştırılıp
yazılacak.

---

## 9. Metadata: ne gizleniyor, ne gizlenmiyor

**Gizlenen:**

- İki tarafın IP adresi birbirinden ve ağdaki dinleyiciden (Tor).
- Mesaj içeriği, uzunluğu (dolgu) ve tipi.
- Kimlik: kalıcı bir tanımlayıcı hiç yok.

**Gizlenmeyen:**

- **Tor kullandığın.** ISP, Tor'a bağlandığını görür. Köprüler (bridge) bunu
  bir ölçüde gizler; kapsama alınıp alınmayacağı açık.
- **Konuşmanın zamanı ve ritmi.** Kapak trafiği eklenmezse paket zamanları
  konuşma temposunu gösterir.
- **Kodu paylaştığın kanal.** Kodu telefonda söylediysen, o görüşmenin kaydı
  iki kişinin konuşmaya hazırlandığını gösterir. Protokolün dışında kalan ve
  kapatılamayan sınır bu.

---

## 10. Reddedilen tasarımlar

| Tasarım | Gerekçe |
| --- | --- |
| Kalıcı kimlik anahtarı (dosyada, parolayla şifreli) | Diske yazılan her şey el konulabilir. Kolaylık için gizlilikten ödün verilmez (kullanıcı kararı, 2026-09-17) |
| Kimliği paroladan türetmek (brain key) | Parola kimliğin kendisi olur; zayıf parola çevrimdışı kırılır, parola değişimi kimliği değiştirir |
| Grup sohbeti | Grup şifrelemesinde ileri gizlilik ayrı ve büyük bir problem; iki kişi kapsamı bilerek seçildi |
| Buluşma sunucusu (Magic Wormhole gibi) | Sunucu, kimin kiminle buluştuğunu görür ve kapatılabilir; Tor onion servisi aynı işi sunucusuz yapıyor |
| Çevrimdışı mesaj | Saklama gerektirir; sıfır kalıcılıkla çelişir. İki taraf da çevrimiçi olacak |
| Sesli sohbet | Sabit hızlı ses akışı, bir tarafın konuştuğunu ve ne zaman konuştuğunu ağa verir; bu, 6. bölümdeki dolgunun tam tersi yönde çalışır — dolgu boyu gizler, sürekli akış zamanlamayı açar. ProxyChat'te ses var (aktarma üzerinden, sabit bit hızıyla); burada olmayacak. Doğrulama kodunun sesle okunması istisna değil: o, program dışında yapılıyor |
| Mesaj geçmişi, ayar dosyası, bildirim önizlemesi | [README.md](README.md) yasaklar tablosu |

---

## 11. Uygulama yazılırken kanıtlanacaklar

Kod yazıldığında bu belgedeki her iddianın karşılığında bir test olmalı:

- Aynı kod iki tarafta **aynı** onion adresini ve aynı ortak sırrı üretiyor.
- Farklı kodlar farklı adres üretiyor; tek bir kelime değişince adres
  tamamen değişiyor.
- 55 bitin altındaki bir kod üretimi **reddediliyor.**
- Yanlış kodla gelen taraf el sıkışmayı tamamlayamıyor ve ikinci deneme
  yapamıyor.
- Araya giren bir taraf iki uçta **farklı** doğrulama kodu üretiyor.
- Doğrulama onaylanmadan mesaj gönderilemiyor.
- Aynı boyutta mesajlar ağda aynı boyutta görünüyor (dolgu).
- Oturum bitince anahtar malzemesi bellekte kalmıyor.
- Diske hiçbir dosya yazılmıyor (çalışma sırasında dosya sistemi izlenerek).

---

## 12. Bu belge ne zaman güncellenir

- Bir **Açık** madde karara bağlandığında.
- Şifre paketi, Noise kalıbı ya da Argon2id parametreleri değiştiğinde —
  bunlar protokol sürümünü de artırır.
- Ağda görünen bayt sırası ya da dolgu kovaları değiştiğinde.
- Reddedilen bir tasarım yeniden gündeme geldiğinde: kararı değiştirmek değil,
  gerekçeyi güncellemek gerekir.
