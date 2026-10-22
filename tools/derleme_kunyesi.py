# ProxyChat — kendi sunucunda, uçtan uca şifreli sohbet
# Copyright (C) 2026 Anti-furry-cloud
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Derleme kunyesi: bu exe'nin hangi girdilerden ciktigini yazar.

Yayinlanan bir SHA-256 tek basina "bu dosya bozulmamis" der, "bu dosya sizin
soylediginiz kaynaktan cikmis" demez. Aradaki farki kapatan sey girdilerin de
kayda gecmesi: hangi commit, hangi Python, hangi PyInstaller, hangi paketler
ve hangi ozetlerle.

Bu, imzanin yerini TUTMAZ. Kunyeyi de biz yaziyoruz; kotu niyetli bir dagitici
ikisini birden uydurabilir. Yaptigi sey, **iyi niyetli** bir dogrulayicinin
ayni exe'yi yeniden uretebilmesini mumkun kilmak -- derleme yeniden
uretilebilir oldugu icin (THREAT_MODEL.md 5.9, 8-A) o kisi cikan ozeti
buradakiyle karsilastirabilir.

Kullanim:

    python -m tools.derleme_kunyesi                 # ekrana
    python -m tools.derleme_kunyesi --cikti dist/DERLEME-KUNYESI.txt
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent

#: Kunyeye ozeti girecek ciktilar. Olmayan dosya sessizce atlanir; kunye
#: yalnizca exe icin de uretilebilsin diye.
CIKTILAR = ("dist/ProxyChat.exe", "dist/ProxyChat-Setup.exe")

BLOK = 1024 * 1024


def ozet(yol: Path) -> str:
    sha = hashlib.sha256()
    with yol.open("rb") as f:
        while parca := f.read(BLOK):
            sha.update(parca)
    return sha.hexdigest()


def komut(*argv: str) -> str | None:
    """Komutu calistirir; yoksa ya da patlarsa None doner."""
    try:
        sonuc = subprocess.run(argv, cwd=KOK, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if sonuc.returncode != 0:
        return None
    return sonuc.stdout.strip() or None


def surum() -> str:
    """apps/proxychat/version.py'deki APP_VERSION.

    Bulunamazsa HATA verir. Eskiden sessizce "?" donuyordu ve kunye "Surum: ?"
    yaziyordu; bunu sinayan test de kunyede "ne donduyse o" yaziyor mu diye
    baktigi icin geciyordu. Surum dosyasi tasindiginda kimse fark etmezdi.
    """
    yol = KOK / "apps" / "proxychat" / "version.py"
    metin = yol.read_text(encoding="utf-8")
    # Satir basina bagli: version.py'nin aciklama metni bu sabitten soz
    # ediyor; oraya ornek bir satir yazilirsa ilk eslesen o olurdu.
    eslesme = re.search(r'(?m)^APP_VERSION\s*=\s*"([^"]+)"', metin)
    if not eslesme:
        raise ValueError(f"APP_VERSION okunamadi: {yol}")
    return eslesme.group(1)


def paket_surumu(ad: str) -> str:
    try:
        from importlib.metadata import version

        return version(ad)
    except Exception:
        return "?"


def kilit_satirlari() -> list[str]:
    """requirements.lock icindeki paket==surum satirlari, ozetin ilk 12'siyle."""
    yol = KOK / "requirements.lock"
    if not yol.is_file():
        return ["  (requirements.lock yok)"]
    satirlar: list[str] = []
    paket = None
    for ham in yol.read_text(encoding="utf-8").splitlines():
        s = ham.strip()
        if not s or s.startswith("#"):
            continue
        if "==" in s:
            paket = s.split("\\")[0].strip()
        elif s.startswith("--hash=sha256:") and paket:
            satirlar.append(f"  {paket:<34} {s.removeprefix('--hash=sha256:')[:16]}...")
            paket = None
    return satirlar or ["  (kilit bos)"]


def kunye() -> str:
    commit = komut("git", "rev-parse", "HEAD") or "?"
    kisa = komut("git", "rev-parse", "--short", "HEAD") or "?"
    # build_exe.ps1 ortamda verilen degeri koruyor (yayin deposundan yeniden
    # uretim icin); kunye de derlemede gercekten kullanilan degeri yazsin.
    ortamdaki = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
    epoch = ortamdaki if ortamdaki.isdigit() else komut("git", "log", "-1", "--format=%ct")
    kirli = komut("git", "status", "--porcelain")
    nsis = komut("makensis", "/VERSION") or komut(
        r"C:\Program Files (x86)\NSIS\makensis.exe", "/VERSION"
    )

    sat = [
        "ProxyChat derleme kunyesi",
        "=" * 60,
        "",
        f"Surum            : {surum()}",
        f"Commit           : {commit}",
        f"Calisma agaci    : {'KIRLI -- bu exe hicbir commit e karsilik gelmiyor' if kirli else 'temiz'}",
        f"SOURCE_DATE_EPOCH: {epoch or '(git yok)'}",
        f"Kunye zamani     : {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%SZ}",
        "",
        "Arac zinciri",
        "-" * 60,
        f"  Python          {'.'.join(map(str, sys.version_info[:3]))}",
        f"  PyInstaller     {paket_surumu('pyinstaller')}",
        f"  hooks-contrib   {paket_surumu('pyinstaller-hooks-contrib')}",
        f"  NSIS            {nsis or '(bulunamadi)'}",
        "",
        "Kilitli paketler (requirements.lock)",
        "-" * 60,
        *kilit_satirlari(),
        "",
        "Ses kodegi",
        "-" * 60,
    ]

    dll = KOK / "dist" / "libopus.dll"
    if dll.is_file():
        sat += [
            f"  libopus.dll     {ozet(dll)}",
            "  Kaynak, derleme secenekleri ve lisans: THIRD-PARTY.md",
        ]
    else:
        sat.append("  (dist/libopus.dll yok -- bu exe Opus'suz olabilir)")

    sat += ["", "Ciktilar", "-" * 60]
    bulunan = False
    for bagil in CIKTILAR:
        yol = KOK / bagil
        if yol.is_file():
            bulunan = True
            sat.append(f"  {ozet(yol)}  {yol.name}")
    if not bulunan:
        sat.append("  (dist/ bos -- once derle)")

    sat += [
        "",
        "-" * 60,
        "Bu kunye imza DEGILDIR. Derlemenin yeniden uretilebilir olmasi,",
        "yukaridaki girdilerle derleyen birinin ayni ozetleri elde etmesini",
        "saglar; kunyenin isi o karsilastirmayi mumkun kilmak.",
        "Ayrinti: THREAT_MODEL.md 5.9",
        "",
    ]
    return "\n".join(sat)


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(description="Derleme kunyesi uretir.")
    ayristirici.add_argument("--cikti", help="yazilacak dosya; verilmezse ekrana")
    secenek = ayristirici.parse_args(argv)

    metin = kunye()
    if secenek.cikti:
        yol = Path(secenek.cikti)
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_text(metin, encoding="utf-8", newline="\n")
        print(f"yazildi: {yol}")
    else:
        print(metin)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
