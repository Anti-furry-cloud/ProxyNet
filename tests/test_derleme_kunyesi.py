"""Derleme kunyesi (tools/derleme_kunyesi.py).

Kunye YAYINLANACAK bir dosya: yayinlanan ozetin yaninda durup "bu exe su
girdilerden cikti" diyor. O yuzden iki sey onemli -- dogru olmasi, ve
icinde makineye ozgu hicbir sey bulunmamasi.

Ikincisi test edilmeye deger, cunku kunyeyi ureten kod dosya yollariyla
calisiyor ve bir gun biri oraya `Path` yazdirmaya kalkabilir. Kullanici
adinin yayinlanan bir dosyaya sizmasi, bu projenin butun belgelerinde
kacindigi seyin ta kendisi.
"""

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import derleme_kunyesi as k


class SurumOkumaTests(unittest.TestCase):
    """Kunye surumu version.py'den okuyor ve bulamazsa SUSMUYOR.

    Eskiden bulunamayinca "?" donuyordu; asagidaki test_surum_yaziyor da
    "kunyede ne donduyse o yaziyor mu" diye baktigi icin "?" ile geciyordu.
    """

    def test_surum_uygulamanin_surumuyle_ayni(self):
        from apps.proxychat.version import APP_VERSION

        self.assertEqual(k.surum(), APP_VERSION)

    def test_aciklamadaki_ornek_satir_surum_sanilmaz(self):
        """Desen satir basina bagli: aciklama metnindeki ornek ilk eslesen olmasin."""
        with tempfile.TemporaryDirectory() as klasor:
            hedef = Path(klasor, "apps", "proxychat")
            hedef.mkdir(parents=True)
            (hedef / "version.py").write_text(
                '"""Ornek:\n\n    APP_VERSION = "9.9.9"\n"""\n\nAPP_VERSION = "1.0.0"\n',
                encoding="utf-8",
            )
            with mock.patch.object(k, "KOK", Path(klasor)):
                self.assertEqual(k.surum(), "1.0.0")

    def test_surum_bulunamazsa_hata_verir(self):
        with tempfile.TemporaryDirectory() as klasor:
            hedef = Path(klasor, "apps", "proxychat")
            hedef.mkdir(parents=True)
            (hedef / "version.py").write_text('APP_NAME = "ProxyChat"\n', encoding="utf-8")
            with mock.patch.object(k, "KOK", Path(klasor)):
                with self.assertRaises(ValueError):
                    k.surum()


class OzetTests(unittest.TestCase):
    def setUp(self):
        self.klasor = Path(tempfile.mkdtemp())

    def test_bilinen_degerle_ayni(self):
        yol = self.klasor / "a.bin"
        yol.write_bytes(b"proxychat")

        self.assertEqual(k.ozet(yol), hashlib.sha256(b"proxychat").hexdigest())

    def test_buyuk_dosya_parca_parca(self):
        icerik = b"x" * (k.BLOK * 2 + 17)
        yol = self.klasor / "buyuk.bin"
        yol.write_bytes(icerik)

        self.assertEqual(k.ozet(yol), hashlib.sha256(icerik).hexdigest())


class KaynakTarihiTests(unittest.TestCase):
    """Kunye, derlemede kullanilan SOURCE_DATE_EPOCH'u yaziyor.

    build_exe.ps1 ortamda verilen degeri koruyor; kunye git'tekini yazarsa
    yayin deposundan yeniden ureten biri yanlis bir deger gorur.
    """

    def test_ortamdaki_deger_yaziliyor(self):
        with mock.patch.dict("os.environ", {"SOURCE_DATE_EPOCH": "1791246136"}):
            self.assertIn("SOURCE_DATE_EPOCH: 1791246136", k.kunye())

    def test_gecersiz_ortam_degeri_yok_sayiliyor(self):
        with mock.patch.dict("os.environ", {"SOURCE_DATE_EPOCH": "dun"}):
            self.assertNotIn("SOURCE_DATE_EPOCH: dun", k.kunye())


class KunyeTests(unittest.TestCase):
    def setUp(self):
        self.metin = k.kunye()

    def test_surum_yaziyor(self):
        self.assertIn(f"Surum            : {k.surum()}", self.metin)

    def test_arac_zinciri_yaziyor(self):
        for parca in ("Python", "PyInstaller", "hooks-contrib", "NSIS"):
            self.assertIn(parca, self.metin, parca)

    def test_kilitli_paketler_yaziyor(self):
        for paket in ("PySide6==", "cryptography==", "pyinstaller=="):
            self.assertIn(paket, self.metin, paket)

    def test_imza_olmadigi_yaziyor(self):
        """Kunyeyi imza sanmak, olmayan bir guvence saymaktir."""
        self.assertIn("imza DEGILDIR", self.metin)

    def test_makineye_ozgu_hicbir_sey_yok(self):
        """Yayinlanacak dosyada kullanici adi ya da mutlak yol olmamali."""
        kok = str(k.KOK)
        self.assertNotIn(kok, self.metin)
        for parca in ("C:\\Users", "C:/Users", "AppData", ".venv", "Desktop"):
            self.assertNotIn(parca, self.metin, f"kunyede {parca} geciyor")

    def test_kirli_agac_soyleniyor(self):
        """Kirli agacta uretilen exe hicbir commit'e karsilik gelmiyor."""
        with mock.patch.object(k, "komut", side_effect=lambda *a: "M bir_dosya.py" if "status" in a else "x"):
            metin = k.kunye()

        self.assertIn("KIRLI", metin)

    def test_temiz_agac_soyleniyor(self):
        with mock.patch.object(k, "komut", side_effect=lambda *a: None if "status" in a else "x"):
            metin = k.kunye()

        self.assertIn("temiz", metin)

    def test_git_yoksa_cokmuyor(self):
        """Depo olmayan bir kopyada da bir sey uretebilmeli."""
        with mock.patch.object(k, "komut", return_value=None):
            metin = k.kunye()

        self.assertIn("ProxyChat derleme kunyesi", metin)


class KilitTests(unittest.TestCase):
    def test_kilit_dosyasi_hash_zorunlu_kiliyor(self):
        """--require-hashes calismasi icin her satirda ozet olmali."""
        satirlar = (k.KOK / "requirements.lock").read_text(encoding="utf-8").splitlines()
        paketler = [s for s in satirlar if s and not s.startswith(("#", " "))]
        ozetler = [s for s in satirlar if s.strip().startswith("--hash=sha256:")]

        self.assertGreaterEqual(len(paketler), 10)
        self.assertGreaterEqual(len(ozetler), len(paketler))

    def test_kilitte_aralik_yok(self):
        """`>=` bir kilitte olmamali; aralik birakmak kilidin amacini bozar."""
        metin = (k.KOK / "requirements.lock").read_text(encoding="utf-8")
        govde = "\n".join(s for s in metin.splitlines() if not s.startswith("#"))

        self.assertNotIn(">=", govde)
        self.assertNotIn("~=", govde)


if __name__ == "__main__":
    unittest.main()
