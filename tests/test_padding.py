"""Mesaj dolgusu (core/padding.py) ve odaya baglanan hali.

Buradaki asil test `test_kisa_mesajlar_ayirt_edilemiyor`: dolgunun varlik
sebebi o. Gerisi bicimin ve sinirlarin kilidi.

THREAT_MODEL.md 5.7 bu dosyaya dayanarak kapandi; testler duserse belgedeki
guvence de duser.
"""

import base64
import unittest

from core import padding
from core.crypto import DecryptionError
from core.protocol import MAX_CONTENT_BYTES
from core.room_session import KEY_ID_BYTES, NONCE_BYTES, SCHEME, RoomSession


class BicimTests(unittest.TestCase):
    def test_gidis_donus(self):
        for uzunluk in (0, 1, 5, 29, 30, 31, 62, 63, 500, 4095, padding.max_plaintext_bytes()):
            veri = b"x" * uzunluk
            self.assertEqual(padding.unpad(padding.pad(veri)), veri, uzunluk)

    def test_sonuc_her_zaman_bir_basamak(self):
        for uzunluk in range(0, 300):
            self.assertIn(len(padding.pad(b"x" * uzunluk)), padding.BUCKETS, uzunluk)

    def test_dolgu_sifir(self):
        """Dolgu rastgele degil: sifreli metnin icinde kaliyor, rastgelelik bedel olurdu."""
        dolgulu = padding.pad(b"ok")
        self.assertEqual(dolgulu[padding.LENGTH_BYTES + 2 :], bytes(len(dolgulu) - 4))

    def test_uzunluk_alani_basta(self):
        self.assertEqual(padding.pad(b"abc")[: padding.LENGTH_BYTES], (3).to_bytes(2, "big"))

    def test_sifirla_biten_metin_bozulmuyor(self):
        """Sifirlari sayarak cozmek bunu yanlis okurdu; uzunluk alani bu yuzden var."""
        veri = b"veri\x00\x00\x00"
        self.assertEqual(padding.unpad(padding.pad(veri)), veri)

    def test_bos_metin(self):
        self.assertEqual(padding.unpad(padding.pad(b"")), b"")
        self.assertEqual(len(padding.pad(b"")), padding.BUCKETS[0])


class BasamakTests(unittest.TestCase):
    def test_taban_basamagi(self):
        """Taban altindaki her sey ayni boyda: dolgunun butun kazanci burada."""
        taban = padding.BUCKETS[0]
        for uzunluk in range(0, taban - padding.LENGTH_BYTES + 1):
            self.assertEqual(len(padding.pad(b"x" * uzunluk)), taban, uzunluk)

    def test_basamagin_tam_ustu_sonrakine_gecer(self):
        taban = padding.BUCKETS[0]
        tam = taban - padding.LENGTH_BYTES
        self.assertEqual(len(padding.pad(b"x" * tam)), taban)
        self.assertEqual(len(padding.pad(b"x" * (tam + 1))), padding.BUCKETS[1])

    def test_basamaklar_artan(self):
        self.assertEqual(list(padding.BUCKETS), sorted(padding.BUCKETS))
        self.assertEqual(len(set(padding.BUCKETS)), len(padding.BUCKETS))

    def test_sizinti_dort_bitin_altinda(self):
        """Kova sayisi uzunluk yerine gorunen bilgiyi belirliyor."""
        self.assertLessEqual(len(padding.BUCKETS), 16)

    def test_bucket_for_uzunluk_alanini_sayiyor(self):
        self.assertEqual(padding.bucket_for(padding.BUCKETS[0] - padding.LENGTH_BYTES), padding.BUCKETS[0])
        self.assertEqual(padding.bucket_for(padding.BUCKETS[0] - padding.LENGTH_BYTES + 1), padding.BUCKETS[1])


class SinirTests(unittest.TestCase):
    def test_en_uzun_metin_sunucu_sinirini_tam_dolduruyor(self):
        oda = RoomSession("oda", "parola")
        token = oda.encrypt("a" * padding.max_plaintext_bytes())

        self.assertEqual(len(token.encode("utf-8")), MAX_CONTENT_BYTES)

    def test_bir_bayt_fazlasi_reddediliyor(self):
        with self.assertRaises(padding.MessageTooLong):
            padding.pad(b"a" * (padding.max_plaintext_bytes() + 1))

    def test_izin_verilen_hicbir_metin_siniri_asmiyor(self):
        oda = RoomSession("oda", "parola")
        for uzunluk in (0, 1, 30, 31, 4095, 4096, padding.max_plaintext_bytes()):
            token = oda.encrypt("a" * uzunluk)
            self.assertLessEqual(len(token.encode("utf-8")), MAX_CONTENT_BYTES, uzunluk)

    def test_zarf_ek_yuku_room_session_ile_ayni(self):
        """Sabit iki yerde yazili (dongusel import); ayrismasi sinirlari kaydirirdi."""
        self.assertEqual(padding.ENVELOPE_BYTES, KEY_ID_BYTES + NONCE_BYTES + 16)

    def test_uzunluk_karakter_degil_bayt(self):
        """Turkce harfler iki bayt: sinir karakterle sayilsa metin sunucudan donerdi."""
        oda = RoomSession("oda", "parola")
        metin = "ş" * (padding.max_plaintext_bytes() // 2)

        self.assertEqual(len(oda.encrypt(metin).encode("utf-8")), MAX_CONTENT_BYTES)


class BozukYukTests(unittest.TestCase):
    def test_uzunluk_alanindan_kisa_yuk(self):
        with self.assertRaises(ValueError):
            padding.unpad(b"\x00")

    def test_bildirilen_uzunluk_yuke_sigmiyor(self):
        with self.assertRaises(ValueError):
            padding.unpad((999).to_bytes(2, "big") + b"kisa")

    def test_bozuk_yuk_cozulemedi_diye_gorunuyor(self):
        """Arayuz ValueError gormemeli; `DecryptionError` bekliyor."""
        oda = RoomSession("oda", "parola")
        ham = base64.urlsafe_b64decode(oda.encrypt("selam").encode("ascii"))
        # Etiketi bozarak degil, bicimi taniyamayacagimiz bir surumu taklit
        # ederek: anahtar kimligi dogru, govde cop.
        bozuk = base64.urlsafe_b64encode(ham[: KEY_ID_BYTES + NONCE_BYTES] + b"\x00" * 32)

        with self.assertRaises(DecryptionError):
            oda.decrypt(bozuk.decode("ascii"))


class OdaTests(unittest.TestCase):
    def setUp(self):
        self.oda = RoomSession("oda", "parola")

    def test_kisa_mesajlar_ayirt_edilemiyor(self):
        """Dolgunun varlik sebebi: sunucu "ok" ile paragrafi ayirt edemesin.

        Ayni kovaya dusen mesajlarin token'lari **birebir ayni** uzunlukta
        olmali. Tek bir tanesi digerlerinden farkli cikarsa 5.7 geri aciliyor.
        """
        mesajlar = ("ok", "hayir", "geliyorum", "tamam", "5 dakika sonra", "yok", "olur")

        boylar = {len(self.oda.encrypt(m)) for m in mesajlar}

        self.assertEqual(len(boylar), 1, f"kisa mesajlar ayirt edilebiliyor: {boylar}")

    def test_dolgusuz_halde_ayirt_edilebilirdi(self):
        """Onceki durumun kaydi: ayni mesajlar sifrelenmeden farkli boydaydi."""
        mesajlar = ("ok", "hayir", "geliyorum")

        self.assertEqual(len({len(m) for m in mesajlar}), 3)

    def test_ayni_uzunluk_ayni_token_boyu(self):
        a = self.oda.encrypt("a" * 100)
        b = self.oda.encrypt("b" * 100)

        self.assertEqual(len(a), len(b))

    def test_ayni_kovadaki_farkli_uzunluklar_ayni_boyda(self):
        """Uzunluklar farkli, kova ayni: token boylari da ayni olmali.

        40 ile 60 ikinci basamaga dusuyor; 40 ile 120 **dusmuyor** ve
        dusmemesi gerekiyor -- dolgu uzunlugu tamamen degil, kova
        hassasiyetine kadar gizliyor.
        """
        self.assertEqual(padding.bucket_for(40), padding.bucket_for(60))

        self.assertEqual(len(self.oda.encrypt("a" * 40)), len(self.oda.encrypt("a" * 60)))

    def test_farkli_kovalar_ayrilabiliyor(self):
        """Dolgunun verdigi guvencenin siniri: kova gizlenmiyor, yazili olsun."""
        self.assertNotEqual(len(self.oda.encrypt("a" * 40)), len(self.oda.encrypt("a" * 120)))

    def test_sema_v2(self):
        """Dolgu pazarliga acik degil: sema adi degisti, eski istemci tanimiyor."""
        self.assertEqual(SCHEME, "aesgcm-x25519-v2")

    def test_uzun_metin_gidis_donus(self):
        metin = "satir\n" * 500

        self.assertEqual(self.oda.decrypt(self.oda.encrypt(metin)), metin)

    def test_can_read_dolguyla_calisiyor(self):
        """Bekletme kuyrugu token'in basina bakiyor; dolgu o yapiyi bozmamali."""
        token = self.oda.encrypt("selam")

        self.assertTrue(self.oda.can_read(token))


if __name__ == "__main__":
    unittest.main()
