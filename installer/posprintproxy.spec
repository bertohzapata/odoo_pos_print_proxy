# -*- mode: python ; coding: utf-8 -*-
"""
Spec de PyInstaller para POS Print Proxy v2.0.

Uso local (Windows con Python 3.11+):
    pyinstaller --noconfirm installer/posprintproxy.spec

Produce dist/POSPrintProxy/ (modo --onedir) con el .exe y sus dependencias.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(SPEC).resolve().parent.parent
GUI_DIR = REPO_ROOT / "posprintproxy" / "gui"
BIN_DIR = REPO_ROOT / "installer" / "bin"


datas = [
    (str(GUI_DIR / "theme.qss"), "posprintproxy/gui"),
    (str(REPO_ROOT / "config.yaml.default"), "."),
]

binaries = []
if (BIN_DIR / "mkcert.exe").exists():
    binaries.append((str(BIN_DIR / "mkcert.exe"), "bin"))


a = Analysis(
    [str(REPO_ROOT / "main.py")],
    pathex=[str(REPO_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "win32print",
        "win32com.client",
        "cryptography",
        "cryptography.hazmat.backends.openssl",
        "posprintproxy.daemon.printer_backend",
        "posprintproxy.gui.views.dashboard_view",
        "posprintproxy.gui.views.printers_view",
        "posprintproxy.gui.views.logs_view",
        "posprintproxy.gui.views.cert_view",
        "posprintproxy.gui.views.system_view",
        "posprintproxy.gui.controllers.daemon_ctrl",
        "posprintproxy.gui.controllers.config_ctrl",
        "posprintproxy.gui.controllers.cert_ctrl",
        "posprintproxy.gui.controllers.update_ctrl",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="POSPrintProxy",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,        # Sin ventana CMD (es una GUI)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(REPO_ROOT / "installer" / "app.ico") if (REPO_ROOT / "installer" / "app.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="POSPrintProxy",
)
