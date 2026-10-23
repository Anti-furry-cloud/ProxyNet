**Türkçe** · [English](README.en.md)

# ProxyChat — Kapsam

ProxyChat, ProxyNet ailesinin **günlük kullanım** sürümüdür. Şifreleme odaklı
sürüm için `../proxynull/README.md`, tehdit modeli için `../../THREAT_MODEL.md`.

Bu belge tek bir soruyu cevaplamak için var: **hangi özellik eklenir, hangisi
eklenmez?** Parlak bir fikir her gündeme geldiğinde baştan tartışmamak için.

---

## 1. Neden var

ProxyChat, Discord'un kopyası olmak için yazılmıyor. Discord'da yüzlerce
geliştirici, mobil istemciler ve çok daha olgun bir ses altyapısı var; özellik
yarışında kazanma ihtimalimiz yok ve bu yarışa girmek anlamsız.

ProxyChat'in var olma sebebi, Discord'un **yapamayacağı** dört şey:

1. **Sunucu sizindir.** Aracı bir şirket yok; kapatabilecek, kural
   değiştirebilecek, hesabınızı askıya alabilecek kimse yok.
2. **Oda parolasıyla uçtan uca şifreleme.** Sunucuyu çalıştıran kişi bile
   mesajları okuyamaz. Discord'da bu hiç olmadı.
3. **Hesap yok.** E-posta, telefon numarası, doğrulama, veri toplama yok.
4. **İnternet gerekmez.** Yerel ağda, dışarıya hiç çıkmadan çalışır.

Bir özellik bu dördünü güçlendirmiyorsa, ProxyChat'i Discord yerine seçme
sebebine bir şey katmıyor demektir.

---

## 2. Kabul ölçütü

Yeni bir özellik önerildiğinde sırayla üç soru:

**S1. Sürtünme mi azaltıyor, özellik listesi mi büyütüyor?**
Uygulamayı *daha az sinir bozucu* yapan şeyler kabul edilir. "Discord'da da
var" bir gerekçe değildir.

**S2. Yukarıdaki dört sebepten hangisini güçlendiriyor ya da hangisini
zayıflatıyor?**
Hiçbirini güçlendirmiyor ve birini zayıflatıyorsa, cevap hayırdır.

**S3. Bedeli ne?**
Saldırı yüzeyi, sızan metadata, bakım yükü, derleme boyutu. Bedel yazılmadan
özellik kabul edilmez.

---

## 3. Bugüne kadar kabul edilenler

Hepsi S1'den geçtiği için kabul edildi — hiçbiri "Discord'da var" diye
eklenmedi:

| Özellik | Neden geçti |
| --- | --- |
| Kopan bağlantıda yeniden bağlanma | Uygulamayı kapatıp açmak zorunda kalmak |
| Ayarların hatırlanması | Her açılışta beş alanı elden doldurmak |
| Arka plan bildirimi | Uygulama yalnızca ekrana bakarken çalışıyordu |
| Katılma/ayrılma satırları | Kimin geldiğini anlamanın hiçbir yolu yoktu |
| Kendi mesajının ayrışması | Akışta kendini bulamamak |
| Oda listesinin sunucudan gelmesi | Karşı taraf açılan kanalı hiç görmüyordu |
| Parola üretme ve gösterme düğmeleri | Kullanıcılar tahmin edilebilir kısa parolalar seçiyordu; üretilen parola da okunamadığı için yüz yüze paylaşılamıyordu |
| Arayüz dili (İngilizce / Türkçe) | Yalnızca Türkçe arayüz, Türkçe bilmeyen arkadaşı dışarıda bırakıyordu |

---

## 4. Şu an kapsam dışı

Bunlar **yasak değil**, ama hiçbiri henüz 2. bölümdeki üç soruyu geçmedi.
Eklenmesi isteniyorsa önce o sorular cevaplanmalı ve gerekçe buraya yazılmalı.

| Özellik | Neden bekliyor |
| --- | --- |
| Roller ve yetkiler | Arkadaş grubu ölçeğinde çözdüğü bir sorun yok |
| Emoji **tepkileri** (mesaja iliştirilen), profil resimleri, temalar | Saf görünüm; dört sebepten hiçbirine dokunmuyor. Emoji **yazmak** 1.11.0'da geldi (seçici + yalnız emojiden oluşan mesajın büyük gösterilmesi): o yalnızca gösterim, ağa giden şey yine düz metin |
| Dosya gönderme, GIF | Protokolü, şifrelemeyi ve boyut sınırlarını baştan kurmayı gerektirir. GIF ayrıca bir görüntü çözücü demek (uzaktan kod çalıştırma açıklarının klasik kaynağı) ve işaretlemeye izin verirse kaçırılmamış bir `<img>` Windows'ta SMB üzerinden kimlik sızdırabilir |
| Botlar, webhook'lar | Ciddi saldırı yüzeyi, karşılığı yok |
| Davet bağlantıları, sunucu keşfi | Merkezî bir dizin gerektirir; 1. maddeyle çelişir |
| Mesaj düzenleme/silme | Geçmiş yönetimi karmaşıklaşır; kalıcılık kararlarıyla çakışır |

Sesli sohbet ayrı değerlendirildi ve 1.8.0'dan beri uygulamada. Tasarımı,
geçtiği karar kapısı ve geliştirme günlüğü
[VOICE_CHAT_PLAN.md](../../VOICE_CHAT_PLAN.md) içinde.

---

## 5. Görsel kimlik

Arayüzün renk paleti şu an **birebir Discord'un koyu teması** (`#313338`,
`#2b2d31`, `#f2f3f5`, `#ed4245`) ve yerleşim de aynı: solda kanallar, ortada
mesajlar, sağda kullanıcılar.

Arkadaş grubu içinde sorun değil. Ancak uygulama halka açık dağıtılacaksa
paletin kendine ait hale getirilmesi gerekir — marka benzerliği gereksiz bir
risk ve "Discord kopyası" izlenimi asıl anlatmak istediğimiz şeyi gölgeliyor.

Öncelik düşük, ama unutulmaması için buraya yazıldı.

---

## 6. Karar kaydı

| Karar | Sonuç | Gerekçe |
| --- | --- | --- |
| ProxyChat'i Discord özellik listesine göre büyütmek | **Reddedildi** | Özellik yarışı kaybedilir; değer dört farkta |
| Kolaylık özellikleri (yeniden bağlanma, bildirim, ayar) | **Kabul edildi** | S1'den geçti, dört sebeple çelişmiyor |
| Kalıcı geçmiş için VPS | **Reddedildi** | `THREAT_MODEL.md` ilke 2 |
| Renk paletini değiştirmek | **Ertelendi** | Halka açık dağıtımdan önce ele alınacak |
