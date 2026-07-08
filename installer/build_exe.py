"""
Build script de PyInstaller.

Uso local (Windows con Python 3.11+):
    pip install -r requirements-dev.txt
    python installer/build_exe.py

Uso en CI: llamado por .github/workflows/release.yml.

Produce: dist/POSPrintProxy/ con el .exe y sus dependencias.
"""
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = REPO_ROOT / "dist"
BUILD_DIR = REPO_ROOT / "build"
BIN_DIR = REPO_ROOT / "installer" / "bin"

MKCERT_VERSION = "v1.4.4"
MKCERT_URL = (
    f"https://github.com/FiloSottile/mkcert/releases/download/{MKCERT_VERSION}/"
    "mkcert-v1.4.4-windows-amd64.exe"
)


def ensure_mkcert() -> Path:
    """Descarga mkcert.exe si no existe. Sera bundleado con el .exe."""
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    mkcert = BIN_DIR / "mkcert.exe"
    if mkcert.exists():
        return mkcert
    print(f"Descargando mkcert desde {MKCERT_URL}...")
    with urllib.request.urlopen(MKCERT_URL, timeout=60) as r:
        with open(mkcert, "wb") as f:
            shutil.copyfileobj(r, f)
    return mkcert


def clean() -> None:
    for p in (DIST_DIR, BUILD_DIR):
        if p.exists():
            shutil.rmtree(p)


def build() -> None:
    ensure_mkcert()

    spec_file = REPO_ROOT / "installer" / "posprintproxy.spec"

    if spec_file.exists():
        cmd = ["pyinstaller", "--noconfirm", str(spec_file)]
    else:
        cmd = [
            "pyinstaller",
            "--noconfirm",
            "--windowed",
            "--name", "POSPrintProxy",
            "--icon", str(REPO_ROOT / "installer" / "app.ico") if (REPO_ROOT / "installer" / "app.ico").exists() else "NONE",
            "--add-data", f"{REPO_ROOT / 'posprintproxy' / 'gui' / 'theme.qss'}:posprintproxy/gui",
            "--add-binary", f"{BIN_DIR / 'mkcert.exe'}:bin",
            "--collect-submodules", "posprintproxy",
            "--hidden-import", "win32print",
            "--hidden-import", "cryptography",
            str(REPO_ROOT / "main.py"),
        ]
        # PyInstaller usa ; en Windows y : en Unix para --add-data. Ajustamos.
        if sys.platform == "win32":
            cmd = [c.replace(":", ";") if c.startswith(str(REPO_ROOT)) and (":" in c and c.count(":") == 1) else c for c in cmd]

    print("Ejecutando:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=REPO_ROOT)

    print()
    print("Build completo:", DIST_DIR / "POSPrintProxy")


def main() -> int:
    if "--clean" in sys.argv:
        clean()
    build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
