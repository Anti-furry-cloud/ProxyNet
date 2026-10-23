"""ChatClient'in baglanti yasam dongusu.

Odak: basarisiz baglanti denemesinin istemciyi yarim birakmamasi, arka plan
thread'lerinin baska thread'in disconnect()'iyle yarismamasi ve kasitli
kapatmanin hata olarak raporlanmamasi.
"""

import socket
import threading
import time
import unittest

from core.client import ChatClient
from core.server import ChatServer


def bos_port() -> int:
    """TCP'de ve UDP'de bos bir port: sunucu ses icin ayni numarayi UDP'de aciyor.

    Yalnizca TCP'ye bakmak yetmiyordu (2026-10-24): Windows bazi UDP port
    araliklarini kendine ayiriyor (netsh ... excludedportrange), secilen port
    oraya duserse UDP bind "erisim engellendi" veriyor ve ses testleri ara
    sira dusuyordu.
    """
    for _ in range(50):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            u.bind(("127.0.0.1", port))
        except OSError:
            continue
        finally:
            u.close()
        return port
    raise RuntimeError("TCP ve UDP'de bos bir port bulunamadi")


class _SunuculuTest(unittest.TestCase):
    def setUp(self):
        self.port = bos_port()
        self.server = ChatServer(host="127.0.0.1", port=self.port)
        self.server.start()
        self.addCleanup(self.server.stop)


class FailedConnectTests(unittest.TestCase):
    def test_failed_connect_leaves_the_client_untouched(self):
        client = ChatClient(room_password="gizli")
        once = (client.host, client.port, client.room, client.username, client._cipher)

        with self.assertRaises(OSError):
            client.connect("127.0.0.1", bos_port(), "baska-oda", "yeni-ad", timeout=1.0)

        sonra = (client.host, client.port, client.room, client.username, client._cipher)
        self.assertEqual(sonra, once, "basarisiz baglanti istemcinin durumunu degistirdi")
        self.assertFalse(client.connected)


class RetryAfterFailureTests(_SunuculuTest):
    def test_connect_succeeds_after_a_failed_attempt(self):
        # Host modu ayni istemciyle sunucu ayaga kalkana kadar tekrar dener.
        joined = threading.Event()
        rooms: list[str] = []

        def capture(packet):
            if packet.get("type") == "joined":
                rooms.append(packet.get("room"))
                joined.set()

        client = ChatClient(on_packet=capture)
        self.addCleanup(client.disconnect)
        with self.assertRaises(OSError):
            client.connect("127.0.0.1", bos_port(), "yanlis", "ayse", timeout=1.0)

        client.connect("127.0.0.1", self.port, "general", "ayse")

        self.assertTrue(joined.wait(5), "ikinci denemede odaya katilinamadi")
        self.assertEqual(rooms, ["general"])
        self.assertEqual(client.room, "general")


class _PaylasilanAlaniGizleyen(ChatClient):
    """Arka plan thread'lerine _transport'u hep None gosterir.

    Bu, "baska bir thread tam o anda disconnect() etti" durumunu kesinlestirir.
    Eskiden dinleme dongusu bu alani once kontrol edip sonra tekrar okuyordu;
    arada None olursa yakalanmayan AttributeError ile dusuyordu.
    """

    def __init__(self, **kwargs):
        self._gercek_transport = None
        self._sahip = threading.get_ident()
        super().__init__(**kwargs)

    @property
    def _transport(self):
        if threading.get_ident() != self._sahip:
            return None
        return self._gercek_transport

    @_transport.setter
    def _transport(self, deger):
        self._gercek_transport = deger


class BackgroundThreadRaceTests(_SunuculuTest):
    def test_listener_uses_its_own_connection_not_the_shared_field(self):
        yakalanmayan: list[BaseException] = []
        eski_kanca = threading.excepthook
        threading.excepthook = lambda args: yakalanmayan.append(args.exc_value)
        self.addCleanup(setattr, threading, "excepthook", eski_kanca)

        joined = threading.Event()

        def capture(packet):
            if packet.get("type") == "joined":
                joined.set()

        client = _PaylasilanAlaniGizleyen(on_packet=capture)
        self.addCleanup(client.disconnect)
        client.connect("127.0.0.1", self.port, "general", "ayse")

        self.assertTrue(joined.wait(5), "dinleme thread'i paylasilan alana bakip erken cikti")
        self.assertEqual(yakalanmayan, [])


class IntentionalDisconnectTests(_SunuculuTest):
    def _baglan(self):
        durumlar: list[str] = []
        kapandi = threading.Event()

        def on_status(state, _payload):
            durumlar.append(state)
            if state == "disconnected":
                kapandi.set()

        client = ChatClient(on_status=on_status)
        self.addCleanup(client.disconnect)
        client.connect("127.0.0.1", self.port, "general", "ayse")
        return client, durumlar, kapandi

    def test_disconnect_is_not_reported_as_an_error(self):
        client, durumlar, kapandi = self._baglan()
        time.sleep(0.2)  # dinleme thread'i recv'de beklemeye girsin

        client.disconnect()

        self.assertTrue(kapandi.wait(5), "disconnected durumu yayilmadi")
        self.assertNotIn("error", durumlar, "kasitli kapatma hata olarak raporlandi")
        self.assertFalse(client.connected)

    def test_server_going_away_is_still_reported(self):
        client, durumlar, kapandi = self._baglan()
        time.sleep(0.2)

        self.server.stop()

        self.assertTrue(kapandi.wait(5), "sunucu kapaninca disconnected yayilmadi")
        self.assertFalse(client.connected)


if __name__ == "__main__":
    unittest.main()
