"""
Vista principal (dashboard): estado del daemon, resumen de impresoras,
boton grande de encender/apagar, contadores clave.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...daemon.daemon import DaemonSnapshot, DaemonStatus
from ..controllers.config_ctrl import ConfigController
from ..controllers.daemon_ctrl import DaemonController


STATUS_LABEL = {
    DaemonStatus.STOPPED: ("Detenido", "BadgeStopped", "StatusDotStopped"),
    DaemonStatus.STARTING: ("Iniciando...", "Badge", "StatusDot"),
    DaemonStatus.RUNNING: ("En ejecucion", "Badge", "StatusDot"),
    DaemonStatus.STOPPING: ("Deteniendo...", "BadgeStopped", "StatusDotStopped"),
    DaemonStatus.ERROR: ("Error", "BadgeError", "StatusDotError"),
}


class DashboardView(QWidget):

    def __init__(
        self,
        daemon_ctrl: DaemonController,
        config_ctrl: ConfigController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.daemon_ctrl = daemon_ctrl
        self.config_ctrl = config_ctrl

        self._build_ui()
        self._connect()
        self._refresh_status(daemon_ctrl.snapshot())
        self._refresh_summary()

    # --- UI ---

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(20)

        title = QLabel("Dashboard")
        title.setObjectName("H1")
        root.addWidget(title)

        # --- Card: estado del daemon ---
        status_box = QGroupBox("Estado del proxy")
        status_layout = QVBoxLayout(status_box)
        status_layout.setContentsMargins(20, 22, 20, 20)
        status_layout.setSpacing(14)

        header = QHBoxLayout()
        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("StatusDot")
        self.status_text = QLabel("Detenido")
        self.status_text.setObjectName("H2")

        self.status_badge = QLabel("STOPPED")
        self.status_badge.setObjectName("Badge")
        self.status_badge.setAlignment(Qt.AlignCenter)

        header.addWidget(self.status_dot)
        header.addWidget(self.status_text)
        header.addStretch(1)
        header.addWidget(self.status_badge)
        status_layout.addLayout(header)

        self.status_detail = QLabel("El daemon no esta corriendo. Presiona Iniciar para arrancar.")
        self.status_detail.setObjectName("Muted")
        self.status_detail.setWordWrap(True)
        status_layout.addWidget(self.status_detail)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.btn_start = QPushButton("Iniciar")
        self.btn_start.setObjectName("Primary")
        self.btn_start.setMinimumWidth(120)

        self.btn_stop = QPushButton("Detener")
        self.btn_stop.setMinimumWidth(120)

        self.btn_restart = QPushButton("Reiniciar")
        self.btn_restart.setMinimumWidth(120)

        buttons.addWidget(self.btn_start)
        buttons.addWidget(self.btn_stop)
        buttons.addWidget(self.btn_restart)
        buttons.addStretch(1)
        status_layout.addLayout(buttons)

        root.addWidget(status_box)

        # --- Card: resumen ---
        summary_box = QGroupBox("Resumen de configuracion")
        grid = QGridLayout(summary_box)
        grid.setContentsMargins(20, 22, 20, 20)
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(12)

        self.summary_domain = self._add_metric(grid, 0, "Dominio Odoo")
        self.summary_printers = self._add_metric(grid, 1, "Impresoras configuradas")
        self.summary_ports = self._add_metric(grid, 2, "Puertos en uso")

        root.addWidget(summary_box)
        root.addStretch(1)

    def _add_metric(self, grid: QGridLayout, row: int, label: str) -> QLabel:
        lbl = QLabel(label)
        lbl.setObjectName("Muted")
        val = QLabel("—")
        val.setObjectName("H2")
        val.setWordWrap(True)
        grid.addWidget(lbl, row, 0, alignment=Qt.AlignTop)
        grid.addWidget(val, row, 1, alignment=Qt.AlignTop)
        grid.setColumnStretch(1, 1)
        return val

    def _connect(self) -> None:
        self.btn_start.clicked.connect(self.daemon_ctrl.start)
        self.btn_stop.clicked.connect(self.daemon_ctrl.stop)
        self.btn_restart.clicked.connect(self.daemon_ctrl.restart)
        self.daemon_ctrl.status_changed.connect(self._refresh_status)
        self.config_ctrl.config_changed.connect(lambda _: self._refresh_summary())

    # --- Refresh ---

    def _refresh_status(self, snap: DaemonSnapshot) -> None:
        label, badge_id, dot_id = STATUS_LABEL[snap.status]
        self.status_text.setText(label)
        self.status_badge.setText(snap.status.value.upper())
        self.status_badge.setObjectName(badge_id)
        self.status_dot.setObjectName(dot_id)

        # Forzar el reload de estilo tras cambiar object name
        for w in (self.status_badge, self.status_dot):
            w.style().unpolish(w)
            w.style().polish(w)

        # Detalle contextual
        if snap.status == DaemonStatus.RUNNING:
            ports_str = ", ".join(str(p) for p in snap.running_ports)
            self.status_detail.setText(f"El daemon esta atendiendo en los puertos: {ports_str}")
        elif snap.status == DaemonStatus.ERROR:
            self.status_detail.setText(f"Ultimo error: {snap.last_error or 'desconocido'}")
        elif snap.status == DaemonStatus.STOPPED:
            self.status_detail.setText(
                "El daemon no esta corriendo. Presiona Iniciar para arrancar."
            )
        elif snap.status == DaemonStatus.STARTING:
            self.status_detail.setText("Levantando los servidores...")
        elif snap.status == DaemonStatus.STOPPING:
            self.status_detail.setText("Cerrando conexiones...")

        # Estado de botones
        running = snap.status in (DaemonStatus.STARTING, DaemonStatus.RUNNING)
        transitioning = snap.status in (DaemonStatus.STARTING, DaemonStatus.STOPPING)
        self.btn_start.setEnabled(not running and not transitioning)
        self.btn_stop.setEnabled(running and not transitioning)
        self.btn_restart.setEnabled(running and not transitioning)

        # Refrescar resumen tambien (puertos podrian cambiar)
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        try:
            cfg = self.config_ctrl.current()
        except Exception:
            return
        self.summary_domain.setText(cfg.allowed_origin)
        self.summary_printers.setText(str(len(cfg.printers)))
        ports = [str(p.port) for p in cfg.printers]
        self.summary_ports.setText(", ".join(ports) if ports else "—")
