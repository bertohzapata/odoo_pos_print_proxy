"""
Entry point del paquete.

    python -m posprintproxy            # Arranca la GUI
    python -m posprintproxy --daemon   # Arranca solo el daemon (sin GUI)
    python -m posprintproxy --minimized  # GUI minimizada a la bandeja
"""
import sys


def main() -> int:
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
