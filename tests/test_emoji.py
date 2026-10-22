"""Emoji: buyuk gosterim mantigi ve secici.

GIF istendi, reddedildi (goruntu cozucu + isaretleme + dosya aktarma).
Emoji bunlarin hicbirini gerektirmiyor: aga giden sey yine duz metin, yalnizca
gosterim degisiyor. Bu testler tam olarak onu kilitliyor.
"""

import unittest

from PySide6.QtWidgets import QApplication

from apps.proxychat.emoji import (
    MAX_LARGE,
    PICKER_ROWS,
    display_size,
    emoji_count,
    is_emoji_only,
    picker_emojis,
)
from apps.proxychat.i18n import set_language
from apps.proxychat.ui import ChatPage, ConnectionController, EmojiPicker

GULUMSEME = "\U0001F642"
GOZYASI = "\U0001F602"
ATES = "\U0001F525"
BASPARMAK = "\U0001F44D"


class TanimaTests(unittest.TestCase):
    def test_tek_emoji_taniniyor(self):
        self.assertTrue(is_emoji_only(GULUMSEME))
        self.assertEqual(emoji_count(GULUMSEME), 1)

    def test_bosluklar_yok_sayiliyor(self):
        self.assertTrue(is_emoji_only(f"  {GULUMSEME}  "))

    def test_metin_karisinca_emoji_sayilmiyor(self):
        self.assertFalse(is_emoji_only(f"merhaba {GULUMSEME}"))

    def test_duz_metin_emoji_degil(self):
        for metin in ("merhaba", "...", "-> <-", "1234", ""):
            self.assertFalse(is_emoji_only(metin), metin)

    def test_noktalama_buyutulmuyor(self):
        """"..." ya da "!!!" buyuk gorunmemeli."""
        self.assertIsNone(display_size("!!!"))
        self.assertIsNone(display_size("<3"))

    def test_ton_degistirici_ayri_emoji_sayilmiyor(self):
        self.assertEqual(emoji_count("\U0001F44D\U0001F3FD"), 1)

    def test_varyasyon_secici_ayri_sayilmiyor(self):
        self.assertEqual(emoji_count("❤️"), 1)

    def test_yalniz_degistiriciden_olusan_metin_emoji_degil(self):
        self.assertFalse(is_emoji_only("️"))


class BoyutTests(unittest.TestCase):
    def test_az_emoji_daha_buyuk(self):
        tek = display_size(GULUMSEME)
        uc = display_size(GOZYASI * 3)
        alti = display_size(ATES * 6)

        self.assertGreater(tek, uc)
        self.assertGreater(uc, alti)

    def test_sinira_kadar_buyutuluyor(self):
        self.assertIsNotNone(display_size(ATES * MAX_LARGE))

    def test_siniri_asinca_normal(self):
        """Yirmi emoji buyuk gosterilirse sohbet okunmaz olur."""
        self.assertIsNone(display_size(ATES * (MAX_LARGE + 1)))

    def test_metin_mesaji_normal(self):
        self.assertIsNone(display_size("selam"))


class SeciciListesiTests(unittest.TestCase):
    def test_tekrar_eden_emoji_yok(self):
        hepsi = picker_emojis()

        self.assertEqual(len(hepsi), len(set(hepsi)))

    def test_hepsi_gercekten_emoji(self):
        for emoji in picker_emojis():
            self.assertTrue(is_emoji_only(emoji), emoji)

    def test_satirlar_esit_uzunlukta(self):
        """Izgara duzgun gorunsun."""
        uzunluklar = {len(satir.split()) for satir in PICKER_ROWS}

        self.assertEqual(len(uzunluklar), 1)


class ArayuzTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "en")
        self.sayfa = ChatPage(ConnectionController())
        self.addCleanup(self.sayfa.deleteLater)

    def test_emoji_dugmesi_gonderin_solunda(self):
        satir = self.sayfa.input_row
        sira = [satir.itemAt(i).widget() for i in range(satir.count())]

        self.assertLess(sira.index(self.sayfa.emoji_button), sira.index(self.sayfa.send_button))
        self.assertGreater(sira.index(self.sayfa.emoji_button), sira.index(self.sayfa.message_input))

    def test_secilen_emoji_yazi_alanina_giriyor(self):
        self.sayfa.message_input.setText("selam")
        self.sayfa.message_input.setCursorPosition(5)

        self.sayfa._insert_emoji(GULUMSEME)

        self.assertEqual(self.sayfa.message_input.text(), f"selam{GULUMSEME}")

    def test_emoji_imlecin_oldugu_yere_giriyor(self):
        self.sayfa.message_input.setText("ab")
        self.sayfa.message_input.setCursorPosition(1)

        self.sayfa._insert_emoji(BASPARMAK)

        self.assertEqual(self.sayfa.message_input.text(), f"a{BASPARMAK}b")

    def test_secici_bir_kez_kuruluyor(self):
        self.sayfa._open_emoji_picker()
        ilk = self.sayfa._emoji_picker
        self.sayfa._emoji_picker.close()

        self.sayfa._open_emoji_picker()

        self.assertIs(self.sayfa._emoji_picker, ilk)
        self.sayfa._emoji_picker.close()

    def test_secicideki_dugme_sayisi_listeyle_ayni(self):
        secici = EmojiPicker()
        self.addCleanup(secici.deleteLater)

        self.assertEqual(secici.layout().count(), len(picker_emojis()))

    def test_emoji_mesaji_buyuk_ciziliyor(self):
        self.sayfa._append_message("eda", GOZYASI)

        html = self.sayfa.message_view.toHtml()
        self.assertIn(f"{display_size(GOZYASI)}pt", html)

    def test_metin_mesaji_buyutulmuyor(self):
        self.sayfa._append_message("eda", "selam")

        self.assertNotIn("30pt", self.sayfa.message_view.toHtml())


if __name__ == "__main__":
    unittest.main()
