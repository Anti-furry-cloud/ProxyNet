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

"""Dagitilan dosyalarin SHA-256 listesini uretir.

Dagitim zinciri korumasiz (THREAT_MODEL 5.9): dosya imzasiz ve bulut
linkiyle paylasiliyor. Imzalama ayri bir is, ama ozetleri **herkese acik
depoda** yayinlamak simdi yapilabilir: indiren kisi kendi dosyasinin
ozetini hesaplayip listeyle karsilastirabilir. Bu, degistirilmis bir
kopyayi yakalamaya yarar -- linki ele geciren biri ozet listesini de
degistiremedigi surece.

Ozet listesi ayni zamanda **kimin dagittiginin kaydi**: bir kopya baska bir
yerde baska bir ozetle dolasiyorsa, o dosya bu projeden cikmamistir.

Kullanim:
    python -m tools.surum_ozetleri dist/ProxyChat-Setup.exe dist/ProxyChat.exe
    python -m tools.surum_ozetleri --cikti SHA256SUMS.txt dist/*.exe
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

#: Buyuk dosyayi belleğe almamak icin parca parca okunur.
BLOK = 1024 * 1024


def ozet(yol: Path) -> str:
    """Dosyanin SHA-256 ozeti (kucuk harfli hex)."""
    sindirici = hashlib.sha256()
    with yol.open("rb") as dosya:
        for parca in iter(lambda: dosya.read(BLOK), b""):
            sindirici.update(parca)
    return sindirici.hexdigest()


def liste(yollar: list[Path]) -> str:
    """`sha256sum` bicimiyle uyumlu liste metni.

    Ayni bicim: `<ozet>  <dosya adi>`. Boylece indiren kisi Linux'ta
    `sha256sum -c`, Windows'ta `Get-FileHash` ile dogrulayabilir. Yol degil
    yalnizca dosya adi yazilir: liste, dosyanin bizim makinemizdeki yerini
    ele vermemeli.
    """
    satirlar = [f"{ozet(yol)}  {yol.name}" for yol in yollar]
    return "\n".join(satirlar) + "\n"


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ayristirici.add_argument("dosyalar", nargs="+", help="ozeti alinacak dosyalar")
    ayristirici.add_argument(
        "--cikti", help="listenin yazilacagi dosya (verilmezse ekrana yazilir)"
    )
    secenekler = ayristirici.parse_args(argv if argv is not None else sys.argv[1:])

    yollar = [Path(ad) for ad in secenekler.dosyalar]
    eksik = [str(yol) for yol in yollar if not yol.is_file()]
    if eksik:
        print(f"Bulunamadi: {', '.join(eksik)}", file=sys.stderr)
        return 1

    metin = liste(yollar)
    if secenekler.cikti:
        # LF satir sonu ZORUNLU. Windows'ta varsayilan CRLF yaziliyordu ve
        # `sha256sum -c` o zaman dosya adlarinin sonunda bir satir basi
        # karakteri goruyordu:
        #
        #     sha256sum: 'ProxyChat.exe'$'\r': No such file or directory
        #
        # Yani liste ekranda duzgun gorunuyor ama DOGRULAMA KOMUTU
        # CALISMIYORDU -- ve o komut, indiren kisiye VERIFYING.md'nin 3.
        # adiminda verdigimiz komutun ta kendisi. Talimati gercekten
        # calistirinca ortaya cikti (2026-09-30).
        Path(secenekler.cikti).write_text(metin, encoding="utf-8", newline="\n")
        print(f"Yazildi: {secenekler.cikti}")
    else:
        print(metin, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
