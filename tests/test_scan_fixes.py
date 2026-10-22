"""15 Eylul 2026 hata taramasinda bulunan ve yeniden uretilen hatalar.

Her test, duzeltmeden onceki kodda basarisiz olur:

1. Uzun mesajlar birikince gecmis paketi 64 KB'i asiyor, odaya girilemiyordu.
2. Sunucu adi "ayse-2" yapinca kendi mesajin kendine bildirim oluyordu.
3. Gizlilik kutularinin isareti kaldirilinca kaydedilmiyordu.
4. Demo'dan hemen cikinca sahte kullanicilar sonraki gercek oturuma siziyordu.
5. Baglanti yenilenince kullanici ilk baglandigi odaya donuyordu.
6. Sunucunun reddedecegi uzun mesaj kutudan siliniyordu.
"""

import os
import tempfile
import threading
import time
import unittest
from unittest import mock

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from apps.proxychat.i18n import t
from apps.proxychat.settings import ChatSettings
from apps.proxychat.ui import ChatPage, ConnectionController, ConnectPage, ProxyChatWindow
from core.client import ChatClient
from core.protocol import MAX_CONTENT_BYTES, encode_packet
from core.server import ChatServer
from core.transport import MAX_LINE_BYTES
from tests.test_client_lifecycle import bos_port
from tests.test_proxychat_ui import _olaylari_isle, izole_ayarlar


class _QtTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])


def _sunucu(testcase, keep_history=False):
    port = bos_port()
    server = ChatServer(host="127.0.0.1", port=port, keep_history=keep_history)
    server.start()
    testcase.addCleanup(server.stop)
    return server, port


class LongHistoryTests(unittest.TestCase):
    """1. Gecmis paketi istemcinin satir sinirina sigmali."""

    def _uzun_mesajlar(self, server, room, adet, boyut=7000):
        for index in range(adet):
            server._append_history(room, {
                "type": "message", "room": room, "user": "yazar",
                "content": f"{index:03d}" + "x" * boyut, "ts": 1.0,
            })

    def test_history_packet_fits_the_client_line_limit(self):
        server = ChatServer(keep_history=True)
        self._uzun_mesajlar(server, "general", 100)

        packet = server._history_packet("general")

        self.assertLessEqual(len(encode_packet(packet)), MAX_LINE_BYTES)
        self.assertTrue(packet["messages"], "hic mesaj yollanmadi")

    def test_newest_messages_are_kept_in_order(self):
        server = ChatServer(keep_history=True)
        self._uzun_mesajlar(server, "general", 30)

        icerikler = [m["content"][:3] for m in server._history_packet("general")["messages"]]

        self.assertEqual(icerikler[-1], "029", "en yeni mesaj atildi")
        self.assertEqual(icerikler, sorted(icerikler), "sira bozuldu")

    def test_short_history_is_sent_whole(self):
        server = ChatServer(keep_history=True)
        self._uzun_mesajlar(server, "general", 100, boyut=20)

        self.assertEqual(len(server._history_packet("general")["messages"]), 100)

    def test_joining_a_room_full_of_long_messages_works(self):
        server, port = _sunucu(self, keep_history=True)
        yazar = ChatClient()
        self.addCleanup(yazar.disconnect)
        yazar.connect("127.0.0.1", port, "general", "yazar")
        for _ in range(10):
            yazar.send_message("x" * 7000)
        time.sleep(0.5)

        durumlar = []
        gecmis = threading.Event()
        yeni = ChatClient(
            on_status=lambda st, pl: durumlar.append(st),
            on_packet=lambda pk: pk.get("type") == "history" and gecmis.set(),
        )
        self.addCleanup(yeni.disconnect)
        yeni.connect("127.0.0.1", port, "general", "yeni")

        self.assertTrue(gecmis.wait(5), "gecmis paketi gelmedi")
        time.sleep(0.3)
        self.assertNotIn("error", durumlar)
        self.assertTrue(yeni.connected, "uzun mesajli odaya giren atildi")


class ServerAssignedNameTests(_QtTestCase):
    """2. Kendi mesajini, sunucunun verdigi addan tanimak."""

    def _page(self):
        controller = ConnectionController()
        controller.username = "ayse"
        page = ChatPage(controller)
        self.addCleanup(page.deleteLater)
        self.bildirimler = []
        page.attention_requested.connect(lambda user, text: self.bildirimler.append(user))
        self.kalin = []
        orijinal = page._append_message

        def kaydet(user, content, ts=None, self_message=False):
            self.kalin.append(self_message)
            orijinal(user, content, ts, self_message)

        page._append_message = kaydet
        page.on_packet({"type": "joined", "room": "general", "user": "ayse-2", "snapshot": {"users": ["ayse", "ayse-2"]}})
        return page

    def test_own_message_under_a_renamed_user_does_not_notify(self):
        page = self._page()

        page.on_packet({"type": "message", "room": "general", "user": "ayse-2", "content": "benim"})

        self.assertEqual(self.bildirimler, [], "kendi mesajin icin bildirim geldi")
        self.assertEqual(self.kalin, [True])

    def test_the_other_ayse_still_notifies(self):
        page = self._page()

        page.on_packet({"type": "message", "room": "general", "user": "ayse", "content": "ben oteki ayse"})

        self.assertEqual(self.bildirimler, ["ayse"])
        self.assertEqual(self.kalin, [False])

    def test_real_session_with_a_duplicate_name(self):
        _server, port = _sunucu(self)
        eski = ChatClient()
        self.addCleanup(eski.disconnect)
        eski.connect("127.0.0.1", port, "general", "ayse")

        window = ProxyChatWindow(izole_ayarlar(self))
        self.addCleanup(window.controller.disconnect)
        window._start_connection("Join", "127.0.0.1", port, "general", "ayse", "")
        _olaylari_isle(5, lambda: window.stack.currentWidget() is window.chat_page)
        _olaylari_isle(0.5)
        bildirimler = []
        window.chat_page.attention_requested.connect(lambda user, text: bildirimler.append(user))

        window.controller.send_message("benim mesajim")
        _olaylari_isle(1.0)

        self.assertEqual(window.controller.client.username, "ayse-2", "test kosulu olusmadi")
        self.assertEqual(bildirimler, [])


class PrivacyChoicePersistenceTests(_QtTestCase):
    """3. Gizlilik kutulari isaretlendikleri anda saklanmali."""

    def setUp(self):
        for ad in ("delete_log_files", "set_logging_enabled"):
            yama = mock.patch(f"apps.proxychat.ui.{ad}")  # gercek log klasorune dokunma
            yama.start()
            self.addCleanup(yama.stop)
        handle, path = tempfile.mkstemp(suffix=".ini")
        os.close(handle)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        self.settings = ChatSettings(QSettings(path, QSettings.Format.IniFormat))

    def _page(self):
        page = ConnectPage(self.settings)
        self.addCleanup(page.deleteLater)
        return page

    def _eski_ayarlar(self, **degerler):
        varsayilan = dict(mode="Join", host="1.2.3.4", port="5555", room="general", username="ayse",
                          password="gizli", remember_password=True, logging_enabled=True, keep_history=True)
        varsayilan.update(degerler)
        self.settings.save(**varsayilan)

    def test_turning_logging_off_is_remembered_without_connecting(self):
        self._eski_ayarlar(logging_enabled=True)
        page = self._page()

        page.logging_box.setChecked(False)

        self.assertFalse(self.settings.load()["logging_enabled"], "tanilama kaydi sonraki acilista yeniden acilir")

    def test_turning_logging_on_is_remembered_too(self):
        self._eski_ayarlar(logging_enabled=False)
        page = self._page()

        page.logging_box.setChecked(True)

        self.assertTrue(self.settings.load()["logging_enabled"])

    def test_unchecking_remember_deletes_the_stored_password_at_once(self):
        self._eski_ayarlar()
        page = self._page()
        if not self.settings.load()["password"]:
            self.skipTest("bu makinede DPAPI yok, saklanan parola olusmadi")

        page.remember_password_box.setChecked(False)

        yuklenen = self.settings.load()
        self.assertFalse(yuklenen["remember_password"])
        self.assertEqual(yuklenen["password"], "", "sifreli parola diskte kaldi")
        self.assertEqual(self.settings._settings.value("password_blob", ""), "")

    def test_keep_history_choice_is_remembered(self):
        self._eski_ayarlar(keep_history=True)
        page = self._page()

        page.keep_history_box.setChecked(False)

        self.assertFalse(self.settings.load()["keep_history"])

    def test_opening_the_page_does_not_change_saved_choices(self):
        self._eski_ayarlar(logging_enabled=False, keep_history=False, remember_password=True)

        self._page()

        yuklenen = self.settings.load()
        self.assertFalse(yuklenen["logging_enabled"])
        self.assertFalse(yuklenen["keep_history"])
        self.assertTrue(yuklenen["remember_password"])


class DemoBotsStopTests(unittest.TestCase):
    """4. Demo kapaninca sahte kullanicilar durmali."""

    def test_leaving_demo_early_does_not_leak_bots_into_the_next_server(self):
        port = bos_port()
        controller = ConnectionController()
        self.addCleanup(controller.disconnect)
        controller.connect_async("Demo", "127.0.0.1", port, "general", "ayse", "")
        baslangic = time.monotonic()
        while controller.client is None or not controller.client.connected:
            self.assertLess(time.monotonic() - baslangic, 5, "Demo baslamadi")
            time.sleep(0.02)
        controller.disconnect()  # sahte kullanicilar 0.8 sn sonra baslar

        gercek = ChatServer(host="127.0.0.1", port=port)
        gercek.start()
        self.addCleanup(gercek.stop)
        gelenler = []
        dinleyici = ChatClient(on_packet=lambda pk: pk.get("type") == "message" and gelenler.append(pk.get("user")))
        self.addCleanup(dinleyici.disconnect)
        dinleyici.connect("127.0.0.1", port, "general", "mehmet")
        time.sleep(2.5)

        self.assertEqual(gelenler, [], "Demo'nun sahte kullanicilari gercek odaya girdi")

    def test_demo_bots_still_run_in_a_live_demo(self):
        port = bos_port()
        controller = ConnectionController()
        self.addCleanup(controller.disconnect)
        gelenler = []
        controller.packet_received.connect(lambda pk: pk.get("type") == "message" and gelenler.append(pk.get("user")))

        controller.connect_async("Demo", "127.0.0.1", port, "general", "ayse", "")
        baslangic = time.monotonic()
        app = QApplication.instance() or QApplication([])
        while len(gelenler) < 3 and time.monotonic() - baslangic < 6:
            app.processEvents()
            time.sleep(0.02)

        self.assertEqual(gelenler, ["nova", "atlas", "echo"])


class ReconnectRoomTests(_QtTestCase):
    """5. Baglanti yenilenince bulunulan odaya donulmeli."""

    def test_reconnect_uses_the_room_you_are_in(self):
        window = ProxyChatWindow(izole_ayarlar(self))
        self.addCleanup(window.close)
        cagrilar = []
        window.controller.connect_async = lambda *args: cagrilar.append(args)
        window.controller.disconnect = lambda: None
        window._start_connection("Join", "1.2.3.4", 5555, "general", "ayse", "gizli")
        window._on_connected({"room": "general", "host": "1.2.3.4", "port": 5555})
        window.chat_page.switch_room("oyun")
        cagrilar.clear()

        window._try_reconnect()

        self.assertEqual(cagrilar, [("Join", "1.2.3.4", 5555, "oyun", "ayse", "gizli")])

    def test_real_reconnect_lands_in_the_current_room(self):
        _server, port = _sunucu(self)
        window = ProxyChatWindow(izole_ayarlar(self))
        self.addCleanup(window.controller.disconnect)
        window._start_connection("Join", "127.0.0.1", port, "general", "ayse", "")
        _olaylari_isle(5, lambda: window.stack.currentWidget() is window.chat_page)
        window.chat_page.switch_room("oyun")
        _olaylari_isle(0.8)

        window._try_reconnect()
        _olaylari_isle(3, lambda: window.controller.client is not None and window.controller.client.room == "oyun"
                       and not window.controller.busy)
        _olaylari_isle(0.5)

        self.assertEqual(window.chat_page.current_room, "oyun")
        self.assertEqual(window.controller.client.room, "oyun")


class TooLongMessageTests(_QtTestCase):
    """6. Reddedilecek uzun mesaj kutuda kalmali."""

    def _baglan(self, parola):
        _server, port = _sunucu(self)
        # Pencere test nesnesinde tutulur; yoksa cop toplayici sayfayi siler.
        self.window = window = ProxyChatWindow(izole_ayarlar(self))
        self.addCleanup(window.controller.disconnect)
        window._start_connection("Join", "127.0.0.1", port, "general", "ayse", parola)
        _olaylari_isle(5, lambda: window.stack.currentWidget() is window.chat_page)
        _olaylari_isle(0.5)
        return window.chat_page

    def test_too_long_message_stays_in_the_box(self):
        page = self._baglan("")
        metin = "ç" * 5000  # 10.000 bayt

        page.message_input.setText(metin)
        page._send_message()
        _olaylari_isle(0.5)

        self.assertEqual(page.message_input.text(), metin, "yazilan metin kayboldu")
        self.assertIn(t("chat.message_too_long"), page.message_view.toPlainText())

    def test_limit_is_measured_after_encryption(self):
        # Duz metin sinirin altinda, sifreli hali ustunde.
        page = self._baglan("gizli")
        metin = "x" * 6500
        self.assertLess(len(metin.encode()), MAX_CONTENT_BYTES)

        page.message_input.setText(metin)
        page._send_message()
        _olaylari_isle(0.5)

        self.assertEqual(page.message_input.text(), metin)

    def test_normal_message_is_still_sent(self):
        page = self._baglan("gizli")

        page.message_input.setText("selam")
        page._send_message()
        _olaylari_isle(1.0)

        self.assertEqual(page.message_input.text(), "")
        self.assertIn("selam", page.message_view.toPlainText())


if __name__ == "__main__":
    unittest.main()
