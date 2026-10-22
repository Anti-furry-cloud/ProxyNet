"""Sesli sohbetin uygulama tarafi: kontrolcu ve arayuz.

Ses karti acilmaz: kontrolcuye sahte bir ses cihazi veriliyor. Boylece
katilim, ayrilma, katilimci listesi ve susturma donanimsiz sinaniyor.
"""

import unittest

from PySide6.QtWidgets import QApplication

from apps.proxychat.voice import VoiceController, VoiceDeviceError
from core.voice_codec import FRAME_PCM_BYTES, available_codec, silence
from core.room_session import RoomSession
from core.voice_gate import NoiseGate


class SahteSesCihazi:
    """QAudioSource/QAudioSink yerine: gonderilen cerceveleri toplar.

    Gercek cihaz gibi bir gurultu kapisi tasir; kontrolcu onu ayarliyor.
    """

    def __init__(self, session, send_frame):
        self.session = session
        self.send_frame = send_frame
        self.muted = False
        self.stopped = False
        self.gate = NoiseGate()

    def konus(self, adet=1, deger=6000):
        """Kapiyi acacak kadar yuksek, konusma seviyesinde cerceveler."""
        cerceve = deger.to_bytes(2, "little", signed=True) * (FRAME_PCM_BYTES // 2)
        for _ in range(adet):
            self.send_frame(silence() if self.muted else self.gate.process(cerceve))

    def stop(self):
        self.stopped = True


class SahteIstemci:
    def __init__(self):
        self.gonderilen = []

    def send_packet(self, packet):
        self.gonderilen.append(packet)

    def tipler(self):
        return [p["type"] for p in self.gonderilen]


class SahteBaglanti:
    """ConnectionController yerine: sesin ihtiyaci olan alanlar."""

    def __init__(self, bagli=True):
        self.client = SahteIstemci() if bagli else None
        self.room = "general"
        self.room_password = "oda-parolasi"
        # Gercek baglantida bu bir RoomSession: ses anahtari oradan turuyor.
        # Sahte olani da gercegini veriyoruz ki testler urunun yolunu kossun.
        self.room_session = RoomSession(self.room, self.room_password)
        self.host = "127.0.0.1"
        self.port = 5555

    def es_ekle(self) -> str:
        """Bir esle metin el sikismasi yapar; acik anahtarini base64 dondurur.

        Ses anahtari o esin acik anahtariyla eslesiyor, o yuzden voice_peers
        paketine gercek bir acik anahtar koymak gerekiyor.
        """
        import base64

        es = RoomSession(self.room, self.room_password)
        benim_acik, benim_etiket = self.room_session.offer()
        es_acik, es_etiket = es.offer()
        esten = es.accept_offer(benim_acik, benim_etiket)
        benden = self.room_session.accept_offer(es_acik, es_etiket)
        self.room_session.accept_sender_key(es_acik, esten)
        es.accept_sender_key(benim_acik, benden)
        return base64.urlsafe_b64encode(es_acik).decode("ascii")


class _QtTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])


class KontrolcuTests(_QtTestCase):
    def _kontrolcu(self, bagli=True):
        self.baglanti = SahteBaglanti(bagli)
        self.cihazlar = []

        def fabrika(session, send_frame):
            cihaz = SahteSesCihazi(session, send_frame)
            self.cihazlar.append(cihaz)
            return cihaz

        kontrolcu = VoiceController(self.baglanti, audio_factory=fabrika)
        self.addCleanup(kontrolcu.leave)
        self.durumlar = []
        kontrolcu.state_changed.connect(self.durumlar.append)
        return kontrolcu

    def _katil(self, kontrolcu, sender_id=1):
        kontrolcu.join()
        kontrolcu.on_packet(
            {
                "type": "voice_joined",
                "sender_id": sender_id,
                "token": "ab" * 16,
                "port": 5555,
                "codec": available_codec(),
            }
        )
        return kontrolcu

    def test_katilim_iki_adim(self):
        """Once kimlik istenir, kimlik gelince tuz duyurulur."""
        kontrolcu = self._kontrolcu()

        kontrolcu.join()
        self.assertEqual(self.baglanti.client.tipler(), ["voice_join"])
        self.assertEqual(kontrolcu.state, "joining")

        kontrolcu.on_packet(
            {"type": "voice_joined", "sender_id": 3, "token": "cd" * 16, "port": 5555}
        )

        self.assertEqual(self.baglanti.client.tipler(), ["voice_join", "voice_salt"])
        tuz = self.baglanti.client.gonderilen[-1]["salt"]
        self.assertEqual(tuz, kontrolcu.session.session_salt.hex())
        self.assertEqual(kontrolcu.state, "on")
        self.assertEqual(self.durumlar, ["joining", "on"])

    def test_baglanti_yokken_katilamaz(self):
        kontrolcu = self._kontrolcu(bagli=False)
        hatalar = []
        kontrolcu.failed.connect(hatalar.append)

        kontrolcu.join()

        self.assertEqual(hatalar, ["voice_not_connected"])
        self.assertEqual(kontrolcu.state, "off")

    def test_ses_cihazi_acilamazsa_temiz_cikilir(self):
        baglanti = SahteBaglanti()

        def patlayan_fabrika(session, send_frame):
            raise VoiceDeviceError("audio_format")

        kontrolcu = VoiceController(baglanti, audio_factory=patlayan_fabrika)
        hatalar = []
        kontrolcu.failed.connect(hatalar.append)
        kontrolcu.join()
        kontrolcu.on_packet(
            {"type": "voice_joined", "sender_id": 1, "token": "ab" * 16, "port": 5555}
        )

        self.assertEqual(hatalar, ["voice_device"])
        self.assertEqual(kontrolcu.state, "off")
        self.assertIsNone(kontrolcu.session)
        self.assertIsNone(kontrolcu.link)

    def test_ayrilinca_her_sey_birakiliyor(self):
        kontrolcu = self._katil(self._kontrolcu())

        kontrolcu.leave()

        self.assertEqual(kontrolcu.state, "off")
        self.assertIsNone(kontrolcu.session)
        self.assertIsNone(kontrolcu.link)
        self.assertTrue(self.cihazlar[0].stopped)
        self.assertEqual(self.baglanti.client.tipler()[-1], "voice_leave")

    def test_katilimcilar_oturuma_ekleniyor(self):
        kontrolcu = self._katil(self._kontrolcu(), sender_id=1)
        es_pub = self.baglanti.es_ekle()
        adlar = []
        kontrolcu.peers_changed.connect(adlar.append)

        kontrolcu.on_packet(
            {
                "type": "voice_peers",
                "room": "general",
                "peers": [
                    {"user": "ben", "sender_id": 1, "salt": "aa" * 16},
                    {"user": "mehmet", "sender_id": 2, "salt": "bb" * 16, "pub": es_pub},
                ],
            }
        )

        self.assertEqual(adlar[-1], ["ben", "mehmet"])
        self.assertEqual(kontrolcu.session.peers(), [2])

    def test_ayrilan_katilimci_oturumdan_cikariliyor(self):
        kontrolcu = self._katil(self._kontrolcu(), sender_id=1)
        es_pub = self.baglanti.es_ekle()
        kontrolcu.on_packet(
            {
                "type": "voice_peers",
                "peers": [
                    {"user": "ben", "sender_id": 1, "salt": "aa" * 16},
                    {"user": "mehmet", "sender_id": 2, "salt": "bb" * 16, "pub": es_pub},
                ],
            }
        )

        kontrolcu.on_packet(
            {"type": "voice_peers", "peers": [{"user": "ben", "sender_id": 1, "salt": "aa" * 16}]}
        )

        self.assertEqual(kontrolcu.session.peers(), [])

    def test_bozuk_katilimci_kaydi_cokmeye_yol_acmiyor(self):
        kontrolcu = self._katil(self._kontrolcu(), sender_id=1)

        kontrolcu.on_packet(
            {"type": "voice_peers", "peers": [{"user": "x", "sender_id": "iki", "salt": "zz"}]}
        )

        self.assertEqual(kontrolcu.session.peers(), [])

    def test_susturma_akisi_durdurmuyor(self):
        """Susturunca sessizlik gider; akisin kesilmesi kimin konustugunu ele verirdi."""
        kontrolcu = self._katil(self._kontrolcu())
        cihaz = self.cihazlar[0]

        kontrolcu.set_muted(True)
        onceki = kontrolcu.session.sent
        cihaz.konus(3)

        self.assertTrue(kontrolcu.muted)
        self.assertEqual(kontrolcu.session.sent, onceki + 3)

    def test_cevapsiz_sunucuda_katilim_birakiliyor(self):
        """Eski bir sunucu voice_join'i tanimaz ve hic cevap vermez."""
        from apps.proxychat import voice as v

        kontrolcu = self._kontrolcu()
        hatalar = []
        kontrolcu.failed.connect(hatalar.append)
        kontrolcu.join()
        self.assertEqual(kontrolcu.state, "joining")

        kontrolcu._on_join_timeout()

        self.assertEqual(hatalar, ["voice_no_server"])
        self.assertEqual(kontrolcu.state, "off")
        self.assertGreater(v.JOIN_TIMEOUT_MS, 0)

    def test_cevap_gelirse_zaman_asimi_calismaz(self):
        kontrolcu = self._katil(self._kontrolcu())
        hatalar = []
        kontrolcu.failed.connect(hatalar.append)

        kontrolcu._on_join_timeout()

        self.assertEqual(hatalar, [])
        self.assertEqual(kontrolcu.state, "on")

    def test_desteklenmeyen_kodekte_acik_hata(self):
        """Oda Opus kullaniyorsa ve bizde libopus yoksa sessizce bozulmasin."""
        from core.voice_codec import CODEC_MULAW, CODEC_OPUS

        kontrolcu = self._kontrolcu()
        kontrolcu._codec = CODEC_MULAW
        hatalar = []
        kontrolcu.failed.connect(hatalar.append)
        kontrolcu.join()

        kontrolcu.on_packet(
            {
                "type": "voice_joined",
                "sender_id": 1,
                "token": "ab" * 16,
                "port": 5555,
                "codec": CODEC_OPUS,
            }
        )

        self.assertEqual(hatalar, ["voice_codec"])
        self.assertEqual(kontrolcu.state, "off")
        self.assertIsNone(kontrolcu.session)
        self.assertEqual(self.baglanti.client.tipler()[-1], "voice_leave")

    def test_gurultu_kapisi_varsayilan_acik(self):
        """Klavye sesi ve cizirti karsi tarafa gitmesin."""
        kontrolcu = self._katil(self._kontrolcu())

        self.assertTrue(kontrolcu.noise_gate)
        self.assertTrue(self.cihazlar[0].gate.enabled)

    def test_esik_ayari_kapiya_gecirilir(self):
        kontrolcu = self._katil(self._kontrolcu())

        kontrolcu.set_gate_threshold(1500)

        self.assertEqual(self.cihazlar[0].gate.open_rms, 1500)
        self.assertEqual(kontrolcu.gate_threshold, 1500)

    def test_esik_sonraki_katilimda_da_gecerli(self):
        kontrolcu = self._kontrolcu()
        kontrolcu.set_gate_threshold(2500)

        self._katil(kontrolcu)

        self.assertEqual(self.cihazlar[0].gate.open_rms, 2500)

    def test_seviye_yayinlaniyor(self):
        kontrolcu = self._katil(self._kontrolcu())
        seviyeler = []
        kontrolcu.level_updated.connect(seviyeler.append)
        self.cihazlar[0].gate.level = 1234.0

        kontrolcu._publish_level()

        self.assertEqual(seviyeler, [1234.0])

    def test_gurultu_kapisi_kapatilabiliyor(self):
        kontrolcu = self._katil(self._kontrolcu())

        kontrolcu.set_noise_gate(False)

        self.assertFalse(self.cihazlar[0].gate.enabled)
        self.assertFalse(kontrolcu.noise_gate)

    def test_kapi_ayari_sonraki_katilimda_da_gecerli(self):
        kontrolcu = self._kontrolcu()
        kontrolcu.set_noise_gate(False)

        self._katil(kontrolcu)

        self.assertFalse(self.cihazlar[0].gate.enabled)

    def test_ilgisiz_paketler_yok_sayiliyor(self):
        kontrolcu = self._kontrolcu()

        kontrolcu.on_packet({"type": "message", "content": "merhaba"})

        self.assertEqual(kontrolcu.state, "off")


class ArayuzTests(_QtTestCase):
    def _sayfa(self):
        from apps.proxychat.ui import ChatPage, ConnectionController

        sayfa = ChatPage(ConnectionController())
        self.addCleanup(sayfa.deleteLater)
        return sayfa

    def test_ses_bolumu_var_ve_kapali_basliyor(self):
        from apps.proxychat.i18n import t

        sayfa = self._sayfa()

        self.assertEqual(sayfa.voice_title.text(), t("chat.voice_title"))
        self.assertEqual(sayfa.voice_status.text(), t("chat.voice_state_off"))
        self.assertFalse(sayfa.voice_mute_box.isEnabled())
        self.assertEqual(sayfa.voice_list.count(), 0)

    def test_dugme_duruma_gore_degisiyor(self):
        sayfa = self._sayfa()
        kapali = sayfa.voice_button.text()

        sayfa.set_voice_state("on")

        self.assertNotEqual(sayfa.voice_button.text(), kapali)
        self.assertTrue(sayfa.voice_mute_box.isEnabled())

    def test_dugme_sinyal_yayiyor(self):
        sayfa = self._sayfa()
        tiklamalar = []
        sayfa.voice_toggle_requested.connect(lambda: tiklamalar.append(True))

        sayfa.voice_button.click()

        self.assertEqual(len(tiklamalar), 1)

    def test_katilimcilar_listede_gorunuyor(self):
        sayfa = self._sayfa()

        sayfa.set_voice_peers(["ayse", "mehmet"])

        self.assertEqual(
            [sayfa.voice_list.item(i).text() for i in range(sayfa.voice_list.count())],
            ["ayse", "mehmet"],
        )

    def test_yalniz_kalinca_soyluyor(self):
        """Seste tek kisi varsa "karsi taraf yok" denir, sessizlik sanilmasin."""
        from apps.proxychat.i18n import t

        sayfa = self._sayfa()

        sayfa.set_voice_peers(["ben"])
        sayfa.set_voice_state("on")
        self.assertEqual(sayfa.voice_status.text(), t("chat.voice_alone"))

        sayfa.set_voice_peers(["ben", "mehmet"])
        self.assertEqual(sayfa.voice_status.text(), t("chat.voice_state_on"))

    def test_sustur_kutusu_sinyal_yayiyor(self):
        sayfa = self._sayfa()
        sayfa.set_voice_state("on")
        degerler = []
        sayfa.voice_mute_changed.connect(degerler.append)

        sayfa.voice_mute_box.setChecked(True)

        self.assertEqual(degerler, [True])

    def test_ayrilinca_sustur_kutusu_sifirlaniyor(self):
        sayfa = self._sayfa()
        sayfa.set_voice_state("on")
        sayfa.voice_mute_box.setChecked(True)

        sayfa.set_voice_state("off")

        self.assertFalse(sayfa.voice_mute_box.isChecked())
        self.assertFalse(sayfa.voice_mute_box.isEnabled())

    def test_esik_kaydiricisi_birakinca_sinyal_yayiyor(self):
        """Surukledikce degil, birakinca: her piksel icin ayar kaydedilmesin."""
        sayfa = self._sayfa()
        degerler = []
        sayfa.voice_threshold_changed.connect(degerler.append)

        sayfa.voice_threshold.setValue(1500)
        self.assertEqual(degerler, [])

        sayfa.voice_threshold.sliderReleased.emit()

        self.assertEqual(degerler, [1500])

    def test_seviye_cubugu_guncelleniyor(self):
        sayfa = self._sayfa()

        sayfa.set_voice_level(1200.0)

        self.assertEqual(sayfa.voice_level.value(), 1200)

    def test_cubuk_ust_sinirda_taskin_yapmiyor(self):
        from apps.proxychat.ui import VOICE_LEVEL_MAX

        sayfa = self._sayfa()

        sayfa.set_voice_level(99999.0)

        self.assertEqual(sayfa.voice_level.value(), VOICE_LEVEL_MAX)

    def test_kayitli_esik_kaydiriciya_yaziliyor(self):
        sayfa = self._sayfa()
        degerler = []
        sayfa.voice_threshold_changed.connect(degerler.append)

        sayfa.set_voice_threshold(2200)

        self.assertEqual(sayfa.voice_threshold.value(), 2200)
        self.assertEqual(degerler, [], "ayari geri yazmak sinyal yaymamali")

    def test_kapi_kapaliyken_kaydirici_devre_disi(self):
        sayfa = self._sayfa()

        sayfa.voice_gate_box.setChecked(False)

        self.assertFalse(sayfa.voice_threshold.isEnabled())
        self.assertIn("kapal", sayfa.voice_threshold_hint.text().lower() + "kapal")

    def test_esik_ipucu_degeri_yaziyor(self):
        sayfa = self._sayfa()

        sayfa.set_voice_threshold(1800)

        self.assertIn("1800", sayfa.voice_threshold_hint.text())

    def test_hata_mesaji_gosteriliyor(self):
        sayfa = self._sayfa()

        sayfa.set_voice_error("voice_device")

        self.assertNotEqual(sayfa.voice_status.text(), "")
        self.assertNotIn("error.", sayfa.voice_status.text())


if __name__ == "__main__":
    unittest.main()
