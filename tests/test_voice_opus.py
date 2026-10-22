"""libopus baglamasi (core/voice_opus.py).

DLL bulunamazsa bu testler atlanir: libopus depoda durmuyor, gelistirirken
disaridan gosteriliyor (PROXYCHAT_OPUS_DLL). Boylece CI'da ve baska bir
makinede takim kirilmaz.

Sinyal sinus degil konusmaya benzer uretiliyor: Opus'un yedek cerceve (FEC)
kararlari sinyalin konusma gibi gorunmesine bagli.
"""

import math
import random
import unittest

from core import voice_opus as o

ORNEK_HIZI = 16000
CERCEVE_MS = 20
CERCEVE_ORNEK = ORNEK_HIZI * CERCEVE_MS // 1000


def konusma(sira: int, tohum: int = 7) -> bytes:
    """Konusmaya benzer 20 ms'lik cerceve: harmonikler + zarf + az gurultu."""
    rastgele = random.Random(tohum + sira)
    temel = 120 + 30 * math.sin(sira / 7)
    zarf = 0.4 + 0.6 * abs(math.sin(sira / 11))
    ornekler = bytearray()
    for n in range(CERCEVE_ORNEK):
        t = (sira * CERCEVE_ORNEK + n) / ORNEK_HIZI
        deger = sum(math.sin(2 * math.pi * temel * h * t) / h for h in (1, 2, 3, 4, 5))
        deger += rastgele.uniform(-0.05, 0.05)
        ornek = int(max(-1.0, min(1.0, deger / 2)) * 9000 * zarf)
        ornekler += ornek.to_bytes(2, "little", signed=True)
    return bytes(ornekler)


def guc(pcm: bytes) -> float:
    """Cercevenin ortalama enerjisi; sessizlikle sesi ayirmak icin."""
    toplam = 0
    for i in range(0, len(pcm), 2):
        ornek = int.from_bytes(pcm[i : i + 2], "little", signed=True)
        toplam += ornek * ornek
    return math.sqrt(toplam / max(1, len(pcm) // 2))


@unittest.skipUnless(o.opus_available(), "libopus yok (PROXYCHAT_OPUS_DLL)")
class OpusTests(unittest.TestCase):
    def _kodlayici(self, bitrate=o.DEFAULT_BITRATE, fec=True, kayip=None):
        k = o.OpusEncoder(
            ORNEK_HIZI,
            CERCEVE_MS,
            bitrate=bitrate,
            fec=fec,
            expected_loss=o.DEFAULT_EXPECTED_LOSS if kayip is None else kayip,
        )
        self.addCleanup(k.close)
        return k

    def _cozucu(self):
        c = o.OpusDecoder(ORNEK_HIZI, CERCEVE_MS)
        self.addCleanup(c.close)
        return c

    def _yedek_var_mi(self, bitrate, kayip) -> bool:
        """Kaybolan cerceve sonraki paketin icindeki yedekten kurulabiliyor mu?"""
        kodlayici = self._kodlayici(bitrate=bitrate, kayip=kayip)
        paketler = [kodlayici.encode(konusma(i)) for i in range(24)]
        fecli, plcli = self._cozucu(), self._cozucu()
        for paket in paketler[:20]:
            fecli.decode(paket)
            plcli.decode(paket)
        # 21. cerceve kayboldu: FEC'li cozucu sonraki paketi yedek olarak
        # kullanir, PLC'li cozucu yalnizca tahmin uretir. Ciktilar ayniysa
        # pakette yedek yoktur.
        return fecli.decode(paketler[21], fec=True) != plcli.decode(None)

    def test_paket_boyu_sese_gore_degismiyor(self):
        """Sabit bit hizi: sessizlik ve konusma ayni boyda paket verir.

        Degisken bit hizinda paket boylari kimin ne zaman konustugunu ele
        verir (Wright ve ark., 2008); esiklerin dayandigi tercih bu.
        """
        kodlayici = self._kodlayici()
        boylar = {len(kodlayici.encode(b"\x00" * CERCEVE_ORNEK * 2))}
        for i in range(25):
            boylar.add(len(kodlayici.encode(konusma(i))))

        self.assertEqual(boylar, {60}, "24 kbit/s'de her paket 60 bayt olmali")

    def test_16_kbit_daha_kucuk_paket(self):
        kodlayici = self._kodlayici(bitrate=16000)
        self.assertEqual(len(kodlayici.encode(konusma(0))), 40)

    def test_ses_bastan_sona_geciyor(self):
        kodlayici, cozucu = self._kodlayici(), self._cozucu()
        cikan = cozucu.decode(kodlayici.encode(konusma(0)))

        self.assertEqual(len(cikan), CERCEVE_ORNEK * 2)
        self.assertGreater(guc(cikan), 100, "cozulen cerceve sessiz cikti")

    def test_kayip_cerceve_gizlenir(self):
        """Paket gelmediginde cozucu kendi gizlemesini uretir (PLC)."""
        kodlayici, cozucu = self._kodlayici(), self._cozucu()
        for i in range(3):
            cozucu.decode(kodlayici.encode(konusma(i)))

        gizlenen = cozucu.decode(None)

        self.assertEqual(len(gizlenen), CERCEVE_ORNEK * 2)

    def test_varsayilan_ayarlarda_fec_yedegi_var(self):
        self.assertTrue(
            self._yedek_var_mi(o.DEFAULT_BITRATE, o.DEFAULT_EXPECTED_LOSS),
            "varsayilan ayarlarda FEC yedegi uretilmiyor",
        )

    def test_dusuk_kayip_beklentisinde_yedek_yok(self):
        """Olculen davranis (2026-09-24), varsayilanin 10 olmasinin sebebi.

        24 kbit/s sabit bit hizinda libopus, kayip beklentisi %5'ken yedek
        cerceve koymuyor. Kutuphane bunu degistirirse test uyarir.
        """
        self.assertFalse(self._yedek_var_mi(o.DEFAULT_BITRATE, 5))

    def test_16_kbitte_fec_yok(self):
        """16 kbit/s secilirse FEC'ten vazgecilmis olur; karar buna bagli."""
        self.assertFalse(self._yedek_var_mi(16000, 20))

    def test_fec_cercevesi_sessiz_degil(self):
        kodlayici = self._kodlayici()
        paketler = [kodlayici.encode(konusma(i)) for i in range(24)]
        cozucu = self._cozucu()
        for paket in paketler[:20]:
            cozucu.decode(paket)

        kurtarilan = cozucu.decode(paketler[21], fec=True)

        self.assertEqual(len(kurtarilan), CERCEVE_ORNEK * 2)
        self.assertGreater(guc(kurtarilan), 100)

    def test_fec_icin_sonraki_paket_sart(self):
        with self.assertRaises(ValueError):
            self._cozucu().decode(None, fec=True)

    def test_yanlis_boyutta_cerceve_reddedilir(self):
        with self.assertRaises(ValueError):
            self._kodlayici().encode(b"\x00" * 100)

    def test_surum_okunabiliyor(self):
        self.assertIn("libopus", o.library_version())


class DllBulmaTests(unittest.TestCase):
    """DLL aramasi: ortam degiskeni her seyin onunde gelir."""

    def test_ortam_degiskeni_oncelikli(self):
        from unittest import mock

        with mock.patch.dict("os.environ", {"PROXYCHAT_OPUS_DLL": __file__}):
            self.assertEqual(o.dll_path(), __file__)

    def test_olmayan_dosya_yok_sayilir(self):
        from unittest import mock

        with mock.patch.dict("os.environ", {"PROXYCHAT_OPUS_DLL": "yok-boyle-bir-dosya.dll"}):
            self.assertNotEqual(o.dll_path(), "yok-boyle-bir-dosya.dll")


if __name__ == "__main__":
    unittest.main()


class SabitBitHiziTests(unittest.TestCase):
    """VBR ve DTX kapali kalsin; DLL olmadan da kilitli olsun.

    Ses tarafinda mesaj dolgusuna (core/padding.py) gerek yok, cunku
    cerceveler sabit boyda gidiyor: mu-law yapisi geregi (ornek basina bir
    bayt), Opus ise **ayarla**. O ayar iki satir:

        _set(_SET_VBR, 0)   # sabit bit hizi
        _set(_SET_DTX, 0)   # sessizlikte de gonder

    VBR acilirsa paket boyu sese gore degisir ve konusmanin ritmi telden
    okunur; DTX acilirsa sessizlikte paket hic gitmez, yani **kim ne zaman
    konustu** dogrudan gorunur. Ikisi de THREAT_MODEL.md 5.3'un kapali
    tutmayi vaat ettigi sey.

    `test_paket_boyu_sese_gore_degismiyor` bunu gercek DLL ile olcuyor ama
    libopus yoksa atlaniyor -- yani bu makinede ve CI'da hicbir sey ayarin
    degismesini engellemiyordu. Burada ctypes katmani taklit ediliyor, boylece
    test her yerde calisiyor.
    """

    class SahteKutuphane:
        def __init__(self):
            self.ayarlar: list[tuple[int, int]] = []
            self.yikildi = False

        def opus_encoder_create(self, sample_rate, kanal, uygulama, hata):
            return 0x1000  # bos olmayan bir isaretci yeterli

        def opus_encoder_ctl(self, durum, istek, deger):
            self.ayarlar.append((istek.value, deger.value))
            return 0

        def opus_encoder_destroy(self, durum):
            self.yikildi = True

    def _kodlayici(self, **kwargs):
        sahte = self.SahteKutuphane()
        gercek = o.library
        o.library = lambda: sahte
        self.addCleanup(lambda: setattr(o, "library", gercek))
        kodlayici = o.OpusEncoder(ORNEK_HIZI, CERCEVE_MS, **kwargs)
        self.addCleanup(kodlayici.close)
        return sahte

    def test_vbr_kapali(self):
        sahte = self._kodlayici()

        self.assertIn((o._SET_VBR, 0), sahte.ayarlar)

    def test_dtx_kapali(self):
        sahte = self._kodlayici()

        self.assertIn((o._SET_DTX, 0), sahte.ayarlar)

    def test_vbr_hic_acilmiyor(self):
        """Sonradan 1 yazan bir satir eklenirse bu test duser."""
        sahte = self._kodlayici()

        vbr = [deger for istek, deger in sahte.ayarlar if istek == o._SET_VBR]
        self.assertEqual(vbr, [0])

    def test_dtx_hic_acilmiyor(self):
        sahte = self._kodlayici()

        dtx = [deger for istek, deger in sahte.ayarlar if istek == o._SET_DTX]
        self.assertEqual(dtx, [0])

    def test_bit_hizi_isteniyor(self):
        sahte = self._kodlayici(bitrate=16000)

        self.assertIn((o._SET_BITRATE, 16000), sahte.ayarlar)

    def test_kaynak_metninde_vbr_acan_satir_yok(self):
        """Taklit katmani atlanip baska bir yerden acilmasina karsi."""
        from pathlib import Path

        kaynak = Path(o.__file__).read_text(encoding="utf-8")

        for istek in ("_SET_VBR", "_SET_DTX"):
            for satir in kaynak.splitlines():
                if f"_set({istek}," in satir:
                    self.assertIn(f"_set({istek}, 0)", satir, satir.strip())
