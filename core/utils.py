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

from __future__ import annotations

import socket


DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5555


def parse_port_input(raw_value: str, default_port: int = DEFAULT_PORT) -> int:
    value = raw_value.strip()
    if not value:
        return default_port

    port = int(value)
    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535.")
    return port


def get_local_ipv4_addresses() -> list[str]:
    addresses: list[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM):
            ip = info[4][0]
            if ip.startswith("127.") or ip in addresses:
                continue
            addresses.append(ip)
    except socket.gaierror:
        pass
    return addresses


def socket_error_code(error: OSError) -> int | None:
    """A socket error's code: winerror on Windows, errno elsewhere.

    Turning the code into text a person reads is the interface's job (the
    language choice lives there); core/ produces no text meant for the user.
    """
    code = getattr(error, "winerror", None)
    if code is None:
        code = getattr(error, "errno", None)
    return code

