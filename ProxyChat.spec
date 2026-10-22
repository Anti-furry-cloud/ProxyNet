# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller yapilandirmasi.

Derleme icin tek kaynak burasidir; build_exe.ps1 bu dosyayi cagirir.

Not: PySide6 icin bilerek collect_all() KULLANILMIYOR. collect_all tum Qt
modullerini (WebEngine, Quick, Qt3D, Charts...) pakete koyuyor ve exe'yi
~245 MB'a cikariyordu. PyInstaller'in kendi PySide6 hook'u QtWidgets/QtGui/
QtCore icin gerekenleri zaten topluyor; asagidaki EXCLUDED_QT_MODULES ile
kullanilmayanlari disarida birakiyoruz.
"""

import os

# libopus depoya KONMUYOR. Kaynagi dogrulanmamis 0,5 MB'lik bir ikiliyi
# depoda tasimak, bir guvenlik projesinde odenmek istemeyen bir bedel
# (bkz. THIRD-PARTY.md). Bunun yerine derleme aninda PROXYCHAT_OPUS_DLL ile
# gosteriliyor ve pakete gomuluyor; `core/voice_opus.py` donmus exe'de once
# _MEIPASS'e baktigi icin calisma aninda kendiliginden bulunuyor.
#
# Degisken yoksa liste bos kalir ve exe Opus'suz cikar -- ses o zaman
# mu-law'a duser (cerceve 60 bayt yerine 320). Bunun sessizce olmamasi icin
# build_exe.ps1 degisken yokken duruyor; bilerek Opus'suz derlemek icin
# oradaki -Opussuz anahtari var.
_opus = os.environ.get("PROXYCHAT_OPUS_DLL", "")
OPUS_BINARIES = [(_opus, ".")] if _opus and os.path.isfile(_opus) else []


# Uygulama QtCore + QtGui + QtWidgets kullaniyor; sesli sohbetle birlikte
# QtMultimedia da gerekiyor (mikrofon ve hoparlor). QtMultimedia 2026-09-25'e
# kadar bu listedeydi; sesli sohbet uygulamaya girince cikarildi ve exe'nin
# ne kadar buyudugu OLCULDU (bkz. docs/sesli-sohbet-plani.md, Faz 4).
EXCLUDED_QT_MODULES = [
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtGraphs",
    "PySide6.QtHelp",
    "PySide6.QtHttpServer",
    "PySide6.QtLocation",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtNfc",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickControls2",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialBus",
    "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio",
    "PySide6.QtSql",
    "PySide6.QtStateMachine",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtUiTools",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
]


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=OPUS_BINARIES,
    datas=[('assets/proxychat_splash.png', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDED_QT_MODULES + ['tkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ProxyChat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX KAPALI, iki sebeple. (1) Yeniden uretilebilirlik: UPX'in cikisi
    # derlemeden derlemeye degisebiliyor ve zincirin ucunda duruyor.
    # (2) Antivirus: UPX'lenmis bir exe sezgisel taramanin klasik
    # tetikleyicisi, ve bu imzasiz bir sifreli sohbet programi.
    # Olcum (2026-09-29): UPX bu makinede zaten kurulu degildi, yani True
    # sessizce hicbir sey yapmiyordu -- ama bir gun kurulsaydi cikti
    # degisirdi. Acikca kapatmak o mayini kaldiriyor.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/ProxyChat.ico'],
)
