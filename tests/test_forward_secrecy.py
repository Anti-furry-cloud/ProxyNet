"""Ileri gizliligin protokol tarafi: anahtar takasi gercek soketlerle.

Kripto katmani ayri sinaniyor (test_key_agreement, test_room_session). Burada
sunucu ve istemcinin birlikte dogru davranip davranmadigina bakiliyor: takas
paketleri tasiniyor mu, arayuze sizmiyor mu, anahtari gecikmis mesaj ekranda
gorunuyor mu, cikan esin anahtari birakiliyor mu.
"""

import threading
import time
import unittest

from core.client import ChatClient
from core.crypto import UNDECRYPTABLE_PLACEHOLDER
from core.room_session import SCHEME, RoomSession
from core.server import KEY_EXCHANGE_TYPES, ChatServer
from tests.test_client_lifecycle import bos_port

PAROLA = "dogru-at-pil-zimba"


class Toplayici:
    """Istemcinin arayuze verdigi paketleri toplar."""

    def __init__(self) -> None:
        self.paketler: list[dict] = []
        self.katildi = threading.Event()
        self._olaylar: dict[str, threading.Event] = {}

    def __call__(self, paket: dict) -> None:
        self.paketler.append(paket)
        if paket.get("type") == "joined":
            self.katildi.set()
        olay = self._olaylar.get(paket.get("type", ""))
        if olay is not None:
            olay.set()

    def bekle(self, tip: str, sure: float = 5.0) -> bool:
        olay = self._olaylar.setdefault(tip, threading.Event())
        if any(p.get("type") == tip for p in self.paketler):
            return True
        return olay.wait(sure)

    def mesajlar(self) -> list[dict]:
        return [p for p in self.paketler if p.get("type") == "message"]


class SunucuTarafiTests(unittest.TestCase):
    def test_tasinan_paket_tipleri_yazili(self):
        self.assertEqual(KEY_EXCHANGE_TYPES, frozenset({"key_offer", "sender_key"}))

    def test_sunucu_kodu_anahtar_anlasmasini_import_etmiyor(self):
        """Takas uclarda; sunucunun ortak sirri hesaplama yetenegi olmamali."""
        import ast
        from pathlib import Path

        kaynak = Path("core/server.py").read_text(encoding="utf-8")
        adlar = set()
        for dugum in ast.walk(ast.parse(kaynak)):
            if isinstance(dugum, ast.Import):
                adlar.update(a.name for a in dugum.names)
            elif isinstance(dugum, ast.ImportFrom) and dugum.module:
                adlar.add(dugum.module)

        self.assertNotIn("cryptography", {a.split(".")[0] for a in adlar})
        self.assertNotIn("key_agreement", {a.rsplit(".", 1)[-1] for a in adlar})


class TakasTests(unittest.TestCase):
    """Iki istemci, gercek sunucu."""

    def setUp(self):
        self.port = bos_port()
        self.server = ChatServer(port=self.port, keep_history=True)
        self.server.start()
        self.addCleanup(self.server.stop)
        self.istemciler: list[ChatClient] = []

    def istemci(self, ad: str, parola: str = PAROLA, oda: str = "general"):
        toplayici = Toplayici()
        client = ChatClient(on_packet=toplayici, room_password=parola)
        self.istemciler.append(client)
        self.addCleanup(client.disconnect)
        client.connect("127.0.0.1", self.port, oda, ad)
        self.assertTrue(toplayici.katildi.wait(5), f"{ad} odaya katilamadi")
        return client, toplayici

    def anahtar_bekle(self, client: ChatClient, adet: int = 1, sure: float = 5.0) -> None:
        bitis = time.monotonic() + sure
        while time.monotonic() < bitis:
            oturum = client._cipher
            if isinstance(oturum, RoomSession) and oturum.peer_count >= adet:
                return
            time.sleep(0.02)
        raise AssertionError("anahtar takasi tamamlanmadi")

    def test_takas_kendiliginden_tamamlaniyor(self):
        ayse, _ = self.istemci("ayse")
        veli, _ = self.istemci("veli")

        self.anahtar_bekle(ayse)
        self.anahtar_bekle(veli)

    def test_takas_paketleri_arayuze_sizmiyor(self):
        """Kullanicinin gorecegi bir tarafi yok; sohbette gorunmemeli."""
        _, ayse_t = self.istemci("ayse")
        veli, _ = self.istemci("veli")
        self.anahtar_bekle(veli)

        tipler = {p.get("type") for p in ayse_t.paketler}

        self.assertFalse(tipler & KEY_EXCHANGE_TYPES, f"takas paketi arayuze gitti: {tipler}")

    def test_mesaj_karsi_tarafta_okunuyor(self):
        ayse, _ = self.istemci("ayse")
        veli, veli_t = self.istemci("veli")
        self.anahtar_bekle(ayse)

        ayse.send_message("bulusma 21:00")

        self.assertTrue(veli_t.bekle("message"), "mesaj gelmedi")
        self.assertEqual(veli_t.mesajlar()[0]["content"], "bulusma 21:00")
        self.assertEqual(veli_t.mesajlar()[0]["enc"], SCHEME)

    def test_anahtari_gecikmis_mesaj_yer_tutucu_gostermiyor(self):
        """Takas baglantidan sonra oldugu icin mesaj anahtardan once gelebilir.

        Bekletme kuyrugu bunun icin var: mesaj, anahtar gelince gosteriliyor.
        Bekleme olmasaydi "parola farkli" yer tutucusu cikardi -- oysa parola
        dogru, anahtar yoldaydi.
        """
        ayse, _ = self.istemci("ayse")
        veli, veli_t = self.istemci("veli")
        # Takasin bitmesini BEKLEMEDEN gonderiyoruz: yaris kasitli.
        ayse.send_message("hemen yazdim")

        self.assertTrue(veli_t.bekle("message"), "mesaj hic gelmedi")
        icerik = veli_t.mesajlar()[0]["content"]
        self.assertEqual(icerik, "hemen yazdim")
        self.assertNotEqual(icerik, UNDECRYPTABLE_PLACEHOLDER)

    def test_sonradan_gelen_yeni_mesajlari_okuyabiliyor(self):
        ayse, _ = self.istemci("ayse")
        veli, _ = self.istemci("veli")
        self.anahtar_bekle(ayse)

        eda, eda_t = self.istemci("eda")
        self.anahtar_bekle(eda, adet=2)
        ayse.send_message("eda da geldi")

        self.assertTrue(eda_t.bekle("message"), "mesaj gelmedi")
        self.assertEqual(eda_t.mesajlar()[-1]["content"], "eda da geldi")

    def test_cikan_esin_anahtari_birakiliyor(self):
        ayse, _ = self.istemci("ayse")
        veli, _ = self.istemci("veli")
        self.anahtar_bekle(ayse)

        veli.disconnect()

        bitis = time.monotonic() + 5.0
        while time.monotonic() < bitis and ayse._cipher.peer_count:
            time.sleep(0.02)
        self.assertEqual(ayse._cipher.peer_count, 0, "cikan esin anahtari bellekte kaldi")

    def test_farkli_parola_anlasmayi_kurmuyor(self):
        ayse, _ = self.istemci("ayse")
        _, veli_t = self.istemci("veli", parola="baska-parola")

        time.sleep(0.5)

        self.assertEqual(ayse._cipher.peer_count, 0)
        self.assertTrue(ayse._mismatched, "parola uyusmazligi fark edilmedi")

    def test_sifreli_oda_gecmis_tutmuyor(self):
        ayse, _ = self.istemci("ayse")
        veli, veli_t = self.istemci("veli")
        self.anahtar_bekle(ayse)
        ayse.send_message("unutulacak")
        self.assertTrue(veli_t.bekle("message"))

        self.assertEqual(self.server._history.get("general", []), [])


class ParolasizOdaTests(unittest.TestCase):
    """Parolasiz odada hicbir sey degismemeli: takas da yok, gecmis de var."""

    def setUp(self):
        self.port = bos_port()
        self.server = ChatServer(port=self.port, keep_history=True)
        self.server.start()
        self.addCleanup(self.server.stop)

    def test_takas_yapilmiyor_ve_gecmis_calisiyor(self):
        toplayici = Toplayici()
        ayse = ChatClient(on_packet=toplayici)
        self.addCleanup(ayse.disconnect)
        ayse.connect("127.0.0.1", self.port, "general", "ayse")
        self.assertTrue(toplayici.katildi.wait(5))

        ayse.send_message("duz metin")
        self.assertTrue(toplayici.bekle("message"))

        self.assertNotIsInstance(ayse._cipher, RoomSession)
        gecmis = self.server._history.get("general", [])
        self.assertEqual(len(gecmis), 1)
        self.assertEqual(gecmis[0]["content"], "duz metin")


if __name__ == "__main__":
    unittest.main()
