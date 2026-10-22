"""Dinleme portunun sunucuya ayrilmasi ve baglanti ekraninda Enter.

Ikinci taramada (15 Eylul 2026) bulundu: Windows'ta SO_REUSEADDR yuzunden
ayni porta ikinci bir sunucu hatasiz aciliyor, baska bir surec de Host
0.0.0.0'i dinlerken 127.0.0.1:<port>'u dinleyip Host'un kendi baglantisini
uzerine alabiliyordu.
"""

import os
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from apps.proxychat.i18n import t
from apps.proxychat.settings import ChatSettings
from apps.proxychat.ui import ConnectionController, ConnectPage, describe_socket_error
from core.client import ChatClient
from core.server import ChatServer
from tests.test_client_lifecycle import bos_port


class PortReservationTests(unittest.TestCase):
    def _sunucu(self, host="0.0.0.0", port=None):
        server = ChatServer(host=host, port=port if port is not None else bos_port())
        server.start()
        self.addCleanup(server.stop)
        return server

    def test_second_server_on_the_same_port_is_refused(self):
        ilk = self._sunucu()

        with self.assertRaises(OSError):
            ChatServer(host="0.0.0.0", port=ilk.port).start()

    @unittest.skipUnless(sys.platform == "win32", "gasp yalnizca Windows'un SO_REUSEADDR davranisinda mumkun")
    def test_another_process_cannot_take_over_localhost_on_the_port(self):
        ilk = self._sunucu()
        saldirgan = textwrap.dedent(
            """
            import socket, sys
            s = socket.socket()
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", int(sys.argv[1])))
                s.listen(1)
                print("GASPETTI")
            except OSError:
                print("REDDEDILDI")
            """
        )
        handle, yol = tempfile.mkstemp(suffix=".py")
        os.close(handle)
        self.addCleanup(os.remove, yol)
        with open(yol, "w", encoding="utf-8") as dosya:
            dosya.write(saldirgan)

        sonuc = subprocess.run([sys.executable, yol, str(ilk.port)], capture_output=True, text=True, timeout=30)

        self.assertEqual(sonuc.stdout.strip(), "REDDEDILDI", sonuc.stderr)

    def test_port_can_be_reopened_right_after_stopping(self):
        # Host modunda yeniden baglanma sunucuyu kapatip ayni portta hemen acar.
        # Sunucu baglantilari kendisi kapattigi icin TIME_WAIT onda kalir.
        port = bos_port()
        ilk = ChatServer(host="0.0.0.0", port=port)
        ilk.start()
        istemci = ChatClient()
        istemci.connect("127.0.0.1", port, "general", "ayse")
        time.sleep(0.3)
        ilk.stop()
        istemci.disconnect()

        ikinci = self._sunucu(port=port)

        self.assertTrue(ikinci.running)
        yeni = ChatClient()
        self.addCleanup(yeni.disconnect)
        yeni.connect("127.0.0.1", port, "general", "ayse")
        self.assertTrue(yeni.connected)

    def test_port_taken_by_another_program_gets_a_readable_message(self):
        self.assertEqual(describe_socket_error(OSError(10013, "erisim")), t("socket_error.10013"))


class SecondHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_starting_a_second_host_on_the_same_port_reports_an_error(self):
        ilk = ChatServer(host="0.0.0.0", port=bos_port())
        ilk.start()
        self.addCleanup(ilk.stop)
        controller = ConnectionController()
        self.addCleanup(controller.disconnect)
        hatalar, baglandi = [], []
        controller.connection_failed.connect(hatalar.append)
        controller.connected.connect(baglandi.append)

        controller._connect_worker("Host", "0.0.0.0", ilk.port, "general", "ayse", "")

        self.assertEqual(baglandi, [], "ikinci Host sessizce acildi")
        self.assertEqual(len(hatalar), 1)
        self.assertIn(hatalar[0], {t("socket_error.10048"), t("socket_error.10013")})


class EnterKeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _page(self):
        handle, path = tempfile.mkstemp(suffix=".ini")
        os.close(handle)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        page = ConnectPage(ChatSettings(QSettings(path, QSettings.Format.IniFormat)))
        self.addCleanup(page.deleteLater)
        page.host_edit.setText("25.1.2.3")
        self.istekler = []
        page.connect_requested.connect(lambda *args: self.istekler.append(args))
        return page

    def test_enter_in_any_text_field_connects(self):
        page = self._page()
        for alan in ("username_edit", "host_edit", "port_edit", "room_edit", "password_edit"):
            with self.subTest(alan=alan):
                self.istekler.clear()

                getattr(page, alan).returnPressed.emit()

                self.assertEqual(len(self.istekler), 1)

    def test_enter_while_connecting_does_not_start_a_second_attempt(self):
        page = self._page()
        page.set_busy(True)

        page.password_edit.returnPressed.emit()

        self.assertEqual(self.istekler, [])


if __name__ == "__main__":
    unittest.main()
