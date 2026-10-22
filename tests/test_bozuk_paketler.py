"""Bozuk bicimli paketler ne istemciyi ne arayuzu dusurmemeli.

Zarf duz metin gidiyor ve odaya girmek parola istemiyor: bir paketin turu de
dahil hicbir seyine guvenilmez. Bu dosya iki sey yapiyor:

- Bulanik testin (fuzzing) buldugu dort arayuz durumunu tek tek kilitliyor:
  sozluk yerine metin gelen ``snapshot``, liste yerine sayi gelen ``users`` ve
  ``messages``, hashlenemeyen ``ts``.
- Ayni bulanik testin kucuk, sabit tohumlu bir surumunu calistiriyor: dinleme
  dongusunun adimlari ve arayuzun ``on_packet``'i rastgele paketlerle.
"""

import base64
import random
import secrets
import unittest

from apps.proxychat.ui import ChatPage, ConnectionController
from core.client import ChatClient
from core.room_session import SCHEME, RoomSession
from tests.test_proxychat_ui import _QtTestCase

PAROLA = "p"


def b64(ham: bytes) -> str:
    return base64.urlsafe_b64encode(ham).decode("ascii")


class _Sayfa(_QtTestCase):
    def sayfa(self) -> ChatPage:
        page = ChatPage(ConnectionController())
        self.addCleanup(page.deleteLater)
        page.controller.switch_room = lambda room: None
        return page


class ArayuzBozukAlanTests(_Sayfa):
    def test_metin_olarak_gelen_snapshot(self):
        page = self.sayfa()

        page.on_packet({"type": "joined", "room": "general", "user": "ayse", "snapshot": "bozuk"})

        self.assertEqual(page._snapshot_users, [])

    def test_sayi_olarak_gelen_kullanici_listesi(self):
        page = self.sayfa()

        page.on_packet({"type": "room_snapshot", "room": page.current_room, "users": 0})

        self.assertEqual(page._snapshot_users, [])

    def test_sayi_olarak_gelen_gecmis(self):
        page = self.sayfa()

        page.on_packet({"type": "history", "room": page.current_room, "messages": 10**21})

    def test_sozluk_olarak_gelen_zaman_damgasi(self):
        page = self.sayfa()
        mesaj = {"user": "veli", "content": "selam", "ts": {"a": 1}}

        page.on_packet({"type": "history", "room": page.current_room, "messages": [mesaj, dict(mesaj)]})

        kayit = page._room_logs[page.current_room]
        self.assertEqual(len(kayit), 1, "ayni mesaj iki kez kaydedildi")
        self.assertIsNone(kayit[0]["ts"])


class SesPaketiTests(_QtTestCase):
    """voice_joined ve voice_peers de sunucudan duz metin geliyor."""

    def kontrolcu(self):
        from tests.test_voice_ui import KontrolcuTests

        kontrolcu = KontrolcuTests._kontrolcu(self)
        self.hatalar = []
        kontrolcu.failed.connect(self.hatalar.append)
        kontrolcu.join()
        return kontrolcu

    def katildi(self, **alanlar):
        from core.voice_codec import available_codec

        kontrolcu = self.kontrolcu()
        paket = {"type": "voice_joined", "sender_id": 1, "token": "ab" * 16, "port": 5555,
                 "codec": available_codec()}
        paket.update(alanlar)
        kontrolcu.on_packet(paket)
        return kontrolcu

    def test_bozuk_jeton_katilimi_asili_birakmiyor(self):
        for jeton in ("zz", 5, ["ab"]):
            with self.subTest(jeton=jeton):
                kontrolcu = self.katildi(token=jeton)

                self.assertNotEqual(kontrolcu.state, "joining")
                self.assertNotEqual(kontrolcu.state, "on")
                self.assertIn("voice_not_connected", self.hatalar)

    def test_bozuk_port_baglantinin_portuna_dusuyor(self):
        for port in ("abc", -1, 70000, None):
            with self.subTest(port=port):
                kontrolcu = self.katildi(port=port)

                self.assertEqual(kontrolcu.state, "on")

    def test_bozuk_katilimci_listesi(self):
        kontrolcu = self.katildi()
        adlar = []
        kontrolcu.peers_changed.connect(adlar.append)

        for katilimcilar in (5, "x", [5, "x", None, {"user": "veli", "sender_id": 2, "salt": "aa" * 16}]):
            with self.subTest(katilimcilar=katilimcilar):
                kontrolcu.on_packet({"type": "voice_peers", "peers": katilimcilar})

        self.assertEqual(adlar, [[], [], ["veli"]])


class SunucuTests(unittest.TestCase):
    def test_turu_liste_olan_paket_baglantiyi_bitirmiyor(self):
        """Eskiden kume aramasinda TypeError atip is parcacigini oldururdu."""
        import json
        import socket

        from core.server import ChatServer
        from tests.test_client_lifecycle import bos_port

        port = bos_port()
        server = ChatServer(port=port)
        server.start()
        self.addCleanup(server.stop)
        sock = socket.create_connection(("127.0.0.1", port), timeout=3)
        self.addCleanup(sock.close)
        satirlar = [{"type": "join", "room": "general", "user": "x"}, {"type": [1]}, {"type": {"a": 1}},
                    {"type": "ping"}]
        sock.sendall("".join(json.dumps(s) + "\n" for s in satirlar).encode())

        gelen = b""
        while b'"pong"' not in gelen:
            parca = sock.recv(65536)
            if not parca:
                break
            gelen += parca

        self.assertIn(b'"pong"', gelen, "bozuk paketten sonra baglanti kapandi")


class BulanikTests(_Sayfa):
    TURLER = ["joined", "room_snapshot", "key_offer", "sender_key", "message", "history",
              "room_list", "error", "peers_verified", "voice_peers", 7, None]
    ALANLAR = ["room", "user", "users", "pub", "mac", "key", "to", "content", "enc", "ts",
               "messages", "rooms", "code", "message", "snapshot", "moved", "peers"]

    def deger(self, rnd: random.Random):
        return rnd.choice([
            None, 0, -1, 2**70, 3.5, True, "", "x" * 50, [], {}, ["a", 1, None], {"a": 1},
            b64(secrets.token_bytes(rnd.choice([0, 1, 16, 32, 60]))), "\u0000<img>",
        ])

    def paket(self, rnd: random.Random, veli: RoomSession) -> dict:
        p = {"type": rnd.choice(self.TURLER)}
        for alan in rnd.sample(self.ALANLAR, rnd.randrange(0, 8)):
            p[alan] = self.deger(rnd)
        if p["type"] == "message" and rnd.random() < 0.4:
            p["content"] = veli.encrypt("merhaba")
            p["enc"] = rnd.choice([SCHEME, "baska", None, 5])
        return p

    def test_rastgele_paketler_istisna_kacirmiyor(self):
        rnd = random.Random(1127)
        veli = RoomSession("general", PAROLA)
        for parola in (PAROLA, ""):
            with self.subTest(parolali=bool(parola)):
                client = ChatClient(on_packet=lambda _p: None, room_password=parola)
                client._cipher = client._cipher_for("general")
                page = self.sayfa()
                for _ in range(1500):
                    p = self.paket(rnd, veli)
                    client._absorb_session_state(p)
                    if client._handle_key_exchange(p):
                        continue
                    client._flush_deferred()
                    if client._defer_if_unreadable(p):
                        continue
                    client._deliver(p)
                    page.on_packet(dict(p))


if __name__ == "__main__":
    unittest.main()
