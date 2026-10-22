"""Sesli sohbet cekirdegi: paket bicimi, sifreleme ve jitter tamponu.

Bu testlerin hicbiri ses donanimi, soket ya da Qt kullanmaz; hepsi saf
mantik uzerinde calisir ve CI'da kosabilir.
"""

import unittest

from core.crypto import derive_master_key
from core.voice_crypto import (
    SESSION_SALT_BYTES,
    VOICE_ENCRYPTION_SCHEME,
    NullVoiceCipher,
    ReplayError,
    ReplayWindow,
    SequenceReuseError,
    UnknownSenderError,
    VoiceCipher,
    VoiceDecryptionError,
    derive_session_key,
    derive_voice_key,
    make_voice_cipher,
)
from core.voice_jitter import JitterBuffer
from core.voice_packet import (
    HEADER_BYTES,
    MAX_DATAGRAM_BYTES,
    TYPE_AUDIO,
    VOICE_PROTOCOL_VERSION,
    VoicePacketError,
    decode_header,
    encode_header,
    pack,
    read_sender_id,
    unpack,
)


def ses_cercevesi(tohum: int, uzunluk: int = 320) -> bytes:
    """Testlerde mikrofon yerine gecen, tekrarlanabilir bayt dizisi."""
    return bytes((tohum * 31 + i) % 256 for i in range(uzunluk))


def tanistir(alici, *gonderenler) -> None:
    """Sinyallesmenin yapacagi isi yapar: gonderenlerin oturum tuzlarini bildirir."""
    for gonderen in gonderenler:
        alici.add_sender(gonderen.sender_id, gonderen.session_salt)


class PaketBicimiTests(unittest.TestCase):
    def test_baslik_gidis_donusu(self):
        header = decode_header(encode_header(7, 1234, 5678))

        self.assertEqual(header.version, VOICE_PROTOCOL_VERSION)
        self.assertEqual(header.type, TYPE_AUDIO)
        self.assertEqual(header.sender_id, 7)
        self.assertEqual(header.sequence, 1234)
        self.assertEqual(header.timestamp_ms, 5678)

    def test_baslik_sabit_boyutlu(self):
        self.assertEqual(len(encode_header(0, 0, 0)), HEADER_BYTES)
        self.assertEqual(len(encode_header(4294967295, 2**64 - 1, 2**32 - 1)), HEADER_BYTES)

    def test_zaman_damgasi_basa_sarar(self):
        header = decode_header(encode_header(1, 1, 2**32 + 5))

        self.assertEqual(header.timestamp_ms, 5)

    def test_sigmayan_alanlar_reddedilir(self):
        with self.assertRaises(VoicePacketError):
            encode_header(2**32, 1, 1)
        with self.assertRaises(VoicePacketError):
            encode_header(1, 2**64, 1)

    def test_kisa_datagram_reddedilir(self):
        with self.assertRaises(VoicePacketError):
            decode_header(b"kisa")

    def test_bilinmeyen_surum_reddedilir(self):
        bozuk = bytearray(encode_header(1, 1, 1))
        bozuk[0] = 99

        with self.assertRaises(VoicePacketError):
            decode_header(bytes(bozuk))

    def test_bilinmeyen_tip_reddedilir(self):
        bozuk = bytearray(encode_header(1, 1, 1))
        bozuk[1] = 99

        with self.assertRaises(VoicePacketError):
            decode_header(bytes(bozuk))

    def test_paket_ayrilir(self):
        header, body = unpack(pack(encode_header(3, 9, 180), b"sifreli"))

        self.assertEqual(header.sender_id, 3)
        self.assertEqual(body, b"sifreli")

    def test_bos_govde_reddedilir(self):
        with self.assertRaises(VoicePacketError):
            unpack(encode_header(1, 1, 1))

    def test_mtu_ustundeki_paket_reddedilir(self):
        with self.assertRaises(VoicePacketError):
            pack(encode_header(1, 1, 1), b"x" * MAX_DATAGRAM_BYTES)


class AktarmaGorunumuTests(unittest.TestCase):
    """Host'un ses paketinden gorebildigi (ve goremedigi) seyler."""

    def test_host_gondereni_anahtarsiz_okuyabilir(self):
        datagram = VoiceCipher("general", "gizli", 42).seal(ses_cercevesi(1), 0, 0)

        # Host'un elinde oda parolasi yok; yine de yonlendirebilmeli.
        self.assertEqual(read_sender_id(datagram), 42)

    def test_host_sesin_kendisini_goremez(self):
        audio = b"gizli ses verisi" * 10
        datagram = VoiceCipher("general", "gizli", 42).seal(audio, 0, 0)

        self.assertNotIn(audio, datagram)


class SesAnahtariTests(unittest.TestCase):
    def test_ayni_oda_ve_parola_ayni_anahtari_verir(self):
        self.assertEqual(derive_voice_key("general", "gizli"), derive_voice_key("general", "gizli"))

    def test_farkli_parola_farkli_anahtar(self):
        self.assertNotEqual(derive_voice_key("general", "gizli"), derive_voice_key("general", "x"))

    def test_oda_adi_anahtara_giriyor(self):
        self.assertNotEqual(derive_voice_key("general", "gizli"), derive_voice_key("baska", "gizli"))

    def test_ses_anahtari_metin_anahtarindan_farkli(self):
        """Ayni parola, ayni oda; ama iki kullanim ayni anahtari paylasmamali."""
        ses = derive_voice_key("general", "gizli")

        self.assertNotEqual(ses, derive_master_key("general", "gizli"))

    def test_anahtar_32_bayt(self):
        self.assertEqual(len(derive_voice_key("general", "gizli")), 32)

    def test_ana_anahtardan_turuyor(self):
        """Prototipin ses anahtari ana anahtardan HKDF ile cikar.

        Urun yolu artik boyle degil: orada ses anahtari oda oturumunun
        gonderen anahtarindan turuyor (`derive_voice_session_key`). Bu
        turetme prototipe ait ve Faz 0 kayitlariyla uyumlu kalmak zorunda.
        """
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF

        from core import voice_crypto

        beklenen = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=voice_crypto._VOICE_KEY_INFO,
        ).derive(derive_master_key("general", "gizli"))

        self.assertEqual(derive_voice_key("general", "gizli"), beklenen)


class TekrarPenceresiTests(unittest.TestCase):
    def test_ilk_paket_kabul_edilir(self):
        self.assertTrue(ReplayWindow().check(0))

    def test_ayni_numara_ikinci_kez_reddedilir(self):
        window = ReplayWindow()
        window.check(5)

        self.assertFalse(window.check(5))

    def test_sirasi_bozulan_paket_kabul_edilir(self):
        window = ReplayWindow()
        window.check(10)

        self.assertTrue(window.check(8))
        self.assertTrue(window.check(9))
        self.assertFalse(window.check(8))

    def test_pencerenin_disindaki_eski_paket_reddedilir(self):
        window = ReplayWindow(size=8)
        window.check(100)

        self.assertFalse(window.check(91))
        self.assertTrue(window.check(93))

    def test_buyuk_sicramadan_sonra_gecmis_unutulur(self):
        window = ReplayWindow(size=8)
        window.check(1)
        window.check(2)

        self.assertTrue(window.check(1000))
        self.assertEqual(window.highest, 1000)
        # Sicramanin gerisi artik "cok eski".
        self.assertFalse(window.check(2))
        # Yeni pencere icindeki numaralar hala taze.
        self.assertTrue(window.check(999))
        self.assertFalse(window.check(1000))

    def test_sifir_boy_pencere_reddedilir(self):
        with self.assertRaises(ValueError):
            ReplayWindow(size=0)


class SesSifrelemeTests(unittest.TestCase):
    def test_gidis_donusu(self):
        gonderen = VoiceCipher("general", "gizli", 1)
        alici = VoiceCipher("general", "gizli", 2)
        tanistir(alici, gonderen)
        audio = ses_cercevesi(3)

        header, cozulen = alici.open(gonderen.seal(audio, 0, 0))

        self.assertEqual(cozulen, audio)
        self.assertEqual(header.sender_id, 1)

    def test_yanlis_parola_cozemez(self):
        gonderen = VoiceCipher("general", "gizli", 1)
        alici = VoiceCipher("general", "yanlis", 2)
        tanistir(alici, gonderen)

        with self.assertRaises(VoiceDecryptionError) as hata:
            alici.open(gonderen.seal(ses_cercevesi(1), 0, 0))
        self.assertIs(type(hata.exception), VoiceDecryptionError)

    def test_baslik_kurcalanirsa_cozulemez(self):
        """Baslik AAD oldugu icin aktarmayi yapan taraf onu degistiremez."""
        gonderen = VoiceCipher("general", "gizli", 1)
        alici = VoiceCipher("general", "gizli", 2)
        tanistir(alici, gonderen)
        datagram = bytearray(gonderen.seal(ses_cercevesi(1), 0, 0))
        datagram[17] ^= 0xFF  # zaman damgasinin son bayti: nonce degismez, yalnizca AAD

        with self.assertRaises(VoiceDecryptionError) as hata:
            alici.open(bytes(datagram))
        self.assertIs(type(hata.exception), VoiceDecryptionError)

    def test_host_paketi_baska_gonderenin_adina_yonlendiremez(self):
        gonderen = VoiceCipher("general", "gizli", 1)
        diger = VoiceCipher("general", "gizli", 3)
        alici = VoiceCipher("general", "gizli", 2)
        tanistir(alici, gonderen, diger)
        datagram = bytearray(gonderen.seal(ses_cercevesi(1), 0, 0))
        datagram[5] ^= 0x02  # gonderen kimligi 1 -> 3

        with self.assertRaises(VoiceDecryptionError) as hata:
            alici.open(bytes(datagram))
        self.assertIs(type(hata.exception), VoiceDecryptionError)

    def test_govde_kurcalanirsa_cozulemez(self):
        gonderen = VoiceCipher("general", "gizli", 1)
        alici = VoiceCipher("general", "gizli", 2)
        tanistir(alici, gonderen)
        datagram = bytearray(gonderen.seal(ses_cercevesi(1), 0, 0))
        datagram[-1] ^= 0xFF

        with self.assertRaises(VoiceDecryptionError) as hata:
            alici.open(bytes(datagram))
        self.assertIs(type(hata.exception), VoiceDecryptionError)

    def test_ayni_ses_farkli_sirada_farkli_sifreli_metin_verir(self):
        gonderen = VoiceCipher("general", "gizli", 1)
        audio = ses_cercevesi(4)

        self.assertNotEqual(gonderen.seal(audio, 0, 0), gonderen.seal(audio, 1, 0))

    def test_tekrarlanan_paket_reddedilir(self):
        gonderen = VoiceCipher("general", "gizli", 1)
        alici = VoiceCipher("general", "gizli", 2)
        tanistir(alici, gonderen)
        datagram = gonderen.seal(ses_cercevesi(5), 7, 140)

        alici.open(datagram)

        with self.assertRaises(ReplayError):
            alici.open(datagram)

    def test_tekrar_penceresi_gonderen_basina_ayri(self):
        alici = VoiceCipher("general", "gizli", 9)
        birinci = VoiceCipher("general", "gizli", 1)
        ikinci = VoiceCipher("general", "gizli", 2)
        tanistir(alici, birinci, ikinci)

        alici.open(birinci.seal(ses_cercevesi(6), 0, 0))
        # Ayni sira numarasi, baska gonderen: tekrar sayilmamali.
        self.assertEqual(alici.open(ikinci.seal(ses_cercevesi(7), 0, 0))[1], ses_cercevesi(7))

    def test_sema_etiketi(self):
        self.assertEqual(VoiceCipher("general", "gizli", 1).scheme, VOICE_ENCRYPTION_SCHEME)
        self.assertTrue(VoiceCipher("general", "gizli", 1).enabled)

    def test_sifreleme_yuku_16_bayt(self):
        """AES-GCM etiketi disinda sismeme olmamali (base64 yok, tuz pakette degil)."""
        audio = ses_cercevesi(9, 320)
        datagram = VoiceCipher("general", "gizli", 1).seal(audio, 0, 0)

        self.assertEqual(len(datagram), HEADER_BYTES + len(audio) + 16)


class OturumAyrimiTests(unittest.TestCase):
    """v1'deki nonce tekrari hatasinin geri gelmemesi icin.

    v1'de anahtar oda adi ve paroladan turuyordu ve hic degismiyordu; ayni
    gonderen kimligi yeni bir oturumda sifirdan saydiginda ayni anahtarla
    ayni nonce tekrar kullaniliyordu.
    """

    def test_ayni_kimlik_iki_oturumda_anahtar_akisini_tekrarlamaz(self):
        dun = VoiceCipher("general", "gizli", 1)
        bugun = VoiceCipher("general", "gizli", 1)  # Host yeniden baslamis, ayni kimlik
        gizli_ses = b"GIZLI KONUSMA: yarin saat 5te" + bytes(291)
        sessizlik = bytes(320)  # saldirganin tahmin edebilecegi cerceve

        a = dun.seal(gizli_ses, 0, 0)[HEADER_BYTES:-16]
        b = bugun.seal(sessizlik, 0, 0)[HEADER_BYTES:-16]
        sifreli_xor = bytes(x ^ y for x, y in zip(a, b))

        self.assertNotEqual(sifreli_xor, bytes(x ^ y for x, y in zip(gizli_ses, sessizlik)))
        self.assertNotIn(b"GIZLI KONUSMA", sifreli_xor)

    def test_her_oturum_kendi_tuzunu_uretir(self):
        birinci = VoiceCipher("general", "gizli", 1)
        ikinci = VoiceCipher("general", "gizli", 1)

        self.assertEqual(len(birinci.session_salt), SESSION_SALT_BYTES)
        self.assertNotEqual(birinci.session_salt, ikinci.session_salt)

    def test_eski_oturumun_kaydedilmis_paketi_yeni_oturumda_cozulemez(self):
        alici = VoiceCipher("general", "gizli", 9)
        dun = VoiceCipher("general", "gizli", 1)
        tanistir(alici, dun)
        kaydedilen = dun.seal(ses_cercevesi(1), 0, 0)
        alici.open(kaydedilen)

        bugun = VoiceCipher("general", "gizli", 1)
        tanistir(alici, bugun)

        with self.assertRaises(VoiceDecryptionError) as hata:
            alici.open(kaydedilen)
        self.assertIs(type(hata.exception), VoiceDecryptionError)
        self.assertEqual(alici.open(bugun.seal(ses_cercevesi(2), 0, 0))[1], ses_cercevesi(2))

    def test_odadan_cikip_giren_sifirdan_sayabilir(self):
        alici = VoiceCipher("general", "gizli", 9)
        ilk = VoiceCipher("general", "gizli", 1)
        tanistir(alici, ilk)
        alici.open(ilk.seal(ses_cercevesi(8), 0, 0))

        alici.forget(1)
        yeniden = VoiceCipher("general", "gizli", 1)  # yeni oturum = yeni ornek
        tanistir(alici, yeniden)

        self.assertEqual(alici.open(yeniden.seal(ses_cercevesi(8), 0, 0))[1], ses_cercevesi(8))

    def test_unutulan_gonderenin_paketi_reddedilir(self):
        alici = VoiceCipher("general", "gizli", 9)
        gonderen = VoiceCipher("general", "gizli", 1)
        tanistir(alici, gonderen)
        alici.forget(1)

        with self.assertRaises(UnknownSenderError):
            alici.open(gonderen.seal(ses_cercevesi(1), 0, 0))

    def test_ayni_sira_numarasi_ikinci_kez_muhurlenemez(self):
        gonderen = VoiceCipher("general", "gizli", 1)
        gonderen.seal(ses_cercevesi(1), 5, 100)

        with self.assertRaises(SequenceReuseError):
            gonderen.seal(ses_cercevesi(2), 5, 100)
        with self.assertRaises(SequenceReuseError):
            gonderen.seal(ses_cercevesi(2), 4, 80)
        gonderen.seal(ses_cercevesi(2), 6, 120)

    def test_basarisiz_muhurleme_sira_numarasini_harcamaz(self):
        gonderen = VoiceCipher("general", "gizli", 1)

        with self.assertRaises(VoicePacketError):
            gonderen.seal(b"x" * MAX_DATAGRAM_BYTES, 0, 0)
        gonderen.seal(ses_cercevesi(1), 0, 0)

    def test_bilinmeyen_gonderen_reddedilir(self):
        gonderen = VoiceCipher("general", "gizli", 1)

        with self.assertRaises(UnknownSenderError):
            VoiceCipher("general", "gizli", 2).open(gonderen.seal(ses_cercevesi(1), 0, 0))

    def test_kendi_paketimiz_geri_donunce_kayitsiz_cozulur(self):
        biz = VoiceCipher("general", "gizli", 1)

        self.assertEqual(biz.open(biz.seal(ses_cercevesi(1), 0, 0))[1], ses_cercevesi(1))

    def test_kendi_kimligimiz_baska_tuzla_kaydedilemez(self):
        biz = VoiceCipher("general", "gizli", 1)
        cakisan = VoiceCipher("general", "gizli", 1)

        biz.add_sender(1, biz.session_salt)  # ayni tuz: sorun yok
        with self.assertRaises(ValueError):
            biz.add_sender(1, cakisan.session_salt)

    def test_ayni_tuzla_yeniden_kayit_tekrar_korumasini_sifirlamaz(self):
        """voice_peers tekrar gelebilir; bu bir tekrar saldirisina kapi acmamali."""
        gonderen = VoiceCipher("general", "gizli", 1)
        alici = VoiceCipher("general", "gizli", 2)
        tanistir(alici, gonderen)
        datagram = gonderen.seal(ses_cercevesi(1), 0, 0)
        alici.open(datagram)

        tanistir(alici, gonderen)

        with self.assertRaises(ReplayError):
            alici.open(datagram)

    def test_yanlis_uzunlukta_tuz_reddedilir(self):
        alici = VoiceCipher("general", "gizli", 2)

        with self.assertRaises(ValueError):
            alici.add_sender(1, b"kisa")
        with self.assertRaises(ValueError):
            derive_session_key(bytes(32), bytes(SESSION_SALT_BYTES + 1), 1)

    def test_oturum_anahtari_tuza_ve_kimlige_bagli(self):
        anahtar = derive_voice_key("general", "gizli")
        tuz = bytes(range(SESSION_SALT_BYTES))
        baska_tuz = bytes(reversed(range(SESSION_SALT_BYTES)))

        self.assertEqual(derive_session_key(anahtar, tuz, 1), derive_session_key(anahtar, tuz, 1))
        self.assertNotEqual(derive_session_key(anahtar, tuz, 1), derive_session_key(anahtar, tuz, 2))
        self.assertNotEqual(derive_session_key(anahtar, tuz, 1), derive_session_key(anahtar, baska_tuz, 1))
        self.assertNotEqual(derive_session_key(anahtar, tuz, 1), anahtar)


class ParolasizSesTests(unittest.TestCase):
    def test_parolasiz_oda_sesi_gecirir(self):
        gonderen = NullVoiceCipher(1)
        alici = NullVoiceCipher(2)
        tanistir(alici, gonderen)
        audio = ses_cercevesi(10)

        self.assertEqual(alici.open(gonderen.seal(audio, 0, 0))[1], audio)

    def test_parolasiz_ses_sifrelenmemis(self):
        audio = b"acik ses"

        self.assertIn(audio, NullVoiceCipher(1).seal(audio, 0, 0))

    def test_parolasiz_surum_de_tekrari_reddeder(self):
        gonderen = NullVoiceCipher(1)
        alici = NullVoiceCipher(2)
        tanistir(alici, gonderen)
        datagram = gonderen.seal(ses_cercevesi(11), 3, 60)
        alici.open(datagram)

        with self.assertRaises(ReplayError):
            alici.open(datagram)

    def test_parolasiz_surum_de_ayni_oturum_kurallarini_uygular(self):
        gonderen = NullVoiceCipher(1)
        gonderen.seal(ses_cercevesi(1), 0, 0)

        with self.assertRaises(SequenceReuseError):
            gonderen.seal(ses_cercevesi(1), 0, 0)
        with self.assertRaises(UnknownSenderError):
            NullVoiceCipher(2).open(NullVoiceCipher(1).seal(ses_cercevesi(1), 0, 0))

    def test_parolasiz_oda_sifrelemiyor(self):
        self.assertIsInstance(make_voice_cipher("general", "", 1), NullVoiceCipher)
        self.assertIsInstance(make_voice_cipher("general", None, 1), NullVoiceCipher)

    def test_anahtarsiz_parolali_oturum_reddediliyor(self):
        """Ileri gizlilikten sessizce dusmek yok.

        Oda oturumunun gonderen anahtari verilmezse fabrika hata verir;
        paroladan turetilen semayi isteyen (yalnizca prototip) bunu acikca
        soylemek zorunda.
        """
        from core.voice_crypto import SenderKeyMissingError

        with self.assertRaises(SenderKeyMissingError):
            make_voice_cipher("general", "gizli", 1)

    def test_prototip_semayi_acikca_isteyebiliyor(self):
        cipher = make_voice_cipher("general", "gizli", 1, allow_password_scheme=True)

        self.assertIsInstance(cipher, VoiceCipher)

    def test_anahtar_verilince_ileri_gizli_surum(self):
        from core.voice_crypto import ForwardSecretVoiceCipher

        cipher = make_voice_cipher("general", "gizli", 1, b"k" * 32)

        self.assertIsInstance(cipher, ForwardSecretVoiceCipher)

    def test_iki_surum_ayni_tel_bicimini_uretir(self):
        sifreli = VoiceCipher("general", "gizli", 1).seal(ses_cercevesi(12), 4, 80)
        acik = NullVoiceCipher(1).seal(ses_cercevesi(12), 4, 80)

        self.assertEqual(sifreli[:HEADER_BYTES], acik[:HEADER_BYTES])


class JitterTamponuTests(unittest.TestCase):
    def kur(self, **kwargs) -> JitterBuffer:
        varsayilan = {"target_ms": 60, "frame_ms": 20, "capacity": 50}
        varsayilan.update(kwargs)
        return JitterBuffer(**varsayilan)

    def test_hedef_dolmadan_ses_cikmaz(self):
        buffer = self.kur()
        buffer.push(0, b"a")
        buffer.push(1, b"b")

        self.assertIsNone(buffer.pop())
        self.assertTrue(buffer.filling)
        self.assertEqual(buffer.buffered_ms, 40)

    def test_hedef_dolunca_sirayla_cikar(self):
        buffer = self.kur()
        for sira, cerceve in enumerate([b"a", b"b", b"c"]):
            buffer.push(sira, cerceve)

        self.assertEqual([buffer.pop(), buffer.pop(), buffer.pop()], [b"a", b"b", b"c"])
        self.assertFalse(buffer.filling)

    def test_sirasi_bozulan_paketler_duzeltilir(self):
        buffer = self.kur()
        buffer.push(2, b"c")
        buffer.push(0, b"a")
        buffer.push(1, b"b")

        self.assertEqual([buffer.pop(), buffer.pop(), buffer.pop()], [b"a", b"b", b"c"])

    def test_kayip_cerceve_yerine_sessizlik(self):
        buffer = self.kur()
        for sira, cerceve in [(0, b"a"), (1, b"b"), (2, b"c"), (4, b"e")]:
            buffer.push(sira, cerceve)

        cikan = [buffer.pop() for _ in range(5)]

        self.assertEqual(cikan, [b"a", b"b", b"c", None, b"e"])
        self.assertEqual(buffer.lost, 1)

    def test_gec_kalan_paket_atilir(self):
        buffer = self.kur()
        for sira in range(3):
            buffer.push(sira, bytes([sira]))
        buffer.pop()
        buffer.pop()

        self.assertFalse(buffer.push(0, b"gec"))
        self.assertEqual(buffer.late, 1)

    def test_tekrarlanan_paket_atilir(self):
        buffer = self.kur()
        buffer.push(1, b"b")

        self.assertFalse(buffer.push(1, b"b"))
        self.assertEqual(buffer.duplicate, 1)

    def test_tampon_tasarsa_yeni_paket_atilir(self):
        buffer = self.kur(capacity=3)
        for sira in range(3):
            buffer.push(sira, bytes([sira]))

        self.assertFalse(buffer.push(3, b"d"))
        self.assertEqual(buffer.overflow, 1)

    def test_tampon_bosalinca_yeniden_doldurur(self):
        buffer = self.kur()
        for sira in range(3):
            buffer.push(sira, bytes([sira]))
        for _ in range(3):
            buffer.pop()

        self.assertIsNone(buffer.pop())
        self.assertEqual(buffer.underrun, 1)
        self.assertTrue(buffer.filling)

    def test_susup_devam_eden_konusma_gec_sayilmaz(self):
        """Underrun'dan sonra _next ileri kacmamali."""
        buffer = self.kur()
        for sira in range(3):
            buffer.push(sira, bytes([sira]))
        for _ in range(4):
            buffer.pop()

        # Karsi taraf yeniden konusmaya basliyor.
        for sira in (3, 4, 5):
            self.assertTrue(buffer.push(sira, bytes([sira])))

        self.assertEqual(buffer.pop(), bytes([3]))
        self.assertEqual(buffer.late, 0)

    def test_gonderen_yeniden_baslarsa_akis_sifirlanir(self):
        buffer = self.kur()
        for sira in range(3):
            buffer.push(sira, bytes([sira]))
        buffer.pop()

        self.assertTrue(buffer.push(9000, b"yeni"))
        self.assertEqual(buffer.resync, 1)
        self.assertTrue(buffer.filling)
        self.assertEqual(buffer.buffered_frames, 1)

    def test_reset_akisi_bastan_baslatir(self):
        buffer = self.kur()
        for sira in range(3):
            buffer.push(sira, bytes([sira]))
        buffer.pop()

        buffer.reset()

        self.assertTrue(buffer.filling)
        self.assertEqual(buffer.buffered_frames, 0)

    def test_hedef_cerceve_sayisi_yukari_yuvarlanir(self):
        self.assertEqual(JitterBuffer(target_ms=50, frame_ms=20).target_frames, 3)
        self.assertEqual(JitterBuffer(target_ms=0, frame_ms=20).target_frames, 1)

    def test_gecersiz_ayarlar_reddedilir(self):
        with self.assertRaises(ValueError):
            JitterBuffer(frame_ms=0)
        with self.assertRaises(ValueError):
            JitterBuffer(target_ms=-1)
        with self.assertRaises(ValueError):
            JitterBuffer(capacity=0)


def akis(buffer: JitterBuffer, varislar: dict[int, list[int]], tik_sayisi: int):
    """Her tikte (20 ms) once o tikte gelen paketler itilir, sonra bir cerceve cekilir.

    (tik, gecikme) ciftlerini ve gercek cercevenin atildigi tikleri dondurur.
    Gecikme tik cinsinden: calindigi tik eksi gonderildigi tik.
    """
    gecikmeler = []
    atma_tikleri = []
    for tik in range(tik_sayisi):
        for sira in varislar.get(tik, []):
            buffer.push(sira, sira.to_bytes(4, "big"))
        onceki = buffer.dropped
        yuk = buffer.pop()
        if buffer.dropped > onceki:
            atma_tikleri.append(tik)
        if yuk is not None:
            gecikmeler.append((tik, tik - int.from_bytes(yuk, "big")))
    return gecikmeler, atma_tikleri


def sicramali_varis() -> dict[int, list[int]]:
    """Her paket 1 tik gecikmeyle gelir; 50-62 arasi paketler ag takilip 63. tikte toplu gelir.

    Olculen hattaki 250 ms'lik sicramalarin sade hali.
    """
    varis: dict[int, list[int]] = {}
    for sira in range(300):
        tik = 63 if 50 <= sira <= 62 else sira + 1
        varis.setdefault(tik, []).append(sira)
    return varis


class JitterYetismeTests(unittest.TestCase):
    """Bir gecikme sicramasi kalici gecikmeye donusmemeli."""

    def test_yetisme_kapaliyken_sicrama_gecikmeye_kalici_eklenir(self):
        """Duzeltmeden onceki davranis; simulasyonda bulunan hata buydu."""
        gecikmeler, _ = akis(JitterBuffer(catchup_interval=None), sicramali_varis(), 300)

        sonra = [d for tik, d in gecikmeler if tik >= 150]
        self.assertGreaterEqual(min(sonra), 12)

    def test_sicramadan_sonra_gecikme_hedefe_geri_iner(self):
        buffer = JitterBuffer()
        gecikmeler, _ = akis(buffer, sicramali_varis(), 300)

        once = {d for tik, d in gecikmeler if 20 <= tik < 50}
        sicrama = max(d for tik, d in gecikmeler if 63 <= tik < 70)
        sonra = [d for tik, d in gecikmeler if tik >= 150]

        self.assertEqual(once, {3})  # 1 tik ag + 60 ms tampon
        self.assertGreaterEqual(sicrama, 12)  # sicrama gercekten oldu
        self.assertLessEqual(max(sonra), buffer.target_frames + buffer.catchup_slack_frames)
        self.assertFalse(buffer.catching_up)
        # Birikmis ~10 cerceveden fazlasi atilmamali.
        self.assertLessEqual(buffer.dropped, 12)

    def test_yetisme_hizi_sinirli(self):
        buffer = JitterBuffer()
        _, atma_tikleri = akis(buffer, sicramali_varis(), 300)

        self.assertTrue(atma_tikleri)
        araliklar = [b - a for a, b in zip(atma_tikleri, atma_tikleri[1:])]
        self.assertTrue(all(aralik >= buffer.catchup_interval for aralik in araliklar), araliklar)

    def test_esik_asilmadikca_cerceve_atilmaz(self):
        buffer = JitterBuffer()  # hedef 3 cerceve, pay 2 cerceve
        for sira in range(5):
            buffer.push(sira, bytes([sira]))

        cikan = [buffer.pop() for _ in range(5)]

        self.assertEqual(cikan, [bytes([s]) for s in range(5)])
        self.assertEqual((buffer.dropped, buffer.skipped), (0, 0))

    def test_yetisirken_bos_yuva_sessizlik_yerine_atlanir(self):
        buffer = JitterBuffer()
        for sira in (0, 1, 2):
            buffer.push(sira, bytes([sira]))
        cikan = [buffer.pop()]
        for sira in range(4, 10):  # 3 kayip
            buffer.push(sira, bytes([sira]))

        cikan += [buffer.pop(), buffer.pop()]

        # 1 gercek cerceve olarak atildi; 3 numarali bos yuva sessizlik calmadan atlandi.
        self.assertEqual(cikan, [bytes([0]), bytes([2]), bytes([4])])
        self.assertEqual((buffer.dropped, buffer.skipped, buffer.lost), (1, 1, 0))

    def test_bos_yuvalar_fazlayi_karsiliyorsa_gercek_cerceve_atilmaz(self):
        buffer = JitterBuffer()
        for sira in (0, 1, 2):
            buffer.push(sira, bytes([sira]))
        cikan = [buffer.pop()]
        buffer.push(9, bytes([9]))  # 3-8 kayip

        cikan += [buffer.pop() for _ in range(5)]

        self.assertEqual(buffer.dropped, 0)
        self.assertEqual([c for c in cikan if c is not None], [bytes([0]), bytes([1]), bytes([2]), bytes([9])])

    def test_derinlik_bosluklari_da_sayar(self):
        buffer = JitterBuffer()
        for sira in (0, 1, 2):
            buffer.push(sira, bytes([sira]))
        buffer.pop()
        buffer.push(9, bytes([9]))

        self.assertEqual(buffer.buffered_frames, 3)
        self.assertEqual(buffer.depth_frames, 9)

    def test_gecersiz_yetisme_ayarlari_reddedilir(self):
        with self.assertRaises(ValueError):
            JitterBuffer(catchup_interval=0)
        with self.assertRaises(ValueError):
            JitterBuffer(catchup_slack_ms=-1)
        JitterBuffer(catchup_interval=None)


class UctanUcaTests(unittest.TestCase):
    """Sentetik ses -> sifrele -> bozuk bir ag -> coz -> tampon -> cerceve."""

    def test_bozuk_agdan_gecen_konusma_dogru_sirada_cikar(self):
        gonderen = VoiceCipher("general", "gizli", 1)
        alici = VoiceCipher("general", "gizli", 2)
        tanistir(alici, gonderen)
        buffer = JitterBuffer(target_ms=60, frame_ms=20)

        cerceveler = [ses_cercevesi(i) for i in range(10)]
        datagramlar = [gonderen.seal(c, i, i * 20) for i, c in enumerate(cerceveler)]

        # Ag: 3. paketi dusur, 5 ile 6'nin sirasini boz, 7'yi iki kez teslim et.
        # Her 20 ms'de bir paket gelir, ses cihazi da her 20 ms'de bir ceker.
        yol = [0, 1, 2, 4, 6, 5, 7, 7, 8, 9]

        cikan = []
        for indeks in yol:
            try:
                header, audio = alici.open(datagramlar[indeks])
                buffer.push(header.sequence, audio)
            except ReplayError:
                pass  # kopya paket: sessizce atilir
            cikan.append(buffer.pop())
        cikan += [buffer.pop(), buffer.pop()]

        # Ilk iki cekiste tampon doluyor; 3. cerceve kayip, yerine sessizlik.
        beklenen = [None, None, *cerceveler[:3], None, *cerceveler[4:]]
        self.assertEqual(cikan, beklenen)
        self.assertEqual(buffer.lost, 1)
        self.assertEqual(buffer.late, 0)
        self.assertEqual(buffer.dropped, 0)

    def test_yanlis_parolali_katilimci_hicbir_cerceve_alamaz(self):
        gonderen = VoiceCipher("general", "gizli", 1)
        alici = VoiceCipher("general", "baska-parola", 2)
        tanistir(alici, gonderen)
        buffer = JitterBuffer(target_ms=60, frame_ms=20)

        for sira in range(5):
            with self.assertRaises(VoiceDecryptionError):
                alici.open(gonderen.seal(ses_cercevesi(sira), sira, sira * 20))

        self.assertIsNone(buffer.pop())


if __name__ == "__main__":
    unittest.main()
