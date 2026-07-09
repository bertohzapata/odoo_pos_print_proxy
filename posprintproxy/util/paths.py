"""
Resolucion de rutas del sistema.

En instalacion normal (installer Windows):
    - Codigo: C:\\Program Files\\POSPrintProxy\\
    - Config y datos: %APPDATA%\\POSPrintProxy\\
    - Logs: %APPDATA%\\POSPrintProxy\\logs\\
    - Certs: %APPDATA%\\POSPrintProxy\\certs\\

En desarrollo (repo clonado):
    - Todo relativo al cwd (compatibilidad con v1.4)
"""
import os
import sys
from pathlib import Path

APP_FOLDER_NAME = "POSPrintProxy"


def is_frozen() -> bool:
    """True si estamos ejecutando dentro del bundle PyInstaller."""
    return getattr(sys, "frozen", False)


def app_data_dir() -> Path:
    """
    Retorna la carpeta de datos del usuario.

    - Windows instalado:  %APPDATA%\\POSPrintProxy
    - Desarrollo:         cwd (para no ensuciar AppData del dev)
    """
    if is_frozen() and os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            path = Path(appdata) / APP_FOLDER_NAME
            path.mkdir(parents=True, exist_ok=True)
            return path
    # Desarrollo: raiz del repo
    return Path.cwd()


def install_dir() -> Path:
    """Carpeta de la instalacion (donde vive el .exe o el codigo)."""
    if is_frozen():
        return Path(sys.executable).parent
    # Desarrollo: raiz del paquete
    return Path(__file__).resolve().parents[2]


def config_path() -> Path:
    """
    Ruta al config.yaml efectivo.

    Prioridad:
    1. AppData del usuario (produccion)
    2. cwd (desarrollo)
    """
    return app_data_dir() / "config.yaml"


def cert_dir() -> Path:
    """Carpeta donde viven los certificados y la CA."""
    path = app_data_dir() / "certs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cert_pem() -> Path:
    return cert_dir() / "localhost.pem"


def cert_key() -> Path:
    return cert_dir() / "localhost-key.pem"


def mkcert_binary() -> Path:
    """
    Ubicacion del mkcert.exe. Preferimos el bundleado en install_dir/, luego
    el descargado en cert_dir/.
    """
    bundled = install_dir() / "bin" / "mkcert.exe"
    if bundled.exists():
        return bundled
    return cert_dir() / "mkcert.exe"


def logs_dir() -> Path:
    """Carpeta de logs (rotativos)."""
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def debug_dir() -> Path:
    """
    Carpeta donde se guardan las impresiones para diagnostico cuando el
    modo debug esta activo. Los archivos NO se rotan; el usuario los
    borra manualmente.
    """
    path = app_data_dir() / "debug"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_config_template() -> Path:
    """Plantilla de config.yaml para primera ejecucion (dentro del install)."""
    return install_dir() / "config.yaml.default"
