"""Urun tarafindaki ses oturumu (core/voice_session.py) ve kodek katmani.

Ses donanimi ve soket yok: cerceveler elle uretiliyor.
"""

import math
import unittest

from core.voice_codec import (
    CODEC_MULAW,
    CODEC_OPUS,
    FRAME_BYTES,
    FRAME_PCM_BYTES,
    FrameCodec,
    available_codec,
    choose_codec,
    silence,
)
from core.voice_jitter import DEFAULT_TARGET_MS
from core.voice_opus import opus_available
from core.voice_packet import FRAME_MS, HEADER_BYTES
from core.voice_session import DEVICE_ALLOWANCE_MS, TIMING, VoiceSession


def konusma(deger: int = 1200) -> bytes:
    """Sessizlikten ayirt edilebilen bir cerceve."""
    return deger.to_bytes(2, "little", signed=True) * (FRAME_PCM_BYTES // 2)


def guc(pcm: bytes) -> float:
    toplam = 0
    for i in range(0, len(pcm), 2):
        ornek = int.from_bytes(pcm[i : i + 2], "little", signed=True)
        toplam += ornek * ornek
    return math.sqrt(toplam / max(1, len(pcm) // 2))


def anahtar(kimlik: int) -> bytes:
    """Testler icin kararli bir gonderen anahtari.

    Uretimde bu anahtar oda oturumundan geliyor ve rastgele
    (`core/room_session.py`). Burada kimlikten uretiliyor ki testler okunur
    kalsin: 2 numarali gonderenin anahtari her zaman ayni.
    """
    return bytes([kimlik]) * 32


class SahteSaat:
    def __init__(self):
        self.simdi = 1000.0

    def __call__(self):
        return self.simdi


class KodekSecimiTests(unittest.TestCase):
    def test_ortak_kodek(self):
        self.assertEqual(choose_codec(CODEC_OPUS, CODEC_OPUS), CODEC_OPUS)
        self.assertEqual(choose_codec(CODEC_OPUS, CODEC_MULAW), CODEC_MULAW)
        self.assertEqual(choose_codec(CODEC_MULAW, CODEC_OPUS), CODEC_MULAW)
        self.assertEqual(choose_codec(CODEC_OPUS, None), CODEC_MULAW)

    def test_kullanilabilir_kodek_kutuphaneye_bagli(self):
        beklenen = CODEC_OPUS if opus_available() else CODEC_MULAW
        self.assertEqual(available_codec(), beklenen)

    def test_bilinmeyen_kodek_reddedilir(self):
        with self.assertRaises(ValueError):
            FrameCodec("mp3")

    def test_mulaw_cerceve_boyu_sabit(self):
        kodek = FrameCodec(CODEC_MULAW)
        self.addCleanup(kodek.close)

        boylar = {len(kodek.encode(konusma(d))) for d in (0, 500, 9000, -9000)}

        self.assertEqual(boylar, {FRAME_BYTES[CODEC_MULAW]})

    def test_mulawda_kodek_gizlemesi_yok(self):
        kodek = FrameCodec(CODEC_MULAW)
        self.addCleanup(kodek.close)
        self.assertIsNone(kodek.conceal())

    def test_yanlis_boyutta_cerceve_reddedilir(self):
        kodek = FrameCodec(CODEC_MULAW)
        self.addCleanup(kodek.close)
        with self.assertRaises(ValueError):
            kodek.encode(b"\x00" * 100)


class OturumTests(unittest.TestCase):
    def _ikili(self, parola="gizli", kodek=CODEC_MULAW):
        saat = SahteSaat()
        ayse = VoiceSession("oda", parola, 1, kodek, clock=saat, own_sender_key=anahtar(1))
        mehmet = VoiceSession("oda", parola, 2, kodek, clock=saat, own_sender_key=anahtar(2))
        self.addCleanup(ayse.close)
        self.addCleanup(mehmet.close)
        ayse.add_peer(2, mehmet.session_salt, anahtar(2))
        mehmet.add_peer(1, ayse.session_salt, anahtar(1))
        return saat, ayse, mehmet

    def _doldur(self, gonderen, alan, adet=None):
        for _ in range(adet or DEFAULT_TARGET_MS // FRAME_MS):
            alan.incoming(gonderen.outgoing(konusma()))

    def test_ses_bastan_sona_gidiyor(self):
        _saat, ayse, mehmet = self._ikili()
        self._doldur(ayse, mehmet)

        cikan = mehmet.play()

        self.assertEqual(len(cikan), FRAME_PCM_BYTES)
        self.assertNotEqual(cikan, silence(), "ses calinmadi")
        self.assertEqual(mehmet.received, DEFAULT_TARGET_MS // FRAME_MS)

    def test_kendi_paketi_calinmaz(self):
        """Aktarmadan kendi paketimiz geri gelirse kendimizi duymayiz."""
        _saat, ayse, _mehmet = self._ikili()

        ayse.incoming(ayse.outgoing(konusma()))

        self.assertEqual(ayse.received, 0)

    def test_yanlis_parola_cozulemez(self):
        saat = SahteSaat()
        ayse = VoiceSession("oda", "gizli", 1, clock=saat, own_sender_key=anahtar(1))
        yabanci = VoiceSession("oda", "baska", 2, clock=saat, own_sender_key=anahtar(99))
        self.addCleanup(ayse.close)
        self.addCleanup(yabanci.close)
        # Yanlis anahtarla deniyor: dogru anahtari bilmiyor.
        yabanci.add_peer(1, ayse.session_salt, anahtar(99))

        yabanci.incoming(ayse.outgoing(konusma()))

        self.assertEqual((yabanci.received, yabanci.undecryptable), (0, 1))

    def test_tanimadigi_gonderen_calinmaz(self):
        _saat, ayse, mehmet = self._ikili()
        mehmet.remove_peer(1)

        mehmet.incoming(ayse.outgoing(konusma()))

        self.assertEqual(mehmet.received, 0)
        self.assertEqual(mehmet.play(), silence())

    def test_bozuk_datagram_sayiliyor(self):
        _saat, _ayse, mehmet = self._ikili()

        mehmet.incoming(b"")
        mehmet.incoming(b"x" * (HEADER_BYTES + 4))

        self.assertEqual(mehmet.malformed, 2)

    def test_uc_kisi_ayni_anda_konusabiliyor(self):
        """Dort kisilik odanin calismasi icin karistirma sart."""
        saat = SahteSaat()
        oturumlar = [
            VoiceSession("oda", "gizli", i, clock=saat, own_sender_key=anahtar(i))
            for i in (1, 2, 3)
        ]
        for o in oturumlar:
            self.addCleanup(o.close)
        for o in oturumlar:
            for digeri in oturumlar:
                if digeri is not o:
                    o.add_peer(digeri.sender_id, digeri.session_salt, anahtar(digeri.sender_id))
        dinleyen = oturumlar[0]
        for _ in range(DEFAULT_TARGET_MS // FRAME_MS):
            for konusan in oturumlar[1:]:
                dinleyen.incoming(konusan.outgoing(konusma(4000)))

        karisim = dinleyen.play()

        self.assertEqual(len(karisim), FRAME_PCM_BYTES)
        self.assertGreater(guc(karisim), guc(konusma(4000)), "sesler toplanmadi")
        self.assertEqual(dinleyen.peers(), [2, 3])

    def test_kayip_cerceve_gizleniyor(self):
        _saat, ayse, mehmet = self._ikili()
        self._doldur(ayse, mehmet)
        for _ in range(DEFAULT_TARGET_MS // FRAME_MS):
            mehmet.play()
        ayse.outgoing(konusma())  # bu cerceve "kayboluyor"

        gizlenmis = mehmet.play()

        self.assertEqual(mehmet.concealed, 1)
        self.assertEqual(len(gizlenmis), FRAME_PCM_BYTES)

    def test_uzun_kayipta_sessizlige_dusuyor(self):
        _saat, ayse, mehmet = self._ikili()
        self._doldur(ayse, mehmet)
        mehmet.play()

        son = [mehmet.play() for _ in range(8)][-1]

        self.assertEqual(son, silence())
        self.assertGreater(mehmet.silent, 0)

    def test_sira_numaralari_artiyor(self):
        """Nonce tekrarini onleyen kural: ayni numara iki kez kullanilmaz."""
        from core.voice_packet import decode_header

        _saat, ayse, _mehmet = self._ikili()

        siralar = [decode_header(ayse.outgoing(konusma())).sequence for _ in range(5)]

        self.assertEqual(siralar, sorted(set(siralar)))
        self.assertEqual(siralar[0], 1)

    def test_paket_boyu_sese_gore_degismiyor(self):
        _saat, ayse, _mehmet = self._ikili()

        boylar = {len(ayse.outgoing(konusma(d))) for d in (0, 300, 9000)}

        self.assertEqual(len(boylar), 1)
        beklenen = HEADER_BYTES + FRAME_BYTES[CODEC_MULAW] + TIMING.size + 16
        self.assertEqual(boylar.pop(), beklenen)


class ZamanEkiTests(unittest.TestCase):
    def _ikili(self):
        saat = SahteSaat()
        ayse = VoiceSession("oda", "gizli", 1, clock=saat, own_sender_key=anahtar(1))
        mehmet = VoiceSession("oda", "gizli", 2, clock=saat, own_sender_key=anahtar(2))
        self.addCleanup(ayse.close)
        self.addCleanup(mehmet.close)
        ayse.add_peer(2, mehmet.session_salt, anahtar(2))
        mehmet.add_peer(1, ayse.session_salt, anahtar(1))
        return saat, ayse, mehmet

    def test_gidis_donus_hesaplaniyor(self):
        saat, ayse, mehmet = self._ikili()
        paket = ayse.outgoing(konusma())
        saat.simdi += 0.030  # tek yon 30 ms
        mehmet.incoming(paket)
        saat.simdi += 0.015  # mehmet cevap vermeden once bekliyor
        cevap = mehmet.outgoing(konusma())
        saat.simdi += 0.030
        ayse.incoming(cevap)

        self.assertEqual(ayse.rtt.summary(), {"median": 60, "p95": 60, "count": 1})
        self.assertEqual(mehmet.rtt.count, 0, "yankilanan damga henuz donmedi")

    def test_baskasinin_yankisi_bize_yazilmiyor(self):
        """Uc kisilik odada yankiyi yalnizca sahibi sayar."""
        saat, ayse, mehmet = self._ikili()
        zeynep = VoiceSession("oda", "gizli", 3, clock=saat, own_sender_key=anahtar(3))
        self.addCleanup(zeynep.close)
        zeynep.add_peer(1, ayse.session_salt, anahtar(1))
        ayse.add_peer(3, zeynep.session_salt, anahtar(3))

        mehmet.incoming(ayse.outgoing(konusma()))
        saat.simdi += 0.02
        # Mehmet, Ayse'nin damgasini yankiliyor; Zeynep bunu duyuyor.
        zeynep.add_peer(2, mehmet.session_salt, anahtar(2))
        zeynep.incoming(mehmet.outgoing(konusma()))

        self.assertEqual(zeynep.rtt.count, 0)

    def test_agizdan_kulaga_rtt_yarisi_arti_tampon_arti_cihaz(self):
        saat, ayse, mehmet = self._ikili()
        for _ in range(DEFAULT_TARGET_MS // FRAME_MS + 1):
            mehmet.incoming(ayse.outgoing(konusma()))
            saat.simdi += 0.05
            ayse.incoming(mehmet.outgoing(konusma()))
            saat.simdi += 0.05
        rtt = ayse._last_rtt
        self.assertIsNotNone(rtt)

        tampon = ayse._peers[2].buffer
        ayse.play()

        beklenen = round(rtt / 2 + tampon.buffered_ms + DEVICE_ALLOWANCE_MS)
        self.assertEqual(ayse.mouth_to_ear.percentile(0.5), beklenen)

    def test_olcum_yoksa_yuzdelik_none(self):
        _saat, ayse, _mehmet = self._ikili()
        self.assertIsNone(ayse.rtt.percentile(0.95))
        self.assertEqual(ayse.stats()["rtt_ms"]["count"], 0)


@unittest.skipUnless(opus_available(), "libopus yok (PROXYCHAT_OPUS_DLL)")
class OpusOturumTests(unittest.TestCase):
    def _ikili(self):
        saat = SahteSaat()
        ayse = VoiceSession("oda", "gizli", 1, CODEC_OPUS, clock=saat, own_sender_key=anahtar(1))
        mehmet = VoiceSession("oda", "gizli", 2, CODEC_OPUS, clock=saat, own_sender_key=anahtar(2))
        self.addCleanup(ayse.close)
        self.addCleanup(mehmet.close)
        ayse.add_peer(2, mehmet.session_salt, anahtar(2))
        mehmet.add_peer(1, ayse.session_salt, anahtar(1))
        return saat, ayse, mehmet

    def test_datagram_mulawin_ucte_birinden_kucuk(self):
        _saat, ayse, _mehmet = self._ikili()

        datagram = ayse.outgoing(konusma())

        # 18 baslik + 60 ses + 10 zaman eki + 16 GCM etiketi
        self.assertEqual(len(datagram), 104)

    def test_ses_bastan_sona_gidiyor(self):
        _saat, ayse, mehmet = self._ikili()
        for _ in range(DEFAULT_TARGET_MS // FRAME_MS):
            mehmet.incoming(ayse.outgoing(konusma()))

        cikan = mehmet.play()

        self.assertEqual(len(cikan), FRAME_PCM_BYTES)
        self.assertEqual(mehmet.received, DEFAULT_TARGET_MS // FRAME_MS)

    def test_gizlemeyi_kodek_yapiyor(self):
        _saat, ayse, mehmet = self._ikili()
        for _ in range(DEFAULT_TARGET_MS // FRAME_MS):
            mehmet.incoming(ayse.outgoing(konusma()))
        for _ in range(DEFAULT_TARGET_MS // FRAME_MS):
            mehmet.play()
        ayse.outgoing(konusma())  # kayboluyor

        gizlenmis = mehmet.play()

        self.assertEqual(mehmet.concealed, 1)
        self.assertEqual(len(gizlenmis), FRAME_PCM_BYTES)

    def test_farkli_kodekten_gelen_paket_atiliyor(self):
        saat = SahteSaat()
        ulawci = VoiceSession("oda", "gizli", 1, CODEC_MULAW, clock=saat, own_sender_key=anahtar(1))
        opuscu = VoiceSession("oda", "gizli", 2, CODEC_OPUS, clock=saat, own_sender_key=anahtar(2))
        self.addCleanup(ulawci.close)
        self.addCleanup(opuscu.close)
        opuscu.add_peer(1, ulawci.session_salt, anahtar(1))

        opuscu.incoming(ulawci.outgoing(konusma()))

        self.assertEqual((opuscu.received, opuscu.malformed), (0, 1))


if __name__ == "__main__":
    unittest.main()
