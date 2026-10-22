"""Anahtar takasi paketleri istemciyi dusurmemeli.

Odaya girmek parola istemiyor (THREAT_MODEL 5.5); yani anahtar paketlerini
parolayi bilmeyen biri de gonderebilir. 1.12.6'ya kadar teklifinden once gelen
sarili bir anahtar, dinleme dongusunden kacan bir istisna atiyordu
(UnknownSenderKey yakalanmiyordu) ve alicinin baglantisi kapaniyordu: kurbanin
acik anahtarina adresli tek bir uydurma paket yetiyordu.

Ayni ailede: dusuk dereceli bir X25519 noktasi ValueError atiyordu, ve
yabancilardan gelen paketlerin tutuldugu iki liste sinirsiz buyuyordu.
"""

import base64
import secrets
import threading
import time
import unittest

import core.client as client_modulu
from core.client import ChatClient
from core.key_agreement import EphemeralKey, OfferError, offer_mac
from core.room_session import RoomSession
from core.server import ChatServer
from tests.test_client_lifecycle import bos_port

PAROLA = "dogru-at-pil-zimba"
ODA = "general"


def b64(ham: bytes) -> str:
    return base64.urlsafe_b64encode(ham).decode("ascii")


def uydurma_acik_anahtar() -> bytes:
    return EphemeralKey().public_key


class _Istemci(unittest.TestCase):
    def setUp(self):
        self.client = ChatClient(room_password=PAROLA)
        self.client._cipher = RoomSession(ODA, PAROLA)
        self.oturum = self.client._cipher

    def anahtar_paketi(self, gonderen: bytes, sarili: bytes) -> dict:
        return {
            "type": "sender_key",
            "room": ODA,
            "user": "veli",
            "pub": b64(gonderen),
            "key": b64(sarili),
            "to": b64(self.oturum.public_key),
        }


class TekliftenOnceGelenAnahtarTests(_Istemci):
    def test_uydurma_anahtar_istisna_atmiyor(self):
        paket = self.anahtar_paketi(uydurma_acik_anahtar(), secrets.token_bytes(60))

        self.client._handle_key_exchange(paket)  # patlamamali

        self.assertEqual(len(self.client._pending_keys), 1)

    def test_teklif_gelince_bekleyen_anahtar_kullaniliyor(self):
        """Kodun bastan beri ele almak istedigi sira; hic calismamisti."""
        veli = RoomSession(ODA, PAROLA)
        sarili = veli.accept_offer(*self.oturum.offer())
        veli_acik, veli_etiket = veli.offer()

        self.client._handle_key_exchange(self.anahtar_paketi(veli_acik, sarili))
        self.client._handle_key_exchange(
            {"type": "key_offer", "room": ODA, "user": "veli", "pub": b64(veli_acik), "mac": b64(veli_etiket)}
        )

        self.assertIn(veli_acik, self.oturum.keyed_peers())
        self.assertEqual(self.client.verified_users(), {"veli"})
        self.assertEqual(self.client._pending_keys, {})

    def test_yabanci_listeleri_sinirli(self):
        sinir = client_modulu.MAX_TRACKED_STRANGERS
        for _ in range(sinir + 40):
            self.client._handle_key_exchange(self.anahtar_paketi(uydurma_acik_anahtar(), secrets.token_bytes(60)))
            self.client._handle_key_exchange(
                {
                    "type": "key_offer",
                    "room": ODA,
                    "user": "mallory",
                    "pub": b64(uydurma_acik_anahtar()),
                    "mac": b64(secrets.token_bytes(32)),
                }
            )

        self.assertEqual(len(self.client._pending_keys), sinir)
        self.assertEqual(len(self.client._mismatched), sinir)

    def test_sinirda_en_eski_bekleyen_anahtar_gidiyor(self):
        sinir = client_modulu.MAX_TRACKED_STRANGERS
        ilk = uydurma_acik_anahtar()
        self.client._handle_key_exchange(self.anahtar_paketi(ilk, secrets.token_bytes(60)))
        for _ in range(sinir):
            self.client._handle_key_exchange(self.anahtar_paketi(uydurma_acik_anahtar(), secrets.token_bytes(60)))

        self.assertNotIn(ilk, self.client._pending_keys)


class DusukDereceliNoktaTests(_Istemci):
    def test_eslesme_anahtari_offer_error_atiyor(self):
        for ad, nokta in (("sifir", bytes(32)), ("bir", b"\x01" + bytes(31))):
            with self.subTest(nokta=ad):
                with self.assertRaises(OfferError):
                    EphemeralKey().pair_key(nokta)

    def test_imzasi_gecerli_kotu_teklif_istemciyi_dusurmuyor(self):
        """Parolayi bilen biri gecerli imzayla dusuk dereceli nokta yollarsa."""
        nokta = bytes(32)
        etiket = offer_mac(nokta, self.oturum._master, ODA)

        self.client._handle_key_exchange(
            {"type": "key_offer", "room": ODA, "user": "mallory", "pub": b64(nokta), "mac": b64(etiket)}
        )

        self.assertEqual(self.oturum.peer_count, 0)


class GercekBaglantiTests(unittest.TestCase):
    """Parolasiz bir saldirgan, sunucu uzerinden kurbana uydurma paket yolluyor."""

    def setUp(self):
        self.port = bos_port()
        self.server = ChatServer(port=self.port)
        self.server.start()
        self.addCleanup(self.server.stop)

    def baglan(self, ad: str, parola: str = ""):
        katildi = threading.Event()
        durumlar: list[str] = []

        def paket(p: dict) -> None:
            if p.get("type") == "joined":
                katildi.set()

        client = ChatClient(on_packet=paket, on_status=lambda s, _d: durumlar.append(s), room_password=parola)
        self.addCleanup(client.disconnect)
        client.connect("127.0.0.1", self.port, ODA, ad)
        self.assertTrue(katildi.wait(5), f"{ad} katilamadi")
        return client, durumlar

    def test_kurbanin_baglantisi_kopmuyor(self):
        kurban, durumlar = self.baglan("ayse", PAROLA)
        saldirgan, _ = self.baglan("mallory")
        hedef = b64(kurban._cipher.public_key)

        for _ in range(3):
            saldirgan.send_packet(
                {
                    "type": "sender_key",
                    "room": ODA,
                    "pub": b64(uydurma_acik_anahtar()),
                    "key": b64(secrets.token_bytes(60)),
                    "to": hedef,
                }
            )
        bitis = time.monotonic() + 3
        while time.monotonic() < bitis and len(kurban._pending_keys) < 3:
            time.sleep(0.02)

        self.assertEqual(len(kurban._pending_keys), 3, "paketler kurbana ulasmadi")
        self.assertTrue(kurban.connected)
        self.assertNotIn("disconnected", durumlar)


if __name__ == "__main__":
    unittest.main()
