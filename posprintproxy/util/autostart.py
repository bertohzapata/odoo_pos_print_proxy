"""
Gestion de auto-inicio en Windows via registro HKCU\\Run.

No requiere admin. Se activa/desactiva via toggle en la GUI.
"""
import sys
from pathlib import Path


REGISTRY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
REGISTRY_KEY_NAME = "POSPrintProxy"


def _get_registry():
    """Import winreg solo cuando se necesita (no existe en Linux/Mac)."""
    try:
        import winreg
        return winreg
    except ImportError:
        return None


def is_enabled() -> bool:
    """True si el auto-start esta activo en HKCU\\Run."""
    winreg = _get_registry()
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, REGISTRY_KEY_NAME)
            return bool(value)
    except FileNotFoundError:
        return False
    except OSError:
        return False


def current_command() -> str | None:
    """Retorna el comando registrado, o None si no hay."""
    winreg = _get_registry()
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, REGISTRY_KEY_NAME)
            return value
    except FileNotFoundError:
        return None
    except OSError:
        return None


def enable(exe_path: Path | None = None, minimized: bool = True) -> bool:
    """
    Habilita el auto-inicio. Retorna True si tuvo exito.

    Si exe_path es None, usa sys.executable (o script actual en dev).
    Si minimized=True, agrega el flag --minimized para que arranque a la
    bandeja sin abrir el dashboard.
    """
    winreg = _get_registry()
    if winreg is None:
        return False

    if exe_path is None:
        exe_path = Path(sys.executable)

    command = f'"{exe_path}"'
    if minimized:
        command += " --minimized"

    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH) as key:
            winreg.SetValueEx(key, REGISTRY_KEY_NAME, 0, winreg.REG_SZ, command)
        return True
    except OSError:
        return False


def disable() -> bool:
    """Deshabilita el auto-inicio. Retorna True si tuvo exito (o si no existia)."""
    winreg = _get_registry()
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, REGISTRY_KEY_NAME)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False
