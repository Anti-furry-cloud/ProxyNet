**Türkçe** · [English](README.md)

# ProxyNet

Kendi sunucunda çalışan, uçtan uca şifreli sohbet. Amaç bir arkadaş grubunun
konuşabilmesi değil yalnızca — amaç **mesajların hiç kimse tarafından
okunamaması**, sunucuyu işleten kişi ve devlet ölçeğinde bir rakip dahil.

## Hızlı başlangıç

**[ProxyChat 1.13.0'ı indir (Windows 10/11)](../../releases/latest)**. O sayfadan `ProxyChat-Setup.exe` dosyasını al.

1. **Kur.** Dosyanın Authenticode imzası yok, bu yüzden Windows SmartScreen
   uyarı verir: *Ek bilgi → Yine de çalıştır*. Önce dosyayı kontrol etmek
   istersen: [VERIFYING.md](VERIFYING.md).
2. **Aynı ağda olun.** Herkesin sunucuyu açanın bilgisayarına ulaşabilmesi
   gerekiyor: aynı yerel ağ ya da Hamachi gibi bir sanal LAN.
3. **Biri sunucuyu açar.** **Host**'u seçer, dinlenecek ağı seçer, bir oda
   parolası girer ve bağlanır. Adresi ve parolayı arkadaşlarına iletir — yüz
   yüze ya da şifreli bir mesajlaşma uygulamasıyla.
4. **Diğerleri katılır.** **Join**'i seçer; adresi, aynı oda adını ve aynı
   parolayı girer. Parola aynı değilse kimse mesajları okuyamaz.

> **Güvenmeden önce:** tek kişinin yazdığı erken bir sürüm ve **hiçbir
> bağımsız güvenlik denetiminden geçmedi.** **Ne yazdığını korur, kim
> olduğunu değil** — sunucu odada kimin, ne zaman olduğunu görür. Aşağıda
> [ne yapmadığını](#proxychat-bugün-ne-yapmıyor) ve
> [ne için, ne için olmadığını](#ne-için-ne-için-değil) oku.

> **⚠ Sahte bir "ProxyChat.exe" dolaşıyor (2026-10).** İnternette başka
> yerlerde `ProxyChat.exe` adlı bir dosya sunuluyor. **Bu ProxyChat değil, bir
> zararlı yazılım** — uzaktan erişim truva atı. Çalıştırmadan inceledim:
> yaklaşık 14 MB, imzasız, SHA-256
> `6f2b3816fa61328de13496b47c787f768b6634ec7cb68a4a3c370be74e45c94e`.
> Gerçek dosyalar **yalnızca** bu deponun [Releases](../../releases)
> sayfasından gelir; özetleri imzalı `SHA256SUMS.txt` içindedir
> ([VERIFYING.md](VERIFYING.md)). Sahte dosyayı çalıştırdıysan o bilgisayarı
> ele geçirilmiş say: ağdan ayır, tarat, ve parolalarını başka bir cihazdan
> değiştir.

---

## Ne olduğu

ProxyNet tek bir program değil, iki üründen oluşuyor. İkisi de aynı çekirdeği
paylaşıyor ama farklı sözler veriyor.

| | **ProxyChat** | **ProxyNull** |
| --- | --- | --- |
| Kime | Günlük kullanım, arkadaş grubu | Şifrelemenin öncelik olduğu durumlar |
| Durum | Çalışıyor. Son sürüm 1.13.0 ([indir](../../releases/latest)), ilk herkese açık sürüm 1.12.8; sesli sohbet ve ileri gizlilik (metin 1.9.0, ses 1.10.0) içinde | ProxyNull'ın henüz kodu yok; [sınırları](apps/proxynull/README.md) ve [protokol tasarımı](apps/proxynull/PROTOKOL.md) yazılı |
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
  sessizleştiren bir gürültü kapısı var. İki ayrı bilgisayar arasında
  denendi ve çalıştı. Yine de henüz **varsayılan olarak sunulmuyor**: canlı
  kullanım testi geçilmeden öyle anlatılmayacak.
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
- **Kuantuma karşı yalnızca kısmen dayanıklı.** 1.13.0'dan beri oturum
  anahtarı oda parolasına da bağlı; trafiği bugün kaydedip ileride X25519'u
  bir kuantum bilgisayarla kıran biri yine de parolayı bilmek zorunda. Zayıf
  bir parola bunu korumaz, ve tam dayanıklılık (ML-KEM ile hibrit anahtar
  değişimi) henüz yok: [THREAT_MODEL.md](THREAT_MODEL.md) 5.10.
- **Taşıma katmanı şifresiz.** Aktif bir saldırgan mesaj içeriğini
  sahteleyemez ama zarf paketlerini sahteleyebilir.
- **Dağıtılan dosyanın Authenticode imzası yok.** Windows SmartScreen uyarı
  verir. Onun yerine özet listesi GPG ile imzalı; nasıl kontrol edileceği
  [VERIFYING.md](VERIFYING.md) içinde.

Hepsinin ayrıntısı, neden böyle olduğu ve kapatılma sırası burada:
**[THREAT_MODEL.md](THREAT_MODEL.md)**

### Sırada ne var

**Sesli sohbet iki ayrı bilgisayar arasında denendi ve çalıştı.** Sıradaki iş
**canlı kullanım testi**. Sesli sohbetin varsayılan olarak sunulması ona
bağlı. Test henüz başlamadı ve bunun somut bir sebebi var: oturumlar, ürünün
kendi kayıt dosyasını yazmaya başlamasından sonra sayılıyor, o dosyayı şu an
yalnızca ses prototipi yazıyor. Kural böyle yazıldı ki "çalışıyor mu" diye
yapılan denemeler kötü sonuç olarak kayda geçmesin.

[THREAT_MODEL.md](THREAT_MODEL.md) 8. bölümdeki listede kalan iki madde
**bilerek ertelendi**, gerekçeleri orada yazılı: Authenticode imzası (8-B) ve
taşıma katmanı şifrelemesi (9).

#### Son kapananlar

**Kaydedilmiş trafik ve gelecekteki kuantum bilgisayar** (1.13.0). Oturum
anahtarı yalnızca X25519 değişiminden türüyordu; yani bugün kaydedilen trafik,
ileride X25519'u kırabilen bir kuantum bilgisayarla parola bilinmeden
açılabilirdi. Artık paroladan türeyen bir anahtar da oturum anahtarına
giriyor; metin ve ses birlikte korunuyor. Anahtarlar değiştiği için 1.13.0
**1.12.x ile şifreli konuşamaz**: odadaki herkesin güncellemesi gerekiyor.

**Ekranda görünen adres** (1.12.8). Ekranını yayınlayan ya da video çeken biri
IP adresini farkında olmadan sızdırıyordu: adres sohbet ekranındaki
"Bağlandı: …" satırında, Host'un paylaşacağı adres listesinde, bağlantı
ekranındaki IP alanında ve ağ listesinde açıkça duruyordu. Adresler artık
varsayılan olarak maskeli; **Adresi göster** basılı tutulunca görünüyor,
**Adresi kopyala** adresi göstermeden ve pano geçmişine girmeden kopyalıyor.
Bu yalnızca **ekranla** ilgili: arkadaşların bağlandıkları için adresi yine
biliyor, sunucuya bağlanan herkes de onu görüyor. Adresi ağdan gizlemek bu
sürümün işi değil.

**Bir güvenlik taraması** (1.12.7). Programa saldırmakla geçen bir gece on bir
açık çıkardı; hepsi kapandı ve her birinin eski kodda başarısız olan bir testi
var. En kötüleri parola gerektirmiyordu. Biri sesli sohbetten çıkınca Windows,
Host'un ses aktarımını **herkes için** durdurabiliyordu; tek bir uydurma paket
başka birinin bağlantısını koparabiliyordu; odaya girip hiç okumayan bir
istemci herkesin mesajlarını takılabiliyordu. Bir mesajın üstündeki ad, onu
şifreleyen anahtarla karşılaştırılmıyordu, yani yolda değiştirilebiliyordu;
artık uyuşmak zorunda. Kaydedilmiş bir mesajın yeniden gönderilmesi artık iki
kez görünmüyor. Resim etiketi içeren bir oda adı, Windows'ta programa bir ağ
adresi açtırıp IP'yi ve bir parola özetini verdirebiliyordu; adlar artık düz
metin. Şifreli bir odanın bildirimi de artık mesajı taşımıyor, çünkü Windows
bildirimleri diskte tutar. **Hâlâ açık olan** da yazılı: gönderen anahtarları
imza taşımıyor, yani parolayı bilen ve ayrıca paket enjekte edebilen biri hâlâ
başka bir üyenin adıyla yazabilir ([THREAT_MODEL.md](THREAT_MODEL.md) 5.4-B).

**Yeniden üretilebilir derleme ve tedarik zinciri** (1.12.3–1.12.4). Aynı
kaynaktan yapılan iki derleme farklı dosyalar üretiyordu; yani yayınlanan bir
özet "bu dosya bozulmamış" diyebiliyor ama "bu dosya söylediğiniz kaynaktan
çıkmış" diyemiyordu. Artık derleme bit bit yeniden üretilebilir ve farklı bir
klasörden derleyen bile aynı sonucu alıyor. Bağımlılıklar aralık değil, tam
sürüm ve wheel özetiyle kilitli — kurulum artık değiştirilmiş bir paketi
reddediyor. Ses kodeği başka bir projenin derlediği ikiliydi, şimdi Xiph'in
yayımladığı kaynaktan derleniyor. Özet listesi imzalanıyor; nasıl
doğrulanacağı ve **bu doğrulamanın sınırı** [VERIFYING.md](VERIFYING.md)
içinde.

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
katıl/ayrıl, katılımcı listesi, sustur, gürültü kapısı ve eşik ayarı var. Önce aynı
makinede iki kopyayla denendi; daha sonra iki ayrı bilgisayar arasında da
denendi ve çalıştı.

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

## Ne için, ne için değil

ProxyChat **birbirini tanıyan küçük gruplar** için: arkadaşlar, bir oyun
ekibi, bir aile. Sunucuyu gruptan biri kendi bilgisayarında açar; konuşmalar
başka bir şirketin sunucusunda durmaz.

Ne **değildir**:

- **Anonimlik aracı değil.** Bağlandığın sunucu IP adresini görür; sunucuyu
  açan kişi odada kimin, ne zaman olduğunu görür. Kim olduğunu gizlemez,
  yalnızca ne yazdığını korur.
- **Kimseden saklanmak için tasarlanmadı.** Kod açık, tasarımı ve sınırları
  yazılı; gizli bir dağıtımı ya da gizli bir kullanıcı kitlesi yok.
- **Merkezi bir hizmet değil.** Benim işlettiğim bir sunucu yok. Hiçbir
  kullanıcının adını, adresini ya da mesajını görmüyorum, tutmuyorum;
  program da bana hiçbir şey göndermiyor.
- **Yasa dışı kullanım için yapılmadı** ve böyle bir kullanımı desteklemiyorum.

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
| [VOICE_CHAT_PLAN.md](VOICE_CHAT_PLAN.md) | Sesli sohbetin tasarımı ve geliştirme günlüğü — topoloji, paket biçimi, şifreleme şeması, açık güvenlik soruları |
| [apps/proxynull/README.md](apps/proxynull/README.md) | ProxyNull'ın sınırları: zorunluluklar, yasaklar, ProxyChat'ten neden ayrı |
| [apps/proxynull/PROTOKOL.md](apps/proxynull/PROTOKOL.md) | ProxyNull'ın protokol tasarımı — buluşma kodu, Noise el sıkışması, doğrulama kodu, dolgu; kararı verilmiş ve verilmemiş maddeler ayrı işaretli |
| [listening/](listening/LISTENING.tr.md) | Kör dinleme testi: simüle ağ kesintileri konuşmada nasıl duyuluyor |
| [MANUAL.md](MANUAL.md) | Kurulum, kullanım ve kaynaktan derleme |
| [SECURITY.md](SECURITY.md) | Bir güvenlik açığını nasıl bildirirsin |
| [VERIFYING.md](VERIFYING.md) | İndirdiğiniz dosyayı nasıl doğrularsınız, kaynaktan nasıl yeniden derlersiniz, ve bu doğrulamanın sınırı |
| [THIRD-PARTY.md](THIRD-PARTY.md) | Pakete giren üçüncü parti bileşenler, lisansları ve kaynakları |
| [LICENSE](LICENSE) | GNU GPL v3 metni |

Her belgenin en üstünde Türkçe/English geçişi var; ayrıca listelenmedi.

Kaynak kodun kendisi: uygulama [apps/proxychat/](apps/proxychat/README.md), ortak
çekirdek `core/`, testler `tests/`; derleme betikleri kök klasörde.
Geliştirme ayrı bir depoda sürüyor; bu depo onun her sürümde güncellenen bir
**kopyası**, geçmişi değil. Ayrıntısı [VERIFYING.md](VERIFYING.md) içinde.

---

## Resmî kaynak ve kopyalar

Bu projenin tek resmî kaynağı **https://github.com/Anti-furry-cloud/ProxyNet**
adresidir. Başka bir yerde dolaşan bir ProxyChat/ProxyNet kopyası buradan
çıkmamış olabilir; indirmeden önce buraya bakın.

Projenin başka yerlerdeki tek resmî kanalları
**https://www.youtube.com/@ProxyNet_dev** ve
**https://www.tiktok.com/@proxynet.dev** adresleridir. Oralardan dosya
dağıtılmıyor: her indirme bu depodan, imzalı özet listesiyle birlikte gelir.
Benzer adla açılmış ve indirme sunan bir hesap — bir linkte, yorumda ya da
mesajda — bu proje değildir.

Proje **GNU GPL v3** ile yayınlanıyor. Bu, kopyalamayı yasaklamıyor — tam
tersi, serbest bırakıyor. Yalnızca üç şart var:

- Değiştirilmiş sürümü dağıtan, **kaynak kodunu da** vermek zorunda.
- Lisans ve telif notları korunur; kim yazdı sorusu silinemez.
- Türev iş de aynı lisansla dağıtılır.

Yani kodu alıp kapalı kaynak bir ürüne çevirmek ya da yazarını değiştirmek
lisans ihlalidir.

Sürümler [Releases](../../releases) sayfasında yayınlanıyor. Her sürümle
birlikte dosyaların SHA-256 özetleri ve o listenin **imzası** geliyor;
elinizdeki dosyanın özeti orada yazanla aynı değilse, o dosya benim
dağıttığım dosya değildir.

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

GitHub kullanmak istemiyorsan **proxynet.dev@protonmail.com** adresine yaz.
**Bir güvenlik açığı için herkese açık issue açma** — o adresi kullan ve ilk
mesajda yalnızca sorunun ne olduğunu söyle; ayrıntıyı nasıl ileteceğimizi
birlikte seçeriz.

Artık kod da burada, yani iddiaları koda bakarak sınayabilirsin. Bu bir
denetim yerine geçmez: kodu benden başka kimse baştan sona incelemedi.

**Kod okumadan da yardım edebilirsin:** birkaç kısa kaydı dinleyip
kesintilerin sana nasıl geldiğini söyle. Yönerge ve sorular:
**[listening/LISTENING.tr.md](listening/LISTENING.tr.md)**. Cevaplar
[Listening test](https://github.com/Anti-furry-cloud/ProxyNet/discussions/1) tartışmasına.

---

## Lisans

Proje GNU GPL v3 (ya da tercihe göre sonraki bir sürüm) altında; tam metin
[LICENSE](LICENSE) dosyasında. Bu belgeler de projenin parçası.
