"""Icono en la bandeja del sistema con menu contextual."""
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor, QFont
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from ..daemon.daemon import DaemonSnapshot, DaemonStatus
from .controllers.daemon_ctrl import DaemonController
from .controllers.update_ctrl import UpdateInfo


COLOR_RUNNING = "#40c2b2"
COLOR_STOPPED = "#4c5766"
COLOR_ERROR = "#e57171"


def _generate_dot_icon(color_hex: str, size: int = 32) -> QIcon:
    """Genera un icono de bandeja: un circulo relleno de color hex."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    color = QColor(color_hex)
    painter.setBrush(color)
    painter.setPen(Qt.NoPen)
    margin = 4
    painter.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)
    painter.end()
    return QIcon(pixmap)


class TrayIcon(QObject):
    """
    Icono de bandeja. Emite seniales para que el `Application` decida
    (mostrar ventana, salir, etc.).
    """

    show_window_requested = Signal()
    quit_requested = Signal()
    open_view_requested = Signal(str)  # key de vista (dashboard, cert, logs, ...)

    def __init__(self, daemon_ctrl: DaemonController, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.daemon_ctrl = daemon_ctrl

        self._icons = {
            DaemonStatus.STOPPED: _generate_dot_icon(COLOR_STOPPED),
            DaemonStatus.STARTING: _generate_dot_icon(COLOR_RUNNING),
            DaemonStatus.RUNNING: _generate_dot_icon(COLOR_RUNNING),
            DaemonStatus.STOPPING: _generate_dot_icon(COLOR_STOPPED),
            DaemonStatus.ERROR: _generate_dot_icon(COLOR_ERROR),
        }

        self.tray = QSystemTrayIcon()
        self.tray.setIcon(self._icons[DaemonStatus.STOPPED])
        self.tray.setToolTip("POS Print Proxy")
        self.tray.activated.connect(self._on_activated)

        self.menu = QMenu()

        self.status_action = QAction("Detenido", self.menu)
        self.status_action.setEnabled(False)
        self.menu.addAction(self.status_action)
        self.menu.addSeparator()

        self.open_action = QAction("Abrir dashboard", self.menu)
        self.open_action.triggered.connect(self.show_window_requested.emit)
        self.menu.addAction(self.open_action)

        self.menu.addSeparator()

        self.start_action = QAction("Iniciar", self.menu)
        self.start_action.triggered.connect(self.daemon_ctrl.start)
        self.stop_action = QAction("Detener", self.menu)
        self.stop_action.triggered.connect(self.daemon_ctrl.stop)
        self.restart_action = QAction("Reiniciar", self.menu)
        self.restart_action.triggered.connect(self.daemon_ctrl.restart)
        self.menu.addAction(self.start_action)
        self.menu.addAction(self.stop_action)
        self.menu.addAction(self.restart_action)

        self.menu.addSeparator()

        self.logs_action = QAction("Ver logs", self.menu)
        self.logs_action.triggered.connect(lambda: self.open_view_requested.emit("logs"))
        self.cert_action = QAction("Certificado", self.menu)
        self.cert_action.triggered.connect(lambda: self.open_view_requested.emit("cert"))
        self.menu.addAction(self.logs_action)
        self.menu.addAction(self.cert_action)

        self.menu.addSeparator()

        # Placeholder de update (oculto hasta que aparezca uno)
        self.update_action = QAction("", self.menu)
        self.update_action.setVisible(False)
        self.menu.addAction(self.update_action)

        self.quit_action = QAction("Salir", self.menu)
        self.quit_action.triggered.connect(self.quit_requested.emit)
        self.menu.addAction(self.quit_action)

        self.tray.setContextMenu(self.menu)

        # Reaccionar a estado del daemon
        self.daemon_ctrl.status_changed.connect(self._render_status)
        self._render_status(self.daemon_ctrl.snapshot())

    def show(self) -> None:
        self.tray.show()

    def hide(self) -> None:
        self.tray.hide()

    def is_supported(self) -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    def notify(self, title: str, msg: str, kind: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.Information) -> None:
        self.tray.showMessage(title, msg, kind, 5000)

    # --- Handlers ---

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        # Click izquierdo -> abrir dashboard
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_window_requested.emit()

    def _render_status(self, snap: DaemonSnapshot) -> None:
        icon = self._icons.get(snap.status, self._icons[DaemonStatus.STOPPED])
        self.tray.setIcon(icon)

        if snap.status == DaemonStatus.RUNNING:
            ports = ", ".join(str(p) for p in snap.running_ports)
            text = f"En ejecucion (puertos: {ports})"
            self.tray.setToolTip(f"POS Print Proxy — {text}")
        elif snap.status == DaemonStatus.ERROR:
            text = f"Error: {snap.last_error[:60]}"
            self.tray.setToolTip(f"POS Print Proxy — {text}")
        else:
            text = {
                DaemonStatus.STOPPED: "Detenido",
                DaemonStatus.STARTING: "Iniciando...",
                DaemonStatus.STOPPING: "Deteniendo...",
            }.get(snap.status, "")
            self.tray.setToolTip(f"POS Print Proxy — {text}")

        self.status_action.setText(text)

        running = snap.status in (DaemonStatus.STARTING, DaemonStatus.RUNNING)
        transitioning = snap.status in (DaemonStatus.STARTING, DaemonStatus.STOPPING)
        self.start_action.setEnabled(not running and not transitioning)
        self.stop_action.setEnabled(running and not transitioning)
        self.restart_action.setEnabled(running and not transitioning)

    def show_update_available(self, info: UpdateInfo) -> None:
        """Muestra el item de update y una notificacion."""
        self.update_action.setText(f"Actualizar a v{info.latest_version}")
        self.update_action.setVisible(True)
        try:
            self.update_action.triggered.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.update_action.triggered.connect(lambda: self.open_view_requested.emit("system"))

        self.notify(
            "Actualizacion disponible",
            f"POS Print Proxy v{info.latest_version} disponible. "
            f"Estas ejecutando v{info.current_version}. "
            "Abre 'Sistema' para ver detalles.",
        )
