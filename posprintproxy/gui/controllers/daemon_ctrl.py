"""
Controlador Qt del daemon. Envuelve ProxyDaemon con seniales para que la GUI
reaccione al cambio de estado sin necesidad de polling explicito.
"""
import logging

from PySide6.QtCore import QObject, QTimer, Signal

from ...daemon import ProxyDaemon
from ...daemon.daemon import DaemonStatus, DaemonSnapshot


logger = logging.getLogger("pos_print_proxy.gui.daemon")


class DaemonController(QObject):
    """Envuelve el daemon con seniales Qt."""

    # Emite cada vez que el estado cambia (o al arrancar el timer)
    status_changed = Signal(object)  # DaemonSnapshot

    def __init__(self, daemon: ProxyDaemon, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.daemon = daemon
        self._last_status: DaemonStatus | None = None
        self._last_snapshot: DaemonSnapshot | None = None

        # Poll cada 500ms para detectar cambios (thread-safe y simple)
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

        # Snapshot inicial
        self._poll()

    # --- API publica ---

    def start(self) -> None:
        self.daemon.start()
        self._poll()

    def stop(self) -> None:
        self.daemon.stop()
        self._poll()

    def restart(self) -> None:
        self.daemon.restart()
        self._poll()

    def snapshot(self) -> DaemonSnapshot:
        return self.daemon.snapshot()

    # --- Interno ---

    def _poll(self) -> None:
        snap = self.daemon.snapshot()
        if snap.status != self._last_status:
            self._last_status = snap.status
            self._last_snapshot = snap
            self.status_changed.emit(snap)
        else:
            self._last_snapshot = snap
