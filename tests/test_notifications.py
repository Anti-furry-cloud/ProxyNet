"""Arka plan bildirimi ve kendi mesajinin ayirt edilmesi.

Eskiden pencere arkadayken mesaj geldigini anlamanin hicbir yolu yoktu;
uygulama ancak ekrana bakarken calisiyordu. Ayrica kendi mesajin
digerlerinden gorsel olarak ayrismiyordu (_append_message'in self_message
parametresi hic gecirilmiyordu).
"""

import unittest

from PySide6.QtWidgets import QApplication

from apps.proxychat.ui import ChatPage, ConnectionController, ProxyChatWindow
from apps.proxychat.i18n import t
from tests.test_proxychat_ui import izole_ayarlar


class _QtTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])


class AttentionSignalTests(_QtTestCase):
    def _page(self, own_username="ayse"):
        controller = ConnectionController()
        controller.username = own_username
        page = ChatPage(controller)
        self.addCleanup(page.deleteLater)
        self.signals = []
        page.attention_requested.connect(lambda user, text: self.signals.append((user, text)))
        return page

    def test_message_from_someone_else_asks_for_attention(self):
        page = self._page()

        page.on_packet({"type": "message", "room": "general", "user": "mehmet", "content": "selam"})

        self.assertEqual(self.signals, [("mehmet", "selam")])

    def test_your_own_message_does_not_ask_for_attention(self):
        page = self._page(own_username="ayse")

        page.on_packet({"type": "message", "room": "general", "user": "ayse", "content": "ben yazdim"})

        self.assertEqual(self.signals, [], "kendi mesajin icin bildirim istendi")

    def test_message_in_another_room_is_ignored(self):
        page = self._page()
        page.current_room = "general"

        page.on_packet({"type": "message", "room": "oyun", "user": "mehmet", "content": "baska oda"})

        self.assertEqual(self.signals, [])

    def test_undecryptable_message_does_not_leak_into_a_notification(self):
        page = self._page()

        page.on_packet({
            "type": "message", "room": "general", "user": "mehmet",
            "content": "[cozulemedi]", "decrypt_failed": True,
        })

        self.assertEqual(self.signals, [], "cozulemeyen mesaj icin bildirim istendi")


class OwnMessageStylingTests(_QtTestCase):
    def test_your_own_message_is_marked_as_yours(self):
        controller = ConnectionController()
        controller.username = "ayse"
        page = ChatPage(controller)
        self.addCleanup(page.deleteLater)

        kayit = []
        page._append_message = lambda user, content, ts=None, self_message=False: kayit.append(self_message)

        page.on_packet({"type": "message", "room": "general", "user": "ayse", "content": "benim"})
        page.on_packet({"type": "message", "room": "general", "user": "mehmet", "content": "onun"})

        self.assertEqual(kayit, [True, False], "kendi mesaji ayirt edilmedi")


class WindowNotificationTests(_QtTestCase):
    def _window(self):
        window = ProxyChatWindow(izole_ayarlar(self))
        self.addCleanup(window.close)
        return window

    def test_no_alert_while_the_window_is_active(self):
        window = self._window()
        window.isActiveWindow = lambda: True
        cagrildi = []
        if window.tray_icon is not None:
            window.tray_icon.showMessage = lambda *args: cagrildi.append(args)

        window._on_attention_requested("mehmet", "selam")

        self.assertEqual(cagrildi, [], "pencere ondeyken bildirim gosterildi")

    def test_alert_when_the_window_is_not_active(self):
        window = self._window()
        window.isActiveWindow = lambda: False
        if window.tray_icon is None:
            self.skipTest("bu makinede sistem tepsisi yok")
        cagrildi = []
        window.tray_icon.showMessage = lambda *args: cagrildi.append(args)

        window._on_attention_requested("mehmet", "selam")

        self.assertEqual(len(cagrildi), 1, "pencere arkadayken bildirim gosterilmedi")
        self.assertIn("mehmet", cagrildi[0][0])

    def test_long_message_preview_is_trimmed(self):
        window = self._window()
        window.isActiveWindow = lambda: False
        if window.tray_icon is None:
            self.skipTest("bu makinede sistem tepsisi yok")
        cagrildi = []
        window.tray_icon.showMessage = lambda *args: cagrildi.append(args)

        window._on_attention_requested("mehmet", "x" * 500)

        self.assertLessEqual(len(cagrildi[0][1]), 120)

    def test_encrypted_room_keeps_content_out_of_the_notification(self):
        """Windows bildirimleri diske yazar; sifreli odada metin oraya gitmemeli."""
        window = self._window()
        window.isActiveWindow = lambda: False
        if window.tray_icon is None:
            self.skipTest("bu makinede sistem tepsisi yok")
        cagrildi = []
        window.tray_icon.showMessage = lambda *args: cagrildi.append(args)
        window.controller.room_password = "gizli-parola"

        window._on_attention_requested("mehmet", "banka sifrem 1234")

        self.assertIn("mehmet", cagrildi[0][0])
        self.assertNotIn("1234", cagrildi[0][1])
        self.assertEqual(cagrildi[0][1], t("tray.content_hidden"))

    def test_plain_room_still_shows_the_preview(self):
        window = self._window()
        window.isActiveWindow = lambda: False
        if window.tray_icon is None:
            self.skipTest("bu makinede sistem tepsisi yok")
        cagrildi = []
        window.tray_icon.showMessage = lambda *args: cagrildi.append(args)
        window.controller.room_password = ""

        window._on_attention_requested("mehmet", "selam")

        self.assertEqual(cagrildi[0][1], "selam")

    def test_missing_tray_does_not_crash(self):
        window = self._window()
        window.isActiveWindow = lambda: False
        window.tray_icon = None

        window._on_attention_requested("mehmet", "selam")  # patlamamali



class MembershipAnnouncementTests(_QtTestCase):
    """Katilma/ayrilma satirlari, oda anlik goruntusundeki farktan uretilir."""

    def _page(self):
        page = ChatPage(ConnectionController())
        self.addCleanup(page.deleteLater)
        self.lines = []
        page._append_system = lambda text: self.lines.append(text)
        return page

    def test_first_snapshot_does_not_announce_everyone(self):
        page = self._page()

        page._apply_snapshot({"users": ["ayse", "mehmet"]})

        self.assertEqual(self.lines, [], "odaya girerken herkes katildi diye yazildi")

    def test_new_user_is_announced(self):
        page = self._page()
        page._apply_snapshot({"users": ["ayse"]})

        page._apply_snapshot({"users": ["ayse", "mehmet"]})

        self.assertEqual(self.lines, [t("chat.user_joined", user="mehmet")])

    def test_leaving_user_is_announced(self):
        page = self._page()
        page._apply_snapshot({"users": ["ayse", "mehmet"]})

        page._apply_snapshot({"users": ["ayse"]})

        self.assertEqual(self.lines, [t("chat.user_left", user="mehmet")])

    def test_unchanged_list_says_nothing(self):
        page = self._page()
        page._apply_snapshot({"users": ["ayse", "mehmet"]})

        page._apply_snapshot({"users": ["mehmet", "ayse"]})

        self.assertEqual(self.lines, [])

    def test_switching_room_resets_the_baseline(self):
        page = self._page()
        page._apply_snapshot({"users": ["ayse"]})
        page.controller.switch_room = lambda room: None

        page.switch_room("oyun")
        page._apply_snapshot({"users": ["eda", "kerem"]})

        self.assertEqual(self.lines, [], "oda degisiminde eski liste ile karsilastirilmis")

    def test_reconnecting_to_the_same_room_resets_the_baseline(self):
        """Smoke testinde goruldu: yeniden baglanan kisi kendini "katildi" diye goruyordu."""
        page = self._page()
        page._apply_snapshot({"users": ["ayse"]})

        page.on_packet({
            "type": "joined", "room": "general", "user": "ayse-2",
            "snapshot": {"users": ["ayse", "ayse-2"]},
        })
        page._apply_snapshot({"users": ["ayse", "ayse-2"]})

        self.assertEqual(self.lines, [t("chat.joined_self", user="ayse-2")], self.lines)


class RoomMoveAnnouncementTests(_QtTestCase):
    """Smoke testinde goruldu: baska odaya gidip gelen biri icin her seferinde
    "ayrildi" ve "katildi" satiri yaziliyordu. Oda gecisi artik ayri ve art
    arda git-geller tek satirda."""

    def _page(self):
        page = ChatPage(ConnectionController())
        self.addCleanup(page.deleteLater)
        page.on_packet({"type": "joined", "room": "general", "user": "ayse",
                        "snapshot": {"users": ["ayse", "mehmet"]}})
        return page

    @staticmethod
    def _gitti(page):
        page.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse"], "moved": ["mehmet"]})

    @staticmethod
    def _geldi(page):
        page.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse", "mehmet"]})

    def _satirlar(self, page):
        return [s for s in page.message_view.toPlainText().splitlines() if "mehmet" in s]

    def test_repeated_moves_collapse_into_one_line(self):
        page = self._page()

        for _ in range(7):
            self._gitti(page)
            self._geldi(page)

        self.assertEqual(self._satirlar(page), [t("chat.user_moved_back_many", user="mehmet", count=7)])

    def test_single_move_and_return(self):
        page = self._page()

        self._gitti(page)
        self.assertEqual(self._satirlar(page), [t("chat.user_moved", user="mehmet")])
        self._geldi(page)

        self.assertEqual(self._satirlar(page), [t("chat.user_moved_back", user="mehmet")])

    def test_moving_away_again_updates_the_same_line(self):
        page = self._page()
        self._gitti(page)
        self._geldi(page)

        self._gitti(page)

        self.assertEqual(self._satirlar(page), [t("chat.user_moved_many", user="mehmet", count=2)])

    def test_a_message_in_between_starts_a_new_line(self):
        page = self._page()
        self._gitti(page)
        page.on_packet({"type": "message", "room": "general", "user": "ayse", "content": "neredesin", "ts": 1.0})

        self._geldi(page)

        akis = page.message_view.toPlainText()
        self.assertIn(t("chat.user_moved", user="mehmet"), akis)
        self.assertLess(akis.index("neredesin"), akis.index(t("chat.user_returned", user="mehmet")))

    def test_disconnect_is_still_left_and_joined(self):
        page = self._page()

        page.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse"]})
        self._geldi(page)

        self.assertEqual(self._satirlar(page), [t("chat.user_left", user="mehmet"), t("chat.user_joined", user="mehmet")])

    def test_other_lines_are_not_removed(self):
        page = self._page()
        page.on_packet({"type": "message", "room": "general", "user": "ayse", "content": "ilk mesaj", "ts": 1.0})

        for _ in range(3):
            self._gitti(page)
            self._geldi(page)

        akis = page.message_view.toPlainText()
        self.assertIn("ilk mesaj", akis)
        self.assertIn(t("chat.joined_self", user="ayse"), akis)


class TimestampTests(_QtTestCase):
    def test_todays_message_shows_only_the_time(self):
        import time

        page = ChatPage(ConnectionController())
        self.addCleanup(page.deleteLater)

        stamp = page._format_timestamp(time.time())

        self.assertRegex(stamp, r"^\d{2}:\d{2}$")

    def test_older_message_shows_the_date(self):
        import time

        page = ChatPage(ConnectionController())
        self.addCleanup(page.deleteLater)

        stamp = page._format_timestamp(time.time() - 3 * 24 * 3600)

        # Gun, secili dildeki ay adi, saat: "9 Sep 14:05"
        self.assertRegex(stamp, r"^\d{1,2} \S+ \d{2}:\d{2}$")

    def test_broken_timestamp_does_not_crash(self):
        page = ChatPage(ConnectionController())
        self.addCleanup(page.deleteLater)

        self.assertEqual(page._format_timestamp("bozuk"), "--:--")
        self.assertEqual(page._format_timestamp(None), "--:--")

if __name__ == "__main__":
    unittest.main()
