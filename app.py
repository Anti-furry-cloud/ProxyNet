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

import time


def main() -> int:
    """Acilis ekranini ONCE gosterir, agir ice aktarmalari SONRA yapar.

    Paketlenmis exe'de arayuz modulunu ice aktarmak (cryptography, OpenSSL,
    cekirdek) saniyeler suruyor, cunku her DLL yepyeni bir klasorden ilk kez
    yukleniyor. Eskiden acilis ekrani bunun ARDINDAN gosteriliyordu ve cift
    tiklamadan sonra ~5 saniye ekranda hicbir sey yoktu. Burada yalnizca Qt
    ve surum dosyasi yukleniyor; gerisi ekran gorundukten sonra.
    """
    from PySide6.QtWidgets import QApplication

    from apps.proxychat.splash import build_splash_screen

    app = QApplication.instance() or QApplication([])
    splash = build_splash_screen(app)
    splash.show()
    splash.raise_()
    # Asagidaki ice aktarma olay dongusunu tutacak: ekran SIMDI cizilsin.
    app.processEvents()
    gosterildi = time.monotonic()

    from apps.proxychat.ui import run_app

    return run_app(splash, gosterildi)


if __name__ == "__main__":
    raise SystemExit(main())
