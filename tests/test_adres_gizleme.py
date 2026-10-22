"""IP adresi ekranda varsayilan olarak gizli.

Ekranini yayinlayan ya da video ceken biri, sohbet ekranindaki "Baglandi:
25.x.x.x" satirindan ve Host'un paylasilacak adres listesinden adresini
farkinda olmadan sizdiriyordu. Adres artik maske; "Adresi goster" basili
tutulunca gorunuyor, birakinca gizleniyor. "Adresi kopyala" adresi ekranda
gostermeden panoya aliyor. Yalnizca bu makineyi gosteren adres (127.x, Demo)
gizli bir bilgi degil, oldugu gibi kaliyor. Baglanti ekraninda da ayni kural:
Join'in IP alani ve Host'un ag listesi maskeli, "Adresi goster" basili tutulunca
gorunuyor.

Testler gercek panoya dokunmuyor: sahte bir pano yerlestiriliyor.
"""

import os
import tempfile
import unittest
from unittest import mock

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from apps.proxychat.i18n import set_language
from apps.proxychat.settings import ChatSettings
from apps.proxychat.ui import ADDRESS_MASK, ChatPage, ConnectionController, ConnectPage

HOST = "25.12.34.56"
LAN = "192.0.2.10"   # belgeleme icin ayrilmis adres (RFC 5737), gercek degil


class SahtePano:
    def __init__(self):
        self.mime = None

    def setMimeData(self, mime):
        self.mime = mime


class _Sayfa(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "en")
        self.page = ChatPage(ConnectionController())
        self.addCleanup(self.page.deleteLater)
        self.page.retranslate()

    def host_olarak(self):
        self.page.show_connected({"host": HOST, "port": 5555, "encrypted": True, "share_ips": [HOST, LAN]})

    def ekrandaki_metin(self) -> str:
        return self.page.connection_status.text() + "\n" + self.page.server_hint.toPlainText()


class VarsayilanGizliTests(_Sayfa):
    def test_adresler_maskeli(self):
        self.host_olarak()

        metin = self.ekrandaki_metin()
        for adres in (HOST, LAN):
            self.assertNotIn(adres, metin)
        self.assertIn(ADDRESS_MASK, metin)
        self.assertIn(":5555", metin)

    def test_basili_tutunca_gorunur_birakinca_gizlenir(self):
        self.host_olarak()

        self.page.reveal_address_button.pressed.emit()
        self.assertIn(HOST, self.ekrandaki_metin())
        self.assertIn(LAN, self.page.server_hint.toPlainText())

        self.page.reveal_address_button.released.emit()
        self.assertNotIn(HOST, self.ekrandaki_metin())
        self.assertNotIn(LAN, self.ekrandaki_metin())

    def test_dil_degisince_gizli_kaliyor(self):
        self.host_olarak()

        set_language("tr")
        self.page.retranslate()

        self.assertNotIn(HOST, self.ekrandaki_metin())

    def test_yeniden_baglaninca_gizli_kaliyor(self):
        self.host_olarak()
        self.page.reveal_address_button.pressed.emit()
        self.page.reveal_address_button.released.emit()

        self.page.show_connected({"host": HOST, "port": 5555, "encrypted": True})

        self.assertNotIn(HOST, self.ekrandaki_metin())


class DemoTests(_Sayfa):
    def test_yerel_adres_gizlenmiyor_dugme_yok(self):
        self.page.show_connected({"host": "127.0.0.1", "port": 5555, "encrypted": True})

        self.assertIn("127.0.0.1:5555", self.page.connection_status.text())
        self.assertTrue(self.page.reveal_address_button.isHidden())
        self.assertTrue(self.page.copy_address_button.isHidden())


class DugmeTests(_Sayfa):
    def test_katilanda_kopyala_yok_goster_var(self):
        self.page.show_connected({"host": HOST, "port": 5555, "encrypted": True})

        self.assertFalse(self.page.reveal_address_button.isHidden())
        self.assertTrue(self.page.copy_address_button.isHidden())

    def test_hostta_ikisi_de_var(self):
        self.host_olarak()

        self.assertFalse(self.page.reveal_address_button.isHidden())
        self.assertFalse(self.page.copy_address_button.isHidden())

    def test_kopyala_adresi_gostermeden_panoya_aliyor(self):
        self.host_olarak()
        pano = SahtePano()

        with mock.patch("apps.proxychat.ui.QApplication.clipboard", return_value=pano):
            self.page.copy_addresses()

        self.assertEqual(pano.mime.text(), f"{HOST}:5555\n{LAN}:5555")
        self.assertTrue(any("CanIncludeInClipboardHistory" in f for f in pano.mime.formats()))
        self.assertNotIn(HOST, self.ekrandaki_metin())
        self.assertEqual(self.page.copy_address_button.text(), "Copied")


class BaglantiEkraniTests(unittest.TestCase):
    """Baglanti ekrani: saklanan IP program acilir acilmaz alanda, makinenin
    adresleri de Host'un ag listesinde gorunuyordu."""

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "en")
        yama = mock.patch("apps.proxychat.ui.get_local_ipv4_addresses", return_value=[HOST, LAN, "192.0.2.20"])
        yama.start()
        self.addCleanup(yama.stop)
        tutamac, ini = tempfile.mkstemp(suffix=".ini")
        os.close(tutamac)
        self.addCleanup(os.remove, ini)
        self.page = ConnectPage(ChatSettings(QSettings(ini, QSettings.Format.IniFormat)))
        self.addCleanup(self.page.deleteLater)

    def liste(self) -> str:
        return "\n".join(self.page.listen_box.itemText(i) for i in range(self.page.listen_box.count()))

    def test_ip_alani_varsayilan_maskeli_odakta_da(self):
        self.page.host_edit.setText(HOST)
        self.page.show()
        self.page.host_edit.setFocus()
        QApplication.processEvents()

        self.assertNotIn(HOST, self.page.host_edit.displayText())

    def test_yazarken_gorunur_bitince_maskelenir(self):
        self.page.show()
        self.page.host_edit.setFocus()
        QTest.keyClicks(self.page.host_edit, HOST)
        self.assertEqual(self.page.host_edit.displayText(), HOST)

        self.page.host_edit.editingFinished.emit()   # Enter ya da alandan cikis

        self.assertNotIn(HOST, self.page.host_edit.displayText())
        self.assertEqual(self.page.host_edit.text(), HOST)

    def test_kayitli_ipye_yazmak_onu_silmiyor(self):
        # Qt'nin PasswordEchoOnEdit modu ilk tusta alani temizliyordu.
        self.page.host_edit.setText("25.12.34.5")
        self.page.show()
        self.page.host_edit.setFocus()
        QTest.keyClick(self.page.host_edit, Qt.Key.Key_End)
        QTest.keyClicks(self.page.host_edit, "6")

        self.assertEqual(self.page.host_edit.text(), HOST)

    def test_ip_alani_basili_tutunca_gorunur(self):
        self.page.host_edit.setText(HOST)

        self.page.reveal_address_button.pressed.emit()
        self.assertEqual(self.page.host_edit.displayText(), HOST)

        self.page.reveal_address_button.released.emit()
        self.assertNotIn(HOST, self.page.host_edit.displayText())

    def test_ag_listesi_maskeli_tur_yazili(self):
        self.page.mode_box.setCurrentText("Host")

        metin = self.liste()
        for adres in (HOST, LAN):
            self.assertNotIn(adres, metin)
        self.assertIn("Hamachi", metin)
        # Ayni turden iki ag maskeliyken ayirt edilebilsin diye numaralaniyor.
        self.assertIn("Local network 1", metin)
        self.assertIn("Local network 2", metin)
        self.assertIn("0.0.0.0", metin)   # "Butun aglar" bir adres degil

    def test_ag_listesi_basili_tutunca_gorunur_secim_bozulmaz(self):
        self.page.mode_box.setCurrentText("Host")
        self.page.listen_box.setCurrentIndex(self.page.listen_box.findData(LAN))

        self.page.reveal_address_button.pressed.emit()
        self.assertIn(HOST, self.liste())
        self.assertIn(LAN, self.liste())
        self.page.reveal_address_button.released.emit()

        self.assertNotIn(LAN, self.liste())
        self.assertEqual(self.page.listen_box.currentData(), LAN)

    def test_dil_degisince_liste_gizli_kaliyor(self):
        self.page.mode_box.setCurrentText("Host")

        set_language("tr")
        self.page.retranslate()

        self.assertNotIn(HOST, self.liste())
        self.assertIn("Yerel ağ", self.liste())

    def test_dugme_join_ve_hostta_var_demoda_yok(self):
        for mod, gorunur in (("Join", True), ("Host", True), ("Demo", False)):
            self.page.mode_box.setCurrentText(mod)
            self.assertEqual(not self.page.address_row.isHidden(), gorunur, mod)


if __name__ == "__main__":
    unittest.main()
