"""`core/` platform-notr kalsin.

Urun bugun yalnizca Windows'ta dagitiliyor (THREAT_MODEL.md 7, "Linux
destegi"). Ama bu, koda serbestce Windows'a ozgu sey koyabilecegimiz anlamina
gelmiyor: **cekirdek bugun gercekten platform-notr** ve onu oyle tutan sey
yalnizca dikkat. Aylar sonra `core/` icine bir `winreg`, bir `ctypes.windll`
ya da `C:\\` varsayan bir yol girse kimse fark etmez, ve o zaman Linux
dagitimi "paketleme + uc nokta" isi olmaktan cikip arkeoloji isine doner.

Bu testler o borcun birikmesini engelliyor. Dusen bir test "Windows'a ozgu sey
yazmayin" demiyor -- **"onu `apps/proxychat/` altina koyun"** diyor. Urunu
Windows'a baglayan uc nokta (portun ozel ayrilmasi, DPAPI ile parola saklama,
panonun gecmisten haric tutulmasi) bilerek orada duruyor.

Ayni desen `tests/test_voice_relay.py` icinde de var: orada sunucunun
`cryptography` import etmedigi AST ile kilitli.
"""

import ast
import unittest
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
CORE = KOK / "core"

#: Yalnizca Windows'ta var olan moduller. Biri `core/` icinde gorunurse
#: cekirdek artik baska bir platformda import edilemez demektir.
WINDOWS_MODULLERI = (
    "winreg",
    "msvcrt",
    "_winapi",
    "win32api",
    "win32con",
    "win32file",
    "win32event",
    "win32security",
    "pywintypes",
    "winsound",
    "ctypes.wintypes",
)

#: Windows'a ozgu cagri yollari. `ctypes` kendisi yasak degil:
#: `core/voice_opus.py` onu `ctypes.util.find_library("opus")` ile kullaniyor
#: ve o cagri Linux'ta `libopus.so`'yu bulur.
WINDOWS_NITELIKLERI = ("windll", "WinDLL", "oledll", "OleDLL", "startfile")

#: Platforma gore dallanmasina izin verilen dosyalar. Liste kisa tutuluyor:
#: amac dallanmayi yasaklamak degil, YENI bir dallanmanin goze carpmasi.
#: `core/server.py` -> SO_EXCLUSIVEADDRUSE (THREAT_MODEL.md 5.6); o secenek
#: yalnizca Windows'ta var ve `getattr` ile korunuyor.
#: `core/transport.py` -> SO_LINGER yapisinin duzeni (1.12.7): Windows'ta iki
#: u_short, Linux'ta iki int. Iki platform da karsilaniyor; tasirken karar
#: verilecek bir sey birakmiyor.
PLATFORM_DALI_OLABILEN = {"server.py", "transport.py"}


def core_dosyalari() -> list[Path]:
    return sorted(p for p in CORE.glob("*.py") if p.name != "__init__.py")


def agac(yol: Path) -> ast.Module:
    return ast.parse(yol.read_text(encoding="utf-8"))


def import_edilenler(dal: ast.Module) -> set[str]:
    moduller: set[str] = set()
    for dugum in ast.walk(dal):
        if isinstance(dugum, ast.Import):
            moduller.update(ad.name for ad in dugum.names)
        elif isinstance(dugum, ast.ImportFrom) and dugum.module:
            moduller.add(dugum.module)
    return moduller


class CekirdekPlatformNotrTests(unittest.TestCase):
    def test_dosya_bulundu(self):
        """Glob bos donerse asagidaki testler sessizce gecerdi."""
        self.assertGreater(len(core_dosyalari()), 10)

    def test_windows_modulu_import_edilmiyor(self):
        for yol in core_dosyalari():
            moduller = import_edilenler(agac(yol))
            for yasak in WINDOWS_MODULLERI:
                self.assertFalse(
                    any(m == yasak or m.startswith(yasak + ".") for m in moduller),
                    f"{yol.name} '{yasak}' import ediyor; bu kod apps/proxychat/ altina ait",
                )

    def test_windows_cagrisi_yok(self):
        """`ctypes.windll`, `os.startfile` gibi yollar."""
        for yol in core_dosyalari():
            for dugum in ast.walk(agac(yol)):
                if isinstance(dugum, ast.Attribute) and dugum.attr in WINDOWS_NITELIKLERI:
                    self.fail(
                        f"{yol.name}:{dugum.lineno} '{dugum.attr}' kullaniyor; "
                        "bu kod apps/proxychat/ altina ait"
                    )

    def test_apps_import_edilmiyor(self):
        """Katman yonu: arayuz cekirdegi kullanir, tersi olmaz.

        Cekirdek `apps/`'a uzanirsa Qt'ye ve Windows'a dolayli olarak bagimli
        hale gelir; testlerin pencere acmadan calismasi da biter.
        """
        for yol in core_dosyalari():
            for modul in import_edilenler(agac(yol)):
                self.assertFalse(
                    modul == "apps" or modul.startswith("apps."),
                    f"{yol.name} '{modul}' import ediyor; cekirdek arayuzu bilmemeli",
                )

    def test_surucu_harfi_yazilmamis(self):
        """`C:\\...` gibi bir yol, cekirdegi tek bir makineye baglar."""
        for yol in core_dosyalari():
            for dugum in ast.walk(agac(yol)):
                if isinstance(dugum, ast.Constant) and isinstance(dugum.value, str):
                    metin = dugum.value
                    if len(metin) >= 3 and metin[1:3] in (":\\", ":/") and metin[0].isalpha():
                        self.fail(f"{yol.name}:{dugum.lineno} surucu harfli yol: {metin!r}")

    def test_platform_dallari_bilinen_dosyalarda(self):
        """Yeni bir platform dali sessizce girmesin.

        Dallanmak yasak degil -- `core/server.py` bunu bilerek yapiyor. Amac,
        yeni bir dosyanin listeye eklenmeden dallanmamasi: eklerken "bu
        guvence obur platformda nasil degisiyor?" sorusu sorulmus olur.
        """
        dallananlar = set()
        for yol in core_dosyalari():
            for dugum in ast.walk(agac(yol)):
                if isinstance(dugum, ast.Attribute) and dugum.attr == "platform":
                    dallananlar.add(yol.name)
                elif isinstance(dugum, ast.Attribute) and dugum.attr == "system":
                    dallananlar.add(yol.name)

        self.assertEqual(
            dallananlar,
            PLATFORM_DALI_OLABILEN,
            "core/ icindeki platform dallari degisti; THREAT_MODEL.md 7'deki "
            "'Linux destegi' satirini da guncelle",
        )

    def test_windows_dali_korumali(self):
        """`SO_EXCLUSIVEADDRUSE` yalnizca Windows'ta var; `getattr` ile alinmali.

        Dogrudan `socket.SO_EXCLUSIVEADDRUSE` yazmak Linux'ta `AttributeError`
        ile sunucuyu hic acilmaz hale getirirdi.
        """
        kaynak = (CORE / "server.py").read_text(encoding="utf-8")

        self.assertIn('getattr(socket, "SO_EXCLUSIVEADDRUSE", None)', kaynak)
        self.assertNotIn("socket.SO_EXCLUSIVEADDRUSE", kaynak)


if __name__ == "__main__":
    unittest.main()
