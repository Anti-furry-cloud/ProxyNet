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

from __future__ import annotations

import html
import ipaddress
import threading
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QByteArray, QMimeData, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSlider,
    QSplashScreen,
    QStackedWidget,
    QSystemTrayIcon,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .i18n import LANGUAGES, current_language, has_text, passphrase_words, set_language, t
from .logging_setup import delete_log_files, set_logging_enabled
from .emoji import PICKER_ROWS, display_size
from .passphrase import generate_passphrase
from .settings import ChatSettings
# Acilis ekrani ve surum ayri, hafif modullerde: app.py onlari agir ice
# aktarmalardan ONCE gosteriyor. Buradan yeniden disa aciliyorlar, eski
# `from apps.proxychat.ui import ...` kullanimlari bozulmasin.
from .splash import (  # noqa: F401 -- disa acilanlar
    SPLASH_DURATION_SECONDS,
    SPLASH_MAX_SCREEN_FRACTION,
    SPLASH_SIDE_PX,
    build_splash_pixmap,
    build_splash_screen,
    remaining_splash_ms,
    resource_path,
    splash_side_for_screen,
)
from .version import APP_NAME, APP_VERSION
from . import voice as voice_module
from .voice import VoiceController
from core.client import ChatClient
from core.crypto import DECRYPT_REASON_SCHEME, DECRYPT_REASON_SENDER
from core.server import ChatServer
from core.utils import DEFAULT_HOST, DEFAULT_PORT, get_local_ipv4_addresses, parse_port_input, socket_error_code



#: Kenar panellerinin genisligi. Sabit tutuluyor: sohbet alani buyuyunce
#: kenarlarin da buyumesi icin bir sebep yok, tersine okunacak satir uzar.
#: Dogrulanmayan kullanici sayisi bunu asarsa tam sayi yazilmaz, ">100" yazilir.
#: Sebebi kozmetik degil: odaya girmek icin parola gerekmiyor (THREAT_MODEL 5.5),
#: yani biri binlerce sahte kullanici sokabilir. O zaman listenin uzunlugu ya da
#: sayinin kendisi bilgi tasimaz, yalnizca "cok" bilgisini tasir.
UNVERIFIED_LIMIT = 100

#: Dogrulanmayan kullanici sayaci satirini isaretleyen deger.
_UNVERIFIED_ROW = "unverified-row"


def unverified_label(count: int) -> tuple[str, dict]:
    """Dogrulanmayan kullanici satirinin metin anahtari ve degerleri.

    Qt'den bagimsiz: sayi-metin eslemesi pencere acmadan sinanabilsin.
    """
    if count > UNVERIFIED_LIMIT:
        return "chat.unverified_over", {"limit": UNVERIFIED_LIMIT}
    if count == 1:
        return "chat.unverified_one", {}
    return "chat.unverified_many", {"count": count}


#: Ses katilimci listesinin ust siniri; bunun altinda icerige gore boylanir.
#: Dort kisi sigacak kadar: daha fazlasinda kaydirmak, sag kenari o kadar
#: uzatmaktan iyi.
VOICE_LIST_MAX_HEIGHT = 200

SIDEBAR_MIN_WIDTH = 210
SIDEBAR_MAX_WIDTH = 260

#: Ses seviyesi cubugunun ve esik kaydiricisinin ust siniri (RMS).
#: Normal konusma 1000-6000 bandinda; 8000 ustu bagirmak demek.
VOICE_LEVEL_MAX = 8000
#: Kaydiricinin baslangic yeri; core/voice_gate.py'deki varsayilanla ayni.
VOICE_DEFAULT_THRESHOLD = 600

#: Kopyalanan oda parolasi panoda en fazla bu kadar kalir.
CLIPBOARD_CLEAR_MS = 30_000
#: Windows'a "bunu pano gecmisine (Win+V) ekleme, buluta yukleme, pano
#: izleyen programlara gosterme" diyen bicimler. Diger sistemlerde yok sayilir.
_WINDOWS_CLIPBOARD_EXCLUSIONS = {
    'application/x-qt-windows-mime;value="ExcludeClipboardContentFromMonitorProcessing"': b"\x00\x00\x00\x00",
    'application/x-qt-windows-mime;value="CanIncludeInClipboardHistory"': b"\x00\x00\x00\x00",
    'application/x-qt-windows-mime;value="CanUploadToCloudClipboard"': b"\x00\x00\x00\x00",
}


def _private_mime(text: str) -> QMimeData:
    """Pano icin metin; pano gecmisine, bulut panosuna ve izleyicilere girmez."""
    mime = QMimeData()
    mime.setText(text)
    for fmt, value in _WINDOWS_CLIPBOARD_EXCLUSIONS.items():
        mime.setData(fmt, QByteArray(value))
    return mime


#: Ekranda IP yerine gosterilen metin. Ekrani yayinlayan ya da kaydeden biri
#: adresini farkinda olmadan sizdirmasin diye adres varsayilan olarak gizli.
ADDRESS_MASK = "•••.•••.•••.•••"


def _is_loopback(host: str) -> bool:
    """Yalnizca bu makineyi gosteren adres: gizlenecek bir sey yok (Demo modu)."""
    return host.startswith("127.") or host in ("localhost", "::1")


DEFAULT_ROOMS = ["general", "random", "support"]

#: Baglanti koptugunda kac kez yeniden denenecegi ve denemeler arasi bekleme.
#: VPN baglantilari duzenli olarak duser; kullaniciyi uygulamayi kapatip
#: acmaya zorlamamak icin otomatik toparlaniyoruz.
RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY_MS = 3000

#: Onceki deneme surerken kac kez bosuna beklenecegi. Deneme hakki
#: yakilmadan beklenir ama sonsuza kadar degil.
MAX_RECONNECT_BUSY_WAITS = 20


def describe_socket_error(error: OSError) -> str:
    """Soket hatasini gecerli dilde, kullanicinin ne yapacagini soyleyen metne cevirir."""
    code = socket_error_code(error)
    key = f"socket_error.{code}"
    if code is not None and has_text(key):
        return t(key)
    return t("socket_error.other", name=error.__class__.__name__, detail=str(error))


def _plain_label(label: QLabel) -> QLabel:
    """Etiketi duz metne sabitler.

    QLabel'in varsayilani AutoText: HTML'ye benzeyen metni kendiliginden
    zengin metin olarak cizer, <img> etiketindeki dosyayi da yukler. Oda
    adini baskasi seciyor; Windows'ta \\\\sunucu\\pay gibi bir yol, programa o
    sunucuya SMB baglantisi actirir (IP ve NTLM ozeti gider). Veri gosteren
    her etiket bu yuzden duz metin.
    """
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


def _plain_tooltip(text: str) -> str:
    """Ipucunda metni oldugu gibi gosterir.

    Ipucunun bicimi ayarlanamiyor ve QToolTip de HTML'ye benzeyen metni
    zengin metin ciziyor. Cihaz adini cihazin sahibi koyar (Bluetooth), o
    yuzden kacislanip bilerek HTML'ye sariliyor; satir sonlari korunuyor.
    """
    return f"<p style='white-space:pre-wrap'>{html.escape(text)}</p>" if text else ""


def _undecryptable_text(packet: dict) -> str:
    """Cozulemeyen mesajin yerine gosterilecek metin, sebebine gore.

    Iki taraf farkli sifreleme semasi kullaniyorsa (orn. 1.6.x ile 1.7.0)
    parola ayni olsa bile cozulemez; o durumda "parola farkli" demek
    kullaniciyi yanlis yere yonlendirirdi.
    """
    if packet.get("decrypt_reason") == DECRYPT_REASON_SCHEME:
        return t("chat.undecryptable_version")
    if packet.get("decrypt_reason") == DECRYPT_REASON_SENDER:
        return t("chat.undecryptable_sender")
    return t("chat.undecryptable")


#: Oda basina bellekte tutulan en fazla mesaj.
ROOM_LOG_LIMIT = 200


def _log_entry(message: dict[str, Any], own: bool) -> dict[str, Any]:
    """Sunucudan gelen mesaj ya da gecmis ogesinden bellek kaydi.

    Cozulemeyen mesajin metni degil sebebi saklanir: dil degisirse dogru
    dilde yeniden yazilabilsin.
    """
    failed = bool(message.get("decrypt_failed"))
    ts = message.get("ts")
    return {
        "user": str(message.get("user", "system")),
        "content": "" if failed else str(message.get("content", "")),
        # Kayit anahtarinin parcasi (_log_key), o yuzden hashlenebilir olmali:
        # sunucudan liste ya da sozluk gelirse kume kurulurken patliyordu.
        "ts": ts if isinstance(ts, (int, float, str)) else None,
        "own": own,
        "reason": (message.get("decrypt_reason") or "") if failed else None,
    }


def _log_key(entry: dict[str, Any]) -> tuple:
    return (entry["user"], entry["content"], entry["ts"], entry["reason"] is not None)


def _sort_time(ts: Any) -> float:
    try:
        return float(ts)
    except (TypeError, ValueError):
        return 0.0


class ConnectionController(QObject):
    connected = Signal(object)
    connection_failed = Signal(str)
    packet_received = Signal(object)
    status_changed = Signal(str, object)

    def __init__(self) -> None:
        super().__init__()
        self._server: ChatServer | None = None
        self._client: ChatClient | None = None
        self._demo_clients: list[ChatClient] = []
        self._worker: threading.Thread | None = None
        self.mode = "Join"
        self.host = ""
        self.port = DEFAULT_PORT
        self.room = "general"
        self.username = "guest"
        self.room_password = ""
        #: Host/Demo modunda acilacak sunucunun gecmis tutup tutmayacagi.
        #: Varsayilan kapali; bkz. core/server.py.
        self.keep_history = False
        # Kullanicinin kendi kapattigi baglanti ile kopan baglantiyi
        # ayirmak icin: yalnizca ikincisinde yeniden baglanma denenir.
        self._intentional_disconnect = False
        #: Her kapatmada artar. Arka plan isleri (demo kullanicilari) baslarken
        #: aldiklari degerle karsilastirip oturumlari bittiyse durur.
        self._session = 0

    @property
    def client(self) -> ChatClient | None:
        return self._client

    @property
    def busy(self) -> bool:
        """Onceki baglanma denemesi hala suruyor mu?

        Cagiran taraf bunu sormadan connect_async cagirirsa istegi sessizce
        kaybedebilir; yeniden baglanma zinciri tam bu yuzden oluyordu.
        """
        return self._worker is not None and self._worker.is_alive()

    def connect_async(self, mode: str, host: str, port: int, room: str, username: str, room_password: str = "") -> bool:
        """Baglanma denemesini baslatir. Baslatilamadiysa False doner."""
        if self.busy:
            return False

        self.mode = mode
        self.host = host
        self.port = port
        self.room = room
        self.username = username
        self.room_password = room_password
        self._intentional_disconnect = False

        self._worker = threading.Thread(
            target=self._connect_worker,
            args=(mode, host, port, room, username, room_password),
            daemon=True,
        )
        self._worker.start()
        return True

    def _connect_worker(self, mode: str, host: str, port: int, room: str, username: str, room_password: str = "") -> None:
        try:
            share_ips: list[str] = []
            if mode == "Host":
                # host burada sunucunun dinleyecegi adres. Belirli bir adres
                # secildiyse sunucu 127.0.0.1'i dinlemez; kendi istemcimiz de
                # o adrese baglanmali.
                self._server = ChatServer(host=host, port=port, keep_history=self.keep_history)
                self._server.start()
                if host == DEFAULT_HOST:
                    connect_host = "127.0.0.1"
                    share_ips = get_local_ipv4_addresses()
                else:
                    connect_host = host
                    share_ips = [host]
            elif mode == "Demo":
                # Demo yalnizca bu bilgisayarda calisir; aga acilmasi icin sebep yok.
                self._server = ChatServer(host="127.0.0.1", port=port, keep_history=self.keep_history)
                self._server.start()
                connect_host = "127.0.0.1"
            else:
                connect_host = host

            self._client = ChatClient(
                on_packet=self._emit_packet,
                on_status=self._emit_status,
                room_password=room_password,
            )

            last_error: Exception | None = None
            for _ in range(20):
                try:
                    self._client.connect(connect_host, port, room, username, timeout=1.5)
                    self.connected.emit(
                        {
                            "mode": mode,
                            "host": connect_host,
                            "port": port,
                            "room": room,
                            "username": username,
                            "share_ips": share_ips,
                            "encrypted": self._client.encrypted,
                        }
                    )
                    if mode == "Demo":
                        self._launch_demo_clients(connect_host, port, room, room_password)
                    return
                except Exception as error:  # noqa: BLE001
                    last_error = error
                    if mode != "Host":
                        break
                    threading.Event().wait(0.15)
            if last_error is not None:
                raise last_error
        except Exception as error:  # noqa: BLE001
            self._cleanup()
            message = describe_socket_error(error) if isinstance(error, OSError) else str(error)
            self.connection_failed.emit(message)

    def _emit_packet(self, packet: dict[str, Any]) -> None:
        self.packet_received.emit(packet)

    def _emit_status(self, state: str, payload: dict[str, Any]) -> None:
        if state == "disconnected":
            payload = dict(payload)
            payload["intentional"] = self._intentional_disconnect
        self.status_changed.emit(state, payload)
        if state == "error":
            self.connection_failed.emit(str(payload.get("error", t("error.connection"))))

    def send_message(self, text: str) -> None:
        if self._client is not None:
            self._client.send_message(text)

    def message_too_long(self, text: str) -> bool:
        client = self._client
        return client is not None and client.message_too_long(text)

    @property
    def room_session(self):
        """Istemcinin bu odadaki uctan uca oturumu; parolasizsa None.

        Ses tarafi buradan iki sey aliyor: kendi yayin anahtarini ve eslerin
        anahtarlarini. Boylece ses anahtari paroladan degil oturumdan turuyor
        (THREAT_MODEL 5.1).
        """
        from core.room_session import RoomSession

        client = self._client
        oturum = getattr(client, "_cipher", None) if client is not None else None
        return oturum if isinstance(oturum, RoomSession) else None

    @property
    def encrypted(self) -> bool:
        """Bu oturumda oda parolasi var mi?

        Uye listesindeki "dogrulanmadi" isareti buna bagli: parolasiz odada
        dogrulanacak bir sey yok.
        """
        client = self._client
        return client.encrypted if client is not None else bool(self.room_password)

    def switch_room(self, room: str) -> None:
        if self._client is not None:
            self._client.join_room(room)

    def disconnect(self) -> None:
        self._intentional_disconnect = True
        self._cleanup()

    def _cleanup(self) -> None:
        self._session += 1
        for client in list(self._demo_clients):
            client.disconnect()
        self._demo_clients.clear()
        if self._client is not None:
            self._client.disconnect()
            self._client = None
        if self._server is not None:
            self._server.stop()
            self._server = None

    def _launch_demo_clients(self, host: str, port: int, room: str, room_password: str = "") -> None:
        # Demo kapatildiktan sonra sahte kullanicilar durmali. Eskiden bu is
        # oturumdan habersiz devam ediyordu: Demo'dan hemen cikip ayni portta
        # Host baslatan kullanicinin GERCEK odasina nova/atlas/echo girip demo
        # mesajlarini yolluyordu.
        session = self._session

        def still_running() -> bool:
            return self._session == session

        def worker() -> None:
            demo_users = [
                ("nova", t("demo.message_1")),
                ("atlas", t("demo.message_2")),
                ("echo", t("demo.message_3")),
            ]

            time.sleep(0.8)
            for username, message in demo_users:
                if not still_running():
                    return
                bot = ChatClient(room_password=room_password)
                try:
                    bot.connect(host, port, room, username, timeout=2.0)
                except OSError:
                    return
                self._demo_clients.append(bot)
                # Baglanirken oturum kapanmis olabilir; _cleanup bu botu
                # listede goremeden bitirmis olabilecegi icin burada kapatilir.
                if not still_running():
                    bot.disconnect()
                    return
                time.sleep(0.35)
                if not still_running():
                    return
                try:
                    bot.send_message(message)
                except (OSError, ConnectionError):
                    return
                time.sleep(0.35)

        threading.Thread(target=worker, name="ProxyChatDemoBots", daemon=True).start()


def _network_kind(ip: str) -> str:
    """Adresin hangi tur aga ait oldugu: adres gizliyken secimi bununla yapilir."""
    # Hamachi sanal ag adreslerini 25.0.0.0/8 blogundan verir.
    if ip.startswith("25."):
        return "Hamachi"
    try:
        private = ipaddress.ip_address(ip).is_private
    except ValueError:
        private = False
    return t("connect.network_local" if private else "connect.network_other")


def describe_listen_address(ip: str, revealed: bool = False) -> str:
    """Host'un dinleyebilecegi bir adresi listede gosterilecek hale getirir.

    Adres varsayilan olarak maskeli: ag listesi de ekran yayininda adresi
    sizdiriyordu. Hangi aga ait oldugu her zaman yazar; "Butun aglar" bir adres
    degil, gizlenmez.
    """
    if ip == DEFAULT_HOST:
        return t("connect.listen_all")
    return f"{ip if revealed else ADDRESS_MASK} — {_network_kind(ip)}"


def _listen_labels(ips: list[str], revealed: bool) -> list[str]:
    """Listenin etiketleri. Adres gizliyken ayni turden iki ag ayirt edilemezdi
    (Ethernet ve Wi-Fi ikisi de "Yerel ag"); onlara sira numarasi eklenir."""
    kinds = [_network_kind(ip) if ip != DEFAULT_HOST else "" for ip in ips]
    seen: dict[str, int] = {}
    labels = []
    for ip, kind in zip(ips, kinds):
        label = describe_listen_address(ip, revealed)
        if kind and kinds.count(kind) > 1:
            seen[kind] = seen.get(kind, 0) + 1
            label = f"{label} {seen[kind]}"
        labels.append(label)
    return labels


class ConnectPage(QWidget):
    connect_requested = Signal(str, str, int, str, str, str)

    def __init__(self, settings: ChatSettings | None = None) -> None:
        super().__init__()
        self.settings = settings if settings is not None else ChatSettings()
        # Durum satiri hazir metin olarak degil (anahtar, degerler, ham metin)
        # olarak tutulur: dil degisince yeniden yazilabilsin diye.
        self._status: tuple[str | None, dict[str, Any], str] = (None, {}, "")

        # Kartlar sayfada dikeyde ortalaniyor: aksi halde ustte toplanip
        # altta genis bos alan birakiyorlardi.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addStretch(1)
        root = QHBoxLayout()
        root.setSpacing(18)
        outer.addLayout(root)
        outer.addStretch(1)

        self.brand_card = QFrame()
        self.brand_card.setObjectName("brandCard")
        brand_layout = QVBoxLayout(self.brand_card)
        brand_layout.setContentsMargins(24, 24, 24, 24)
        brand_layout.setSpacing(12)

        title = QLabel(APP_NAME)
        title.setObjectName("brandTitle")
        self.subtitle = QLabel()
        self.subtitle.setWordWrap(True)
        self.subtitle.setObjectName("brandSubtitle")
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setObjectName("brandHint")

        self.share_box = QTextBrowser()
        self.share_box.setObjectName("shareBox")
        self.share_box.setOpenExternalLinks(False)
        self.share_box.setReadOnly(True)
        # Icerigi birkac satirlik ipucu; esneme faktoru verilirse kartin
        # tamamini kapliyordu.
        self.share_box.setMinimumHeight(90)
        self.share_box.setMaximumHeight(150)

        brand_layout.addWidget(title)
        brand_layout.addWidget(self.subtitle)
        version = QLabel(f"v{APP_VERSION}")
        version.setObjectName("brandVersion")
        brand_layout.addWidget(version)
        brand_layout.addWidget(self.hint)
        brand_layout.addWidget(self.share_box)

        self.privacy_title = QLabel()
        self.privacy_title.setObjectName("sidebarSection")
        brand_layout.addWidget(self.privacy_title)

        self.keep_history_box = QCheckBox()
        self.keep_history_box.toggled.connect(
            lambda checked: self.settings.save_privacy_choices(keep_history=checked)
        )
        brand_layout.addWidget(self.keep_history_box)

        self.logging_box = QCheckBox()
        self.logging_box.toggled.connect(self._on_logging_toggled)
        brand_layout.addWidget(self.logging_box)

        brand_layout.addStretch(1)

        form_card = QFrame()
        form_card.setObjectName("formCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(24, 24, 24, 24)
        form_layout.setSpacing(12)

        self.form_title = QLabel()
        self.form_title.setObjectName("sectionTitle")
        form_layout.addWidget(self.form_title)

        self.mode_box = QComboBox()
        self.mode_box.addItems(["Join", "Host", "Demo"])
        self.mode_box.currentTextChanged.connect(self._update_mode_state)

        self.username_edit = QLineEdit()

        # Adresler bu ekranda da varsayilan olarak gizli: saklanan IP program
        # acilir acilmaz alanda, makinenin adresleri de ag listesinde
        # gorunuyor, ekranini yayinlayan biri bunlari farkinda olmadan
        # sizdiriyordu. Sohbet ekranindaki gibi basili tutunca gorunur.
        self._reveal_addresses = False

        self.host_edit = QLineEdit()
        self.host_edit.setText("")
        # Yazarken gorunur (kor yazmak hataya acik), alandan cikinca maskelenir.
        # Qt'nin hazir PasswordEchoOnEdit modu kullanilmiyor: o mod, dolu alana
        # basilan ilk tusta ICERIGI SILIYOR (saklanan IP'nin sonuna rakam
        # eklemek isteyen IP'yi kaybediyordu). Gorunurlugu burada biz yonetiyoruz.
        self.host_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.host_edit.textEdited.connect(lambda _text: self.host_edit.setEchoMode(QLineEdit.EchoMode.Normal))
        self.host_edit.editingFinished.connect(self._mask_host_field)

        # Host modunda sunucunun dinleyecegi ag. Varsayilan yok ve secim
        # saklanmaz: kullanici her seferinde bilerek secer. Eskiden sunucu hep
        # 0.0.0.0'i, yani ayni Wi-Fi'deki yabancilarin da ulasabildigi butun
        # aglari dinliyordu (THREAT_MODEL 5.6).
        self.listen_box = QComboBox()

        self.reveal_address_button = QPushButton()
        self.reveal_address_button.pressed.connect(lambda: self._set_addresses_revealed(True))
        self.reveal_address_button.released.connect(lambda: self._set_addresses_revealed(False))

        self.address_row = QWidget()
        self.address_row.setObjectName("addressRow")
        address_layout = QHBoxLayout(self.address_row)
        address_layout.setContentsMargins(0, 0, 0, 0)
        address_layout.setSpacing(8)
        address_layout.addWidget(self.host_edit, 1)
        address_layout.addWidget(self.listen_box, 1)
        address_layout.addWidget(self.reveal_address_button)

        self.port_edit = QLineEdit()
        self.port_edit.setText(str(DEFAULT_PORT))

        self.room_edit = QLineEdit()
        self.room_edit.setText("general")

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        # Elle degistirilen parola artik uretilen parola degil; bildirim kalkar.
        # textEdited yalnizca kullanici yazinca tetiklenir, setText'te degil.
        self.password_edit.textEdited.connect(lambda _text: self.password_notice.hide())
        self.password_edit.textChanged.connect(lambda _text: self._update_copy_button())

        # Parola yuz yuze okunarak paylasilacagi icin gorulebilmeli.
        self.show_password_button = QPushButton()
        self.show_password_button.setCheckable(True)
        self.show_password_button.toggled.connect(self._on_show_password_toggled)

        # Ekran paylasirken parolayi gostermeden Signal'e yapistirabilmek icin.
        self.copy_password_button = QPushButton()
        self.copy_password_button.clicked.connect(self.copy_password)
        self._copied_password: str | None = None
        self._busy = False
        self._update_copy_button()
        self._clipboard_clear_timer = QTimer(self)
        self._clipboard_clear_timer.setSingleShot(True)
        self._clipboard_clear_timer.setInterval(CLIPBOARD_CLEAR_MS)
        self._clipboard_clear_timer.timeout.connect(self.clear_copied_password)
        self._copied_feedback_timer = QTimer(self)
        self._copied_feedback_timer.setSingleShot(True)
        self._copied_feedback_timer.setInterval(2000)
        self._copied_feedback_timer.timeout.connect(self._render_copy_button)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.clear_copied_password)

        self.generate_password_button = QPushButton()
        self.generate_password_button.clicked.connect(self.generate_password)

        # Satir kapsayicisi zemin boyamamali (bkz. stil dosyasi, passwordRow).
        self.password_row = QWidget()
        self.password_row.setObjectName("passwordRow")
        password_layout = QHBoxLayout(self.password_row)
        password_layout.setContentsMargins(0, 0, 0, 0)
        password_layout.setSpacing(8)
        password_layout.addWidget(self.password_edit, 1)
        password_layout.addWidget(self.show_password_button)
        password_layout.addWidget(self.copy_password_button)
        password_layout.addWidget(self.generate_password_button)

        self.password_notice = QLabel()
        self.password_notice.setWordWrap(True)
        self.password_notice.setObjectName("passwordNotice")
        self.password_notice.hide()

        self.remember_password_box = QCheckBox()
        # Isaret kaldirilinca saklanan parola hemen silinir; baglanmayi beklemez.
        self.remember_password_box.toggled.connect(
            lambda checked: self.settings.save_privacy_choices(remember_password=checked)
        )

        self.password_hint = QLabel()
        self.password_hint.setWordWrap(True)
        self.password_hint.setObjectName("brandHint")

        self.status_label = _plain_label(QLabel(""))
        self.status_label.setObjectName("statusLabel")

        fields = [
            self.mode_box,
            self.username_edit,
            self.address_row,
            self.port_edit,
            self.room_edit,
            self.password_row,
            self.password_notice,
            self.remember_password_box,
            self.password_hint,
        ]
        for field in fields:
            form_layout.addWidget(field)

        self.connect_button = QPushButton()
        self.connect_button.clicked.connect(self._emit_connect)
        # Metin alanlarinda Enter da baglanir; eskiden yalnizca dugme calisiyordu.
        for edit in (self.username_edit, self.host_edit, self.port_edit, self.room_edit, self.password_edit):
            edit.returnPressed.connect(self._connect_from_keyboard)
        form_layout.addWidget(self.connect_button)
        form_layout.addWidget(self.status_label)
        form_layout.addStretch(1)

        root.addWidget(self.brand_card, 1)
        root.addWidget(form_card, 1)
        self.retranslate()
        self.load_settings()
        self._update_mode_state(self.mode_box.currentText())

    def retranslate(self) -> None:
        """Butun metinleri gecerli dilde yeniden yazar.

        Dil degistiginde uygulama yeniden baslatilmadan cagrilir; alanlara
        yazilmis degerlere dokunmaz.
        """
        self.subtitle.setText(t("connect.subtitle"))
        self.hint.setText(t("connect.hint"))
        self.privacy_title.setText(t("connect.privacy_title"))
        self.keep_history_box.setText(t("connect.keep_history"))
        self.keep_history_box.setToolTip(t("connect.keep_history_tooltip"))
        self.logging_box.setText(t("connect.logging"))
        self.logging_box.setToolTip(t("connect.logging_tooltip"))
        self.form_title.setText(t("connect.title"))
        self.username_edit.setPlaceholderText(t("connect.username"))
        self.host_edit.setPlaceholderText(t("connect.host_placeholder"))
        self.listen_box.setPlaceholderText(t("connect.listen_placeholder"))
        self.listen_box.setToolTip(t("connect.listen_tooltip"))
        self._render_listen_labels()
        self.reveal_address_button.setText(t("chat.reveal_address"))
        self.reveal_address_button.setToolTip(t("chat.reveal_address_tooltip"))
        self.port_edit.setPlaceholderText(t("connect.port"))
        self.room_edit.setPlaceholderText(t("connect.room"))
        self.password_edit.setPlaceholderText(t("connect.password"))
        self._render_show_password_button()
        self._render_copy_button()
        self.copy_password_button.setToolTip(t("connect.copy_password_tooltip"))
        self.generate_password_button.setText(t("connect.generate_password"))
        self.generate_password_button.setToolTip(t("connect.generate_password_tooltip"))
        self.password_notice.setText(t("connect.password_generated"))
        self.remember_password_box.setText(t("connect.remember_password"))
        self.remember_password_box.setToolTip(t("connect.remember_password_tooltip"))
        self.password_hint.setText(t("connect.password_hint"))
        self.connect_button.setText(t("connect.button"))
        self._apply_mode_texts(self.mode_box.currentText())
        self._render_status()

    def generate_password(self) -> None:
        """Alani secili dilin kelimelerinden uretilmis guclu bir parolayla doldurur.

        Gorunurluge dokunulmaz. Eskiden parola gorunur yapiliyordu; "Gizle"ye
        basmis biri (ornegin ekran paylasirken) Uret'e basinca parola ekrana
        geliyordu. Gormek isteyen Goster'e, gostermeden paylasmak isteyen
        Kopyala'ya basar. Yanindaki bildirim nasil paylasilmasi gerektigini soyler.
        """
        self.password_edit.setText(generate_passphrase(passphrase_words()))
        self.password_notice.show()

    def _clipboard(self):
        return QApplication.clipboard()

    def copy_password(self) -> None:
        """Parolayi gostermeden panoya kopyalar.

        Windows pano gecmisine ve bulut panosuna girmemesi istenir; pano
        CLIPBOARD_CLEAR_MS sonra (ve program kapanirken), hala bu parolayi
        tutuyorsa temizlenir.
        """
        password = self.password_edit.text()
        if not password:
            return
        self._clipboard().setMimeData(_private_mime(password))
        self._copied_password = password
        self._clipboard_clear_timer.start()
        self.copy_password_button.setText(t("connect.password_copied"))
        self._copied_feedback_timer.start()

    def clear_copied_password(self) -> None:
        """Panoyu temizler; kullanici arada baska bir sey kopyaladiysa dokunmaz."""
        self._clipboard_clear_timer.stop()
        if self._copied_password is None:
            return
        clipboard = self._clipboard()
        if clipboard.text() == self._copied_password:
            clipboard.clear()
        self._copied_password = None

    def _render_copy_button(self) -> None:
        self.copy_password_button.setText(t("connect.copy_password"))

    def _update_copy_button(self) -> None:
        self.copy_password_button.setEnabled(not self._busy and bool(self.password_edit.text()))

    def _on_show_password_toggled(self, visible: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self.password_edit.setEchoMode(mode)
        self._render_show_password_button()

    def _render_show_password_button(self) -> None:
        visible = self.show_password_button.isChecked()
        self.show_password_button.setText(t("connect.hide_password" if visible else "connect.show_password"))

    def _on_logging_toggled(self, enabled: bool) -> None:
        """Kayit tercihi aninda uygulanir ve saklanir; yeniden baslatma gerekmez.

        Kapatilirken var olan dosyalar da silinir: kullanici kaydi
        kapattiginda eski kayitlarin diskte kalmasi anlamsiz olurdu.
        """
        self.settings.save_privacy_choices(logging_enabled=enabled)
        if enabled:
            set_logging_enabled(True)
        else:
            delete_log_files()

    def load_settings(self) -> None:
        """Son basarili baglantinin degerlerini alanlara doldurur."""
        saved = self.settings.load()
        if saved["mode"] in {"Join", "Host", "Demo"}:
            self.mode_box.setCurrentText(saved["mode"])
        if saved["username"]:
            self.username_edit.setText(saved["username"])
        if saved["host"]:
            self.host_edit.setText(saved["host"])
        if saved["port"]:
            self.port_edit.setText(saved["port"])
        if saved["room"]:
            self.room_edit.setText(saved["room"])
        self.remember_password_box.setChecked(bool(saved["remember_password"]))
        self.keep_history_box.setChecked(bool(saved["keep_history"]))
        # blockSignals: yukleme sirasinda dosya silme tetiklenmesin
        self.logging_box.blockSignals(True)
        self.logging_box.setChecked(bool(saved["logging_enabled"]))
        self.logging_box.blockSignals(False)
        if saved["password"]:
            self.password_edit.setText(saved["password"])

    def save_settings(self) -> None:
        """Baglanti basarili olunca cagrilir; bozuk degerler saklanmaz."""
        self.settings.save(
            mode=self.mode_box.currentText(),
            host=self.host_edit.text().strip(),
            port=self.port_edit.text().strip(),
            room=self.room_edit.text().strip(),
            username=self.username_edit.text().strip(),
            password=self.password_edit.text(),
            remember_password=self.remember_password_box.isChecked(),
            logging_enabled=self.logging_box.isChecked(),
            keep_history=self.keep_history_box.isChecked(),
        )

    def refresh_listen_addresses(self) -> None:
        """Dinlenebilecek adresleri yeniden listeler.

        Onceki secim hala mevcutsa korunur; adres bilgisayardan kalktiysa
        (orn. Hamachi kapatildi) secim bosalir.
        """
        previous = self.listen_box.currentData()
        self.listen_box.clear()
        for ip in [*get_local_ipv4_addresses(), DEFAULT_HOST]:
            self.listen_box.addItem("", ip)
        self._render_listen_labels()
        # addItem bos listeye ilk ogeyi eklerken onu kendiliginden seciyor;
        # varsayilan secim olmamasi icin index acikca ayarlanir.
        self.listen_box.setCurrentIndex(self.listen_box.findData(previous) if previous is not None else -1)

    def _render_listen_labels(self) -> None:
        ips = [self.listen_box.itemData(i) for i in range(self.listen_box.count())]
        for index, label in enumerate(_listen_labels(ips, self._reveal_addresses)):
            self.listen_box.setItemText(index, label)

    def _set_addresses_revealed(self, revealed: bool) -> None:
        """Basili tutulurken IP alani ve ag listesi acik, birakinca yine maskeli."""
        self._reveal_addresses = revealed
        self.host_edit.setEchoMode(QLineEdit.EchoMode.Normal if revealed else QLineEdit.EchoMode.Password)
        self._render_listen_labels()

    def _mask_host_field(self) -> None:
        """Yazma bitince (Enter ya da alandan cikis) IP yeniden maskelenir."""
        if not self._reveal_addresses:
            self.host_edit.setEchoMode(QLineEdit.EchoMode.Password)

    def _update_mode_state(self, mode: str) -> None:
        joining = mode == "Join"
        # Join disindaki modlarda IP alani gizlenir ama ICERIGI SILINMEZ: Join
        # -> Host -> Join gidip gelen kullanici yazdigi IP'yi kaybediyordu.
        # Eskiden yalnizca devre disi kaliyordu; Host modunda ag listesinin
        # hemen ustunde ikinci bir adres satiri gibi duruyordu.
        self.host_edit.setVisible(joining)
        self.host_edit.setEnabled(joining)
        # Join'de parola odayi kuran taraftan geliyor; burada uretmek onu
        # karsi tarafinkiyle degistirmek demek, yani yalnizca gereksiz degil
        # yaniltici. Dugme gizleniyor ama alanin ICERIGI SILINMIYOR (ayni
        # gerekce host_edit'te de var).
        self.generate_password_button.setVisible(not joining)
        if joining:
            # Host modunda uretilip Join'e gecilirse "parola uretildi" notu
            # oradan kalma bir bilgi olur; kaldiriliyor.
            self.password_notice.hide()

        hosting = mode == "Host"
        self.listen_box.setVisible(hosting)
        # Demo yalnizca bu makineyi dinler: gizlenecek adres yok.
        self.address_row.setVisible(joining or hosting)
        if hosting:
            # Her geciste yenilenir: Hamachi uygulama acildiktan sonra
            # baglanmis olabilir.
            self.refresh_listen_addresses()
        self._apply_mode_texts(mode)

    def _apply_mode_texts(self, mode: str) -> None:
        if mode == "Join":
            self.share_box.setText(t("connect.mode_join"))
        else:
            self.share_box.setText(t("connect.mode_host" if mode == "Host" else "connect.mode_demo"))

    def _connect_from_keyboard(self) -> None:
        # Baglanma suruyorken dugme kapali; Enter ikinci bir deneme baslatmamali.
        if self.connect_button.isEnabled():
            self._emit_connect()

    def _emit_connect(self) -> None:
        mode = self.mode_box.currentText()
        username = self.username_edit.text().strip() or "guest"
        room = self.room_edit.text().strip() or "general"
        try:
            port = parse_port_input(self.port_edit.text(), DEFAULT_PORT)
        except ValueError:
            self.set_status("connect.error_invalid_port")
            return

        if mode == "Join":
            host = self.host_edit.text().strip()
            if not host:
                self.set_status("connect.error_host_required")
                return
        elif mode == "Host":
            # Host modunda host, sunucunun dinleyecegi adrestir.
            host = self.listen_box.currentData()
            if not isinstance(host, str):
                self.set_status("connect.error_choose_network")
                return
        else:
            host = "127.0.0.1"

        self.set_status("connect.connecting")
        self.connect_requested.emit(mode, host, port, room, username, self.password_edit.text())

    def set_busy(self, busy: bool) -> None:
        self.connect_button.setEnabled(not busy)
        self.mode_box.setEnabled(not busy)
        self.username_edit.setEnabled(not busy)
        self.host_edit.setEnabled(not busy and self.mode_box.currentText() == "Join")
        self.listen_box.setEnabled(not busy)
        self.port_edit.setEnabled(not busy)
        self.room_edit.setEnabled(not busy)
        self.password_edit.setEnabled(not busy)
        self.show_password_button.setEnabled(not busy)
        self._busy = busy
        self._update_copy_button()
        self.generate_password_button.setEnabled(not busy)
        self.remember_password_box.setEnabled(not busy)
        self.keep_history_box.setEnabled(not busy)
        self.logging_box.setEnabled(not busy)

    def set_status(self, key: str | None, **values: Any) -> None:
        """Durum satirini bir metin anahtariyla yazar; None satiri temizler."""
        self._status = (key, values, "")
        self._render_status()

    def show_error(self, message: str) -> None:
        # Hata metni cagiran tarafta, o anki dilde uretilmis olarak gelir.
        self._status = (None, {}, message)
        self._render_status()
        self.set_busy(False)

    def _render_status(self) -> None:
        key, values, raw = self._status
        self.status_label.setText(t(key, **values) if key else raw)


def darken(hex_color: str, factor: float = 0.72) -> str:
    """Bir rengin bir tik koyu hali; ayri bir sabit tanimlamamak icin.

    Addan sonraki iki nokta bunu kullaniyor: gri yapinca okunmasi zorlasiyordu,
    adla ayni renk yapinca da vurguyu paylasiyordu. Aradaki yer burasi.
    """
    ham = hex_color.lstrip("#")
    kanallar = (int(ham[i : i + 2], 16) for i in (0, 2, 4))
    return "#" + "".join(f"{min(255, int(deger * factor)):02x}" for deger in kanallar)


class EmojiPicker(QWidget):
    """Mesaj satirinin yanindaki emoji izgarasi.

    Windows'un kendi seciciisi (Win+.) var ama kimse bilmiyor; disaridan
    istenen sey de buydu. Izgara duz metin uretiyor: aga giden sey
    degismiyor, yalnizca yazmak kolaylasiyor.
    """

    picked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        # Qt.Popup: disariya tiklayinca kendiliginden kapanir ve odagi
        # geri verir, ayri bir "kapat" dugmesi gerekmiyor.
        super().__init__(parent, Qt.Popup)
        self.setObjectName("emojiPicker")
        izgara = QGridLayout(self)
        izgara.setContentsMargins(8, 8, 8, 8)
        izgara.setSpacing(2)
        for satir, metin in enumerate(PICKER_ROWS):
            for sutun, emoji in enumerate(metin.split()):
                dugme = QPushButton(emoji)
                dugme.setObjectName("emojiCell")
                dugme.setFlat(True)
                dugme.setFixedSize(34, 34)
                dugme.clicked.connect(lambda _=False, e=emoji: self._sec(e))
                izgara.addWidget(dugme, satir, sutun)

    def _sec(self, emoji: str) -> None:
        self.picked.emit(emoji)
        self.close()

    def show_above(self, anchor: QWidget) -> None:
        """Dugmenin ustunde acar; ekran disina tasmasin diye hizalanir."""
        self.adjustSize()
        kose = anchor.mapToGlobal(anchor.rect().topRight())
        self.move(kose.x() - self.width(), kose.y() - self.height() - 6)
        self.show()


class ChatPage(QWidget):
    leave_requested = Signal()
    #: Sesli sohbete katil / ayril dugmesi.
    voice_toggle_requested = Signal()
    #: Mikrofonu sustur kutusu (akis durmaz, sessizlik gider).
    voice_mute_changed = Signal(bool)
    #: Gurultu kapisi kutusu: konusma yokken mikrofon sessizlestirilir.
    voice_gate_changed = Signal(bool)
    #: Kapinin esigi (RMS): kaydirici birakildiginda.
    voice_threshold_changed = Signal(int)
    #: Kullanici mikrofon / hoparlor secti. Bos bayt = sistem varsayilani.
    voice_input_device_changed = Signal(bytes)
    voice_output_device_changed = Signal(bytes)
    #: Cihaz listesi ilk kez gerekti (satir acildi). Liste acilista okunmuyor:
    #: QtMultimedia'yi yuklemek paketlenmis exe'de acilisa saniye mertebesinde
    #: eklerdi, satir ise zaten kapali. Fareyle UZERINE GELMEK listeyi
    #: okumaz: ayni yukleme o an arayuzu ~1 sn dondururdu (incelemede
    #: bulundu). Ipucu liste okunana kadar genel metni gosteriyor.
    voice_devices_needed = Signal()
    #: Baskasindan mesaj geldi: (kullanici adi, icerik). Pencerenin one
    #: cikarilmasi/bildirim gosterilmesi gerekip gerekmedigine ana pencere
    #: karar verir -- sohbet sayfasi pencerenin durumunu bilmez.
    attention_requested = Signal(str, str)

    def __init__(self, controller: ConnectionController) -> None:
        super().__init__()
        self.controller = controller
        self.current_room = "general"
        self._room_items: dict[str, QListWidgetItem] = {}
        # None = henuz ilk anlik goruntu gelmedi (bkz. _announce_membership_change)
        self._known_users: set[str] | None = None
        # Sunucunun bildirdigi uye listesi (iddia) ve anahtar takasindan gelen
        # dogrulanmis kume (kanit). Ikisi ayri tutuluyor: zarf paketleri duz
        # metin gittigi icin liste sahtelenebilir, kanit sahtelenemez.
        self._snapshot_users: list[str] = []
        #: Biz odaya girdigimizde zaten iceride olanlar. Onlarin sonradan
        #: dogrulanmasi bir katilma degil; duyurulmamali.
        self._initial_users: set[str] = set()
        self._verified_users: set[str] = set()
        # Durum metinleri hazir metin olarak degil, dil degisince yeniden
        # yazilabilsin diye (tur, degerler) olarak tutulur.
        self._connection_state: tuple[str, dict[str, Any]] = ("chat.waiting", {})
        self._channel_state: tuple[str, dict[str, Any]] = ("chat.status_waiting", {})
        self._hint_state: tuple[str, dict[str, Any]] | None = None
        #: Adres yalnizca "Goster" basili tutulurken acik.
        self._reveal_addresses = False
        # None = oturum ayrintilari henuz gelmedi (bkz. show_connected).
        self._encrypted: bool | None = None
        #: Sunucunun bu oturuma verdigi ad ("joined" paketinden). Istenen addan
        #: farkli olabilir: odada ayni ad varsa sunucu "ayse-2" yapar.
        self._own_username: str | None = None
        #: Oda -> bu oturumda gorulen mesajlar. Yalnizca bellekte; diske
        #: yazilmaz, oturum bitince silinir (forget_messages). Gecmis
        #: varsayilan kapali oldugu icin (1.7.0) odaya geri donunce ekran
        #: bos kaliyordu.
        self._room_logs: dict[str, list[dict[str, Any]]] = {}
        #: Bu odadan baska odaya gecmis kisiler (donunce "geri dondu" yazilir).
        self._moved_away: set[str] = set()
        #: Son satir bir oda gecisi satiriysa: (kullanici, sayi, uzakta mi).
        self._presence_tail: tuple[str, int, bool] | None = None
        self._away_gap = False
        self._joined_user = "guest"

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        self.left_sidebar = QFrame()
        self.left_sidebar.setObjectName("sidebar")
        left_layout = QVBoxLayout(self.left_sidebar)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(10)

        brand = QLabel(APP_NAME)
        brand.setObjectName("sidebarBrand")
        left_layout.addWidget(brand)

        self.connection_status = _plain_label(QLabel())
        self.connection_status.setObjectName("tinyStatus")
        left_layout.addWidget(self.connection_status)

        # Adres varsayilan gizli; basili tutunca gorunur, birakinca gizlenir.
        # Bir tikla acilip unutulan bir anahtar, yayinda acik kalirdi.
        address_row = QHBoxLayout()
        self.reveal_address_button = QPushButton()
        self.reveal_address_button.setObjectName("disclosureButton")
        self.reveal_address_button.pressed.connect(lambda: self._set_addresses_revealed(True))
        self.reveal_address_button.released.connect(lambda: self._set_addresses_revealed(False))
        self.copy_address_button = QPushButton()
        self.copy_address_button.setObjectName("disclosureButton")
        self.copy_address_button.clicked.connect(self.copy_addresses)
        address_row.addWidget(self.reveal_address_button)
        address_row.addWidget(self.copy_address_button)
        address_row.addStretch(1)
        left_layout.addLayout(address_row)

        self.channels_title = QLabel()
        self.channels_title.setObjectName("sidebarSection")
        left_layout.addWidget(self.channels_title)

        room_row = QHBoxLayout()
        self.new_room_edit = QLineEdit()
        self.add_room_button = QPushButton("+")
        self.add_room_button.setFixedWidth(36)
        self.add_room_button.clicked.connect(self._add_room_from_field)
        room_row.addWidget(self.new_room_edit, 1)
        room_row.addWidget(self.add_room_button)
        left_layout.addLayout(room_row)

        self.room_list = QListWidget()
        self.room_list.setSpacing(0)
        self.room_list.setUniformItemSizes(True)
        self.room_list.itemClicked.connect(self._switch_room_from_item)
        left_layout.addWidget(self.room_list, 1)

        self.server_hint = QTextBrowser()
        self.server_hint.setObjectName("hintBox")
        self.server_hint.setReadOnly(True)
        self.server_hint.setMinimumHeight(70)
        self.server_hint.setMaximumHeight(110)
        # Yazacak bir sey yokken gizli: icinde hicbir sey olmayan bir cerceve
        # olarak duruyordu.
        self.server_hint.setVisible(False)
        left_layout.addWidget(self.server_hint)

        # Baglantiyi bilerek kapatip baglanti ekranina donmenin tek yolu;
        # eskiden uygulamayi kapatip acmak gerekiyordu.
        self.leave_button = QPushButton()
        self.leave_button.clicked.connect(self.leave_requested.emit)
        left_layout.addWidget(self.leave_button)

        self.center_panel = QFrame()
        self.center_panel.setObjectName("centerPanel")
        center_layout = QVBoxLayout(self.center_panel)
        center_layout.setContentsMargins(16, 16, 16, 16)
        center_layout.setSpacing(10)

        header = QHBoxLayout()
        header_box = QVBoxLayout()
        self.channel_title = _plain_label(QLabel("#general"))
        self.channel_title.setObjectName("channelTitle")
        self.channel_status = _plain_label(QLabel())
        self.channel_status.setObjectName("channelStatus")
        header_box.addWidget(self.channel_title)
        header_box.addWidget(self.channel_status)
        header.addLayout(header_box, 1)
        center_layout.addLayout(header)

        self.message_view = QTextBrowser()
        self.message_view.setObjectName("messageView")
        self.message_view.setOpenExternalLinks(False)
        self.message_view.setReadOnly(True)
        center_layout.addWidget(self.message_view, 1)

        input_row = QHBoxLayout()
        #: Testler ve ileride eklenecek dugmeler bu siraya bakiyor.
        self.input_row = input_row
        self.message_input = QLineEdit()
        self.message_input.returnPressed.connect(self._send_message)
        self.send_button = QPushButton()
        self.send_button.setObjectName("primaryButton")
        self.send_button.clicked.connect(self._send_message)
        self.emoji_button = QPushButton("🙂")
        self.emoji_button.setObjectName("emojiButton")
        self.emoji_button.setFixedWidth(44)
        self.emoji_button.clicked.connect(self._open_emoji_picker)
        self._emoji_picker: EmojiPicker | None = None
        input_row.addWidget(self.message_input, 1)
        input_row.addWidget(self.emoji_button)
        input_row.addWidget(self.send_button)
        center_layout.addLayout(input_row)

        # Sag kenar tek bir kart degil, iki ayri kart: kullanicilar ve ses.
        # Tek kartken aradaki bosluk kimseye ait degildi ve panel ortasinda
        # kocaman bir delik gibi duruyordu; simdi bosluk kullanici listesinin,
        # ses bolumu de kendi blogunun icinde.
        self.right_sidebar = QFrame()
        self.right_sidebar.setObjectName("sidebarStack")
        sidebar_layout = QVBoxLayout(self.right_sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(10)

        self.users_panel = QFrame()
        self.users_panel.setObjectName("sidebar")
        right_layout = QVBoxLayout(self.users_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(10)
        sidebar_layout.addWidget(self.users_panel, 1)

        self.users_title = QLabel()
        self.users_title.setObjectName("sectionTitle")
        right_layout.addWidget(self.users_title)

        self.user_list = QListWidget()
        self.user_list.setObjectName("userList")
        self.user_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.user_list.itemClicked.connect(self._on_user_item_clicked)
        #: Dogrulanmayan kullanicilarin adlari acik mi (satira tiklanarak).
        self._unverified_expanded = False
        right_layout.addWidget(self.user_list, 1)

        # --- Sesli sohbet: ses TCP'den degil, ayri bir UDP yolundan gider;
        # burada yalnizca katilim ve durum gosteriliyor. Kendi karti var;
        # icerigi kadar yer kapliyor, kullanici listesi gibi buyumuyor.
        self.voice_panel = QFrame()
        self.voice_panel.setObjectName("sidebar")
        right_layout = QVBoxLayout(self.voice_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(10)
        sidebar_layout.addWidget(self.voice_panel, 0)

        self.voice_title = QLabel()
        self.voice_title.setObjectName("sectionTitle")
        right_layout.addWidget(self.voice_title)

        self.voice_status = _plain_label(QLabel())
        self.voice_status.setObjectName("tinyStatus")
        self.voice_status.setWordWrap(True)
        right_layout.addWidget(self.voice_status)

        self.voice_list = QListWidget()
        self.voice_list.setObjectName("voiceList")
        self.voice_list.setMaximumHeight(110)
        # Iki kisilik listede bile kaydirma cubugu cikiyordu.
        self.voice_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.voice_list.setVisible(False)
        right_layout.addWidget(self.voice_list)

        self.voice_button = QPushButton()
        self.voice_button.setObjectName("primaryButton")
        self.voice_button.clicked.connect(self.voice_toggle_requested.emit)
        right_layout.addWidget(self.voice_button)

        self.voice_mute_box = QCheckBox()
        self.voice_mute_box.toggled.connect(self.voice_mute_changed.emit)
        self.voice_mute_box.setEnabled(False)
        right_layout.addWidget(self.voice_mute_box)

        # Cihaz secimi kapi ayarlarindan ONCE: esik mikrofona gore degisiyor.
        # Bir kerelik ayar, her gorusmede yer kaplamasin: ince bir ac/kapa
        # satirinin arkasinda KAPALI duruyor. Kapaliyken de hangi cihazin
        # kullanildigi bilinsin diye secim satirin ipucunda yaziyor.
        self.voice_devices_button = QPushButton()
        self.voice_devices_button.setObjectName("disclosureButton")
        self.voice_devices_button.setCheckable(True)
        self.voice_devices_button.setCursor(Qt.PointingHandCursor)
        self.voice_devices_button.toggled.connect(self._on_voice_devices_toggled)
        right_layout.addWidget(self.voice_devices_button)

        self.voice_devices_section = QWidget()
        # Adi stil sayfasindaki saydam kapsayicilar kuralinda; yoksa kartin
        # uzerinde farkli renkte bir serit olarak gorunuyordu.
        self.voice_devices_section.setObjectName("voiceDevicesSection")
        bolum = QVBoxLayout(self.voice_devices_section)
        bolum.setContentsMargins(0, 0, 0, 0)
        bolum.setSpacing(6)

        # `activated` yalnizca kullanici secince tetiklenir; liste kodla
        # doldurulurken (kulaklik takilinca) yanlislikla kayit yapilmaz.
        self.voice_input_label = QLabel()
        self.voice_input_label.setObjectName("tinyStatus")
        bolum.addWidget(self.voice_input_label)
        self.voice_input_box = self._device_box()
        self.voice_input_box.activated.connect(
            lambda indeks: self.voice_input_device_changed.emit(self._device_at(self.voice_input_box, indeks))
        )
        bolum.addWidget(self.voice_input_box)

        self.voice_output_label = QLabel()
        self.voice_output_label.setObjectName("tinyStatus")
        bolum.addWidget(self.voice_output_label)
        self.voice_output_box = self._device_box()
        self.voice_output_box.activated.connect(
            lambda indeks: self.voice_output_device_changed.emit(self._device_at(self.voice_output_box, indeks))
        )
        bolum.addWidget(self.voice_output_box)

        for box in (self.voice_input_box, self.voice_output_box):
            box.currentIndexChanged.connect(lambda _i: self._render_voice_devices_button())
        self.voice_devices_section.setVisible(False)
        right_layout.addWidget(self.voice_devices_section)

        # Varsayilan acik: mikrofon konusma yokken klavye sesini ve cizirtiyi
        # de tasiyordu. Kapatan kullanici ham sesi gonderir.
        self.voice_gate_box = QCheckBox()
        self.voice_gate_box.setChecked(True)
        self.voice_gate_box.toggled.connect(self.voice_gate_changed.emit)
        self.voice_gate_box.toggled.connect(self._update_gate_controls)
        right_layout.addWidget(self.voice_gate_box)

        # Esik kisiye ve mikrofona gore degisiyor: kullanici ayarlasin.
        # Cubuk o anki sesi gosteriyor, kaydiricinin nereye konacagi
        # konusurken gorulebilsin diye.
        self.voice_level = QProgressBar()
        self.voice_level.setObjectName("voiceLevel")
        self.voice_level.setRange(0, VOICE_LEVEL_MAX)
        self.voice_level.setTextVisible(False)
        self.voice_level.setFixedHeight(8)
        right_layout.addWidget(self.voice_level)

        self.voice_threshold = QSlider(Qt.Horizontal)
        self.voice_threshold.setRange(0, VOICE_LEVEL_MAX)
        self.voice_threshold.setValue(VOICE_DEFAULT_THRESHOLD)
        # Surukledikce degil, birakinca uygulanir: her piksel icin ayar
        # kaydetmek gereksiz.
        self.voice_threshold.sliderReleased.connect(
            lambda: self.voice_threshold_changed.emit(self.voice_threshold.value())
        )
        self.voice_threshold.valueChanged.connect(self._render_threshold_hint)
        right_layout.addWidget(self.voice_threshold)

        self.voice_threshold_hint = QLabel()
        self.voice_threshold_hint.setObjectName("tinyStatus")
        self.voice_threshold_hint.setWordWrap(True)
        right_layout.addWidget(self.voice_threshold_hint)

        #: "off" | "joining" | "on"
        self._voice_state = "off"

        # Kenar panelleri sabit genislikte, sohbet kalani aliyor. Eskiden
        # 1:2:1 esnekti, yani ekranin yarisi kenarlara gidiyordu: bakilan sey
        # ile onun cevresindeki takim ayni yer kapliyordu.
        for kenar in (self.left_sidebar, self.right_sidebar):
            kenar.setMinimumWidth(SIDEBAR_MIN_WIDTH)
            kenar.setMaximumWidth(SIDEBAR_MAX_WIDTH)
        root.addWidget(self.left_sidebar, 0)
        root.addWidget(self.center_panel, 1)
        root.addWidget(self.right_sidebar, 0)

        self.retranslate()
        self._populate_default_rooms()
        self._set_controls_enabled(False)

    @staticmethod
    def _device_box() -> QComboBox:
        box = QComboBox()
        # Cihaz adlari uzun olabiliyor ("Mikrofon (Realtek(R) Audio)"); kenar
        # panelini genisletmesin, tam ad ipucunda gorunsun.
        box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        box.setMinimumContentsLength(12)
        box.currentIndexChanged.connect(lambda _i: box.setToolTip(_plain_tooltip(box.currentText())))
        return box

    @staticmethod
    def _device_at(box: QComboBox, index: int) -> bytes:
        """Listedeki satirin cihaz kimligi; ilk satir (sistem varsayilani) bos."""
        return bytes.fromhex(box.itemData(index) or "")

    def set_voice_devices(
        self,
        inputs: list[tuple[bytes, str]],
        outputs: list[tuple[bytes, str]],
        input_id: bytes = b"",
        output_id: bytes = b"",
    ) -> None:
        """Cihaz listelerini doldurur ve secili olani gosterir.

        Secili cihaz takili degilse (kulaklik cikarilmis) "sistem varsayilani"
        gosterilir, ama bu bir SECIM degil: kayit degismez, kulaklik geri
        takilinca liste tazelenir ve yine o secili gelir.
        """
        self._fill_device_box(self.voice_input_box, inputs, input_id)
        self._fill_device_box(self.voice_output_box, outputs, output_id)

    def _on_voice_devices_toggled(self, acik: bool) -> None:
        if acik:
            self.voice_devices_needed.emit()
        self.voice_devices_section.setVisible(acik)
        self._render_voice_devices_button()

    def _render_voice_devices_button(self) -> None:
        """Ok yonu acik/kapali durumu, ipucu secili cihazlari gosterir."""
        ok = "▾" if self.voice_devices_button.isChecked() else "▸"
        self.voice_devices_button.setText(f"{ok}  {t('chat.voice_devices')}")
        if not self.voice_input_box.count():
            # Liste henuz okunmadi; ad bilinmiyor.
            self.voice_devices_button.setToolTip(t("chat.voice_devices_tooltip"))
            return
        self.voice_devices_button.setToolTip(
            _plain_tooltip(
                t(
                    "chat.voice_devices_summary",
                    microphone=self.voice_input_box.currentText(),
                    speaker=self.voice_output_box.currentText(),
                )
            )
        )

    def select_voice_devices(self, input_id: bytes, output_id: bytes) -> None:
        """Listeyi yeniden kurmadan secimi gosterir (ornegin geri donuste)."""
        for box, kimlik in ((self.voice_input_box, input_id), (self.voice_output_box, output_id)):
            indeks = box.findData(kimlik.hex()) if kimlik else 0
            box.setCurrentIndex(indeks if indeks >= 0 else 0)

    def _fill_device_box(self, box: QComboBox, devices: list[tuple[bytes, str]], selected: bytes) -> None:
        box.clear()
        # Veri olarak hex metin: bayt dizisi QVariant'a girince findData ile
        # guvenilir bulunmuyor, metin bulunuyor.
        box.addItem(t("chat.voice_device_default"), "")
        for kimlik, ad in devices:
            box.addItem(ad, kimlik.hex())
        indeks = box.findData(selected.hex()) if selected else 0
        box.setCurrentIndex(indeks if indeks >= 0 else 0)

    def set_voice_level(self, level: float) -> None:
        """Mikrofonun o anki seviyesi; cubugu gunceller."""
        self.voice_level.setValue(min(int(level), VOICE_LEVEL_MAX))

    def set_voice_threshold(self, threshold: int) -> None:
        """Kayitli esigi kaydiriciya yazar (sinyal yaymadan)."""
        if threshold <= 0:
            threshold = VOICE_DEFAULT_THRESHOLD
        self.voice_threshold.blockSignals(True)
        self.voice_threshold.setValue(min(threshold, VOICE_LEVEL_MAX))
        self.voice_threshold.blockSignals(False)
        self._render_threshold_hint()

    def _update_gate_controls(self, *_args) -> None:
        acik = self.voice_gate_box.isChecked()
        self.voice_threshold.setEnabled(acik)
        self._render_threshold_hint()

    def _render_threshold_hint(self, *_args) -> None:
        if not self.voice_gate_box.isChecked():
            self.voice_threshold_hint.setText(t("chat.voice_threshold_off"))
        else:
            self.voice_threshold_hint.setText(
                t("chat.voice_threshold_hint", value=self.voice_threshold.value())
            )

    def set_voice_state(self, state: str) -> None:
        """Sesli sohbetin durumu: "off", "joining", "on"."""
        self._voice_state = state
        self.voice_mute_box.setEnabled(state == "on")
        if state != "on":
            self.voice_mute_box.setChecked(False)
        self._render_voice()

    def set_voice_peers(self, names: list[str]) -> None:
        self.voice_list.clear()
        for name in names:
            self.voice_list.addItem(name)
        # Liste icerigi kadar yer kaplasin: sabit 110 piksel, iki kisilik
        # odada yarisi bos duruyordu. Kimse yoksa hic gorunmuyor.
        self.voice_list.setVisible(bool(names))
        if names:
            # Cerceve payi sabit sayi degil olculerek aliniyor: listenin
            # kenarligi ve dolgusu degisince (ses listesi kendi cercevesine
            # girdiginde oldu) sabit bir pay kaydirma cubugu cikariyordu.
            pay = 2 * self.voice_list.frameWidth() + 2
            satir = self.voice_list.sizeHintForRow(0)
            self.voice_list.setFixedHeight(
                min(VOICE_LIST_MAX_HEIGHT, satir * len(names) + pay)
            )
        self._render_voice()

    def set_voice_error(self, key: str) -> None:
        self.voice_status.setText(t(f"error.{key}"))

    def _render_voice(self) -> None:
        durum = {
            "off": "chat.voice_state_off",
            "joining": "chat.voice_state_joining",
            "on": "chat.voice_state_on",
        }.get(self._voice_state, "chat.voice_state_off")
        self.voice_button.setText(
            t("chat.voice_leave") if self._voice_state != "off" else t("chat.voice_join")
        )
        if self._voice_state == "on" and self.voice_list.count() <= 1:
            self.voice_status.setText(t("chat.voice_alone"))
        else:
            self.voice_status.setText(t(durum))

    def retranslate(self) -> None:
        """Butun metinleri gecerli dilde yeniden yazar.

        Sohbet akisina daha once eklenmis satirlar (mesajlar, katildi/ayrildi
        satirlari) yazildiklari dilde kalir; bunlar gecmis kaydidir.
        """
        self.channels_title.setText(t("chat.channels"))
        self.new_room_edit.setPlaceholderText(t("chat.add_room"))
        self.leave_button.setText(t("chat.leave"))
        self.message_input.setPlaceholderText(t("chat.message_placeholder"))
        self.send_button.setText(t("chat.send"))
        self.users_title.setText(t("chat.users"))
        self.emoji_button.setToolTip(t("chat.emoji"))
        self.voice_title.setText(t("chat.voice_title"))
        self.voice_mute_box.setText(t("chat.voice_mute"))
        self.voice_input_label.setText(t("chat.voice_microphone"))
        self.voice_output_label.setText(t("chat.voice_speaker"))
        # Ilk satir "sistem varsayilani": dil degisince o da degismeli.
        for box in (self.voice_input_box, self.voice_output_box):
            if box.count():
                box.setItemText(0, t("chat.voice_device_default"))
        self.voice_input_box.setToolTip(_plain_tooltip(self.voice_input_box.currentText()))
        self.voice_output_box.setToolTip(_plain_tooltip(self.voice_output_box.currentText()))
        # setItemText currentIndexChanged tetiklemiyor; ipucu elle tazelenir.
        self._render_voice_devices_button()
        self.voice_gate_box.setText(t("chat.voice_gate"))
        self.voice_gate_box.setToolTip(t("chat.voice_gate_tooltip"))
        self.voice_threshold.setToolTip(t("chat.voice_threshold_tooltip"))
        self._render_threshold_hint()
        self._render_voice()
        self.reveal_address_button.setText(t("chat.reveal_address"))
        self.reveal_address_button.setToolTip(t("chat.reveal_address_tooltip"))
        self.copy_address_button.setText(t("chat.copy_addresses"))
        self._render_connection_status()
        self._render_channel_status()
        self._render_server_hint()

    def _render_connection_status(self) -> None:
        kind, values = self._connection_state
        if kind != "connected":
            self.connection_status.setText(t(kind, **values))
            return
        encrypted = values["encrypted"]
        lock = t("chat.lock_encrypted" if encrypted else "chat.lock_plain")
        host = self._shown_address(values["host"])
        self.connection_status.setText(f"{t('chat.connected_to', host=host, port=values['port'])}\n{lock}")
        self.connection_status.setToolTip(t("chat.lock_encrypted_tooltip" if encrypted else "chat.lock_plain_tooltip"))
        self._render_address_controls()

    def _shown_address(self, host: str) -> str:
        """Ekranda gosterilecek adres: basili tutulmadikca maske."""
        return host if self._reveal_addresses or _is_loopback(host) else ADDRESS_MASK

    def _private_addresses(self) -> list[str]:
        """Gizlenen, yani bu makinenin disindan erisilen adresler."""
        adresler: list[str] = []
        kind, values = self._connection_state
        if kind == "connected" and not _is_loopback(values["host"]):
            adresler.append(values["host"])
        if self._hint_state is not None and self._hint_state[0] == "share":
            adresler.extend(ip for ip in self._hint_state[1]["ips"] if not _is_loopback(ip))
        return adresler

    def _render_address_controls(self) -> None:
        gizli = bool(self._private_addresses())
        self.reveal_address_button.setVisible(gizli)
        paylasilacak = self._hint_state is not None and self._hint_state[0] == "share"
        self.copy_address_button.setVisible(paylasilacak)

    def _set_addresses_revealed(self, revealed: bool) -> None:
        self._reveal_addresses = revealed
        self._render_connection_status()
        self._render_server_hint()

    def copy_addresses(self) -> None:
        """Paylasilacak adresleri ekranda gostermeden kopyalar."""
        if self._hint_state is None or self._hint_state[0] != "share":
            return
        values = self._hint_state[1]
        metin = "\n".join(f"{ip}:{values['port']}" for ip in values["ips"])
        QApplication.clipboard().setMimeData(_private_mime(metin))
        self.copy_address_button.setText(t("chat.address_copied"))
        QTimer.singleShot(1500, lambda: self.copy_address_button.setText(t("chat.copy_addresses")))

    def _render_channel_status(self) -> None:
        key, values = self._channel_state
        self.channel_status.setText(t(key, **values))

    def _render_server_hint(self) -> None:
        self._render_address_controls()
        if self._hint_state is None:
            self.server_hint.setVisible(False)
            return
        kind, values = self._hint_state
        if kind != "share":
            metin = t(kind, **values)
            self.server_hint.setText(metin)
            self.server_hint.setVisible(bool(metin.strip()))
            return
        ips = values["ips"]
        self.server_hint.setVisible(True)
        heading = t("chat.share_addresses" if len(ips) > 1 else "chat.share_address")
        satirlar = "\n".join(f"- {self._shown_address(ip)}:{values['port']}" for ip in ips)
        self.server_hint.setText(heading + "\n" + satirlar)

    def _set_channel_state(self, key: str, **values: Any) -> None:
        self._channel_state = (key, values)
        self._render_channel_status()

    def mark_connected(self) -> None:
        self._set_channel_state("chat.connected")

    def _populate_default_rooms(self) -> None:
        for room in DEFAULT_ROOMS:
            self._ensure_room_item(room)
        self._select_room("general")

    def _ensure_room_item(self, room: str) -> None:
        if room in self._room_items:
            return
        item = QListWidgetItem(f"#{room}")
        # Oda adi metinden geri ayiklanmaz: "#" ile baslayan bir oda adinda
        # (orn. "##dev") gorunen metin ile gercek ad ayirt edilemiyordu.
        item.setData(Qt.ItemDataRole.UserRole, room)
        self.room_list.addItem(item)
        self._room_items[room] = item

    def _select_room(self, room: str) -> None:
        if room in self._room_items:
            self.room_list.setCurrentItem(self._room_items[room])

    def _remove_room_item(self, room: str) -> None:
        item = self._room_items.pop(room, None)
        if item is None:
            return
        self.room_list.takeItem(self.room_list.row(item))

    def sync_rooms(self, rooms: list[str]) -> None:
        """Oda listesini sunucudan gelen listeye gore gunceller.

        Gorunecek odalar: sunucudaki acik odalar + her zaman duran varsayilan
        odalar + icinde bulundugumuz oda. Bu listede olmayanlar kaldirilir --
        boylece bosalan odalar listeden kendiliginden duser.
        """
        wanted = {str(room) for room in rooms if str(room).strip()}
        wanted.update(DEFAULT_ROOMS)
        wanted.add(self.current_room)

        for room in list(self._room_items):
            if room not in wanted:
                self._remove_room_item(room)
        for room in sorted(wanted):
            self._ensure_room_item(room)

        self._select_room(self.current_room)

    def _add_room_from_field(self) -> None:
        room = self.new_room_edit.text().strip()
        if not room:
            return
        self.new_room_edit.clear()
        self.switch_room(room)

    def _switch_room_from_item(self, item: QListWidgetItem) -> None:
        room = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(room, str):
            return
        self.switch_room(room)

    def switch_room(self, room: str) -> None:
        already_here = room == self.current_room

        self._ensure_room_item(room)
        self._select_room(room)
        self.current_room = room
        self.channel_title.setText(f"#{room}")

        if already_here:
            # Zaten bu odadayiz. Sunucuya yeniden katilma paketi yollamak
            # gecmisi bastan cektiriyor ve arayuz ekrani temizledigi icin
            # sistem satirlari (katildi/ayrildi, baglanti uyarilari) siliniyordu.
            # Secili odaya tiklamak yeterince kolay oldugu icin sik yasaniyordu.
            return

        self._known_users = None
        self._initial_users = set()
        self._verified_users = set()
        switching = html.escape(t("chat.switching_room", room=room))
        self.message_view.append(f"<div style='color:#7a7a7a;font-style:italic;'>{switching}</div>")
        self.controller.switch_room(room)

    def _open_emoji_picker(self) -> None:
        if self._emoji_picker is None:
            self._emoji_picker = EmojiPicker(self)
            self._emoji_picker.picked.connect(self._insert_emoji)
        self._emoji_picker.show_above(self.emoji_button)

    def _insert_emoji(self, emoji: str) -> None:
        """Emojiyi imlecin oldugu yere koyar ve odagi yazi alanina geri verir."""
        self.message_input.insert(emoji)
        self.message_input.setFocus()

    def _send_message(self) -> None:
        text = self.message_input.text().strip()
        if not text:
            return
        if self.controller.message_too_long(text):
            # Kutu temizlenmez: eskiden mesaj once siliniyor, sunucu da
            # reddedince yazilan metin geri gelmiyordu.
            self._append_system(t("chat.message_too_long"))
            return
        self.message_input.clear()
        self.controller.send_message(text)

    def _format_timestamp(self, ts: Any) -> str:
        """Bugunku mesajlarda saat, eski mesajlarda gun/ay da gosterilir.

        Yalnizca saat gostermek, dunden kalan gecmisi bugunmus gibi
        gosteriyordu. Ay adlari isletim sisteminin yerel ayarindan degil,
        secili arayuz dilinden gelir.
        """
        try:
            moment = datetime.fromtimestamp(float(ts))
        except Exception:  # noqa: BLE001
            return "--:--"
        clock = moment.strftime("%H:%M")
        if moment.date() == datetime.now().date():
            return clock
        month = t("chat.months").split()[moment.month - 1]
        return t("chat.date_format", day=moment.day, month=month, time=clock)

    def _is_following_latest(self) -> bool:
        """Kullanici en alttaysa (yeni mesajlari takip ediyorsa) True.

        Birkac piksellik tolerans var: Qt her zaman tam maximum degerini
        vermiyor.
        """
        bar = self.message_view.verticalScrollBar()
        return bar.value() >= bar.maximum() - 4

    def _scroll_to_bottom_if_following(self, was_following: bool) -> None:
        """Eski mesajlari okuyan kullaniciyi zorla asagi cekmez.

        Eskiden her yeni mesajda en alta atlaniyordu; gecmisi okurken biri
        yazdiginda okudugun yeri kaybediyordun.
        """
        if not was_following:
            return
        bar = self.message_view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _append_message(self, username: str, content: str, ts: Any = None, self_message: bool = False) -> None:
        was_following = self._is_following_latest()
        name = html.escape(username)
        body = html.escape(content)
        stamp = html.escape(self._format_timestamp(ts))
        # Kendi mesajin vurgulu, digerleri sakin. Saat once geliyor ama en
        # soluk olani o: goz once ada, sonra metne gitsin.
        # Kendi mesajin vurgulu, digerleri sakin. Saat once geliyor ama en
        # soluk olani o: goz once ada, sonra metne gitsin.
        color = "#ffffff" if self_message else "#dbdee1"
        weight = "700" if self_message else "600"
        # Yalnizca emojiden olusan kisa mesaj buyuk gosterilir. Aga giden sey
        # degismiyor -- bu tamamen bir gosterim karari (bkz. apps/proxychat/emoji.py).
        punto = display_size(content)
        govde = (
            f"<span style='font-size:{punto}pt;line-height:120%;'>{body}</span>"
            if punto
            else f"<span style='color:#b5bac1;'>{body}</span>"
        )
        self.message_view.append(
            f"<div style='margin:3px 0;'>"
            f"<span style='color:#72767d;font-size:8.5pt;'>{stamp}</span>"
            f"<span style='color:{color};font-weight:{weight};'>&nbsp;&nbsp;{name}</span>"
            # Iki nokta adin renginin koyusu: gri okunmuyordu, adla ayni
            # renk olunca da vurguyu paylasiyordu.
            f"<span style='color:{darken(color)};'>:</span>&nbsp;{govde}"
            f"</div>"
        )
        self._presence_tail = None
        self._scroll_to_bottom_if_following(was_following)

    def _append_system(self, text: str) -> None:
        was_following = self._is_following_latest()
        self.message_view.append(
            f"<div style='margin:3px 0;color:#6b6b6b;font-style:italic;"
            f"font-size:9.5pt;'>{html.escape(text)}</div>"
        )
        self._presence_tail = None
        self._scroll_to_bottom_if_following(was_following)

    def _remove_last_line(self) -> None:
        cursor = QTextCursor(self.message_view.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.deletePreviousChar()

    def _announce_room_move(self, user: str, away: bool) -> None:
        """Oda gecisini tek satirda gosterir.

        Ayni kisinin art arda git-gelleri yeni satir eklemez, son satir
        guncellenir. Arada baska bir satir yazildiysa yeni satir baslar.
        """
        tail = self._presence_tail
        if tail is not None and tail[0] == user and tail[2] != away:
            count = tail[1] + 1 if away else tail[1]
            self._remove_last_line()
        elif away:
            count = 1
        else:
            self._append_system(t("chat.user_returned", user=user))
            self._presence_tail = (user, 1, False)
            return

        if away:
            key = "chat.user_moved" if count == 1 else "chat.user_moved_many"
        else:
            key = "chat.user_moved_back" if count == 1 else "chat.user_moved_back_many"
        self._append_system(t(key, user=user, count=count))
        self._presence_tail = (user, count, away)

    def _append_log_entry(self, entry: dict[str, Any]) -> None:
        if entry["reason"] is not None:
            # core'un yer tutucusu yerine secili dildeki metin.
            self._append_system(f"{entry['user']}: {_undecryptable_text({'decrypt_reason': entry['reason']})}")
            return
        self._append_message(entry["user"], entry["content"], entry["ts"], entry["own"])

    def _render_room(self, room: str) -> None:
        """Odayi bellekteki mesajlarla bastan cizer.

        Sira: once gorulmus mesajlar, varsa "sen yokken yazilanlar gelmedi"
        notu, sonra katilma satiri ve sifreleme bildirimi.
        """
        self.message_view.clear()
        for entry in self._room_logs.get(room, []):
            self._append_log_entry(entry)
        if self._away_gap:
            self._append_system(t("chat.away_gap"))
        self._append_system(t("chat.joined_self", user=self._joined_user))
        self._append_encryption_notice()

    def forget_messages(self) -> None:
        """Oturum bitince bellekte tutulan mesajlar birakilir."""
        self._room_logs.clear()
        self._away_gap = False

    def on_packet(self, packet: dict[str, Any]) -> None:
        packet_type = packet.get("type")
        if packet_type == "joined":
            room = str(packet.get("room", self.current_room))
            self.current_room = room
            self.channel_title.setText(f"#{room}")
            self._set_channel_state("chat.connected")
            user = packet.get("user")
            if isinstance(user, str) and user:
                self._own_username = user
            self.message_view.clear()
            # Her "joined" yeni bir baslangic: sohbet sayfasi oturumlar arasinda
            # yeniden kullaniliyor. Eskiden liste yalnizca baska odaya geciste
            # sifirlaniyordu; ayni odaya yeniden baglaninca onceki oturumun
            # listesiyle karsilastirilip kisi kendini "katildi" diye goruyordu.
            self._known_users = None
            self._initial_users = set()
            self._verified_users = set()
            self._moved_away = set()
            self._joined_user = str(packet.get("user", "guest"))
            # Bu odada daha once gorulen mesajlar varsa geri getirilir; arada
            # yazilanlar gelmedigi icin bir not dusulur.
            self._away_gap = bool(self._room_logs.get(room))
            self._render_room(room)
            snapshot = packet.get("snapshot") or {}
            self._apply_snapshot(snapshot)
            self._ensure_room_item(room)
            self._select_room(room)
            return

        if packet_type == "history":
            room = str(packet.get("room", ""))
            if room != self.current_room:
                return
            # Sunucu gecmisi "joined"in hemen ardindan yollar. Bellekteki
            # kayitla birlestirilip oda bastan cizilir; ayni mesaj iki kez
            # gorunmez. Gecmis geldiyse aradaki bosluk da kapanmistir.
            log = self._room_logs.setdefault(room, [])
            seen = {_log_key(entry) for entry in log}
            messages = packet.get("messages")
            for message in messages if isinstance(messages, list) else ():
                if not isinstance(message, dict):
                    continue
                entry = _log_entry(message, own=False)
                if _log_key(entry) not in seen:
                    log.append(entry)
                    seen.add(_log_key(entry))
            log.sort(key=lambda entry: _sort_time(entry["ts"]))
            del log[:-ROOM_LOG_LIMIT]
            self._away_gap = False
            self._render_room(room)
            return

        if packet_type == "message":
            room = str(packet.get("room", self.current_room))
            if room != self.current_room:
                return

            username = str(packet.get("user", "guest"))
            # Istenen ad degil, sunucunun verdigi ad: aksi halde "ayse-2" olan
            # kullanicinin kendi her mesaji kendisine bildirim olarak geliyordu.
            own_message = username == (self._own_username or self.controller.username)

            entry = _log_entry(packet, own=own_message)
            log = self._room_logs.setdefault(room, [])
            log.append(entry)
            del log[:-ROOM_LOG_LIMIT]
            self._append_log_entry(entry)
            if packet.get("decrypt_failed"):
                return

            content = entry["content"]
            if not own_message:
                # Pencerenin onde olup olmadigina ana pencere karar verir.
                self.attention_requested.emit(username, content)
            return

        if packet_type == "room_list":
            rooms = packet.get("rooms", [])
            if isinstance(rooms, list):
                self.sync_rooms([str(room) for room in rooms])
            return

        if packet_type == "room_snapshot":
            room = str(packet.get("room", self.current_room))
            self._ensure_room_item(room)
            if room == self.current_room:
                self._apply_snapshot(packet)
            return

        if packet_type == "peers_verified":
            # Anahtar takasindan gelen kanit. Uye listesinden SONRA geliyor
            # (takas bir gidis-donus suruyor), o yuzden liste yeniden ciziliyor.
            users = packet.get("users")
            if isinstance(users, list):
                self._verified_users = {str(user) for user in users}
                self._render_user_list()
                # Katilma duyurusu dogrulamaya bagli ve dogrulama uye
                # listesinden SONRA geliyor; o yuzden burada tekrar bakiliyor.
                self._announce_membership_change(self._snapshot_users)
            return

        if packet_type == "error":
            # Sunucu "code" yolluyorsa metin secili dilde gosterilir; kodu
            # tanimiyorsak (daha yeni bir sunucu) sunucunun kendi metnine duser.
            code = packet.get("code")
            key = f"server_error.{code}"
            if isinstance(code, str) and has_text(key):
                self._append_system(t(key))
            else:
                self._append_system(str(packet.get("message", t("error.generic"))))

    def _apply_snapshot(self, snapshot: Any) -> None:
        # Paketi sunucu kuruyor ve zarf duz metin gidiyor: tur de dahil hicbir
        # seyine guvenilmez. Bozuk bir alan arayuzu yarim guncellenmis birakmasin.
        if not isinstance(snapshot, dict):
            snapshot = {}
        raw_users = snapshot.get("users")
        users = [str(user) for user in raw_users] if isinstance(raw_users, list) else []

        self._snapshot_users = users
        self._render_user_list()
        self._set_channel_state("chat.user_count_one" if len(users) == 1 else "chat.user_count", count=len(users))

        moved = snapshot.get("moved")
        self._announce_membership_change(users, moved if isinstance(moved, list) else ())

    def _is_verified(self, user: str) -> bool:
        """Bu kisi parolayi bildigini kanitladi mi?

        Parolasiz odada dogrulanacak bir sey yok, herkes gecerli sayilir.
        Kendi adimiz da her zaman gecerli.
        """
        return (
            not self.controller.encrypted
            or user in self._verified_users
            or user == self._own_username
        )

    def unverified_users(self) -> list[str]:
        """Listede gorunen ama kanit uretmemis kisiler."""
        return [u for u in self._snapshot_users if not self._is_verified(u)]

    def _render_user_list(self) -> None:
        """Uye listesini cizer; dogrulanmayanlari tek satirda toplar.

        Liste sunucudan geliyor, yani bir iddia (THREAT_MODEL 5.4-B). Kanit
        anahtar takasindan geliyor. Dogrulanmayanlari tek tek yazmak iki
        sebeple kotu: okurken gurultu, ve odaya girmek parola gerektirmedigi
        icin (5.5) biri binlerce sahte ad sokarsa liste kullanilamaz hale
        gelir. Bu yuzden hepsi tek bir sayac satirinda toplaniyor; adlar
        satira tiklayinca aciliyor.
        """
        self.user_list.clear()
        for user in self._snapshot_users:
            if not self._is_verified(user):
                continue
            item = QListWidgetItem(user)
            if self.controller.encrypted:
                item.setToolTip(t("chat.user_verified_hint"))
            self.user_list.addItem(item)

        dogrulanmayan = self.unverified_users()
        if not dogrulanmayan:
            self._unverified_expanded = False
            return

        anahtar, degerler = unverified_label(len(dogrulanmayan))
        sayac = QListWidgetItem(t(anahtar, **degerler))
        sayac.setToolTip(t("chat.unverified_hint"))
        sayac.setData(Qt.UserRole, _UNVERIFIED_ROW)
        self.user_list.addItem(sayac)
        if not self._unverified_expanded:
            return
        # Acik olsa bile adlarin tamami cizilmez: sahte kullanici seli
        # senaryosunda binlerce satir olusturmak arayuzu kilitlerdi.
        for user in dogrulanmayan[:UNVERIFIED_LIMIT]:
            item = QListWidgetItem(f"   {user}")
            item.setToolTip(t("chat.user_unverified_hint"))
            self.user_list.addItem(item)

    def _on_user_item_clicked(self, item: QListWidgetItem) -> None:
        if item.data(Qt.UserRole) != _UNVERIFIED_ROW:
            return
        self._unverified_expanded = not self._unverified_expanded
        self._render_user_list()

    def _announce_membership_change(self, users: list[str], moved: Any = ()) -> None:
        """Kullanici listesindeki degisimi sohbet akisinda duyurur.

        Ayri bir paket tipine gerek yok: sunucu zaten her uyelik degisiminde
        oda anlik goruntusu yolluyor, fark buradan cikariliyor.

        Odaya ilk girildiginde kimse duyurulmaz -- yoksa mevcut herkes o anda
        katilmis gibi gorunurdu.
        """
        current = set(users)
        # Duyurulacak olanlar, listede gorunenlerin hepsi degil: sifreli odada
        # yalnizca parolayi bildigini kanitlamis olanlar. Sahte kullanici seli
        # sohbeti "X kanala katildi" satirlariyla doldurabilirdi ve o satirlar
        # sunucunun iddiasindan baska bir seye dayanmiyordu (THREAT_MODEL 5.4-B).
        duyurulabilir = {u for u in current if self._is_verified(u)}
        if self._known_users is None:
            if not current:
                # Bos bir uye listesi taban cizgisi olamaz: kendimiz her zaman
                # odadayiz. `joined` paketi anlik goruntusuz gelirse boyle
                # oluyordu ve sonraki gercek listede herkes yeni katilmis gibi
                # duyuruluyordu.
                return
            self._known_users = duyurulabilir
            self._initial_users = set(current)
            return

        moved_users = {str(user) for user in moved}
        for user in sorted(duyurulabilir - self._known_users):
            if user in self._initial_users:
                # Biz gelmeden once buradaydi; el sikismasinin simdi bitmesi
                # onun yeni geldigi anlamina gelmiyor.
                continue
            if user in self._moved_away:
                # Baska odaya gecmisti, geri geldi.
                self._moved_away.discard(user)
                self._announce_room_move(user, away=False)
            else:
                self._append_system(t("chat.user_joined", user=user))
        for user in sorted(self._known_users - current):
            # Cikti: bir daha gelirse bu kez gercekten katilmis olur.
            self._initial_users.discard(user)
            if user in moved_users:
                # Baglantiyi kesmedi, baska odaya gecti. Bu arada buraya
                # yazilanlar ona ulasmaz, o yuzden yine de gosterilir.
                self._moved_away.add(user)
                self._announce_room_move(user, away=True)
            else:
                self._moved_away.discard(user)
                self._append_system(t("chat.user_left", user=user))
        # Ayrilma anlik goruntuye gore, katilma dogrulamaya gore. Daha once
        # duyurulmus ve hala odada olanlar korunuyor.
        self._known_users = (self._known_users & current) | duyurulabilir

    def show_connected(self, payload: dict[str, Any]) -> None:
        """Oturum ayrintilarini gosterir: adres, sifreleme durumu, paylasilacak adres.

        Ayrintilar denetleyicinin "connected" sinyalinden gelir. Eskiden
        istemcinin kendi "connected" durum paketinden okunuyordu; o pakette
        sifreleme ve paylasilacak adres bilgisi hic yoktu. Bu yuzden gosterge
        parola girilse de hep "Oda parolasi yok" diyordu ve Host'un
        paylasacagi adres hic gorunmuyordu.
        """
        port = payload.get("port", DEFAULT_PORT)
        self._encrypted = bool(payload.get("encrypted", False))
        self._connection_state = (
            "connected",
            {"host": str(payload.get("host", "")), "port": port, "encrypted": self._encrypted},
        )
        self._render_connection_status()
        self._append_encryption_notice()
        share_ips = payload.get("share_ips", [])
        self._hint_state = ("share", {"ips": list(share_ips), "port": port}) if share_ips else ("chat.ready", {})
        self._render_server_hint()
        self._set_controls_enabled(True)

    def _append_encryption_notice(self) -> None:
        # "joined" paketi oturum ayrintilarindan once de sonra da gelebilir;
        # hangisi sonra gelirse bildirimi o yazar, ekranda hep bir tane kalir.
        if self._encrypted is None:
            return
        self._append_system(t("chat.encrypted_notice" if self._encrypted else "chat.plain_notice"))

    def on_status(self, state: str, payload: dict[str, Any]) -> None:
        # "connected" burada islenmez: istemcinin durum paketi oturum
        # ayrintilarini tasimiyor; pencere show_connected()'i cagiriyor.
        if state == "disconnected":
            self._encrypted = None
            self._own_username = None
            self._connection_state = ("chat.closed", {})
            self._render_connection_status()
            self._set_controls_enabled(False)
            return

        if state == "error":
            self._append_system(str(payload.get("error", t("error.connection"))))

    def show_reconnecting(self, attempt: int, total: int) -> None:
        self._connection_state = ("chat.reconnecting_status", {"attempt": attempt, "total": total})
        self._render_connection_status()
        self._append_system(t("chat.reconnecting_notice", attempt=attempt, total=total))
        self._set_controls_enabled(False)

    def show_reconnected(self) -> None:
        self._append_system(t("chat.reconnected"))

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.message_input.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.room_list.setEnabled(enabled)
        self.add_room_button.setEnabled(enabled)
        self.new_room_edit.setEnabled(enabled)


class ProxyChatWindow(QMainWindow):
    def __init__(self, settings: ChatSettings | None = None) -> None:
        super().__init__()
        self.settings = settings if settings is not None else ChatSettings()
        # Sayfalar kurulurken metinleri okudugu icin dil onlardan once ayarlanir.
        set_language(self.settings.load_language())
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1450, 920)

        self.controller = ConnectionController()
        self.stack = QStackedWidget()
        self.connect_page = ConnectPage(self.settings)
        self.chat_page = ChatPage(self.controller)
        self.stack.addWidget(self.connect_page)
        self.stack.addWidget(self.chat_page)

        # Dil secimi pencerenin sag ustunde, iki sayfada da ayni yerde durur.
        # Dunya simgesi, arayuz dilini okuyamayan birinin de kutuyu bulmasi icin.
        self.language_box = QComboBox()
        self.language_box.setObjectName("languageBox")
        for code, name in LANGUAGES.items():
            self.language_box.addItem(f"🌐  {name}", code)
        self.language_box.setCurrentIndex(self.language_box.findData(current_language()))
        self.language_box.currentIndexChanged.connect(self._on_language_selected)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(24, 14, 24, 0)
        top_bar.addStretch(1)
        top_bar.addWidget(self.language_box)
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addLayout(top_bar)
        central_layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self._last_connection: tuple[Any, ...] | None = None
        self._reconnect_attempt = 0
        self._reconnect_busy_waits = 0
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._try_reconnect)

        self.connect_page.connect_requested.connect(self._start_connection)
        self.controller.connected.connect(self._on_connected)
        self.controller.connection_failed.connect(self._on_connect_failed)
        self.controller.packet_received.connect(self.chat_page.on_packet)
        self.controller.status_changed.connect(self.chat_page.on_status)
        # chat_page'den SONRA baglanmali: durum metnini bu yazsin.
        self.controller.status_changed.connect(self._on_status)
        self.chat_page.leave_requested.connect(self._leave_session)
        # Sesli sohbet: sinyallesme ayni TCP kanalindan, ses ayri UDP yolundan.
        self.voice = VoiceController(self.controller)
        self.controller.packet_received.connect(self.voice.on_packet)
        self.chat_page.voice_toggle_requested.connect(self._toggle_voice)
        self.chat_page.voice_mute_changed.connect(self.voice.set_muted)
        self.chat_page.voice_gate_changed.connect(self.voice.set_noise_gate)
        self.chat_page.voice_gate_changed.connect(
            lambda acik: self.settings.save_voice_gate(enabled=acik)
        )
        self.chat_page.voice_threshold_changed.connect(self.voice.set_gate_threshold)
        self.chat_page.voice_threshold_changed.connect(
            lambda esik: self.settings.save_voice_gate(threshold=esik)
        )
        self.voice.level_updated.connect(self.chat_page.set_voice_level)
        # Kayitli kapi ayari: ses her acildiginda yeniden ayarlanmasin.
        gate_enabled, gate_threshold = self.settings.load_voice_gate()
        self.chat_page.voice_gate_box.setChecked(gate_enabled)
        self.chat_page.set_voice_threshold(gate_threshold)
        self.voice.set_noise_gate(gate_enabled)
        if gate_threshold:
            self.voice.set_gate_threshold(gate_threshold)
        # Ses cihazlari: kayitli secim hemen yuklenir (sese katilinca o cihaz
        # acilsin), ama LISTE ilk ihtiyacta okunur -- satir acilinca, ipucu
        # istenince ya da sese katilinca. Acilista okumak QtMultimedia'yi
        # yukleyip paketlenmis exe'nin acilisini uzatiyordu. Cihaz kaynagina
        # modul uzerinden erisiliyor ki testler sabit bir liste koyabilsin.
        giris, cikis = self.settings.load_voice_devices()
        self.voice.set_devices(input_id=giris, output_id=cikis)
        self._voice_devices_loaded = False
        self.chat_page.voice_devices_needed.connect(self._ensure_voice_devices)
        self.voice.state_changed.connect(
            lambda durum: durum == "on" and self._ensure_voice_devices()
        )
        self.chat_page.voice_input_device_changed.connect(
            lambda kimlik: self._choose_voice_device(input_id=kimlik)
        )
        self.chat_page.voice_output_device_changed.connect(
            lambda kimlik: self._choose_voice_device(output_id=kimlik)
        )
        self.voice.state_changed.connect(self.chat_page.set_voice_state)
        self.voice.peers_changed.connect(self.chat_page.set_voice_peers)
        self.voice.failed.connect(self.chat_page.set_voice_error)
        self.chat_page.attention_requested.connect(self._on_attention_requested)

        self.tray_icon = self._build_tray_icon()
        self.language_box.setToolTip(t("window.language"))
        # Odak zinciri dil kutusuyla basliyordu: pencere acilinca kutu vurgulu
        # geliyor ve ilk tus vurusu dili degistirebiliyordu. Acilista ad yazilir.
        self.connect_page.username_edit.setFocus()

    def _toggle_voice(self) -> None:
        """Ayni dugme: sesteysek ayril, degilsek katil."""
        if self.voice.state == "off":
            self.voice.join()
        else:
            self.voice.leave()

    def _ensure_voice_devices(self) -> None:
        """Cihaz listesini ilk ihtiyacta bir kez okur ve izlemeye baslar."""
        if self._voice_devices_loaded:
            return
        self._voice_devices_loaded = True
        self._refresh_voice_devices()
        voice_module.audio_devices.watch(self, self._refresh_voice_devices)

    def _refresh_voice_devices(self) -> None:
        """Cihaz listesini tazeler; secili gosterilen, kontrolcudeki istek.

        Kulaklik cikarilinca listeden duser ve "sistem varsayilani" gorunur;
        geri takilinca bu cagri onu yeniden secili getirir. Kayda dokunmaz.
        """
        girisler, cikislar = voice_module.audio_devices.list()
        self.chat_page.set_voice_devices(
            girisler, cikislar, self.voice.input_device, self.voice.output_device
        )
        # Gorusme suruyorsa ve kart cikarilan bir cihazdaysa kontrolcu onu
        # yeniden acar (bkz. VoiceController.on_devices_changed).
        self.voice.on_devices_changed(
            {kimlik for kimlik, _ad in girisler}, {kimlik for kimlik, _ad in cikislar}
        )

    def _choose_voice_device(
        self, *, input_id: bytes | None = None, output_id: bytes | None = None
    ) -> None:
        """Kullanici cihaz secti: uygula, sonra GERCEKTE kullanilani kaydet.

        Gorusme sirasinda yeni cihaz acilamazsa kontrolcu eskisine doner.
        Arayuz ve kayit istenene degil, kullanilana uymali; yoksa liste bir
        cihazi gosterirken ses baskasindan gelir.
        """
        self.voice.set_devices(input_id=input_id, output_id=output_id)
        giris, cikis = self.voice.input_device, self.voice.output_device
        self.chat_page.select_voice_devices(giris, cikis)
        self.settings.save_voice_devices(input_id=giris, output_id=cikis)

    def _on_language_selected(self, index: int) -> None:
        """Dil aninda uygulanir ve saklanir; yeniden baslatma gerekmez."""
        code = self.language_box.itemData(index)
        if not isinstance(code, str):
            return
        set_language(code)
        self.settings.save_language(code)
        self.retranslate()

    def retranslate(self) -> None:
        self.language_box.setToolTip(t("window.language"))
        self.connect_page.retranslate()
        self.chat_page.retranslate()

    def _build_tray_icon(self) -> QSystemTrayIcon | None:
        """Bildirim balonu icin tepsi ikonu. Tepsi yoksa None doner."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return None
        icon = QIcon(resource_path("assets", "ProxyChat.ico"))
        if icon.isNull():
            icon = self.windowIcon()
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip(APP_NAME)
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        return tray

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show()
            self.raise_()
            self.activateWindow()

    def _on_attention_requested(self, username: str, content: str) -> None:
        """Pencere onde degilse kullaniciyi uyarir.

        Pencere zaten aktifse hicbir sey yapilmaz: kullanici mesaji gormus
        demektir, gorev cubugunu yanip sondurmek rahatsiz edici olur.
        """
        if self.isActiveWindow():
            return

        application = QApplication.instance()
        if application is not None:
            # Gorev cubugu dugmesini yanip sondurur.
            application.alert(self, 0)

        if self.tray_icon is not None:
            if self.controller.encrypted:
                # Windows bildirimleri Bildirim Merkezi'nin veritabanina, yani
                # diske yazar ve kilit ekraninda gorunebilir. Sifreli odada
                # cozulmus metni oraya vermek "mesajlar diske yazilmaz"
                # sozunu bozardi; yalnizca kimin yazdigi gider.
                preview = t("tray.content_hidden")
            else:
                preview = content if len(content) <= 120 else content[:117] + "..."
            self.tray_icon.showMessage(t("tray.wrote", user=username), preview, QSystemTrayIcon.MessageIcon.Information, 4000)

    def _start_connection(self, mode: str, host: str, port: int, room: str, username: str, room_password: str) -> None:
        self.controller.keep_history = self.connect_page.keep_history_box.isChecked()
        self._last_connection = (mode, host, port, room, username, room_password)
        self._reconnect_attempt = 0
        self._reconnect_busy_waits = 0
        self.connect_page.set_busy(True)
        self.controller.connect_async(mode, host, port, room, username, room_password)

    def _on_status(self, state: str, payload: dict[str, Any]) -> None:
        if state != "disconnected" or payload.get("intentional"):
            return
        if self.stack.currentWidget() is not self.chat_page:
            return
        self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        if self._reconnect_timer.isActive():
            return
        if self._last_connection is None:
            self._return_to_connect_page("connect.connection_lost")
            return

        self._reconnect_attempt += 1
        if self._reconnect_attempt > RECONNECT_ATTEMPTS:
            self._return_to_connect_page("connect.reconnect_gave_up", attempts=RECONNECT_ATTEMPTS)
            return

        self.chat_page.show_reconnecting(self._reconnect_attempt, RECONNECT_ATTEMPTS)
        self._reconnect_timer.start(RECONNECT_DELAY_MS)

    def _try_reconnect(self) -> None:
        if self._last_connection is None:
            return

        if self.controller.busy:
            # Onceki deneme hala suruyor (Host modunda 30 saniyeyi bulabiliyor).
            # Eskiden burada connect_async sessizce geri donuyor, hicbir sinyal
            # yayilmadigi icin zincir kopuyor ve kullanici kilitli ekranda
            # kaliyordu. Simdi deneme HAKKI YAKILMADAN tekrar bakiliyor.
            self._reconnect_busy_waits += 1
            if self._reconnect_busy_waits <= MAX_RECONNECT_BUSY_WAITS:
                self._reconnect_timer.start(RECONNECT_DELAY_MS)
                return
            self._return_to_connect_page("connect.previous_attempt_pending")
            return

        self._reconnect_busy_waits = 0
        # Once eski oturumu tamamen kapat: Host modunda sunucu hala ayakta
        # olabilir ve ayni porta yeniden baglanmak "port kullanimda" hatasi verir.
        self.controller.disconnect()
        # Ilk baglanilan oda degil, kullanicinin su an bulundugu oda: eskiden
        # "oyun"a gecmis biri baglanti yenilenince "general"e donuyordu.
        mode, host, port, _first_room, username, room_password = self._last_connection
        room = self.chat_page.current_room
        if not self.controller.connect_async(mode, host, port, room, username, room_password):
            self._reconnect_timer.start(RECONNECT_DELAY_MS)

    def _leave_session(self) -> None:
        self._reconnect_timer.stop()
        self._reconnect_attempt = 0
        self._return_to_connect_page(None)

    def _return_to_connect_page(self, status_key: str | None, **values: Any) -> None:
        self._reconnect_timer.stop()
        # Odadan cikarken ses de kapanir: soket ve ses karti birakilir.
        self.voice.leave()
        self.controller.disconnect()
        self.chat_page.forget_messages()
        self.stack.setCurrentWidget(self.connect_page)
        self.connect_page.set_busy(False)
        self.connect_page.set_status(status_key, **values)

    def _on_connected(self, payload: dict[str, Any]) -> None:
        reconnected = self._reconnect_attempt > 0
        self._reconnect_attempt = 0
        self._reconnect_busy_waits = 0
        self._reconnect_timer.stop()

        room = str(payload.get("room", "general"))
        self.chat_page.current_room = room
        self.chat_page.channel_title.setText(f"#{room}")
        self.chat_page.mark_connected()
        self.chat_page.show_connected(payload)
        self.stack.setCurrentWidget(self.chat_page)
        self.chat_page.switch_room(room)
        if reconnected:
            self.chat_page.show_reconnected()
        self.connect_page.set_status("connect.connected")
        self.connect_page.set_busy(False)
        # Yalnizca calistigi kanitlanmis degerler saklanir.
        self.connect_page.save_settings()

    def _on_connect_failed(self, message: str) -> None:
        if self.stack.currentWidget() is self.chat_page:
            # Yeniden baglanma denemesi basarisiz oldu; kullaniciyi baglanti
            # ekranina firlatmak yerine bir sonraki denemeyi planla.
            self._schedule_reconnect()
            return
        self.connect_page.show_error(message)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.tray_icon is not None:
            self.tray_icon.hide()
        self.voice.leave()
        self.controller.disconnect()
        super().closeEvent(event)


def build_stylesheet() -> str:
    return """
        QWidget {
            background: #313338;
            color: #f2f3f5;
            font-family: "Segoe UI";
            font-size: 10.5pt;
        }
        /* Etiketler ve kutucuklar kendi zeminlerini boyamamali: QWidget
           kuralindaki #313338, kartlarin koyu zemini uzerine acik renkli
           dikdortgenler basiyordu. Bos bir etiket bile serit gibi
           gorunuyordu. */
        QLabel, QCheckBox, QWidget#passwordRow, QWidget#addressRow, QWidget#voiceDevicesSection {
            background: transparent;
        }
        /* Uretilen parolanin nasil paylasilacagi: uyari degil, dikkat cekici not. */
        QLabel#passwordNotice {
            color: #f0b232;
        }
        QFrame#brandCard, QFrame#formCard, QFrame#sidebar, QFrame#centerPanel {
            background: #2b2d31;
            border: 1px solid #1f2125;
            border-radius: 18px;
        }
        QLabel#brandTitle {
            font-size: 28pt;
            font-weight: 800;
            color: #f2f3f5;
        }
        QLabel#brandSubtitle {
            font-size: 11.5pt;
            color: #b5bac1;
        }
        QLabel#brandVersion {
            font-size: 10pt;
            color: #8b9098;
        }
        QLabel#brandHint, QLabel#tinyStatus, QLabel#channelStatus {
            color: #b5bac1;
        }
        QLabel#sectionTitle {
            font-size: 15pt;
            font-weight: 700;
            color: #f2f3f5;
        }
        QLabel#sidebarBrand {
            font-size: 18pt;
            font-weight: 800;
            color: #f2f3f5;
        }
        QLabel#sidebarSection {
            font-size: 10pt;
            font-weight: 700;
            letter-spacing: 1px;
            color: #b5bac1;
            margin-top: 4px;
        }
        QLabel#channelTitle {
            font-size: 20pt;
            font-weight: 800;
            color: #f2f3f5;
        }
        QLabel#statusLabel {
            color: #ed4245;
        }
        QTextBrowser#shareBox, QTextBrowser#hintBox {
            background: #2b2d31;
            border: 1px solid #1f2125;
            border-radius: 14px;
            padding: 10px;
            color: #f2f3f5;
        }
        /* Sohbet bir kutu degil, sayfanin kendisi. Koyu kartin icindeki koyu
           kart, mesajlar azken kocaman bir bosluk gibi duruyordu. */
        QTextBrowser#messageView {
            background: transparent;
            border: none;
            padding: 4px 2px;
            color: #f2f3f5;
            font-size: 10.5pt;
        }
        QLineEdit, QComboBox {
            background: #383A40;
            border: 1px solid #1f2125;
            border-radius: 12px;
            padding: 9px 10px;
            selection-background-color: #cfd7e2;
            color: #f2f3f5;
        }
        /* Listeler panelin uzerinde duruyor, ayri bir kutu degil: uc oge icin
           470 piksellik bos cerceve cizmenin anlami yoktu. */
        QListWidget {
            background: transparent;
            border: none;
            padding: 0px;
            selection-background-color: transparent;
            color: #f2f3f5;
        }
        /* Sag ustteki dil secimi: form alanlarindan kucuk, goze batmayan. */
        QComboBox#languageBox {
            background: #2b2d31;
            padding: 5px 10px;
            border-radius: 10px;
            font-size: 9.5pt;
            min-width: 110px;
        }
        QListWidget::item {
            padding: 6px 10px;
            margin: 1px 0px;
            border-radius: 8px;
            color: #b5bac1;
        }
        QListWidget::item:hover {
            background: #35373d;
            color: #f2f3f5;
        }
        /* Secili kanal gercekten secili gorunsun: eskiden secili (#40444b) ile
           uzerine gelme (#3f4248) neredeyse ayni tondu. */
        QListWidget::item:selected {
            background: #404aa8;
            color: #ffffff;
        }
        QLineEdit:focus, QComboBox:focus, QListWidget:focus, QTextBrowser:focus {
            border: 1px solid #5865f2;
        }
        QListWidget {
            alternate-background-color: #313338;
        }
        QPushButton {
            background: #4f545c;
            border: 1px solid #1f2125;
            border-radius: 12px;
            padding: 9px 14px;
            color: #f2f3f5;
        }
        QPushButton:hover {
            background: #5b6068;
        }
        QPushButton:pressed {
            background: #454b53;
        }
        QPushButton:disabled {
            color: #8b9098;
            background: #3a3d44;
        }
        /* Birincil eylemler: gozun gidecegi tek renkli nokta. */
        QPushButton#primaryButton {
            background: #5865f2;
            border: 1px solid #4752c4;
            font-weight: 600;
        }
        QPushButton#primaryButton:hover {
            background: #6874f5;
        }
        QPushButton#primaryButton:pressed {
            background: #4752c4;
        }
        QPushButton#primaryButton:disabled {
            background: #3a3d44;
            border: 1px solid #1f2125;
            color: #8b9098;
        }
        /* Kullanici listesinde adlarin alti cizgili: kimin nerede bittigi
           belli olsun. Yalnizca bu listede -- kanal listesinde secili oge
           zaten belli, orada cizgi gurultu olurdu. */
        QListWidget#userList::item {
            border-bottom: 1px solid rgba(255, 255, 255, 0.16);
            border-radius: 0px;
            margin: 0px;
            padding: 7px 10px;
        }
        QListWidget#userList::item:last {
            border-bottom: none;
        }
        /* Sag kenarin iki karti bir kapsayicida duruyor; kapsayici kendi
           zeminini boyamamali, yoksa kartlarin arasi serit gibi gorunur. */
        QFrame#sidebarStack {
            background: transparent;
            border: none;
        }
        /* Ses katilimcilari kendi cercevesinde: kullanici listesinden ayri
           bir sey oldugu belli olsun. */
        QListWidget#voiceList {
            background: #232428;
            border: 1px solid #1f2125;
            border-radius: 10px;
            padding: 4px;
        }
        QListWidget#voiceList::item {
            border-radius: 6px;
            padding: 5px 8px;
        }
        /* Emoji seciciisi: sohbetin uzerinde duran kucuk bir panel. */
        QWidget#emojiPicker {
            background: #2b2d31;
            border: 1px solid #1f2125;
            border-radius: 14px;
        }
        QPushButton#emojiCell {
            background: transparent;
            border: none;
            border-radius: 8px;
            font-size: 16pt;
            padding: 0px;
        }
        QPushButton#emojiCell:hover {
            background: #3f4248;
        }
        QPushButton#emojiButton {
            font-size: 13pt;
            padding: 6px 0px;
        }
        /* Ac/kapa satiri: bir kerelik ayarlari saklayan ince metin. Dolu bir
           dugme gibi dursa "Sese katil"in yaninda ikinci bir eylem sanilirdi. */
        QPushButton#disclosureButton,
        QPushButton#disclosureButton:hover,
        QPushButton#disclosureButton:pressed,
        QPushButton#disclosureButton:checked {
            background: transparent;
            border: none;
            padding: 2px 0px;
            color: #b5bac1;
            text-align: left;
        }
        QPushButton#disclosureButton:hover {
            color: #f2f3f5;
        }
        /* Ses olcer ve esik: geri kalaniyla ayni dilde olsun. Ham Qt
           gorunumu (ince mavi cizgi, varsayilan tutamac) yamali duruyordu. */
        QProgressBar#voiceLevel {
            background: #232428;
            border: none;
            border-radius: 4px;
        }
        QProgressBar#voiceLevel::chunk {
            background: #3ba55d;
            border-radius: 4px;
        }
        QSlider::groove:horizontal {
            background: #232428;
            height: 4px;
            border-radius: 2px;
        }
        QSlider::sub-page:horizontal {
            background: #5865f2;
            border-radius: 2px;
        }
        QSlider::handle:horizontal {
            background: #f2f3f5;
            width: 14px;
            height: 14px;
            margin: -6px 0;
            border-radius: 7px;
        }
        QSlider::handle:horizontal:disabled {
            background: #6b6f76;
        }
    """


def run_app(splash: QSplashScreen | None = None, splash_shown_at: float | None = None) -> int:
    """Uygulamayi calistirir.

    app.py acilis ekranini bu modul ice aktarilmadan ONCE gosterip buraya
    veriyor (bkz. splash.py). `python -m apps.proxychat` yolu vermiyor; o
    zaman ekran burada gosterilir.
    """
    app = QApplication.instance() or QApplication([])
    if splash is None:
        splash = build_splash_screen(app)
        splash.show()
        splash.raise_()
        splash_shown_at = time.monotonic()
    elif splash_shown_at is None:
        # Ekran verilmis ama ne zaman gosterildigi verilmemis: simdiden say.
        # Eskiden burada None'dan cikarma yapilip acilis cokuyordu.
        splash_shown_at = time.monotonic()

    settings = ChatSettings()
    # Tanilama kaydi varsayilan kapali; yalnizca kullanici actiysa dosya acilir.
    set_logging_enabled(bool(settings.load()["logging_enabled"]))
    app.setStyleSheet(build_stylesheet())

    window = ProxyChatWindow(settings)

    def reveal_window() -> None:
        window.show()
        window.raise_()
        splash.finish(window)

    # Acilis ekrani EN AZ SPLASH_DURATION_SECONDS gorunur; ice aktarmalar ve
    # pencere kurulumu zaten o kadar surduyse hemen. Eskiden bu iki saniye
    # kurulumun USTUNE ayrica bekleniyordu. Zamanlayici, time.sleep degil:
    # beklerken olay dongusu calisir, pencere "yanit vermiyor"a dusmez.
    QTimer.singleShot(remaining_splash_ms(time.monotonic() - splash_shown_at), reveal_window)
    return app.exec()
