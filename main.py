"""
Entry point de compatibilidad con v1.x.

En v2.0 la app se lanza como paquete:
    python -m posprintproxy

Este archivo se conserva para que start_proxy.bat y guias antiguas sigan
funcionando. Redirige a la GUI (o al daemon con --daemon).
"""
import sys

from posprintproxy.__main__ import main


if __name__ == "__main__":
    sys.exit(main())
