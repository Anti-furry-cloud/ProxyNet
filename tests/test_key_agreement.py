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
    pair_psk,
    unwrap_sender_key,
    verify_offer,
    wrap_sender_key,
)

ODA = "kule"
PAROLA = "dogru-at-pil-zimba"


def ana_anahtar(oda: str = ODA, parola: str = PAROLA) -> bytes:
    return derive_master_key(oda, parola)


#: Testlerin cogu icin parola ayni; Argon2id yavas oldugu icin bir kez turetiliyor.
PSK = pair_psk(ana_anahtar(), ODA)


class IkiliAnahtarTests(unittest.TestCase):
    def test_iki_taraf_ayni_anahtari_buluyor(self):
        ayse, veli = EphemeralKey(), EphemeralKey()

        self.assertEqual(ayse.pair_key(veli.public_key, PSK), veli.pair_key(ayse.public_key, PSK))

    def test_acik_anahtar_32_bayt(self):
        self.assertEqual(len(EphemeralKey().public_key), PUBLIC_KEY_BYTES)

    def test_her_oturum_farkli_anahtar_uretiyor(self):
        """Ileri gizliligin koku: ayni parola, ayni oda, farkli anahtar.

        Bugunku tasarimda anahtar parolanin fonksiyonu oldugu icin iki oturum
        ayni anahtari kullaniyor (bkz. tests/test_crypto.py →
        ForwardSecrecyTests). Burada oyle degil.
        """
        birinci = EphemeralKey().pair_key(EphemeralKey().public_key, PSK)
        ikinci = EphemeralKey().pair_key(EphemeralKey().public_key, PSK)

        self.assertNotEqual(birinci, ikinci)

    def test_parola_ikili_anahtara_giriyor(self):
        """1.13.0'dan beri: ayni gecici anahtarlar, farkli parola, farkli anahtar.

        Bu test 1.9.0'da tam tersini kilitliyordu ("parola ikili anahtara
        girmiyor"): o gun parolanin tek isi dogrulamakti. Kuantuma karsi ilk
        adimda (THREAT_MODEL 5.10) parola anahtara da girdi -- bilerek.
        """
        ayse, veli = EphemeralKey(), EphemeralKey()
        baska = pair_psk(ana_anahtar(parola="baska-parola"), ODA)

        self.assertNotEqual(ayse.pair_key(veli.public_key, PSK), ayse.pair_key(veli.public_key, baska))

    def test_kendi_anahtarimizla_anlasma_reddediliyor(self):
        ayse = EphemeralKey()

        with self.assertRaises(OfferError):
            ayse.pair_key(ayse.public_key, PSK)

    def test_bozuk_acik_anahtar_reddediliyor(self):
        ayse = EphemeralKey()

        with self.assertRaises(OfferError):
            ayse.pair_key(b"kisa", PSK)


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
        self.ikili = self.ayse.pair_key(self.veli.public_key, PSK)

    def test_sarilip_aciliyor(self):
        gonderen = new_sender_key()

        sarili = wrap_sender_key(self.ikili, gonderen)

        self.assertEqual(unwrap_sender_key(self.veli.pair_key(self.ayse.public_key, PSK), sarili), gonderen)

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
        yabanci = EphemeralKey().pair_key(EphemeralKey().public_key, PSK)

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
            "sarili": wrap_sender_key(ayse.pair_key(veli.public_key, PSK), gonderen),
            "mesaj": AESGCM(gonderen).encrypt(b"\x00" * 12, b"bulusma 21:00", None),
        }

        # Rakip: parola elinde, yani gecerli teklif bile uretebilir. Ama gecmis
        # oturumun gizli anahtari yok; kendi anahtariyla baska bir ikili
        # anahtar buluyor ve sarili paketi acamiyor.
        rakip = EphemeralKey()
        verify_offer(kayit["ayse_acik"], offer_mac(kayit["ayse_acik"], anahtar, ODA), anahtar, ODA)

        with self.assertRaises(SenderKeyError):
            unwrap_sender_key(rakip.pair_key(kayit["ayse_acik"], PSK), kayit["sarili"])

    def test_oturum_bitince_ayni_anahtar_bir_daha_dogmuyor(self):
        """Yeni oturum, ayni parolayla bile eski anahtari uretemiyor."""
        ayse, veli = EphemeralKey(), EphemeralKey()
        eski = ayse.pair_key(veli.public_key, PSK)

        yeniden = EphemeralKey().pair_key(EphemeralKey().public_key, PSK)

        self.assertNotEqual(eski, yeniden)


class KuantumTests(unittest.TestCase):
    """Kuantuma karsi ilk adim (1.13.0, THREAT_MODEL 5.10).

    Senaryo: rakip oturumu kaydetti ve yillar sonra X25519'u kirabilen bir
    makineye sahip oldu. Testte bunu, rakibe Ayse'nin gecici gizli anahtarini
    vererek modelliyoruz -- X25519'u kirmanin sonucu tam olarak bu. Elinde
    **olmayan** sey parola.
    """

    def setUp(self):
        self.ayse, self.veli = EphemeralKey(), EphemeralKey()
        self.gonderen = new_sender_key()
        self.sarili = wrap_sender_key(self.ayse.pair_key(self.veli.public_key, PSK), self.gonderen)

    def test_x25519_kirilsa_da_parolasiz_acilmiyor(self):
        # Rakip X25519'u kirdi: Ayse'nin gizli anahtarina sahip (ayni nesne).
        # Parolayi bilmedigi icin kendi tahminiyle bir on paylasimli anahtar kuruyor.
        tahmin = pair_psk(ana_anahtar(parola="tahmin-edilen"), ODA)

        with self.assertRaises(SenderKeyError):
            unwrap_sender_key(self.ayse.pair_key(self.veli.public_key, tahmin), self.sarili)

    def test_x25519_kirilip_parola_da_bilinirse_aciliyor(self):
        """Sinir durustce: zayif ya da sizmis parola korumuyor."""
        self.assertEqual(
            unwrap_sender_key(self.ayse.pair_key(self.veli.public_key, PSK), self.sarili),
            self.gonderen,
        )

    def test_eski_turetim_artik_anahtari_vermiyor(self):
        """1.12.x'teki gibi yalnizca X25519'dan turetmek ise yaramiyor."""
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF

        ortak = self.ayse._private.exchange(X25519PublicKey.from_public_bytes(self.veli.public_key))
        tuz = b"".join(sorted((self.ayse.public_key, self.veli.public_key)))
        eski = HKDF(algorithm=hashes.SHA256(), length=32, salt=tuz, info=b"proxynet-pair-v1").derive(ortak)

        with self.assertRaises(SenderKeyError):
            unwrap_sender_key(eski, self.sarili)

    def test_on_paylasimli_anahtar_odaya_bagli(self):
        self.assertNotEqual(pair_psk(ana_anahtar(), ODA), pair_psk(ana_anahtar(), "baska-oda"))

    def test_on_paylasimli_anahtar_teklif_etiketiyle_ayni_degil(self):
        """Etiket acikta gidiyor; on paylasimli anahtar ondan cikarilamamali."""
        anahtar = ana_anahtar()

        self.assertNotEqual(pair_psk(anahtar, ODA), offer_mac(self.ayse.public_key, anahtar, ODA))
        self.assertNotEqual(pair_psk(anahtar, ODA), anahtar)

    def test_oda_oturumu_parolanin_on_paylasimli_anahtarini_kullaniyor(self):
        """pair_key'in dogru olmasi yetmez; oda oturumu ona dogru anahtari vermeli.

        Iki taraf ayni yanlis anahtari verse (ornegin bos oda adiyla) testler
        yine gecerdi; burada sarili anahtar, oda + parolanin on paylasimli
        anahtariyla disaridan aciliyor.
        """
        from core.room_session import RoomSession

        ea, eb = EphemeralKey(), EphemeralKey()
        a = RoomSession(ODA, PAROLA, ephemeral=ea)
        b = RoomSession(ODA, PAROLA, ephemeral=eb)

        sarili = a.accept_offer(*b.offer())

        self.assertEqual(unwrap_sender_key(eb.pair_key(ea.public_key, PSK), sarili), a._sender_key)

    def test_bilinen_cevap(self):
        """Turetimin tamami sabit girdilerle kilitli (test vektoru).

        Baglam dizesi, HKDF girdilerinin sirasi ya da info etiketi sessizce
        degisirse anahtarlar degisir ve iki surum birbirini acamaz; bunu
        yalnizca bilinen cevap yakalar. Degerler modulden degil, ayrica
        dogrudan HMAC + X25519 + HKDF ile hesaplanarak dogrulandi (2026-10-24).
        """
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

        psk = pair_psk(bytes(range(32)), "kule")
        a = EphemeralKey(X25519PrivateKey.from_private_bytes(bytes([1]) * 32))
        b = EphemeralKey(X25519PrivateKey.from_private_bytes(bytes([2]) * 32))

        self.assertEqual(psk.hex(), "3210287eae6d7b1fc2bce77dcc62c6c5b63bf8d8d07999c71018070320ead2e8")
        self.assertEqual(
            a.pair_key(b.public_key, psk).hex(),
            "0761690a79c98586401117e29bc348abf138026173d24c3dec49326491c5b453",
        )

    def test_on_paylasimli_anahtarsiz_cagri_reddediliyor(self):
        """Unutulan arguman sessizce eski anahtara dusmesin."""
        with self.assertRaises(TypeError):
            self.ayse.pair_key(self.veli.public_key)
        with self.assertRaises(ValueError):
            self.ayse.pair_key(self.veli.public_key, b"kisa")


if __name__ == "__main__":
    unittest.main()
