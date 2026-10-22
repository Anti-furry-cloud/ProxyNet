"""Her kaynak dosya GPL basligini tasimali.

Lisans basligi projenin sahipligini ve kosullarini dosyanin kendisine
yaziyor: kod kopyalanip baska bir yere konsa bile kimin yazdigi ve hangi
lisansla dagitildigi orada kaliyor. Bu test, yeni dosya eklerken baslik
koymayi unutmayi yakalar.

Testler bu kuralin disinda: dagitilan pakete girmiyorlar.
"""

import unittest
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent

#: Basligin tasimasi gereken satirlar.
ZORUNLU = (
    "Copyright (C) 2026 Anti-furry-cloud",
    "GNU General Public License",
)

#: Basligin arandigi klasorler. `tests/` disarida.
KLASORLER = ("core", "tools", "apps")


def kaynak_dosyalar():
    for klasor in KLASORLER:
        for yol in sorted((KOK / klasor).rglob("*.py")):
            if "__pycache__" in yol.parts:
                continue
            yield yol


class LisansBasligiTests(unittest.TestCase):
    def test_her_kaynak_dosyada_baslik_var(self):
        eksik = []
        for yol in kaynak_dosyalar():
            bas = yol.read_text(encoding="utf-8")[:1200]
            if not all(satir in bas for satir in ZORUNLU):
                eksik.append(str(yol.relative_to(KOK)))

        self.assertEqual(eksik, [], f"lisans basligi eksik: {eksik}")

    def test_taranan_dosya_var(self):
        """Yol yanlissa test sessizce gecmesin."""
        self.assertGreater(len(list(kaynak_dosyalar())), 20)


if __name__ == "__main__":
    unittest.main()


class UcuncuPartiAtifTests(unittest.TestCase):
    """Pakete giren ucuncu parti bilesenler yazili olsun.

    libopus BSD 3 madde ile geliyor ve o lisans, IKILI dagitimin lisans
    metnini de birlikte vermesini sart kosuyor. DLL 1.12.2'de exe'nin icine
    girdi, yani artik dagittigimiz dosyanin parcasi -- bu yuzden atif dosyasi
    bir tercih degil, yukumluluk.

    Ozet de kilitli: THIRD-PARTY.md'de yazan deger, derlemede paketlenen
    dosyanin ozetiyle ayni olmali. Ayrisirsa, belge baska bir ikiliyi
    anlatiyor demektir.
    """

    def _metin(self, ad: str) -> str:
        return (KOK / ad).read_text(encoding="utf-8")

    def test_dosyalar_var(self):
        for ad in ("THIRD-PARTY.md", "THIRD-PARTY.en.md"):
            self.assertTrue((KOK / ad).is_file(), ad)

    def test_pakete_giren_bilesenler_yazili(self):
        for ad in ("THIRD-PARTY.md", "THIRD-PARTY.en.md"):
            metin = self._metin(ad)
            for bilesen in ("libopus", "PySide6", "cryptography"):
                self.assertIn(bilesen, metin, f"{bilesen} {ad} icinde yok")

    def test_bsd_lisans_metni_duruyor(self):
        """Kosullar ve sorumluluk reddi birebir bulunmali."""
        for ad in ("THIRD-PARTY.md", "THIRD-PARTY.en.md"):
            metin = self._metin(ad)
            self.assertIn("Redistribution and use in source and binary forms", metin, ad)
            self.assertIn("THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS", metin, ad)

    def test_ozet_paketlenen_dll_ile_ayni(self):
        """DLL elde yoksa atlanir; varsa belge onu anlatmali."""
        import hashlib
        import os

        yol = os.environ.get("PROXYCHAT_OPUS_DLL") or str(KOK / "dist" / "libopus.dll")
        if not Path(yol).is_file():
            self.skipTest("libopus.dll bu makinede yok")

        ozet = hashlib.sha256(Path(yol).read_bytes()).hexdigest()

        for ad in ("THIRD-PARTY.md", "THIRD-PARTY.en.md"):
            self.assertIn(ozet, self._metin(ad), f"{ad} baska bir ikiliyi anlatiyor")
