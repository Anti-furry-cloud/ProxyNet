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

"""ProxyChat arayuz metinleri ve dil secimi.

Metinler dil basina bir modulde durur (``locales/``). Yeni bir dil eklemek
icin ``locales/en.py`` kopyalanir, degerler cevrilir ve dil
``locales/__init__.py`` icindeki ``CATALOGS``'a yazilir. Anahtar kumesinin ve
``{yer tutucularin}`` Ingilizceyle birebir ayni kalmasini tests/test_i18n.py
denetler.

Gecerli dil modul duzeyinde tutulur: uygulamada tek pencere var ve dil
degistiginde pencere butun sayfalara ``retranslate()`` cagirir.
"""

from __future__ import annotations

from typing import Any

from .locales import CATALOGS

#: Ilk acilista ve taninmayan bir kayitli degerde kullanilan dil.
DEFAULT_LANGUAGE = "en"

#: Kod -> dilin kendi dilindeki adi. Secim kutusunda bu sirayla gorunur.
LANGUAGES: dict[str, str] = {code: module.NAME for code, module in CATALOGS.items()}

_current = DEFAULT_LANGUAGE


def normalize_language(code: Any) -> str:
    """Bilinen bir dil koduysa kendisini, degilse varsayilan dili dondurur."""
    return code if isinstance(code, str) and code in CATALOGS else DEFAULT_LANGUAGE


def set_language(code: Any) -> str:
    """Gecerli dili degistirir ve gercekten uygulanan kodu dondurur."""
    global _current
    _current = normalize_language(code)
    return _current


def current_language() -> str:
    return _current


def has_text(key: str) -> bool:
    """Anahtar referans (Ingilizce) katalogda var mi?"""
    return key in CATALOGS[DEFAULT_LANGUAGE].TEXTS


def passphrase_words() -> tuple[str, ...]:
    """Parola uretimi icin gecerli dilin kelime listesi; yoksa Ingilizcesi."""
    words = getattr(CATALOGS[_current], "WORDS", None)
    return words if words else CATALOGS[DEFAULT_LANGUAGE].WORDS


def t(key: str, **values: Any) -> str:
    """Anahtarin gecerli dildeki metni.

    Gecerli dilde eksikse Ingilizceye, orada da yoksa anahtarin kendisine
    duser: eksik bir ceviri arayuzu bos birakmamali.
    """
    text = CATALOGS[_current].TEXTS.get(key)
    if text is None:
        text = CATALOGS[DEFAULT_LANGUAGE].TEXTS.get(key, key)
    return text.format(**values) if values else text
