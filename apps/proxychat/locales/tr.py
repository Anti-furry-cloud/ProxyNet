# ProxyChat — kendi sunucunda, uçtan uca şifreli sohbet
# Copyright (C) 2026 Anti-furry-cloud
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Turkce. Anahtarlar en.py ile birebir ayni olmali (tests/test_i18n.py)."""

NAME = "Türkçe"

TEXTS = {
    # --- Pencere --------------------------------------------------------
    "window.language": "Arayüz dili",
    "tray.wrote": "{user} yazdı",
    "tray.content_hidden": "Yeni mesaj. Şifreli odada içerik bildirimde gösterilmez.",

    # --- Baglanti sayfasi -----------------------------------------------
    "connect.subtitle": "Kendi sunucunda, arkadaşlarınla sohbet. Hamachi ya da yerel ağ üzerinden.",
    "connect.hint": "Host modu bu bilgisayarda sunucu başlatır. Join modu Hamachi IP ile bağlanır.",
    "connect.privacy_title": "GİZLİLİK",
    "connect.keep_history": "Oda geçmişini tut (Host modu)",
    "connect.keep_history_tooltip": (
        "Sunucu, oda başına son 100 mesajı bellekte tutar; odaya sonradan\n"
        "girenler bunları görür. Diske hiçbir zaman yazılmaz.\n"
        "Dikkat: açıkken odaya giren HERKES, oda parolasını bilmese bile,\n"
        "bu mesajları şifreli hâlde alır. Parola zayıfsa bilgisayarında\n"
        "deneyerek çözebilir. Varsayılan kapalıdır."
    ),
    "connect.logging": "Tanılama kaydı tut",
    "connect.logging_tooltip": (
        "Sunucu olaylarını bir dosyaya yazar: oda adı, olay türü ve zaman.\n"
        "Mesaj içeriği, kullanıcı adı ve IP adresi YAZILMAZ.\n"
        "Varsayılan kapalıdır; yalnızca sorun araştırırken açın.\n"
        "Kapatıldığında var olan kayıt dosyaları da silinir."
    ),
    "connect.title": "Bağlan",
    "connect.username": "Kullanıcı adı",
    "connect.host_placeholder": "Hamachi IP ya da sunucu IP",
    "connect.listen_placeholder": "Dinlenecek ağı seç",
    "connect.listen_tooltip": (
        "Sunucu yalnızca seçilen ağdan gelen bağlantıları kabul eder.\n"
        "Hamachi seçilirse aynı Wi-Fi'deki yabancılar sunucuya ulaşamaz.\n"
        "Arkadaşların yerel ağdan bağlanacaksa yerel IP'yi seç."
    ),
    "connect.listen_all": "Bütün ağlar (0.0.0.0)",
    "connect.network_local": "Yerel ağ",
    "connect.network_other": "Diğer ağ",
    "connect.port": "Port",
    "connect.room": "Oda adı",
    "connect.password": "Oda parolası — girilirse mesajlar şifrelenir",
    "connect.show_password": "Göster",
    "connect.hide_password": "Gizle",
    "connect.copy_password": "Kopyala",
    "connect.password_copied": "Kopyalandı",
    "connect.copy_password_tooltip": (
        "Parolayı ekranda göstermeden panoya kopyalar.\n"
        "Windows pano geçmişine eklenmez ve 30 saniye sonra panodan silinir."
    ),
    "connect.generate_password": "Üret",
    "connect.generate_password_tooltip": (
        "Rastgele kelimelerden güçlü bir parola üretir.\n"
        "Yüz yüze ya da Signal'den paylaş — Discord gibi mesajları saklayan uygulamalardan asla."
    ),
    "connect.password_generated": (
        "Yeni parola üretildi. Odadaki herkesin tam olarak bunu girmesi gerekir. Yüz yüze söyle "
        "ya da Signal'den kaybolan mesajla gönder — Discord, Instagram, SMS ya da e-postadan değil."
    ),
    "connect.remember_password": "Oda parolasını hatırla",
    "connect.remember_password_tooltip": (
        "Parola Windows hesabına bağlı olarak şifrelenip saklanır. "
        "Başka bir hesap ya da başka bir bilgisayar okuyamaz."
    ),
    "connect.password_hint": (
        "Parola girilirse mesajlar bu cihazda şifrelenir; sunucu yalnızca "
        "şifreli metni görür. Odadaki herkesin aynı parolayı girmesi gerekir."
    ),
    "connect.button": "Bağlan",
    "connect.mode_join": "Join modu: sunucunun Hamachi IP adresini gir.",
    "connect.mode_host": (
        "Host modu: sunucu bu bilgisayarda açılır.\n"
        "Dinlenecek ağı seç. Hamachi seçersen aynı Wi-Fi'deki yabancılar sunucuya ulaşamaz."
    ),
    "connect.mode_demo": (
        "Demo modu: yerel sunucu açılır ve sahte kullanıcılar odaya girer.\n"
        "Arkadaş olmadan arayüzü test etmek için kullan."
    ),
    "connect.error_host_required": "Hamachi IP gerekli.",
    "connect.error_choose_network": "Dinlenecek ağı seç.",
    "connect.error_invalid_port": "Port 1 ile 65535 arasında bir sayı olmalı.",
    "connect.connecting": "Bağlanıyor...",
    "connect.connected": "Bağlandı.",
    "connect.connection_lost": "Bağlantı koptu.",
    "connect.reconnect_gave_up": "Bağlantı {attempts} denemede yeniden kurulamadı.",
    "connect.previous_attempt_pending": "Önceki bağlantı denemesi bitmedi.",

    # --- Sohbet sayfasi -------------------------------------------------
    "chat.waiting": "Bağlantı bekleniyor",
    "chat.channels": "KANALLAR",
    "chat.add_room": "Oda ekle",
    "chat.leave": "Bağlantıyı kes",
    "chat.status_waiting": "Bağlantı durumu: bekleniyor",
    "chat.message_placeholder": "Mesaj yaz...",
    "chat.send": "Gönder",
    "chat.unverified_one": "Doğrulanmayan kullanıcı: 1",
    "chat.unverified_many": "Doğrulanmayan kullanıcılar: {count}",
    "chat.unverified_over": "Doğrulanmayan kullanıcılar: >{limit}",
    "chat.unverified_hint": "Adları görmek için tıkla. Bu kişiler oda parolasını bildiğini kanıtlamadı; yazdıkları okunamaz.",
    "chat.emoji": "Emoji ekle",
    "chat.users": "Kullanıcılar",
    "chat.user_unverified": "{user}  · doğrulanmadı",
    "chat.user_unverified_hint": (
        "Bu kişi oda parolasını bildiğini henüz kanıtlamadı. El sıkışma sürüyor "
        "olabilir ya da parolası farklı. Kullanıcı listesi sunucudan geliyor; "
        "kanıt ise anahtar takasından."
    ),
    "chat.user_verified_hint": "Oda parolasını bildiğini kanıtladı.",
    "chat.voice_title": "SESLİ SOHBET",
    "chat.voice_join": "Sese katıl",
    "chat.voice_leave": "Sesten ayrıl",
    "chat.voice_mute": "Mikrofonu sustur",
    "chat.voice_microphone": "Mikrofon",
    "chat.voice_speaker": "Hoparlör",
    "chat.voice_device_default": "Sistem varsayılanı",
    "chat.voice_devices": "Ses cihazları",
    "chat.voice_devices_tooltip": "Mikrofon ve hoparlör seçimi",
    "chat.voice_devices_summary": "Mikrofon: {microphone}\nHoparlör: {speaker}",
    "chat.voice_gate": "Gürültü kapısı",
    "chat.voice_gate_tooltip": "Konuşmadığın anlarda mikrofonu sessize çevirir: klavye sesi ve cızırtı karşı tarafa gitmez.",
    "chat.voice_threshold_tooltip": "Eşiği ayarla: çubuk konuşurken eşiği geçmeli, sessizken geçmemeli.",
    "chat.voice_threshold_hint": "Eşik {value}. Konuşurken çubuk bunu geçmeli.",
    "chat.voice_threshold_off": "Gürültü kapısı kapalı: mikrofon ne alıyorsa gidiyor.",
    "chat.voice_state_off": "Ses kapalı.",
    "chat.voice_state_joining": "Sese katılınıyor...",
    "chat.voice_state_on": "Ses açık.",
    "chat.voice_alone": "Ses açık. Odada seste başka kimse yok.",
    "chat.switching_room": "# {room} kanalına geçiliyor...",
    "chat.joined_self": "{user} kanalına katıldı.",
    "chat.away_gap": "— Bu odada değilken yazılan mesajlar sana ulaşmadı. —",
    "chat.user_joined": "{user} kanala katıldı.",
    "chat.user_left": "{user} kanaldan ayrıldı.",
    "chat.user_moved": "{user} başka bir odaya geçti.",
    "chat.user_moved_many": "{user} başka bir odaya geçti (×{count}).",
    "chat.user_moved_back": "{user} başka bir odaya geçip geri döndü.",
    "chat.user_moved_back_many": "{user} başka bir odaya geçip geri döndü (×{count}).",
    "chat.user_returned": "{user} kanala geri döndü.",
    "chat.connected": "Bağlandı",
    "chat.user_count_one": "{count} kullanıcı bağlı",
    "chat.user_count": "{count} kullanıcı bağlı",
    "chat.connected_to": "Bağlandı: {host}:{port}",
    "chat.lock_encrypted": "🔒 Uçtan uca şifreli",
    "chat.lock_plain": "🔓 Oda parolası yok",
    "chat.lock_encrypted_tooltip": (
        "Mesajlar bu cihazda şifreleniyor; sunucuyu çalıştıran kişi dahil\n"
        "kimse okuyamıyor."
    ),
    "chat.lock_plain_tooltip": (
        "Oda parolası girilmediği için mesajlar şifrelenmiyor.\n"
        "Şifrelemek için bağlanırken bir oda parolası girin ve aynı\n"
        "parolayı odadaki herkesle paylaşın."
    ),
    "chat.encrypted_notice": (
        "Oda parolası girildi: mesajlar bu cihazda şifreleniyor, "
        "sunucu içeriği göremiyor."
    ),
    "chat.plain_notice": (
        "Oda parolası girilmedi: mesajlar şifrelenmiyor. Şifrelemek "
        "için bağlanırken bir oda parolası gir ve aynı parolayı "
        "arkadaşlarınla paylaş."
    ),
    "chat.share_addresses": "Arkadaşlarının bağlanabileceği adresler:",
    "chat.share_address": "Arkadaşlarının bağlanacağı adres:",
    "chat.reveal_address": "Adresi göster",
    "chat.reveal_address_tooltip": "Adres, ekran yayınında ya da kayıtta sızmasın diye gizli. Görmek için basılı tut; bırakınca yine gizlenir.",
    "chat.copy_addresses": "Adresi kopyala",
    "chat.address_copied": "Kopyalandı",
    "chat.ready": "Bağlantı hazır.",
    "chat.closed": "Bağlantı kapandı",
    "chat.reconnecting_status": "Bağlantı koptu — yeniden deneniyor ({attempt}/{total})",
    "chat.reconnecting_notice": "Bağlantı koptu. Yeniden bağlanılıyor... ({attempt}/{total})",
    "chat.reconnected": "Bağlantı yeniden kuruldu.",
    "chat.message_too_long": "Mesaj gönderilemeyecek kadar uzun. Kısalt ya da birkaç mesaja böl.",
    "chat.undecryptable": "[çözülemedi — oda parolası farklı]",
    "chat.undecryptable_version": "[çözülemedi — karşı taraf farklı bir ProxyChat sürümü kullanıyor]",
    "chat.undecryptable_sender": "[gösterilmedi — gönderen bu adla doğrulanamadı]",
    # Onceki gunlerin mesajlari: "9 Eyl 14:05".
    "chat.date_format": "{day} {month} {time}",
    "chat.months": "Oca Şub Mar Nis May Haz Tem Ağu Eyl Eki Kas Ara",

    # --- Demo kullanicilari ---------------------------------------------
    "demo.message_1": "Selam, bu demo odası.",
    "demo.message_2": "Mesaj listesi ve kullanıcı listesi burada test ediliyor.",
    "demo.message_3": "Oda geçişi ve çoklu istemci akışı çalışıyor.",

    # --- Hatalar --------------------------------------------------------
    "error.generic": "Hata",
    "error.voice_device": "Ses cihazı 16 kHz mono kaydı desteklemiyor; sesli sohbet açılamadı.",
    "error.voice_device_switch": "Seçilen ses cihazı açılamadı; görüşme önceki cihazla sürüyor.",
    "error.voice_not_connected": "Sesli sohbet için önce bir odaya bağlanman gerekiyor.",
    "error.voice_no_server": "Sunucu sesli sohbete cevap vermedi; eski bir sürüm olabilir. İki taraf da aynı sürümü kullanmalı.",
    "error.voice_codec": "Odadaki ses, bu bilgisayarda bulunmayan bir kodek kullanıyor (Opus). Sese katılamadın; herkeste aynı kurulum olmalı.",
    "error.connection": "Bağlantı hatası",
    "socket_error.10013": "Bu portu başka bir program kullanıyor (10013). Başka bir port seç ya da o programı kapat.",
    "socket_error.10048": "Bu port zaten kullanımda (10048). Başka bir port seç ya da diğer sunucuyu kapat.",
    "socket_error.10049": "Seçilen adres bu bilgisayarda yok (10049). Hamachi hâlâ bağlı mı?",
    "socket_error.10053": "Bağlantı kesildi (10053). Karşı taraf oturumu kapattı ya da hat koptu.",
    "socket_error.10060": "Bağlantı zaman aşımına uğradı (10060). Sunucu IP'sini, portu ve güvenlik duvarı ya da VPN kurallarını kontrol et.",
    "socket_error.10061": "Hedef bağlantıyı reddetti (10061). Sunucu henüz çalışmıyor olabilir.",
    "socket_error.other": "{name}: {detail}",

    "server_error.server_full": "Sunucu dolu.",
    "server_error.join_timeout": "Katılma isteği zamanında gelmedi.",
    "server_error.join_required": "Sunucu önce katılma isteği bekliyordu.",
    "server_error.idle_timeout": "Bağlantı çok uzun süre boşta kaldı.",
    "server_error.malformed_packet": "Sunucu bozuk bir paket aldı.",
    "server_error.malformed_packet_ignored": "Bozuk bir paket yok sayıldı.",
    "server_error.packet_too_large": "Bir paket boyut sınırını aştı.",
    "server_error.message_too_long": "Mesaj çok uzun.",
    "server_error.rate_limited": "Çok hızlı mesaj gönderiyorsun, biraz bekle.",
}

# Parola kelimeleri: yalnizca kucuk ASCII harf (c g i o s u'nun Turkce
# karakterli halleri YOK), 3-8 harf, yuksek sesle soylemesi kolay somut
# kelimeler. Parola baska klavyesi olan bir arkadasa da yazdirilabilmeli.
WORDS = tuple("""
elma armut kiraz erik incir karpuz kavun limon portakal muz nar ayva zeytin
fasulye nohut mercimek kabak lahana marul maydanoz nane kekik tarhun safran bal
peynir yumurta ekmek simit pide lokma helva baklava kurabiye pasta kek marmelat
ayran limonata kahve salep boza kefir kebap dolma sarma pilav makarna salata
tahin pekmez lokum kestane ceviz badem kaju hurma dut ananas kivi avokado
deniz dalga kum sahil ada liman gemi sandal yelken balina yunus ahtapot midye
istakoz karides levrek hamsi palamut orkinos tepe vadi orman yaprak dal tohum
filiz papatya lale karanfil nergis zambak orkide yosun mantar kedi inek koyun
tavuk horoz hindi kaz sincap kirpi aslan kaplan zebra fil gergedan maymun kurt
tilki geyik ceylan panda penguen kartal kanarya flamingo leylek karga kelebek
kumsal solucan yarasa timsah bulut kar dolu sis gezegen saman kuyu dere
nehir kaya mermer granit elmas yakut inci pencere duvar tavan zemin merdiven
balkon mutfak salon oda banyo dolap masa koltuk kanepe yatak yorgan perde lamba
ayna saat takvim kitap defter kalem silgi cetvel makas zarf pul harita pusula
fener mum kibrit anahtar kilit zincir halat sepet kova tencere tava tabak kase
fincan demlik semaver kavanoz testi araba tren vapur roket balon tekne kayak
paten motor yol sokak cadde meydan kale kule saray okul park pazar otel gitar
keman davul piyano zurna saz ney def zil nota resim heykel boya kilim dantel
ipek pamuk kadife deri keten kazak ceket palto etek pantolon terlik bere
eldiven kemer yaka cep mavi mor pembe beyaz siyah gri turuncu lacivert bordo
bej haki eflatun sakin cesur eski yeni derin sessiz parlak serin ince uzun
mutlu zengin temiz berrak sert hafif zeki nazik kibar sevimli bilye oyuncak
bebek top yapboz dama tavla zar kart madalya kupa bayrak mektup telefon radyo
kamera ekran kablo pil mikrofon anten uydu robot kutu paket hediye mendil
havlu sabun tarak kolye bilezik baston valiz ova yayla kanyon volkan buzul
kutup okyanus koy burun vaha step tundra savan bostan bahar yaz sonbahar mevsim
sabah gece hafta atom enerji lazer radar sinyal kristal kuvars mercek prizma
galaksi nebula kuyruk meteor uzay evren vazo tablo heybe tepsi fanus tarla
harman ambar kiler sedef mercan akvaryum kamp piknik karavan
""".split())
