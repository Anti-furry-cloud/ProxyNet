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

"""Uygulamanin adi ve surumu -- TEK KAYNAK.

Ayri ve hafif bir dosyada, cunku acilis ekrani bunlari agir ice
aktarmalardan (cryptography, cekirdek) ONCE gosteriyor (bkz. splash.py).

Bu dosyayi metin olarak okuyanlar var; sabit adini ya da bicimini
degistirirsen onlari da degistir (testler ikisini de kontrol ediyor):

  - build_installer.ps1       -> kurulum dosyasinin kayit defteri surumu
  - tools/derleme_kunyesi.py  -> derleme kunyesindeki surum
"""

APP_NAME = "ProxyChat"
APP_VERSION = "1.13.0"
