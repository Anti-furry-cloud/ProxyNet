"""Acilis: ekran agir ice aktarmalardan ONCE gorunsun.

Paketlenmis exe'de cift tiklamadan sonra ~5 saniye ekranda hicbir sey
yoktu: acilis ekrani, arayuz modulunun butun ice aktarmalari -- cryptography,
OpenSSL, cekirdek -- bittikten sonra gosteriliyordu. Ustune, ekranin sabit
2 saniyesi pencere kurulduktan SONRA ayrica bekleniyordu.

Bu testler sunlari kilitliyor:

- splash.py hafif kaliyor (yoksa kazanc sessizce kaybolur);
- app.py arayuz modulunu ekran gosterildikten SONRA ice aktariyor;
- 2 saniye "en az gorunme suresi", kurulumun ustune eklenen bekleme degil;
- surumun tek kaynagi version.py, ve onu metin olarak okuyan kurulum betigi
  gercekten oradan okuyor.
"""

import ast
import re
import subprocess
import sys
import unittest
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]

#: Acilis ekranindan once YUKLENMEMESI gereken agir paketler.
AGIR = ("cryptography", "core", "apps.proxychat.ui", "apps.proxychat.voice", "apps.proxychat.settings")


def _yuklenenler(kod: str) -> list[str]:
    """Temiz bir surecte `kod`u calistirip yuklenen agir modulleri dondurur."""
    betik = (
        f"import sys\n{kod}\n"
        f"agir = {AGIR!r}\n"
        "print('\\n'.join(sorted(m for m in sys.modules "
        "if any(m == a or m.startswith(a + '.') for a in agir))))\n"
    )
    sonuc = subprocess.run(
        [sys.executable, "-c", betik], cwd=KOK, capture_output=True, text=True, check=True
    )
    return [s for s in sonuc.stdout.splitlines() if s]


class AcilisEkraniHafifTests(unittest.TestCase):
    def test_splash_modulu_agir_hicbir_sey_yuklemez(self):
        """Bu module agir bir ice aktarma eklenirse acilis ekrani yine gec gelir."""
        self.assertEqual(_yuklenenler("import apps.proxychat.splash"), [])

    def test_app_py_ice_aktarilinca_arayuz_yuklenmez(self):
        """Arayuz ancak main() icinde, ekran gosterildikten sonra yuklenmeli."""
        self.assertEqual(_yuklenenler("import app"), [])

    def test_main_once_ekrani_gosterir_sonra_arayuzu_yukler(self):
        agac = ast.parse((KOK / "app.py").read_text(encoding="utf-8"))
        main = next(d for d in agac.body if isinstance(d, ast.FunctionDef) and d.name == "main")
        sira = []
        for dugum in ast.walk(main):
            if isinstance(dugum, ast.ImportFrom) and dugum.module == "apps.proxychat.ui":
                sira.append(("ui", dugum.lineno))
            if isinstance(dugum, ast.Call) and getattr(dugum.func, "attr", None) == "show":
                sira.append(("show", dugum.lineno))
            if isinstance(dugum, ast.Call) and getattr(dugum.func, "attr", None) == "processEvents":
                sira.append(("processEvents", dugum.lineno))
        # Her turun ILK gectigi satir: arayuz iki kez ice aktarilirsa (biri
        # erken) dict() sonuncusunu tutar ve erken olani gormezdi -- bu
        # testin ilk hali tam boyle kaciriyordu (kasten bozulan kodla denendi).
        satir = {}
        for tur, no in sira:
            satir[tur] = min(no, satir.get(tur, no))
        self.assertLess(satir["show"], satir["ui"], "ekran arayuz yuklenmeden ONCE gosterilmeli")
        self.assertLess(satir["processEvents"], satir["ui"], "ekran yuklemeden once CIZILMELI")


class EnAzGorunmeTests(unittest.TestCase):
    """2 saniye kurulumun ustune eklenmiyor; toplam en az gorunme suresi."""

    def test_kurulum_kisaysa_kalan_bekleniyor(self):
        from apps.proxychat.splash import SPLASH_DURATION_SECONDS, remaining_splash_ms

        self.assertEqual(remaining_splash_ms(0.5), int((SPLASH_DURATION_SECONDS - 0.5) * 1000))

    def test_kurulum_zaten_uzun_surduyse_beklenmez(self):
        from apps.proxychat.splash import remaining_splash_ms

        self.assertEqual(remaining_splash_ms(3.0), 0)
        self.assertEqual(remaining_splash_ms(2.0), 0)

    def test_run_app_sabit_degil_kalan_sureyi_bekler(self):
        """Eskisi `singleShot(SPLASH_DURATION_SECONDS * 1000, ...)` idi."""
        kaynak = (KOK / "apps" / "proxychat" / "ui.py").read_text(encoding="utf-8")
        govde = kaynak[kaynak.index("def run_app"):]
        self.assertIn("remaining_splash_ms(", govde)
        self.assertNotIn("SPLASH_DURATION_SECONDS * 1000", govde)


class SurumKaynagiTests(unittest.TestCase):
    def test_arayuz_surumu_version_py_den_aliyor(self):
        from apps.proxychat import ui, version

        self.assertEqual(ui.APP_VERSION, version.APP_VERSION)
        self.assertEqual(ui.APP_NAME, version.APP_NAME)
        self.assertNotRegex(
            (KOK / "apps" / "proxychat" / "ui.py").read_text(encoding="utf-8"),
            r'(?m)^APP_VERSION\s*=',
            "ikinci bir surum tanimi kaymaya davetiye",
        )

    def test_kurulum_betigi_surumu_version_py_den_okur(self):
        """build_installer.ps1 surumu dosyayi METIN olarak okuyor.

        Okudugu yol ve desen gercekten version.py'deki degeri vermeli; yoksa
        kurulum dosyasi kayit defterine "0.0.0" yazar ve kimse fark etmez.
        """
        from apps.proxychat.version import APP_VERSION

        betik = (KOK / "build_installer.ps1").read_text(encoding="utf-8")
        yol = re.search(r'Join-Path \$PSScriptRoot "(apps\\proxychat\\[^"]+)"', betik).group(1)
        desen = re.search(r"-notmatch '([^']+)'", betik).group(1)
        self.assertEqual(yol, r"apps\proxychat\version.py")
        hedef = (KOK / yol.replace("\\", "/")).read_text(encoding="utf-8")
        self.assertEqual(re.search(desen, hedef).group(1), APP_VERSION)

        # Desen satir basina bagli: aciklamadaki ornek satir surum sanilmasin.
        ornekli = '"""Ornek:\n\n    APP_VERSION = "9.9.9"\n"""\n\nAPP_VERSION = "1.0.0"\n'
        self.assertEqual(re.search(desen, ornekli).group(1), "1.0.0")


if __name__ == "__main__":
    unittest.main()
