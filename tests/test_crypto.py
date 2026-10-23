import secrets
import threading
import unittest

from core.client import ChatClient
from core.crypto import (
    DECRYPT_REASON_PASSWORD,
    DECRYPT_REASON_SCHEME,
    UNDECRYPTABLE_PLACEHOLDER,
    NullCipher,
    decrypt_packet_content,
    derive_master_key,
)
from core.room_session import SCHEME, RoomSession
from core.server import ChatServer
from core.voice_crypto import (
    SESSION_SALT_BYTES,
    derive_session_key,
    derive_voice_key,
)


class RoomKeyDerivationTests(unittest.TestCase):
    """Paroladan turetilen ana anahtar. Artik mesaj sifrelemiyor (bu anahtar
    imzanin ve prototipin ses anahtarinin kaynagi) ama ozellikleri ayni
    kalmali: iki taraf ayni parolayla ayni degeri bulmali."""

    def test_same_room_and_password_produce_the_same_key(self):
        self.assertEqual(derive_master_key("general", "gizli"), derive_master_key("general", "gizli"))

    def test_room_name_is_part_of_the_salt(self):
        self.assertNotEqual(derive_master_key("general", "gizli"), derive_master_key("random", "gizli"))

    def test_room_name_matching_ignores_case_and_padding(self):
        self.assertEqual(derive_master_key("General", "gizli"), derive_master_key("  general  ", "gizli"))

    def test_different_passwords_produce_different_keys(self):
        self.assertNotEqual(derive_master_key("general", "gizli"), derive_master_key("general", "gizli2"))


class Argon2idTests(unittest.TestCase):
    """THREAT_MODEL.md 5.8: anahtar 1.7.0'dan beri Argon2id ile turuyor."""

    def test_bilinen_cevap_vektoru(self):
        """Parametre, tuz ya da oda adi normallestirmesi sessizce degismesin.

        Bu deger degisirse ayni oda + parola baska bir anahtar verir ve
        farkli surumler birbirinin imzasini dogrulayamaz. Bilerek
        degistirildiyse sema etiketi de degismeli.
        """
        self.assertEqual(
            derive_master_key("general", "gizli").hex(),
            "6bb7285396214b5303f3c465521abf2ddcc767b2e33b0237bebce3814cf66b09",
        )

    def test_rfc_9106_ikinci_secenek(self):
        from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

        from core import crypto

        self.assertEqual(
            (crypto.ARGON2_ITERATIONS, crypto.ARGON2_LANES, crypto.ARGON2_MEMORY_KIB),
            (3, 4, 64 * 1024),
        )
        elle = Argon2id(
            salt=b"proxynet:argon2id:room:general", length=32,
            iterations=3, lanes=4, memory_cost=64 * 1024,
        ).derive(b"gizli")
        self.assertEqual(derive_master_key("General ", "gizli"), elle)

    def test_eski_pbkdf2_anahtari_uretilmez(self):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        eski = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32,
            salt=b"proxynet:room:general", iterations=240_000,
        ).derive(b"gizli")
        self.assertNotEqual(derive_master_key("general", "gizli"), eski)

    def test_sema_etiketi_guncel(self):
        """Fernet semasi 1.9.0'da birakildi; etiket onu yansitmali.

        v1 -> v2 (1.12.0): yuk dolgulanmaya baslandi. Tel bicimi degistigi
        icin etiket de degisti; dolgu anlayan bir istemcinin dolgu
        anlamayan biriyle konusmasi dolguyu anlamsiz kilardi, o yuzden
        pazarlik degil temiz kirilma (core/padding.py).

        v2 -> v3 (1.13.0): ikili anahtara paroladan tureyen on paylasimli
        anahtar girdi (kuantuma karsi ilk adim, THREAT_MODEL 5.10). Tel bicimi
        ayni ama anahtarlar farkli; eski istemciyle "farkli surum" gorulsun.
        """
        self.assertEqual(SCHEME, "aesgcm-x25519-v3")


class ClientKeyCacheTests(unittest.TestCase):
    """Argon2id bilerek yavas: ayni oda icin anahtar bir kez turetilmeli.

    Host modu baglanirken sunucu ayaga kalkana kadar 20 kez deniyor, oda
    degistirme ise arayuz thread'inden cagriliyor.
    """

    def setUp(self):
        from unittest import mock

        import core.client

        self.sayac = []
        gercek = core.client.RoomSession

        def sayan(room, password, **k):
            self.sayac.append(room)
            return gercek(room, password, **k)

        yama = mock.patch.object(core.client, "RoomSession", sayan)
        yama.start()
        self.addCleanup(yama.stop)

    def test_istemci_olusturulurken_anahtar_turetilmez(self):
        client = ChatClient(room_password="gizli")

        self.assertEqual(self.sayac, [])
        self.assertTrue(client.encrypted)

    def test_ayni_oda_icin_bir_kez_turetilir(self):
        client = ChatClient(room_password="gizli")

        birinci = client._cipher_for("general")
        ikinci = client._cipher_for("  General ")
        client._cipher_for("oyun")

        self.assertIs(birinci, ikinci)
        self.assertEqual(len(self.sayac), 2)

    def test_parolasiz_istemci_sifreli_degil(self):
        self.assertFalse(ChatClient().encrypted)


class NullCipherTests(unittest.TestCase):
    """Parolasiz oda. Sifreleyen yol `tests/test_room_session.py`'de."""

    def test_null_cipher_passes_text_through(self):
        cipher = NullCipher()

        self.assertEqual(cipher.decrypt(cipher.encrypt("merhaba")), "merhaba")
        self.assertIsNone(cipher.scheme)
        self.assertFalse(cipher.enabled)


class PacketDecryptionTests(unittest.TestCase):
    def test_plaintext_packet_is_left_untouched(self):
        packet = {"type": "message", "content": "merhaba"}

        self.assertEqual(decrypt_packet_content(packet, RoomSession("general", "gizli"))["content"], "merhaba")

    def test_encrypted_packet_is_decrypted(self):
        cipher = RoomSession("general", "gizli")
        packet = {"type": "message", "content": cipher.encrypt("merhaba"), "enc": SCHEME}

        self.assertEqual(decrypt_packet_content(packet, cipher)["content"], "merhaba")

    def test_wrong_password_yields_a_placeholder_instead_of_raising(self):
        packet = {
            "type": "message",
            "content": RoomSession("general", "gizli").encrypt("merhaba"),
            "enc": SCHEME,
        }

        result = decrypt_packet_content(packet, RoomSession("general", "yanlis"))

        self.assertEqual(result["content"], UNDECRYPTABLE_PLACEHOLDER)
        self.assertTrue(result["decrypt_failed"])

    def test_client_without_password_marks_encrypted_message_as_unreadable(self):
        packet = {
            "type": "message",
            "content": RoomSession("general", "gizli").encrypt("merhaba"),
            "enc": SCHEME,
        }

        result = decrypt_packet_content(packet, NullCipher())

        self.assertEqual(result["content"], UNDECRYPTABLE_PLACEHOLDER)
        self.assertTrue(result["decrypt_failed"])
        self.assertEqual(result["decrypt_reason"], DECRYPT_REASON_PASSWORD)

    def test_wrong_password_reason_is_password(self):
        packet = {
            "type": "message",
            "content": RoomSession("general", "gizli").encrypt("merhaba"),
            "enc": SCHEME,
        }

        result = decrypt_packet_content(packet, RoomSession("general", "yanlis"))

        self.assertEqual(result["decrypt_reason"], DECRYPT_REASON_PASSWORD)

    def test_older_version_packet_is_reported_as_a_version_mismatch(self):
        """1.6.x ayni parolayla yollasa da cozulemez; sebep parola degil surum."""
        packet = {"type": "message", "content": "gAAAAAeskitoken", "enc": "fernet-pbkdf2-v1"}

        result = decrypt_packet_content(packet, RoomSession("general", "gizli"))

        self.assertTrue(result["decrypt_failed"])
        self.assertEqual(result["decrypt_reason"], DECRYPT_REASON_SCHEME)
        self.assertEqual(result["content"], UNDECRYPTABLE_PLACEHOLDER)


class EncryptedChatIntegrationTests(unittest.TestCase):
    def _wait_for_join(self, port, *clients_and_events):
        for client, event in clients_and_events:
            self.assertTrue(event.wait(5), "istemci odaya katilamadi")

    def test_matching_passwords_exchange_readable_messages(self):
        port = 8791
        server = ChatServer(port=port)
        server.start()

        joined = threading.Event()
        received = threading.Event()
        seen: list[dict] = []

        def capture_b(packet):
            if packet.get("type") == "joined":
                joined.set()
            if packet.get("type") == "message":
                seen.append(packet)
                received.set()

        client_a = ChatClient(room_password="gizli")
        client_b = ChatClient(on_packet=capture_b, room_password="gizli")

        try:
            client_a.connect("127.0.0.1", port, "general", "ayse")
            client_b.connect("127.0.0.1", port, "general", "mehmet")
            self.assertTrue(joined.wait(5), "ikinci istemci odaya katilamadi")
            self.assertTrue(client_a.encrypted)

            client_a.send_message("gizli mesaj")

            self.assertTrue(received.wait(5), "mesaj karsi tarafa ulasmadi")
            self.assertEqual(seen[0]["content"], "gizli mesaj")
        finally:
            client_a.disconnect()
            client_b.disconnect()
            server.stop()

    def test_server_only_ever_holds_ciphertext(self):
        port = 8792
        server = ChatServer(port=port, keep_history=True)
        server.start()

        joined = threading.Event()
        received = threading.Event()
        # Sunucunun kurdugu yayin paketini yakala: gecmis artik sifreli mesaji
        # saklamadigi icin "sunucunun elindeki" sey budur.
        yayinlar: list[dict] = []
        gercek_kur = server.hub.build_message_packet

        def kuran(*a, **k):
            paket = gercek_kur(*a, **k)
            yayinlar.append(paket)
            return paket

        server.hub.build_message_packet = kuran

        def capture_b(packet):
            if packet.get("type") == "joined":
                joined.set()
            if packet.get("type") == "message":
                received.set()

        client_a = ChatClient(room_password="gizli")
        client_b = ChatClient(on_packet=capture_b, room_password="gizli")

        try:
            client_a.connect("127.0.0.1", port, "general", "ayse")
            client_b.connect("127.0.0.1", port, "general", "mehmet")
            self.assertTrue(joined.wait(5), "ikinci istemci odaya katilamadi")

            client_a.send_message("gizli mesaj")
            self.assertTrue(received.wait(5), "mesaj karsi tarafa ulasmadi")

            self.assertEqual(len(yayinlar), 1)
            self.assertNotIn("gizli mesaj", yayinlar[0]["content"])
            self.assertEqual(yayinlar[0]["enc"], SCHEME)
            # Ve sifreli mesaj diske/bellege yazilmadi.
            self.assertEqual(server._history.get("general", []), [])
        finally:
            client_a.disconnect()
            client_b.disconnect()
            server.stop()

    def test_wrong_password_sees_placeholder_not_plaintext(self):
        port = 8793
        server = ChatServer(port=port)
        server.start()

        joined = threading.Event()
        received = threading.Event()
        seen: list[dict] = []

        def capture_b(packet):
            if packet.get("type") == "joined":
                joined.set()
            if packet.get("type") == "message":
                seen.append(packet)
                received.set()

        client_a = ChatClient(room_password="gizli")
        client_b = ChatClient(on_packet=capture_b, room_password="baska-parola")

        try:
            client_a.connect("127.0.0.1", port, "general", "ayse")
            client_b.connect("127.0.0.1", port, "general", "mehmet")
            self.assertTrue(joined.wait(5), "ikinci istemci odaya katilamadi")

            client_a.send_message("gizli mesaj")

            self.assertTrue(received.wait(5), "mesaj karsi tarafa ulasmadi")
            self.assertEqual(seen[0]["content"], UNDECRYPTABLE_PLACEHOLDER)
            self.assertTrue(seen[0]["decrypt_failed"])
        finally:
            client_a.disconnect()
            client_b.disconnect()
            server.stop()

    def test_encrypted_rooms_keep_no_history(self):
        port = 8794
        server = ChatServer(port=port, keep_history=True)
        server.start()

        first_joined = threading.Event()
        delivered = threading.Event()
        history_seen = threading.Event()
        histories: list[dict] = []

        def capture_a(packet):
            if packet.get("type") == "joined":
                first_joined.set()
            if packet.get("type") == "message":
                delivered.set()

        def capture_c(packet):
            if packet.get("type") == "history":
                histories.append(packet)
                history_seen.set()

        client_a = ChatClient(on_packet=capture_a, room_password="gizli")
        client_c = ChatClient(on_packet=capture_c, room_password="gizli")

        try:
            client_a.connect("127.0.0.1", port, "general", "ayse")
            self.assertTrue(first_joined.wait(5), "ilk istemci odaya katilamadi")
            client_a.send_message("eski mesaj")
            self.assertTrue(delivered.wait(5), "mesaj sunucuya ulasmadi")

            client_c.connect("127.0.0.1", port, "general", "eda")

            # Gecmis paketi yine geliyor (host gecmisi acik birakti) ama
            # sifreli mesaj icinde YOK: ileri gizlilikte sonradan gelen onu
            # zaten cozemez, saklamak ise 5.2'nin acigini ayakta tutardi.
            self.assertTrue(history_seen.wait(5), "gecmis paketi gelmedi")
            self.assertEqual(histories[0]["messages"], [])
            self.assertEqual(server._history.get("general", []), [])
        finally:
            client_a.disconnect()
            client_c.disconnect()
            server.stop()

    def test_passwordless_rooms_still_work_unchanged(self):
        port = 8795
        server = ChatServer(port=port)
        server.start()

        joined = threading.Event()
        received = threading.Event()
        seen: list[dict] = []

        def capture_b(packet):
            if packet.get("type") == "joined":
                joined.set()
            if packet.get("type") == "message":
                seen.append(packet)
                received.set()

        client_a = ChatClient()
        client_b = ChatClient(on_packet=capture_b)

        try:
            client_a.connect("127.0.0.1", port, "general", "ayse")
            client_b.connect("127.0.0.1", port, "general", "mehmet")
            self.assertTrue(joined.wait(5), "ikinci istemci odaya katilamadi")
            self.assertFalse(client_a.encrypted)

            client_a.send_message("acik mesaj")

            self.assertTrue(received.wait(5), "mesaj karsi tarafa ulasmadi")
            self.assertEqual(seen[0]["content"], "acik mesaj")
            self.assertNotIn("enc", seen[0])
        finally:
            client_a.disconnect()
            client_b.disconnect()
            server.stop()


class ConnectPageWiringTests(unittest.TestCase):
    """Parola alaninin sinyal zinciri: arity hatalari ancak calisma aninda patlar."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def test_password_reaches_the_controller(self):
        from apps.proxychat.ui import ProxyChatWindow
        from tests.test_proxychat_ui import izole_ayarlar

        window = ProxyChatWindow(izole_ayarlar(self))
        captured: list[tuple] = []
        window.controller.connect_async = lambda *args: captured.append(args)

        page = window.connect_page
        page.mode_box.setCurrentText("Host")
        page.listen_box.setCurrentIndex(page.listen_box.findData("0.0.0.0"))
        page.username_edit.setText("ayse")
        page.room_edit.setText("general")
        page.port_edit.setText("8799")
        page.password_edit.setText("gizli")
        page._emit_connect()

        self.assertEqual(captured, [("Host", "0.0.0.0", 8799, "general", "ayse", "gizli")])
        window.close()

    def test_empty_password_is_passed_through_as_empty_string(self):
        from apps.proxychat.ui import ProxyChatWindow
        from tests.test_proxychat_ui import izole_ayarlar

        window = ProxyChatWindow(izole_ayarlar(self))
        captured: list[tuple] = []
        window.controller.connect_async = lambda *args: captured.append(args)

        page = window.connect_page
        page.mode_box.setCurrentText("Host")
        page.listen_box.setCurrentIndex(page.listen_box.findData("0.0.0.0"))
        page.port_edit.setText("8798")
        page._emit_connect()

        self.assertEqual(captured[0][-1], "")
        window.close()


class ForwardSecrecyTests(unittest.TestCase):
    """THREAT_MODEL.md 5.1'in durumu, calistirilabilir halde.

    Metin sohbetinde acik **kapandi** (1.9.0): anahtar artik paroladan degil,
    oturum basina uretilen gecici X25519 anahtarlarindan doguyor
    (`core/key_agreement.py`, `core/room_session.py`). Parola yalnizca karsi
    tarafi dogruluyor. Protokol tarafinin testleri
    `tests/test_forward_secrecy.py`'de.

    Seste de kapandi (1.10.0): ses oturum anahtari da oda oturumunun gonderen
    anahtarindan turuyor. Metin tarafinda yapilan is bunun provasiydi; ikisi
    de ayni malzemeyi kullaniyor, yalnizca HKDF'nin ``info`` alani ayri.
    """

    ODA = "kule"
    PAROLA = "dogru-at-pil-zimba"

    def test_urunun_yolu_ileri_gizli(self):
        """Sifreli odada istemcinin kullandigi sey RoomSession olmali."""
        from core.room_session import RoomSession

        client = ChatClient(room_password=self.PAROLA)

        oturum = client._cipher_for(self.ODA)

        self.assertIsInstance(oturum, RoomSession)

    def test_iki_oturum_ayni_parolayla_bile_ayni_anahtari_kullanmiyor(self):
        """Acigin koku buydu: anahtarin parolanin fonksiyonu olmasi."""
        from core.room_session import RoomSession, UnknownSenderKey

        birinci = RoomSession(self.ODA, self.PAROLA)
        ikinci = RoomSession(self.ODA, self.PAROLA)

        token = birinci.encrypt("bulusma 21:00")

        with self.assertRaises(UnknownSenderKey):
            ikinci.decrypt(token)

    def test_ses_de_ileri_gizli(self):
        """Ses anahtari artik oda oturumundan turuyor, paroladan degil.

        Bu test uzun sure `expectedFailure` ile kirmizi durdu: ses tarafi
        metin tarafi duzeldikten sonra da paroladan turetiyordu. Oturum tuzu
        her oturumda yeniden uretiliyor ama `voice_peers` onu duz metin
        duyurdugu icin kaydi tutan rakip tuzu da elde ediyordu; parola
        sonradan sizsa ses aciliyordu.
        """
        from core.room_session import RoomSession
        from core.voice_crypto import SESSION_SALT_BYTES, derive_voice_session_key

        tuz = secrets.token_bytes(SESSION_SALT_BYTES)
        birinci = RoomSession(self.ODA, self.PAROLA)
        ikinci = RoomSession(self.ODA, self.PAROLA)

        # Ayni oda, ayni parola, iki ayri oturum: ses anahtarlari da ayri.
        self.assertNotEqual(
            derive_voice_session_key(birinci.own_sender_key(), tuz, 7),
            derive_voice_session_key(ikinci.own_sender_key(), tuz, 7),
        )

    def test_eski_ses_turetmesi_ileri_gizli_degil(self):
        """`derive_voice_key` neden artik urun yolunda degil.

        Paroladan turetilen ses anahtari deterministikti: parola + tuz
        elindeyse anahtar yeniden hesaplanabiliyordu. Fonksiyon eski paketleri
        anlamak icin kaynakta duruyor; bu test neden birakildiginin kaydi.
        """
        tuz = secrets.token_bytes(SESSION_SALT_BYTES)

        self.assertEqual(
            derive_session_key(derive_voice_key(self.ODA, self.PAROLA), tuz, 7),
            derive_session_key(derive_voice_key(self.ODA, self.PAROLA), tuz, 7),
        )


if __name__ == "__main__":
    unittest.main()
