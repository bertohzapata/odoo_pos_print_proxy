"""
Entry point del paquete.

    python -m posprintproxy            # Arranca la GUI
    python -m posprintproxy --daemon   # Arranca solo el daemon (sin GUI)
    python -m posprintproxy --minimized  # GUI minimizada a la bandeja
"""
import io
import sys


def _ensure_std_streams() -> None:
    """
    En PyInstaller --windowed sys.stdout y sys.stderr son None. Muchas
    librerias (uvicorn, print()) asumen que existen y fallan con AttributeError
    o `'NoneType' object has no attribute 'isatty'`. Los reemplazamos con
    buffers en memoria que descartan la salida silenciosamente.
    """
    class _NullTTY(io.StringIO):
        def isatty(self) -> bool:
            return False

    if sys.stdout is None:
        sys.stdout = _NullTTY()
    if sys.stderr is None:
        sys.stderr = _NullTTY()


def main() -> int:
    _ensure_std_streams()

    if "--daemon" in sys.argv:
        # Modo daemon puro (retrocompat con v1.4)
        sys.argv = [a for a in sys.argv if a != "--daemon"]
        from .daemon.daemon import main as daemon_main
        daemon_main()
        return 0

    from .gui.app import main as gui_main
    return gui_main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
