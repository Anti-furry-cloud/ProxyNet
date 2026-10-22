"""Gurultu kapisi (core/voice_gate.py).

Cerceveler elle uretiliyor: ses karti yok.
"""

import math
import unittest

from core.voice_codec import FRAME_PCM_BYTES, silence
from core.voice_gate import (
    CLOSE_RATIO,
    DEFAULT_CLOSE_RMS,
    DEFAULT_OPEN_RMS,
    NoiseGate,
    frame_rms,
    scaled,
)
from core.voice_packet import FRAME_MS


def ton(genlik: int) -> bytes:
    """Verilen genlikte bir cerceve (sinus; RMS ~ genlik/1.41)."""
    ornekler = bytearray()
    for i in range(FRAME_PCM_BYTES // 2):
        deger = int(genlik * math.sin(2 * math.pi * 300 * i / 16000))
        ornekler += deger.to_bytes(2, "little", signed=True)
    return bytes(ornekler)


def duz(deger: int) -> bytes:
    """Sabit degerli cerceve: RMS tam olarak |deger|."""
    return deger.to_bytes(2, "little", signed=True) * (FRAME_PCM_BYTES // 2)


class OlcumTests(unittest.TestCase):
    def test_rms_sessizlikte_sifir(self):
        self.assertEqual(frame_rms(silence()), 0.0)

    def test_rms_sabit_cercevede_genlige_esit(self):
        self.assertAlmostEqual(frame_rms(duz(1000)), 1000.0, places=6)

    def test_kisma(self):
        self.assertEqual(scaled(duz(1000), 1.0), duz(1000))
        self.assertEqual(scaled(duz(1000), 0.0), silence())
        self.assertAlmostEqual(frame_rms(scaled(duz(1000), 0.5)), 500.0, places=6)


class KapiTests(unittest.TestCase):
    """Temel davranis. On bakis kapali: cikti gecikmesiz olsun, sinamasi kolay."""

    def _kapi(self, **k):
        k.setdefault("lookahead_frames", 0)
        return NoiseGate(**k)

    def test_sessiz_cerceve_sessizlige_ceviriliyor(self):
        """Klavye sesi ve cizirti esigin altindaysa gitmiyor."""
        kapi = self._kapi()

        cikan = kapi.process(duz(50))

        self.assertEqual(cikan, silence())
        self.assertEqual(kapi.silenced, 1)
        self.assertFalse(kapi.is_open)

    def test_konusma_gecirilir(self):
        kapi = self._kapi()

        cikan = kapi.process(duz(DEFAULT_OPEN_RMS + 100))

        self.assertEqual(cikan, duz(DEFAULT_OPEN_RMS + 100))
        self.assertTrue(kapi.is_open)

    def test_cerceve_boyu_degismiyor(self):
        """Akis sabit hizda ve sabit boyda kalmali."""
        kapi = self._kapi()

        for cerceve in (duz(20), duz(5000), duz(20)):
            self.assertEqual(len(kapi.process(cerceve)), FRAME_PCM_BYTES)

    def test_kelime_arasindaki_duraklar_kesilmiyor(self):
        """Tutma suresi: kisa sessizlikte kapi acik kalir."""
        kapi = self._kapi(hold_ms=300)
        kapi.process(duz(5000))

        # 300 ms tutma = 15 cerceve; 10 cerceve sessizlikten sonra hala acik.
        for _ in range(10):
            cikan = kapi.process(duz(100))

        self.assertTrue(kapi.is_open)
        self.assertNotEqual(cikan, silence())

    def test_uzun_sessizlikte_kapaniyor(self):
        kapi = self._kapi(hold_ms=100, release_ms=FRAME_MS)
        kapi.process(duz(5000))

        for _ in range(20):
            cikan = kapi.process(duz(80))

        self.assertFalse(kapi.is_open)
        self.assertEqual(cikan, silence())

    def test_histerezis_kapiyi_carptirmiyor(self):
        """Iki esik arasindaki ses kapiyi acip kapatmamali."""
        kapi = self._kapi(hold_ms=0)
        kapi.process(duz(DEFAULT_OPEN_RMS + 200))
        arada = (DEFAULT_OPEN_RMS + DEFAULT_CLOSE_RMS) // 2

        for _ in range(10):
            kapi.process(duz(arada))

        self.assertTrue(kapi.is_open, "esikler arasinda kapi kapandi")

    def test_kapanis_sonumlenerek_oluyor(self):
        """Birden kesmek tak diye duyulur."""
        kapi = self._kapi(hold_ms=0, release_ms=60)
        kapi.process(duz(5000))

        ilk = frame_rms(kapi.process(duz(10)))
        ikinci = frame_rms(kapi.process(duz(10)))

        self.assertGreater(ilk, 0.0)
        self.assertLess(ikinci, ilk)

    def test_kapatilinca_her_sey_geciyor(self):
        kapi = self._kapi()
        kapi.enabled = False

        cikan = kapi.process(duz(10))

        self.assertEqual(cikan, duz(10))
        self.assertEqual(kapi.silenced, 0)

    def test_esikler_tutarsizsa_hata(self):
        with self.assertRaises(ValueError):
            NoiseGate(open_rms=100, close_rms=500)

    def test_yanlis_boyutta_cerceve_reddediliyor(self):
        with self.assertRaises(ValueError):
            self._kapi().process(b"\x00" * 10)

    def test_sifirlama(self):
        kapi = self._kapi()
        kapi.process(duz(5000))

        kapi.reset()

        self.assertFalse(kapi.is_open)

    def test_alcak_sesle_konusma_kesilmiyor(self):
        """Ses kapatma esiginin ustunde kaldigi surece kapi acik kalmali.

        Eskiden tutma sayaci bu durumda da azaliyordu: alcak sesle konusmaya
        devam eden birinin sozu 300 ms sonra kesiliyordu.
        """
        kapi = self._kapi(hold_ms=100)
        kapi.process(duz(5000))
        arada = (DEFAULT_OPEN_RMS + DEFAULT_CLOSE_RMS) // 2

        for _ in range(50):  # 1 saniye boyunca alcak sesle konusma
            cikan = kapi.process(duz(arada))

        self.assertTrue(kapi.is_open, "alcak sesle konusma kesildi")
        self.assertEqual(cikan, duz(arada))

    def test_gercekci_akis(self):
        """Sessizlik -> konusma -> sessizlik: konusma bozulmadan gecmeli."""
        kapi = self._kapi(hold_ms=100, release_ms=40)
        gecen = []

        for _ in range(10):
            gecen.append(kapi.process(ton(60)) != silence())
        konusma = [kapi.process(ton(6000)) != silence() for _ in range(25)]
        for _ in range(30):
            gecen.append(kapi.process(ton(60)) != silence())

        self.assertTrue(all(konusma), "konusma kirpildi")
        self.assertEqual(gecen[:10], [False] * 10, "bastaki cizirti gecti")
        self.assertFalse(gecen[-1], "sonunda kapanmadi")


class OnBakisTests(unittest.TestCase):
    """Kelimenin esigin altinda kalan baslangici kirpilmamali."""

    def test_kapi_acilinca_onceki_cerceveler_de_gidiyor(self):
        kapi = NoiseGate(lookahead_frames=2, hold_ms=0)
        # Yumusak baslangic: esigin altinda iki cerceve, sonra yuksek ses.
        yumusak = duz(DEFAULT_OPEN_RMS // 3)

        ilk = [kapi.process(yumusak) for _ in range(2)]
        sonraki = [kapi.process(duz(5000)) for _ in range(3)]

        self.assertEqual(ilk, [silence(), silence()], "kuyruk dolarken sessizlik gider")
        # Kuyruktakiler kapi acilinca gonderiliyor: yumusak baslangic geciyor.
        self.assertEqual(sonraki[0], yumusak)
        self.assertEqual(sonraki[1], yumusak)
        self.assertEqual(sonraki[2], duz(5000))

    def test_akis_hizi_degismiyor(self):
        """Her cagriya bir cerceve; on bakis paket sayisini degistirmemeli."""
        kapi = NoiseGate(lookahead_frames=2)

        cikanlar = [kapi.process(duz(100)) for _ in range(10)]

        self.assertEqual(len(cikanlar), 10)
        self.assertTrue(all(len(c) == FRAME_PCM_BYTES for c in cikanlar))

    def test_sessizlikte_sessizlik_cikiyor(self):
        kapi = NoiseGate(lookahead_frames=2)

        cikanlar = [kapi.process(duz(50)) for _ in range(10)]

        self.assertEqual(cikanlar[-1], silence())

    def test_sifirlama_kuyrugu_bosaltiyor(self):
        kapi = NoiseGate(lookahead_frames=2)
        kapi.process(duz(5000))

        kapi.reset()

        self.assertFalse(kapi.is_open)
        self.assertEqual(kapi.process(duz(50)), silence())


class EsikTests(unittest.TestCase):
    def test_esik_ayarlaninca_kapatma_esigi_de_degisiyor(self):
        kapi = NoiseGate()

        kapi.set_threshold(1000)

        self.assertEqual(kapi.open_rms, 1000)
        self.assertEqual(kapi.close_rms, 1000 * CLOSE_RATIO)

    def test_esik_yukseltilince_kisik_ses_kesiliyor(self):
        kapi = NoiseGate(lookahead_frames=0, hold_ms=0)
        kapi.set_threshold(300)
        self.assertNotEqual(kapi.process(duz(400)), silence())

        kapi.set_threshold(2000)
        for _ in range(5):
            cikan = kapi.process(duz(400))

        self.assertEqual(cikan, silence())

    def test_seviye_okunabiliyor(self):
        """Arayuzdeki cubuk bu degeri gosteriyor."""
        kapi = NoiseGate()

        kapi.process(duz(1234))

        self.assertAlmostEqual(kapi.level, 1234.0, places=6)


if __name__ == "__main__":
    unittest.main()
