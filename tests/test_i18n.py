"""Arayuz dili: Ingilizce varsayilan, Turkce secilebilir, aninda uygulanir.

Odak: kataloglarin eksiksiz ve birbiriyle uyumlu olmasi, secimin saklanmasi,
dil degisince ekrandaki metinlerin yeniden yazilmasi ve arayuz koduna yeniden
Turkce metin gomulmemesi.
"""

import re
import socket
import string
import tokenize
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from PySide6.QtWidgets import QApplication

from apps.proxychat.i18n import DEFAULT_LANGUAGE, LANGUAGES, current_language, set_language, t
from apps.proxychat.locales import CATALOGS
from apps.proxychat.ui import ChatPage, ConnectionController, ProxyChatWindow, describe_socket_error
from core.server import MAX_CONTENT_BYTES, ChatServer
from core.transport import LineSocket
from tests.test_client_lifecycle import bos_port
from tests.test_proxychat_ui import izole_ayarlar

KOK = Path(__file__).resolve().parents[1]
UI_KAYNAGI = KOK / "apps" / "proxychat" / "ui.py"
SUNUCU_KAYNAGI = KOK / "core" / "server.py"


def _yer_tutucular(metin: str) -> list[str]:
    return sorted({alan for _, alan, _, _ in string.Formatter().parse(metin) if alan})


class CatalogTests(unittest.TestCase):
    def test_english_is_the_default_and_turkish_is_offered(self):
        self.assertEqual(DEFAULT_LANGUAGE, "en")
        self.assertEqual(list(LANGUAGES), ["en", "tr"])

    def test_every_language_has_exactly_the_english_keys(self):
        referans = set(CATALOGS["en"].TEXTS)
        for kod, modul in CATALOGS.items():
            with self.subTest(dil=kod):
                self.assertEqual(set(modul.TEXTS) - referans, set(), "Ingilizcede olmayan anahtar")
                self.assertEqual(referans - set(modul.TEXTS), set(), "cevrilmemis anahtar")

    def test_placeholders_match_english(self):
        # Yer tutucusu farkli bir ceviri, format() cagrisinda KeyError ile patlar.
        for kod, modul in CATALOGS.items():
            for anahtar, metin in modul.TEXTS.items():
                with self.subTest(dil=kod, anahtar=anahtar):
                    self.assertEqual(_yer_tutucular(metin), _yer_tutucular(CATALOGS["en"].TEXTS[anahtar]))

    def test_month_lists_have_twelve_names(self):
        for kod in CATALOGS:
            set_language(kod)
            self.assertEqual(len(t("chat.months").split()), 12, kod)

    def test_unknown_language_falls_back_to_english(self):
        self.assertEqual(set_language("xx"), "en")
        self.assertEqual(set_language(None), "en")
        self.assertEqual(set_language(""), "en")

    def test_missing_translation_falls_back_to_english(self):
        eksik = dict(CATALOGS["tr"].TEXTS)
        del eksik["chat.send"]

        with mock.patch.object(CATALOGS["tr"], "TEXTS", eksik):
            set_language("tr")
            self.assertEqual(t("chat.send"), CATALOGS["en"].TEXTS["chat.send"])

    def test_every_key_used_in_the_interface_exists(self):
        kaynak = UI_KAYNAGI.read_text(encoding="utf-8")
        kullanilan = set(
            re.findall(r'"((?:window|tray|connect|chat|demo|error|socket_error|server_error)\.[a-z0-9_]+)"', kaynak)
        )

        self.assertGreater(len(kullanilan), 40, "anahtarlar bulunamadi, test bos gecerdi")
        self.assertEqual(kullanilan - set(CATALOGS["en"].TEXTS), set())

    def test_every_code_the_server_sends_has_a_translation(self):
        kaynak = SUNUCU_KAYNAGI.read_text(encoding="utf-8")
        kodlar = set(re.findall(r'"code": "([a-z_]+)"', kaynak))
        kodlar |= set(re.findall(r'_reject_connection\(conn, "([a-z_]+)"', kaynak))
        for eslesme in re.findall(r'code = "([a-z_]+)" if .+ else "([a-z_]+)"', kaynak):
            kodlar |= set(eslesme)

        self.assertGreaterEqual(len(kodlar), 9, f"sunucu kodlari bulunamadi: {kodlar}")
        eksik = {kod for kod in kodlar if f"server_error.{kod}" not in CATALOGS["en"].TEXTS}
        self.assertEqual(eksik, set())

    def test_no_turkish_text_is_hardcoded_in_the_interface(self):
        # Arayuz metni yalnizca locales/ icinde durur. Yorumlar ve belge dizeleri
        # bu depoda zaten ASCII yaziliyor; kontrol yalnizca dize sabitlerine bakar.
        turkce = re.compile("[çğıöşüÇĞİÖŞÜ]")
        with UI_KAYNAGI.open("rb") as dosya:
            dizeler = [tok.string for tok in tokenize.tokenize(dosya.readline) if tok.type == tokenize.STRING]

        self.assertGreater(len(dizeler), 50, "dize sabitleri okunamadi, test bos gecerdi")
        self.assertEqual([dize for dize in dizeler if turkce.search(dize)], [])


class _QtTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])


class LanguageSelectionTests(_QtTestCase):
    def _window(self, ayarlar=None):
        window = ProxyChatWindow(ayarlar if ayarlar is not None else izole_ayarlar(self))
        self.addCleanup(window.close)
        return window

    @staticmethod
    def _sec(window, kod):
        window.language_box.setCurrentIndex(window.language_box.findData(kod))

    def test_first_launch_is_in_english(self):
        window = self._window()

        self.assertEqual(current_language(), "en")
        self.assertEqual(window.language_box.currentData(), "en")
        self.assertEqual(window.connect_page.connect_button.text(), "Connect")
        self.assertEqual(window.chat_page.send_button.text(), "Send")

    def test_choosing_turkish_updates_both_pages_immediately(self):
        window = self._window()

        self._sec(window, "tr")

        self.assertEqual(current_language(), "tr")
        self.assertEqual(window.connect_page.connect_button.text(), "Bağlan")
        self.assertEqual(window.connect_page.username_edit.placeholderText(), "Kullanıcı adı")
        self.assertEqual(window.chat_page.send_button.text(), "Gönder")
        self.assertEqual(window.chat_page.message_input.placeholderText(), "Mesaj yaz...")
        self.assertEqual(window.language_box.toolTip(), "Arayüz dili")

    def test_switching_back_to_english_works(self):
        window = self._window()
        self._sec(window, "tr")

        self._sec(window, "en")

        self.assertEqual(window.chat_page.send_button.text(), "Send")
        self.assertEqual(window.connect_page.privacy_title.text(), "PRIVACY")

    def test_choice_is_remembered(self):
        ayarlar = izole_ayarlar(self)
        ilk = self._window(ayarlar)
        self._sec(ilk, "tr")
        set_language("en")  # modul durumu degil, kayit okunmali

        ikinci = self._window(ayarlar)

        self.assertEqual(current_language(), "tr")
        self.assertEqual(ikinci.language_box.currentData(), "tr")
        self.assertEqual(ikinci.connect_page.connect_button.text(), "Bağlan")

    def test_typed_values_survive_a_language_change(self):
        window = self._window()
        page = window.connect_page
        page.username_edit.setText("ayse")
        page.room_edit.setText("oyun")

        self._sec(window, "tr")

        self.assertEqual(page.username_edit.text(), "ayse")
        self.assertEqual(page.room_edit.text(), "oyun")

    def test_status_line_is_retranslated(self):
        window = self._window()
        page = window.connect_page
        page.mode_box.setCurrentText("Host")
        page._emit_connect()  # ag secilmedi
        self.assertEqual(page.status_label.text(), "Choose the network to listen on.")

        self._sec(window, "tr")

        self.assertEqual(page.status_label.text(), "Dinlenecek ağı seç.")

    def test_listen_list_is_retranslated_without_losing_the_choice(self):
        window = self._window()
        page = window.connect_page
        page.mode_box.setCurrentText("Host")
        index = page.listen_box.findData("0.0.0.0")
        page.listen_box.setCurrentIndex(index)

        self._sec(window, "tr")

        self.assertEqual(page.listen_box.itemText(index), "Bütün ağlar (0.0.0.0)")
        self.assertEqual(page.listen_box.currentData(), "0.0.0.0")

    def test_mode_hint_is_retranslated(self):
        window = self._window()
        page = window.connect_page
        page.mode_box.setCurrentText("Demo")

        self._sec(window, "tr")

        self.assertEqual(page.share_box.toPlainText(), CATALOGS["tr"].TEXTS["connect.mode_demo"])

    def test_connection_details_are_retranslated(self):
        window = self._window()
        chat = window.chat_page
        chat.show_connected({"host": "25.1.2.3", "port": 5555, "encrypted": True, "share_ips": ["25.1.2.3"]})
        self.assertIn("End-to-end encrypted", chat.connection_status.text())

        self._sec(window, "tr")

        self.assertIn("Uçtan uca şifreli", chat.connection_status.text())
        self.assertIn("Arkadaşlarının bağlanacağı adres", chat.server_hint.toPlainText())
        self.assertEqual(chat.reveal_address_button.text(), "Adresi göster")
        # Adres dil degisince de gizli kaliyor (bkz. test_adres_gizleme.py); port gorunur.
        for metin in (chat.connection_status.text(), chat.server_hint.toPlainText()):
            self.assertNotIn("25.1.2.3", metin)
            self.assertIn(":5555", metin)

    def test_user_count_is_retranslated(self):
        window = self._window()
        chat = window.chat_page
        chat._apply_snapshot({"users": ["ayse", "mehmet"]})
        self.assertEqual(chat.channel_status.text(), "2 users connected")

        self._sec(window, "tr")

        self.assertEqual(chat.channel_status.text(), "2 kullanıcı bağlı")


class TranslatedMessageTests(_QtTestCase):
    def _page(self):
        page = ChatPage(ConnectionController())
        self.addCleanup(page.deleteLater)
        self.lines = []
        page._append_system = self.lines.append
        return page

    def test_one_user_is_not_called_users(self):
        page = self._page()

        page._apply_snapshot({"users": ["ayse"]})

        self.assertEqual(page.channel_status.text(), "1 user connected")

    def test_server_error_with_a_known_code_is_shown_in_the_chosen_language(self):
        set_language("tr")
        page = self._page()

        page.on_packet({"type": "error", "code": "message_too_long", "message": "message too long"})

        self.assertEqual(self.lines, ["Mesaj çok uzun."])

    def test_unknown_code_falls_back_to_the_server_text(self):
        page = self._page()

        page.on_packet({"type": "error", "code": "gelecekteki_bir_kod", "message": "sunucunun metni"})

        self.assertEqual(self.lines, ["sunucunun metni"])

    def test_error_from_an_older_server_without_a_code_still_shows(self):
        page = self._page()

        page.on_packet({"type": "error", "message": "eski sunucu"})

        self.assertEqual(self.lines, ["eski sunucu"])

    def test_undecryptable_message_uses_the_chosen_language(self):
        page = self._page()

        page.on_packet({
            "type": "message", "room": "general", "user": "mehmet",
            "content": "[cozulemedi - oda parolasi farkli]", "decrypt_failed": True,
        })

        self.assertEqual(self.lines, ["mehmet: [could not decrypt — different room password]"])

    def test_version_mismatch_is_not_blamed_on_the_password(self):
        page = self._page()

        page.on_packet({
            "type": "message", "room": "general", "user": "mehmet",
            "content": "[cozulemedi - oda parolasi farkli]",
            "decrypt_failed": True, "decrypt_reason": "scheme",
        })

        self.assertEqual(
            self.lines,
            ["mehmet: [could not decrypt — the other side uses a different ProxyChat version]"],
        )

    def test_older_dates_use_month_names_of_the_chosen_language(self):
        page = self._page()
        eski = datetime(2025, 9, 9, 14, 5).timestamp()

        self.assertEqual(page._format_timestamp(eski), "9 Sep 14:05")
        set_language("tr")
        self.assertEqual(page._format_timestamp(eski), "9 Eyl 14:05")

    def test_socket_errors_are_translated(self):
        hata = OSError(10061, "reddedildi")

        self.assertEqual(describe_socket_error(hata), CATALOGS["en"].TEXTS["socket_error.10061"])
        set_language("tr")
        self.assertEqual(describe_socket_error(hata), CATALOGS["tr"].TEXTS["socket_error.10061"])

    def test_unknown_socket_error_keeps_the_details(self):
        mesaj = describe_socket_error(OSError(99999, "tuhaf bir hata"))

        self.assertIn("tuhaf bir hata", mesaj)


class ServerErrorCodeTests(unittest.TestCase):
    def test_server_errors_carry_a_machine_readable_code(self):
        port = bos_port()
        server = ChatServer(host="127.0.0.1", port=port)
        server.start()
        self.addCleanup(server.stop)
        transport = LineSocket(socket.create_connection(("127.0.0.1", port), timeout=5))
        self.addCleanup(transport.close)

        transport.send_packet({"type": "join", "room": "general", "user": "ayse"})
        transport.send_packet({"type": "message", "content": "x" * (MAX_CONTENT_BYTES + 10)})

        hata = None
        for _ in range(20):
            packet = transport.recv_packet()
            if packet is not None and packet.get("type") == "error":
                hata = packet
                break

        self.assertIsNotNone(hata, "hata paketi gelmedi")
        self.assertEqual(hata["code"], "message_too_long")
        # code'u tanimayan eski istemciler bu metni gostermeye devam eder.
        self.assertIn("too long", hata["message"])


if __name__ == "__main__":
    unittest.main()
