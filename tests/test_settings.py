"""Baglanti ayarlarinin saklanmasi.

Kritik nokta parola: THREAT_MODEL.md ilke 4 geregi diske duz yazilamaz.
Buradaki testler bunu dosyanin ham icerigine bakarak dogruluyor.
"""

import os
import sys
import tempfile
import unittest

from PySide6.QtCore import QSettings

from apps.proxychat.settings import ChatSettings, protect, unprotect


class _SettingsTestCase(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".ini")
        os.close(handle)
        self.addCleanup(lambda: os.path.exists(self.path) and os.remove(self.path))
        self.settings = ChatSettings(QSettings(self.path, QSettings.Format.IniFormat))

    def dosya_icerigi(self) -> str:
        with open(self.path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()


class DpapiTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "DPAPI yalnizca Windows'ta")
    def test_round_trip(self):
        blob = protect("gizli-parola")
        self.assertIsNotNone(blob)
        self.assertEqual(unprotect(blob), "gizli-parola")

    @unittest.skipUnless(sys.platform == "win32", "DPAPI yalnizca Windows'ta")
    def test_ciphertext_does_not_contain_the_password(self):
        blob = protect("cok-gizli-sey")
        self.assertNotIn("cok-gizli-sey", blob)

    @unittest.skipUnless(sys.platform == "win32", "DPAPI yalnizca Windows'ta")
    def test_garbage_input_returns_none_instead_of_raising(self):
        self.assertIsNone(unprotect("bu gecerli bir blob degil"))
        self.assertIsNone(unprotect(""))

    def test_empty_password_is_not_protected(self):
        self.assertIsNone(protect(""))


class SettingsRoundTripTests(_SettingsTestCase):
    def test_connection_fields_are_remembered(self):
        self.settings.save(
            mode="Join", host="25.1.2.3", port="5555",
            room="oyun", username="ayse",
        )

        saved = self.settings.load()

        self.assertEqual(saved["mode"], "Join")
        self.assertEqual(saved["host"], "25.1.2.3")
        self.assertEqual(saved["port"], "5555")
        self.assertEqual(saved["room"], "oyun")
        self.assertEqual(saved["username"], "ayse")

    def test_defaults_when_nothing_was_saved(self):
        saved = self.settings.load()

        self.assertEqual(saved["mode"], "Join")
        self.assertEqual(saved["room"], "general")
        self.assertEqual(saved["password"], "")
        self.assertFalse(saved["remember_password"])


class PasswordStorageTests(_SettingsTestCase):
    def test_password_is_not_stored_by_default(self):
        self.settings.save(
            mode="Join", host="h", port="5555", room="general",
            username="ayse", password="gizli-parola",
        )

        self.assertEqual(self.settings.load()["password"], "")
        self.assertNotIn("gizli-parola", self.dosya_icerigi())

    @unittest.skipUnless(sys.platform == "win32", "DPAPI yalnizca Windows'ta")
    def test_password_is_stored_encrypted_when_asked(self):
        self.settings.save(
            mode="Join", host="h", port="5555", room="general",
            username="ayse", password="gizli-parola", remember_password=True,
        )

        # Geri okunabiliyor...
        self.assertEqual(self.settings.load()["password"], "gizli-parola")
        # ...ama dosyada duz metin olarak durmuyor.
        self.assertNotIn("gizli-parola", self.dosya_icerigi())

    @unittest.skipUnless(sys.platform == "win32", "DPAPI yalnizca Windows'ta")
    def test_turning_off_remember_deletes_the_stored_password(self):
        self.settings.save(
            mode="Join", host="h", port="5555", room="general",
            username="ayse", password="gizli-parola", remember_password=True,
        )
        self.assertEqual(self.settings.load()["password"], "gizli-parola")

        self.settings.save(
            mode="Join", host="h", port="5555", room="general",
            username="ayse", password="gizli-parola", remember_password=False,
        )

        self.assertEqual(self.settings.load()["password"], "")
        self.assertNotIn("password_blob", self.dosya_icerigi())

    @unittest.skipUnless(sys.platform == "win32", "DPAPI yalnizca Windows'ta")
    def test_corrupt_blob_is_ignored_instead_of_crashing(self):
        self.settings.save(
            mode="Join", host="h", port="5555", room="general",
            username="ayse", password="gizli", remember_password=True,
        )
        # Blob bozulursa (baska hesap, kopyalanan dosya) uygulama cokmemeli.
        self.settings._settings.setValue("password_blob", "bozuk-veri")
        self.settings._settings.sync()

        self.assertEqual(self.settings.load()["password"], "")


class HistoryDefaultTests(unittest.TestCase):
    """THREAT_MODEL.md 5.2: oda gecmisi 1.7.0'dan beri varsayilan kapali.

    Asil tuzak eski kurulumlar: 1.6.x save() her baglantida keep_history=True
    yaziyordu, yani yalnizca varsayilani degistirmek hicbir mevcut kullaniciyi
    etkilemezdi.
    """

    def _yol(self) -> str:
        handle, path = tempfile.mkstemp(suffix=".ini")
        os.close(handle)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    def _ham(self, path: str) -> QSettings:
        return QSettings(path, QSettings.Format.IniFormat)

    def test_yeni_kurulumda_gecmis_kapali(self):
        self.assertFalse(ChatSettings(self._ham(self._yol())).load()["keep_history"])

    def test_eski_surumun_kaydettigi_gecmis_bir_kez_sifirlanir(self):
        path = self._yol()
        eski = self._ham(path)
        eski.setValue("keep_history", True)  # 1.6.x'in her baglantida yazdigi
        eski.setValue("username", "ayse")
        eski.setValue("logging_enabled", True)
        eski.sync()

        yuklenen = ChatSettings(self._ham(path)).load()

        self.assertFalse(yuklenen["keep_history"])
        # Gecis yalnizca gecmise dokunur.
        self.assertEqual(yuklenen["username"], "ayse")
        self.assertTrue(yuklenen["logging_enabled"])

    def test_gecisten_sonra_bilerek_acilan_gecmis_korunur(self):
        path = self._yol()
        eski = self._ham(path)
        eski.setValue("keep_history", True)
        eski.sync()

        ChatSettings(self._ham(path)).save_privacy_choices(keep_history=True)

        # Bir sonraki acilis: gecis ikinci kez calismamali.
        self.assertTrue(ChatSettings(self._ham(path)).load()["keep_history"])

    def test_sunucu_varsayilan_olarak_gecmis_tutmaz(self):
        from core.server import ChatServer

        self.assertFalse(ChatServer().keep_history)

    def test_arayuzde_kutu_isaretsiz_gelir(self):
        from PySide6.QtWidgets import QApplication

        from apps.proxychat.ui import ConnectPage, ConnectionController

        QApplication.instance() or QApplication([])
        page = ConnectPage(ChatSettings(self._ham(self._yol())))
        self.addCleanup(page.deleteLater)

        self.assertFalse(page.keep_history_box.isChecked())
        self.assertFalse(ConnectionController().keep_history)


class ConnectPageSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def _settings(self):
        handle, path = tempfile.mkstemp(suffix=".ini")
        os.close(handle)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return ChatSettings(QSettings(path, QSettings.Format.IniFormat))

    def test_saved_values_populate_the_form_on_next_launch(self):
        from apps.proxychat.ui import ConnectPage

        settings = self._settings()
        settings.save(
            mode="Join", host="25.9.9.9", port="6000",
            room="oyun", username="mehmet",
        )

        page = ConnectPage(settings)
        self.addCleanup(page.deleteLater)

        self.assertEqual(page.username_edit.text(), "mehmet")
        self.assertEqual(page.host_edit.text(), "25.9.9.9")
        self.assertEqual(page.port_edit.text(), "6000")
        self.assertEqual(page.room_edit.text(), "oyun")

    def test_form_saves_what_the_user_typed(self):
        from apps.proxychat.ui import ConnectPage

        settings = self._settings()
        page = ConnectPage(settings)
        self.addCleanup(page.deleteLater)

        page.username_edit.setText("eda")
        page.host_edit.setText("25.5.5.5")
        page.port_edit.setText("7000")
        page.room_edit.setText("sohbet")
        page.save_settings()

        saved = settings.load()
        self.assertEqual(saved["username"], "eda")
        self.assertEqual(saved["host"], "25.5.5.5")
        self.assertEqual(saved["port"], "7000")
        self.assertEqual(saved["room"], "sohbet")

    def test_password_field_stays_empty_when_remember_is_off(self):
        from apps.proxychat.ui import ConnectPage

        settings = self._settings()
        page = ConnectPage(settings)
        self.addCleanup(page.deleteLater)
        page.password_edit.setText("gizli")
        page.remember_password_box.setChecked(False)
        page.save_settings()

        page2 = ConnectPage(settings)
        self.addCleanup(page2.deleteLater)

        self.assertEqual(page2.password_edit.text(), "")
        self.assertFalse(page2.remember_password_box.isChecked())

    @unittest.skipUnless(sys.platform == "win32", "DPAPI yalnizca Windows'ta")
    def test_password_comes_back_when_remember_is_on(self):
        from apps.proxychat.ui import ConnectPage

        settings = self._settings()
        page = ConnectPage(settings)
        self.addCleanup(page.deleteLater)
        page.password_edit.setText("gizli")
        page.remember_password_box.setChecked(True)
        page.save_settings()

        page2 = ConnectPage(settings)
        self.addCleanup(page2.deleteLater)

        self.assertEqual(page2.password_edit.text(), "gizli")
        self.assertTrue(page2.remember_password_box.isChecked())



class ModeSwitchTests(unittest.TestCase):
    """Mod degisimi kullanicinin yazdigini silmemeli."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def _page(self):
        from apps.proxychat.ui import ConnectPage

        handle, path = tempfile.mkstemp(suffix=".ini")
        os.close(handle)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        page = ConnectPage(ChatSettings(QSettings(path, QSettings.Format.IniFormat)))
        self.addCleanup(page.deleteLater)
        return page

    def test_switching_away_from_join_keeps_the_typed_address(self):
        page = self._page()
        page.mode_box.setCurrentText("Join")
        page.host_edit.setText("25.12.34.56")

        page.mode_box.setCurrentText("Host")

        self.assertEqual(page.host_edit.text(), "25.12.34.56", "yazilan IP silindi")
        self.assertFalse(page.host_edit.isEnabled(), "Host modunda alan aktif kaldi")
        self.assertTrue(page.host_edit.isHidden(), "Host modunda gereksiz IP alani gorunuyor")

    def test_ip_field_is_hidden_in_demo_mode_too(self):
        page = self._page()

        page.mode_box.setCurrentText("Demo")

        self.assertTrue(page.host_edit.isHidden())

    def test_coming_back_to_join_restores_the_field(self):
        page = self._page()
        page.mode_box.setCurrentText("Join")
        page.host_edit.setText("25.12.34.56")
        page.mode_box.setCurrentText("Host")

        page.mode_box.setCurrentText("Join")

        self.assertEqual(page.host_edit.text(), "25.12.34.56")
        self.assertTrue(page.host_edit.isEnabled())
        self.assertFalse(page.host_edit.isHidden())

    def test_host_mode_ignores_the_leftover_join_address(self):
        page = self._page()
        page.host_edit.setText("25.12.34.56")
        page.mode_box.setCurrentText("Host")
        page.listen_box.setCurrentIndex(page.listen_box.findData("0.0.0.0"))
        page.port_edit.setText("5555")
        yakalanan = []
        page.connect_requested.connect(lambda *args: yakalanan.append(args))

        page._emit_connect()

        self.assertEqual(yakalanan[0][1], "0.0.0.0", "Host modunda Join alaninda kalan IP kullanildi")

if __name__ == "__main__":
    unittest.main()
