"""Oda listesinin sunucu tarafindan yonetilmesi.

Testcinin bildirdigi iki hata:
  1. Biri yeni oda actiginda karsi taraf bunu hic gormuyordu.
  2. Herkes ciktiktan sonra bile odalar listede kaliyordu.

Ikisinin de sebebi ayniydi: oda listesi tamamen istemcinin kendi arayuzunde
yasiyordu, sunucu bildigi uyelik bilgisini kimseye soylemiyordu.
"""

import threading
import unittest

from PySide6.QtWidgets import QApplication

from apps.proxychat.ui import DEFAULT_ROOMS, ChatPage, ConnectionController
from core.client import ChatClient
from core.server import MAX_HISTORY_ROOMS, ChatServer


class _Baglanti:
    """Bir istemci ve ondan gelen paketleri toplayan yardimci."""

    def __init__(self, port, username, room="general"):
        self.joined = threading.Event()
        self.room_lists: list[list[str]] = []
        self.son_liste = threading.Event()
        self.client = ChatClient(on_packet=self._on_packet)
        self.client.connect("127.0.0.1", port, room, username)
        assert self.joined.wait(5), f"{username} odaya katilamadi"

    def _on_packet(self, packet):
        if packet.get("type") == "joined":
            self.joined.set()
        if packet.get("type") == "room_list":
            self.room_lists.append(list(packet.get("rooms", [])))
            self.son_liste.set()

    def liste_bekle(self, kosul, timeout=5.0):
        """Gelen oda listelerinden biri kosulu saglayana kadar bekler.

        Hic room_list paketi gelmediyse hata verir: aksi halde "oda listede
        yok" testleri, liste hic gonderilmedigi icin bos yere gecerdi.
        """
        import time

        son = time.monotonic() + timeout
        while time.monotonic() < son:
            if self.room_lists and kosul(self.room_lists[-1]):
                return self.room_lists[-1]
            time.sleep(0.05)
        if not self.room_lists:
            raise AssertionError("sunucudan hic room_list paketi gelmedi")
        return self.room_lists[-1]

    def kapat(self):
        self.client.disconnect()


class ServerRoomListTests(unittest.TestCase):
    def test_new_room_is_announced_to_everyone_not_just_the_creator(self):
        port = 8841
        server = ChatServer(port=port)
        server.start()

        a = b = None
        try:
            a = _Baglanti(port, "ayse")
            b = _Baglanti(port, "mehmet")
            b.room_lists.clear()

            # ayse yeni bir oda aciyor
            a.client.join_room("oyun")

            liste = b.liste_bekle(lambda rooms: "oyun" in rooms)
            self.assertIn(
                "oyun",
                liste,
                "yeni acilan oda diger istemciye bildirilmedi",
            )
        finally:
            if a:
                a.kapat()
            if b:
                b.kapat()
            server.stop()

    def test_room_disappears_from_the_list_once_it_is_empty(self):
        port = 8842
        server = ChatServer(port=port)
        server.start()

        a = b = None
        try:
            a = _Baglanti(port, "ayse")
            b = _Baglanti(port, "mehmet")

            a.client.join_room("oyun")
            b.liste_bekle(lambda rooms: "oyun" in rooms)

            # ayse odadan cikiyor -> oda bosaliyor
            a.client.join_room("general")

            liste = b.liste_bekle(lambda rooms: "oyun" not in rooms)
            self.assertNotIn(
                "oyun",
                liste,
                "bosalan oda listeden dusmedi",
            )
        finally:
            if a:
                a.kapat()
            if b:
                b.kapat()
            server.stop()

    def test_room_disappears_when_the_last_member_disconnects(self):
        port = 8843
        server = ChatServer(port=port)
        server.start()

        a = b = None
        try:
            b = _Baglanti(port, "mehmet")
            a = _Baglanti(port, "ayse")
            a.client.join_room("oyun")
            b.liste_bekle(lambda rooms: "oyun" in rooms)

            a.kapat()
            a = None

            liste = b.liste_bekle(lambda rooms: "oyun" not in rooms)
            self.assertNotIn("oyun", liste, "baglanti kesilince oda listede kaldi")
        finally:
            if a:
                a.kapat()
            if b:
                b.kapat()
            server.stop()

    def test_history_survives_an_empty_room(self):
        """Oda bosalinca gecmis SILINMEZ.

        Kisa sureligine cikip geri gelen kullanici sohbeti kaybetmemeli;
        oda listesinden dusmesi gecmisin silinmesini gerektirmiyor.
        """
        port = 8844
        server = ChatServer(port=port, keep_history=True)
        server.start()

        a = None
        try:
            a = _Baglanti(port, "ayse")
            a.client.join_room("oyun")
            a.client.send_message("kalici mesaj")

            import time

            son = time.monotonic() + 5
            while time.monotonic() < son and not server._history.get("oyun"):
                time.sleep(0.05)
            self.assertTrue(server._history.get("oyun"), "mesaj gecmise yazilmadi")

            a.client.join_room("general")
            time.sleep(0.5)

            self.assertIn("oyun", server._history, "bosalan odanin gecmisi silinmis")
        finally:
            if a:
                a.kapat()
            server.stop()

    def test_history_room_count_is_capped(self):
        """Sinirsiz oda gecmisi birikmesin: en eski odalar dusurulur."""
        server = ChatServer(port=8845, keep_history=True)
        for index in range(MAX_HISTORY_ROOMS + 10):
            server._append_history(f"oda-{index}", {"type": "message", "content": "x"})

        self.assertEqual(len(server._history), MAX_HISTORY_ROOMS)
        self.assertNotIn("oda-0", server._history, "en eski oda dusurulmedi")
        self.assertIn(f"oda-{MAX_HISTORY_ROOMS + 9}", server._history)

    def test_writing_to_an_existing_room_keeps_it_fresh(self):
        """Mesaj alan oda listenin sonuna tasinir, erken dusurulmez."""
        server = ChatServer(port=8846, keep_history=True)
        server._append_history("eski-ama-aktif", {"type": "message", "content": "x"})
        for index in range(MAX_HISTORY_ROOMS - 1):
            server._append_history(f"dolgu-{index}", {"type": "message", "content": "x"})

        # aktif odaya yeni mesaj gelirse tazelenmeli
        server._append_history("eski-ama-aktif", {"type": "message", "content": "y"})
        for index in range(5):
            server._append_history(f"yeni-{index}", {"type": "message", "content": "x"})

        self.assertIn("eski-ama-aktif", server._history)


class ChatPageRoomSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _page(self):
        page = ChatPage(ConnectionController())
        self.addCleanup(page.deleteLater)
        return page

    def test_rooms_from_the_server_appear_in_the_list(self):
        page = self._page()

        page.on_packet({"type": "room_list", "rooms": ["general", "oyun"]})

        self.assertIn("oyun", page._room_items)

    def test_rooms_missing_from_the_server_list_are_removed(self):
        page = self._page()
        page.on_packet({"type": "room_list", "rooms": ["general", "oyun"]})
        self.assertIn("oyun", page._room_items)

        page.on_packet({"type": "room_list", "rooms": ["general"]})

        self.assertNotIn("oyun", page._room_items, "bosalan oda arayuzden silinmedi")

    def test_default_rooms_are_always_kept(self):
        page = self._page()

        page.on_packet({"type": "room_list", "rooms": []})

        for room in DEFAULT_ROOMS:
            self.assertIn(room, page._room_items)

    def test_the_room_you_are_in_is_never_removed(self):
        page = self._page()
        page.current_room = "oyun"
        page.on_packet({"type": "room_list", "rooms": ["oyun"]})

        # sunucu listesi bosalsa bile icinde oldugumuz oda kalmali
        page.on_packet({"type": "room_list", "rooms": []})

        self.assertIn("oyun", page._room_items)

    def test_list_widget_and_bookkeeping_stay_in_sync(self):
        page = self._page()
        page.on_packet({"type": "room_list", "rooms": ["general", "oyun", "sohbet"]})
        self.assertIn("sohbet", page._room_items, "oda hic eklenmemis, test bos gecerdi")

        page.on_packet({"type": "room_list", "rooms": ["general"]})

        self.assertEqual(page.room_list.count(), len(page._room_items))
        self.assertEqual(page.room_list.count(), len(set(DEFAULT_ROOMS) | {page.current_room}))


if __name__ == "__main__":
    unittest.main()
