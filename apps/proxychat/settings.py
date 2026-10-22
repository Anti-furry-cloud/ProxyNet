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

"""ProxyChat baglanti ayarlarinin saklanmasi.

Burasi bilerek uygulama katmanindadir: core/ diske hicbir sey yazmaz
(bkz. THREAT_MODEL.md ilke 2).

Parola islemi ozel: THREAT_MODEL.md ilke 4 "anahtar malzemesi diske duz
yazilmaz, kolayliklar ancak isletim sistemi korumasiyla ve istege bagli
olarak eklenir" diyor. Bu yuzden:

- Parola varsayilan olarak SAKLANMAZ; kullanici acikca kutuyu isaretlemeli.
- Saklandiginda Windows DPAPI ile sifrelenir. Cozulmesi ayni Windows
  kullanici hesabini gerektirir; makinedeki baska bir hesap ya da kopyalanan
  bir registry dosyasi ise yaramaz.
- Kutu isaretli degilse daha once saklanmis parola da silinir.
"""

from __future__ import annotations

import base64
import ctypes
import sys
from ctypes import wintypes
from typing import Any

from PySide6.QtCore import QSettings


ORGANIZATION = "ProxyNet"
APPLICATION = "ProxyChat"

#: DPAPI'ye verilen ek gizli deger. Ayni makinedeki baska bir programin
#: blobu sifresini cozmesini zorlastirir.
_ENTROPY = b"proxychat-room-password-v1"

_CRYPTPROTECT_UI_FORBIDDEN = 0x01


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _is_windows() -> bool:
    return sys.platform == "win32"


def _make_blob(data: bytes) -> tuple[_DataBlob, Any]:
    """Blob ile birlikte tamponu da dondurur; tampon canli kalmali."""
    buffer = ctypes.create_string_buffer(data, len(data))
    blob = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    return blob, buffer


def _read_blob(blob: _DataBlob) -> bytes:
    buffer = ctypes.create_string_buffer(blob.cbData)
    ctypes.memmove(buffer, blob.pbData, blob.cbData)
    return buffer.raw


def protect(secret: str) -> str | None:
    """Metni DPAPI ile sifreleyip base64 olarak dondurur.

    Basarisiz olursa None doner -- cagiran taraf o zaman hicbir sey saklamaz.
    Sessizce duz metne dusmek kabul edilemez.
    """
    if not secret or not _is_windows():
        return None

    data_in, _keep = _make_blob(secret.encode("utf-8"))
    entropy, _keep_entropy = _make_blob(_ENTROPY)
    data_out = _DataBlob()

    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(data_in), None, ctypes.byref(entropy),
        None, None, _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(data_out),
    )
    if not ok:
        return None

    try:
        return base64.b64encode(_read_blob(data_out)).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(data_out.pbData)


def unprotect(stored: str) -> str | None:
    """protect() ciktisini cozer. Baska hesapta ya da bozuksa None doner."""
    if not stored or not _is_windows():
        return None

    try:
        raw = base64.b64decode(stored.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError):
        return None

    data_in, _keep = _make_blob(raw)
    entropy, _keep_entropy = _make_blob(_ENTROPY)
    data_out = _DataBlob()

    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(data_in), None, ctypes.byref(entropy),
        None, None, _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(data_out),
    )
    if not ok:
        return None

    try:
        return _read_blob(data_out).decode("utf-8", errors="replace")
    finally:
        ctypes.windll.kernel32.LocalFree(data_out.pbData)


#: Gizlilik varsayilanlarinin surumu. Bir gizlilik secenegi varsayilan
#: olarak kapatildiginda artar; eski surumun kaydettigi deger bir kez silinir.
PRIVACY_DEFAULTS_VERSION = 2


class ChatSettings:
    """Baglanti ekranindaki degerleri saklar ve geri yukler."""

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings if settings is not None else QSettings(ORGANIZATION, APPLICATION)
        self._migrate_privacy_defaults()

    def _migrate_privacy_defaults(self) -> None:
        """Eski surumun varsayilan diye kaydettigi gizlilik degerlerini bir kez siler.

        1.6.x'e kadar oda gecmisi varsayilan olarak acikti ve save() bu degeri
        her basarili baglantida kayda yaziyordu. Yani bir kez baglanmis her
        kullanicida ``keep_history=True`` kayitliydi, ama bu bilincli bir tercih
        degil varsayilandi. Yalnizca varsayilani degistirmek mevcut hicbir
        kullaniciyi etkilemezdi. Gecisten sonra kutuyu kendisi isaretleyenin
        tercihine bir daha dokunulmaz.
        """
        stored = self._settings.value("privacy_defaults_version", 1, type=int)
        if stored >= PRIVACY_DEFAULTS_VERSION:
            return
        if stored < 2:
            self._settings.remove("keep_history")
        self._settings.setValue("privacy_defaults_version", PRIVACY_DEFAULTS_VERSION)
        self._settings.sync()

    def load(self) -> dict[str, Any]:
        stored_password = ""
        remember = self._settings.value("remember_password", False, type=bool)
        if remember:
            blob = self._settings.value("password_blob", "", type=str)
            stored_password = unprotect(blob) or ""

        return {
            "mode": self._settings.value("mode", "Join", type=str),
            "host": self._settings.value("host", "", type=str),
            "port": self._settings.value("port", "", type=str),
            "room": self._settings.value("room", "general", type=str),
            "username": self._settings.value("username", "", type=str),
            "remember_password": remember,
            "password": stored_password,
            # Tanilama kaydi diske yazar, yani kaliciliktir: varsayilan KAPALI
            # (THREAT_MODEL.md ilke 2). Sorun arastirirken acilir.
            "logging_enabled": self._settings.value("logging_enabled", False, type=bool),
            # Oda gecmisi yalnizca bellekte tutulur, diske inmez; ama aciksa
            # odaya parolasiz giren biri de sifreli gecmisi alabilir
            # (THREAT_MODEL.md 5.2). 1.7.0'dan beri varsayilan KAPALI.
            "keep_history": self._settings.value("keep_history", False, type=bool),
            "language": self.load_language(),
        }

    def load_language(self) -> str:
        """Kayitli arayuz dili. Hic secilmediyse bos; varsayilan dil i18n'de.

        load()'dan ayri: pencere acilirken yalnizca dil gerekiyor ve load()
        parolayi DPAPI ile cozmeye calisiyor.
        """
        return self._settings.value("language", "", type=str)

    def save_privacy_choices(
        self,
        *,
        logging_enabled: bool | None = None,
        keep_history: bool | None = None,
        remember_password: bool | None = None,
    ) -> None:
        """Gizlilik kutularini isaretlendikleri anda saklar.

        save() yalnizca basarili baglantida cagriliyor. Eskiden kutunun
        isaretini kaldirip baglanmadan cikan kullanicinin tercihi kayboluyordu:
        tanilama kaydi bir sonraki acilista yeniden aciliyor, "hatirla"
        kaldirilsa bile sifreli parola diskte kaliyordu.
        """
        if logging_enabled is not None:
            self._settings.setValue("logging_enabled", logging_enabled)
        if keep_history is not None:
            self._settings.setValue("keep_history", keep_history)
        if remember_password is not None:
            self._settings.setValue("remember_password", remember_password)
            if not remember_password:
                self._settings.remove("password_blob")
        self._settings.sync()

    def save_language(self, language: str) -> None:
        """Dil secimi aninda saklanir; save() gibi basarili baglantiyi beklemez."""
        self._settings.setValue("language", language)
        self._settings.sync()

    def load_voice_gate(self) -> tuple[bool, int]:
        """Gurultu kapisi: (acik mi, esik). Esik RMS cinsinden.

        Ses ayari kisiye ve mikrofona bagli; her acilista yeniden
        ayarlanmasin diye saklaniyor. Gizli bir bilgi degil.
        """
        acik = self._settings.value("voice_gate", True, type=bool)
        esik = self._settings.value("voice_gate_threshold", 0, type=int)
        return acik, esik

    def save_voice_gate(self, *, enabled: bool | None = None, threshold: int | None = None) -> None:
        """Kapi ayarini degistigi anda saklar."""
        if enabled is not None:
            self._settings.setValue("voice_gate", enabled)
        if threshold is not None:
            self._settings.setValue("voice_gate_threshold", int(threshold))
        self._settings.sync()

    def load_voice_devices(self) -> tuple[bytes, bytes]:
        """Secili ses cihazlari: (mikrofon, hoparlor). Bos bayt sistem varsayilani.

        Yalnizca cihazin KIMLIGI saklaniyor, adi degil: Bluetooth cihaz
        adlarinda kisi adi bulunabiliyor ("Ayse'nin AirPods'u"). Kimlik
        Windows'un ses ucu numarasi; kisisel bir bilgi tasimiyor ve ag
        uzerinden hicbir yere gitmiyor.
        """
        return (
            self._device_id("voice_input_device"),
            self._device_id("voice_output_device"),
        )

    def _device_id(self, key: str) -> bytes:
        deger = self._settings.value(key, "", type=str)
        try:
            return bytes.fromhex(deger)
        except ValueError:
            # Bozuk kayit: varsayilana dusmek, programi acilmaz yapmaktan iyi.
            return b""

    def save_voice_devices(
        self, *, input_id: bytes | None = None, output_id: bytes | None = None
    ) -> None:
        """Cihaz secimini degistigi anda saklar."""
        if input_id is not None:
            self._settings.setValue("voice_input_device", bytes(input_id).hex())
        if output_id is not None:
            self._settings.setValue("voice_output_device", bytes(output_id).hex())
        self._settings.sync()

    def save(
        self,
        mode: str,
        host: str,
        port: str,
        room: str,
        username: str,
        password: str = "",
        remember_password: bool = False,
        logging_enabled: bool = False,
        keep_history: bool = False,
    ) -> None:
        self._settings.setValue("mode", mode)
        self._settings.setValue("host", host)
        self._settings.setValue("port", port)
        self._settings.setValue("room", room)
        self._settings.setValue("username", username)
        self._settings.setValue("remember_password", remember_password)
        self._settings.setValue("logging_enabled", logging_enabled)
        self._settings.setValue("keep_history", keep_history)

        blob = protect(password) if (remember_password and password) else None
        if blob is None:
            # Sifreleme basarisizsa ya da hatirlama kapaliysa saklanmis
            # parola kaliyorsa silinir. Duz metin yazmak yok.
            self._settings.remove("password_blob")
        else:
            self._settings.setValue("password_blob", blob)

        self._settings.sync()

    def clear(self) -> None:
        self._settings.clear()
        self._settings.sync()
