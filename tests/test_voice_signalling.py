"""Faz 1b: sunucudaki sinyallesme ve ses aktarmasi, gercek soketlerle.

Ses donanimi yok: paketler elle uretiliyor. Sunucu 127.0.0.1'e baglaniyor,
UDP portu TCP ile ayni numara.
"""

import socket
import time
import unittest

from core.server import ChatServer
from core.transport import LineSocket
from core.voice_packet import TYPE_AUDIO, TYPE_HELLO, encode_header, pack
from tests.test_client_lifecycle import bos_port

YEREL = "127.0.0.1"


def ses(sender_id: int, sira: int = 1, govde: bytes = b"sifreli") -> bytes:
    return pack(encode_header(sender_id, sira, 0, TYPE_AUDIO), govde)


def merhaba(sender_id: int, jeton_hex: str) -> bytes:
    return pack(encode_header(sender_id, 0, 0, TYPE_HELLO), bytes.fromhex(jeton_hex))


class Istemci:
    """Testler icin ince bir istemci: TCP sinyallesme + UDP ses soketi."""

    def __init__(self, port: int, kullanici: str, oda: str = "general") -> None:
        self.port = port
        self.tcp = LineSocket(socket.create_connection((YEREL, port), timeout=3))
        self.tcp.send_packet({"type": "join", "room": oda, "user": kullanici})
        self.paketler = []
        self._bekle("joined")
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.bind((YEREL, 0))
        self.udp.settimeout(2.0)
        self.sender_id: int | None = None
        self.token: str | None = None

    def katilimci_bekle(self, adet: int, sure: float = 3.0) -> list[dict]:
        """Istenen sayida katilimci iceren voice_peers paketini bekler.

        Katilim iki adimli oldugu icin once bos bir liste yayinlaniyor;
        testler dolu olani beklemeli.
        """
        import time as _t

        bitis = _t.monotonic() + sure
        while _t.monotonic() < bitis:
            paket = self._bekle("voice_peers", max(0.2, bitis - _t.monotonic()))
            if len(paket["peers"]) == adet:
                return paket["peers"]
        raise AssertionError(f"{adet} katilimcili voice_peers gelmedi")

    def _bekle(self, tip: str, sure: float = 3.0) -> dict:
        bitis = time.monotonic() + sure
        while time.monotonic() < bitis:
            paket = self.tcp.recv_packet()
            if paket is None:
                continue
            self.paketler.append(paket)
            if paket.get("type") == tip:
                return paket
        raise AssertionError(f"{tip} paketi gelmedi: {[p.get('type') for p in self.paketler]}")

    def sese_katil(self, tuz: str = "ab" * 16) -> dict:
        """Katilim iki adim: kimlik/jeton, sonra tuz (bkz. core/voice_relay.py)."""
        self.tcp.send_packet({"type": "voice_join"})
        cevap = self._bekle("voice_joined")
        self.sender_id, self.token = cevap["sender_id"], cevap["token"]
        if tuz:
            self.tcp.send_packet({"type": "voice_salt", "salt": tuz})
        return cevap

    def merhaba_yolla(self) -> None:
        self.udp.sendto(merhaba(self.sender_id, self.token), (YEREL, self.port))

    def ses_yolla(self, sira: int = 1, govde: bytes = b"sifreli") -> bytes:
        paket = ses(self.sender_id, sira, govde)
        self.udp.sendto(paket, (YEREL, self.port))
        return paket

    def ses_bekle(self) -> bytes | None:
        try:
            return self.udp.recv(4096)
        except socket.timeout:
            return None

    def kapat(self) -> None:
        self.tcp.close()
        self.udp.close()


class SinyallesmeTests(unittest.TestCase):
    def setUp(self):
        self.port = bos_port()
        self.server = ChatServer(host=YEREL, port=self.port)
        self.server.start()
        self.addCleanup(self.server.stop)
        self.istemciler = []

    def istemci(self, ad: str, oda: str = "general") -> Istemci:
        c = Istemci(self.port, ad, oda)
        self.istemciler.append(c)
        self.addCleanup(c.kapat)
        return c

    def test_katilan_kimlik_ve_jeton_aliyor(self):
        ayse = self.istemci("ayse")

        cevap = ayse.sese_katil()

        self.assertEqual(cevap["sender_id"], 1)
        self.assertEqual(len(bytes.fromhex(cevap["token"])), 16)
        self.assertEqual(cevap["port"], self.port)

    def test_kimlikler_farkli_ve_yeniden_kullanilmiyor(self):
        ayse = self.istemci("ayse")
        mehmet = self.istemci("mehmet")

        ilk = ayse.sese_katil()["sender_id"]
        ikinci = mehmet.sese_katil()["sender_id"]
        ayse.tcp.send_packet({"type": "voice_leave"})
        time.sleep(0.2)
        zeynep = self.istemci("zeynep")
        ucuncu = zeynep.sese_katil()["sender_id"]

        self.assertEqual({ilk, ikinci}, {1, 2})
        self.assertNotIn(ucuncu, {ilk, ikinci})

    def test_katilimci_listesi_yayinlaniyor_ve_ip_tasimiyor(self):
        ayse = self.istemci("ayse")
        mehmet = self.istemci("mehmet")
        ayse.sese_katil(tuz="cd" * 16)

        [katilimci] = mehmet.katilimci_bekle(1)
        paket = mehmet.paketler[-1]

        self.assertEqual(paket["room"], "general")
        self.assertEqual(katilimci["user"], "ayse")
        self.assertEqual(katilimci["salt"], "cd" * 16)
        self.assertNotIn("ip", katilimci)
        self.assertNotIn(YEREL, str(paket))

    def test_ayrilinca_listeden_dusuyor(self):
        ayse = self.istemci("ayse")
        mehmet = self.istemci("mehmet")
        ayse.sese_katil()
        mehmet.katilimci_bekle(1)

        ayse.tcp.send_packet({"type": "voice_leave"})

        self.assertEqual(mehmet.katilimci_bekle(0), [])

    def test_baglanti_kopunca_sesten_de_dusuyor(self):
        ayse = self.istemci("ayse")
        mehmet = self.istemci("mehmet")
        ayse.sese_katil()
        mehmet.katilimci_bekle(1)

        ayse.tcp.close()

        self.assertEqual(mehmet.katilimci_bekle(0), [])

    def test_oda_degistirince_ses_de_tasiniyor(self):
        ayse = self.istemci("ayse")
        mehmet = self.istemci("mehmet")
        ayse.sese_katil()
        mehmet.katilimci_bekle(1)

        ayse.tcp.send_packet({"type": "join", "room": "random", "user": "ayse"})

        self.assertEqual(mehmet.katilimci_bekle(0), [])


class AktarmaTests(unittest.TestCase):
    def setUp(self):
        self.port = bos_port()
        self.server = ChatServer(host=YEREL, port=self.port)
        self.server.start()
        self.addCleanup(self.server.stop)

    def _ikili(self):
        ayse = Istemci(self.port, "ayse")
        mehmet = Istemci(self.port, "mehmet")
        self.addCleanup(ayse.kapat)
        self.addCleanup(mehmet.kapat)
        ayse.sese_katil()
        mehmet.sese_katil()
        ayse.merhaba_yolla()
        mehmet.merhaba_yolla()
        time.sleep(0.3)  # merhabalarin islenmesi
        return ayse, mehmet

    def test_ses_karsi_tarafa_aynen_gidiyor(self):
        ayse, mehmet = self._ikili()

        gonderilen = ayse.ses_yolla(govde=b"bu-sifreli-kalmali")

        self.assertEqual(mehmet.ses_bekle(), gonderilen)

    def test_gonderen_kendi_sesini_geri_almiyor(self):
        ayse, _mehmet = self._ikili()

        ayse.ses_yolla()

        self.assertIsNone(ayse.ses_bekle())

    def test_merhabasiz_ses_iletilmiyor(self):
        ayse = Istemci(self.port, "ayse")
        mehmet = Istemci(self.port, "mehmet")
        self.addCleanup(ayse.kapat)
        self.addCleanup(mehmet.kapat)
        ayse.sese_katil()
        mehmet.sese_katil()
        mehmet.merhaba_yolla()
        time.sleep(0.2)

        ayse.ses_yolla()

        self.assertIsNone(mehmet.ses_bekle())

    def test_merhaba_alicilara_iletilmiyor(self):
        """Merhaba Host'ta tuketilir; ses akisina karismaz."""
        ayse, mehmet = self._ikili()

        ayse.merhaba_yolla()

        self.assertIsNone(mehmet.ses_bekle())

    def test_sahte_kimlikle_gelen_paket_iletilmiyor(self):
        ayse, mehmet = self._ikili()
        sahte = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(sahte.close)

        sahte.sendto(ses(ayse.sender_id, 99), (YEREL, self.port))

        self.assertIsNone(mehmet.ses_bekle())

    def test_baska_odadaki_duymuyor(self):
        ayse, mehmet = self._ikili()
        mehmet.tcp.send_packet({"type": "join", "room": "random", "user": "mehmet"})
        time.sleep(0.3)

        ayse.ses_yolla()

        self.assertIsNone(mehmet.ses_bekle())

    def test_sesli_sohbet_metin_sohbetini_bozmuyor(self):
        ayse, mehmet = self._ikili()
        ayse.ses_yolla()

        ayse.tcp.send_packet({"type": "message", "room": "general", "content": "merhaba"})

        paket = mehmet._bekle("message")
        self.assertEqual(paket.get("content"), "merhaba")


if __name__ == "__main__":
    unittest.main()
