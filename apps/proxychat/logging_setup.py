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

"""ProxyChat log dosyasi.

Sunucu olaylari eskiden print ile stdout'a gidiyordu; pencereli exe'de stdout
olmadigi icin pratikte hicbir yere gitmiyordu. Testci "bozuldu" dediginde
bakilacak bir sey yoktu.

Katman ayrimi korunuyor: core/ yalnizca logging kaydi uretir, dosyaya yazma
karari ve yeri BU katmandadir (THREAT_MODEL.md ilke 2 -- cekirdek diske
yazmaz).

Loglara mesaj icerigi ya da uzunlugu YAZILMAZ. Yazilanlar: olay adi, oda adi
ve durum. Bkz. THREAT_MODEL.md 5.3.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

APP_DIR_NAME = "ProxyChat"
LOG_FILE_NAME = "proxychat.log"

#: Kucuk tutuluyor: log bir teshis araci, arsiv degil.
MAX_BYTES = 512 * 1024
BACKUP_COUNT = 1


def log_directory() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_STATE_HOME")
    if base:
        return Path(base) / APP_DIR_NAME / "logs"
    return Path.home() / f".{APP_DIR_NAME.lower()}" / "logs"


def log_file_path() -> Path:
    return log_directory() / LOG_FILE_NAME


def setup_logging(level: int = logging.INFO) -> Path | None:
    """Log dosyasini kurar ve yolunu dondurur.

    Dosya acilamazsa (izin, disk dolu) uygulama calismaya devam eder;
    log ugruna baslamamak dogru olmaz.
    """
    logger = logging.getLogger("proxychat")
    logger.setLevel(level)

    # Ayni handler'i iki kez eklemeyelim (testler, yeniden baslatma).
    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler):
            return Path(handler.baseFilename)

    try:
        directory = log_directory()
        directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            directory / LOG_FILE_NAME,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError:
        return None

    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return Path(handler.baseFilename)


def teardown_logging() -> None:
    """Dosya kaydini durdurur ve dosyayi kapatir.

    Kullanici tanilama kaydini kapattiginda cagrilir; uygulamanin yeniden
    baslatilmasini beklemeye gerek kalmaz.
    """
    logger = logging.getLogger("proxychat")
    for handler in list(logger.handlers):
        if isinstance(handler, RotatingFileHandler):
            logger.removeHandler(handler)
            handler.close()


def set_logging_enabled(enabled: bool) -> Path | None:
    """Tanilama kaydini acar ya da kapatir."""
    if enabled:
        return setup_logging()
    teardown_logging()
    return None


def delete_log_files() -> int:
    """Diskteki log dosyalarini siler, silinen dosya sayisini dondurur.

    Kullanici kaydi kapattiginda geriye eski kayitlarin kalmasi anlamsiz
    olurdu.
    """
    teardown_logging()
    silinen = 0
    directory = log_directory()
    if not directory.is_dir():
        return 0
    for path in directory.glob(f"{LOG_FILE_NAME}*"):
        try:
            path.unlink()
            silinen += 1
        except OSError:
            continue
    return silinen
