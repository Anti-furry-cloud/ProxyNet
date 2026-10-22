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

"""Rastgele kelimelerden oda parolasi uretir.

Neden kelime: parola yuz yuze soylenerek ya da telefonda okunarak paylasilmali
(THREAT_MODEL.md 3. bolum). "kavanoz-bulut-terlik-fener-deniz" soylemesi,
ezberlemesi ve dogru yazmasi kolay, tahmin etmesi zor bir paroladir.

Guc listenin buyuklugunden gelir, kelimelerin gizliliginden degil: saldirgan
listeyi bilse bile her kelime log2(liste boyutu) bit belirsizlik ekler. Kelime
sayisi bu yuzden sabit degil, listeye gore hesaplanir.

Rastgelelik ``secrets`` modulunden gelir; ``random`` tahmin edilebilir oldugu
icin parola uretiminde kullanilmamalidir.
"""

from __future__ import annotations

import math
import secrets
from collections.abc import Sequence

#: Uretilen parolanin en az kac bit tahmin edilemezlik tasiyacagi.
#: 50 bit, anahtar turetmenin yavasligiyla birlikte cevrimdisi tahmin
#: saldirisini ev donanimi icin anlamsiz kilar; uzun parolayi yuz yuze
#: soylemek de hala makul kalir.
MIN_ENTROPY_BITS = 50

SEPARATOR = "-"


def words_needed(list_size: int, min_bits: float = MIN_ENTROPY_BITS) -> int:
    """Hedef guce ulasmak icin kac kelime gerektigi."""
    if list_size < 2:
        raise ValueError("kelime listesinde en az iki farkli kelime olmali")
    return math.ceil(min_bits / math.log2(list_size))


def entropy_bits(list_size: int, word_count: int) -> float:
    return word_count * math.log2(list_size)


def generate_passphrase(words: Sequence[str], min_bits: float = MIN_ENTROPY_BITS) -> str:
    # Tekrar eden kelime listeyi buyuk gosterip gucu oldugundan fazla
    # hesaplatirdi; hesap tekillestirilmis liste uzerinden yapilir.
    unique = sorted(set(words))
    count = words_needed(len(unique), min_bits)
    return SEPARATOR.join(secrets.choice(unique) for _ in range(count))
