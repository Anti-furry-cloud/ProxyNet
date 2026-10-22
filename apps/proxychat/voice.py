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

"""Sesli sohbetin uygulama tarafi: ses karti ve katilim yonetimi.

Katilim iki adim (bkz. `core/voice_relay.py`):

1. `voice_join` -> Host kimlik ve jeton verir (`voice_joined`). Paket bizim
   gecici acik anahtarimizi da tasir; digerleri ses anahtarini kimden
   turetecegini bununla buluyor.
2. Kimlik gelince oturum kurulur, tuzu `voice_salt` ile duyurulur.

Sonra UDP soketi acilir, Host'a merhaba yollanir ve ses akmaya baslar.
Odadaki digerleri `voice_peers` ile ogrenilir; herkesin oturum tuzu ve acik
anahtari oradan gelir. Kimsenin IP'si gorulmez, ses Host uzerinden aktarilir.

Ses anahtari paroladan degil oda oturumundan turuyor (1.10.0), yani metin
gibi ileri gizli. Esin metin el sikismasi ses katilimindan sonra bitebilir;
o durumda es sessizce atlanir ve anahtar gelince katilimci listesi yeniden
islenir -- eksik anahtar hata degil, gecici bir durum.

Ses karti katmani (``VoiceAudio``) ayri tutuldu: testler kontrolcuyu sahte
bir ses cihaziyla calistirip donanim acmadan sinayabiliyor.
"""

from __future__ import annotations

import base64

from typing import Any, Callable

from PySide6.QtCore import QObject, QTimer, Signal

from core.voice_codec import FRAME_PCM_BYTES, SAMPLE_RATE, available_codec, choose_codec, silence
from core.voice_crypto import SenderKeyMissingError
from core.voice_gate import NoiseGate
from core.voice_net import VoiceLink
from core.voice_packet import FRAME_MS
from core.voice_session import VoiceSession

#: Ses kartinin kendi tamponu (cerceve sayisi). Buyuk tampon gecikmeyi
#: artirir; prototipte olculen deger bu.
DEVICE_BUFFER_FRAMES = 4

#: Sayilarin arayuze tazelenme araligi (ms).
STATS_INTERVAL_MS = 1000

#: Seviye cubugunun tazelenme araligi (ms). Goz icin 100 ms yeterli;
#: her cerceveyi (20 ms) yayinlamak arayuzu bosuna mesgul ederdi.
LEVEL_INTERVAL_MS = 100

#: voice_joined bu sure icinde gelmezse katilim birakilir (ms). Eski bir
#: sunucu (1.7.0 ve oncesi) voice_join paketini tanimiyor ve hic cevap
#: vermiyor; kullanici "katiliniyor" yazisinda asili kalmasin.
JOIN_TIMEOUT_MS = 5000

#: Bir ses cihazi: (kimlik, ekranda gorunen ad). Kimlik bos bayt ise
#: "sistem varsayilani" demek.
AudioDevice = tuple[bytes, str]


def pick_device(devices: list[Any], wanted: bytes, default: Any) -> Any:
    """Istenen cihaz hala takiliysa onu, degilse sistem varsayilanini dondurur.

    Kayitli kulaklik cikarilmis olabilir; o durumda hata vermek yerine
    varsayilana dusulur. Kayit SILINMEZ: kulaklik geri takilinca yine o
    secilir (bkz. arayuzdeki cihaz listesi).
    """
    if wanted:
        for cihaz in devices:
            if bytes(cihaz.id()) == wanted:
                return cihaz
    return default


class SystemAudioDevices:
    """Isletim sisteminin ses cihazlari.

    QtMultimedia ilk kullanimda yukleniyor (~0,5 sn, surec basina bir kez).
    Testler bu nesnenin yerine sabit bir liste koyuyor (bkz. conftest.py):
    sonuclar makinedeki donanima bagli olmasin.
    """

    def __init__(self) -> None:
        self._watcher: Any | None = None

    def list(self) -> tuple[list[AudioDevice], list[AudioDevice]]:
        """Takili cihazlar: (girisler, cikislar). Yuklenemezse ikisi de bos."""
        try:
            from PySide6.QtMultimedia import QMediaDevices
        except ImportError:  # pragma: no cover - paketlenmemis Qt
            return [], []
        girisler = [(bytes(d.id()), d.description()) for d in QMediaDevices.audioInputs()]
        cikislar = [(bytes(d.id()), d.description()) for d in QMediaDevices.audioOutputs()]
        return girisler, cikislar

    def watch(self, parent: QObject, callback: Callable[[], None]) -> None:
        """Kulaklik takilip cikarildiginda `callback` cagrilir."""
        try:
            from PySide6.QtMultimedia import QMediaDevices
        except ImportError:  # pragma: no cover - paketlenmemis Qt
            return
        # Sinyaller ornek uzerinde; nesne yasadigi surece dinliyor.
        self._watcher = QMediaDevices(parent)
        self._watcher.audioInputsChanged.connect(callback)
        self._watcher.audioOutputsChanged.connect(callback)


#: Arayuzun kullandigi cihaz kaynagi. Testler bunu degistiriyor.
audio_devices = SystemAudioDevices()


class VoiceAudio:
    """Mikrofonu oturuma, oturumu hoparlore baglar.

    Calma hizini **ses karti** belirler: kartta bir cerceve kadar yer
    acildikca bir cerceve yazilir. Zamanlayiciyla yazmak Windows'ta
    gecikmeyi buyutuyordu (prototipte olculdu).

    `input_id` / `output_id` bos ise sistem varsayilani kullanilir. Kayitli
    cihaz takili degilse de varsayilana dusulur (`pick_device`).
    """

    def __init__(
        self,
        session: VoiceSession,
        send_frame: Callable[[bytes], None],
        input_id: bytes = b"",
        output_id: bytes = b"",
    ) -> None:
        from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QAudioSource, QMediaDevices

        self.session = session
        self._send_frame = send_frame
        self.muted = False
        #: Konusma yokken mikrofonu sessizlestirir (klavye sesi, cizirti).
        #: Akisi durdurmaz; sessizlik cercevesi yine gider.
        self.gate = NoiseGate()

        bicim = QAudioFormat()
        bicim.setSampleRate(SAMPLE_RATE)
        bicim.setChannelCount(1)
        bicim.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        mikrofon = pick_device(
            QMediaDevices.audioInputs(), input_id, QMediaDevices.defaultAudioInput()
        )
        hoparlor = pick_device(
            QMediaDevices.audioOutputs(), output_id, QMediaDevices.defaultAudioOutput()
        )
        if not mikrofon.isFormatSupported(bicim) or not hoparlor.isFormatSupported(bicim):
            raise VoiceDeviceError("audio_format")
        #: GERCEKTE acilan cihazlar (istenen degil: istenen takili degilse
        #: varsayilan acilir). Gorusmede cihaz listesi degisince kartin
        #: kaybolan bir cihazda kalip kalmadigi buna bakilarak anlasiliyor.
        self.input_device_id = bytes(mikrofon.id())
        self.output_device_id = bytes(hoparlor.id())

        self._source = QAudioSource(mikrofon, bicim)
        self._sink = QAudioSink(hoparlor, bicim)
        self._input = self._source.start()
        self._sink.setBufferSize(FRAME_PCM_BYTES * DEVICE_BUFFER_FRAMES)
        self._output = self._sink.start()
        self._pending = b""
        self._input.readyRead.connect(self._on_microphone)
        self._playback = QTimer()
        self._playback.timeout.connect(self._on_speaker)
        self._playback.start(5)

    def _on_microphone(self) -> None:
        self._pending += bytes(self._input.readAll())
        while len(self._pending) >= FRAME_PCM_BYTES:
            frame, self._pending = self._pending[:FRAME_PCM_BYTES], self._pending[FRAME_PCM_BYTES:]
            # Susturuldugunda da cerceve gider: akisin durmasi kimin ne zaman
            # konustugunu aga soylerdi (bkz. plan §2.2).
            self._send_frame(silence() if self.muted else self.gate.process(frame))

    def _on_speaker(self) -> None:
        while self._sink.bytesFree() >= FRAME_PCM_BYTES:
            self._output.write(self.session.play())

    def stop(self) -> None:
        self._playback.stop()
        self._source.stop()
        self._sink.stop()


class VoiceDeviceError(RuntimeError):
    """Ses cihazi istenen bicimi desteklemiyor."""


class VoiceController(QObject):
    """Sesli sohbete katilma, ayrilma ve durum bildirimi."""

    #: "off", "joining", "on"
    state_changed = Signal(str)
    #: Odada seste olanlarin adlari.
    peers_changed = Signal(list)
    #: Hata anahtari (i18n): "voice_device", "voice_device_switch" (yeni cihaz
    #: acilamadi, gorusme eskisiyle suruyor), "voice_not_connected".
    failed = Signal(str)
    #: Her saniye: `VoiceSession.stats()`.
    stats_updated = Signal(dict)
    #: Mikrofonun o anki seviyesi (RMS). Arayuzdeki cubuk bunu gosteriyor.
    level_updated = Signal(float)

    def __init__(
        self,
        connection: Any,
        audio_factory: Callable[[VoiceSession, Callable[[bytes], None]], Any] | None = None,
    ) -> None:
        super().__init__()
        self._connection = connection
        #: Kullanicinin sectigi cihazlar; bos bayt = sistem varsayilani.
        #: Fabrikanin imzasi (oturum, gonderici) degismedi: gercek fabrika
        #: secimi kendisi okuyor, testlerin sahte fabrikalari etkilenmiyor.
        self._input_id = b""
        self._output_id = b""
        self._audio_factory = audio_factory or self._open_audio
        self.session: VoiceSession | None = None
        self.link: VoiceLink | None = None
        self.audio: Any | None = None
        self.state = "off"
        self.peers: list[str] = []
        self._codec = available_codec()
        #: Gurultu kapisi varsayilan acik: klavye sesi ve cizirti gitmesin.
        #: Son voice_peers paketi; anahtar gecikince yeniden islenecek.
        self._last_peers: dict | None = None
        self._gate_enabled = True
        #: Kullanicinin sectigi esik (RMS). 0 ise kapinin kendi varsayilani.
        self._gate_threshold = 0
        #: Seviye cubugu ses akmadan da kipirdasin diye ayri ve sik.
        self._level_timer = QTimer(self)
        self._level_timer.timeout.connect(self._publish_level)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._publish_stats)
        self._join_timeout = QTimer(self)
        self._join_timeout.setSingleShot(True)
        self._join_timeout.timeout.connect(self._on_join_timeout)

    # --- katilim -------------------------------------------------------

    def join(self) -> None:
        """Sese katilma istegi. Kimlik gelince `on_packet` devam ettirir."""
        client = getattr(self._connection, "client", None)
        if client is None or self.state != "off":
            if client is None:
                self.failed.emit("voice_not_connected")
            return
        self._set_state("joining")
        self._join_timeout.start(JOIN_TIMEOUT_MS)
        paket = {"type": "voice_join", "codec": self._codec}
        oturum = getattr(self._connection, "room_session", None)
        if oturum is not None:
            # Gecici acik anahtarimiz: alicilar ses anahtarini kimden
            # turetecegini bununla buluyor. Kullanici adiyla eslestirmek
            # sunucunun soyledigine guvenmek olurdu.
            paket["pub"] = base64.urlsafe_b64encode(oturum.public_key).decode("ascii")
        client.send_packet(paket)

    def _on_join_timeout(self) -> None:
        """Sunucu cevap vermedi: buyuk ihtimalle sesli sohbeti bilmeyen bir surum."""
        if self.state != "joining":
            return
        self.failed.emit("voice_no_server")
        self._teardown()

    def leave(self) -> None:
        client = getattr(self._connection, "client", None)
        if client is not None and self.state != "off":
            try:
                client.send_packet({"type": "voice_leave"})
            except (OSError, ConnectionError):
                pass
        self._teardown()

    def _teardown(self) -> None:
        self._timer.stop()
        self._join_timeout.stop()
        self._level_timer.stop()
        self.level_updated.emit(0.0)
        if self.audio is not None:
            self.audio.stop()
            self.audio = None
        if self.link is not None:
            self.link.stop()
            self.link = None
        if self.session is not None:
            self.session.close()
            self.session = None
        self.peers = []
        self.peers_changed.emit([])
        self._set_state("off")

    def _set_state(self, state: str) -> None:
        if state != self.state:
            self.state = state
            self.state_changed.emit(state)

    # --- sunucudan gelenler --------------------------------------------

    def on_packet(self, packet: dict) -> None:
        """Sunucudan gelen ses paketlerini isler; digerlerini yok sayar."""
        tip = packet.get("type")
        if tip == "voice_joined":
            self._on_joined(packet)
        elif tip == "voice_peers":
            self._on_peers(packet)
        elif tip == "peers_verified" and self._last_peers is not None:
            # Bir esin metin anahtari yeni geldi: ses anahtari artik
            # turetilebilir. Son katilimci listesini yeniden isliyoruz.
            self._on_peers(self._last_peers)

    @staticmethod
    def _peer_sender_key(oda_oturumu, katilimci: dict) -> bytes | None:
        """Esin yayin anahtari; acik anahtariyla eslestirilerek bulunuyor."""
        if oda_oturumu is None:
            return None
        acik = katilimci.get("pub")
        if not isinstance(acik, str) or not acik:
            return None
        try:
            ham = base64.urlsafe_b64decode(acik.encode("ascii"))
        except (ValueError, TypeError):
            return None
        return oda_oturumu.sender_key_of(ham)

    def _on_joined(self, packet: dict) -> None:
        if self.state != "joining":
            return
        self._join_timeout.stop()
        sender_id = packet.get("sender_id")
        token = packet.get("token") or ""
        # Paketi sunucu kuruyor ve zarf duz metin gidiyor; bozuk bir jeton
        # eskiden asagida bytes.fromhex'te patliyor, katilimi "katiliyor"
        # halinde asili birakiyordu.
        try:
            token_bytes: bytes | None = bytes.fromhex(token) if token else b""
        except (TypeError, ValueError):
            token_bytes = None
        port = packet.get("port")
        if not isinstance(port, int) or not 0 < port < 65536:
            port = self._connection.port
        if not isinstance(sender_id, int) or token_bytes is None:
            self.failed.emit("voice_not_connected")
            self._teardown()
            return
        # Odanin kodegini ilk katilan belirler; biz onu destekleyemiyorsak
        # sessizce yanlis kodekle konusmak yerine acikca vazgeciyoruz.
        # Eskiden iki taraf farkli kodekte kalir, paketler cozulmez ve
        # kimse sebebini anlamazdi.
        oda_kodegi = packet.get("codec") or self._codec
        codec = choose_codec(self._codec, oda_kodegi)
        if codec != oda_kodegi:
            self.failed.emit("voice_codec")
            client = getattr(self._connection, "client", None)
            if client is not None:
                try:
                    client.send_packet({"type": "voice_leave"})
                except (OSError, ConnectionError):
                    pass
            self._teardown()
            return
        oda_oturumu = getattr(self._connection, "room_session", None)
        self.session = VoiceSession(
            self._connection.room,
            self._connection.room_password or None,
            sender_id,
            codec,
            own_sender_key=oda_oturumu.own_sender_key() if oda_oturumu is not None else None,
        )
        client = getattr(self._connection, "client", None)
        if client is not None:
            client.send_packet({"type": "voice_salt", "salt": self.session.session_salt.hex()})
        self.link = VoiceLink(
            self._connection.host or "127.0.0.1",
            port,
            self.session,
            token_bytes,
        )
        self.link.start()
        try:
            self.audio = self._audio_factory(self.session, self.link.send_frame)
            self._configure_audio(self.audio)
        except VoiceDeviceError:
            self.failed.emit("voice_device")
            self._teardown()
            return
        self._timer.start(STATS_INTERVAL_MS)
        self._level_timer.start(LEVEL_INTERVAL_MS)
        self._set_state("on")

    def _on_peers(self, packet: dict) -> None:
        # Paket saklaniyor: bir esin metin anahtari ses katilimindan SONRA
        # gelebiliyor; o an listeyi yeniden isliyoruz (bkz. on_packet).
        self._last_peers = packet
        oda_oturumu = getattr(self._connection, "room_session", None)
        katilimcilar = packet.get("peers")
        if not isinstance(katilimcilar, list):
            katilimcilar = []
        katilimcilar = [k for k in katilimcilar if isinstance(k, dict)]
        adlar = []
        for katilimci in katilimcilar:
            ad = str(katilimci.get("user", ""))
            kimlik = katilimci.get("sender_id")
            tuz = katilimci.get("salt") or ""
            adlar.append(ad)
            if self.session is None or kimlik == self.session.sender_id:
                continue
            anahtar = self._peer_sender_key(oda_oturumu, katilimci)
            try:
                self.session.add_peer(int(kimlik), bytes.fromhex(tuz), anahtar)
            except SenderKeyMissingError:
                # Metin el sikismasi henuz bitmedi; anahtar gelince yeniden
                # denenecek. Sessizce geciyoruz, bu bir hata degil.
                continue
            except (TypeError, ValueError):
                continue
        if self.session is not None:
            for kimlik in self.session.peers():
                if kimlik not in {k.get("sender_id") for k in katilimcilar}:
                    self.session.remove_peer(kimlik)
        self.peers = adlar
        self.peers_changed.emit(adlar)

    # --- ses cihazlari ---------------------------------------------------

    def _open_audio(self, session: VoiceSession, send_frame: Callable[[bytes], None]) -> VoiceAudio:
        return VoiceAudio(session, send_frame, self._input_id, self._output_id)

    def _configure_audio(self, audio: Any, muted: bool = False) -> None:
        """Yeni acilan ses kartina kullanicinin ayarlarini uygular."""
        audio.muted = muted
        audio.gate.enabled = self._gate_enabled
        if self._gate_threshold:
            audio.gate.set_threshold(self._gate_threshold)

    @property
    def input_device(self) -> bytes:
        return self._input_id

    @property
    def output_device(self) -> bytes:
        return self._output_id

    def set_devices(self, input_id: bytes | None = None, output_id: bytes | None = None) -> None:
        """Mikrofon ve/veya hoparlor secimi; bos bayt sistem varsayilani demek.

        Gorusme suruyorsa YALNIZCA ses karti yeniden aciliyor: oturum,
        sifreleme, jitter tamponlari ve UDP baglantisi `VoiceAudio`'dan ayri,
        onlara dokunulmuyor. Ses bir an kesilir, gorusme kesilmez.

        Yeni cihaz acilamazsa (istenen bicimi desteklemiyorsa) gorusmeyi
        dusurmek yerine onceki cihaza donulur ve hata bildirilir. Cagiran
        `input_device` / `output_device` ile gercekte ne kullanildigini
        okuyup arayuzu ve kaydi ona gore guncellemeli.
        """
        onceki = (self._input_id, self._output_id)
        if input_id is not None:
            self._input_id = bytes(input_id)
        if output_id is not None:
            self._output_id = bytes(output_id)
        if self.audio is None or (self._input_id, self._output_id) == onceki:
            return
        # Susturma BURADA okunuyor, yeniden acmadan once: ilk deneme eski
        # karti kapatip None yapiyor. Eskiden ikinci deneme (geri donus)
        # susturmayi None'dan okuyup False sayiyordu -- kullanici susturmusken
        # mikrofon acik gidiyor, arayuzdeki kutu ise isaretli kaliyordu.
        susturulmus = bool(self.audio.muted)
        try:
            self._reopen_audio(susturulmus)
        except VoiceDeviceError:
            self._input_id, self._output_id = onceki
            # "Sesli sohbet acilamadi" DEGIL: gorusme eski cihazla suruyor.
            self.failed.emit("voice_device_switch")
            try:
                self._reopen_audio(susturulmus)
            except VoiceDeviceError:
                # Az once calisan cihaz da acilmiyorsa (cikarilmis olabilir)
                # sessiz bir gorusmede kalmaktansa ayriliyoruz.
                self.failed.emit("voice_device")
                self.leave()

    def on_devices_changed(self, inputs: set[bytes], outputs: set[bytes]) -> None:
        """Takili cihazlar degisti (kulaklik takildi ya da cikarildi).

        Gorusme suruyorsa ve kart artik olmayan bir cihazdaysa yeniden
        acilir: secili cihaz yoksa `pick_device` varsayilana duser. Eskiden
        liste tazeleniyor ama kart cikarilan cihazda kaliyordu; gorusme
        sessizce sagir ve dilsiz oluyordu. Secili cihaz geri takilinca da
        ona donulur. Susturma korunur.
        """
        if self.audio is None:
            return
        acik_giris = getattr(self.audio, "input_device_id", None)
        acik_cikis = getattr(self.audio, "output_device_id", None)
        if acik_giris is None or acik_cikis is None:
            return
        kayboldu = acik_giris not in inputs or acik_cikis not in outputs
        geri_geldi = any(
            secili and secili in takili and secili != acik
            for secili, takili, acik in (
                (self._input_id, inputs, acik_giris),
                (self._output_id, outputs, acik_cikis),
            )
        )
        if not (kayboldu or geri_geldi):
            return
        try:
            self._reopen_audio(bool(self.audio.muted))
        except VoiceDeviceError:
            self.failed.emit("voice_device")
            self.leave()

    def _reopen_audio(self, muted: bool) -> None:
        """Ses kartini mevcut secimle yeniden acar; susturma verilenle ayni."""
        if self.audio is not None:
            self.audio.stop()
            self.audio = None
        if self.session is None or self.link is None:
            return
        yeni = self._audio_factory(self.session, self.link.send_frame)
        self._configure_audio(yeni, muted=muted)
        self.audio = yeni

    # --- durum ---------------------------------------------------------

    def set_noise_gate(self, enabled: bool) -> None:
        """Gurultu kapisini acar/kapatir; sonraki oturumlarda da gecerli."""
        self._gate_enabled = enabled
        if self.audio is not None:
            self.audio.gate.enabled = enabled

    def set_gate_threshold(self, threshold: int) -> None:
        """Kapinin esigi (RMS). Kisiden kisiye ve mikrofona gore degisir."""
        self._gate_threshold = max(0, int(threshold))
        if self.audio is not None and self._gate_threshold:
            self.audio.gate.set_threshold(self._gate_threshold)

    @property
    def gate_threshold(self) -> int:
        return self._gate_threshold

    def _publish_level(self) -> None:
        if self.audio is not None:
            self.level_updated.emit(self.audio.gate.level)

    @property
    def noise_gate(self) -> bool:
        return self._gate_enabled

    def set_muted(self, muted: bool) -> None:
        """Susturma yalnizca mikrofonu keser; akis devam eder."""
        if self.audio is not None:
            self.audio.muted = muted

    @property
    def muted(self) -> bool:
        return bool(self.audio is not None and self.audio.muted)

    def _publish_stats(self) -> None:
        if self.session is not None:
            self.stats_updated.emit(self.session.stats())

    def frame_ms(self) -> int:  # pragma: no cover - kolaylik
        return FRAME_MS
