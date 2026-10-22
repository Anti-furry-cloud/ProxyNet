"""Host'ta ses aktarmasi (core/voice_relay.py).

Soket yok: aktarici ne gonderilecegini donduruyor, testler onu okuyor.
Adresler yer tutucu; gercek IP testlere girmez.
"""

import unittest

from core.voice_packet import TYPE_AUDIO, TYPE_HELLO, encode_header, pack
from core.voice_relay import (
    RATE_LIMIT_PACKETS,
    TOKEN_BYTES,
    VoiceRelay,
)

AYSE = ("25.12.34.56", 40001)
MEHMET = ("25.12.34.57", 40002)
YABANCI = ("25.12.34.99", 40003)


def ses(sender_id: int, sira: int = 1, govde: bytes = b"sifreli-ses") -> bytes:
    return pack(encode_header(sender_id, sira, 0, TYPE_AUDIO), govde)


def merhaba(sender_id: int, jeton: bytes) -> bytes:
    return pack(encode_header(sender_id, 0, 0, TYPE_HELLO), jeton)


class SaatliRelay(VoiceRelay):
    """Hiz siniri testleri icin zamani elle ilerletilebilen aktarici."""

    def __init__(self):
        self.simdi = 1000.0
        super().__init__(clock=lambda: self.simdi)


class KimlikTests(unittest.TestCase):
    def test_kimlikler_birden_baslar_ve_artar(self):
        relay = VoiceRelay()

        ayse = relay.join("c1", "ayse", "general", AYSE[0])
        mehmet = relay.join("c2", "mehmet", "general", MEHMET[0])

        self.assertEqual((ayse.sender_id, mehmet.sender_id), (1, 2))

    def test_cikan_kimlik_yeniden_kullanilmaz(self):
        """Eski sahibin yolda kalmis paketleri yeninin akisina karismasin."""
        relay = VoiceRelay()
        ayse = relay.join("c1", "ayse", "general", AYSE[0])
        relay.leave("c1")

        yeni = relay.join("c3", "zeynep", "general", AYSE[0])

        self.assertNotEqual(yeni.sender_id, ayse.sender_id)
        self.assertEqual(yeni.sender_id, 2)

    def test_jeton_her_katilimda_yeni_ve_16_bayt(self):
        relay = VoiceRelay()

        ilk = relay.join("c1", "ayse", "general", AYSE[0]).token
        relay.leave("c1")
        ikinci = relay.join("c1", "ayse", "general", AYSE[0]).token

        self.assertEqual(len(ilk), TOKEN_BYTES)
        self.assertNotEqual(ilk, ikinci)

    def test_ayni_istemci_iki_kez_katilirsa_eskisi_dusar(self):
        relay = VoiceRelay()
        ilk = relay.join("c1", "ayse", "general", AYSE[0])

        ikinci = relay.join("c1", "ayse", "general", AYSE[0])

        self.assertEqual(relay.participant("c1"), ikinci)
        self.assertEqual(relay.handle(merhaba(ilk.sender_id, ilk.token), AYSE), [])

    def test_tuzu_bilinmeyen_listede_gorunmez(self):
        """Katilim iki adim: tuz gelmeden kimse o kisiyi cozemez zaten."""
        relay = VoiceRelay()
        relay.join("c1", "ayse", "general", AYSE[0])

        self.assertEqual(relay.peers("general"), [])
        self.assertTrue(relay.set_salt("c1", "ef" * 16))
        self.assertEqual(relay.peers("general")[0]["salt"], "ef" * 16)
        self.assertFalse(relay.set_salt("yok-boyle-istemci", "ab" * 16))

    def test_katilimci_listesinde_ip_yok(self):
        relay = VoiceRelay()
        relay.join("c1", "ayse", "general", AYSE[0], session_salt="ab" * 16, public_key="AAAA")

        [katilimci] = relay.peers("general")

        self.assertEqual(
            katilimci,
            {"user": "ayse", "sender_id": 1, "salt": "ab" * 16, "pub": "AAAA"},
        )
        self.assertNotIn(AYSE[0], str(katilimci))

    def test_acik_anahtar_duyuruluyor(self):
        """Alicilar ses anahtarini kimden turetecegini bununla buluyor."""
        relay = VoiceRelay()
        relay.join("c1", "ayse", "general", AYSE[0], session_salt="ab" * 16, public_key="ACIK")

        [katilimci] = relay.peers("general")

        self.assertEqual(katilimci["pub"], "ACIK")

    def test_oda_degisince_ses_de_tasinir(self):
        relay = VoiceRelay()
        relay.join("c1", "ayse", "general", AYSE[0], session_salt="ab" * 16)

        relay.move("c1", "random")

        self.assertEqual(relay.peers("general"), [])
        self.assertEqual(len(relay.peers("random")), 1)


class ElSikismaTests(unittest.TestCase):
    def _relay(self):
        relay = VoiceRelay()
        self.ayse = relay.join("c1", "ayse", "general", AYSE[0])
        self.mehmet = relay.join("c2", "mehmet", "general", MEHMET[0])
        return relay

    def test_dogru_jeton_adresi_bagliyor(self):
        relay = self._relay()

        cevap = relay.handle(merhaba(self.ayse.sender_id, self.ayse.token), AYSE)

        self.assertEqual(cevap, [], "merhabaya cevap verilmemeli")
        self.assertEqual(relay.participant("c1").address, AYSE)

    def test_yanlis_jeton_baglamaz(self):
        relay = self._relay()

        relay.handle(merhaba(self.ayse.sender_id, b"\x00" * TOKEN_BYTES), AYSE)

        self.assertIsNone(relay.participant("c1").address)
        self.assertEqual(relay.rejected, 1)

    def test_baskasinin_jetonu_kendi_kimligine_yaramaz(self):
        relay = self._relay()

        relay.handle(merhaba(self.ayse.sender_id, self.mehmet.token), AYSE)

        self.assertIsNone(relay.participant("c1").address)

    def test_baska_ipden_gelen_merhaba_reddedilir(self):
        """Jeton yolda okunmus olsa bile kaynak IP tutmali."""
        relay = self._relay()

        relay.handle(merhaba(self.ayse.sender_id, self.ayse.token), (YABANCI[0], 5000))

        self.assertIsNone(relay.participant("c1").address)
        self.assertEqual(relay.rejected, 1)

    def test_port_degisirse_ayni_jetonla_yeniden_baglanir(self):
        """NAT portu degistirebilir ya da istemci yeniden baslayabilir."""
        relay = self._relay()
        relay.handle(merhaba(self.ayse.sender_id, self.ayse.token), AYSE)
        yeni_port = (AYSE[0], 45000)

        relay.handle(merhaba(self.ayse.sender_id, self.ayse.token), yeni_port)

        self.assertEqual(relay.participant("c1").address, yeni_port)

    def test_tanimayan_kimlik_reddedilir(self):
        relay = self._relay()

        self.assertEqual(relay.handle(merhaba(999, b"x" * TOKEN_BYTES), AYSE), [])
        self.assertEqual(relay.rejected, 1)


class AktarmaTests(unittest.TestCase):
    def _bagli_relay(self, clock_relay=None):
        relay = clock_relay or VoiceRelay()
        self.ayse = relay.join("c1", "ayse", "general", AYSE[0])
        self.mehmet = relay.join("c2", "mehmet", "general", MEHMET[0])
        relay.handle(merhaba(self.ayse.sender_id, self.ayse.token), AYSE)
        relay.handle(merhaba(self.mehmet.sender_id, self.mehmet.token), MEHMET)
        return relay

    def test_ses_odadaki_otekilere_gider(self):
        relay = self._bagli_relay()
        paket = ses(self.ayse.sender_id)

        gonderilecek = relay.handle(paket, AYSE)

        self.assertEqual(gonderilecek, [(paket, MEHMET)])

    def test_gonderene_geri_gitmez(self):
        relay = self._bagli_relay()

        gonderilecek = relay.handle(ses(self.ayse.sender_id), AYSE)

        self.assertNotIn(AYSE, [adres for _veri, adres in gonderilecek])

    def test_paket_degistirilmeden_iletilir(self):
        """Host sesi cozmez, dokunmaz: bayt bayt ayni paket gider."""
        relay = self._bagli_relay()
        paket = ses(self.ayse.sender_id, govde=b"bu-sifreli-kalmali")

        [(veri, _adres)] = relay.handle(paket, AYSE)

        self.assertEqual(veri, paket)

    def test_baska_odadaki_duymaz(self):
        relay = self._bagli_relay()
        relay.move("c2", "random")

        self.assertEqual(relay.handle(ses(self.ayse.sender_id), AYSE), [])

    def test_baglanmamis_kisiye_gonderilmez(self):
        relay = VoiceRelay()
        ayse = relay.join("c1", "ayse", "general", AYSE[0])
        relay.join("c2", "mehmet", "general", MEHMET[0])  # merhaba yollamadi
        relay.handle(merhaba(ayse.sender_id, ayse.token), AYSE)

        self.assertEqual(relay.handle(ses(ayse.sender_id), AYSE), [])

    def test_merhabasiz_ses_reddedilir(self):
        relay = VoiceRelay()
        ayse = relay.join("c1", "ayse", "general", AYSE[0])
        relay.join("c2", "mehmet", "general", MEHMET[0])

        self.assertEqual(relay.handle(ses(ayse.sender_id), AYSE), [])
        self.assertEqual(relay.rejected, 1)

    def test_baglandiktan_sonra_baska_adresten_gelen_ses_reddedilir(self):
        relay = self._bagli_relay()

        gonderilecek = relay.handle(ses(self.ayse.sender_id), (AYSE[0], 55555))

        self.assertEqual(gonderilecek, [])
        self.assertEqual(relay.rejected, 1)

    def test_odaya_bagli_olmayan_sahte_paket_reddedilir(self):
        relay = self._bagli_relay()

        self.assertEqual(relay.handle(ses(4242), YABANCI), [])

    def test_bozuk_ve_tanimsiz_paketler_atilir(self):
        relay = self._bagli_relay()

        self.assertEqual(relay.handle(b"", AYSE), [])
        self.assertEqual(relay.handle(b"x" * 10, AYSE), [])
        bilinmeyen_tip = pack(encode_header(self.ayse.sender_id, 1, 0, TYPE_AUDIO), b"ses")
        bozuk_surum = bytes([9]) + bilinmeyen_tip[1:]
        self.assertEqual(relay.handle(bozuk_surum, AYSE), [])
        self.assertEqual(relay.rejected, 3)

    def test_hiz_siniri_seli_kesiyor(self):
        relay = self._bagli_relay(SaatliRelay())

        iletilen = sum(
            1 for i in range(RATE_LIMIT_PACKETS + 20) if relay.handle(ses(self.ayse.sender_id, i + 1), AYSE)
        )

        self.assertEqual(iletilen, RATE_LIMIT_PACKETS)

    def test_pencere_dolunca_yeniden_akar(self):
        relay = self._bagli_relay(SaatliRelay())
        for i in range(RATE_LIMIT_PACKETS + 5):
            relay.handle(ses(self.ayse.sender_id, i + 1), AYSE)

        relay.simdi += 1.0

        self.assertTrue(relay.handle(ses(self.ayse.sender_id, 999), AYSE))

    def test_hiz_siniri_gonderen_basina(self):
        """Biri sel gonderirse otekinin sesi kesilmemeli."""
        relay = self._bagli_relay(SaatliRelay())
        for i in range(RATE_LIMIT_PACKETS + 5):
            relay.handle(ses(self.ayse.sender_id, i + 1), AYSE)

        self.assertTrue(relay.handle(ses(self.mehmet.sender_id, 1), MEHMET))


class IlkeTests(unittest.TestCase):
    def test_aktarma_cozme_yetenegi_import_etmiyor(self):
        """Ilke 1: sunucu zincirinde cozme yetenegi bulunmaz.

        Aciklamalarda kelime gecebilir; bakilan sey import satirlari.
        """
        import ast
        from pathlib import Path

        agac = ast.parse(Path("core/voice_relay.py").read_text(encoding="utf-8"))
        moduller = set()
        for dugum in ast.walk(agac):
            if isinstance(dugum, ast.Import):
                moduller.update(ad.name for ad in dugum.names)
            elif isinstance(dugum, ast.ImportFrom) and dugum.module:
                moduller.add(dugum.module)

        for yasak in ("cryptography", "core.voice_crypto"):
            self.assertFalse(
                any(m == yasak or m.startswith(yasak + ".") for m in moduller),
                f"{yasak} import edilmis: {moduller}",
            )


if __name__ == "__main__":
    unittest.main()
