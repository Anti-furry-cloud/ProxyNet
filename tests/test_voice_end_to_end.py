"""Sesli sohbetin tam yolu: iki istemci, gercek sunucu, gercek soketler.

Ses donanimi yok: mikrofon cercevesi elle veriliyor, cikan cerceve elle
okunuyor. Aradaki her sey gercek — sinyallesme, sifreleme, UDP, Host'ta
aktarma, jitter tamponu.
"""

import socket
import time
import unittest

from core.server import ChatServer
from core.transport import LineSocket
from core.voice_codec import CODEC_MULAW, FRAME_PCM_BYTES, available_codec, silence
from core.voice_jitter import DEFAULT_TARGET_MS
from core.voice_net import VoiceLink, hello_packet
from core.voice_packet import FRAME_MS
from core.voice_session import VoiceSession
from tests.test_client_lifecycle import bos_port

YEREL = "127.0.0.1"
ODA = "general"
PAROLA = "oda-parolasi"


def konusma(deger: int = 1500) -> bytes:
    return deger.to_bytes(2, "little", signed=True) * (FRAME_PCM_BYTES // 2)


def anahtar(kimlik: int) -> bytes:
    """Testler icin kararli bir gonderen anahtari.

    Uretimde bu anahtar oda oturumundan geliyor ve rastgele
    (`core/room_session.py`). Burada kimlikten uretiliyor ki testler okunur
    kalsin: 2 numarali gonderenin anahtari her zaman ayni.
    """
    return bytes([kimlik]) * 32


class SesliIstemci:
    """Testler icin ince bir istemci: sinyallesme + ses, arayuz yok."""

    def __init__(self, port: int, kullanici: str, oda: str = ODA, kodek: str = CODEC_MULAW) -> None:
        self.tcp = LineSocket(socket.create_connection((YEREL, port), timeout=3))
        self.tcp.send_packet({"type": "join", "room": oda, "user": kullanici})
        self.paketler: list[dict] = []
        self._bekle("joined")
        self.kodek = kodek
        self.session: VoiceSession | None = None
        self.link: VoiceLink | None = None
        self.port = port

    def _bekle(self, tip: str, sure: float = 3.0) -> dict:
        bitis = time.monotonic() + sure
        while time.monotonic() < bitis:
            paket = self.tcp.recv_packet()
            if paket is None:
                continue
            self.paketler.append(paket)
            if paket.get("type") == tip:
                return paket
        raise AssertionError(f"{tip} gelmedi: {[p.get('type') for p in self.paketler]}")

    def sese_katil(self) -> None:
        """Iki adim: once kimlik ve jeton, sonra tuz.

        Tuz kimlikten sonra uretilebiliyor, cunku cozme anahtari ikisinden
        birden turuyor.
        """
        self.tcp.send_packet({"type": "voice_join"})
        cevap = self._bekle("voice_joined")
        self.sender_id = cevap["sender_id"]
        self.token = cevap["token"]
        self.session = VoiceSession(
            ODA, PAROLA, self.sender_id, self.kodek, own_sender_key=anahtar(self.sender_id)
        )
        self.tcp.send_packet({"type": "voice_salt", "salt": self.session.session_salt.hex()})
        self.link = VoiceLink(YEREL, cevap["port"], self.session, bytes.fromhex(self.token))
        self.link.start()

    def katilimcilari_isle(self, bekle: int = 1, sure: float = 3.0) -> list[int]:
        """voice_peers paketlerini isler; istenen sayida karsi taraf gelene kadar.

        Katilim iki adimli oldugu icin ilk yayin bos gelebiliyor: kimlik
        verildiginde tuz henuz bilinmiyor.
        """
        bitis = time.monotonic() + sure
        while time.monotonic() < bitis:
            paket = self._bekle("voice_peers", max(0.2, bitis - time.monotonic()))
            for katilimci in paket["peers"]:
                if katilimci["sender_id"] != self.sender_id:
                    self.session.add_peer(
                        katilimci["sender_id"],
                        bytes.fromhex(katilimci["salt"]),
                        anahtar(katilimci["sender_id"]),
                    )
            if len(self.session.peers()) >= bekle:
                return self.session.peers()
        raise AssertionError(f"{bekle} karsi taraf gelmedi: {self.session.peers()}")

    def konus(self, adet: int = DEFAULT_TARGET_MS // FRAME_MS, deger: int = 1500) -> None:
        for _ in range(adet):
            self.link.send_frame(konusma(deger))

    def kapat(self) -> None:
        if self.link is not None:
            self.link.stop()
        if self.session is not None:
            self.session.close()
        self.tcp.close()


class UctanUcaTests(unittest.TestCase):
    def setUp(self):
        self.port = bos_port()
        self.server = ChatServer(host=YEREL, port=self.port)
        self.server.start()
        self.addCleanup(self.server.stop)

    def istemci(self, ad: str, oda: str = ODA) -> SesliIstemci:
        c = SesliIstemci(self.port, ad, oda)
        self.addCleanup(c.kapat)
        return c

    def _ikili(self):
        ayse = self.istemci("ayse")
        mehmet = self.istemci("mehmet")
        ayse.sese_katil()
        mehmet.sese_katil()
        ayse.katilimcilari_isle()
        mehmet.katilimcilari_isle()
        time.sleep(0.3)  # merhabalarin Host'ta islenmesi
        return ayse, mehmet

    def test_ses_karsi_tarafa_ulasip_calinabiliyor(self):
        ayse, mehmet = self._ikili()

        ayse.konus()
        time.sleep(0.5)

        self.assertGreater(mehmet.session.received, 0, "hic ses paketi gelmedi")
        cikan = mehmet.session.play()
        self.assertEqual(len(cikan), FRAME_PCM_BYTES)
        self.assertNotEqual(cikan, silence(), "gelen ses calinmadi")

    def test_ses_sifreli_gidiyor(self):
        """Aradaki paketler duz PCM tasimamali."""
        ayse, _mehmet = self._ikili()
        ham = konusma()

        datagram = ayse.session.outgoing(ham)

        self.assertNotIn(ham[:32], datagram)

    def test_parolayi_bilmeyen_cozemiyor(self):
        ayse, mehmet = self._ikili()
        yabanci = VoiceSession(ODA, "yanlis-parola", 99, own_sender_key=anahtar(99))
        self.addCleanup(yabanci.close)
        # Yanlis anahtarla deniyor.
        yabanci.add_peer(ayse.sender_id, ayse.session.session_salt, anahtar(99))

        yabanci.incoming(ayse.session.outgoing(konusma()))

        self.assertEqual((yabanci.received, yabanci.undecryptable), (0, 1))
        self.assertEqual(mehmet.session.undecryptable, 0)

    def test_gonderen_kendi_sesini_geri_almiyor(self):
        ayse, _mehmet = self._ikili()

        ayse.konus()
        time.sleep(0.4)

        self.assertEqual(ayse.session.received, 0)

    def test_baska_odadaki_duymuyor(self):
        ayse, mehmet = self._ikili()
        mehmet.tcp.send_packet({"type": "join", "room": "random", "user": "mehmet"})
        time.sleep(0.4)

        ayse.konus()
        time.sleep(0.4)

        self.assertEqual(mehmet.session.received, 0)

    def test_merhabasiz_ses_iletilmiyor(self):
        """Adres baglanmadan gonderilen ses Host'ta duruyor."""
        ayse = self.istemci("ayse")
        mehmet = self.istemci("mehmet")
        ayse.sese_katil()
        mehmet.sese_katil()
        ayse.katilimcilari_isle()
        mehmet.katilimcilari_isle()
        time.sleep(0.3)
        yabanci_soket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(yabanci_soket.close)

        # Ayse'nin kimligiyle, baska bir soketten (dolayisiyla baska porttan).
        yabanci_soket.sendto(ayse.session.outgoing(konusma()), (YEREL, self.port))
        time.sleep(0.4)

        self.assertEqual(mehmet.session.received, 0)

    def test_uc_kisi_ayni_odada(self):
        ayse, mehmet = self._ikili()
        zeynep = self.istemci("zeynep")
        zeynep.sese_katil()
        zeynep.katilimcilari_isle(bekle=2)
        ayse.katilimcilari_isle(bekle=2)
        mehmet.katilimcilari_isle(bekle=2)
        time.sleep(0.3)

        ayse.konus()
        mehmet.konus()
        time.sleep(0.6)

        self.assertGreater(zeynep.session.received, 0)
        self.assertEqual(sorted(zeynep.session.peers()), [ayse.sender_id, mehmet.sender_id])
        self.assertNotEqual(zeynep.session.play(), silence())

    def test_gidis_donus_olculuyor(self):
        ayse, mehmet = self._ikili()

        for _ in range(12):
            ayse.konus(adet=1)
            mehmet.konus(adet=1)
            time.sleep(0.05)
        time.sleep(0.3)

        self.assertGreater(ayse.session.rtt.count + mehmet.session.rtt.count, 0)

    def test_ayrilinca_ses_kesiliyor(self):
        ayse, mehmet = self._ikili()
        ayse.tcp.send_packet({"type": "voice_leave"})
        time.sleep(0.4)
        onceki = mehmet.session.received

        ayse.konus()
        time.sleep(0.4)

        self.assertEqual(mehmet.session.received, onceki)

    def test_merhaba_paketi_alicilara_gitmiyor(self):
        ayse, mehmet = self._ikili()
        onceki = mehmet.session.received

        ayse.link.say_hello()
        time.sleep(0.3)

        self.assertEqual(mehmet.session.received, onceki)

    def test_kullanilabilir_kodek_iki_tarafta_da_ayni(self):
        """Kodek secimi kutuphaneye bagli; testte ikisi de ayni makinede."""
        self.assertIn(available_codec(), ("ulaw", "opus"))

    def test_hello_paketi_18_bayt_baslik_arti_jeton(self):
        paket = hello_packet(7, bytes(range(16)))
        self.assertEqual(len(paket), 18 + 16)


if __name__ == "__main__":
    unittest.main()
