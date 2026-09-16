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

Durum: **Faz 1 başladı, çekirdek yazıldı.** Ses paketi biçimi, şifreleme ve
jitter tamponu `core/` altında duruyor ve test ediliyor; ses donanımı, ağ ve
arayüz henüz yok. Faz 0'ın karar kapısı **hâlâ açık** — yazılan çekirdek ağ
ölçümünden bağımsız olduğu için beklemedi.

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
| Host yükleme bandı (4 kişi, Opus) | 0 | ~0,4 Mbit/s — sıradan bir ev bağlantısının çok altında |
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
| `voice_state` | çift yönlü | `muted`, `speaking` |

Sunucu ses verisine hiç dokunmaz; yalnızca kimin konuştuğunu ve paketleri
kime ileteceğini bilir.

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
oda parolası ──PBKDF2──▶ ana anahtar ──HKDF──▶ ses anahtarı
ses anahtarı + oturum tuzu + gönderen kimliği ──HKDF──▶ oturum anahtarı
```

- **Ana anahtar** metin tarafıyla ortak. Metin anahtarı bit bit aynı kaldı,
  uyumluluk bozulmadı; bir test bunu doğruluyor.
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
| Prototip | Ham PCM 16 kHz 16-bit | ~256 kbit/s | Yeni ikili bağımlılık yok, hattı kanıtlar |
| Sürüm | Opus | ~24–32 kbit/s | 8–10 kat daha az bant, konuşmada daha iyi kalite |

Opus'a geçildiğinde `libopus` pakete eklenmeli ve bir Python bağlaması
seçilmeli. Prototipi PCM ile yapmak, kodek sorunlarıyla ağ sorunlarını
birbirine karıştırmamayı sağlar.

---

## 5. Jitter buffer — atlanamaz

UDP paketleri sırasız, düzensiz aralıklarla ve bazıları hiç gelmeden varır.
Doğrudan hoparlöre yazmak cırtlak ses üretir.

Yazıldı: `core/voice_jitter.py`. İçinde saat, soket ya da Qt yok; girdi sıra
numarası ve bayt dizisi, çıktı çerçeve sırası. Ses cihazı her 20 ms'de bir
`pop()` çağırır, `None` dönerse o çerçevede sessizlik çalar.

- Hedef tampon **60 ms**. Uyarlanabilir hâli henüz yok.
- Sıra numarasına göre yeniden sıralama.
- Tamponun gerisinde kalan paket atılır.
- Kayıp çerçeve yerine sessizlik. Sönümlenmiş tekrar henüz yok.
- **Tampon tamamen boşalırsa baştan doldurmaya döner.** Boş tamponu tüketmeye
  devam etmek sıra sayacını ileri kaçırır ve karşı taraf yeniden konuşmaya
  başladığında her çerçeve "geç kalmış" sayılırdı.
- Gönderen yeniden başlarsa (sıra numarası her iki yönde de anlamsız uzaklıkta)
  akış sıfırlanır.

---

## 6. Arayüz

- Sol kenar çubuğunda "Sesli Sohbet" bölümü, katıl/ayrıl düğmesi.
- Katılanların listesi; konuşan kişinin adı vurgulanır (basit RMS eşiği).
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
  çıkan çerçeve sırasını doğrula.
- ✅ Kripto testleri: AES-GCM gidiş-dönüş, yanlış parola çözemez, tekrar eden
  paket reddedilir, başlık kurcalanırsa çözülemez, aynı kimlikle iki oturum
  aynı anahtar akışını üretmez (§3'teki hatanın regresyon testi).
- ✅ Uçtan uca test: sentetik ses → şifrele → bozuk bir ağ (kayıp, sıra
  bozulması, kopya paket) → çöz → tampon → doğru çerçeve sırası.

Hepsi `tests/test_voice.py` içinde, 68 test. Ses donanımı, soket ya da Qt
kullanmıyorlar; CI'da çalışırlar. Ses donanımı gerektiren hiçbir test CI'da
çalışmamalı.

---

## 8. Fazlar

| Faz | İş | Çıktı |
| --- | --- | --- |
| **0. Ölçüm** | UDP gecikme, jitter ve kayıp ölçen küçük bir araç | **Karar kapısı**: rakamlar kötüyse plan burada durur — araç hazır, ölçüm bekliyor |
| **1a. Çekirdek** ✅ | Paket biçimi, AES-GCM + HKDF, jitter tamponu, testler | Ses donanımı olmadan çalışan, test edilmiş çekirdek |
| **1b. İskelet** | Sinyalleşme paketleri, UDP soketi, Host'ta aktarma, PCM 16 kHz, tek yönlü | Bir kişi konuşur, diğeri duyar |
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

### Faz 0 ölçüm aracı

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
