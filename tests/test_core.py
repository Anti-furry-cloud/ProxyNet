import unittest
import threading
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from core.protocol import decode_packet, encode_packet
from core.server_state import AnonymousLogger, RoomRegistry
from core.hub import MessageHub
from core.server import ChatServer
from core.client import ChatClient
from apps.proxychat.ui import APP_VERSION, build_splash_pixmap, resource_path


class ProxyChatProtocolTests(unittest.TestCase):
    def test_encode_decode_round_trip_preserves_packet_fields(self):
        packet = {
            "type": "message",
            "room": "general",
            "user": "ayse",
            "content": "Merhaba!",
        }

        raw = encode_packet(packet)
        decoded = decode_packet(raw)

        self.assertEqual(decoded, packet)


class ProxyChatServerStateTests(unittest.TestCase):
    def test_room_registry_tracks_members_and_broadcast_targets(self):
        registry = RoomRegistry()

        registry.join("general", "client-a", "ayse")
        registry.join("general", "client-b", "mehmet")
        registry.join("general", "client-c", "eda")

        self.assertEqual(registry.member_count("general"), 3)
        self.assertEqual(registry.usernames("general"), ["ayse", "mehmet", "eda"])
        self.assertEqual(registry.broadcast_targets("general", exclude_client_id="client-b"), ["client-a", "client-c"])

    def test_room_registry_removes_empty_rooms(self):
        registry = RoomRegistry()

        registry.join("general", "client-a", "ayse")
        registry.leave("general", "client-a")

        self.assertEqual(registry.member_count("general"), 0)
        self.assertEqual(registry.rooms(), [])

    def test_anonymous_logger_masks_user_identity(self):
        logger = AnonymousLogger()

        entry = logger.format_event(
            event="message_received",
            room="general",
            sender="ayse",
            details={"content": "hello", "client_id": "client-a", "ip": "26.0.0.1"},
        )

        self.assertIn("message_received", entry)
        self.assertIn("general", entry)
        # Icerik de uzunlugu da yazilmaz (THREAT_MODEL.md 5.3): logger'a
        # yanlislikla icerik verilse bile.
        self.assertNotIn("hello", entry)
        self.assertNotIn("content_length", entry)
        self.assertNotIn("5", entry)
        self.assertNotIn("ayse", entry)
        self.assertNotIn("client-a", entry)
        self.assertNotIn("26.0.0.1", entry)


class ProxyChatHubTests(unittest.TestCase):
    def test_broadcast_message_reaches_everyone_in_the_room(self):
        hub = MessageHub()

        sender = hub.attach_client("client-a")
        receiver_1 = hub.attach_client("client-b")
        receiver_2 = hub.attach_client("client-c")

        hub.join_room("general", "client-a", "ayse")
        hub.join_room("general", "client-b", "mehmet")
        hub.join_room("general", "client-c", "eda")

        hub.broadcast_message("general", "client-a", "Merhaba!")

        self.assertEqual(len(sender.sent_packets), 1)
        self.assertEqual(len(receiver_1.sent_packets), 1)
        self.assertEqual(len(receiver_2.sent_packets), 1)
        self.assertEqual(sender.sent_packets[0]["type"], "message")
        self.assertEqual(sender.sent_packets[0]["content"], "Merhaba!")
        self.assertEqual(sender.sent_packets[0]["room"], "general")
        self.assertEqual(sender.sent_packets[0]["user"], "ayse")
        self.assertIn("ts", sender.sent_packets[0])
        self.assertEqual(receiver_1.sent_packets[0]["type"], "message")
        self.assertEqual(receiver_1.sent_packets[0]["content"], "Merhaba!")
        self.assertEqual(receiver_1.sent_packets[0]["room"], "general")
        self.assertEqual(receiver_1.sent_packets[0]["user"], "ayse")
        self.assertIn("ts", receiver_1.sent_packets[0])

    def test_room_snapshot_reflects_current_users(self):
        hub = MessageHub()

        hub.attach_client("client-a")
        hub.attach_client("client-b")
        hub.join_room("general", "client-a", "ayse")
        hub.join_room("general", "client-b", "mehmet")

        snapshot = hub.room_snapshot("general")

        self.assertEqual(snapshot["room"], "general")
        self.assertEqual(snapshot["users"], ["ayse", "mehmet"])
        self.assertEqual(snapshot["count"], 2)


class ProxyChatIntegrationTests(unittest.TestCase):
    def test_two_clients_can_exchange_messages_via_server(self):
        port = 8766
        server = ChatServer(port=port)
        server.start()

        received = threading.Event()
        joined = threading.Event()
        packets: list[tuple[str, dict]] = []

        def capture_a(packet):
            packets.append(("a", packet))

        def capture_b(packet):
            packets.append(("b", packet))
            if packet.get("type") == "joined":
                joined.set()
            if packet.get("type") == "message":
                received.set()

        client_a = ChatClient(on_packet=capture_a)
        client_b = ChatClient(on_packet=capture_b)

        try:
            client_a.connect("127.0.0.1", port, "general", "ayse")
            client_b.connect("127.0.0.1", port, "general", "mehmet")
            self.assertTrue(joined.wait(5), "second client did not finish joining")
            client_a.send_message("merhaba")

            self.assertTrue(received.wait(5), "message did not reach the second client")
            self.assertTrue(any(packet.get("type") == "message" and packet.get("content") == "merhaba" for _tag, packet in packets))
        finally:
            client_a.disconnect()
            client_b.disconnect()
            server.stop()

    def test_sender_receives_own_message_without_room_switching(self):
        port = 8767
        server = ChatServer(port=port)
        server.start()

        sender_received = threading.Event()

        def capture_a(packet):
            if packet.get("type") == "message" and packet.get("content") == "merhaba":
                sender_received.set()

        client_a = ChatClient(on_packet=capture_a)
        client_b = ChatClient()

        try:
            client_a.connect("127.0.0.1", port, "general", "ayse")
            client_b.connect("127.0.0.1", port, "general", "mehmet")
            client_a.send_message("merhaba")

            self.assertTrue(sender_received.wait(5), "sender did not receive own message immediately")
        finally:
            client_a.disconnect()
            client_b.disconnect()
            server.stop()

    def test_message_history_includes_timestamps(self):
        port = 8768
        server = ChatServer(port=port, keep_history=True)
        server.start()

        history_seen = threading.Event()
        packets = []

        def capture(packet):
            packets.append(packet)
            if packet.get("type") == "history":
                history_seen.set()

        client = ChatClient(on_packet=capture)

        try:
            client.connect("127.0.0.1", port, "general", "ayse")
            self.assertTrue(history_seen.wait(5), "initial history packet was not received")
            client.send_message("merhaba")
            time.sleep(0.3)
            client.disconnect()

            packets.clear()
            history_seen.clear()
            client = ChatClient(on_packet=capture)
            client.connect("127.0.0.1", port, "general", "ayse")

            self.assertTrue(history_seen.wait(5), "history with message timestamp was not received after reconnect")
            self.assertTrue(any(packet.get("type") == "history" for packet in packets))
            self.assertTrue(
                any(
                    message.get("ts")
                    for packet in packets
                    if packet.get("type") == "history"
                    for message in packet.get("messages", [])
                )
            )
        finally:
            client.disconnect()
            server.stop()


class ProxyChatUiResourceTests(unittest.TestCase):
    def test_splash_image_is_present_in_the_source_tree(self):
        splash_path = Path(resource_path("assets", "proxychat_splash.png"))

        self.assertTrue(splash_path.exists(), f"Missing splash image: {splash_path}")
        self.assertGreater(splash_path.stat().st_size, 0)

    def test_splash_pixmap_can_be_built(self):
        _app = QApplication.instance() or QApplication([])
        pixmap = build_splash_pixmap()

        self.assertFalse(pixmap.isNull())
        self.assertGreater(pixmap.width(), 0)
        self.assertGreater(pixmap.height(), 0)

    # Acilis ekrani eskiden 1024x1024 gorseli oldugu gibi ve "her zaman ustte"
    # gosteriyordu: 1080p ekrani neredeyse tamamen kapliyor, arkaya alinamiyordu.
    def test_splash_is_a_medium_square(self):
        from apps.proxychat.ui import SPLASH_SIDE_PX

        _app = QApplication.instance() or QApplication([])
        pixmap = build_splash_pixmap()

        self.assertEqual((pixmap.width(), pixmap.height()), (SPLASH_SIDE_PX, SPLASH_SIDE_PX))
        self.assertLessEqual(SPLASH_SIDE_PX, 480)

    def test_splash_size_follows_the_requested_side(self):
        _app = QApplication.instance() or QApplication([])

        pixmap = build_splash_pixmap(250)

        self.assertEqual((pixmap.width(), pixmap.height()), (250, 250))

    def test_splash_shrinks_on_small_screens(self):
        from apps.proxychat.ui import SPLASH_SIDE_PX, splash_side_for_screen

        self.assertEqual(splash_side_for_screen(1032), SPLASH_SIDE_PX)
        self.assertEqual(splash_side_for_screen(600), 270)
        self.assertEqual(splash_side_for_screen(None), SPLASH_SIDE_PX)
        self.assertGreaterEqual(splash_side_for_screen(100), 160)

    def test_splash_window_can_be_sent_behind_other_windows(self):
        from PySide6.QtCore import Qt
        from apps.proxychat.ui import build_splash_screen

        app = QApplication.instance() or QApplication([])
        splash = build_splash_screen(app)
        self.addCleanup(splash.deleteLater)

        self.assertFalse(splash.windowFlags() & Qt.WindowType.WindowStaysOnTopHint, "acilis ekrani ustte kilitli")
        self.assertLessEqual(max(splash.pixmap().width(), splash.pixmap().height()), 480)

    def test_app_version_looks_like_a_semver_string(self):
        self.assertRegex(APP_VERSION, r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
