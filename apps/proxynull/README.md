**Türkçe** · [English](README.en.md)

# ProxyNull

**Durum: henüz kod yazılmadı.** Bu klasör ürünün sınırlarını tanımlar.
Protokol tasarımı: **[PROTOKOL.md](PROTOKOL.md)**.

ProxyNull, ProxyNet ailesinin **şifreleme odaklı** sürümüdür. ProxyChat'ten
farkı özellik eksikliği değil, özellik **reddi**dir: burada her özellik bir
saldırı yüzeyi ve metadata sızıntısı adayı olarak değerlendirilir ve
varsayılan cevap hayırdır.

İsim buradan gelir — geriye hiçbir şey kalmaz.

## Bu ürünün var oluş amacı

`../../THREAT_MODEL.md` içindeki **T5** rakibine karşı koruma: trafiği yıllarca
saklayan, sunucuya el koyabilen, hukuki zorlama uygulayabilen bir rakip.
ProxyChat bu hedefi taşımaz, ProxyNull taşır.

## Zorunluluklar

- **İleri gizlilik (forward secrecy).** Oturum anahtarları geçicidir ve
  silinir. Parola sonradan ele geçse bile kaydedilmiş trafik açılamaz.
- **Yalnızca iki kişi.** Grup sohbeti yok; grup şifrelemesinde ileri gizlilik
  ayrı ve büyük bir problem.
- **Kalıcı kimlik yok, doğrulama her oturumda.** İleri gizlilik, aktif MITM'e
  karşı doğrulama olmadan işe yaramaz. Kalıcı kimlik anahtarı diske yazılmak
  zorunda olduğu için reddedildi; yerine her oturumda o oturuma özel kısa bir
  doğrulama kodu sesle karşılaştırılır ve onaylanmadan mesaj gönderilemez.
- **Buluşma tek kullanımlık kodla.** Sunucu yok: iki taraf da aynı kısa kodu
  girer, buluşma adresi o koddan hesaplanır ve bağlantı Tor onion servisi
  üzerinden kurulur.
- **Sıfır kalıcılık.** Ne mesaj geçmişi, ne ayar dosyası, ne log. Diske hiçbir
  şey yazılmaz.
- **Zarf şifreleme ve dolgu.** Oda adı ve kullanıcı adı şifreli yükün içinde;
  mesajlar sabit boyut kovalarına doldurulur.
- **Mod pazarlığı yok.** Güvenlik seviyesi protokolde müzakere edilmez;
  düşürme saldırısına (downgrade attack) kapı açar.

## Yasaklar

Aşağıdakiler ProxyChat'e aittir ve buraya **eklenmeyecektir**:

| Yasak | Gerekçe |
| --- | --- |
| Mesaj geçmişi | Kalıcılık, el konulabilir yığın yaratır |
| Ayar/parola/kimlik hatırlama | Anahtar malzemesi diske yazılmaz |
| İçerik önizlemeli bildirim | Ekranda ve bildirim geçmişinde sızıntı |
| Yazıyor göstergesi | Tuş zamanlaması metin ve etkinlik hakkında bilgi verir |
| Grup sohbeti, oda kavramı | İki kişi kapsamı bilerek seçildi |
| Sesli sohbet | Sürekli akış, konuşmanın zamanlamasını ele verir; gerekçesi [PROTOKOL.md](PROTOKOL.md) 10. bölümde |
| Dosya gönderme, tema, emoji | Saldırı yüzeyi, karşılığı yok |

İzin verilenler: kopan bağlantıyı yeniden kurma (güvenlikle çelişmez) ve
içeriksiz "yeni mesaj" uyarısı.

## Kullanım beklentisi

Bu tasarımın kaçınılmaz sonucu şu: **her oturum bir ritüelle başlar.** Kalıcı
kimlik olmadığı için doğrulama hatırlanamaz — her bağlantıda kısa doğrulama
kodu karşı tarafla program dışından karşılaştırılmak ve iki tarafça
onaylanmak zorunda. Onay gelmeden tek mesaj gönderilemez.

Bu bir eksiklik değil, verilen kararın bedeli. Ama sonucunun burada yazılı
olması gerekiyor: ProxyNull **seyrek ve bilinçli** kullanılan bir araç olacak.
Günlük sohbet ProxyChat'te kalıyor; ProxyNull onun yerini almıyor ve bu yüzden
iki ürün birlikte yaşıyor. "Neden sürekli kullanılmıyor" sorusu sonradan bir
başarısızlık gibi görünmesin — cevabı tasarımın içinde.

## ProxyChat ile ilişkisi

**Kod paylaşılmaz.** ProxyNull ayrı bir dilde (Rust) yazılacak ve protokolü
de kasten ayrışacak — ileri gizlilik, zarf şifreleme, geçmişsizlik. Dolayısıyla
`core/` paketi ProxyChat'e aittir, buradan kullanılmaz.

Bunun kaçınılmaz bedeli iki bağımsız implementasyondur. Divergence'ı önleyen
şey ortak kod değil, **ortak yazılı referanslardır**: `THREAT_MODEL.md` ve
`docs/` altındaki tasarım belgeleri. Protokol yazılmaya başlandığında
normatif bir spesifikasyon belgesi de buraya eklenmelidir.

İki ürünün kullanıcıları birbiriyle **konuşamaz**; bu, ayrımın kabul edilmiş
sonucudur.

## Hedef platformlar

**Windows ve Linux birlikte**, ilk sürümden itibaren.

Gerekçe kullanıcı sayısı değil, doğru kitle: ProxyNull son kullanıcıyı değil,
T5 rakibine karşı korunması gereken insanları hedefliyor ve o kitle Linux'ta
yoğun (Tails, Qubes, Whonix). Bir de kodu denetleyecek güvenlik
araştırmacıları var — çalıştıramadıkları bir şeyi incelemezler.

Maliyeti düşük, çünkü ProxyChat'i Windows'a bağlayan üç şeyin de burada
karşılığı yok:

| ProxyChat'te | ProxyNull'da |
| --- | --- |
| Qt arayüzü | Komut satırı, platform bağımsız |
| DPAPI ile parola saklama | Parola saklamak zaten yasak |
| NSIS installer | Rust tek statik binary üretiyor |

Geriye kalan çekirdek (soketler, Noise, ratchet) platform-nötr.

Ek kazanç: yeniden üretilebilir derleme Linux'ta hem daha kolay hem daha
anlamlı (bkz. THREAT_MODEL.md 5.9).

**macOS şimdilik kapsam dışı.** Rust tarafı bedava ama Apple'ın imzalama ve
noterleme süreci ücretli geliştirici hesabı gerektiriyor. Talep gelirse
değerlendirilir.

**Grafik arayüz eklenirse maliyet burada artar** — Rust'ın çapraz platform
GUI ekosistemi Qt kadar olgun değil. Bu, komut satırı kararının bir gerekçesi
daha.

## Yol haritası

Sırası ve gerekçeleri `../../THREAT_MODEL.md` 8. bölümde.

1. ~~**Protokol tasarımı** — dilden bağımsız, normatif belge.~~ Taslağı
   yazıldı: [PROTOKOL.md](PROTOKOL.md). İçinde kararı verilmiş maddeler ve
   hâlâ açık olanlar ayrı işaretli.
2. **Rust implementasyonu** — bu klasörde bir Cargo projesi olarak. Python
   prototip aşaması yok: `snow` (Noise), `zeroize` ve statik, yeniden
   üretilebilir binary bu ürünün gereksinimleri ve Python'la karşılanamaz.
3. Arayüz komut satırı; grafik arayüz yok.

Kararlar netleşmeden kod yazılmayacak.
