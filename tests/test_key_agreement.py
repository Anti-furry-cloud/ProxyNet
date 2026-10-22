"""Gecici anahtar anlasmasi (core/key_agreement.py).

Ag yok: iki tarafin da anahtarlari burada elle uretiliyor. Amac, ileri
gizliligin kripto katmanini protokole dokunmadan kilitlemek.
"""

import unittest

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.crypto import derive_master_key
from core.key_agreement import (
    OFFER_MAC_BYTES,
    PUBLIC_KEY_BYTES,
    SENDER_KEY_BYTES,
    EphemeralKey,
    OfferError,
    SenderKeyError,
    new_sender_key,
    offer_mac,
    unwrap_sender_key,
    verify_offer,
    wrap_sender_key,
)

ODA = "kule"
PAROLA = "dogru-at-pil-zimba"


def ana_anahtar(oda: str = ODA, parola: str = PAROLA) -> bytes:
    return derive_master_key(oda, parola)


class IkiliAnahtarTests(unittest.TestCase):
    def test_iki_taraf_ayni_anahtari_buluyor(self):
        ayse, veli = EphemeralKey(), EphemeralKey()

        self.assertEqual(ayse.pair_key(veli.public_key), veli.pair_key(ayse.public_key))

    def test_acik_anahtar_32_bayt(self):
        self.assertEqual(len(EphemeralKey().public_key), PUBLIC_KEY_BYTES)

    def test_her_oturum_farkli_anahtar_uretiyor(self):
        """Ileri gizliligin koku: ayni parola, ayni oda, farkli anahtar.

        Bugunku tasarimda anahtar parolanin fonksiyonu oldugu icin iki oturum
        ayni anahtari kullaniyor (bkz. tests/test_crypto.py →
        ForwardSecrecyTests). Burada oyle degil.
        """
        birinci = EphemeralKey().pair_key(EphemeralKey().public_key)
        ikinci = EphemeralKey().pair_key(EphemeralKey().public_key)

        self.assertNotEqual(birinci, ikinci)

    def test_parola_ikili_anahtara_girmiyor(self):
        """Anahtar yalnizca gecici anahtarlardan doguyor; parola imzada.

        Ayni gecici anahtarlarla, parolayi bilmeden de ayni ikili anahtar
        cikar -- cunku parolanin isi sifrelemek degil, dogrulamak.
        """
        ayse, veli = EphemeralKey(), EphemeralKey()

        self.assertEqual(ayse.pair_key(veli.public_key), veli.pair_key(ayse.public_key))

    def test_kendi_anahtarimizla_anlasma_reddediliyor(self):
        ayse = EphemeralKey()

        with self.assertRaises(OfferError):
            ayse.pair_key(ayse.public_key)

    def test_bozuk_acik_anahtar_reddediliyor(self):
        ayse = EphemeralKey()

        with self.assertRaises(OfferError):
            ayse.pair_key(b"kisa")


class TeklifTests(unittest.TestCase):
    def test_kendi_teklifi_dogrulaniyor(self):
        anahtar = ana_anahtar()
        ayse = EphemeralKey()

        verify_offer(ayse.public_key, ayse.offer(anahtar, ODA), anahtar, ODA)

    def test_etiket_32_bayt(self):
        ayse = EphemeralKey()

        self.assertEqual(len(ayse.offer(ana_anahtar(), ODA)), OFFER_MAC_BYTES)

    def test_farkli_parola_dogrulanmiyor(self):
        """Parolayi bilmeyen gecerli teklif uretemez."""
        ayse = EphemeralKey()
        etiket = ayse.offer(ana_anahtar(parola="baska-parola"), ODA)

        with self.assertRaises(OfferError):
            verify_offer(ayse.public_key, etiket, ana_anahtar(), ODA)

    def test_teklif_baska_odaya_tasinamiyor(self):
        anahtar = ana_anahtar()
        ayse = EphemeralKey()
        etiket = ayse.offer(anahtar, ODA)

        with self.assertRaises(OfferError):
            verify_offer(ayse.public_key, etiket, anahtar, "baska-oda")

    def test_degistirilmis_acik_anahtar_yakalaniyor(self):
        """Aradaki biri acik anahtari degistirirse etiket tutmaz."""
        anahtar = ana_anahtar()
        ayse = EphemeralKey()
        etiket = ayse.offer(anahtar, ODA)
        sahte = EphemeralKey().public_key

        with self.assertRaises(OfferError):
            verify_offer(sahte, etiket, anahtar, ODA)

    def test_tek_bit_bozulan_etiket_reddediliyor(self):
        anahtar = ana_anahtar()
        ayse = EphemeralKey()
        etiket = bytearray(ayse.offer(anahtar, ODA))
        etiket[0] ^= 1

        with self.assertRaises(OfferError):
            verify_offer(ayse.public_key, bytes(etiket), anahtar, ODA)

    def test_yanlis_boyda_etiket_reddediliyor(self):
        ayse = EphemeralKey()

        with self.assertRaises(OfferError):
            verify_offer(ayse.public_key, b"kisa", ana_anahtar(), ODA)

    def test_ayni_girdi_ayni_etiketi_veriyor(self):
        anahtar = ana_anahtar()
        ayse = EphemeralKey()

        self.assertEqual(
            offer_mac(ayse.public_key, anahtar, ODA),
            offer_mac(ayse.public_key, anahtar, ODA),
        )


class GonderenAnahtariTests(unittest.TestCase):
    def setUp(self):
        self.ayse, self.veli = EphemeralKey(), EphemeralKey()
        self.ikili = self.ayse.pair_key(self.veli.public_key)

    def test_sarilip_aciliyor(self):
        gonderen = new_sender_key()

        sarili = wrap_sender_key(self.ikili, gonderen)

        self.assertEqual(unwrap_sender_key(self.veli.pair_key(self.ayse.public_key), sarili), gonderen)

    def test_anahtar_32_bayt_ve_her_seferinde_farkli(self):
        birinci, ikinci = new_sender_key(), new_sender_key()

        self.assertEqual(len(birinci), SENDER_KEY_BYTES)
        self.assertNotEqual(birinci, ikinci)

    def test_ayni_anahtar_iki_kez_sarilinca_farkli_cikiyor(self):
        """Nonce her sarmada yeni: ayni cikti tekrar etmemeli."""
        gonderen = new_sender_key()

        self.assertNotEqual(
            wrap_sender_key(self.ikili, gonderen),
            wrap_sender_key(self.ikili, gonderen),
        )

    def test_yanlis_ikili_anahtarla_acilmiyor(self):
        sarili = wrap_sender_key(self.ikili, new_sender_key())
        yabanci = EphemeralKey().pair_key(EphemeralKey().public_key)

        with self.assertRaises(SenderKeyError):
            unwrap_sender_key(yabanci, sarili)

    def test_kurcalanan_paket_reddediliyor(self):
        sarili = bytearray(wrap_sender_key(self.ikili, new_sender_key()))
        sarili[-1] ^= 1

        with self.assertRaises(SenderKeyError):
            unwrap_sender_key(self.ikili, bytes(sarili))

    def test_cok_kisa_paket_reddediliyor(self):
        with self.assertRaises(SenderKeyError):
            unwrap_sender_key(self.ikili, b"kisa")

    def test_yanlis_boyda_gonderen_anahtari_sarilmiyor(self):
        with self.assertRaises(ValueError):
            wrap_sender_key(self.ikili, b"kisa")


class IleriGizlilikTests(unittest.TestCase):
    """Hedefin bu katmanda karsilanip karsilanmadigi.

    Senaryo T5: rakip oturumun butun paketlerini kaydetti (iki acik anahtar,
    sarilmis gonderen anahtari, sifreli mesaj) ve parolayi aylar sonra ele
    gecirdi. Elinde **olmayan** sey gecici gizli anahtarlar.
    """

    def test_parola_ve_kayit_birlikte_yetmiyor(self):
        anahtar = ana_anahtar()
        ayse, veli = EphemeralKey(), EphemeralKey()
        gonderen = new_sender_key()
        # Agda gorunen ve kaydedilen her sey:
        kayit = {
            "ayse_acik": ayse.public_key,
            "veli_acik": veli.public_key,
            "sarili": wrap_sender_key(ayse.pair_key(veli.public_key), gonderen),
            "mesaj": AESGCM(gonderen).encrypt(b"\x00" * 12, b"bulusma 21:00", None),
        }

        # Rakip: parola elinde, yani gecerli teklif bile uretebilir. Ama gecmis
        # oturumun gizli anahtari yok; kendi anahtariyla baska bir ikili
        # anahtar buluyor ve sarili paketi acamiyor.
        rakip = EphemeralKey()
        verify_offer(kayit["ayse_acik"], offer_mac(kayit["ayse_acik"], anahtar, ODA), anahtar, ODA)

        with self.assertRaises(SenderKeyError):
            unwrap_sender_key(rakip.pair_key(kayit["ayse_acik"]), kayit["sarili"])

    def test_oturum_bitince_ayni_anahtar_bir_daha_dogmuyor(self):
        """Yeni oturum, ayni parolayla bile eski anahtari uretemiyor."""
        ayse, veli = EphemeralKey(), EphemeralKey()
        eski = ayse.pair_key(veli.public_key)

        yeniden = EphemeralKey().pair_key(EphemeralKey().public_key)

        self.assertNotEqual(eski, yeniden)


if __name__ == "__main__":
    unittest.main()
