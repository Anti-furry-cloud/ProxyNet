"""Uye listesi bir iddia, anahtar takasi bir kanit.

Zarf paketleri duz metin gittigi icin sunucunun bildirdigi uye listesi
sahtelenebilir; sunucunun kendisi de uydurabilir (THREAT_MODEL.md 5.4). Burada
sinanan sey, istemcinin ve arayuzun ikisini ayri tutmasi: listede gorunen ama
paroladan turetilmis imzayi ve anahtar sahipligini gosteremeyen biri
"dogrulanmadi" diye isaretleniyor.
"""

import threading
import time
import unittest

from PySide6.QtWidgets import QApplication

from apps.proxychat.i18n import set_language, t
from apps.proxychat.ui import ChatPage, ConnectionController
from core.client import ChatClient
from core.room_session import RoomSession
from core.server import ChatServer
from tests.test_client_lifecycle import bos_port

PAROLA = "dogru-at-pil-zimba"


class Toplayici:
    def __init__(self) -> None:
        self.paketler: list[dict] = []
        self.katildi = threading.Event()

    def __call__(self, paket: dict) -> None:
        self.paketler.append(paket)
        if paket.get("type") == "joined":
            self.katildi.set()

    def dogrulananlar(self) -> list[list[str]]:
        return [p["users"] for p in self.paketler if p.get("type") == "peers_verified"]


class CekirdekTests(unittest.TestCase):
    def setUp(self):
        self.port = bos_port()
        self.server = ChatServer(port=self.port)
        self.server.start()
        self.addCleanup(self.server.stop)

    def istemci(self, ad: str, parola: str = PAROLA):
        toplayici = Toplayici()
        client = ChatClient(on_packet=toplayici, room_password=parola)
        self.addCleanup(client.disconnect)
        client.connect("127.0.0.1", self.port, "general", ad)
        self.assertTrue(toplayici.katildi.wait(5), f"{ad} odaya katilamadi")
        return client, toplayici

    def bekle(self, kosul, sure: float = 5.0) -> None:
        bitis = time.monotonic() + sure
        while time.monotonic() < bitis:
            if kosul():
                return
            time.sleep(0.02)
        raise AssertionError("beklenen durum olusmadi")

    def test_takas_bitmeden_kimse_dogrulanmis_degil(self):
        ayse, _ = self.istemci("ayse")

        self.assertEqual(ayse.verified_users(), set())

    def test_takas_bitince_es_dogrulaniyor(self):
        ayse, _ = self.istemci("ayse")
        self.istemci("veli")

        self.bekle(lambda: ayse.verified_users() == {"veli"})

    def test_dogrulama_arayuze_paketle_bildiriliyor(self):
        _, ayse_t = self.istemci("ayse")
        self.istemci("veli")

        self.bekle(lambda: ["veli"] in ayse_t.dogrulananlar())

    def test_farkli_parolali_kisi_dogrulanmiyor(self):
        """Parolayi bilmeyen listede gorunur ama kanit uretemez."""
        ayse, _ = self.istemci("ayse")
        self.istemci("veli", parola="baska-parola")

        time.sleep(0.6)

        self.assertEqual(ayse.verified_users(), set())

    def test_parolasiz_oturumda_dogrulama_yok(self):
        toplayici = Toplayici()
        ayse = ChatClient(on_packet=toplayici)
        self.addCleanup(ayse.disconnect)
        ayse.connect("127.0.0.1", self.port, "general", "ayse")
        self.assertTrue(toplayici.katildi.wait(5))

        self.assertEqual(ayse.verified_users(), set())
        self.assertNotIsInstance(ayse._cipher, RoomSession)

    def test_es_cikinca_dogrulanmis_kumeden_dusuyor(self):
        ayse, ayse_t = self.istemci("ayse")
        veli, _ = self.istemci("veli")
        self.bekle(lambda: ayse.verified_users() == {"veli"})

        veli.disconnect()

        self.bekle(lambda: ayse.verified_users() == set())
        self.assertEqual(ayse_t.dogrulananlar()[-1], [])

    def test_anahtar_sahipligi_kanit_sayiliyor(self):
        """Teklifi dogrulanan degil, sarili anahtarini acabildigimiz es.

        Kaydedilmis bir teklif yeniden oynatilabilir; sarili anahtarin
        acilabilmesi ise gizli anahtarin elde tutuldugunu gosteriyor.
        """
        ayse = RoomSession("kule", PAROLA)
        veli = RoomSession("kule", PAROLA)
        veli_acik, veli_etiket = veli.offer()
        ayse_acik, ayse_etiket = ayse.offer()

        ayse.accept_offer(veli_acik, veli_etiket)  # yalnizca teklif dogrulandi

        self.assertEqual(ayse.keyed_peers(), set(), "teklif tek basina kanit sayildi")

        sarili = veli.accept_offer(ayse_acik, ayse_etiket)
        ayse.accept_sender_key(veli_acik, sarili)

        self.assertEqual(ayse.keyed_peers(), {veli_acik})


class SahteKontrolcu:
    """ChatPage'in ihtiyaci olan kadari; ag yok."""

    def __init__(self, encrypted: bool = True) -> None:
        self.encrypted = encrypted
        self.username = "ayse"

    def switch_room(self, room):  # pragma: no cover - cagrilmiyor
        pass


class SayfaKurulumu:
    """Ortak kurulum. Test icermiyor: alt siniflar tekrar kosmasin."""

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "en")

    def sayfa(self, encrypted: bool = True) -> ChatPage:
        sayfa = ChatPage(SahteKontrolcu(encrypted))
        self.addCleanup(sayfa.deleteLater)
        sayfa._own_username = "ayse"
        return sayfa

    def satirlar(self, sayfa: ChatPage) -> list[str]:
        return [sayfa.user_list.item(i).text() for i in range(sayfa.user_list.count())]


class ArayuzTests(SayfaKurulumu, unittest.TestCase):
    def test_dogrulanmayan_listede_adiyla_gorunmuyor(self):
        """Ad yerine sayac satiri; adlar tiklaninca aciliyor."""
        sayfa = self.sayfa()

        sayfa.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse", "veli"]})

        self.assertEqual(self.satirlar(sayfa), ["ayse", t("chat.unverified_one")])

    def test_dogrulama_gelince_ad_listeye_giriyor(self):
        sayfa = self.sayfa()
        sayfa.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse", "veli"]})

        sayfa.on_packet({"type": "peers_verified", "room": "general", "users": ["veli"]})

        self.assertEqual(self.satirlar(sayfa), ["ayse", "veli"])

    def test_kendimiz_her_zaman_dogrulanmis_sayiliyoruz(self):
        sayfa = self.sayfa()

        sayfa.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse"]})

        self.assertEqual(self.satirlar(sayfa), ["ayse"])

    def test_parolasiz_odada_isaret_yok(self):
        sayfa = self.sayfa(encrypted=False)

        sayfa.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse", "veli"]})

        self.assertEqual(self.satirlar(sayfa), ["ayse", "veli"])

    def test_ipuclari_var(self):
        sayfa = self.sayfa()

        sayfa.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse", "veli"]})

        self.assertEqual(sayfa.user_list.item(0).toolTip(), t("chat.user_verified_hint"))
        self.assertEqual(sayfa.user_list.item(1).toolTip(), t("chat.unverified_hint"))

    def test_dogrulama_paketi_sohbete_yazilmiyor(self):
        """Kullanicinin gorecegi bir sistem satiri degil."""
        sayfa = self.sayfa()
        sayfa.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse", "veli"]})
        once = sayfa.message_view.toPlainText()

        sayfa.on_packet({"type": "peers_verified", "room": "general", "users": ["veli"]})

        self.assertEqual(sayfa.message_view.toPlainText(), once)

    def test_es_dusunce_sayaca_geri_donuyor(self):
        sayfa = self.sayfa()
        sayfa.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse", "veli"]})
        sayfa.on_packet({"type": "peers_verified", "room": "general", "users": ["veli"]})

        sayfa.on_packet({"type": "peers_verified", "room": "general", "users": []})

        self.assertEqual(self.satirlar(sayfa), ["ayse", t("chat.unverified_one")])


class SayacEtiketiTests(unittest.TestCase):
    """Sayi-metin eslemesi; Qt gerekmiyor."""

    def test_tek_kisi_tekil(self):
        from apps.proxychat.ui import unverified_label

        self.assertEqual(unverified_label(1), ("chat.unverified_one", {}))

    def test_birden_fazla_cogul(self):
        from apps.proxychat.ui import unverified_label

        self.assertEqual(unverified_label(2), ("chat.unverified_many", {"count": 2}))

    def test_sinirda_hala_sayi(self):
        from apps.proxychat.ui import UNVERIFIED_LIMIT, unverified_label

        anahtar, degerler = unverified_label(UNVERIFIED_LIMIT)

        self.assertEqual(anahtar, "chat.unverified_many")
        self.assertEqual(degerler["count"], UNVERIFIED_LIMIT)

    def test_siniri_asinca_sayi_yazilmiyor(self):
        """Sahte kullanici selinde tam sayi bilgi tasimaz, yalnizca "cok" tasir."""
        from apps.proxychat.ui import UNVERIFIED_LIMIT, unverified_label

        anahtar, degerler = unverified_label(UNVERIFIED_LIMIT + 1)

        self.assertEqual(anahtar, "chat.unverified_over")
        self.assertEqual(degerler, {"limit": UNVERIFIED_LIMIT})


class SayacSatiriTests(SayfaKurulumu, unittest.TestCase):
    """Dogrulanmayanlar tek satirda toplaniyor mu?"""

    def kur(self, sayfa, dogrulanan=(), hepsi=()):
        sayfa.on_packet({"type": "room_snapshot", "room": "general", "users": list(hepsi)})
        sayfa.on_packet(
            {"type": "peers_verified", "room": "general", "users": list(dogrulanan)}
        )

    def test_dogrulanmayanlar_tek_satirda(self):
        sayfa = self.sayfa()

        self.kur(sayfa, dogrulanan=["veli"], hepsi=["ayse", "veli", "x", "y", "z"])

        satirlar = self.satirlar(sayfa)
        self.assertEqual(satirlar, ["ayse", "veli", t("chat.unverified_many", count=3)])

    def test_tek_dogrulanmayan_tekil_yaziliyor(self):
        sayfa = self.sayfa()

        self.kur(sayfa, dogrulanan=["veli"], hepsi=["ayse", "veli", "x"])

        self.assertEqual(self.satirlar(sayfa)[-1], t("chat.unverified_one"))

    def test_tiklayinca_adlar_aciliyor(self):
        sayfa = self.sayfa()
        self.kur(sayfa, dogrulanan=[], hepsi=["ayse", "x", "y"])
        sayac = sayfa.user_list.item(sayfa.user_list.count() - 1)

        sayfa._on_user_item_clicked(sayac)

        satirlar = self.satirlar(sayfa)
        self.assertIn("   x", satirlar)
        self.assertIn("   y", satirlar)

    def test_tekrar_tiklayinca_kapaniyor(self):
        sayfa = self.sayfa()
        self.kur(sayfa, dogrulanan=[], hepsi=["ayse", "x"])
        sayac = sayfa.user_list.item(sayfa.user_list.count() - 1)
        sayfa._on_user_item_clicked(sayac)

        sayfa._on_user_item_clicked(sayfa.user_list.item(sayfa.user_list.count() - 2))

        self.assertEqual(self.satirlar(sayfa), ["ayse", t("chat.unverified_one")])

    def test_acik_liste_de_sinirli(self):
        """Binlerce satir cizmek arayuzu kilitlerdi."""
        from apps.proxychat.ui import UNVERIFIED_LIMIT

        sayfa = self.sayfa()
        kalabalik = ["ayse"] + [f"sahte{i}" for i in range(UNVERIFIED_LIMIT + 50)]
        self.kur(sayfa, dogrulanan=[], hepsi=kalabalik)
        sayac = sayfa.user_list.item(sayfa.user_list.count() - 1)

        sayfa._on_user_item_clicked(sayac)

        # 1 kendimiz + 1 sayac + en fazla UNVERIFIED_LIMIT ad
        self.assertEqual(sayfa.user_list.count(), 2 + UNVERIFIED_LIMIT)

    def test_dogrulanan_olmayinca_sayac_yok(self):
        sayfa = self.sayfa()

        self.kur(sayfa, dogrulanan=["veli"], hepsi=["ayse", "veli"])

        self.assertEqual(self.satirlar(sayfa), ["ayse", "veli"])

    def test_parolasiz_odada_sayac_yok(self):
        sayfa = self.sayfa(encrypted=False)

        sayfa.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse", "x"]})

        self.assertEqual(self.satirlar(sayfa), ["ayse", "x"])


class KatilmaDuyurusuTests(SayfaKurulumu, unittest.TestCase):
    """Dogrulanmayanin girdigi sohbette hic gorunmemeli."""

    def sistem_satirlari(self, sayfa) -> str:
        return sayfa.message_view.toPlainText()

    def test_dogrulanmayan_katilma_duyurulmuyor(self):
        sayfa = self.sayfa()
        sayfa.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse"]})

        sayfa.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse", "sahte"]})

        self.assertNotIn("sahte", self.sistem_satirlari(sayfa))

    def test_dogrulaninca_duyuruluyor(self):
        sayfa = self.sayfa()
        sayfa.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse"]})
        sayfa.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse", "veli"]})

        sayfa.on_packet({"type": "peers_verified", "room": "general", "users": ["veli"]})

        self.assertIn("veli", self.sistem_satirlari(sayfa))

    def test_odaya_girdigimizde_iceridekiler_duyurulmuyor(self):
        """Onlar biz gelmeden once oradaydi; el sikismasi bitince katilmis olmuyorlar."""
        sayfa = self.sayfa()
        sayfa.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse", "veli"]})

        sayfa.on_packet({"type": "peers_verified", "room": "general", "users": ["veli"]})

        self.assertNotIn("veli", self.sistem_satirlari(sayfa))

    def test_dogrulanmayanin_ayrilmasi_da_duyurulmuyor(self):
        sayfa = self.sayfa()
        sayfa.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse"]})
        sayfa.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse", "sahte"]})

        sayfa.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse"]})

        self.assertNotIn("sahte", self.sistem_satirlari(sayfa))

    def test_dogrulanmis_kisinin_ayrilmasi_duyuruluyor(self):
        sayfa = self.sayfa()
        sayfa.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse"]})
        sayfa.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse", "veli"]})
        sayfa.on_packet({"type": "peers_verified", "room": "general", "users": ["veli"]})

        sayfa.on_packet({"type": "room_snapshot", "room": "general", "users": ["ayse"]})

        self.assertIn(t("chat.user_left", user="veli"), self.sistem_satirlari(sayfa))


if __name__ == "__main__":
    unittest.main()
