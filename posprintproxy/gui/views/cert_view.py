"""Vista de certificados HTTPS: estado, expiracion, boton de renovacion."""
import datetime as _dt

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..controllers.cert_ctrl import CertController, CertInfo


class CertView(QWidget):

    def __init__(self, cert_ctrl: CertController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cert_ctrl = cert_ctrl
        self._build_ui()
        self._connect()
        self._refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(16)

        title = QLabel("Certificado HTTPS")
        title.setObjectName("H1")
        root.addWidget(title)

        subtitle = QLabel(
            "El proxy sirve HTTPS local en localhost. Los navegadores requieren "
            "que el cert este firmado por una CA que Windows confie. Este panel "
            "gestiona la CA local (mkcert) y renueva el cert cuando expira."
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        # Card de estado
        state_box = QGroupBox("Estado actual")
        grid = QGridLayout(state_box)
        grid.setContentsMargins(20, 22, 20, 20)
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(10)

        self.status_label = QLabel("—")
        self.status_label.setObjectName("H2")
        grid.addWidget(QLabel("Estado:"), 0, 0, alignment=Qt.AlignRight)
        grid.addWidget(self.status_label, 0, 1)

        self.subject_label = QLabel("—")
        self.subject_label.setWordWrap(True)
        grid.addWidget(QLabel("Sujeto:"), 1, 0, alignment=Qt.AlignRight | Qt.AlignTop)
        grid.addWidget(self.subject_label, 1, 1)

        self.issuer_label = QLabel("—")
        self.issuer_label.setWordWrap(True)
        grid.addWidget(QLabel("Emitido por:"), 2, 0, alignment=Qt.AlignRight | Qt.AlignTop)
        grid.addWidget(self.issuer_label, 2, 1)

        self.valid_from_label = QLabel("—")
        grid.addWidget(QLabel("Valido desde:"), 3, 0, alignment=Qt.AlignRight)
        grid.addWidget(self.valid_from_label, 3, 1)

        self.valid_to_label = QLabel("—")
        grid.addWidget(QLabel("Valido hasta:"), 4, 0, alignment=Qt.AlignRight)
        grid.addWidget(self.valid_to_label, 4, 1)

        self.days_label = QLabel("—")
        grid.addWidget(QLabel("Dias restantes:"), 5, 0, alignment=Qt.AlignRight)
        grid.addWidget(self.days_label, 5, 1)

        grid.setColumnStretch(1, 1)
        root.addWidget(state_box)

        # Renovacion
        renew_box = QGroupBox("Renovar certificado")
        renew_layout = QVBoxLayout(renew_box)
        renew_layout.setContentsMargins(20, 22, 20, 20)
        renew_layout.setSpacing(10)

        self.renew_help = QLabel(
            "La renovacion regenera el cert para localhost + 127.0.0.1 + ::1. "
            "Si es la primera vez, tambien instala la CA local en Windows "
            "(puede pedir confirmacion de administrador)."
        )
        self.renew_help.setObjectName("Muted")
        self.renew_help.setWordWrap(True)
        renew_layout.addWidget(self.renew_help)

        self.progress_label = QLabel("")
        self.progress_label.setObjectName("Muted")
        renew_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # infinito
        self.progress_bar.setVisible(False)
        renew_layout.addWidget(self.progress_bar)

        btn_row = QHBoxLayout()
        self.btn_renew = QPushButton("Renovar ahora")
        self.btn_renew.setObjectName("Primary")
        self.btn_refresh = QPushButton("Refrescar estado")
        self.btn_refresh.setObjectName("Ghost")
        btn_row.addWidget(self.btn_renew)
        btn_row.addWidget(self.btn_refresh)
        btn_row.addStretch(1)
        renew_layout.addLayout(btn_row)

        root.addWidget(renew_box)
        root.addStretch(1)

    def _connect(self) -> None:
        self.btn_renew.clicked.connect(self._on_renew)
        self.btn_refresh.clicked.connect(self._refresh)
        self.cert_ctrl.renew_started.connect(self._on_renew_started)
        self.cert_ctrl.renew_progress.connect(self._on_renew_progress)
        self.cert_ctrl.renew_finished.connect(self._on_renew_finished)
        self.cert_ctrl.info_changed.connect(self._render_info)

    # --- Handlers ---

    def _refresh(self) -> None:
        self.cert_ctrl.inspect()

    def _on_renew(self) -> None:
        confirm = QMessageBox.question(
            self, "Renovar certificado",
            "Se regenerara el certificado y, si es la primera vez, se instalara "
            "la CA local en Windows. Podria pedirte confirmacion de administrador.\n\n"
            "¿Continuar?"
        )
        if confirm == QMessageBox.Yes:
            self.cert_ctrl.renew(install_ca=True)

    def _on_renew_started(self) -> None:
        self.btn_renew.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_label.setText("Iniciando renovacion...")

    def _on_renew_progress(self, msg: str) -> None:
        self.progress_label.setText(msg)

    def _on_renew_finished(self, ok: bool, msg: str) -> None:
        self.btn_renew.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        self.progress_bar.setVisible(False)
        if ok:
            self.progress_label.setText(msg)
            QMessageBox.information(self, "Renovacion completada", msg)
        else:
            self.progress_label.setText("")
            QMessageBox.critical(self, "Renovacion fallo", msg)

    def _render_info(self, info: CertInfo) -> None:
        if not info.exists:
            self.status_label.setText("No instalado")
            self.subject_label.setText("—")
            self.issuer_label.setText("—")
            self.valid_from_label.setText("—")
            self.valid_to_label.setText("—")
            self.days_label.setText("—")
            return

        if info.expired:
            self.status_label.setText("Expirado - renovar")
        elif info.expires_soon:
            self.status_label.setText(f"Expira pronto ({info.days_left} dias)")
        elif info.valid:
            self.status_label.setText("Valido")
        else:
            self.status_label.setText(f"Invalido: {info.error}")

        self.subject_label.setText(info.subject or "—")
        self.issuer_label.setText(info.issuer or "—")
        self.valid_from_label.setText(
            info.not_before.strftime("%Y-%m-%d %H:%M UTC") if info.not_before else "—"
        )
        self.valid_to_label.setText(
            info.not_after.strftime("%Y-%m-%d %H:%M UTC") if info.not_after else "—"
        )
        self.days_label.setText(str(info.days_left) if info.exists else "—")
