"""Ventana principal con sidebar de navegacion y contenido apilado."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __app_name__, __version__
from .controllers.cert_ctrl import CertController
from .controllers.config_ctrl import ConfigController
from .controllers.daemon_ctrl import DaemonController
from .controllers.update_ctrl import UpdateController
from .qt_log_handler import QtLogBridge
from .views.cert_view import CertView
from .views.dashboard_view import DashboardView
from .views.logs_view import LogsView
from .views.printers_view import PrintersView
from .views.system_view import SystemView


NAV_ITEMS = [
    ("dashboard", "Dashboard"),
    ("printers", "Impresoras"),
    ("logs", "Logs"),
    ("cert", "Certificado"),
    ("system", "Sistema"),
]


class MainWindow(QMainWindow):
    """
    Ventana principal. Al cerrarla, se oculta a la bandeja (no cierra la app).
    Salir del programa: menu del tray > Salir.
    """

    def __init__(
        self,
        daemon_ctrl: DaemonController,
        config_ctrl: ConfigController,
        cert_ctrl: CertController,
        update_ctrl: UpdateController,
        log_bridge: QtLogBridge,
    ) -> None:
        super().__init__()
        self.setWindowTitle(f"{__app_name__} v{__version__}")
        self.setMinimumSize(960, 620)
        self.resize(1080, 700)
        self._quitting_from_tray = False

        self._build_ui(daemon_ctrl, config_ctrl, cert_ctrl, update_ctrl, log_bridge)

    def _build_ui(
        self,
        daemon_ctrl: DaemonController,
        config_ctrl: ConfigController,
        cert_ctrl: CertController,
        update_ctrl: UpdateController,
        log_bridge: QtLogBridge,
    ) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- Sidebar ----
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(0, 20, 0, 20)
        side_layout.setSpacing(4)

        brand = QLabel(__app_name__)
        brand.setObjectName("TitleBarTitle")
        brand.setContentsMargins(24, 4, 24, 2)
        side_layout.addWidget(brand)

        version = QLabel(f"v{__version__}")
        version.setObjectName("TitleBarSubtitle")
        version.setContentsMargins(24, 0, 24, 20)
        side_layout.addWidget(version)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        self.nav_buttons = {}
        for key, label in NAV_ITEMS:
            btn = QPushButton(label)
            btn.setObjectName("SidebarButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            side_layout.addWidget(btn)
            self.nav_buttons[key] = btn
            self.nav_group.addButton(btn)

        side_layout.addStretch(1)

        root.addWidget(sidebar)

        # ---- Content ----
        content = QWidget()
        content.setObjectName("Content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 1)

        # Views
        self.dashboard_view = DashboardView(daemon_ctrl, config_ctrl)
        self.printers_view = PrintersView(daemon_ctrl, config_ctrl)
        self.logs_view = LogsView(log_bridge)
        self.cert_view = CertView(cert_ctrl)
        self.system_view = SystemView(config_ctrl, update_ctrl)

        self.stack.addWidget(self.dashboard_view)
        self.stack.addWidget(self.printers_view)
        self.stack.addWidget(self.logs_view)
        self.stack.addWidget(self.cert_view)
        self.stack.addWidget(self.system_view)

        root.addWidget(content, 1)

        # Conexion nav -> stack
        for i, (key, _) in enumerate(NAV_ITEMS):
            self.nav_buttons[key].clicked.connect(lambda _c=False, idx=i: self.stack.setCurrentIndex(idx))

        # Default: dashboard
        self.nav_buttons["dashboard"].setChecked(True)
        self.stack.setCurrentIndex(0)

    # --- Cerrar a la bandeja ---

    def request_quit(self) -> None:
        """Llamar desde el tray para cerrar realmente la app."""
        self._quitting_from_tray = True
        self.close()

    def is_quitting(self) -> bool:
        return self._quitting_from_tray

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._quitting_from_tray:
            event.accept()
        else:
            # Ocultar a la bandeja
            event.ignore()
            self.hide()

    def show_view(self, key: str) -> None:
        for i, (k, _) in enumerate(NAV_ITEMS):
            if k == key:
                self.nav_buttons[k].setChecked(True)
                self.stack.setCurrentIndex(i)
                return
