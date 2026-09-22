"""
Abstraccion de una impresora fisica.

Envuelve la logica de conversion imagen -> ESC/POS + envio al spooler de
Windows con nombre + tamano de papel + rol para logging claro.
"""
import base64
import logging
import threading
from dataclasses import dataclass, field

from .printer_backend import (
    print_image_win32,
    open_cashbox_win32,
    print_image_network,
    open_cashbox_network,
    probe_network_printer,
    list_printers,
    DEFAULT_TCP_PORT,
)


logger = logging.getLogger("pos_print_proxy.printer")


@dataclass
class Printer:
    """
    Representa una impresora fisica gestionada por el proxy.

    Los datos vienen del config.yaml (PrinterConfig). Esta clase agrega
    metodos de negocio (imprimir, abrir cajon) que dispatch al backend
    correcto segun el transporte:
      - connection == "usb"     -> spooler de Windows (windows_printer)
      - connection == "network" -> socket TCP crudo a host:tcp_port (9100)
    """
    name: str                  # nombre amigable para logs
    windows_printer: str = ""  # solo USB: nombre EXACTO en Windows
    paper_width: int = 576     # 576 = 80mm, 384 = 58mm
    role: str = "both"         # informativo
    connection: str = "usb"    # "usb" | "network"
    host: str = ""             # solo network: IP/hostname
    tcp_port: int = DEFAULT_TCP_PORT  # solo network

    # Serializa los trabajos hacia ESTA impresora. El 9100 atiende una conexion
    # a la vez; sin el lock, dos trabajos concurrentes del mismo proxy podrian
    # intercalarse. La contencion ENTRE dispositivos distintos se maneja por
    # reintento a nivel de socket (create_connection reintentable arriba).
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    @property
    def target(self) -> str:
        """Descripcion del destino para logs."""
        if self.connection == "network":
            return f"{self.host}:{self.tcp_port}"
        return f"'{self.windows_printer}'"

    def print_receipt(self, receipt_b64: str) -> None:
        """Decodifica base64, convierte a ESC/POS raster y envia al destino."""
        image_bytes = base64.b64decode(receipt_b64)
        with self._lock:
            if self.connection == "network":
                print_image_network(image_bytes, self.host, self.tcp_port, self.paper_width)
            else:
                print_image_win32(image_bytes, self.windows_printer, self.paper_width)
        logger.info(
            f"[{self.name}] Impreso ({len(image_bytes)} bytes) -> {self.target}"
        )

    def open_cashbox(self) -> None:
        """Envia el comando ESC/POS de apertura de cajon."""
        with self._lock:
            if self.connection == "network":
                open_cashbox_network(self.host, self.tcp_port)
            else:
                open_cashbox_win32(self.windows_printer)
        logger.info(f"[{self.name}] Cajon abierto -> {self.target}")


def detect_or_warn(printer: Printer) -> None:
    """
    Verifica que la impresora exista/este alcanzable.
    No falla si no la encuentra, solo advierte en el log.
    """
    if printer.connection == "network":
        if probe_network_printer(printer.host, printer.tcp_port):
            logger.info(
                f"[{printer.name}] Impresora de red alcanzable en {printer.target}"
            )
        else:
            logger.warning(
                f"[{printer.name}] ATENCION: no responde el puerto TCP en "
                f"{printer.target}. Verifica IP, cable de red y que la "
                f"impresora este encendida."
            )
        return

    try:
        available = list_printers()
    except Exception:
        logger.warning(
            f"[{printer.name}] No se pudo enumerar impresoras de Windows "
            f"(win32print no disponible)"
        )
        return

    if printer.windows_printer not in available:
        logger.warning(
            f"[{printer.name}] ATENCION: '{printer.windows_printer}' no esta en la "
            f"lista de impresoras de Windows. Disponibles: {available}"
        )
