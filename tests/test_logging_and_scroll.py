"""Log dosyasi ve sohbet akisinin kaydirma davranisi.

Log: sunucu olaylari eskiden print ile stdout'a gidiyordu, pencereli exe'de
hicbir yere. Testci bir sorun bildirdiginde bakilacak kayit yoktu.

Kaydirma: her yeni mesajda ekran zorla en alta atliyordu; gecmisi okurken
biri yazdiginda okudugun yeri kaybediyordun.
"""

import logging
import os
import tempfile
import threading
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from apps.proxychat.logging_setup import log_file_path, setup_logging
from apps.proxychat.ui import ChatPage, ConnectionController
from core.client import ChatClient
from core.server import ChatServer
from core.server_state import AnonymousLogger


class LogDestinationTests(unittest.TestCase):
    def test_log_path_lives_under_the_local_app_data_folder(self):
        path = log_file_path()

        self.assertEqual(path.name, "proxychat.log")
        self.assertIn("ProxyChat", str(path))

    def test_setup_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            eski = os.environ.get("LOCALAPPDATA")
            os.environ["LOCALAPPDATA"] = tmp
            logger = logging.getLogger("proxychat")
            onceki = list(logger.handlers)
            logger.handlers = []
            try:
                first = setup_logging()
                second = setup_logging()
                self.assertEqual(first, second)
                self.assertEqual(len(logger.handlers), 1, "handler iki kez eklendi")
            finally:
                for handler in logger.handlers:
                    handler.close()
                logger.handlers = onceki
                if eski is None:
                    os.environ.pop("LOCALAPPDATA", None)
                else:
                    os.environ["LOCALAPPDATA"] = eski


class ServerLoggingTests(unittest.TestCase):
    """Sunucu olaylari logging'e gidiyor ve icerik sizdirmiyor."""

    def test_events_reach_the_logger_and_carry_no_message_length(self):
        port = 8861
        server = ChatServer(port=port)
        server.start()

        kayitlar: list[str] = []

        class Yakalayici(logging.Handler):
            def emit(self, record):
                kayitlar.append(record.getMessage())

        handler = Yakalayici()
        logger = logging.getLogger("proxychat.server")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        joined = threading.Event()
        client = ChatClient(
            on_packet=lambda p: joined.set() if p.get("type") == "joined" else None
        )
        try:
            client.connect("127.0.0.1", port, "general", "ayse")
            self.assertTrue(joined.wait(5), "istemci katilamadi")
            client.send_message("cok gizli bir mesaj")

            import time

            son = time.monotonic() + 5
            while time.monotonic() < son and not any("message_received" in k for k in kayitlar):
                time.sleep(0.05)

            self.assertTrue(any("client_joined" in k for k in kayitlar), "katilma olayi loglanmadi")
            self.assertTrue(any("message_received" in k for k in kayitlar), "mesaj olayi loglanmadi")

            hepsi = " ".join(kayitlar)
            self.assertNotIn("cok gizli bir mesaj", hepsi, "mesaj icerigi loga sizdi")
            self.assertNotIn("content_length", hepsi, "mesaj uzunlugu loga sizdi")
        finally:
            logger.removeHandler(handler)
            client.disconnect()
            server.stop()

    def test_anonymous_logger_still_hides_content_itself(self):
        """Bicimlendirici zaten icerigi yazmiyordu; bu guvence korunuyor."""
        satir = AnonymousLogger().format_event(
            "message_received", "general", details={"content": "gizli", "status": "ok"}
        )

        self.assertNotIn("gizli", satir)


class _SahteBar:
    """Gercek QScrollBar yerine: degerleri elle kontrol edebilelim."""

    def __init__(self, value: int, maximum: int) -> None:
        self._value = value
        self._maximum = maximum

    def value(self) -> int:
        return self._value

    def maximum(self) -> int:
        return self._maximum

    def setValue(self, value: int) -> None:
        self._value = value


class _SahteGorunum:
    """Icerik eklendikce kaydirilabilir alani buyuyen sahte mesaj gorunumu."""

    def __init__(self, bar: _SahteBar) -> None:
        self._bar = bar

    def verticalScrollBar(self) -> _SahteBar:
        return self._bar

    def append(self, _html: str) -> None:
        self._bar._maximum += 10


class ScrollFollowTests(unittest.TestCase):
    """Kaydirma karari.

    Gercek QScrollBar kullanilamiyor: widget gosterilmediginde Qt belge
    duzenini hesaplamiyor ve maximum() hep 0 kaliyor. Bunun yerine sahte bir
    gorunumle karar mantigi ve SIRALAMA test ediliyor -- "takip ediyor mu"
    olcumu icerik eklenmeden ONCE yapilmali.
    """

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _page(self, value: int, maximum: int):
        page = ChatPage(ConnectionController())
        self.addCleanup(page.deleteLater)
        bar = _SahteBar(value, maximum)
        page.message_view = _SahteGorunum(bar)
        return page, bar

    def test_following_is_detected_at_the_bottom(self):
        page, _bar = self._page(value=100, maximum=100)

        self.assertTrue(page._is_following_latest())

    def test_a_few_pixels_of_tolerance_still_counts_as_following(self):
        page, _bar = self._page(value=97, maximum=100)

        self.assertTrue(page._is_following_latest())

    def test_scrolled_up_is_not_following(self):
        page, _bar = self._page(value=0, maximum=100)

        self.assertFalse(page._is_following_latest())

    def test_new_message_scrolls_down_when_you_are_at_the_bottom(self):
        page, bar = self._page(value=100, maximum=100)

        page._append_message("mehmet", "yeni mesaj")

        self.assertEqual(bar.value(), bar.maximum(), "en alttayken asagi inilmedi")

    def test_reading_history_is_not_interrupted(self):
        page, bar = self._page(value=0, maximum=100)

        page._append_message("mehmet", "yeni mesaj geldi")

        self.assertEqual(bar.value(), 0, "kullanici zorla asagi cekildi")

    def test_system_lines_follow_the_same_rule(self):
        page, bar = self._page(value=0, maximum=100)

        page._append_system("mehmet kanaldan ayrıldı.")

        self.assertEqual(bar.value(), 0)

    def test_system_line_scrolls_down_when_following(self):
        page, bar = self._page(value=100, maximum=100)

        page._append_system("mehmet kanala katıldı.")

        self.assertEqual(bar.value(), bar.maximum())



class LogFormatTests(unittest.TestCase):
    def test_status_appears_only_once(self):
        """status hem ozel dalda hem genel donguye giriyordu; iki kez yaziliyordu."""
        satir = AnonymousLogger().format_event("client_joined", "general", details={"status": "ok"})

        self.assertEqual(satir.count("status="), 1, f"status tekrarlandi: {satir}")

    def test_other_details_still_appear(self):
        satir = AnonymousLogger().format_event(
            "x", "general", details={"status": "ok", "reason": "timeout"}
        )

        self.assertIn("reason=timeout", satir)
        self.assertIn("status=ok", satir)


class HistoryToggleTests(unittest.TestCase):
    """Gecmis tutma kapatilabilmeli: calisan makineden alinacak yigin kalmasin."""

    def _sunucu_ve_istemci(self, port, keep_history):
        server = ChatServer(port=port, keep_history=keep_history)
        server.start()
        self.addCleanup(server.stop)
        joined = threading.Event()
        client = ChatClient(on_packet=lambda p: joined.set() if p.get("type") == "joined" else None)
        client.connect("127.0.0.1", port, "general", "ayse")
        self.addCleanup(client.disconnect)
        self.assertTrue(joined.wait(5), "istemci katilamadi")
        return server, client

    def test_history_is_kept_when_turned_on(self):
        server, client = self._sunucu_ve_istemci(8871, keep_history=True)

        client.send_message("hatirlanacak")
        import time

        son = time.monotonic() + 5
        while time.monotonic() < son and not server._history.get("general"):
            time.sleep(0.05)

        self.assertTrue(server._history.get("general"), "gecmis acikken tutulmadi")

    def test_nothing_is_retained_when_history_is_off(self):
        server, client = self._sunucu_ve_istemci(8872, keep_history=False)

        for index in range(5):
            client.send_message(f"unutulacak {index}")
        import time

        time.sleep(1.0)

        self.assertEqual(server._history, {}, "gecmis kapaliyken mesaj bellekte tutuldu")

    def test_late_joiner_gets_no_history_packet_when_off(self):
        server, _client = self._sunucu_ve_istemci(8873, keep_history=False)

        gelen = []
        joined = threading.Event()

        def yakala(packet):
            gelen.append(packet.get("type"))
            if packet.get("type") == "joined":
                joined.set()

        ikinci = ChatClient(on_packet=yakala)
        ikinci.connect("127.0.0.1", 8873, "general", "mehmet")
        self.addCleanup(ikinci.disconnect)
        self.assertTrue(joined.wait(5), "ikinci istemci katilamadi")
        import time

        time.sleep(0.5)

        self.assertNotIn("history", gelen, "gecmis kapaliyken history paketi yollandi")


class LoggingToggleTests(unittest.TestCase):
    """Tanilama kaydi kapatilabilmeli ve kapatilinca dosyalar silinmeli."""

    def setUp(self):
        from apps.proxychat import logging_setup

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._eski = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = self._tmp.name

        logger = logging.getLogger("proxychat")
        self._onceki = list(logger.handlers)
        logger.handlers = []

        def geri_al():
            logging_setup.teardown_logging()
            logging.getLogger("proxychat").handlers = self._onceki
            if self._eski is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = self._eski

        self.addCleanup(geri_al)

    def test_enabling_creates_the_file(self):
        from apps.proxychat.logging_setup import set_logging_enabled

        path = set_logging_enabled(True)

        self.assertIsNotNone(path)
        self.assertTrue(Path(path).exists())

    def test_disabling_removes_the_handler(self):
        from apps.proxychat.logging_setup import set_logging_enabled

        set_logging_enabled(True)
        set_logging_enabled(False)

        logger = logging.getLogger("proxychat")
        self.assertEqual(logger.handlers, [], "kayit kapatildi ama handler duruyor")

    def test_nothing_is_written_after_disabling(self):
        from apps.proxychat.logging_setup import log_file_path, set_logging_enabled

        set_logging_enabled(True)
        logging.getLogger("proxychat.server").info("ilk-satir")
        set_logging_enabled(False)
        logging.getLogger("proxychat.server").info("bu-yazilmamali")

        if log_file_path().exists():
            self.assertNotIn("bu-yazilmamali", log_file_path().read_text(encoding="utf-8"))

    def test_delete_removes_existing_log_files(self):
        from apps.proxychat.logging_setup import delete_log_files, log_file_path, set_logging_enabled

        set_logging_enabled(True)
        logging.getLogger("proxychat.server").info("silinecek")
        self.assertTrue(log_file_path().exists())

        silinen = delete_log_files()

        self.assertGreaterEqual(silinen, 1)
        self.assertFalse(log_file_path().exists(), "kayit dosyasi silinmedi")

if __name__ == "__main__":
    unittest.main()
