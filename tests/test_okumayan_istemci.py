"""Hic okumayan bir istemci odayi kilitlememeli.

Sunucu her yayini alicilara sirayla, gonderenin is parcacigindan yaziyor.
Okumayan bir istemcinin tamponu dolunca her yazma soket zaman asimini
bekliyordu; baglanti acik kaldigi icin bir sonraki yayin da. Odaya girip hic
okumayan tek bir istemci (parola gerekmiyor) tamponu dolduktan sonra her
mesaji geciktiriyor, bir kismini da hiz sinirina carptirip kaybettiriyordu.

Duzeltme: yazma zaman asimina dusen baglanti sert kapatiliyor (RST). Windows'ta
duz bir shutdown yetmiyordu -- tamponda veri varken nazik kapanisi bekliyor,
sahibinin recv'i hic uyanmiyor ve bir sonraki yazma yine zaman asimini
bekliyordu.
"""

import json
import socket
import threading
import time
import unittest

import core.server as server_modulu
from core.client import ChatClient
from core.server import ChatServer
from core.transport import LineSocket
from tests.test_client_lifecycle import bos_port

YEREL = "127.0.0.1"


def okumayan_cift(zaman_asimi: float):
    """(sunucu tarafi LineSocket, okumayan karsi soket)."""
    dinleyen = socket.socket()
    dinleyen.bind((YEREL, 0))
    dinleyen.listen(1)
    kotu = socket.socket()
    kotu.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
    kotu.connect(dinleyen.getsockname())
    conn, _ = dinleyen.accept()
    dinleyen.close()
    conn.settimeout(zaman_asimi)
    return LineSocket(conn), kotu


class AktarimKatmaniTests(unittest.TestCase):
    def test_zaman_asiminda_baglanti_sert_kapaniyor(self):
        hat, kotu = okumayan_cift(0.3)
        self.addCleanup(kotu.close)
        self.addCleanup(hat.close)
        olaylar = []
        okuyan = threading.Thread(target=lambda: _dongu(hat, olaylar), daemon=True)
        okuyan.start()

        with self.assertRaises(socket.timeout):
            for _ in range(10_000):
                hat.send_packet({"type": "x", "content": "y" * 4000})

        okuyan.join(2)
        self.assertFalse(okuyan.is_alive(), "sahibinin recv'i uyanmadi")
        bas = time.monotonic()
        with self.assertRaises(OSError):
            hat.send_packet({"type": "x"})
        self.assertLess(time.monotonic() - bas, 0.2, "kapali baglantiya yazma yine zaman asimini bekledi")


def _dongu(hat: LineSocket, olaylar: list) -> None:
    """Sunucunun istemci dongusu gibi: zaman asiminda tekrar dener, OSError'da biter."""
    while True:
        try:
            if hat.recv_packet() is None:
                olaylar.append("eof")
                return
        except socket.timeout:
            continue
        except OSError:
            olaylar.append("bitti")
            return


class SunucuTests(unittest.TestCase):
    """Okumayan istemci, tamponu dolunca odadan atiliyor; mesajlar akmaya devam ediyor.

    Tamponun ne kadar veriyle dolacagi makineye bagli: eskiden test sabit 16
    mesaj (~112 KB) gonderip bunun yettigini varsayiyordu. Bizim makinede
    yetiyordu, GitHub'in Windows sunucusunda (daha buyuk yerel baglanti
    tamponlari) yetmedi ve istemci hic atilmadi. Artik istemci atilana kadar
    -- bir ust sinirla -- gonderiliyor. Hiz siniri yalnizca bu testte
    kaldiriliyor; yoksa saniyede iki mesajla buyuk bir tamponu doldurmak
    dakikalar surerdi.
    """

    def test_okumayan_istemci_odadan_atiliyor_mesajlar_akiyor(self):
        eski = server_modulu._POLL_INTERVAL
        server_modulu._POLL_INTERVAL = 0.3
        self.addCleanup(setattr, server_modulu, "_POLL_INTERVAL", eski)
        gercek_sinirlayici = server_modulu.RateLimiter
        server_modulu.RateLimiter = lambda max_events=0, window=10.0: gercek_sinirlayici(10**6, window)
        self.addCleanup(setattr, server_modulu, "RateLimiter", gercek_sinirlayici)
        port = bos_port()
        server = ChatServer(port=port)
        server.start()
        self.addCleanup(server.stop)

        gelen = []
        katildi = threading.Event()

        def topla(p):
            if p.get("type") == "joined":
                katildi.set()
            if p.get("type") == "message":
                gelen.append(p.get("content"))

        alici = ChatClient(on_packet=topla)
        self.addCleanup(alici.disconnect)
        alici.connect(YEREL, port, "general", "alici")
        self.assertTrue(katildi.wait(3))
        gonderen = ChatClient(on_packet=lambda p: None)
        self.addCleanup(gonderen.disconnect)
        gonderen.connect(YEREL, port, "general", "gonderen")

        kotu = socket.socket()
        kotu.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
        self.addCleanup(kotu.close)
        kotu.connect((YEREL, port))
        kotu.sendall((json.dumps({"type": "join", "room": "general", "user": "kotu"}) + "\n").encode())
        bitis = time.monotonic() + 3
        while "kotu" not in server.hub.registry.usernames("general") and time.monotonic() < bitis:
            time.sleep(0.02)

        # Atilana kadar gonder: ust sinir 20 sn ya da ~16 MB.
        n = 0
        bitis = time.monotonic() + 20
        while "kotu" in server.hub.registry.usernames("general") and n < 2000 and time.monotonic() < bitis:
            gonderen.send_message(f"{n:04d}" + "m" * 7000)
            n += 1
            time.sleep(0.01)
        self.assertNotIn("kotu", server.hub.registry.usernames("general"), f"okumayan istemci {n} mesajdan sonra da atilmadi")

        # Atildiktan sonra mesajlar takilmadan akiyor.
        for i in range(5):
            gonderen.send_message(f"son{i}")
            n += 1
        bitis = time.monotonic() + 5
        while len(gelen) < n and time.monotonic() < bitis:
            time.sleep(0.05)
        self.assertGreaterEqual(len(gelen), n - 1, f"mesajlar takildi: {len(gelen)}/{n}")
        self.assertIn("son4", gelen)


if __name__ == "__main__":
    unittest.main()
