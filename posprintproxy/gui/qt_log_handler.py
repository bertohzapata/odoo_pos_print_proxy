"""
Handler de logging que reemite cada linea via una senial Qt para pintarla
en el visor de logs en tiempo real.
"""
import logging

from PySide6.QtCore import QObject, Signal


class QtLogBridge(QObject):
    """Objeto Qt que emite lineas de log como senial."""
    line = Signal(str, int)  # (mensaje formateado, nivel numero)


class QtLogHandler(logging.Handler):
    """Handler que empuja cada record al bridge Qt."""

    def __init__(self, bridge: QtLogBridge) -> None:
        super().__init__()
        self.bridge = bridge
        self.setFormatter(logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        ))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            # emit es thread-safe cuando la conexion cruza hilos
            self.bridge.line.emit(msg, record.levelno)
        except Exception:
            self.handleError(record)
