**Türkçe** · [English](CHANGELOG.en.md)

---

# Değişiklik günlüğü

Burada "birkaç sorun düzeltildi" yazmıyor. Her madde **neyin yanlış olduğunu**
anlatıyor; nasıl düzeltildiğini değil. Nasılını merak edersen
[THREAT_MODEL.md](THREAT_MODEL.md) ve commit mesajları o işi görüyor.

Başlıkta **⚠ tel kırılması** yazıyorsa o sürüm, eski sürümlerle şifreli mesaj
alışverişi yapamaz; iki taraf da "farklı sürüm" görür. Bu bilerek böyle:
pazarlık olmadığı için kimse iki tarafı eski şemaya düşürmeye zorlayamaz.

Henüz herkese açık bir sürüm dağıtılmadı.

---

## 1.12.0 — ⚠ tel kırılması

- **Şifreli bir mesajın uzunluğu, düz metnin uzunluğuyla birebir aynıydı.**
  Sunucu mesajı okuyamıyordu ama boyuna bakıp "bu üç karakterlik bir cevap, bu
  dört yüz karakterlik bir paragraf" diyebiliyordu. Artık yük sabit
  basamaklara yuvarlanıyor: "ok", "hayır", "geliyorum" telde **tıpatıp aynı
  boyda** gidiyor.
- Bunun bedeli iki bayt: gönderilebilecek en uzun mesaj 6112'den **6110
  bayta** indi. Gerçek uzunluğu taşıyan alan oradan çıkıyor.
- **Ses paketlerinin boyunun konuşmadan bağımsız olması bir ayara bağlıydı ve
  o ayarı koruyan hiçbir şey yoktu.** Ayarı ölçen test, ses kütüphanesi kurulu
  olmayan bir makinede atlanıyordu — yani çoğu yerde hiç çalışmıyordu. Biri
  değişken bit hızını açsaydı paket boyu sese göre değişir ve konuşmanın ritmi
  ağdan okunabilir hâle gelirdi. Artık kütüphane olmadan da kilitli.

## 1.11.0

- Emoji yazmak için mesaj kutusunun sağına bir seçici geldi. Yalnızca
  emojiden oluşan kısa mesajlar büyük gösteriliyor — `test👍` küçük kalır, tek
  başına `👍` büyür. (GIF yok ve olmayacak: bir görüntü çözücü, işaretlemeye
  izin vermek ve dosya aktarma demek — üçü de yeni saldırı yüzeyi. Emoji
  bunların hiçbirini gerektirmiyor, ağa giden şey yine düz metin.)
- **Oda parolasını bildiğini kanıtlayamayan biri odaya girdiğinde sohbete
  "katıldı" satırı düşüyordu.** Sahte kullanıcı üreten biri sohbeti bu
  satırlarla doldurabilirdi. Artık hiç gösterilmiyor; kullanıcı listesinde
  tek bir satırda sayılıyor, üstüne tıklanınca adlar açılıyor. Sayı 100'ü
  geçerse ">100" yazıyor.
- Mesajlarda adın arkasında iki nokta yoktu, adla metin birbirine
  karışıyordu. İki nokta geldi ve adın renginin koyusunda çiziliyor.
- Kullanıcı listesinde adlar bitişikti; aralarına ince bir ayraç çizgisi
  girdi.
- Sağ kenar tek bir uzun sütundu; kullanıcılar ve sesli sohbet artık iki ayrı
  kart.

## 1.10.1

- **`core/crypto.py`'nin büyük kısmı, artık hiçbir yerden çağrılmayan eski
  Fernet yolunu içeriyordu.** Kimse kullanmıyordu ama dosyayı okuyan biri
  "ProxyChat hâlâ paroladan türetilen sabit anahtarla şifreliyor" sonucuna
  varabilirdi; ayrıca kullanılmayan bir şifreleme yolu, bir gün yanlışlıkla
  yeniden bağlanabilecek bir yoldur. Silindi.
- **Ses şifreleyicisi, anahtar verilmediğinde sessizce paroladan türeyen eski
  şemaya düşüyordu.** Sessiz bir geri düşüş, olmaması gereken şeydir: artık
  açıkça izin verilmediyse hata veriyor.

## 1.10.0 — ⚠ tel kırılması (ses)

- **Sesin anahtarı hâlâ paroladan türüyordu.** Metin tarafı bir sürüm önce
  ileri gizli olmuştu, ses değildi: parola aylar sonra sızsa kaydedilmiş ses
  açılabilirdi. Artık ses oturum anahtarı da oda oturumundan türüyor, yani ses
  metnin ileri gizliliğini miras alıyor.

## 1.9.0 — ⚠ tel kırılması

- **Mesajları şifreleyen anahtar paroladan türüyordu ve hiç değişmiyordu.**
  Yani parola aylar sonra ele geçse, o güne kadar kaydedilmiş bütün trafik
  geriye dönük açılabilirdi. Artık anahtar her oturumda yeniden doğuyor ve
  oturum bitince bırakılıyor; parolanın işi şifrelemek değil, karşı tarafın
  odaya ait olduğunu doğrulamak.
- **Odaya sonradan giren biri, kendisi orada yokken yazılmış mesajları
  alıyordu.** Şifreli odalarda geçmiş tamamen kaldırıldı — zaten ileri
  gizlilikle sonradan bağlanan onları açamazdı. Parolasız odalarda geçmiş
  duruyor.
- **Kullanıcı listesi sunucunun söylediği şeydi.** Sunucu istediği adı
  listeye koyabilirdi. Artık liste bir kanıt: yalnızca anahtar takasını
  tamamlayabilen kişiler adlarıyla görünüyor.

## 1.8.0

- **Sesli sohbet uygulamanın içine girdi.** Sunucu sesi çözmeden aktarıyor;
  arayüzde katıl/ayrıl, katılımcı listesi ve sustur var.
- **Mikrofon, kimse konuşmazken tuş seslerini ve uğultuyu taşıyordu.** Gürültü
  kapısı geldi: konuşma yokken mikrofon sessize çevriliyor. Akış durmuyor —
  durursa kimin ne zaman konuştuğu ağdan görünürdü.
- **Sesli sohbete eski bir sunucu üzerinden katılmaya çalışmak sonsuza kadar
  bekliyordu**, çünkü eski sunucular o isteğe hiç cevap vermiyor. Artık 5
  saniye sonra vazgeçip nedenini söylüyor.
- İki taraf farklı ses kodeği kullandığında ses sessizce bozuluyordu; artık
  açık bir hata veriyor.

## 1.7.0

- **Oda geçmişi varsayılan olarak açıktı.** Odaya giren herkes, girmeden önce
  yazılmış her şeyi alıyordu. Varsayılan kapatıldı; açıksa bile yalnızca
  bellekte duruyor, diske yazılmıyor ve sunucu kapanınca gidiyor.
- **Parola PBKDF2 ile türetiliyordu ve bir ekran kartı binlerce denemeyi aynı
  anda yürütebiliyordu.** Argon2id'ye geçildi: her deneme 64 MiB bellek de
  istiyor, paralel denemenin bedeli bellekle çarpılıyor.
- **"Parola üret" düğmesi parolayı ekranda gösteriyordu.** Artık göstermeden
  kopyalanabiliyor; kopya Windows pano geçmişinden ve bulut panosundan hariç
  tutuluyor ve 30 saniye sonra siliniyor.
- **Geçmiş kapalıyken oda değiştirmek görünümü siliyordu.** Gördüğün mesajlar
  artık bellekte kalıyor, döndüğünde geri geliyor ve arada geçen süre için bir
  not düşülüyor.
- **Aynı odaya yeniden girince kendini "katıldı" diye görüyordun.**
- Oda değiştiren biri "ayrıldı" + "katıldı" diye iki kez görünüyordu; artık
  tek satır ve hangi odaya geçtiği yazılmıyor.
- Kayıt aracı, içerik verilirse mesaj uzunluğunu yazma yeteneğini hâlâ
  taşıyordu (sızıntının kendisi 1.5.0'da kapanmıştı). O yetenek de kaldırıldı
  ki bir çağrı yeniden içerik verdiğinde sızıntı geri gelmesin.

## 1.6.3

- **Aynı porta ikinci bir sunucu hatasız açılabiliyordu.** Dahası, Host
  "Bütün ağlar"ı dinlerken başka bir program `127.0.0.1`'deki aynı portu
  dinleyip Host'un kendi bağlantısını üzerine alabiliyordu. Port artık
  sunucuya özel olarak ayrılıyor.

## 1.6.2

- **Host modu bütün ağ arayüzlerini dinliyordu.** Yani yalnızca VPN
  arayüzünü değil, bağlı olduğun ev ya da kafe ağını ve sanal adaptörleri de.
  VPN kullanmak bunu düzeltmiyordu. Artık dinlenecek ağ her başlatışta
  listeden elle seçiliyor; varsayılan yok ve seçim saklanmıyor.

## 1.5.0

- **Sunucunun olay kayıtları, şifreli metnin uzunluğunu yazıyordu.** İçerik
  kayda hiç girmiyordu ama uzunluk tek başına bilgi veriyor. Kaldırıldı.

---

Daha eski sürümler dağıtılmadı ve burada listelenmiyor.
