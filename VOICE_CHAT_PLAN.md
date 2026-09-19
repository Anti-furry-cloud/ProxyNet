**Türkçe** · [English](VOICE_CHAT_PLAN.en.md)

# Sesli sohbet — tasarım planı

> **Yayın notu (2026-09-16):** Kaynak kodu henüz açık değil; metindeki dosya
> yolları (`core/voice_crypto.py` gibi) şu an görünmüyor ve kod açıldığında
> her iddianın nereden doğrulanacağını göstermek için bilerek bırakıldı.
> **Bu plan tamamlanmış bir tasarım değil.** Özellikle 3. bölümdeki şifreleme
> şeması hiçbir bağımsız incelemeden geçmedi. Erken yayınlanmasının sebebi
> tam olarak bu: üzerine daha fazla kod yazılmadan önce hatası görülsün.
> **Güncelleme (2026-09-16):** yayından sonra 3. bölümdeki şemada ciddi bir
> hata bulundu ve düzeltildi. Ne olduğu, nasıl bulunduğu ve düzeltmesi 3.
> bölümde açıkça yazılı.

Durum: **Faz 1 başladı, çekirdek yazıldı; prototip iki bilgisayar arasında
konuştu.** Ses paketi biçimi, şifreleme ve jitter tamponu `core/` altında
duruyor ve test ediliyor. Ses donanımı ve ağ artık var, ama yalnızca
dağıtılmayan bir komut satırı aracında; arayüz tarafı henüz yok. Faz 0'ın
karar kapısı **hâlâ açık**: v2 ölçümlerinin üçü yapıldı, ikisi eksik.

Hedef: sanal LAN (VPN) ya da yerel ağ üzerinde 2–5 kişilik bir arkadaş
grubunun konuşabilmesi. Discord'un yerini almak değil.

---

## 1. Neden mevcut protokol doğrudan kullanılamaz

Bugünkü taşıma katmanı satır sonuyla ayrılmış JSON üzerinden **TCP**. Ses için
iki sorunu var:

- **Head-of-line blocking.** TCP kayıp bir paketi yeniden gönderene kadar
  arkasındaki her şeyi bekletir. Metin için doğru, ses için felaket: gecikme
  birikir ve konuşma kesik kesik olur.
- **Geç gelen ses paketi çöptür.** Ses gerçek zamanlıdır; 300 ms geciken bir
  paketi doğru şekilde teslim etmenin bir değeri yoktur, atılması gerekir.
  TCP bunu yapamaz, UDP yapar.

Karar: **ses için UDP, sinyalleşme için mevcut TCP kanalı.** İkisi birlikte
çalışır; TCP kanalı zaten kim nerede sorusunun cevabını tutuyor.

Bu senaryoda bir avantaj var: sanal LAN kurulu olduğu için NAT geçişi
(STUN/TURN, ICE) gerekmiyor. Gerçek dünyada sesli sohbetin en pahalı kısmı
budur ve burada bedavaya geliyor. Bedeli, o sanal ağın kendisine bağımlı
olmak.

---

## 2. Mimari

### 2.1 Topoloji

| Seçenek | Artı | Eksi |
| --- | --- | --- |
| **Mesh** (herkes herkese) | Sunucu CPU'su sıfır, uçtan uca şifreleme doğal | N-1 kat yükleme bandı; 5 kişiden sonra sıkıntı |
| **Sunucuda karıştırma (mix)** | İstemci tek akış yollar | Sunucunun sesi **çözmesi** gerekir → uçtan uca şifreleme ölür |
| **Aktarma (SFU, karıştırmadan)** | İstemci tek akış yollar, sunucu şifreli veriyi görmeden iletir | Sunucuda bant genişliği, biraz daha karmaşık |

**Karar (2026-09-16): Host üzerinden aktarma.** Mesh, `voice_peers` paketiyle
odadaki herkesin IP adresini herkese dağıtıyordu; bu, [THREAT_MODEL.md](THREAT_MODEL.md)
ilke 3'e ("metadata da veridir") aykırı yeni bir sızıntıydı. Aktarmada Host
zaten gördüğü IP'leri görmeye devam eder, katılımcılar birbirininkini görmez.

Aktarmanın bedeli taşınabilir:

| | Mesh | Host üzerinden aktarma |
| --- | --- | --- |
| Tek yön gecikme | doğrudan | bir durak fazla, kabaca iki katı — "iyi" eşiği 150 ms |
| Host yükleme bandı (4 kişi, Opus) | 0 | ~0,45 Mbit/s (Host da konuşanlardan biriyse) — herkes sürekli gönderir (§4, sessizlikte susma kapalı); sıradan bir ev bağlantısının çok altında |
| IP sızıntısı | herkes herkesi görür | yalnızca Host görür (metin sohbetindeki durumla aynı) |
| Güvenlik duvarı izni | her katılımcıda | yalnızca Host'ta |

Karıştırma (mix) hâlâ **asla**: sunucunun sesi duyması bu projenin şifreleme
vaadini çöpe atar. Aktarma şifreli veriye dokunmaz.

Bu bir prototip kararı. Katılımcı sayısı büyürse ya da Host'un yükleme bandı
darlık yaparsa mesh yeniden değerlendirilir; paket biçimi ikisini de
destekliyor.

### 2.2 Sinyalleşme (mevcut TCP kanalı)

Yeni paket tipleri:

| Paket | Yön | İçerik |
| --- | --- | --- |
| `voice_join` | istemci → sunucu | UDP portu, oturum tuzu (16 bayt) |
| `voice_leave` | istemci → sunucu | — |
| `voice_peers` | sunucu → istemci | odadaki ses katılımcıları: `user`, `sender_id`, oturum tuzu — **IP yok** |

Sunucu ses verisine hiç dokunmaz; yalnızca kimin sesli sohbette olduğunu ve
paketleri kime ileteceğini bilir. **Kimin konuştuğunu ya da mikrofonunu
kapattığını bilmez** (2026-09-19): ilk taslaktaki `voice_state` paketi
(`muted`, `speaking`) kaldırıldı. Gerekçe §4'teki Opus araştırmasında: ses
akışı konuşma olsun olmasın sabit hızda akıyor, bu bilgiyi sunucuya ayrıca
vermek o önlemi boşa çıkarırdı.

### 2.3 Ses paketi biçimi (UDP)

JSON değil, ikili. 20 ms'lik çerçeveler. Yazıldı: `core/voice_packet.py`.

```
[ 1 bayt  ] sürüm
[ 1 bayt  ] tip
[ 4 bayt  ] gönderen kimliği          ] açık metin, aynı zamanda
[ 8 bayt  ] sıra numarası             ] ek kimlik doğrulama verisi (AAD)
[ 4 bayt  ] zaman damgası (ms)        ]
[ N bayt  ] şifreli ses + 16 baytlık GCM etiketi
```

Başlık 18 bayt. İlk taslaktan iki farkı var:

- **Nonce taşınmıyor.** İki taraf da onu başlıktan üretiyor (aşağıda §3), bu
  da paket başına 12 bayt kazandırıyor.
- **Sıra numarası 8 bayt.** 4 bayt, başa sardığında oturum anahtarını
  yenilemeyi gerektiriyordu; 8 bayt saniyede 50 paketle pratikte hiç sarmaz ve
  o mekanizmaya gerek kalmaz.

Başlığın açık metin olması aktarma kararının gereği: Host paketi kimin
gönderdiğini okuyup yönlendirebilmeli. Başlık aynı zamanda AAD olduğu için
Host onu **değiştiremez** — değiştirirse alıcının çözme işlemi başarısız olur.
Toplam şifreleme yükü çerçeve başına 16 bayt (yalnızca GCM etiketi).

---

## 3. Şifreleme — mevcut oda parolasını kullan, ama Fernet ile değil

Ses de oda parolasından türetilen anahtarla şifrelenmeli, yoksa metin şifreli
ses açık olur ve vaat tutarsız hale gelir.

Ancak metin tarafında kullanılan **Fernet ses için yanlış araç**:

- Token başına ~57 bayt sabit yük **artı** base64 (%33 şişme). 20 ms'lik
  çerçeve 640 baytken bu kabul edilemez.
- Fernet zaman damgası taşır ve yeniden oynatma korumasını çağırana bırakır.

Karar: **AES-GCM, ve her gönderenin her ses oturumu için ayrı bir anahtar.**
Yazıldı: `core/voice_crypto.py`, şema etiketi `aesgcm-hkdf-v2`.

```
oda parolası ──Argon2id──▶ ana anahtar ──HKDF──▶ ses anahtarı
ses anahtarı + oturum tuzu + gönderen kimliği ──HKDF──▶ oturum anahtarı
```

- **Ana anahtar** metin tarafıyla ortak: metin anahtarı onun base64 hâli, bir
  test bunu doğruluyor. 1.7.0'dan beri ana anahtar Argon2id ile türüyor.
- **Ses anahtarı** `HKDF(info=b"proxynet-voice-v1")` ile türer. Metin
  anahtarıyla aynı değildir ve onunla doğrudan hiçbir şey şifrelenmez.
- **Oturum tuzu:** her gönderen sesli sohbete her katılışında 16 baytlık
  rastgele bir tuz üretir ve `voice_join` ile bildirir. Tuz gizli değildir;
  Host da görür, ama parola olmadan anahtarı vermez.
- **Oturum anahtarı:** `HKDF(salt=oturum tuzu, info=b"proxynet-voice-session-v1"
  + gönderen kimliği)`. Paketler bununla şifrelenir.
- **Nonce** = 4 bayt gönderen kimliği + 8 bayt sıra numarası. Telde
  taşınmıyor, iki taraf da başlıktan üretiyor.
- Gönderen tarafta sıra numarası **kesin artan** olmak zorunda. Aynı ya da daha
  küçük bir numarayla mühürleme denemesi sessizce geçilmez, hata verir.
- **Yeniden oynatma koruması:** 64 paketlik kayan pencere (RFC 3711 yaklaşımı),
  gönderen başına ayrı. Aynı tuzla tekrar gelen bir kayıt pencereyi
  sıfırlamaz; sıfırlasaydı tekrarlanan bir `voice_peers` paketi eski
  paketlerin yeniden kabul edilmesine kapı açardı.
- Kendi kimliğimiz **başka bir tuzla** kaydedilmeye çalışılırsa hata verilir.
  Bu, Host'un aynı kimliği iki kişiye verdiği anlamına gelir.
- Parolasız odalarda ses de şifrelenmez; metin tarafındaki tercihin aynısı.
  Tel biçimi ve oturum kuralları değişmez.

### Bulunan hata: oturumlar arası nonce tekrarı (2026-09-16, düzeltildi)

İlk sürümde (`aesgcm-hkdf-v1`) oturum anahtarı yoktu; her paket doğrudan ses
anahtarıyla şifreleniyordu. Ses anahtarı oda adı ve paroladan türediği için
**hiç değişmiyor.** Sonuç:

1. Bugün Ayşe `sender_id = 1` alır, sıra numarası 0'dan sayar.
2. Yarın Host yeniden başlar; aynı oda, aynı parola. Ayşe yine `sender_id = 1`
   alır, sıra yine 0'dan başlar.
3. **Aynı anahtar, aynı nonce.** AES-GCM'de bu, iki çerçevenin şifresiz
   hâllerinin XOR'unu ele verir. Çerçevelerden biri tahmin edilebilirse
   (konuşmada sık görülen sessizlik gibi) diğeri doğrudan okunur. Ayrıca
   kimlik doğrulama anahtarı sızar ve sahte paket üretilebilir.

Aynı şey tek bir oturum içinde de oluyordu: odadan çıkıp giren birinin sıra
numarası sıfırdan başlıyordu ve bu belgenin ilk hâli bunu normal akış olarak
anlatıyordu. "Gönderen kimliği oturum içinde benzersiz olmalı" şartı, oturumlar
arasını korumuyordu.

- **Nasıl bulundu:** Discord'un uçtan uca ses şifrelemesi DAVE incelenirken.
  DAVE her gönderene ayrı anahtar türetiyor ve üyelik değiştikçe anahtarları
  yeniliyor; bizim tasarımda bunun karşılığı yoktu.
- **Doğrulama:** düzeltmeden önce senaryo bir betikle denendi. Önceki oturumun
  bir çerçevesindeki metin, sonraki oturumun sessizlik çerçevesi yardımıyla
  geri çıkarıldı. Düzeltmeden sonra aynı betik anlamsız bayt çıkarıyor.
- **Etkisi:** ses kodu henüz hiçbir yerde ağa bağlı çalışmıyor; gerçek bir
  trafik etkilenmedi. Ama tasarım bu belgede yayınlanmıştı.
- **Düzeltme:** yukarıdaki oturum tuzu. Nonce tekrarı için artık iki oturumun
  aynı 128 bitlik tuzu çekmesi gerekir. Gizlilik gönderen kimliğinin
  benzersizliğine bağlı değil ve önceki bir oturumdan kaydedilmiş paket yeni
  oturumun anahtarıyla çözülemez.
- **Testler:** `tests/test_voice.py` içinde `OturumAyrimiTests`, saldırı
  senaryosunun kendisi dahil.

**Bu tasarımın çözmediği:** aynı oda parolasını bilen herkes herhangi bir
gönderenin oturum anahtarını türetebilir, yani oda üyeleri birbirinin adına
paket üretebilir. Metin tarafında da durum aynı. DAVE bunu MLS ile kimlik
doğrulamalı grup anahtar değişimi yaparak çözüyor; bu, projenin şu anki
kapsamının dışında.

**Uyarı:** bu şema tek kişi tarafından tasarlandı ve dışarıdan incelenmedi.
İlk sürümündeki hata bunun neden önemli olduğunu gösteriyor. Bir hata daha
görürseniz duymak isterim.

---

## 4. Ses yakalama ve çalma

Qt'nin ses arayüzleri (`QAudioSource` / `QAudioSink`) kullanılacak. Mevcut
arayüz kütüphanesiyle birlikte geliyor, yeni bağımlılık gerekmiyor.

**Dikkat — paketlemeyi etkiler:** Qt'nin çokluortam modülleri şu an
uygulamanın paketine bilerek **dahil edilmiyor** (exe boyutunu büyük ölçüde
küçülten bir tercihin parçası). Sesli sohbet gelirse bunlar geri alınmalı ve
boyut artışı **ölçülmeli** — tahmin edilmemeli.

### Kodek

| Aşama | Kodek | Bant genişliği (mono) | Neden |
| --- | --- | --- | --- |
| Prototip | G.711 µ-law 16 kHz | ~128 kbit/s | Yeni ikili bağımlılık yok, hattı kanıtlar |
| Sürüm | Opus, sabit bit hızı | 24 kbit/s | ~4 kat daha küçük datagram, konuşmada daha iyi kalite, kayıp paketi geri kuran FEC |

Prototip dışarıdan kütüphane gerektirmeyen bir kodekle yapıldı; böylece
kodek sorunlarıyla ağ sorunları birbirine karışmıyor. İlk deneme 8 kHz ile
yapıldı ve telefon kalitesinde duyuldu, 16 kHz'e çıkarıldı. µ-law geçici bir
çözüm: dayandığı standart kütüphane modülü (`audioop`) Python 3.13'te
kaldırıldı.

### Opus araştırması (2026-09-18)

Denemeler, dinleme testindeki kamu malı kayıtla yapıldı; kayıp gerçek bir
hattan değil, rastgele üretildi. Aşağıdakiler karar önerisi, kesinleşmedi.

- **Bağlama: doğrudan libopus.** Opus'u çalıştıran hazır Python paketleri
  FFmpeg'in tamamını, video kodekleri dahil onlarca MB getiriyor. `libopus`
  tek başına küçük bir kütüphane ve `ctypes` ile doğrudan çağrılabiliyor;
  ağdan gelen, güvenilmeyen paketi çözen kod yalnızca libopus olur. Lisansı
  BSD 3 maddedir, projenin GPLv3 lisansıyla uyumludur.
- **Sabit bit hızı (CBR), sessizlikte susma (DTX) kapalı.** Değişken bit
  hızında paket boyu sese göre değişiyor ve sessizliği açıkça gösteriyor.
  Şifreli VoIP'te paket boylarından söylenen sözlerin kısmen
  çıkarılabildiği yayımlanmış bir saldırıdır (Wright ve ark., 2008). CBR'de
  her paket aynı boyda çıktı. DTX aynı sebeple kapalı: sessizlikte paket
  göndermemek kimin ne zaman konuştuğunu ağa söyler. Bedeli, herkesin
  konuşmasa da sürekli bant kullanması (§2.1).
- **FEC çalışıyor.** Kayıp çerçeve bir sonraki paketin içindeki yedekten
  kurulabiliyor; bunun için tampon en az bir çerçeve önde durmalı.
- **Tedarik zinciri.** Dağıtılacak kütüphane, Xiph'in yayımladığı kaynak
  arşivinden kendimiz derlenmeli; başka bir projenin derlediği ikiliyi
  dağıtmak, o projenin derleme hattına güvenmek demek.

| Kodek | Çerçeve (20 ms) | Datagram (başlık + GCM etiketi dahil) |
| --- | --- | --- |
| µ-law 16 kHz (prototip) | 320 bayt | 354 bayt |
| Opus 24 kbit/s CBR | 60 bayt | 94 bayt |
| Opus 16 kbit/s CBR | 40 bayt | 74 bayt |

Açık: 24 mü 16 kbit/s mi (dinleyerek karar verilecek); 16 kHz'de mi
kalınacak, 48 kHz'e mi çıkılacak; FEC'in gerçek hatta, art arda gelen
kayıplarda ne kazandırdığı. Jitter tamponunun kodu Faz 0 v2 kapısı
kapanana kadar değişmeyeceği için Opus önce yalnızca prototipe girecek.

---

## 5. Jitter buffer — atlanamaz

UDP paketleri sırasız, düzensiz aralıklarla ve bazıları hiç gelmeden varır.
Doğrudan hoparlöre yazmak cırtlak ses üretir.

Yazıldı: `core/voice_jitter.py`. İçinde saat, soket ya da Qt yok; girdi sıra
numarası ve bayt dizisi, çıktı çerçeve sırası. Ses cihazı tükettikçe
`pop()` çağrılır (ortalama 20 ms'de bir), `None` dönerse o çerçevede
sessizlik ya da kayıp gizleme çalar. Çağrının hızını zamanlayıcı değil ses
kartı belirliyor; gerekçesi prototip bölümünde ölçüldü.

- Hedef tampon **60 ms**. Uyarlanabilir hâli henüz yok.
- Sıra numarasına göre yeniden sıralama.
- Tamponun gerisinde kalan paket atılır.
- Kayıp çerçeve yerine sessizlik. Sönümlenmiş tekrar henüz yok.
- **Tampon tamamen boşalırsa baştan doldurmaya döner.** Boş tamponu tüketmeye
  devam etmek sıra sayacını ileri kaçırır ve karşı taraf yeniden konuşmaya
  başladığında her çerçeve "geç kalmış" sayılırdı.
- Gönderen yeniden başlarsa (sıra numarası her iki yönde de anlamsız uzaklıkta)
  akış sıfırlanır.

### Bulunan zayıflık: gecikme birikmesi (2026-09-16, düzeltildi)

Tamponun ilk hâli, bir gecikme sıçramasından sonra biriken çerçeveleri olduğu
gibi çalıyordu. Sıçrama sırasında tampon boşalıp yeniden dolduğunda en eski
çerçeveden başlıyor ve hedefin üstündeki fazlayı eritecek bir mekanizma
olmadığı için **her sıçrama gecikmeye kalıcı olarak ekleniyordu.** O günkü 54
birim testin hiçbiri bunu yakalamadı: testler tek tek davranışları
doğruluyordu, uzun bir akıştaki birikimi değil.

**Nasıl bulundu:** `tools/ses_simulasyonu.py` bir konuşma kaydını, gerçek bir
ölçümün istatistiklerine uydurulmuş sentetik bir ağ izinden (~%1,3 kayıp, arada
100–280 ms'lik takılmalar) ve bu tampondan geçirip `.wav` olarak yazıyor.
Gecikme saniye saniye izlendiğinde 80 ms'den başlayıp her takılmada yükseldiği
ve 300 ms'de kaldığı görüldü.

**Düzeltme — yetişme:** tampon hedefin 40 ms üstüne çıkınca fazlayı azar azar
eritir, hedefe inince durur.

- Sıradaki yuva zaten boşsa (kayıp paket) orada sessizlik çalınmaz, atlanır.
- Gerçek bir çerçeve en fazla 5 çerçevede bir ve ancak tampondaki boş yuvalar
  fazlayı karşılamıyorsa atılır. 200 ms'lik birikme ~1 saniyede erir; kayıp tek
  bir uzun boşluk yerine 20 ms'lik parçalara dağılır.
- WebRTC'nin NetEq'i aynı işi çözülmüş sesi perdeyi bozmadan sıkıştırarak
  yapıyor. Bu tampon şifreli ya da kodlanmış baytlarla çalıştığı için o yol bu
  katmanda kapalı.

**Bedeli, dürüst hâliyle.** Aynı ağ izinde, üç farklı rastgele tohumun
ortalaması, 43 saniyelik konuşma:

| | Yetişme yok (ilk hâl) | Yetişme (pay 40 ms, her 5 çerçeve) |
| --- | --- | --- |
| Gecikme ortancası (ağ + tampon) | 280 ms | 80 ms |
| 150 ms'yi aşan süre | 35,9 sn | 3,2 sn |
| Konuşma içindeki boşluk | 0,89 sn | 1,95 sn |
| Yetişmek için atılan konuşma | 0 | 1,25 sn |

İlk hâl gecikmeyi biriktirdiği için farkında olmadan 300 ms'lik büyük bir
tampona dönüşüyor ve sonraki takılmaları boşluksuz yutuyordu. Yeni tampon
hedefe döndüğü için her takılmada boşalıyor. Payı büyütmek boşlukları biraz
azaltıyor ama gecikmeyi geri getiriyor (pay 100 ms, her 10 çerçeve: ortanca
127 ms, boşluk 1,56 sn). Hiçbir ayar ikisini birden kazandırmıyor; hat
gerçekten takılıyorsa bu katmanda ya beklenir ya atlanır. Konuşmada gecikme
kesintiden daha yıkıcı olduğu için varsayılan düşük gecikme tarafında.

Kalan boşlukları azaltacak olanlar bu katmanın dışında: sık takılan hatta
hedefi geçici olarak büyütüp hat sakinleşince küçülten **uyarlanabilir hedef**,
çözülmüş seste **zaman sıkıştırma** (konuşma atmak yerine fark edilmeyecek
hızlandırma) ve tek tük kayıp paketleri geri kuran **Opus FEC**.

---

## 6. Arayüz

- Sol kenar çubuğunda "Sesli Sohbet" bölümü, katıl/ayrıl düğmesi.
- Katılanların listesi; konuşan kişinin adı vurgulanır (basit RMS eşiği; her
  alıcı çözdüğü sesten kendisi hesaplar, ağdan böyle bir bilgi gelmez).
- Sustur ve bas-konuş, gönderilen akışı durdurmaz: tuşa basılmadığında ya da
  mikrofon kapalıyken de sessizlik çerçevesi gider, dışarıdan fark görünmez.
- Sustur (mikrofon) ve sağırlaştır (hoparlör) düğmeleri.
- **Bas-konuş (push-to-talk)** seçeneği — varsayılan açık olsun.

### Yankı sorunu, dürüst hâliyle

Qt'nin akustik yankı bastırma (AEC) desteği yok. Hoparlörden çıkan ses
mikrofona geri girer ve karşı taraf kendini duyar. Gerçek çözüm WebRTC
seviyesinde iş ve bu projenin ölçeğinin çok dışında.

Gerçekçi yaklaşım: **kulaklık önerilir** ve bas-konuş varsayılan gelir.
Küçük projelerin tamamı bunu böyle çözer; belgede açıkça yazılmalı.

---

## 7. Test edilebilirlik

Mevcut test yapısı, ses eklendiğinde çürümemeli. Bunun tek yolu **ses
donanımını arayüzün arkasına almak**:

- `AudioDevice` protokolü: `read_frame()` / `write_frame()`. Gerçek uygulaması
  Qt, testlerde sahte uygulama (sentetik dalga). **Henüz yazılmadı.**
- ✅ Jitter buffer birim testleri: sırasız, tekrar eden ve kayıp paketler ver,
  çıkan çerçeve sırasını doğrula. Bir gecikme sıçramasından sonra
  gecikmenin hedefe geri indiği ve yetişme hızının sınırlı kaldığı da.
- ✅ Kripto testleri: AES-GCM gidiş-dönüş, yanlış parola çözemez, tekrar eden
  paket reddedilir, başlık kurcalanırsa çözülemez, aynı kimlikle iki oturum
  aynı anahtar akışını üretmez (§3'teki hatanın regresyon testi).
- ✅ Uçtan uca test: sentetik ses → şifrele → bozuk bir ağ (kayıp, sıra
  bozulması, kopya paket) → çöz → tampon → doğru çerçeve sırası.

Hepsi `tests/test_voice.py` içinde, 76 test. Ses donanımı, soket ya da Qt
kullanmıyorlar; CI'da çalışırlar. Ses donanımı gerektiren hiçbir test CI'da
çalışmamalı.

---

## 8. Fazlar

| Faz | İş | Çıktı |
| --- | --- | --- |
| **0. Ölçüm** | UDP gecikme, jitter ve kayıp ölçen küçük bir araç | **Karar kapısı**: rakamlar kötüyse plan burada durur — v1: KÖTÜ; v2: beş ölçümün üçü yapıldı, ikisi bekliyor |
| **1a. Çekirdek** ✅ | Paket biçimi, AES-GCM + HKDF, jitter tamponu, testler | Ses donanımı olmadan çalışan, test edilmiş çekirdek |
| **1b. İskelet** | Sinyalleşme paketleri, UDP soketi, Host'ta aktarma, µ-law 16 kHz, tek yönlü | Bir kişi konuşur, diğeri duyar |
| **2. Çift yönlü** | Ses cihazı arayüzü, Qt entegrasyonu, iki yön | 2 kişi karşılıklı konuşur |
| **3. Kullanılabilirlik** | Opus, bas-konuş, konuşma göstergesi, sustur | 4 kişi kullanabilir |
| **4. Paketleme** | Qt ses modüllerini pakete geri al, boyutu ölç, UDP güvenlik duvarı kuralı, belgeler | Dağıtılabilir sürüm |

Faz 1a'nın Faz 0'ı beklememesinin sebebi: yazılan üç modülün hiçbiri ağ
ölçümüne bağlı değil. Ölçüm kötü çıkarsa duracak olan 1b ve sonrası.

**Faz 0 ciddiye alınmalı.** Sanal LAN yazılımları bazı bağlantılarda eşler
arası doğrudan tünel kuramaz ve trafiği kendi aktarma sunucularından geçirir;
bu durumda gecikme sesli sohbet için yeterli olmayabilir. Bunu ölçmeden Faz
1b'ye başlamak, en kötü ihtimalle haftalarca emeğin kullanılamaz çıkması
demektir.

### Faz 0 ölçüm aracı (v1)

> Bu alt bölüm v1'i anlatıyor. v1 kurallarıyla yapılan ölçümler KÖTÜ çıktı;
> geçerli kurallar aşağıda, **Faz 0 v2** başlığında.

`tools/ses_olcum.py` — yalnızca standart kütüphane kullanır, bağımsız
çalışır.

- Bir taraf **Bekle**, diğer taraf **Ölç** seçer ve karşı tarafın adresini
  yazar. Ölçen tarafta güvenlik duvarı izni gerekmez; bekleyen tarafta bir UDP
  portu için izin istenir.
- 20 ms arayla (bir ses çerçevesi) iki ölçüm yapılır, her biri 30 saniye:
  Opus benzeri ~120 baytlık paketler ve ham PCM boyutunda ~700 baytlık
  paketler.
- Ölçülenler: gidiş-dönüş gecikmesi (ortanca, %95, en yüksek), **iki yönde
  ayrı ayrı** kayıp, sırası bozulan paket, RFC 3550 jitter'ı ve 60 ms'lik
  tampona yetişemeyen paket oranı. İki bilgisayarın saati farklı olduğu için
  tek yön ölçümler saat farkından etkilenmeyecek şekilde hesaplanır.
- Sonuç ekrana yazılır ve bir metin dosyasına kaydedilir. Dosyada IP adresi
  yoktur.

Karar eşikleri (tek yön gecikme tahmini = gidiş-dönüş ortancası / 2; etkin
kayıp = kayıp + tampona yetişemeyen, kötü olan yön):

| Karar | Tek yön gecikme | Etkin kayıp |
| --- | --- | --- |
| **İyi** | ≤ 150 ms | ≤ %1 |
| **Kabul edilebilir** | ≤ 300 ms | ≤ %3 |
| **Kötü** — plan burada durur | daha fazlası | daha fazlası |

Gecikme eşikleri ITU-T G.114'e dayanır. **Karar Opus ölçümüne göre verilir**;
PCM ölçümü yalnızca prototip aşamasının çalışıp çalışmayacağını gösterir.

Bilinen sınırlar: 60 ms sabit tampon, planlanan uyarlanabilir tampondan
katıdır (sonuç kötümser çıkabilir); en hızlı paketin transit süresi taban
alınır; ölçüm tek bir anın fotoğrafıdır, farklı saatlerde tekrarlanmalıdır.

### Faz 0 v2 — ölçümden önce yazılan kurallar (2026-09-17)

**Bu bölüm, v2 ölçümlerinden önce yazıldı ve commit'lendi; commit tarihi bunun
kanıtı.** Aşağıdaki kurallar, ölçüm sonuçları görüldükten sonra
değiştirilmeyecek.

#### v1'in sonucu

v1 kurallarıyla iki ayrı internet bağlantısı arasında üç ölçüm yapıldı, üçü de
**KÖTÜ** çıktı. Gecikme sorun değildi; sebep kayıp ve anlık takılmalardı. Bu
sonuç kayıtta kalır ve yeniden yorumlanmaz. v2 kararına da katılmaz; zaten v1
paket paket kayıt tutmadığı için katılamaz.

#### Neden v2, ve bunun zayıf yanı

v1'in sorusu şuydu: sabit 60 ms tampon ve kayıp telafisi olmadan bu hat sesi
taşır mı? Plan en başından yetişen tampon ve kayıp gizleme öngörüyordu, v1'in
kötümser çıkabileceği de ölçümden önce yazılmıştı (yukarıda, "Bilinen
sınırlar"). **Ama v2'yi yazma isteği kötü sonucu gördükten sonra doğdu.** Bunu
saklamıyorum; aşağıdaki kurallar bu zayıflığın kararı çarpıtmasını engellemek
için var.

#### Yöntem

1. Ölçüm aracı (`tools/ses_olcum.py`, kayıt sürümü 2) iki yöndeki **her
   paketin** gönderilme ve varış anını kaydeder. v1 aracıyla karışmasın diye
   protokol sürümü değişti; iki sürüm birbirinin paketini tanımaz.
2. Karar araçta verilmez. `tools/ses_degerlendir.py` kaydı **gerçek jitter
   tamponu kodundan** (`core/voice_jitter.py`) geçirir ve ses cihazının her 20
   ms'de bir çerçeve istediğini taklit eder.
3. Bu oynatma döngüsü, simülasyon aracının ses ürettiği döngüyle **aynı
   fonksiyon.** Simülasyon bu fonksiyona geçirildiğinde daha önce üretilmiş ses
   dosyalarının hepsi bayt bayt aynı yeniden üretildi.
4. İki bilgisayarın saati farklı olduğu için en hızlı paketin tek yön süresi,
   gidiş-dönüşün en kısasının yarısı kabul edilir. Gönderenin zamanlama sapması
   dışarıda bırakılır; gerçek bir ses uygulamasında çerçeveleri ses kartının
   saati düzenli üretir.
5. **FEC'e kredi verilmez:** eşiğin dayandığı dinlemede FEC yoktu.

#### Ölçütler ve eşikler

- **Kesinti oranı:** konuşma sırasında çalınamayan çerçevelerin payı: boşluk,
  yetişmek için atılan çerçeve ve atlanan boş yuva.
- **Ağızdan kulağa gecikme, %95:** ağ + tampon + 40 ms ses cihazı payı. v1
  ortanca kullanıyordu; %95 daha katı ve tamponun gecikme biriktirmesini
  gizlemez.
- Her ölçümde **iki yönün kötüsü** sayılır. Karar, v1'deki gibi Opus benzeri
  küçük paket fazından verilir.

| Karar | Kesinti oranı | Ağızdan kulağa %95 |
| --- | --- | --- |
| **İyi** | ≤ %1 | ≤ 150 ms |
| **Kabul edilebilir** | ≤ %5,8 | ≤ 300 ms |
| **Kötü** | daha fazlası | daha fazlası |

İyi eşikleri v1 ile aynı. Gecikme eşikleri ITU-T G.114'e dayanıyor.

**Kabul edilebilir kesinti eşiği (%5,8) bir dinlemeye dayanıyor.** Ürün sahibi,
16 Eylül'deki bir ölçümün istatistiklerine uydurulmuş sentetik bir ağ izinden
yetişen tampon ve sönümlü tekrarla üretilmiş bir konuşma kaydını dinledi, ve
kesintileri Discord'da ara sıra yaşanan kesintilerle aynı seviyede buldu. Eşik,
o kaydın bu değerlendirmeyle ölçülen kesinti oranı: 2137 çerçevede 75 boşluk,
46 atılan, 3 atlanan boş yuva. Referans kaydın SHA-256'sı `060f1138…0e39`; eşiği
yeniden hesaplayan bir test var (`tests/test_ses_degerlendir.py`).

Bu eşiğin zayıf yanları:

- tek dinleyici;
- robotik bir seslendirici sesi;
- gecikme tek başına dinlenen kayıtta duyulmaz, bu yüzden gecikme eşiği sayı
  olarak kaldı;
- yargı v1 sonuçları görüldükten **sonra** verildi.

#### Kaç ölçüm, hangisi sayılır

- Ölçümler tarih sırasına göre sayılır. Bir takvim gününden **en fazla 3** ölçüm
  sayılır ve **ilk 5** sayılan ölçüm kararı verir. Sonrakiler yok sayılır: iyi
  bir sonuç gelene kadar ölçmeye devam etmek işe yaramaz.
- **En kötü ölçüm dışarıda bırakılır;** kalan dördün en kötüsü kapı kararıdır.
- Araç her ölçümden önce kısa bir koşul listesi sorar (indirme, bağlantı türü,
  ekran paylaşımı). Cevaplar sonuç görülmeden kayda girer, ama yalnızca not
  içindir.
- **Sonradan ölçüm çıkarılmaz.** Bozucu bir durum sonradan anlaşılsa bile ölçüm
  sayılır. Tek bir sapmaya karşı tolerans "en kötüsü hariç" kuralında.
- Karşı tarafın paket kaydı alınamayan ölçüm **KÖTÜ** sayılır, tekrar ölçmek
  için bahane olmasın diye.
- Kablosuz bağlantı serbest; hedef kitle çoğunlukla kablosuz ağda.

#### Önceden bağlanan kararlar

- **İyi ya da kabul edilebilir:** Faz 1b başlar.
- **Kötü: v3 yazılmaz.** Bu kurallar bir daha değiştirilmez. İzin verilen tek
  adım altyapıyı değiştirmek (başka VPN, kablo, başka karşı taraf) ve **aynı v2
  kurallarıyla** yeniden ölçmek.
- Tampon kodu v2 kayıtları görüldükten sonra değiştirilirse, **aynı kayıtlarla
  yeniden değerlendirilmez;** yeni ölçüm gerekir. Aksi hâlde kod ölçülen veriye
  uydurulmuş olurdu.

#### Durum: ilk gün (2026-09-17)

Sayılan üç ölçüm yapıldı ve üçü de **kabul edilebilir** eşiklerin içinde
kaldı. Kalan iki ölçüm başka bir güne kalıyor; bir günden en fazla üç ölçüm
sayılıyor. Kapı kararı beşi tamamlanınca verilecek: en kötü ölçüm dışarıda
bırakılıp kalan dördün en kötüsüne bakılacak. Sayılar burada yayınlanmıyor;
karar açıklandığında gerekçesi de yazılacak.

---

### Sesli sohbet prototipi (2026-09-17)

Sesli sohbetin uçtan uca yolu ilk kez gerçek bir hat üzerinde denendi:
mikrofon → 20 ms çerçeve → şifreleme → UDP → jitter tamponu → kayıp gizleme →
hoparlör. İki ayrı internet bağlantısındaki iki bilgisayar arasında **canlı
konuşma yapıldı ve ses anlaşılır şekilde geldi.**

Prototip, dağıtılan programın parçası değil: ayrı bir komut satırı aracı
olarak duruyor ve arayüze bağlı değil. Amacı ağ tarafını denemek.

Denemede iki hata bulundu, ikisi de düzeltildi:

- **Hiçbir paket alınmıyordu.** Ağ soketi, Qt'nin uygulama nesnesinden önce
  kuruluyordu; bu sırada "veri geldi" bildirimi hiç bağlanmıyor. Program
  gönderiyor ama hiçbir şey almıyordu. İlk testler bunu yakalamamıştı, çünkü
  uygulama nesnesini kendileri önceden kuruyorlardı; yeni test ayrı bir
  süreçte çalışıyor.
- **Gecikme boşu boşuna büyüyordu.** Çalma 20 ms'lik bir zamanlayıcıya
  bağlıydı. Windows'ta zamanlayıcı çözünürlüğü ~15,6 ms olduğu için çalma,
  mikrofonun üretiminden yavaş kalıyor ve fark tamponda birikiyordu: hedef
  60 ms olmasına rağmen tampon 80–100 ms'te duruyordu. Kayıp yoktu, yalnızca
  gecikme. Çekme kipi (`QIODevice`) de denendi ve daha kötü çıktı: ses kartı
  tek seferde birkaç çerçeve istediği için tampon 0 ile 460 ms arasında
  salındı. Seçilen yol, kartın boş yerine bakıp her seferinde en fazla bir
  çerçeve yazmak; saati ses kartı belirliyor. Yerel ölçüm: tampon 40 ms'te
  sabit, 30 saniyede sıfır boşalma ve sıfır atılan çerçeve.

Jitter tamponunun kodu **kasten değiştirilmedi.** Faz 0 v2 kurallarına göre
o kod ölçüm kayıtları görüldükten sonra değiştirilirse aynı kayıtlar yeniden
değerlendirilemez; kayıp gizleme bu yüzden tamponun içinde değil prototipte.

### Gerçek kullanım denemesi (2026-09-18) — kapıya sayılmaz

Prototip, iki ayrı internet bağlantısı arasında bir saati aşkın, kesintisiz
ve şifreli bir gerçek konuşmada kullanıldı. Konuşanların izlenimi: "Discord
kullanıyormuş gibi."

- Faz 0 v2 tanımıyla kesinti oranı iki yönde de %1,5'in altında kaldı.
- Tampon birkaç kısa sıçramadan ve bir kez birkaç saniyelik bir takılmadan
  sonra her seferinde kendiliğinden toparlandı.
- O takılmada gelmeyen çerçeveler **kayıp sayılmadı**, çünkü sıra
  numarasında boşluk yoktu. Gönderen tarafın takılması (mikrofonun çerçeve
  üretmemesi) prototipin bugünkü sayaçlarında görünmüyor; bir sonraki
  sürümde ayrıca sayılacak.

**Neden kapıya sayılmıyor:** Faz 0 v2 ölçüm aracıyla ve Opus benzeri küçük
paketlerle ölçülür, burada 354 baytlık µ-law paketi vardı; ağızdan kulağa
%95 hiç ölçülmedi; ve sonucu gördükten sonra hangi verinin sayılacağını
seçmek, ön kaydın önlemeye çalıştığı hatanın kendisi. Bu oturum ayrı bir
kanıt olarak duruyor.

---

## 9. Açık güvenlik soruları

Bunlar 1b'ye başlamadan çözülmesi gereken, bilinen ve tanımlı problemler.
Buraya yazılmalarının sebebi, çözülmüş gibi davranılmasını engellemek.

- **`sender_id` nasıl atanacak?** Host atamalı ve bir oturum içinde aynı
  kimliği iki kişiye vermemeli: kimlik, paketin kime yönlendirileceğini ve
  hangi tekrar penceresine düşeceğini belirliyor. **Gizlilik artık buna
  bağlı değil** (§3'teki oturum tuzu), ama bir çakışma sesleri karıştırır.
  İstemci kendi kimliğinin başka bir tuzla kaydedildiğini fark edip hata
  veriyor; Host tarafındaki atama kuralı 1b'de yazılacak.
- **Aktarma yapan Host'a kimlik doğrulaması yok.** Host, gelen ses paketini
  kime ileteceğine `sender_id` ile karar veriyor. Odaya bağlı olmayan biri
  Host'a UDP paketi yollarsa Host onu çözemez ama yönlendirebilir. Hız sınırı
  ve bir tür kimlik doğrulama gerekecek.

Kapanan sorular:

- ~~Mesh mi, aktarma mı?~~ → **Host üzerinden aktarma** (2026-09-16, §2.1).
- ~~Oturumlar arasında nonce tekrarı~~ → **oturum tuzu** (2026-09-16, §3).
  Bu bir soru olarak değil, yayınlanmış tasarımda hata olarak bulundu.
- ~~Katılımcı 4'ü aşarsa aktarmaya otomatik geçilsin mi?~~ → Baştan aktarma.
