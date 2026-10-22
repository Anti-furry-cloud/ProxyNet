"""Ileri gizli oda oturumu (core/room_session.py).

Ag yok: iki ya da uc oturum nesnesi birbirine elle paket veriyor. Boylece
anahtar akisinin tamami soket acmadan sinaniyor.
"""

import unittest

from core.crypto import DecryptionError
from core.key_agreement import OfferError
from core.room_session import (
    KEY_ID_BYTES,
    SCHEME,
    RoomSession,
    UnknownSenderKey,
    key_id,
)

ODA = "kule"
PAROLA = "dogru-at-pil-zimba"


def el_sik(birinci: RoomSession, ikinci: RoomSession) -> None:
    """Iki oturumu karsilikli anahtarlandirir; agda olacak sirayla."""
    ilk_acik, ilk_etiket = birinci.offer()
    ikinci_acik, ikinci_etiket = ikinci.offer()

    ikinciden = ikinci.accept_offer(ilk_acik, ilk_etiket)
    birinciden = birinci.accept_offer(ikinci_acik, ikinci_etiket)

    birinci.accept_sender_key(ikinci_acik, ikinciden)
    ikinci.accept_sender_key(ilk_acik, birinciden)


class ElSikismaTests(unittest.TestCase):
    def setUp(self):
        self.ayse = RoomSession(ODA, PAROLA)
        self.veli = RoomSession(ODA, PAROLA)

    def test_el_sikistiktan_sonra_mesaj_cozuluyor(self):
        el_sik(self.ayse, self.veli)

        token = self.ayse.encrypt("bulusma 21:00")

        self.assertEqual(self.veli.decrypt(token), "bulusma 21:00")

    def test_kendi_mesajini_cozebiliyor(self):
        """Arayuz gonderdigi mesaji da listede gosteriyor."""
        token = self.ayse.encrypt("hazirim")

        self.assertEqual(self.ayse.decrypt(token), "hazirim")

    def test_anahtar_gelmeden_gelen_mesaj_parola_hatasi_degil(self):
        """Gecici durum: es henuz anahtarini gondermedi."""
        token = self.ayse.encrypt("erken geldim")

        with self.assertRaises(UnknownSenderKey):
            self.veli.decrypt(token)

    def test_farkli_parolali_es_reddediliyor(self):
        yabanci = RoomSession(ODA, "baska-parola")
        acik, etiket = yabanci.offer()

        with self.assertRaises(OfferError):
            self.ayse.accept_offer(acik, etiket)

    def test_anlasma_olmadan_gonderen_anahtari_acilmiyor(self):
        acik, _ = self.veli.offer()

        with self.assertRaises(UnknownSenderKey):
            self.ayse.accept_sender_key(acik, b"x" * 40)

    def test_es_sayisi(self):
        self.assertEqual(self.ayse.peer_count, 0)

        el_sik(self.ayse, self.veli)

        self.assertEqual(self.ayse.peer_count, 1)

    def test_es_cikinca_anahtari_birakiliyor(self):
        el_sik(self.ayse, self.veli)
        token = self.veli.encrypt("cikiyorum")
        veli_acik, _ = self.veli.offer()

        self.ayse.forget_peer(veli_acik)

        with self.assertRaises(UnknownSenderKey):
            self.ayse.decrypt(token)
        self.assertEqual(self.ayse.peer_count, 0)


class UcKisiTests(unittest.TestCase):
    """Gonderen anahtari deseni grup icin: herkes herkesi cozmeli."""

    def test_herkes_herkesin_mesajini_cozuyor(self):
        ayse, veli, zeynep = (RoomSession(ODA, PAROLA) for _ in range(3))
        el_sik(ayse, veli)
        el_sik(ayse, zeynep)
        el_sik(veli, zeynep)

        tokenlar = {
            "ayse": ayse.encrypt("ben ayse"),
            "veli": veli.encrypt("ben veli"),
            "zeynep": zeynep.encrypt("ben zeynep"),
        }

        for oturum in (ayse, veli, zeynep):
            for kim, token in tokenlar.items():
                self.assertEqual(oturum.decrypt(token), f"ben {kim}")


class TokenTests(unittest.TestCase):
    def setUp(self):
        self.ayse = RoomSession(ODA, PAROLA)

    def test_ayni_metin_farkli_token_veriyor(self):
        """Nonce her mesajda yeni; ayni metin ayni token'i vermemeli."""
        self.assertNotEqual(self.ayse.encrypt("selam"), self.ayse.encrypt("selam"))

    def test_kurcalanan_token_reddediliyor(self):
        token = bytearray(self.ayse.encrypt("selam").encode("ascii"))
        token[-2] = ord("A") if token[-2] != ord("A") else ord("B")

        with self.assertRaises(DecryptionError):
            self.ayse.decrypt(bytes(token).decode("ascii"))

    def test_kisa_token_reddediliyor(self):
        with self.assertRaises(DecryptionError):
            self.ayse.decrypt("YWJj")

    def test_bozuk_base64_reddediliyor(self):
        with self.assertRaises(DecryptionError):
            self.ayse.decrypt("bu base64 degil!!")

    def test_baska_odadaki_es_el_sikisamiyor(self):
        """Teklifin etiketinde oda adi var: takas odalar arasi yapilamaz."""
        baska = RoomSession("baska-oda", PAROLA)
        acik, etiket = baska.offer()

        with self.assertRaises(OfferError):
            self.ayse.accept_offer(acik, etiket)

    def test_ayni_anahtarla_bile_token_baska_odada_cozulmuyor(self):
        """AAD'de oda adi var.

        Anahtar bir sekilde iki odada ayni olsa bile (el sikisma bunu zaten
        engelliyor, burada anahtar elle veriliyor) mesaj odasindan cikamiyor.
        """
        ortak = b"k" * 32
        burada = RoomSession(ODA, PAROLA, sender_key=ortak)
        orada = RoomSession("baska-oda", PAROLA, sender_key=ortak)

        token = burada.encrypt("gizli")

        with self.assertRaises(DecryptionError):
            orada.decrypt(token)

    def test_sema_adi(self):
        self.assertEqual(self.ayse.scheme, SCHEME)
        self.assertNotEqual(SCHEME, "fernet-argon2id-v1")


class AnahtarKimligiTests(unittest.TestCase):
    def test_kimlik_4_bayt_ve_kararli(self):
        anahtar = b"k" * 32

        self.assertEqual(len(key_id(anahtar)), KEY_ID_BYTES)
        self.assertEqual(key_id(anahtar), key_id(anahtar))

    def test_farkli_anahtar_farkli_kimlik(self):
        self.assertNotEqual(key_id(b"a" * 32), key_id(b"b" * 32))

    def test_kimlik_anahtari_ele_vermiyor(self):
        anahtar = b"k" * 32

        self.assertNotIn(key_id(anahtar), anahtar)


class IleriGizlilikTests(unittest.TestCase):
    """Bu katmanin varlik sebebi: tests/test_crypto.py'deki hedef testleri."""

    def test_iki_oturum_ayni_parolayla_bile_birbirini_cozmuyor(self):
        birinci = RoomSession(ODA, PAROLA)
        token = birinci.encrypt("bulusma 21:00")

        # Oturum bitti, yeni oturum ayni oda ve ayni parolayla acildi.
        ikinci = RoomSession(ODA, PAROLA)

        with self.assertRaises(UnknownSenderKey):
            ikinci.decrypt(token)

    def test_parolayi_bilen_rakip_kaydi_acamiyor(self):
        """T5 senaryosu: parola sonradan sizdi, kayit rakibin elinde."""
        ayse, veli = RoomSession(ODA, PAROLA), RoomSession(ODA, PAROLA)
        el_sik(ayse, veli)
        kayit = [ayse.encrypt("bulusma 21:00"), veli.encrypt("hazirim")]

        # Rakip parolayi biliyor, yani gecerli bir oturum bile kurabilir.
        rakip = RoomSession(ODA, PAROLA)

        for token in kayit:
            with self.assertRaises(UnknownSenderKey):
                rakip.decrypt(token)


if __name__ == "__main__":
    unittest.main()
