"""
Abstraccion de una impresora fisica.

Envuelve la logica de conversion imagen -> ESC/POS + envio al spooler de
Windows con nombre + tamano de papel + rol para logging claro.
"""
import base64
import logging
from dataclasses import dataclass

from .printer_backend import (
    print_image_win32,
    open_cashbox_win32,
    list_printers,
)


logger = logging.getLogger("pos_print_proxy.printer")


@dataclass
class Printer:
    """
    Representa una impresora fisica gestionada por el proxy.

    Los datos vienen del config.yaml (PrinterConfig). Esta clase agrega
    metodos de negocio (imprimir, abrir cajon) que dispatch al backend
    Windows correcto.
    """
    name: str                  # nombre amigable para logs
    windows_printer: str       # nombre EXACTO en Windows
    paper_width: int = 576     # 576 = 80mm, 384 = 58mm
    role: str = "both"         # informativo

    def print_receipt(self, receipt_b64: str) -> None:
        """Decodifica base64, convierte a ESC/POS raster y envia al spooler."""
        image_bytes = base64.b64decode(receipt_b64)
        print_image_win32(image_bytes, self.windows_printer, self.paper_width)
        logger.info(
            f"[{self.name}] Impreso ({len(image_bytes)} bytes) -> '{self.windows_printer}'"
        )

    def open_cashbox(self) -> None:
        """Envia el comando ESC/POS de apertura de cajon."""
        open_cashbox_win32(self.windows_printer)
        logger.info(f"[{self.name}] Cajon abierto -> '{self.windows_printer}'")


def detect_or_warn(printer: Printer) -> None:
    """
    Verifica que la impresora Windows exista en el sistema.
    No falla si no la encuentra, solo advierte en el log.
    """
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
