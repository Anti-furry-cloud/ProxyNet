"""Seste ileri gizlilik: ses anahtari paroladan degil, oturumdan.

Metin tarafinda 1.9.0'da yapilanin ayni fikri ses icin. Ag ve ses karti yok;
iki sifreleyici birbirine elle paket veriyor.
"""

import unittest

from core.key_agreement import new_sender_key
from core.room_session import RoomSession
from core.voice_crypto import (
    VOICE_ENCRYPTION_SCHEME,
    VOICE_FORWARD_SECRET_SCHEME,
    ForwardSecretVoiceCipher,
    SenderKeyMissingError,
    SESSION_SALT_BYTES,
    VoiceDecryptionError,
    derive_session_key,
    derive_voice_key,
    derive_voice_session_key,
)

ODA = "kule"
PAROLA = "dogru-at-pil-zimba"
CERCEVE = b"ses cercevesi" * 4


def ikili() -> tuple[ForwardSecretVoiceCipher, ForwardSecretVoiceCipher, bytes, bytes]:
    """El sikismis iki ses oturumu."""
    ayse_anahtar, veli_anahtar = new_sender_key(), new_sender_key()
    ayse = ForwardSecretVoiceCipher(ayse_anahtar, 1)
    veli = ForwardSecretVoiceCipher(veli_anahtar, 2)
    ayse.add_sender(2, veli.session_salt, veli_anahtar)
    veli.add_sender(1, ayse.session_salt, ayse_anahtar)
    return ayse, veli, ayse_anahtar, veli_anahtar


class TuretmeTests(unittest.TestCase):
    def test_ayni_malzemeden_metin_ve_ses_ayri_anahtar(self):
        """HKDF'nin info alani ayri: ayni anahtardan ikisi ayni cikmamali."""
        anahtar = new_sender_key()
        tuz = b"t" * SESSION_SALT_BYTES

        ses = derive_voice_session_key(anahtar, tuz, 1)

        self.assertNotEqual(ses, anahtar)
        self.assertEqual(len(ses), 32)

    def test_paroladan_turetilen_anahtardan_farkli(self):
        """Eski sema ile yeni sema ayni tuz ve kimlikte bile ayni anahtari vermemeli."""
        tuz = b"t" * SESSION_SALT_BYTES
        eski = derive_session_key(derive_voice_key(ODA, PAROLA), tuz, 1)

        yeni = derive_voice_session_key(new_sender_key(), tuz, 1)

        self.assertNotEqual(eski, yeni)

    def test_gonderen_kimligi_anahtari_degistiriyor(self):
        anahtar, tuz = new_sender_key(), b"t" * SESSION_SALT_BYTES

        self.assertNotEqual(
            derive_voice_session_key(anahtar, tuz, 1),
            derive_voice_session_key(anahtar, tuz, 2),
        )

    def test_tuz_anahtari_degistiriyor(self):
        anahtar = new_sender_key()

        self.assertNotEqual(
            derive_voice_session_key(anahtar, b"a" * SESSION_SALT_BYTES, 1),
            derive_voice_session_key(anahtar, b"b" * SESSION_SALT_BYTES, 1),
        )

    def test_yanlis_boyda_anahtar_reddediliyor(self):
        with self.assertRaises(ValueError):
            derive_voice_session_key(b"kisa", b"t" * SESSION_SALT_BYTES, 1)


class AkisTests(unittest.TestCase):
    def test_ses_karsi_tarafta_cozuluyor(self):
        ayse, veli, _, _ = ikili()

        paket = ayse.seal(CERCEVE, 1, 100)

        _, govde = veli.open(paket)
        self.assertEqual(govde, CERCEVE)

    def test_kendi_paketimizi_cozebiliyoruz(self):
        """Aktarma dongusuyle geri donen kendi paketimiz."""
        ayse, _, _, _ = ikili()

        paket = ayse.seal(CERCEVE, 1, 100)

        self.assertEqual(ayse.open(paket)[1], CERCEVE)

    def test_yanlis_anahtarla_cozulmuyor(self):
        ayse, _, _, _ = ikili()
        yabanci = ForwardSecretVoiceCipher(new_sender_key(), 2)
        yabanci.add_sender(1, ayse.session_salt, new_sender_key())  # yanlis anahtar

        paket = ayse.seal(CERCEVE, 1, 100)

        with self.assertRaises(VoiceDecryptionError):
            yabanci.open(paket)

    def test_sema_etiketi_eskisinden_farkli(self):
        """Iki sema birbirine sessizlik uretmesin diye ayri etiket."""
        self.assertEqual(ForwardSecretVoiceCipher(new_sender_key(), 1).scheme, VOICE_FORWARD_SECRET_SCHEME)
        self.assertNotEqual(VOICE_FORWARD_SECRET_SCHEME, VOICE_ENCRYPTION_SCHEME)

    def test_anahtari_olmayan_gonderen_reddediliyor(self):
        """Metin el sikismasi bitmeden ses anahtari turetilemez."""
        ayse = ForwardSecretVoiceCipher(new_sender_key(), 1)

        with self.assertRaises(SenderKeyMissingError):
            ayse.add_sender(2, b"t" * SESSION_SALT_BYTES)

    def test_cikan_gonderenin_anahtari_birakiliyor(self):
        ayse, veli, _, veli_anahtar = ikili()

        ayse.forget(2)

        with self.assertRaises(SenderKeyMissingError):
            ayse.add_sender(2, veli.session_salt)

    def test_yeni_tuz_yeni_oturum(self):
        """Ayni gonderen yeni tuzla gelirse eski anahtar atilir."""
        ayse, veli, _, veli_anahtar = ikili()
        eski_paket = veli.seal(CERCEVE, 1, 100)
        self.assertEqual(ayse.open(eski_paket)[1], CERCEVE)

        yeni_veli = ForwardSecretVoiceCipher(veli_anahtar, 2)
        ayse.add_sender(2, yeni_veli.session_salt, veli_anahtar)

        with self.assertRaises(VoiceDecryptionError):
            ayse.open(eski_paket)


class IleriGizlilikTests(unittest.TestCase):
    """Varlik sebebi: parola artik ses anahtarinin kokunde degil."""

    def test_parola_ses_anahtarini_vermiyor(self):
        """T5 senaryosu: kayit ve parola rakibin elinde, ses yine kapali.

        Rakip oturum tuzunu da kaydetmistir (voice_peers duz metin gidiyor) ve
        parolayi da biliyor. Eskiden bu ikisi yetiyordu; artik yetmiyor, cunku
        anahtarin kokunde parola yok.
        """
        ayse, _, ayse_anahtar, _ = ikili()
        kayit = ayse.seal(CERCEVE, 1, 100)
        tuz = ayse.session_salt

        # Rakibin paroladan turetebilecegi her sey:
        paroladan = derive_session_key(derive_voice_key(ODA, PAROLA), tuz, 1)
        gercek = derive_voice_session_key(ayse_anahtar, tuz, 1)

        self.assertNotEqual(paroladan, gercek)
        rakip = ForwardSecretVoiceCipher(new_sender_key(), 2)
        rakip.add_sender(1, tuz, paroladan)  # paroladan turetileni anahtar diye dener
        with self.assertRaises(VoiceDecryptionError):
            rakip.open(kayit)

    def test_yeni_oturum_eski_sesi_acamiyor(self):
        """Ayni parolayla acilan yeni oturum eskisini cozememeli."""
        ayse, _, _, _ = ikili()
        kayit = ayse.seal(CERCEVE, 1, 100)

        # Oturum bitti; yeni oturum yeni bir gonderen anahtariyla aciliyor.
        yeni_ayse = ForwardSecretVoiceCipher(new_sender_key(), 1)
        dinleyici = ForwardSecretVoiceCipher(new_sender_key(), 2)
        dinleyici.add_sender(1, ayse.session_salt, yeni_ayse._own_key)

        with self.assertRaises(VoiceDecryptionError):
            dinleyici.open(kayit)

    def test_oda_oturumunun_anahtariyla_calisiyor(self):
        """Malzeme uydurma degil: metin tarafindaki gercek gonderen anahtari."""
        ayse_oturum = RoomSession(ODA, PAROLA)
        veli_oturum = RoomSession(ODA, PAROLA)
        ayse_acik, ayse_etiket = ayse_oturum.offer()
        veli_acik, veli_etiket = veli_oturum.offer()
        veli_oturum.accept_offer(ayse_acik, ayse_etiket)
        ayse_oturum.accept_offer(veli_acik, veli_etiket)

        ayse_ses = ForwardSecretVoiceCipher(ayse_oturum.own_sender_key(), 1)
        veli_ses = ForwardSecretVoiceCipher(veli_oturum.own_sender_key(), 2)
        veli_ses.add_sender(1, ayse_ses.session_salt, ayse_oturum.own_sender_key())

        self.assertEqual(veli_ses.open(ayse_ses.seal(CERCEVE, 1, 100))[1], CERCEVE)


if __name__ == "__main__":
    unittest.main()


def el_sik(birinci: RoomSession, ikinci: RoomSession) -> None:
    """Iki oda oturumunu karsilikli anahtarlandirir (agda olacak sirayla)."""
    ilk_acik, ilk_etiket = birinci.offer()
    ikinci_acik, ikinci_etiket = ikinci.offer()
    ikinciden = ikinci.accept_offer(ilk_acik, ilk_etiket)
    birinciden = birinci.accept_offer(ikinci_acik, ikinci_etiket)
    birinci.accept_sender_key(ikinci_acik, ikinciden)
    ikinci.accept_sender_key(ilk_acik, birinciden)


class SahteIstemci:
    def __init__(self):
        self.gonderilen = []

    def send_packet(self, packet):
        self.gonderilen.append(packet)


class SahteBaglanti:
    """ConnectionController yerine: sesin ihtiyaci olan alanlar + oda oturumu."""

    def __init__(self, room_session: RoomSession | None):
        self.client = SahteIstemci()
        self.room = "kule"
        self.room_password = PAROLA
        self.host = "127.0.0.1"
        self.port = 5555
        self.room_session = room_session


class UrunYoluTests(unittest.TestCase):
    """Kontrolcu gercekten ileri gizli sifreleyiciyi kuruyor mu?

    Ses karti yok: kontrolcuye sahte cihaz veriliyor.
    """

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def kontrolcu(self, oturum):
        from apps.proxychat.voice import VoiceController

        from tests.test_voice_ui import SahteSesCihazi

        baglanti = SahteBaglanti(oturum)
        k = VoiceController(baglanti, audio_factory=lambda s, f: SahteSesCihazi(s, f))
        self.addCleanup(k.leave)
        return k, baglanti

    def katil(self, k, sender_id=1):
        k.join()
        k.on_packet(
            {"type": "voice_joined", "sender_id": sender_id, "token": "ab" * 16, "port": 5555}
        )

    def test_voice_join_acik_anahtari_tasiyor(self):
        oturum = RoomSession(ODA, PAROLA)
        k, baglanti = self.kontrolcu(oturum)

        k.join()

        [paket] = [p for p in baglanti.client.gonderilen if p["type"] == "voice_join"]
        import base64

        self.assertEqual(base64.urlsafe_b64decode(paket["pub"]), oturum.public_key)

    def test_sifreleyici_ileri_gizli_surum(self):
        oturum = RoomSession(ODA, PAROLA)
        k, _ = self.kontrolcu(oturum)

        self.katil(k)

        self.assertIsInstance(k.session.cipher, ForwardSecretVoiceCipher)
        self.assertEqual(k.session.cipher.scheme, VOICE_FORWARD_SECRET_SCHEME)

    def test_esin_anahtari_acik_anahtarla_bulunuyor(self):
        import base64

        ayse = RoomSession(ODA, PAROLA)
        veli = RoomSession(ODA, PAROLA)
        veli_acik, _ = veli.offer()
        el_sik(ayse, veli)
        k, _ = self.kontrolcu(ayse)
        self.katil(k, sender_id=1)

        k.on_packet(
            {
                "type": "voice_peers",
                "peers": [
                    {"user": "ayse", "sender_id": 1, "salt": "ab" * 16, "pub": ""},
                    {
                        "user": "veli",
                        "sender_id": 2,
                        "salt": "cd" * 16,
                        "pub": base64.urlsafe_b64encode(veli_acik).decode("ascii"),
                    },
                ],
            }
        )

        self.assertIn(2, k.session.peers())

    def test_anahtari_gelmemis_es_atlaniyor_sonra_ekleniyor(self):
        """Metin el sikismasi ses katiliminden sonra bitebilir."""
        import base64

        ayse = RoomSession(ODA, PAROLA)
        veli = RoomSession(ODA, PAROLA)
        veli_acik, _ = veli.offer()
        k, _ = self.kontrolcu(ayse)
        self.katil(k, sender_id=1)
        peers = {
            "type": "voice_peers",
            "peers": [
                {
                    "user": "veli",
                    "sender_id": 2,
                    "salt": "cd" * 16,
                    "pub": base64.urlsafe_b64encode(veli_acik).decode("ascii"),
                }
            ],
        }

        k.on_packet(peers)
        self.assertNotIn(2, k.session.peers(), "anahtarsiz es eklendi")

        # Metin el sikismasi simdi tamamlaniyor.
        el_sik(ayse, veli)
        k.on_packet({"type": "peers_verified", "room": ODA, "users": ["veli"]})

        self.assertIn(2, k.session.peers(), "anahtar gelince es eklenmedi")
