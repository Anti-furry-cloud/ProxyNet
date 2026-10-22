"""ProxyChat arayuz davranisi.

Odak: baglanti koptugunda kullanicinin cikmaz sokakta kalmamasi. Eskiden
kopan baglanti sonrasi sohbet ekrani kilitleniyor ve uygulamayi kapatip
acmaktan baska yol kalmiyordu.
"""

import time
import unittest

from PySide6.QtWidgets import QApplication

from apps.proxychat.i18n import t
from apps.proxychat.ui import RECONNECT_ATTEMPTS, ProxyChatWindow

def izole_ayarlar_ve_yol(testcase):
    """Gercek registry yerine gecici bir INI dosyasi: (ayar nesnesi, yol).

    Bu olmadan arayuz testleri kullanicinin gercek ayarlarina yaziyor ve
    okuyordu: hem kirletiyor hem de testin sonucu makinede kayitli degerlere
    bagli hale geliyordu. Yol, dosyaya NE yazildigini okumak isteyen testler
    icin (ornegin cihaz adinin kayda girmedigini dogrulayan).
    """
    import tempfile, os
    from PySide6.QtCore import QSettings
    from apps.proxychat.settings import ChatSettings

    handle, path = tempfile.mkstemp(suffix=".ini")
    os.close(handle)
    testcase.addCleanup(lambda: os.path.exists(path) and os.remove(path))
    return ChatSettings(QSettings(path, QSettings.Format.IniFormat)), path


def izole_ayarlar(testcase):
    """Gercek registry yerine gecici bir INI dosyasi kullanan ayar nesnesi."""
    return izole_ayarlar_ve_yol(testcase)[0]



class _QtTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _window(self):
        window = ProxyChatWindow(izole_ayarlar(self))
        self.addCleanup(window.close)
        # Gercek ag baglantisi kurulmasin; cagrilari kaydet.
        self.calls = []
        window.controller.connect_async = lambda *args: self.calls.append(args)
        window.controller.disconnect = lambda: self.calls.append(("disconnect",))
        # Zamanlayici testlerde kendiliginden atesleme yapmasin.
        window._reconnect_timer.stop()
        return window

    def _enter_chat(self, window):
        window._start_connection("Join", "1.2.3.4", 5555, "general", "ayse", "gizli")
        window._on_connected({"room": "general", "host": "1.2.3.4", "port": 5555})
        self.assertIs(window.stack.currentWidget(), window.chat_page)


class ReconnectTests(_QtTestCase):
    def test_unexpected_drop_schedules_a_reconnect_instead_of_freezing(self):
        window = self._window()
        self._enter_chat(window)

        window._on_status("disconnected", {"room": "general", "intentional": False})

        self.assertTrue(window._reconnect_timer.isActive(), "yeniden baglanma planlanmadi")
        self.assertIs(window.stack.currentWidget(), window.chat_page)
        self.assertEqual(window._reconnect_attempt, 1)

    def test_intentional_disconnect_does_not_reconnect(self):
        window = self._window()
        self._enter_chat(window)

        window._on_status("disconnected", {"room": "general", "intentional": True})

        self.assertFalse(window._reconnect_timer.isActive())
        self.assertEqual(window._reconnect_attempt, 0)

    def test_reconnect_uses_the_original_connection_details(self):
        window = self._window()
        self._enter_chat(window)
        self.calls.clear()

        window._try_reconnect()

        # Once eski oturum kapatilir (Host modunda port serbest kalsin), sonra baglanilir.
        self.assertEqual(self.calls[0], ("disconnect",))
        self.assertEqual(self.calls[1], ("Join", "1.2.3.4", 5555, "general", "ayse", "gizli"))

    def test_gives_up_after_the_attempt_limit_and_returns_to_connect_page(self):
        window = self._window()
        self._enter_chat(window)

        for _ in range(RECONNECT_ATTEMPTS + 1):
            window._reconnect_timer.stop()
            window._schedule_reconnect()

        self.assertIs(
            window.stack.currentWidget(),
            window.connect_page,
            "deneme hakki bitince baglanti ekranina donulmedi",
        )
        self.assertEqual(
            window.connect_page.status_label.text(),
            t("connect.reconnect_gave_up", attempts=RECONNECT_ATTEMPTS),
        )

    def test_successful_reconnect_clears_the_attempt_counter(self):
        window = self._window()
        self._enter_chat(window)
        window._on_status("disconnected", {"room": "general", "intentional": False})
        self.assertEqual(window._reconnect_attempt, 1)

        window._on_connected({"room": "general", "host": "1.2.3.4", "port": 5555})

        self.assertEqual(window._reconnect_attempt, 0)
        self.assertFalse(window._reconnect_timer.isActive())

    def test_failure_during_reconnect_retries_instead_of_dumping_the_user(self):
        window = self._window()
        self._enter_chat(window)

        window._on_connect_failed("baglanti reddedildi")

        self.assertIs(window.stack.currentWidget(), window.chat_page)
        self.assertTrue(window._reconnect_timer.isActive())

    def test_failure_on_the_connect_page_still_shows_the_error(self):
        window = self._window()

        window._on_connect_failed("host bulunamadi")

        self.assertIs(window.stack.currentWidget(), window.connect_page)
        self.assertEqual(window.connect_page.status_label.text(), "host bulunamadi")


class LeaveButtonTests(_QtTestCase):
    def test_leave_button_returns_to_the_connect_page(self):
        window = self._window()
        self._enter_chat(window)

        window.chat_page.leave_button.click()

        self.assertIs(window.stack.currentWidget(), window.connect_page)
        self.assertEqual(window._reconnect_attempt, 0)
        self.assertFalse(window._reconnect_timer.isActive())

    def test_leaving_deliberately_closes_the_session(self):
        window = self._window()
        self._enter_chat(window)
        self.calls.clear()

        window.chat_page.leave_button.click()

        self.assertIn(("disconnect",), self.calls)


class LeaveWithRealConnectionTests(_QtTestCase):
    """Gercek baglantida 'Baglantiyi kes' hata metni gostermemeli.

    Kasitli kapatmada istemcinin dinleme thread'i kapanan soketten OSError
    aliyor ve bunu hata olarak yayiyordu; baglanti ekraninda her seferinde
    "[WinError 10038] Bir islem yuva olmayan bir oge uzerinde denendi" yaziyordu.
    """

    def _pompala(self, saniye, kosul=lambda: False):
        bitis = time.monotonic() + saniye
        while time.monotonic() < bitis and not kosul():
            self._app.processEvents()
            time.sleep(0.02)

    def test_leaving_shows_no_error_text(self):
        from core.server import ChatServer
        from tests.test_client_lifecycle import bos_port

        port = bos_port()
        server = ChatServer(host="127.0.0.1", port=port)
        server.start()
        self.addCleanup(server.stop)
        window = ProxyChatWindow(izole_ayarlar(self))
        self.addCleanup(window.controller.disconnect)

        window.controller.connect_async("Join", "127.0.0.1", port, "general", "ayse", "")
        self._pompala(5, lambda: window.stack.currentWidget() is window.chat_page)
        self.assertIs(window.stack.currentWidget(), window.chat_page, "baglanilamadi")
        self._pompala(0.3)  # dinleme thread'i recv'de beklemeye girsin

        window.chat_page.leave_button.click()
        self._pompala(1.0)  # kuyruktaki sinyaller islensin

        self.assertIs(window.stack.currentWidget(), window.connect_page)
        self.assertEqual(window.connect_page.status_label.text(), "")


def _olaylari_isle(saniye, kosul=lambda: False):
    bitis = time.monotonic() + saniye
    while time.monotonic() < bitis and not kosul():
        QApplication.processEvents()
        time.sleep(0.02)


class RealSessionDisplayTests(_QtTestCase):
    """Gercek baglantida oturum ayrintilari dogru gorunmeli.

    Eski testler bu bilgileri elle uydurup sayfaya veriyordu ve hata hic
    gorunmedi: gercek oturumda gosterge parola girilse de hep "Oda parolasi
    yok" diyordu, Host'un paylasacagi adres hic cikmiyordu ve gecmis paketi
    katilma satiriyla sifreleme bildirimini ekrandan siliyordu.
    """

    def _baglan(self, mode, password):
        from core.server import ChatServer
        from tests.test_client_lifecycle import bos_port

        port = bos_port()
        window = ProxyChatWindow(izole_ayarlar(self))
        self.addCleanup(window.controller.disconnect)
        if mode == "Join":
            server = ChatServer(host="127.0.0.1", port=port, keep_history=True)
            server.start()
            self.addCleanup(server.stop)

        window.controller.connect_async(mode, "127.0.0.1", port, "general", "ayse", password)
        _olaylari_isle(5, lambda: window.stack.currentWidget() is window.chat_page)
        self.assertIs(window.stack.currentWidget(), window.chat_page, "baglanilamadi")
        _olaylari_isle(0.5)  # joined, history ve snapshot paketleri islensin
        return window, port

    def test_indicator_says_encrypted_when_a_password_was_entered(self):
        window, _port = self._baglan("Join", "gizli")

        self.assertIn(t("chat.lock_encrypted"), window.chat_page.connection_status.text())

    def test_indicator_says_unencrypted_without_a_password(self):
        window, _port = self._baglan("Join", "")

        self.assertIn(t("chat.lock_plain"), window.chat_page.connection_status.text())

    def test_host_shows_the_address_to_share(self):
        window, port = self._baglan("Host", "")

        self.assertIn(f"127.0.0.1:{port}", window.chat_page.server_hint.toPlainText())

    def test_join_line_and_encryption_notice_survive_the_history_packet(self):
        window, _port = self._baglan("Join", "gizli")

        akis = window.chat_page.message_view.toPlainText()
        self.assertIn(t("chat.joined_self", user="ayse"), akis)
        self.assertEqual(akis.count(t("chat.encrypted_notice")), 1, akis)


def _busy_taklidi(testcase, deger: bool):
    """ConnectionController.busy'yi gecici olarak sabitler.

    delattr ile silmek sinifin gercek ozelligini yok ediyordu; orijinal
    saklanip geri konuyor.
    """
    from apps.proxychat.ui import ConnectionController

    orijinal = ConnectionController.busy
    ConnectionController.busy = property(lambda self: deger)
    testcase.addCleanup(lambda: setattr(ConnectionController, "busy", orijinal))


class ReconnectChainTests(_QtTestCase):
    """Yeniden baglanma zinciri sessizce olmemeli.

    connect_async, onceki isci hala calisirken hicbir sinyal yaymadan geri
    donuyordu; pencere ne basari ne hata duydugu icin bir sonraki denemeyi
    planlamiyor ve kullanici kilitli sohbet ekraninda kaliyordu.
    """

    def test_busy_controller_keeps_the_chain_alive_without_burning_an_attempt(self):
        window = self._window()
        self._enter_chat(window)
        _busy_taklidi(self, True)
        window._reconnect_attempt = 1

        window._try_reconnect()

        self.assertTrue(window._reconnect_timer.isActive(), "zincir koptu")
        self.assertEqual(window._reconnect_attempt, 1, "deneme hakki bosuna yandi")
        self.assertEqual(window._reconnect_busy_waits, 1)

    def test_endless_busy_eventually_gives_up_with_a_message(self):
        from apps.proxychat.ui import MAX_RECONNECT_BUSY_WAITS

        window = self._window()
        self._enter_chat(window)
        _busy_taklidi(self, True)

        for _ in range(MAX_RECONNECT_BUSY_WAITS + 1):
            window._reconnect_timer.stop()
            window._try_reconnect()

        self.assertIs(window.stack.currentWidget(), window.connect_page)
        self.assertEqual(window.connect_page.status_label.text(), t("connect.previous_attempt_pending"))

    def test_refused_start_reschedules_instead_of_dropping(self):
        window = self._window()
        self._enter_chat(window)
        window.controller.connect_async = lambda *args: False  # baslatilamadi

        window._try_reconnect()

        self.assertTrue(window._reconnect_timer.isActive(), "reddedilen deneme zinciri kirdi")

    def test_busy_counter_resets_after_a_successful_connect(self):
        window = self._window()
        self._enter_chat(window)
        window._reconnect_busy_waits = 5

        window._on_connected({"room": "general", "host": "1.2.3.4", "port": 5555})

        self.assertEqual(window._reconnect_busy_waits, 0)


class SameRoomClickTests(_QtTestCase):
    """Oda listesine tiklama: icinde oldugun odaya tiklamak sohbeti silmemeli,
    tiklanan oda adi da bozulmamali."""

    def _page(self):
        from apps.proxychat.ui import ChatPage, ConnectionController

        page = ChatPage(ConnectionController())
        self.addCleanup(page.deleteLater)
        self.gonderilen = []
        page.controller.switch_room = lambda room: self.gonderilen.append(room)
        return page

    def test_clicking_the_current_room_sends_no_rejoin(self):
        page = self._page()
        page.current_room = "general"

        page.switch_room("general")

        self.assertEqual(self.gonderilen, [], "gereksiz yeniden katilma yollandi")

    def test_clicking_the_current_room_keeps_the_messages(self):
        page = self._page()
        page.current_room = "general"
        page._append_message("mehmet", "onemli bir mesaj")

        page.switch_room("general")

        self.assertIn("onemli bir mesaj", page.message_view.toPlainText())

    def test_switching_to_a_different_room_still_works(self):
        page = self._page()
        page.current_room = "general"

        page.switch_room("oyun")

        self.assertEqual(self.gonderilen, ["oyun"])
        self.assertEqual(page.current_room, "oyun")
        self.assertIsNone(page._known_users, "yeni odada uye listesi sifirlanmadi")

    def test_clicking_the_current_room_still_highlights_it(self):
        page = self._page()
        page.switch_room("oyun")
        page.room_list.setCurrentItem(None)

        page.switch_room("oyun")

        self.assertIs(page.room_list.currentItem(), page._room_items["oyun"])

    def test_room_whose_name_starts_with_hash_is_not_mangled(self):
        # Oda adi eskiden ogenin metninden lstrip("#") ile ayiklaniyordu;
        # "##dev" odasina tiklayan kullanici "dev" odasina gidiyordu.
        page = self._page()
        page._ensure_room_item("##dev")

        page._switch_room_from_item(page._room_items["##dev"])

        self.assertEqual(self.gonderilen, ["##dev"])
        self.assertEqual(page.current_room, "##dev")


class RoomMemoryTests(_QtTestCase):
    """Gecmis varsayilan kapaliyken (1.7.0) odaya geri donunce ekran bos
    kaliyordu: general'e yazip random'a gecen ve geri donen kullanici tum
    mesajlari silinmis goruyordu. Gorulen mesajlar artik bellekte tutuluyor."""

    def _page(self):
        from apps.proxychat.ui import ChatPage, ConnectionController

        page = ChatPage(ConnectionController())
        self.addCleanup(page.deleteLater)
        page.controller.switch_room = lambda room: None
        self.dikkat = []
        page.attention_requested.connect(lambda *args: self.dikkat.append(args))
        return page

    @staticmethod
    def _joined(page, room, user="ayse"):
        page.on_packet({"type": "joined", "room": room, "user": user, "snapshot": {"users": [user]}})

    @staticmethod
    def _mesaj(page, room, user, content, ts):
        page.on_packet({"type": "message", "room": room, "user": user, "content": content, "ts": ts})

    def test_messages_come_back_when_returning_to_a_room(self):
        page = self._page()
        self._joined(page, "general")
        self._mesaj(page, "general", "ayse", "TEST", 100.0)
        self._mesaj(page, "general", "mehmet", "selam", 101.0)

        page.switch_room("random")
        self._joined(page, "random")
        self.assertNotIn("TEST", page.message_view.toPlainText())
        page.switch_room("general")
        self._joined(page, "general")

        akis = page.message_view.toPlainText()
        self.assertIn("TEST", akis)
        self.assertIn("selam", akis)
        self.assertEqual(self.dikkat, [("mehmet", "selam")], "geri getirilen mesaj yeniden bildirim yapti")

    def test_gap_notice_is_shown_between_old_messages_and_the_join_line(self):
        page = self._page()
        self._joined(page, "general")
        self._mesaj(page, "general", "mehmet", "selam", 101.0)
        self._joined(page, "random")

        self._joined(page, "general")

        akis = page.message_view.toPlainText()
        self.assertLess(akis.index("selam"), akis.index(t("chat.away_gap")))
        self.assertLess(akis.index(t("chat.away_gap")), akis.index(t("chat.joined_self", user="ayse")))

    def test_first_visit_has_no_gap_notice(self):
        page = self._page()

        self._joined(page, "general")

        self.assertNotIn(t("chat.away_gap"), page.message_view.toPlainText())

    def test_leaving_the_session_forgets_the_messages(self):
        window = self._window()
        page = window.chat_page
        self._joined(page, "general")
        self._mesaj(page, "general", "mehmet", "gizli bir sey", 101.0)

        window._leave_session()
        self._joined(page, "general")

        self.assertNotIn("gizli bir sey", page.message_view.toPlainText())
        self.assertEqual(page._room_logs, {})

    def test_server_history_is_merged_without_duplicates(self):
        page = self._page()
        self._joined(page, "general")
        self._mesaj(page, "general", "mehmet", "ikinci", 102.0)
        self._joined(page, "random")

        self._joined(page, "general")
        page.on_packet({"type": "history", "room": "general", "messages": [
            {"user": "eda", "content": "birinci", "ts": 101.0},
            {"user": "mehmet", "content": "ikinci", "ts": 102.0},
        ]})

        akis = page.message_view.toPlainText()
        self.assertEqual(akis.count("ikinci"), 1, akis)
        self.assertLess(akis.index("birinci"), akis.index("ikinci"))
        self.assertNotIn(t("chat.away_gap"), akis, "gecmis geldigi halde bosluk notu kaldi")

    def test_undecryptable_lines_come_back_too(self):
        page = self._page()
        self._joined(page, "general")
        page.on_packet({"type": "message", "room": "general", "user": "mehmet", "content": "[cozulemedi]",
                        "ts": 101.0, "decrypt_failed": True, "decrypt_reason": "password"})
        self._joined(page, "random")

        self._joined(page, "general")

        self.assertIn(t("chat.undecryptable"), page.message_view.toPlainText())

    def test_memory_per_room_is_bounded(self):
        from apps.proxychat.ui import ROOM_LOG_LIMIT

        page = self._page()
        self._joined(page, "general")
        for i in range(ROOM_LOG_LIMIT + 20):
            self._mesaj(page, "general", "mehmet", f"m{i}", float(i))

        self.assertEqual(len(page._room_logs["general"]), ROOM_LOG_LIMIT)
        self.assertEqual(page._room_logs["general"][0]["content"], "m20")

    def test_real_server_without_history_brings_messages_back(self):
        from core.server import ChatServer
        from tests.test_client_lifecycle import bos_port

        port = bos_port()
        server = ChatServer(host="127.0.0.1", port=port)
        server.start()
        self.addCleanup(server.stop)
        window = ProxyChatWindow(izole_ayarlar(self))
        self.addCleanup(window.controller.disconnect)
        window.controller.connect_async("Join", "127.0.0.1", port, "general", "ayse", "gizli")
        _olaylari_isle(5, lambda: window.stack.currentWidget() is window.chat_page)
        _olaylari_isle(0.5)
        page = window.chat_page

        window.controller.send_message("TEST")
        _olaylari_isle(3, lambda: "TEST" in page.message_view.toPlainText())
        page.switch_room("random")
        _olaylari_isle(3, lambda: page.current_room == "random" and "TEST" not in page.message_view.toPlainText())
        page.switch_room("general")
        _olaylari_isle(3, lambda: "TEST" in page.message_view.toPlainText())

        self.assertIn("TEST", page.message_view.toPlainText())



class RoomMoveRealServerTests(_QtTestCase):
    def test_someone_hopping_rooms_takes_one_line(self):
        """Smoke testindeki ekran: 7 git-gel icin 14 satir yaziliyordu."""
        from core.client import ChatClient
        from core.server import ChatServer
        from tests.test_client_lifecycle import bos_port

        port = bos_port()
        server = ChatServer(host="127.0.0.1", port=port)
        server.start()
        self.addCleanup(server.stop)
        window = ProxyChatWindow(izole_ayarlar(self))
        self.addCleanup(window.controller.disconnect)
        window.controller.connect_async("Join", "127.0.0.1", port, "general", "ayse", "")
        _olaylari_isle(5, lambda: window.stack.currentWidget() is window.chat_page)
        page = window.chat_page
        mehmet = ChatClient()
        self.addCleanup(mehmet.disconnect)
        mehmet.connect("127.0.0.1", port, "general", "mehmet")
        _olaylari_isle(3, lambda: page.user_list.count() == 2)

        for _ in range(7):
            mehmet.join_room("random")
            _olaylari_isle(3, lambda: page.user_list.count() == 1)
            mehmet.join_room("general")
            _olaylari_isle(3, lambda: page.user_list.count() == 2)
        _olaylari_isle(0.3)

        satirlar = [s for s in page.message_view.toPlainText().splitlines() if "mehmet" in s]
        self.assertEqual(satirlar, [
            t("chat.user_joined", user="mehmet"),
            t("chat.user_moved_back_many", user="mehmet", count=7),
        ])


if __name__ == "__main__":
    unittest.main()
