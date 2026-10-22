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

"""Dil kataloglari.

Her modul uc sey tanimlar: ``NAME`` (dilin kendi dilindeki adi), ``TEXTS``
(anahtar -> metin) ve ``WORDS`` (parola uretimi icin kelime listesi).
Ingilizce (``en``) referans katalogtur; baska bir dilde eksik kalan anahtar ya
da kelime listesi Ingilizceye duser.

Kelime listeleri yalnizca kucuk ASCII harflerden olusur: parola baska dilde
klavyesi olan bir arkadasa da yazdirilabilmeli. Tekrarsizlik ve buyukluk
tests/test_passphrase.py'de denetlenir.

Moduller burada acikca import edilir: PyInstaller dinamik import'lari
goremez, boylece derlemeye her dil kendiliginden girer.
"""

from . import en, tr

CATALOGS = {
    "en": en,
    "tr": tr,
}
