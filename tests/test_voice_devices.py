"""Ses cihazi secimi: mikrofon ve hoparlor.

Eskiden secim yoktu; ses her zaman Windows'un varsayilan cihazindan
aciliyordu ve yanlis mikrofonu kullanan biri bunu ancak Windows ayarlarindan
degistirebiliyordu. Bu testler sunlari kilitliyor:

- Kayitli cihaz takili degilse varsayilana dusulur ama kayit SILINMEZ;
  kulaklik geri takilinca yine o secilir.
- Gorusme sirasinda cihaz degisince YALNIZCA ses karti yeniden acilir;
  oturum, sifreleme ve UDP baglantisi ayni kalir.
- Yeni cihaz acilamazsa gorusme dusmez, eski cihaza donulur; arayuz ve kayit
  istenene degil gercekte kullanilana uyar.
- Ayara yalnizca cihazin kimligi yazilir, adi degil.

Gercek ses donanimi acilmaz: cihaz listesi conftest.py'deki sabit listeden
geliyor, ses karti sahte.
"""

import unittest
from unittest import mock

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from apps.proxychat import voice
from apps.proxychat.i18n import set_language, t
from apps.proxychat.settings import ChatSettings
from apps.proxychat.voice import VoiceController, VoiceDeviceError, pick_device
from core.voice_codec import available_codec
from tests.test_voice_ui import SahteBaglanti, SahteSesCihazi
from tests.test_proxychat_ui import izole_ayarlar_ve_yol


class SahteCihaz:
    """QAudioDevice yerine: yalnizca kimligi var."""

    def __init__(self, kimlik: bytes):
        self._kimlik = kimlik

    def id(self):
        return self._kimlik


class _QtTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])


class CihazSecimiTests(unittest.TestCase):
    """pick_device: istenen takiliysa o, degilse varsayilan."""

    def setUp(self):
        self.varsayilan = SahteCihaz(b"varsayilan")
        self.liste = [SahteCihaz(b"a"), SahteCihaz(b"kulaklik"), self.varsayilan]

    def test_istenen_takiliysa_o_secilir(self):
        self.assertEqual(pick_device(self.liste, b"kulaklik", self.varsayilan).id(), b"kulaklik")

    def test_istenen_cikarilmissa_varsayilana_dusulur(self):
        """Hata vermek yerine varsayilan: kulaklik cikarilmis olabilir."""
        self.assertIs(pick_device(self.liste, b"takili-degil", self.varsayilan), self.varsayilan)

    def test_bos_kimlik_sistem_varsayilani_demek(self):
        self.assertIs(pick_device(self.liste, b"", self.varsayilan), self.varsayilan)


class AyarTests(unittest.TestCase):
    def test_hic_kayit_yoksa_ikisi_de_varsayilan(self):
        ayarlar, _ = izole_ayarlar_ve_yol(self)
        self.assertEqual(ayarlar.load_voice_devices(), (b"", b""))

    def test_kaydedilen_geri_okunur(self):
        """Kimlikler herhangi bir bayt tasiyabilir; hex olarak saklaniyor."""
        ayarlar, _ = izole_ayarlar_ve_yol(self)
        ayarlar.save_voice_devices(input_id=b"\x00mic\xff", output_id=b"{0.0.0}.{guid}")
        self.assertEqual(ayarlar.load_voice_devices(), (b"\x00mic\xff", b"{0.0.0}.{guid}"))

    def test_yalnizca_biri_degisince_digeri_korunur(self):
        ayarlar, _ = izole_ayarlar_ve_yol(self)
        ayarlar.save_voice_devices(input_id=b"mic", output_id=b"spk")
        ayarlar.save_voice_devices(input_id=b"yeni-mic")
        self.assertEqual(ayarlar.load_voice_devices(), (b"yeni-mic", b"spk"))

    def test_bozuk_kayit_programi_acilmaz_yapmaz(self):
        """Elle bozulmus kayit: varsayilana dus, cokme."""
        _, yol = izole_ayarlar_ve_yol(self)
        ham = QSettings(yol, QSettings.Format.IniFormat)
        ham.setValue("voice_input_device", "bu-hex-degil")
        ham.sync()
        ayarlar = ChatSettings(QSettings(yol, QSettings.Format.IniFormat))
        self.assertEqual(ayarlar.load_voice_devices(), (b"", b""))


class KaydedenSesKarti(SahteSesCihazi):
    """Gercek VoiceAudio yerine: hangi cihazlarla acildigini kaydeder."""

    acilanlar: list = []

    def __init__(self, session, send_frame, input_id=b"", output_id=b""):
        super().__init__(session, send_frame)
        self.input_id = input_id
        self.output_id = output_id
        KaydedenSesKarti.acilanlar.append(self)


class GercekSesKartiTests(_QtTestCase):
    """VoiceAudio'nun KENDISI: hangi cihazi actigini dogru bildiriyor mu?

    Diger testler sahte kart kullaniyor ve o sahte kart kimligini kendisi
    yaziyor. Kasten bozulan kodla denendi: gercek kart kimligi bildirmeyi
    biraksa butun testler geciyordu, gorusmede cikarilan kulaklik ozelligi ise
    urunde sessizce kapaniyordu. Burada QtMultimedia'nin yerine sahte bir
    modul konuyor: gercek kod calisiyor, donanim acilmiyor.
    """

    def _modul(self, girisler, cikislar, varsayilan_giris, varsayilan_cikis):
        import types

        def cihaz(kimlik):
            c = mock.Mock()
            c.id.return_value = kimlik
            c.isFormatSupported.return_value = True
            return c

        g = {k: cihaz(k) for k in girisler}
        c = {k: cihaz(k) for k in cikislar}
        modul = types.ModuleType("PySide6.QtMultimedia")
        modul.QMediaDevices = mock.Mock()
        modul.QMediaDevices.audioInputs.return_value = list(g.values())
        modul.QMediaDevices.audioOutputs.return_value = list(c.values())
        modul.QMediaDevices.defaultAudioInput.return_value = g[varsayilan_giris]
        modul.QMediaDevices.defaultAudioOutput.return_value = c[varsayilan_cikis]
        modul.QAudioFormat = mock.MagicMock()
        modul.QAudioSource = mock.MagicMock()
        modul.QAudioSink = mock.MagicMock()
        return modul

    def _kart(self, modul, input_id=b"", output_id=b""):
        import sys

        with mock.patch.dict(sys.modules, {"PySide6.QtMultimedia": modul}):
            kart = voice.VoiceAudio(mock.Mock(), lambda _f: None, input_id, output_id)
        self.addCleanup(kart.stop)  # calma zamanlayicisi dursun
        return kart

    def test_secili_cihaz_takiliysa_onu_acar_ve_bildirir(self):
        modul = self._modul([b"ic", b"kulaklik"], [b"spk"], b"ic", b"spk")
        kart = self._kart(modul, input_id=b"kulaklik")
        self.assertEqual(kart.input_device_id, b"kulaklik")
        self.assertEqual(modul.QAudioSource.call_args[0][0].id(), b"kulaklik", "gercekten o cihaz acilmali")

    def test_secili_cihaz_yoksa_varsayilani_acar_ve_VARSAYILANI_bildirir(self):
        """Bildirilen, istenen degil GERCEKTE acilan olmali; yoksa kontrolcu
        kartin kaybolan bir cihazda oldugunu anlayamaz."""
        modul = self._modul([b"ic"], [b"spk"], b"ic", b"spk")
        kart = self._kart(modul, input_id=b"cikarilmis-kulaklik")
        self.assertEqual(kart.input_device_id, b"ic")
        self.assertEqual(kart.output_device_id, b"spk")

    def test_bicimi_desteklemeyen_cihaz_reddedilir(self):
        modul = self._modul([b"ic"], [b"spk"], b"ic", b"spk")
        modul.QMediaDevices.defaultAudioInput.return_value.isFormatSupported.return_value = False
        import sys

        with mock.patch.dict(sys.modules, {"PySide6.QtMultimedia": modul}):
            with self.assertRaises(VoiceDeviceError):
                voice.VoiceAudio(mock.Mock(), lambda _f: None)


class _KontrolcuTestleri(_QtTestCase):
    """Kontrolcu testlerinin ortak yardimcilari; kendisi test icermiyor."""

    def _kontrolcu(self, fabrika=None):
        self.baglanti = SahteBaglanti()
        self.cihazlar = []

        def varsayilan_fabrika(session, send_frame):
            cihaz = SahteSesCihazi(session, send_frame)
            self.cihazlar.append(cihaz)
            return cihaz

        kontrolcu = VoiceController(self.baglanti, audio_factory=fabrika or varsayilan_fabrika)
        self.addCleanup(kontrolcu.leave)
        self.hatalar = []
        kontrolcu.failed.connect(self.hatalar.append)
        return kontrolcu

    def _katil(self, kontrolcu):
        kontrolcu.join()
        kontrolcu.on_packet(
            {
                "type": "voice_joined",
                "sender_id": 1,
                "token": "ab" * 16,
                "port": 5555,
                "codec": available_codec(),
            }
        )
        self.assertEqual(kontrolcu.state, "on")
        return kontrolcu

class KontrolcuCihazTests(_KontrolcuTestleri):
    def test_gercek_fabrika_secilen_cihazlari_kullanir(self):
        """Fabrika imzasi degismedi; secimi gercek fabrika kendisi okuyor."""
        KaydedenSesKarti.acilanlar = []
        with mock.patch.object(voice, "VoiceAudio", KaydedenSesKarti):
            kontrolcu = VoiceController(SahteBaglanti())
            self.addCleanup(kontrolcu.leave)
            kontrolcu.set_devices(input_id=b"kulaklik-mic", output_id=b"kulaklik")
            self._katil(kontrolcu)
        acilan = KaydedenSesKarti.acilanlar[-1]
        self.assertEqual((acilan.input_id, acilan.output_id), (b"kulaklik-mic", b"kulaklik"))

    def test_gorusme_disinda_secim_yalnizca_saklanir(self):
        kontrolcu = self._kontrolcu()
        kontrolcu.set_devices(input_id=b"mic", output_id=b"spk")
        self.assertEqual((kontrolcu.input_device, kontrolcu.output_device), (b"mic", b"spk"))
        self.assertEqual(self.cihazlar, [], "gorusme yokken ses karti acilmamali")

    def test_gorusmede_degisince_yalnizca_ses_karti_yeniden_acilir(self):
        """Oturum, sifreleme ve UDP baglantisi ayni nesne kalmali."""
        kontrolcu = self._katil(self._kontrolcu())
        oturum, baglanti, eski_kart = kontrolcu.session, kontrolcu.link, kontrolcu.audio

        kontrolcu.set_devices(input_id=b"kulaklik-mic")

        self.assertTrue(eski_kart.stopped, "eski ses karti kapatilmali")
        self.assertIsNot(kontrolcu.audio, eski_kart)
        self.assertIs(kontrolcu.session, oturum, "oturum (sifreleme, tamponlar) ayni kalmali")
        self.assertIs(kontrolcu.link, baglanti, "UDP baglantisi ayni kalmali")
        self.assertEqual(kontrolcu.state, "on")

    def test_yeni_kart_susturmayi_ve_kapiyi_korur(self):
        """Cihaz degisti diye susturulmus mikrofon acilmamali."""
        kontrolcu = self._katil(self._kontrolcu())
        kontrolcu.set_muted(True)
        kontrolcu.set_noise_gate(False)
        kontrolcu.set_gate_threshold(1234)

        kontrolcu.set_devices(input_id=b"kulaklik-mic")

        self.assertTrue(kontrolcu.audio.muted)
        self.assertFalse(kontrolcu.audio.gate.enabled)
        self.assertEqual(kontrolcu.gate_threshold, 1234)

    def test_ayni_cihaz_secilince_kart_yeniden_acilmaz(self):
        kontrolcu = self._kontrolcu()
        kontrolcu.set_devices(input_id=b"mic")
        self._katil(kontrolcu)
        kart = kontrolcu.audio
        kontrolcu.set_devices(input_id=b"mic")
        self.assertIs(kontrolcu.audio, kart)
        self.assertFalse(kart.stopped)

    def test_yeni_cihaz_acilamazsa_eskisine_donulur(self):
        """Gorusme dusmez; hata bildirilir ve secim geri alinir."""
        cihazlar = []

        def fabrika(session, send_frame):
            if kontrolcu.input_device == b"bozuk":
                raise VoiceDeviceError("audio_format")
            cihaz = SahteSesCihazi(session, send_frame)
            cihazlar.append(cihaz)
            return cihaz

        kontrolcu = self._kontrolcu(fabrika)
        kontrolcu.set_devices(input_id=b"calisan")
        self._katil(kontrolcu)

        kontrolcu.set_devices(input_id=b"bozuk")

        # "Sesli sohbet acilamadi" DEGIL: gorusme suruyor, mesaj onu soylemeli.
        self.assertEqual(self.hatalar, ["voice_device_switch"])
        self.assertEqual(kontrolcu.input_device, b"calisan", "secim geri alinmali")
        self.assertEqual(kontrolcu.state, "on", "gorusme dusmemeli")
        self.assertIsNotNone(kontrolcu.audio)
        self.assertFalse(kontrolcu.audio.stopped)

    def test_geri_donuste_susturma_korunur(self):
        """GIZLILIK: susturulmus mikrofon geri donuste acik gitmemeli.

        Inceleme buldu: ilk deneme eski karti kapatip None yapiyor, ikinci
        deneme susturmayi None'dan okuyup False sayiyordu. Kullanici
        susturmusken mikrofon canli aciliyor, arayuzdeki kutu isaretli
        kaliyordu. Butun mutasyon testleri bunu kaciriyordu, cunku hicbir
        test once susturup sonra basarisiz bir gecis denemiyordu.
        """

        def fabrika(session, send_frame):
            if kontrolcu.input_device == b"bozuk":
                raise VoiceDeviceError("audio_format")
            return SahteSesCihazi(session, send_frame)

        kontrolcu = self._kontrolcu(fabrika)
        kontrolcu.set_devices(input_id=b"calisan")
        self._katil(kontrolcu)
        kontrolcu.set_muted(True)

        kontrolcu.set_devices(input_id=b"bozuk")

        self.assertTrue(kontrolcu.audio.muted, "geri donulen kart susturulmus acilmali")
        self.assertTrue(kontrolcu.muted)

    def test_eski_cihaz_da_acilmazsa_sessiz_gorusmede_kalinmaz(self):
        """Az once calisan cihaz da yoksa (cikarilmis) ayrilmak, sessiz kalmaktan iyi."""
        acilis = {"sayi": 0}

        def fabrika(session, send_frame):
            acilis["sayi"] += 1
            if acilis["sayi"] > 1:
                raise VoiceDeviceError("audio_format")
            return SahteSesCihazi(session, send_frame)

        kontrolcu = self._kontrolcu(fabrika)
        self._katil(kontrolcu)

        kontrolcu.set_devices(input_id=b"baska")

        # Once "yeni cihaz acilmadi", sonra "ses acilamadi": gercekten kapandi.
        self.assertEqual(self.hatalar, ["voice_device_switch", "voice_device"])
        self.assertEqual(kontrolcu.state, "off")
        self.assertIsNone(kontrolcu.audio)


class GorusmedeCihazDegisimiTests(_KontrolcuTestleri):
    """Kulaklik gorusme SIRASINDA cikarilip takiliyor.

    Inceleme buldu: liste tazeleniyordu ama ses karti cikarilan cihazda
    kaliyordu; gorusme sessizce sagir ve dilsiz oluyordu.
    """

    GIRIS_VARSAYILAN = b"mic-varsayilan"
    CIKIS_VARSAYILAN = b"spk-varsayilan"

    def _kimlikli(self, girisler, cikislar, patlat=lambda: False):
        """Gercek kart gibi GERCEKTE actigi cihazi bildiren sahte kart."""
        self.takili = {"giris": set(girisler), "cikis": set(cikislar)}
        self.acilanlar = []

        def fabrika(session, send_frame):
            if patlat():
                raise VoiceDeviceError("audio_format")
            kart = SahteSesCihazi(session, send_frame)
            g, c = kontrolcu.input_device, kontrolcu.output_device
            kart.input_device_id = g if g in self.takili["giris"] else self.GIRIS_VARSAYILAN
            kart.output_device_id = c if c in self.takili["cikis"] else self.CIKIS_VARSAYILAN
            self.acilanlar.append(kart)
            return kart

        kontrolcu = self._kontrolcu(fabrika)
        return kontrolcu

    def _kulaklikla_gorusmede(self, **kw):
        kontrolcu = self._kimlikli(
            {b"kulaklik-mic", self.GIRIS_VARSAYILAN}, {self.CIKIS_VARSAYILAN}, **kw
        )
        kontrolcu.set_devices(input_id=b"kulaklik-mic")
        self._katil(kontrolcu)
        self.assertEqual(kontrolcu.audio.input_device_id, b"kulaklik-mic")
        return kontrolcu

    def test_kullanilan_kulaklik_cikarilinca_varsayilana_gecilir(self):
        kontrolcu = self._kulaklikla_gorusmede()
        kontrolcu.set_muted(True)
        oturum, eski = kontrolcu.session, kontrolcu.audio

        self.takili["giris"] = {self.GIRIS_VARSAYILAN}
        kontrolcu.on_devices_changed(self.takili["giris"], self.takili["cikis"])

        self.assertTrue(eski.stopped)
        self.assertEqual(kontrolcu.audio.input_device_id, self.GIRIS_VARSAYILAN)
        self.assertTrue(kontrolcu.audio.muted, "susturma korunmali")
        self.assertIs(kontrolcu.session, oturum, "gorusme kesilmemeli")
        self.assertEqual(kontrolcu.input_device, b"kulaklik-mic", "secim silinmemeli")

    def test_secili_kulaklik_geri_takilinca_ona_donulur(self):
        kontrolcu = self._kulaklikla_gorusmede()
        self.takili["giris"] = {self.GIRIS_VARSAYILAN}
        kontrolcu.on_devices_changed(self.takili["giris"], self.takili["cikis"])

        self.takili["giris"] = {b"kulaklik-mic", self.GIRIS_VARSAYILAN}
        kontrolcu.on_devices_changed(self.takili["giris"], self.takili["cikis"])

        self.assertEqual(kontrolcu.audio.input_device_id, b"kulaklik-mic")

    def test_ilgisiz_bir_cihaz_degisince_kart_yeniden_acilmaz(self):
        kontrolcu = self._kulaklikla_gorusmede()
        kart = kontrolcu.audio
        kontrolcu.on_devices_changed(
            self.takili["giris"] | {b"yeni-webcam-mic"}, self.takili["cikis"]
        )
        self.assertIs(kontrolcu.audio, kart)
        self.assertFalse(kart.stopped)

    def test_cikarildiktan_sonra_hic_acilamazsa_ayrilir(self):
        durum = {"patla": False}
        kontrolcu = self._kulaklikla_gorusmede(patlat=lambda: durum["patla"])
        durum["patla"] = True
        kontrolcu.on_devices_changed({self.GIRIS_VARSAYILAN}, self.takili["cikis"])
        self.assertEqual(self.hatalar, ["voice_device"])
        self.assertEqual(kontrolcu.state, "off")

    def test_gorusme_yokken_hicbir_sey_yapmaz(self):
        kontrolcu = self._kimlikli({self.GIRIS_VARSAYILAN}, {self.CIKIS_VARSAYILAN})
        kontrolcu.on_devices_changed(set(), set())
        self.assertEqual(self.acilanlar, [])

    def test_kimligini_bildirmeyen_kart_yok_sayilir(self):
        """Eski sahte kartlar (ve kimlik tasimayan herhangi bir kart) bozulmaz."""
        kontrolcu = self._katil(self._kontrolcu())
        kart = kontrolcu.audio
        kontrolcu.on_devices_changed(set(), set())
        self.assertIs(kontrolcu.audio, kart)


class _PencereTestleri(_QtTestCase):
    """Pencere testlerinin ortak yardimcilari; kendisi test icermiyor."""

    def _pencere(self, ayarlar=None, yukle=True):
        """Pencere; `yukle` ise cihaz listesi GERCEK sinyal yoluyla istenir.

        Liste acilista okunmuyor (bkz. TembelYuklemeTests); listeye bakan
        testler onu kullanicinin yapacagi gibi istiyor.
        """
        from apps.proxychat.ui import ProxyChatWindow

        if ayarlar is None:
            ayarlar, self.ayar_yolu = izole_ayarlar_ve_yol(self)
        pencere = ProxyChatWindow(ayarlar)
        self.addCleanup(pencere.close)
        pencere._reconnect_timer.stop()
        if yukle:
            pencere.chat_page.voice_devices_needed.emit()
        return pencere

    @staticmethod
    def _ipucu_iste(dugme):
        """Fare uzerine gelmis gibi: Qt'nin ipucu olayini gonderir."""
        from PySide6.QtCore import QEvent, QPoint
        from PySide6.QtGui import QHelpEvent

        QApplication.sendEvent(dugme, QHelpEvent(QEvent.Type.ToolTip, QPoint(4, 4), dugme.mapToGlobal(QPoint(4, 4))))
        return dugme.toolTip()

    @staticmethod
    def _satirlar(kutu):
        return [(kutu.itemText(i), kutu.itemData(i)) for i in range(kutu.count())]

class PencereCihazTests(_PencereTestleri):
    def test_liste_sistem_varsayilaniyla_baslar(self):
        pencere = self._pencere()
        kutu = pencere.chat_page.voice_input_box
        self.assertEqual(
            self._satirlar(kutu),
            [
                (t("chat.voice_device_default"), ""),
                ("Dahili mikrofon", b"mic-ic".hex()),
                ("Kulaklik mikrofonu", b"mic-kulaklik".hex()),
            ],
        )
        self.assertEqual(kutu.currentIndex(), 0)
        self.assertEqual(pencere.chat_page.voice_output_box.count(), 3)

    def test_kayitli_cihaz_acilista_secili_gelir(self):
        ayarlar, self.ayar_yolu = izole_ayarlar_ve_yol(self)
        ayarlar.save_voice_devices(input_id=b"mic-kulaklik", output_id=b"spk-kulaklik")
        pencere = self._pencere(ayarlar)
        sayfa = pencere.chat_page
        self.assertEqual(sayfa.voice_input_box.currentText(), "Kulaklik mikrofonu")
        self.assertEqual(sayfa.voice_output_box.currentText(), "Kulaklik")
        self.assertEqual(pencere.voice.input_device, b"mic-kulaklik")

    def test_secim_kontrolcuye_ve_kayda_gider(self):
        pencere = self._pencere()
        kutu = pencere.chat_page.voice_input_box
        kutu.setCurrentIndex(2)
        kutu.activated.emit(2)  # kullanicinin secmesi

        self.assertEqual(pencere.voice.input_device, b"mic-kulaklik")
        yeniden = ChatSettings(QSettings(self.ayar_yolu, QSettings.Format.IniFormat))
        self.assertEqual(yeniden.load_voice_devices()[0], b"mic-kulaklik")

    def test_kayda_cihazin_adi_degil_yalnizca_kimligi_yazilir(self):
        """Bluetooth cihaz adlarinda kisi adi olabiliyor ("Ayse'nin AirPods'u")."""
        voice.audio_devices.degistir(girisler=[(b"bt-1", "Ayse'nin AirPods'u")])
        pencere = self._pencere()
        kutu = pencere.chat_page.voice_input_box
        kutu.setCurrentIndex(1)
        kutu.activated.emit(1)

        with open(self.ayar_yolu, encoding="utf-8", errors="replace") as f:
            icerik = f.read()
        self.assertNotIn("AirPods", icerik)
        self.assertNotIn("Ayse", icerik)
        self.assertIn(b"bt-1".hex(), icerik)

    def test_cikarilan_kulaklik_geri_takilinca_yine_secili_gelir(self):
        """Cikarildiginda 'sistem varsayilani' gorunur ama kayit silinmez."""
        ayarlar, self.ayar_yolu = izole_ayarlar_ve_yol(self)
        ayarlar.save_voice_devices(input_id=b"mic-kulaklik")
        pencere = self._pencere(ayarlar)
        kutu = pencere.chat_page.voice_input_box
        kulaklikli = voice.audio_devices.girisler

        voice.audio_devices.degistir(girisler=[(b"mic-ic", "Dahili mikrofon")])
        self.assertEqual(kutu.currentIndex(), 0, "takili degil: sistem varsayilani gorunur")
        yeniden = ChatSettings(QSettings(self.ayar_yolu, QSettings.Format.IniFormat))
        self.assertEqual(yeniden.load_voice_devices()[0], b"mic-kulaklik", "kayit silinmemeli")

        voice.audio_devices.degistir(girisler=kulaklikli)
        self.assertEqual(kutu.currentText(), "Kulaklik mikrofonu")

    def test_cihaz_acilamazsa_arayuz_ve_kayit_kullanilana_uyar(self):
        """Liste bir cihazi gosterirken ses baskasindan gelmemeli."""
        pencere = self._pencere()
        pencere.voice.set_devices(input_id=b"mic-ic")
        pencere.chat_page.select_voice_devices(b"mic-ic", b"")
        # Kontrolcu yeni cihazi acamadi ve eskisine dondu: istegi yok sayiyoruz.
        pencere.voice.set_devices = lambda **_kw: None

        kutu = pencere.chat_page.voice_input_box
        kutu.setCurrentIndex(2)
        kutu.activated.emit(2)

        self.assertEqual(kutu.currentText(), "Dahili mikrofon")
        yeniden = ChatSettings(QSettings(self.ayar_yolu, QSettings.Format.IniFormat))
        self.assertEqual(yeniden.load_voice_devices()[0], b"mic-ic")

    # --- ac/kapa satiri -------------------------------------------------
    # Cihaz secimi bir kerelik ayar; panelde surekli yer kaplamamali.
    # isVisible() degil isHidden(): hic gosterilmemis bir pencerede butun
    # alt ogeler "gorunmez" sayiliyor ve test hata varken de geciyordu.

    def test_cihaz_bolumu_acilista_kapali(self):
        sayfa = self._pencere().chat_page
        self.assertTrue(sayfa.voice_devices_section.isHidden())
        self.assertFalse(sayfa.voice_devices_button.isChecked())
        self.assertTrue(sayfa.voice_devices_button.text().startswith("▸"))

    def test_dugme_bolumu_acip_kapatir(self):
        sayfa = self._pencere().chat_page
        sayfa.voice_devices_button.click()
        self.assertFalse(sayfa.voice_devices_section.isHidden())
        self.assertTrue(sayfa.voice_devices_button.text().startswith("▾"))
        sayfa.voice_devices_button.click()
        self.assertTrue(sayfa.voice_devices_section.isHidden())
        self.assertTrue(sayfa.voice_devices_button.text().startswith("▸"))

    def test_kapaliyken_secili_cihazlar_ipucunda_gorunur(self):
        """Liste bir kez okunduktan sonra bolum kapaliyken de cihazlar bilinmeli.

        Bolum bir kez acilip kapatiliyor (liste o an okunuyor); kapali
        satirin ipucu artik secili cihazlarin adini gostermeli.
        """
        ayarlar, self.ayar_yolu = izole_ayarlar_ve_yol(self)
        ayarlar.save_voice_devices(input_id=b"mic-kulaklik")
        sayfa = self._pencere(ayarlar, yukle=False).chat_page
        sayfa.voice_devices_button.click()
        sayfa.voice_devices_button.click()
        self.assertTrue(sayfa.voice_devices_section.isHidden())
        ipucu = self._ipucu_iste(sayfa.voice_devices_button)
        self.assertIn("Kulaklik mikrofonu", ipucu)
        self.assertIn(t("chat.voice_device_default"), ipucu)

        sayfa.voice_output_box.setCurrentIndex(2)
        self.assertIn("Kulaklik", sayfa.voice_devices_button.toolTip().split("\n")[1])

    def test_acik_bolum_kartin_uzerinde_serit_olarak_gorunmez(self):
        """Genel `QWidget { background }` kurali kapsayiciyi boyuyordu.

        Bolumun zemini kartin zeminiyle ayni olmali; olcmek icin panel
        uygulamanin stil sayfasiyla cizilip pikseller karsilastiriliyor.
        """
        from apps.proxychat.ui import build_stylesheet

        pencere = self._pencere()
        pencere.setStyleSheet(build_stylesheet())
        sayfa = pencere.chat_page
        sayfa.voice_devices_button.click()
        resim = sayfa.voice_panel.grab().toImage()
        bolum = sayfa.voice_devices_section
        kose = bolum.mapTo(sayfa.voice_panel, bolum.rect().topRight())
        kart = resim.pixelColor(8, resim.height() // 2).name()
        bolum_zemini = resim.pixelColor(kose.x() - 2, kose.y() + 2).name()
        self.assertEqual(bolum_zemini, kart)

    def test_dil_degisince_ac_kapa_satiri_da_cevrilir(self):
        sayfa = self._pencere().chat_page
        once = sayfa.voice_devices_button.text()
        set_language("tr")
        sayfa.retranslate()
        self.assertNotEqual(sayfa.voice_devices_button.text(), once)
        self.assertIn("Ses cihazları", sayfa.voice_devices_button.text())
        self.assertIn("Mikrofon:", sayfa.voice_devices_button.toolTip())

    def test_dil_degisince_sistem_varsayilani_da_cevrilir(self):
        """Varsayilan dil Ingilizce: Turkceye gecip metnin DEGISTIGI dogrulaniyor.

        Bu testin ilk hali Ingilizceden Ingilizceye geciyordu ve ceviri hic
        yapilmasa da geciyordu (kasten bozulan kodla denendi). Once/sonra
        karsilastirmasi o tuzagi kapatiyor.
        """
        pencere = self._pencere()
        kutu = pencere.chat_page.voice_input_box
        once = kutu.itemText(0)

        set_language("tr")
        pencere.chat_page.retranslate()

        self.assertNotEqual(kutu.itemText(0), once, "dil degisti ama metin degismedi")
        self.assertEqual(kutu.itemText(0), "Sistem varsayılanı")
        self.assertEqual(pencere.chat_page.voice_input_label.text(), "Mikrofon")
        self.assertEqual(pencere.chat_page.voice_output_box.itemText(0), "Sistem varsayılanı")


class TembelYuklemeTests(_PencereTestleri):
    """Cihaz listesi acilista OKUNMAZ; ilk ihtiyacta bir kez okunur.

    Paketlenmis exe her acilista kendini yepyeni bir klasore aciyor, yani
    QtMultimedia'nin DLL'leri her seferinde ilk kez yukleniyor. Listeyi
    acilista okumak bu maliyeti, zaten kapali duran bir satir icin, acilisa
    ekliyordu.
    """

    def test_acilista_liste_okunmaz_ama_kayitli_secim_yuklenir(self):
        ayarlar, self.ayar_yolu = izole_ayarlar_ve_yol(self)
        ayarlar.save_voice_devices(input_id=b"mic-kulaklik")
        pencere = self._pencere(ayarlar, yukle=False)
        self.assertEqual(voice.audio_devices.okuma, 0, "liste acilista okunmamali")
        self.assertEqual(voice.audio_devices.dinleyici_sayisi, 0, "izleyici de kurulmamali")
        self.assertEqual(
            pencere.voice.input_device, b"mic-kulaklik",
            "sese katilinca dogru cihaz acilsin diye secim yine de yuklenmeli",
        )

    def test_okunmadan_once_ipucu_genel(self):
        sayfa = self._pencere(yukle=False).chat_page
        self.assertEqual(sayfa.voice_devices_button.toolTip(), t("chat.voice_devices_tooltip"))

    def test_satir_acilinca_liste_bir_kez_okunur(self):
        sayfa = self._pencere(yukle=False).chat_page
        sayfa.voice_devices_button.click()
        self.assertEqual(voice.audio_devices.okuma, 1)
        self.assertEqual(voice.audio_devices.dinleyici_sayisi, 1)
        self.assertEqual(sayfa.voice_input_box.count(), 3)

        sayfa.voice_devices_button.click()
        sayfa.voice_devices_button.click()
        self.assertEqual(voice.audio_devices.okuma, 1, "ikinci acilista yeniden okunmamali")
        self.assertEqual(voice.audio_devices.dinleyici_sayisi, 1, "izleyici bir kez kurulmali")

    def test_fareyle_uzerine_gelmek_listeyi_okumaz(self):
        """Inceleme buldu: ipucu istenince liste okunuyordu.

        Paketlenmis exe'de o ilk yukleme ~1 sn suruyor; yalnizca fareyi
        satirin uzerinden gecirmek pencereyi donduruyordu. Liste artik
        yalnizca acik bir eylemle (satiri acmak, sese katilmak) okunuyor.
        """
        sayfa = self._pencere(yukle=False).chat_page
        ipucu = self._ipucu_iste(sayfa.voice_devices_button)
        self.assertEqual(voice.audio_devices.okuma, 0)
        self.assertEqual(ipucu, t("chat.voice_devices_tooltip"))

    def test_kulaklik_takilip_cikarilinca_kontrolcuye_haber_verilir(self):
        """Gorusmedeki kart kaybolan cihazda kalmasin diye (bkz. kontrolcu testleri)."""
        pencere = self._pencere()
        bildirimler = []
        pencere.voice.on_devices_changed = lambda g, c: bildirimler.append((g, c))

        voice.audio_devices.degistir(girisler=[(b"mic-ic", "Dahili mikrofon")])

        self.assertEqual(bildirimler[-1][0], {b"mic-ic"})
        self.assertEqual(bildirimler[-1][1], {b"spk-ic", b"spk-kulaklik"})

    def test_run_app_zamansiz_verilen_ekranla_cokmez(self):
        """Inceleme buldu: run_app(splash) None'dan cikarma yapip cokuyordu."""
        from PySide6.QtCore import QTimer
        from apps.proxychat import ui

        ayarlar = izole_ayarlar_ve_yol(self)[0]
        bekleme = []
        ekran = mock.Mock()
        with mock.patch.object(ui, "ChatSettings", return_value=ayarlar), \
                mock.patch.object(ui, "ProxyChatWindow", return_value=mock.Mock()), \
                mock.patch.object(ui, "set_logging_enabled"), \
                mock.patch.object(QApplication, "setStyleSheet"), \
                mock.patch.object(QApplication, "exec", return_value=0), \
                mock.patch.object(QTimer, "singleShot", side_effect=lambda ms, f: bekleme.append(ms)):
            self.assertEqual(ui.run_app(ekran), 0)
        self.assertEqual(len(bekleme), 1)
        self.assertGreater(bekleme[0], 0, "ekran yeni gosterildi sayilmali: en az sure beklenir")

    def test_sese_katilinca_liste_okunur(self):
        """Ses karti o anda zaten yukleniyor; liste bedavaya geliyor."""
        pencere = self._pencere(yukle=False)
        pencere.voice.state_changed.emit("on")
        self.assertEqual(voice.audio_devices.okuma, 1)
        self.assertEqual(pencere.chat_page.voice_input_box.count(), 3)

    def test_sesten_cikmak_listeyi_okumaz(self):
        pencere = self._pencere(yukle=False)
        pencere.voice.state_changed.emit("joining")
        pencere.voice.state_changed.emit("off")
        self.assertEqual(voice.audio_devices.okuma, 0)


if __name__ == "__main__":
    unittest.main()
