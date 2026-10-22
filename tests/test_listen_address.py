"""Host modunda sunucunun dinleyecegi ag.

Eskiden sunucu hep 0.0.0.0'i, yani ayni Wi-Fi'deki yabancilarin da
ulasabildigi butun aglari dinliyordu (THREAT_MODEL 5.6). Artik ag her
seferinde elle secilir; varsayilan yoktur ve secim saklanmaz.
"""

import os
import socket
import tempfile
import unittest
from unittest import mock

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from apps.proxychat.i18n import t
from apps.proxychat.settings import ChatSettings
from apps.proxychat.ui import ConnectionController, ConnectPage, describe_listen_address, describe_socket_error
from core.utils import DEFAULT_HOST, get_local_ipv4_addresses
from tests.test_client_lifecycle import bos_port

HAMACHI = "25.12.34.56"
YEREL = "192.168.1.50"


class _SayfaTesti(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.adresler = [HAMACHI, YEREL]
        yama = mock.patch(
            "apps.proxychat.ui.get_local_ipv4_addresses", side_effect=lambda: list(self.adresler)
        )
        yama.start()
        self.addCleanup(yama.stop)
        handle, self.ini = tempfile.mkstemp(suffix=".ini")
        os.close(handle)
        self.addCleanup(lambda: os.path.exists(self.ini) and os.remove(self.ini))

    def _page(self):
        page = ConnectPage(ChatSettings(QSettings(self.ini, QSettings.Format.IniFormat)))
        self.addCleanup(page.deleteLater)
        return page

    def _host_page(self):
        page = self._page()
        page.mode_box.setCurrentText("Host")
        page.username_edit.setText("ayse")
        self.yakalanan = []
        page.connect_requested.connect(lambda *args: self.yakalanan.append(args))
        return page

    def _sec(self, page, ip):
        index = page.listen_box.findData(ip)
        self.assertGreaterEqual(index, 0, f"{ip} listede yok")
        page.listen_box.setCurrentIndex(index)


class ListenAddressListTests(_SayfaTesti):
    def test_list_is_only_shown_in_host_mode(self):
        page = self._page()

        for mode, gorunur in (("Host", True), ("Join", False), ("Demo", False)):
            page.mode_box.setCurrentText(mode)
            self.assertEqual(not page.listen_box.isHidden(), gorunur, mode)

    def test_list_offers_every_local_address_and_all_networks(self):
        page = self._host_page()

        veriler = [page.listen_box.itemData(i) for i in range(page.listen_box.count())]

        self.assertEqual(veriler, [HAMACHI, YEREL, DEFAULT_HOST])

    def test_hamachi_and_all_networks_are_labelled(self):
        # Adres varsayilan olarak maskeli (test_adres_gizleme); tur her zaman yazar.
        self.assertIn("Hamachi", describe_listen_address(HAMACHI))
        self.assertNotIn(HAMACHI, describe_listen_address(HAMACHI))
        self.assertEqual(describe_listen_address(YEREL, revealed=True), f"{YEREL} — {t('connect.network_local')}")
        self.assertEqual(describe_listen_address(DEFAULT_HOST), t("connect.listen_all"))

    def test_list_is_refreshed_when_entering_host_mode(self):
        # Hamachi uygulama acildiktan sonra baglanmis olabilir.
        self.adresler = [YEREL]
        page = self._host_page()
        self.assertEqual(page.listen_box.findData(HAMACHI), -1)
        page.mode_box.setCurrentText("Join")

        self.adresler = [HAMACHI, YEREL]
        page.mode_box.setCurrentText("Host")

        self.assertGreaterEqual(page.listen_box.findData(HAMACHI), 0, "liste yenilenmedi")

    def test_refresh_keeps_a_selection_that_still_exists(self):
        page = self._host_page()
        self._sec(page, YEREL)

        page.refresh_listen_addresses()

        self.assertEqual(page.listen_box.currentData(), YEREL)

    def test_refresh_drops_a_selection_that_disappeared(self):
        page = self._host_page()
        self._sec(page, HAMACHI)

        self.adresler = [YEREL]
        page.refresh_listen_addresses()

        self.assertIsNone(page.listen_box.currentData(), "artik olmayan adres secili kaldi")


class ListenAddressChoiceTests(_SayfaTesti):
    def test_nothing_is_selected_by_default(self):
        page = self._host_page()

        self.assertEqual(page.listen_box.currentIndex(), -1)

    def test_host_does_not_start_without_a_choice(self):
        page = self._host_page()

        page._emit_connect()

        self.assertEqual(self.yakalanan, [])
        self.assertEqual(page.status_label.text(), t("connect.error_choose_network"))

    def test_the_chosen_address_is_what_the_server_gets(self):
        page = self._host_page()
        self._sec(page, HAMACHI)

        page._emit_connect()

        self.assertEqual(self.yakalanan[0][:2], ("Host", HAMACHI))

    def test_the_choice_is_not_remembered(self):
        page = self._host_page()
        self._sec(page, HAMACHI)
        page.save_settings()

        yeni = self._page()

        self.assertEqual(yeni.mode_box.currentText(), "Host", "mod saklanmadi, test bos gecerdi")
        self.assertEqual(yeni.listen_box.currentIndex(), -1, "ag secimi hatirlandi")


class ServerBindTests(unittest.TestCase):
    def _controller(self):
        controller = ConnectionController()
        # Demo botlari ayri thread'de gecikmeli baglaniyor; sunucu kapandiktan
        # sonra baglanmaya calisip gurultu cikarmasinlar.
        controller._launch_demo_clients = lambda *args: None
        self.addCleanup(controller.disconnect)
        self.baglandi = []
        self.hatalar = []
        controller.connected.connect(self.baglandi.append)
        controller.connection_failed.connect(self.hatalar.append)
        return controller

    def test_host_listens_only_on_the_chosen_address(self):
        adresler = get_local_ipv4_addresses()
        if not adresler:
            self.skipTest("bu makinede loopback disinda IPv4 adresi yok")
        ip = adresler[0]
        port = bos_port()
        controller = self._controller()

        controller._connect_worker("Host", ip, port, "general", "ayse", "")

        self.assertEqual(self.hatalar, [])
        self.assertEqual(len(self.baglandi), 1, "Host kendi sunucusuna baglanamadi")
        self.assertEqual(self.baglandi[0]["share_ips"], [ip])
        with self.assertRaises(OSError, msg="sunucu secilmeyen 127.0.0.1'i de dinliyor"):
            socket.create_connection(("127.0.0.1", port), timeout=1.0).close()

    def test_all_networks_is_still_available_as_an_explicit_choice(self):
        port = bos_port()
        controller = self._controller()

        controller._connect_worker("Host", DEFAULT_HOST, port, "general", "ayse", "")

        self.assertEqual(self.hatalar, [])
        self.assertEqual(controller._server.host, DEFAULT_HOST)

    def test_demo_listens_only_on_this_computer(self):
        port = bos_port()
        controller = self._controller()

        controller._connect_worker("Demo", "127.0.0.1", port, "general", "ayse", "")

        self.assertEqual(self.hatalar, [])
        self.assertEqual(controller._server.host, "127.0.0.1")


class AddressErrorMessageTests(unittest.TestCase):
    def test_missing_address_gets_a_readable_message(self):
        message = describe_socket_error(OSError(10049, "istenen adres gecerli degil"))

        self.assertEqual(message, t("socket_error.10049"))
        self.assertIn("10049", message)
        self.assertIn("Hamachi", message)


if __name__ == "__main__":
    unittest.main()
