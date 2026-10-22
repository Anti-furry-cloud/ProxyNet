"""Mesajin kimden geldigi: zarftaki ad ile anahtarin sahibi ayni olmali.

Zarftaki adi sunucu yaziyor ve duz metin gidiyor: yolda Ayse'nin mesaji
Veli'ninmis gibi etiketlenebilir. Anahtar da tek basina yetmez: odadaki herkes
herkesin gonderici anahtarini aliyor, yani bir uye baskasinin anahtariyla
yazabilir. Istemci ikisi birlikte tutunca gosteriyor (core/client.py ->
_check_origin).

Ikinci konu tekrar: kaydedilmis bir mesaj yeniden gonderilince AES-GCM onu yine
aciyor. Ayni mesaj ikinci kez gosterilmiyor (RoomSession.first_sight).
"""

import threading
import time
import unittest

import core.room_session as room_session
from core.client import ChatClient
from core.crypto import DECRYPT_REASON_SENDER
from core.key_agreement import SenderKeyError
from core.room_session import SCHEME, RoomSession
from core.server import ChatServer
from tests.test_client_lifecycle import bos_port

PAROLA = "dogru-at-pil-zimba"
ODA = "general"


class Toplayici:
    def __init__(self) -> None:
        self.paketler: list[dict] = []
        self.katildi = threading.Event()
        self._kilit = threading.Lock()

    def __call__(self, paket: dict) -> None:
        with self._kilit:
            self.paketler.append(paket)
        if paket.get("type") == "joined":
            self.katildi.set()

    def mesajlar(self) -> list[dict]:
        with self._kilit:
            return [p for p in self.paketler if p.get("type") == "message"]


def mesaj(kullanici: str, belirtec: str, enc: str | None = SCHEME) -> dict:
    paket = {"type": "message", "room": ODA, "user": kullanici, "content": belirtec, "ts": 1.0}
    if enc is not None:
        paket["enc"] = enc
    return paket


class _SunuculuTestler(unittest.TestCase):
    def setUp(self):
        self.port = bos_port()
        self.server = ChatServer(port=self.port)
        self.server.start()
        self.addCleanup(self.server.stop)

    def istemci(self, ad: str, parola: str = PAROLA):
        toplayici = Toplayici()
        client = ChatClient(on_packet=toplayici, room_password=parola)
        self.addCleanup(client.disconnect)
        client.connect("127.0.0.1", self.port, ODA, ad)
        self.assertTrue(toplayici.katildi.wait(5), f"{ad} odaya katilamadi")
        return client, toplayici

    def bekle(self, kosul, sure: float = 5.0) -> None:
        bitis = time.monotonic() + sure
        while time.monotonic() < bitis:
            if kosul():
                return
            time.sleep(0.02)
        raise AssertionError("beklenen durum olusmadi")


class KokenTests(_SunuculuTestler):
    def setUp(self):
        super().setUp()
        self.ayse, self.ayse_t = self.istemci("ayse")
        self.veli, _ = self.istemci("veli")
        self.cem, _ = self.istemci("cem")
        self.bekle(lambda: self.ayse.verified_users() == {"veli", "cem"})

    def teslim(self, paket: dict) -> list[dict]:
        once = len(self.ayse_t.mesajlar())
        self.ayse._deliver(paket)
        return self.ayse_t.mesajlar()[once:]

    def test_dogru_ad_ve_anahtar_gosteriliyor(self):
        gelen = self.teslim(mesaj("veli", self.veli._cipher.encrypt("merhaba")))

        self.assertEqual(len(gelen), 1)
        self.assertEqual(gelen[0]["content"], "merhaba")
        self.assertNotIn("decrypt_failed", gelen[0])

    def test_kendi_mesajimiz_gosteriliyor(self):
        gelen = self.teslim(mesaj("ayse", self.ayse._cipher.encrypt("benim")))

        self.assertEqual(gelen[0]["content"], "benim")
        self.assertNotIn("decrypt_failed", gelen[0])

    def test_yolda_yeniden_etiketlenen_mesaj_gosterilmiyor(self):
        """Veli'nin sifreli metni, zarfta Cem yazarak."""
        gelen = self.teslim(mesaj("cem", self.veli._cipher.encrypt("gizli")))

        self.assertEqual(len(gelen), 1)
        self.assertTrue(gelen[0]["decrypt_failed"])
        self.assertEqual(gelen[0]["decrypt_reason"], DECRYPT_REASON_SENDER)
        self.assertNotIn("gizli", gelen[0]["content"])

    def test_baskasinin_anahtariyla_yazan_uye_yakalaniyor(self):
        """Cem, elindeki Veli anahtariyla yaziyor; sunucu durust, zarfta Cem."""
        veli_anahtari = self.cem._cipher.sender_key_of(self.veli._cipher.public_key)
        self.assertIsNotNone(veli_anahtari)
        sahte = RoomSession(ODA, PAROLA, sender_key=veli_anahtari).encrypt("veli adina")

        for zarftaki in ("cem", "veli"):
            with self.subTest(zarftaki=zarftaki):
                gelen = self.teslim(mesaj(zarftaki, sahte))
                if zarftaki == "cem":
                    self.assertEqual(gelen[0]["decrypt_reason"], DECRYPT_REASON_SENDER)
                else:
                    # Zarf da anahtar da Veli diyorsa ayirt edecek bir sey yok:
                    # imzasiz gonderici anahtarinin siniri (THREAT_MODEL 5.1).
                    self.assertEqual(gelen[0]["content"], "veli adina")

    def test_bilinmeyen_adla_gelen_mesaj_gosterilmiyor(self):
        gelen = self.teslim(mesaj("mallory", self.veli._cipher.encrypt("x")))

        self.assertEqual(gelen[0]["decrypt_reason"], DECRYPT_REASON_SENDER)

    def test_tekrar_oynatilan_mesaj_bir_kez_gosteriliyor(self):
        belirtec = self.veli._cipher.encrypt("bir kez")

        ilk = self.teslim(mesaj("veli", belirtec))
        ikinci = self.teslim(mesaj("veli", belirtec))

        self.assertEqual([p["content"] for p in ilk], ["bir kez"])
        self.assertEqual(ikinci, [])

    def test_sahte_kopya_asil_mesaji_engellemiyor(self):
        """Once yeniden etiketlenmis kopya, sonra asli: asli gosterilmeli."""
        belirtec = self.veli._cipher.encrypt("asil")

        self.teslim(mesaj("cem", belirtec))
        gelen = self.teslim(mesaj("veli", belirtec))

        self.assertEqual([p["content"] for p in gelen], ["asil"])

    def test_gecmis_paketindeki_tekrar_ve_sahte_ad_ayiklaniyor(self):
        belirtec = self.veli._cipher.encrypt("gecmis")
        gecmis = {
            "type": "history",
            "room": ODA,
            "messages": [mesaj("veli", belirtec), mesaj("veli", belirtec), mesaj("cem", belirtec)],
        }

        acilan = self.ayse._decrypt_incoming(gecmis)["messages"]

        self.assertEqual(len(acilan), 2)
        self.assertEqual(acilan[0]["content"], "gecmis")
        self.assertEqual(acilan[1]["decrypt_reason"], DECRYPT_REASON_SENDER)

    def test_gercek_mesaj_sunucudan_gecip_gosteriliyor(self):
        self.veli.send_message("selam")

        self.bekle(lambda: any(p.get("content") == "selam" for p in self.ayse_t.mesajlar()))
        gelen = [p for p in self.ayse_t.mesajlar() if p.get("content") == "selam"]
        self.assertEqual(gelen[0]["user"], "veli")
        self.assertNotIn("decrypt_failed", gelen[0])


class ParolasizOdaTests(_SunuculuTestler):
    def test_duz_metne_dokunulmuyor(self):
        """Parolasiz odada baglanacak anahtar yok; tekrar da ayiklanmiyor."""
        toplayici = Toplayici()
        ayse = ChatClient(on_packet=toplayici)
        self.addCleanup(ayse.disconnect)
        ayse.connect("127.0.0.1", self.port, ODA, "ayse")
        self.assertTrue(toplayici.katildi.wait(5))

        for _ in range(2):
            ayse._deliver(mesaj("herhangi", "acik metin", enc=None))

        icerikler = [p["content"] for p in toplayici.mesajlar()]
        self.assertEqual(icerikler, ["acik metin", "acik metin"])


class AnahtarSahipligiTests(unittest.TestCase):
    """Sunucusuz: RoomSession'in kimlik ve tekrar defteri."""

    def eslestir(self, alici: RoomSession, gonderen: RoomSession) -> None:
        acik, etiket = gonderen.offer()
        alici.accept_offer(acik, etiket)
        sarili = gonderen.accept_offer(*alici.offer())
        alici.accept_sender_key(acik, sarili)

    def test_baskasinin_anahtarini_kendi_diye_sunan_reddediliyor(self):
        ayse = RoomSession(ODA, PAROLA)
        veli = RoomSession(ODA, PAROLA)
        self.eslestir(ayse, veli)
        mallory = RoomSession(ODA, PAROLA, sender_key=veli.own_sender_key())

        with self.assertRaises(SenderKeyError):
            self.eslestir(ayse, mallory)

        belirtec = veli.encrypt("x")
        self.assertEqual(ayse.key_owner(belirtec), veli.public_key)

    def test_kendi_anahtarimizi_sunan_reddediliyor(self):
        ayse = RoomSession(ODA, PAROLA)
        mallory = RoomSession(ODA, PAROLA, sender_key=ayse.own_sender_key())

        with self.assertRaises(SenderKeyError):
            self.eslestir(ayse, mallory)
        self.assertEqual(ayse.key_owner(ayse.encrypt("x")), ayse.public_key)

    def test_ayrilan_esin_anahtari_sahipsiz_kaliyor(self):
        ayse = RoomSession(ODA, PAROLA)
        veli = RoomSession(ODA, PAROLA)
        self.eslestir(ayse, veli)
        belirtec = veli.encrypt("x")

        ayse.forget_peer(veli.public_key)

        self.assertIsNone(ayse.key_owner(belirtec))

    def test_bozuk_belirtecin_sahibi_yok(self):
        ayse = RoomSession(ODA, PAROLA)

        for bozuk in ("", "!!!", "QUJD"):
            with self.subTest(bozuk=bozuk):
                self.assertIsNone(ayse.key_owner(bozuk))
                self.assertFalse(ayse.first_sight(bozuk))

    def test_tekrar_defteri_sinirli_ve_en_eskiyi_unutuyor(self):
        ayse = RoomSession(ODA, PAROLA)
        eski_sinir = room_session.SEEN_MESSAGES_LIMIT
        room_session.SEEN_MESSAGES_LIMIT = 2
        self.addCleanup(setattr, room_session, "SEEN_MESSAGES_LIMIT", eski_sinir)
        birinci, ikinci, ucuncu = (ayse.encrypt(str(i)) for i in range(3))

        for belirtec in (birinci, ikinci, ucuncu):
            self.assertTrue(ayse.first_sight(belirtec))

        self.assertEqual(len(ayse._seen), 2)
        self.assertFalse(ayse.first_sight(ucuncu))
        self.assertTrue(ayse.first_sight(birinci))


class ArayuzMetniTests(unittest.TestCase):
    def test_gonderen_dogrulanamadi_kendi_metniyle_yaziliyor(self):
        from apps.proxychat.i18n import set_language, t
        from apps.proxychat.ui import _undecryptable_text

        self.addCleanup(set_language, "en")
        for dil in ("tr", "en"):
            with self.subTest(dil=dil):
                set_language(dil)
                metin = _undecryptable_text({"decrypt_reason": DECRYPT_REASON_SENDER})
                self.assertEqual(metin, t("chat.undecryptable_sender"))
                self.assertNotEqual(metin, t("chat.undecryptable"))


if __name__ == "__main__":
    unittest.main()
