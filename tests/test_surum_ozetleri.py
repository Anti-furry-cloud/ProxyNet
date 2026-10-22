"""Surum ozetleri araci (tools/surum_ozetleri.py)."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from tools import surum_ozetleri as s


class OzetTests(unittest.TestCase):
    def setUp(self):
        self.klasor = Path(tempfile.mkdtemp())

    def dosya(self, ad: str, icerik: bytes) -> Path:
        yol = self.klasor / ad
        yol.write_bytes(icerik)
        return yol

    def test_ozet_bilinen_degerle_ayni(self):
        yol = self.dosya("a.bin", b"proxychat")

        self.assertEqual(s.ozet(yol), hashlib.sha256(b"proxychat").hexdigest())

    def test_buyuk_dosya_parca_parca_okunuyor(self):
        icerik = b"x" * (s.BLOK * 2 + 17)
        yol = self.dosya("buyuk.bin", icerik)

        self.assertEqual(s.ozet(yol), hashlib.sha256(icerik).hexdigest())

    def test_liste_sha256sum_bicimiyle_uyumlu(self):
        ilk = self.dosya("ProxyChat-Setup.exe", b"kurulum")
        ikinci = self.dosya("ProxyChat.exe", b"program")

        metin = s.liste([ilk, ikinci])

        satirlar = metin.splitlines()
        self.assertEqual(len(satirlar), 2)
        for satir, yol in zip(satirlar, (ilk, ikinci)):
            imza, ad = satir.split("  ")
            self.assertEqual(imza, s.ozet(yol))
            self.assertEqual(ad, yol.name)
        self.assertTrue(metin.endswith("\n"))

    def test_listede_makinedeki_yol_yok(self):
        """Liste dosyanin bizde nerede durdugunu ele vermemeli."""
        yol = self.dosya("ProxyChat.exe", b"program")

        metin = s.liste([yol])

        self.assertNotIn(str(self.klasor), metin)

    def test_cikti_dosyaya_yaziliyor(self):
        yol = self.dosya("ProxyChat.exe", b"program")
        cikti = self.klasor / "SHA256SUMS.txt"

        kod = s.main(["--cikti", str(cikti), str(yol)])

        self.assertEqual(kod, 0)
        self.assertEqual(cikti.read_text(encoding="utf-8"), s.liste([yol]))

    def test_olmayan_dosya_hata_veriyor(self):
        self.assertEqual(s.main([str(self.klasor / "yok.exe")]), 1)



class SatirSonuTests(unittest.TestCase):
    """Liste LF ile yazilmali; CRLF `sha256sum -c`'yi bozuyor.

    Bulunma hikayesi (2026-09-30): VERIFYING.md'ye indiren kisi icin uc
    adimlik bir talimat yazdim, sonra onu gercekten calistirdim. Ilk iki
    adim gecti, ucuncusu duzgun gorunen bir listeyle sunu verdi:

        sha256sum: 'ProxyChat.exe'$'\r': No such file or directory

    Windows'ta write_text varsayilan olarak CRLF yaziyordu ve `sha256sum -c`
    dosya adinin sonundaki satir basi karakterini adin parcasi sayiyordu.
    Liste ekranda dogru, komut calismiyor -- yani hata yalnizca talimati
    uygulayinca goruluyor.
    """

    def setUp(self):
        self.klasor = Path(tempfile.mkdtemp())

    def test_cikti_lf_ile_yaziliyor(self):
        hedef = self.klasor / "SHA256SUMS.txt"
        dosya = self.klasor / "ProxyChat.exe"
        dosya.write_bytes(b"program")

        s.main(["--cikti", str(hedef), str(dosya)])

        ham = hedef.read_bytes()
        self.assertNotIn(b"\r\n", ham, "CRLF yazilmis; sha256sum -c bunu okuyamaz")
        self.assertIn(b"\n", ham)

    def test_dosya_adinda_satir_basi_yok(self):
        """Adin sonuna takilan \r, `sha256sum -c`'de 'No such file' oluyor."""
        hedef = self.klasor / "SHA256SUMS.txt"
        dosya = self.klasor / "ProxyChat.exe"
        dosya.write_bytes(b"program")

        s.main(["--cikti", str(hedef), str(dosya)])

        for satir in hedef.read_bytes().split(b"\n"):
            self.assertFalse(satir.endswith(b"\r"), satir)

if __name__ == "__main__":
    unittest.main()
