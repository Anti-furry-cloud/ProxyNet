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

"""Acilis ekrani: agir ice aktarmalardan ONCE gosterilebilsin diye ayri.

Paketlenmis exe her acilista kendini yepyeni bir klasore aciyor; o klasordeki
her DLL ilk kez yukleniyor ve virus tarayicisi her birini tariyor. Olculdu
(2026-10-02): cift tiklamadan sonra ~5 saniye boyunca ekranda HICBIR SEY
yoktu, cunku acilis ekrani arayuz modulunun butun ice aktarmalari --
cryptography, OpenSSL, cekirdek -- bittikten sonra gosteriliyordu.

Bu modul yalnizca Qt'nin cizim siniflarini ve surum dosyasini ice aktariyor.
app.py once bunu gosteriyor, agir kismi sonra yukluyor.

BU MODULE AGIR BIR ICE AKTARMA EKLEME; amacini bozar. Test kilitliyor.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from .version import APP_NAME, APP_VERSION

#: Acilis ekraninin EN AZ gorunme suresi. Eskiden bu sure pencere KURULDUKTAN
#: SONRA ayrica bekleniyordu; artik ekran ice aktarmalar sirasinda zaten
#: gorundugu icin o sure de sayiliyor.
SPLASH_DURATION_SECONDS = 2.0
#: Acilis ekrani kare; kenari bu kadar, ama ekran yuksekliginin
#: SPLASH_MAX_SCREEN_FRACTION'ini gecmez.
SPLASH_SIDE_PX = 400
SPLASH_MAX_SCREEN_FRACTION = 0.45


def _repo_root() -> Path:
    """Depo kokunu isaretli bir klasor arayarak bulur.

    Kac seviye yukari cikilacagini saymak yerine arama yapiyoruz; boylece
    bu dosya baska bir klasore tasindiginda varlik yollari sessizce
    bozulmuyor (apps/proxychat/ altina tasinirken tam bunu yasadik).
    """
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "assets").is_dir():
            return candidate
    return Path(__file__).resolve().parents[2]


def resource_path(*parts: str) -> str:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return str(Path(base, *parts))
    return str(_repo_root().joinpath(*parts))


def splash_side_for_screen(available_height: int | None) -> int:
    """Acilis karesinin kenari: SPLASH_SIDE_PX, kucuk ekranda yuksekligin bir kismi."""
    if not available_height:
        return SPLASH_SIDE_PX
    return max(160, min(SPLASH_SIDE_PX, int(available_height * SPLASH_MAX_SCREEN_FRACTION)))


def build_splash_pixmap(side: int = SPLASH_SIDE_PX) -> QPixmap:
    """Kenari ``side`` piksel olan kare acilis gorseli.

    Gorsel 1024x1024; eskiden kucultulmeden gosteriliyor ve 1080p bir ekrani
    neredeyse tamamen kapliyordu.
    """
    pixmap = QPixmap()
    for candidate in (("assets", "proxychat_splash.png"), ("proxychat_splash.png",)):
        pixmap = QPixmap(resource_path(*candidate))
        if not pixmap.isNull():
            break

    if pixmap.isNull():
        fallback = QPixmap(side, side)
        fallback.fill(QColor("#313338"))
        painter = QPainter(fallback)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("#f2f3f5"))
        font = QFont("Segoe UI")
        font.setPixelSize(max(12, side // 12))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(fallback.rect(), Qt.AlignCenter, f"{APP_NAME}\nv{APP_VERSION}")
        painter.end()
        return fallback

    # Kareye sigdir, tasani ortadan kirp: gorsel kare olmasa da cikti kare olur.
    pixmap = pixmap.scaled(side, side, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    pixmap = pixmap.copy((pixmap.width() - side) // 2, (pixmap.height() - side) // 2, side, side)

    # Alttaki ad/surum seridi karenin boyutuyla orantili.
    bar = max(28, side // 8)
    margin = max(8, side // 28)
    baseline = side - bar // 2 + bar // 6
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.fillRect(0, side - bar, side, bar, QColor(0, 0, 0, 155))
    painter.setPen(QColor("#f2f3f5"))
    title_font = QFont("Segoe UI")
    title_font.setPixelSize(max(11, bar * 9 // 20))
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.drawText(margin, baseline, APP_NAME)
    version_font = QFont("Segoe UI")
    version_font.setPixelSize(max(9, bar * 3 // 10))
    version_font.setBold(True)
    painter.setFont(version_font)
    version = f"v{APP_VERSION}"
    painter.drawText(side - margin - painter.fontMetrics().horizontalAdvance(version), baseline, version)
    painter.end()
    return pixmap


def build_splash_screen(app: QApplication) -> QSplashScreen:
    """Orta boy, ustte kilitli olmayan acilis ekrani.

    Eskiden WindowStaysOnTopHint ile aciliyordu: ekranin cogunu kaplayan
    pencere, baska bir pencereye gecilse bile onde kaliyordu.
    """
    screen = app.primaryScreen()
    side = splash_side_for_screen(screen.availableGeometry().height() if screen is not None else None)
    splash = QSplashScreen(build_splash_pixmap(side))
    splash.setEnabled(False)
    return splash


def remaining_splash_ms(shown_seconds: float) -> int:
    """Acilis ekrani en az SPLASH_DURATION_SECONDS gorunsun diye kalan bekleme.

    Ice aktarmalar ve pencere kurulumu zaten bu kadar surduyse beklenmez.
    """
    return max(0, int((SPLASH_DURATION_SECONDS - shown_seconds) * 1000))
