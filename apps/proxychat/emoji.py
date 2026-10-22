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

"""Emoji: yalnizca emojiden olusan mesajin buyuk gosterilmesi ve secici listesi.

Disaridan GIF istendi; reddedildi, cunku GIF uc ayri yuzey aciyor: goruntu
cozucu (uzaktan kod calistirma acigi sinifi), isaretlemeye izin vermek
(`QTextBrowser` HTML render ediyor; kacirilmamis bir `<img src="\\\\makine\\pay">`
Windows'ta SMB baglantisi kurup NTLM kimligini sizdirir) ve dosya aktarma
(icerik siniri 8 KiB, bir GIF 100 KB'nin uzerinde).

Emoji bunlarin hicbirini gerektirmiyor: aga giden sey yine duz metin, yalnizca
**gosterim** degisiyor. Sifreleme, ileri gizlilik ve paket bicimi etkilenmiyor.

Burada Qt yok: mantik ayri tutuldu ki pencere acmadan sinanabilsin.
"""

from __future__ import annotations

#: Emoji sayilan kod noktasi araliklari. Genis tutuldu ama metin
#: noktalama isaretleri disarida: "..." ya da "->" buyuk gorunmemeli.
_RANGES = (
    (0x1F000, 0x1FAFF),  # kartlar, bayrak harfleri, suratlar, nesneler
    (0x2600, 0x27BF),    # cesitli semboller ve dingbat
    (0x2B00, 0x2BFF),    # yildiz ve oklar
    (0xFE00, 0xFE0F),    # varyasyon seciciler
    (0x200D, 0x200D),    # sifir genislikli birlestirici (ZWJ)
)

#: Kendi basina emoji sayilmayan, yalnizca baska bir emojiye eklenenler.
#: Bunlardan ibaret bir metin emoji degildir.
_MODIFIERS = frozenset({0x200D} | set(range(0xFE00, 0xFE10)) | set(range(0x1F3FB, 0x1F400)))

#: Buyuk gosterimin ust siniri. Bunun uzeri duvar gibi gorunur ve sohbeti
#: okunmaz yapar; Discord da bir yerde kesiyor.
MAX_LARGE = 8

#: Kac emoji varsa o kadar buyuk. Tek emoji en buyugu.
_SIZES = ((1, 30), (3, 24), (MAX_LARGE, 18))

#: Secicide gosterilen emojiler. Uzun bir liste degil, gercekten kullanilanlar;
#: satir satir gruplanmis halde arayuze gidiyor.
PICKER_ROWS = (
    "😀 😄 😂 🙂 😉 😍 😎 🤔",
    "😅 😭 😡 😱 🥱 🤝 🙏 👋",
    "👍 👎 👌 💪 🔥 ✨ 💯 ✅",
    "❌ ⚠️ 🎮 🎧 🎵 🍕 ☕ 🍺",
    "❤️ 💔 🎉 🎁 ⭐ 🌙 ☀️ 🌧️",
)


def _is_emoji_char(ch: str) -> bool:
    kod = ord(ch)
    return any(bas <= kod <= son for bas, son in _RANGES)


def emoji_count(text: str) -> int:
    """Metindeki emoji sayisi; birlestirici ve ton degistiriciler sayilmaz.

    Bayrak ve aile gibi ZWJ ile birlesen diziler birden fazla sayilir; sonuc
    yalnizca yazi boyutunu secmekte kullanildigi icin bu yeterli.
    """
    return sum(1 for ch in text if _is_emoji_char(ch) and ord(ch) not in _MODIFIERS)


def is_emoji_only(text: str) -> bool:
    """Metin bosluklar disinda yalnizca emojiden mi olusuyor?"""
    govde = "".join(text.split())
    if not govde:
        return False
    if not all(_is_emoji_char(ch) for ch in govde):
        return False
    return emoji_count(govde) > 0


def display_size(text: str) -> int | None:
    """Yalnizca emojiden olusan kisa mesajin punto'su; degilse None.

    None donmesi "normal mesaj gibi goster" demek. Cagiran bu ayrimi
    bilmek zorunda degil, yalnizca donen degeri kullanir.
    """
    if not is_emoji_only(text):
        return None
    adet = emoji_count(text)
    if adet > MAX_LARGE:
        return None
    for sinir, punto in _SIZES:
        if adet <= sinir:
            return punto
    return None


def picker_emojis() -> list[str]:
    """Secicideki butun emojiler, satir siralamasiyla duz bir liste."""
    return [e for satir in PICKER_ROWS for e in satir.split()]
