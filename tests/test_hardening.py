"""Sunucu saglamlastirmasi testleri.

Her test, elle dogrulanmasi zor olan bir dayaniklilik davranisini kilitler:
durdurma, bellek siniri, bozuk paket, hiz siniri, ad cakismasi.
"""

import json
import socket
import threading
import time
import unittest

from core.protocol import (
    MalformedPacketError,
    PacketTooLargeError,
    decode_packet,
)
from core.client import ChatClient
from core.server import (
    MAX_CONTENT_BYTES,
    RATE_LIMIT_MESSAGES,
    ChatServer,
    RateLimiter,
)
from core.server_state import RoomRegistry
from core.transport import LineSocket


class _FakeSocket:
    """recv() cagrilarini onceden verilmis parcalardan besleyen sahte soket."""

    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.sent = []

    def recv(self, _size):
        if not self._chunks:
            return b""
        return self._chunks.pop(0)

    def sendall(self, data):
        self.sent.append(data)

    def shutdown(self, _how):
        pass

    def close(self):
        pass


class ProtocolErrorTests(unittest.TestCase):
    def test_broken_json_raises_a_protocol_error_not_a_json_error(self):
        with self.assertRaises(MalformedPacketError):
            decode_packet(b"{bozuk")

    def test_non_object_json_is_rejected(self):
        with self.assertRaises(MalformedPacketError):
            decode_packet(b"[1, 2, 3]")

    def test_invalid_utf8_is_rejected(self):
        with self.assertRaises(MalformedPacketError):
            decode_packet(b"\xff\xfe not utf-8")


class LineSocketLimitTests(unittest.TestCase):
    def test_buffer_growth_is_bounded_when_no_newline_ever_arrives(self):
        # Newline gondermeyen bir istemci: eskiden bu bellegi sinirsiz sisirirdi.
        endless = [b"x" * 4096] * 100
        transport = LineSocket(_FakeSocket(endless), max_line_bytes=8192)

        with self.assertRaises(PacketTooLargeError):
            transport.recv_packet()

    def test_oversized_line_is_rejected(self):
        payload = json.dumps({"type": "message", "content": "y" * 20000}).encode() + b"\n"
        transport = LineSocket(_FakeSocket([payload]), max_line_bytes=8192)

        with self.assertRaises(PacketTooLargeError):
            transport.recv_packet()

    def test_many_blank_lines_do_not_exhaust_the_stack(self):
        # Eskiden bos satirlar ozyineleme ile isleniyordu.
        payload = b"\n" * 5000 + json.dumps({"type": "ping"}).encode() + b"\n"
        transport = LineSocket(_FakeSocket([payload]))

        self.assertEqual(transport.recv_packet(), {"type": "ping"})

    def test_normal_packets_still_round_trip(self):
        payload = json.dumps({"type": "message", "content": "merhaba"}).encode() + b"\n"
        transport = LineSocket(_FakeSocket([payload]))

        self.assertEqual(transport.recv_packet()["content"], "merhaba")


class RateLimiterTests(unittest.TestCase):
    def test_allows_up_to_the_limit_then_blocks(self):
        limiter = RateLimiter(max_events=3, window=10.0)

        self.assertTrue(all(limiter.allow(now=100.0) for _ in range(3)))
        self.assertFalse(limiter.allow(now=100.0))

    def test_window_slides_so_the_client_recovers(self):
        limiter = RateLimiter(max_events=3, window=10.0)
        for _ in range(3):
            limiter.allow(now=100.0)

        self.assertFalse(limiter.allow(now=105.0))
        self.assertTrue(limiter.allow(now=111.0))


class RoomRegistryExclusionTests(unittest.TestCase):
    def test_usernames_can_exclude_one_client(self):
        registry = RoomRegistry()
        registry.join("general", "client-a", "ayse")
        registry.join("general", "client-b", "mehmet")

        self.assertEqual(registry.usernames("general", exclude_client_id="client-a"), ["mehmet"])
        self.assertEqual(registry.usernames("general"), ["ayse", "mehmet"])


class ServerShutdownTests(unittest.TestCase):
    def test_stop_actually_closes_client_connections(self):
        port = 8811
        server = ChatServer(port=port)
        server.start()

        joined = threading.Event()
        disconnected = threading.Event()

        def on_packet(packet):
            if packet.get("type") == "joined":
                joined.set()

        def on_status(state, _payload):
            if state == "disconnected":
                disconnected.set()

        client = ChatClient(on_packet=on_packet, on_status=on_status)
        try:
            client.connect("127.0.0.1", port, "general", "ayse")
            self.assertTrue(joined.wait(5), "istemci odaya katilamadi")

            server.stop()

            self.assertTrue(
                disconnected.wait(5),
                "sunucu durdurulunca istemci baglantisi kapanmadi",
            )
        finally:
            client.disconnect()
            server.stop()

    def test_stop_lets_client_threads_finish(self):
        port = 8812
        server = ChatServer(port=port)
        server.start()

        joined = threading.Event()
        client = ChatClient(on_packet=lambda p: joined.set() if p.get("type") == "joined" else None)
        try:
            client.connect("127.0.0.1", port, "general", "ayse")
            self.assertTrue(joined.wait(5), "istemci odaya katilamadi")

            server.stop()

            alive = [thread for thread in server._client_threads if thread.is_alive()]
            self.assertEqual(alive, [], "istemci thread'leri hala calisiyor")
            self.assertEqual(server._transports, {})
        finally:
            client.disconnect()
            server.stop()

    def test_client_thread_list_does_not_grow_without_bound(self):
        port = 8813
        server = ChatServer(port=port)
        server.start()

        try:
            for index in range(5):
                joined = threading.Event()
                client = ChatClient(
                    on_packet=lambda p: joined.set() if p.get("type") == "joined" else None
                )
                client.connect("127.0.0.1", port, "general", f"kullanici-{index}")
                self.assertTrue(joined.wait(5), "istemci odaya katilamadi")
                client.disconnect()
                time.sleep(0.15)

            # Kapanan baglantilarin thread'leri listede birikmemeli.
            self.assertLess(len(server._client_threads), 5)
        finally:
            server.stop()


class ServerResilienceTests(unittest.TestCase):
    def _raw_connect(self, port):
        sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        sock.settimeout(5)
        return sock

    @staticmethod
    def _recv_until(transport, packet_type, limit=10):
        """Aranan tipteki paket gelene kadar okur.

        Sabit sayida paket okumak kirilgandi: sunucuya yeni bir bilgilendirme
        paketi eklendiginde (ornegin room_list) testler kayiyordu.
        """
        for _ in range(limit):
            packet = transport.recv_packet()
            if packet is None:
                break
            if packet.get("type") == packet_type:
                return packet
        raise AssertionError(f"{packet_type} paketi gelmedi")

    def test_malformed_packet_does_not_kill_the_session(self):
        port = 8814
        server = ChatServer(port=port)
        server.start()

        sock = None
        try:
            sock = self._raw_connect(port)
            transport = LineSocket(sock)
            transport.send_packet({"type": "join", "room": "general", "user": "ayse"})
            self._recv_until(transport, "joined")
            self._recv_until(transport, "room_snapshot")

            sock.sendall(b"{bu json degil\n")
            error_packet = self._recv_until(transport, "error")
            self.assertEqual(error_packet["type"], "error")

            # Oturum ayakta: normal bir mesaj hala calisiyor.
            transport.send_packet({"type": "ping"})
            self.assertEqual(self._recv_until(transport, "pong")["type"], "pong")
        finally:
            if sock is not None:
                sock.close()
            server.stop()

    def test_oversized_message_is_refused_without_dropping_the_session(self):
        port = 8815
        server = ChatServer(port=port, keep_history=True)
        server.start()

        sock = None
        try:
            sock = self._raw_connect(port)
            transport = LineSocket(sock)
            transport.send_packet({"type": "join", "room": "general", "user": "ayse"})
            self._recv_until(transport, "joined")
            self._recv_until(transport, "room_snapshot")

            transport.send_packet({"type": "message", "content": "x" * (MAX_CONTENT_BYTES + 10)})
            error_packet = self._recv_until(transport, "error")

            self.assertEqual(error_packet["type"], "error")
            self.assertIn("too long", error_packet["message"])
            self.assertEqual(server._history.get("general", []), [])
        finally:
            if sock is not None:
                sock.close()
            server.stop()

    def test_rate_limit_drops_flood_but_keeps_the_session(self):
        port = 8816
        server = ChatServer(port=port, keep_history=True)
        server.start()

        sock = None
        try:
            sock = self._raw_connect(port)
            transport = LineSocket(sock)
            transport.send_packet({"type": "join", "room": "general", "user": "ayse"})
            self._recv_until(transport, "joined")
            self._recv_until(transport, "room_snapshot")

            for index in range(RATE_LIMIT_MESSAGES + 10):
                transport.send_packet({"type": "message", "content": f"sel-{index}"})

            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if len(server._history.get("general", [])) >= RATE_LIMIT_MESSAGES:
                    break
                time.sleep(0.05)

            time.sleep(0.5)
            stored = len(server._history.get("general", []))
            self.assertLessEqual(
                stored,
                RATE_LIMIT_MESSAGES,
                f"hiz siniri asildi: {stored} mesaj kaydedildi",
            )
        finally:
            if sock is not None:
                sock.close()
            server.stop()

    def test_join_is_required_before_anything_else(self):
        port = 8817
        server = ChatServer(port=port)
        server.start()

        sock = None
        try:
            sock = self._raw_connect(port)
            transport = LineSocket(sock)
            transport.send_packet({"type": "message", "content": "join atlamaya calisiyorum"})

            packet = self._recv_until(transport, "error")
            self.assertEqual(packet["type"], "error")
        finally:
            if sock is not None:
                sock.close()
            server.stop()


class RoomMoveSnapshotTests(unittest.TestCase):
    """Odadan ayrilan baska odaya mi gecti, baglantiyi mi kesti: kalanlar
    ayirt edebilsin diye eski odaya giden anlik goruntu bunu soyler. Hangi
    odaya gectigi yazilmaz."""

    def _baglan(self, port, user):
        from tests.test_client_lifecycle import bos_port  # noqa: F401

        sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        sock.settimeout(5)
        self.addCleanup(sock.close)
        transport = LineSocket(sock)
        transport.send_packet({"type": "join", "room": "general", "user": user})
        ServerResilienceTests._recv_until(transport, "joined")
        return transport

    def _sunucu(self):
        from tests.test_client_lifecycle import bos_port

        port = bos_port()
        server = ChatServer(host="127.0.0.1", port=port)
        server.start()
        self.addCleanup(server.stop)
        return port

    @staticmethod
    def _son_goruntu(transport, users):
        for _ in range(20):
            packet = ServerResilienceTests._recv_until(transport, "room_snapshot")
            if packet["users"] == users:
                return packet
        raise AssertionError("beklenen anlik goruntu gelmedi")

    def test_switching_room_marks_the_user_as_moved(self):
        port = self._sunucu()
        ayse = self._baglan(port, "ayse")
        mehmet = self._baglan(port, "mehmet")
        self._son_goruntu(ayse, ["ayse", "mehmet"])

        mehmet.send_packet({"type": "join", "room": "random", "user": "mehmet"})
        packet = self._son_goruntu(ayse, ["ayse"])

        self.assertEqual(packet.get("moved"), ["mehmet"])
        self.assertNotIn("random", json.dumps(packet))

    def test_disconnecting_is_not_marked_as_moved(self):
        port = self._sunucu()
        ayse = self._baglan(port, "ayse")
        mehmet = self._baglan(port, "mehmet")
        self._son_goruntu(ayse, ["ayse", "mehmet"])

        mehmet.close()
        packet = self._son_goruntu(ayse, ["ayse"])

        self.assertNotIn("moved", packet)


class UsernameCollisionTests(unittest.TestCase):
    def test_duplicate_username_gets_a_suffix(self):
        port = 8818
        server = ChatServer(port=port)
        server.start()

        first_joined = threading.Event()
        second_joined = threading.Event()
        second_name: list[str] = []

        def capture_b(packet):
            if packet.get("type") == "joined":
                second_name.append(packet["user"])
                second_joined.set()

        client_a = ChatClient(
            on_packet=lambda p: first_joined.set() if p.get("type") == "joined" else None
        )
        client_b = ChatClient(on_packet=capture_b)

        try:
            client_a.connect("127.0.0.1", port, "general", "ayse")
            self.assertTrue(first_joined.wait(5), "ilk istemci odaya katilamadi")
            client_b.connect("127.0.0.1", port, "general", "ayse")
            self.assertTrue(second_joined.wait(5), "ikinci istemci odaya katilamadi")

            self.assertEqual(second_name[0], "ayse-2")
            self.assertEqual(client_b.username, "ayse-2", "istemci yeni adi benimsemedi")
        finally:
            client_a.disconnect()
            client_b.disconnect()
            server.stop()

    def test_messages_carry_the_resolved_username(self):
        port = 8819
        server = ChatServer(port=port)
        server.start()

        seen: list[dict] = []
        first_joined = threading.Event()
        second_joined = threading.Event()
        received = threading.Event()

        def capture_a(packet):
            if packet.get("type") == "joined":
                first_joined.set()
            if packet.get("type") == "message":
                seen.append(packet)
                received.set()

        client_a = ChatClient(on_packet=capture_a)
        client_b = ChatClient(
            on_packet=lambda p: second_joined.set() if p.get("type") == "joined" else None
        )

        try:
            client_a.connect("127.0.0.1", port, "general", "ayse")
            self.assertTrue(first_joined.wait(5), "ilk istemci odaya katilamadi")
            client_b.connect("127.0.0.1", port, "general", "ayse")
            self.assertTrue(second_joined.wait(5), "ikinci istemci odaya katilamadi")

            client_b.send_message("ben ikinci ayse'yim")

            self.assertTrue(received.wait(5), "mesaj ulasmadi")
            self.assertEqual(seen[-1]["user"], "ayse-2")
        finally:
            client_a.disconnect()
            client_b.disconnect()
            server.stop()

    def test_long_and_whitespace_names_are_normalized(self):
        port = 8820
        server = ChatServer(port=port)
        server.start()

        joined = threading.Event()
        names: list[str] = []

        def capture(packet):
            if packet.get("type") == "joined":
                names.append(packet["user"])
                joined.set()

        client = ChatClient(on_packet=capture)
        try:
            client.connect("127.0.0.1", port, "general", "  ayse\nmehmet  " + "u" * 200)
            self.assertTrue(joined.wait(5), "istemci odaya katilamadi")

            self.assertNotIn("\n", names[0])
            self.assertLessEqual(len(names[0]), 64)
        finally:
            client.disconnect()
            server.stop()


if __name__ == "__main__":
    unittest.main()
