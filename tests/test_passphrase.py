"""Oda parolasi uretimi: guclu, rastgele, yuksek sesle soylenebilir.

Odak: kelime listelerinin gucu gercekten tasiyabilmesi (tekrarsiz, yeterince
buyuk), rastgeleligin ``secrets``'ten gelmesi ve baglanti ekranindaki
dugmelerin nasil paylasilacagini soylemesi. Uretmek parolayi ekrana
getirmemeli; Kopyala gostermeden panoya almali.
"""

import math
import re
import tempfile
import os
import unittest
from unittest import mock

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QLineEdit

from apps.proxychat import passphrase
from apps.proxychat.i18n import passphrase_words, set_language, t
from apps.proxychat.locales import CATALOGS
from apps.proxychat.passphrase import MIN_ENTROPY_BITS, SEPARATOR, entropy_bits, generate_passphrase, words_needed
from apps.proxychat.settings import ChatSettings
from apps.proxychat.ui import CLIPBOARD_CLEAR_MS, ConnectPage


class WordListTests(unittest.TestCase):
    def test_every_language_has_a_word_list(self):
        for kod, modul in CATALOGS.items():
            with self.subTest(dil=kod):
                self.assertTrue(getattr(modul, "WORDS", None), "kelime listesi yok")

    def test_words_are_short_lowercase_ascii(self):
        # Baska dilde klavyesi olan bir arkadas da yazabilmeli; ayraci da
        # icermemeli, yoksa kelime sinirlari karisir.
        for kod, modul in CATALOGS.items():
            gecersiz = [kelime for kelime in modul.WORDS if not re.fullmatch(r"[a-z]{3,8}", kelime)]
            with self.subTest(dil=kod):
                self.assertEqual(gecersiz, [])

    def test_words_are_not_repeated(self):
        # Tekrar eden kelime listeyi buyuk gosterip gucu sisirirdi.
        for kod, modul in CATALOGS.items():
            with self.subTest(dil=kod):
                self.assertEqual(len(modul.WORDS), len(set(modul.WORDS)))

    def test_lists_are_large_enough_for_a_sayable_password(self):
        # Kucuk listede hedef guce ulasmak icin soylenemeyecek kadar cok kelime gerekir.
        for kod, modul in CATALOGS.items():
            with self.subTest(dil=kod):
                self.assertGreaterEqual(len(modul.WORDS), 256)
                self.assertLessEqual(words_needed(len(modul.WORDS)), 7)

    def test_current_language_picks_its_own_list(self):
        set_language("tr")
        self.assertIs(passphrase_words(), CATALOGS["tr"].WORDS)
        set_language("en")
        self.assertIs(passphrase_words(), CATALOGS["en"].WORDS)

    def test_language_without_a_list_falls_back_to_english(self):
        set_language("tr")
        with mock.patch.object(CATALOGS["tr"], "WORDS", ()):
            self.assertIs(passphrase_words(), CATALOGS["en"].WORDS)


class GeneratorTests(unittest.TestCase):
    def test_generated_password_reaches_the_target_strength(self):
        for kod, modul in CATALOGS.items():
            parola = generate_passphrase(modul.WORDS)
            kelimeler = parola.split(SEPARATOR)
            with self.subTest(dil=kod, parola=parola):
                self.assertTrue(set(kelimeler) <= set(modul.WORDS))
                self.assertGreaterEqual(entropy_bits(len(set(modul.WORDS)), len(kelimeler)), MIN_ENTROPY_BITS)

    def test_word_count_follows_the_list_size(self):
        self.assertEqual(words_needed(2 ** 10, 50), 5)
        self.assertEqual(words_needed(2 ** 8, 50), 7)
        self.assertEqual(words_needed(2 ** 10, 60), 6)

    def test_duplicates_do_not_inflate_the_strength(self):
        tekrarli = ["a1"] * 1000 + ["b2", "c3", "d4"]

        parola = generate_passphrase(tekrarli, min_bits=10)

        # 4 farkli kelime = kelime basina 2 bit -> 10 bit icin 5 kelime.
        self.assertEqual(len(parola.split(SEPARATOR)), 5)

    def test_randomness_comes_from_secrets(self):
        with mock.patch.object(passphrase.secrets, "choice", side_effect=lambda seq: seq[0]) as secim:
            parola = generate_passphrase(["zebra", "elma", "kavun", "limon"], min_bits=4)

        self.assertTrue(secim.called)
        self.assertEqual(parola, "elma-elma")

    def test_passwords_are_different_each_time(self):
        uretilen = {generate_passphrase(CATALOGS["en"].WORDS) for _ in range(50)}

        self.assertEqual(len(uretilen), 50)

    def test_list_with_a_single_word_is_rejected(self):
        with self.assertRaises(ValueError):
            generate_passphrase(["tek", "tek"])

    def test_strength_math(self):
        self.assertAlmostEqual(entropy_bits(1024, 5), 50.0)
        self.assertAlmostEqual(entropy_bits(524, 6), 6 * math.log2(524))


class PasswordButtonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _page(self):
        handle, path = tempfile.mkstemp(suffix=".ini")
        os.close(handle)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        page = ConnectPage(ChatSettings(QSettings(path, QSettings.Format.IniFormat)))
        self.addCleanup(page.deleteLater)
        return page

    def test_password_is_hidden_by_default(self):
        page = self._page()

        self.assertEqual(page.password_edit.echoMode(), QLineEdit.EchoMode.Password)
        self.assertTrue(page.password_notice.isHidden())
        self.assertEqual(page.show_password_button.text(), "Show")

    def test_generate_fills_the_field_and_keeps_it_hidden(self):
        """Ekran paylasirken Uret'e basmak parolayi herkese gostermemeli."""
        page = self._page()

        page.generate_password_button.click()

        kelimeler = page.password_edit.text().split(SEPARATOR)
        self.assertGreaterEqual(len(kelimeler), 5)
        self.assertTrue(set(kelimeler) <= set(CATALOGS["en"].WORDS))
        self.assertEqual(page.password_edit.echoMode(), QLineEdit.EchoMode.Password, "uretilen parola ekrana geldi")
        self.assertFalse(page.password_notice.isHidden(), "paylasim uyarisi gosterilmedi")
        self.assertEqual(page.show_password_button.text(), "Show")

    def test_generate_after_hide_stays_hidden(self):
        page = self._page()
        page.show_password_button.click()
        page.show_password_button.click()

        page.generate_password_button.click()

        self.assertEqual(page.password_edit.echoMode(), QLineEdit.EchoMode.Password)

    def test_generate_while_shown_stays_shown(self):
        page = self._page()
        page.show_password_button.click()

        page.generate_password_button.click()

        self.assertEqual(page.password_edit.echoMode(), QLineEdit.EchoMode.Normal)
        self.assertEqual(page.show_password_button.text(), "Hide")

    def test_notice_tells_how_to_share(self):
        page = self._page()

        page.generate_password_button.click()

        self.assertIn("Signal", page.password_notice.text())
        self.assertIn("Discord", page.password_notice.text())

    def test_generating_again_gives_a_new_password(self):
        page = self._page()
        page.generate_password_button.click()
        ilk = page.password_edit.text()

        page.generate_password_button.click()

        self.assertNotEqual(page.password_edit.text(), ilk)

    def test_turkish_interface_generates_turkish_words(self):
        set_language("tr")
        page = self._page()

        page.generate_password_button.click()

        self.assertTrue(set(page.password_edit.text().split(SEPARATOR)) <= set(CATALOGS["tr"].WORDS))

    def test_show_button_toggles_visibility(self):
        page = self._page()

        page.show_password_button.click()
        self.assertEqual(page.password_edit.echoMode(), QLineEdit.EchoMode.Normal)

        page.show_password_button.click()
        self.assertEqual(page.password_edit.echoMode(), QLineEdit.EchoMode.Password)
        self.assertEqual(page.show_password_button.text(), "Show")

    def test_typing_your_own_password_removes_the_notice(self):
        page = self._page()
        page.generate_password_button.click()

        page.password_edit.textEdited.emit("kendi-parolam")

        self.assertTrue(page.password_notice.isHidden())

    def test_buttons_follow_the_language(self):
        page = self._page()
        page.generate_password_button.click()

        set_language("tr")
        page.retranslate()

        self.assertEqual(page.generate_password_button.text(), "Üret")
        self.assertEqual(page.show_password_button.text(), "Göster")
        self.assertEqual(page.copy_password_button.text(), "Kopyala")
        self.assertEqual(page.password_notice.text(), t("connect.password_generated"))

    def test_buttons_are_disabled_while_connecting(self):
        page = self._page()

        page.set_busy(True)

        self.assertFalse(page.generate_password_button.isEnabled())
        self.assertFalse(page.show_password_button.isEnabled())
        self.assertFalse(page.copy_password_button.isEnabled())

    def test_generated_password_is_what_gets_sent(self):
        page = self._page()
        page.host_edit.setText("25.1.2.3")
        yakalanan = []
        page.connect_requested.connect(lambda *args: yakalanan.append(args))
        page.generate_password_button.click()

        page._emit_connect()

        self.assertEqual(yakalanan[0][-1], page.password_edit.text())


class FakeClipboard:
    """Testler kullanicinin gercek panosuna dokunmasin."""

    def __init__(self):
        self.mime = None
        self._text = ""

    def setMimeData(self, mime):
        self.mime = mime
        self._text = mime.text()

    def text(self):
        return self._text

    def set_other_text(self, text):
        self.mime = None
        self._text = text

    def clear(self):
        self.mime = None
        self._text = ""


class CopyPasswordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        set_language("en")

    def _page(self):
        handle, path = tempfile.mkstemp(suffix=".ini")
        os.close(handle)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        page = ConnectPage(ChatSettings(QSettings(path, QSettings.Format.IniFormat)))
        self.addCleanup(page.deleteLater)
        self.clipboard = FakeClipboard()
        yama = mock.patch.object(page, "_clipboard", return_value=self.clipboard)
        yama.start()
        self.addCleanup(yama.stop)
        return page

    def test_copy_is_disabled_without_a_password(self):
        page = self._page()

        self.assertFalse(page.copy_password_button.isEnabled())
        page.password_edit.setText("kendi-parolam")
        self.assertTrue(page.copy_password_button.isEnabled())

    def test_copy_puts_the_password_on_the_clipboard_without_showing_it(self):
        page = self._page()
        page.generate_password_button.click()

        page.copy_password_button.click()

        self.assertEqual(self.clipboard.text(), page.password_edit.text())
        self.assertEqual(page.password_edit.echoMode(), QLineEdit.EchoMode.Password)
        self.assertEqual(page.copy_password_button.text(), "Copied")

    def test_copy_asks_windows_to_keep_it_out_of_history_and_cloud(self):
        page = self._page()
        page.password_edit.setText("kendi-parolam")

        page.copy_password_button.click()

        bicimler = self.clipboard.mime.formats()
        for ad in ("CanIncludeInClipboardHistory", "CanUploadToCloudClipboard",
                   "ExcludeClipboardContentFromMonitorProcessing"):
            with self.subTest(bicim=ad):
                eslesen = [b for b in bicimler if ad in b]
                self.assertEqual(len(eslesen), 1)
                self.assertEqual(bytes(self.clipboard.mime.data(eslesen[0])), bytes(4))

    def test_clipboard_is_cleared_after_the_timeout(self):
        page = self._page()
        page.password_edit.setText("kendi-parolam")
        page.copy_password_button.click()

        self.assertTrue(page._clipboard_clear_timer.isActive())
        self.assertEqual(page._clipboard_clear_timer.interval(), CLIPBOARD_CLEAR_MS)
        page._clipboard_clear_timer.timeout.emit()

        self.assertEqual(self.clipboard.text(), "")

    def test_something_else_copied_meanwhile_is_left_alone(self):
        page = self._page()
        page.password_edit.setText("kendi-parolam")
        page.copy_password_button.click()
        self.clipboard.set_other_text("kullanicinin kopyaladigi baska bir sey")

        page.clear_copied_password()

        self.assertEqual(self.clipboard.text(), "kullanicinin kopyaladigi baska bir sey")

    def test_clipboard_is_cleared_when_the_app_quits(self):
        page = self._page()
        page.password_edit.setText("kendi-parolam")
        page.copy_password_button.click()

        self._app.aboutToQuit.emit()

        self.assertEqual(self.clipboard.text(), "")

    def test_copy_label_returns_after_feedback(self):
        page = self._page()
        page.password_edit.setText("kendi-parolam")
        page.copy_password_button.click()

        page._copied_feedback_timer.timeout.emit()

        self.assertEqual(page.copy_password_button.text(), "Copy")

    def test_copy_follows_busy_state(self):
        page = self._page()
        page.password_edit.setText("kendi-parolam")

        page.set_busy(True)
        self.assertFalse(page.copy_password_button.isEnabled())
        page.set_busy(False)
        self.assertTrue(page.copy_password_button.isEnabled())


class UretDugmesiModaBagliTests(unittest.TestCase):
    """Uret dugmesi yalnizca odayi KURAN tarafta anlamli.

    Join'de parola karsi taraftan geliyor; orada uretmek onu karsi tarafinkiyle
    degistirmek demek, yani yalnizca gereksiz degil yaniltici -- kullanici
    dogru parolayi silip yanlisiyla baglanmaya calisir.
    """

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _page(self):
        handle, path = tempfile.mkstemp(suffix=".ini")
        os.close(handle)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        page = ConnectPage(ChatSettings(QSettings(path, QSettings.Format.IniFormat)))
        self.addCleanup(page.deleteLater)
        return page

    def _mod(self, mod: str):
        page = self._page()
        page.mode_box.setCurrentText(mod)
        return page

    def test_join_modunda_gizli(self):
        """Varsayilan mod zaten Join; acilista da gorunmemeli.

        `isVisible()` degil `isHidden()`: hic show() edilmemis bir pencerede
        butun alt widget'lar zaten gorunmez raporlar, yani isVisible ile
        yazilan bu test hata VARKEN de gecerdi. isHidden yalnizca acik
        gizlemeyi gorur.
        """
        page = self._page()

        self.assertEqual(page.mode_box.currentText(), "Join")
        self.assertTrue(page.generate_password_button.isHidden())

    def test_host_ve_demo_modunda_gorunur(self):
        for mod in ("Host", "Demo"):
            page = self._mod(mod)

            self.assertFalse(page.generate_password_button.isHidden(), mod)

    def test_join_e_donunce_yeniden_gizleniyor(self):
        page = self._mod("Host")
        self.assertFalse(page.generate_password_button.isHidden())

        page.mode_box.setCurrentText("Join")

        self.assertTrue(page.generate_password_button.isHidden())

    def test_mod_degisimi_yazilan_parolayi_silmiyor(self):
        """host_edit'teki gerekce burada da gecerli: gidip gelen kaybetmemeli."""
        page = self._page()
        page.password_edit.setText("kavanoz-bulut-terlik")

        page.mode_box.setCurrentText("Host")
        page.mode_box.setCurrentText("Join")

        self.assertEqual(page.password_edit.text(), "kavanoz-bulut-terlik")

    def test_join_e_gecince_uretildi_notu_kalkiyor(self):
        """Host'ta uretilip Join'e gecilirse o not oradan kalma bir bilgi olur."""
        page = self._mod("Host")
        page.generate_password_button.click()
        self.assertFalse(page.password_notice.isHidden())

        page.mode_box.setCurrentText("Join")

        self.assertTrue(page.password_notice.isHidden())


if __name__ == "__main__":
    unittest.main()
