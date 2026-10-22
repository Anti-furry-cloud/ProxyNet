"""Bir katilimcinin portu kapaninca ses aktarimi herkes icin durmamali.

Windows, kapali bir UDP portuna yapilan gonderimi (ICMP "port unreachable")
bir SONRAKI recvfrom'da WSAECONNRESET (10054) olarak bildirir. Soket saglam
kalir. Sunucunun ses dongusu bunu "soket kapandi" sanip duruyordu: biri
programi kapattiginda, coktugunde ya da bunu bilerek yaptiginda odadaki
herkesin sesi kesiliyordu. Istemcinin alma dongusunde de ayni satir vardi.

Ag yok: her sey 127.0.0.1 uzerinde, gercek soketlerle.
"""

import socket
import sys
import time
import unittest
from dataclasses import dataclass

from core.server import ChatServer
from core.transport import LineSocket
from core.voice_net import hello_packet
from core.voice_packet import encode_header
from tests.test_client_lifecycle import bos_port

YEREL = "127.0.0.1"


@dataclass
class Katilimci:
    tcp: LineSocket
    sender_id: int
    token: bytes
    udp: socket.socket


class AktariciTests(unittest.TestCase):
    def setUp(self):
        self.port = bos_port()
        self.server = ChatServer(port=self.port)
        self.server.start()
        self.addCleanup(self.server.stop)

    def katil(self, ad: str) -> Katilimci:
        tcp = LineSocket(socket.create_connection((YEREL, self.port), timeout=3))
        self.addCleanup(tcp.close)
        tcp.send_packet({"type": "join", "room": "general", "user": ad})
        tcp.send_packet({"type": "voice_join"})
        bitis = time.monotonic() + 3
        while time.monotonic() < bitis:
            paket = tcp.recv_packet()
            if paket and paket.get("type") == "voice_joined":
                break
        else:
            self.fail(f"{ad}: voice_joined gelmedi")
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.bind((YEREL, 0))
        udp.settimeout(0.2)
        self.addCleanup(udp.close)
        katilimci = Katilimci(tcp, paket["sender_id"], bytes.fromhex(paket["token"]), udp)
        udp.sendto(hello_packet(katilimci.sender_id, katilimci.token), (YEREL, self.port))
        return katilimci

    def bagli(self, katilimcilar) -> bool:
        kayitlar = {p.sender_id: p for p in self.server.voice._by_sender.values()}
        return all(kayitlar.get(k.sender_id) and kayitlar[k.sender_id].address for k in katilimcilar)

    def gonder(self, kimden: Katilimci, sira: int) -> None:
        kimden.udp.sendto(encode_header(kimden.sender_id, sira, sira * 20) + bytes(60), (YEREL, self.port))

    def alinan(self, kim: Katilimci) -> int:
        sayi = 0
        while True:
            try:
                kim.udp.recvfrom(2048)
                sayi += 1
            except (socket.timeout, ConnectionResetError):
                return sayi

    def test_kapanan_port_aktarimi_durdurmuyor(self):
        ayse, veli, cem = (self.katil(ad) for ad in ("ayse", "veli", "cem"))
        bitis = time.monotonic() + 3
        while not self.bagli((ayse, veli, cem)) and time.monotonic() < bitis:
            time.sleep(0.02)
        self.assertTrue(self.bagli((ayse, veli, cem)), "hello'lar baglanmadi")

        ayse.udp.close()  # Ayse'nin portu artik kapali; aktarici ona gondermeye devam eder.
        for sira in range(1, 6):
            self.gonder(veli, sira)
            time.sleep(0.03)
        time.sleep(0.2)
        self.alinan(cem)

        for sira in range(6, 11):
            self.gonder(veli, sira)
            time.sleep(0.03)
        time.sleep(0.2)

        self.assertTrue(self.server._voice_thread.is_alive(), "ses dongusu durdu")
        self.assertGreater(self.alinan(cem), 0, "sifirlamadan sonra Cem'e ses gelmedi")


@unittest.skipUnless(sys.platform == "win32", "WSAECONNRESET yalnizca Windows'ta")
class IstemciDongusuTests(unittest.TestCase):
    def test_sifirlama_sonrasi_alma_suruyor(self):
        """Sunucunun portu bir an kapaliyken giden paket, istemciyi sagir birakmamali."""
        from core.voice_net import VoiceLink

        class Oturum:
            sender_id = 1

            def __init__(self):
                self.gelen = []

            def incoming(self, veri):
                self.gelen.append(veri)

        gecici = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        gecici.bind((YEREL, 0))
        kapali_port = gecici.getsockname()[1]
        gecici.close()

        oturum = Oturum()
        link = VoiceLink(YEREL, kapali_port, oturum, b"\x00" * 16)
        link.start()  # ilk hello kapali porta gider -> sonraki recvfrom 10054
        self.addCleanup(link.stop)
        time.sleep(0.3)

        gonderen = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(gonderen.close)
        gonderen.sendto(b"merhaba", (YEREL, link._socket.getsockname()[1]))
        bitis = time.monotonic() + 2
        while not oturum.gelen and time.monotonic() < bitis:
            time.sleep(0.02)

        self.assertEqual(oturum.gelen, [b"merhaba"], "istemcinin alma dongusu sifirlamada durdu")


if __name__ == "__main__":
    unittest.main()
