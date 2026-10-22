"""Baskasinin sectigi metin HTML olarak cizilmemeli.

QLabel'in varsayilani AutoText: HTML'ye benzeyen metni zengin metin cizer ve
<img> etiketindeki dosyayi yukler. Oda adini baska kullanicilar seciyor;
Windows'ta \\\\sunucu\\pay gibi bir yol programa o sunucuya SMB baglantisi
actirir. Ipuclari da ayni sekilde yorumlaniyor; cihaz adini cihazin sahibi
koyar (Bluetooth).

Burada ag kullanilmaz: saldiri metni diskteki bir PNG'yi gosterir. Resim
yuklenirse etiket resim boyuna buyur -- duzeltmeden once 48x12 olan etiket
1036x1024 oluyordu.
"""

import html
from pathlib import Path

from PySide6.QtCore import Qt

from apps.proxychat.ui import ChatPage, ConnectionController
from tests.test_proxychat_ui import _QtTestCase

KOK = Path(__file__).resolve().parent.parent
RESIM = next(KOK.glob("assets/*.png")).as_posix()
SALDIRI = f"<img src='file:///{RESIM}'>"


class EtiketTests(_QtTestCase):
    def sayfa(self) -> ChatPage:
        page = ChatPage(ConnectionController())
        self.addCleanup(page.deleteLater)
        page.controller.switch_room = lambda room: None
        return page

    def test_oda_adi_resim_yukletmiyor(self):
        page = self.sayfa()

        page.switch_room(SALDIRI)

        self.assertEqual(page.channel_title.text(), f"#{SALDIRI}")
        self.assertEqual(page.channel_title.textFormat(), Qt.TextFormat.PlainText)
        self.assertLess(page.channel_title.sizeHint().height(), 100)

    def test_veri_gosteren_etiketler_duz_metin(self):
        page = self.sayfa()
        window = self._window()

        etiketler = {
            "channel_title": page.channel_title,
            "channel_status": page.channel_status,
            "connection_status": page.connection_status,
            "voice_status": page.voice_status,
            "status_label": window.connect_page.status_label,
        }
        for ad, etiket in etiketler.items():
            with self.subTest(etiket=ad):
                self.assertEqual(etiket.textFormat(), Qt.TextFormat.PlainText)


class IpucuTests(_QtTestCase):
    def sayfa_cihazlarla(self, ad: str) -> ChatPage:
        page = ChatPage(ConnectionController())
        self.addCleanup(page.deleteLater)
        page.set_voice_devices([(b"\x01", ad)], [(b"\x02", "Hoparlor")], b"\x01", b"\x02")
        page._render_voice_devices_button()
        return page

    def test_cihaz_adi_ipucunda_kacislaniyor(self):
        page = self.sayfa_cihazlarla(SALDIRI)

        for ad, ipucu in (
            ("mikrofon listesi", page.voice_input_box.toolTip()),
            ("ses cihazlari satiri", page.voice_devices_button.toolTip()),
        ):
            with self.subTest(ipucu=ad):
                self.assertNotIn("<img", ipucu)
                self.assertIn(html.escape(SALDIRI), ipucu)

    def test_ozet_ipucunda_satir_sonu_korunuyor(self):
        page = self.sayfa_cihazlarla("Kulaklik mikrofonu")

        ipucu = page.voice_devices_button.toolTip()

        self.assertIn("pre-wrap", ipucu)
        self.assertIn("Kulaklik mikrofonu\n", ipucu)
