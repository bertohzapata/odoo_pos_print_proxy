"""Dialogo modal para crear/editar una impresora."""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ...daemon.config_manager import PrinterConfig, VALID_ROLES


PAPER_WIDTHS = {
    "80mm (576px)": 576,
    "58mm (384px)": 384,
}

# Etiqueta visible -> valor interno de connection
CONNECTIONS = {
    "USB (impresora de Windows)": "usb",
    "Red (IP, puerto 9100)": "network",
}
_CONN_LABEL = {v: k for k, v in CONNECTIONS.items()}


class PrinterDialog(QDialog):
    """
    Formulario para editar una impresora. Autodetecta impresoras Windows
    y permite escribir un nombre custom si la impresora no aparece.
    """

    def __init__(
        self,
        printer: Optional[PrinterConfig] = None,
        used_ports: Optional[list[int]] = None,
        used_names: Optional[list[str]] = None,
        detected_printers: Optional[list[str]] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Impresora" if printer else "Nueva impresora")
        self.setMinimumWidth(440)
        self.used_ports = set(used_ports or [])
        self.used_names = set(used_names or [])
        self.original_port = printer.port if printer else None
        self.original_name = printer.name if printer else None

        self._build_ui(detected_printers or [])
        if printer:
            self._load(printer)
        else:
            self._suggest_defaults()

    def _build_ui(self, detected: list[str]) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        title = QLabel("Configuracion de impresora")
        title.setObjectName("H2")
        root.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("ej: Caja Principal, Cocina, Bar")
        form.addRow("Nombre amigable:", self.name_edit)

        # Tipo de conexion
        self.conn_combo = QComboBox()
        for label in CONNECTIONS.keys():
            self.conn_combo.addItem(label)
        self.conn_combo.currentIndexChanged.connect(self._on_conn_changed)
        form.addRow("Conexion:", self.conn_combo)

        # --- Campos USB ---
        self.driver_combo = QComboBox()
        self.driver_combo.setEditable(True)
        if detected:
            self.driver_combo.addItems(detected)
        self.driver_combo.setPlaceholderText("ej: POS-80")
        self.driver_row_label = QLabel("Impresora Windows:")
        form.addRow(self.driver_row_label, self.driver_combo)

        # --- Campos RED ---
        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("ej: 192.168.1.50")
        self.host_row_label = QLabel("IP de la impresora:")
        form.addRow(self.host_row_label, self.host_edit)

        self.tcp_port_spin = QSpinBox()
        self.tcp_port_spin.setRange(1, 65535)
        self.tcp_port_spin.setValue(9100)
        self.tcp_row_label = QLabel("Puerto TCP:")
        form.addRow(self.tcp_row_label, self.tcp_port_spin)

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(8072)
        form.addRow("Puerto local (proxy):", self.port_spin)

        self.paper_combo = QComboBox()
        for label in PAPER_WIDTHS.keys():
            self.paper_combo.addItem(label)
        form.addRow("Ancho de papel:", self.paper_combo)

        self.role_combo = QComboBox()
        for r in ["receipt", "kitchen", "bar", "both"]:
            self.role_combo.addItem(r)
        form.addRow("Rol:", self.role_combo)

        root.addLayout(form)

        hint = QLabel(
            "El rol es solo una etiqueta informativa; la asignacion real de "
            "productos a impresoras se hace en Odoo por categoria."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        root.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setObjectName("Primary")
        buttons.button(QDialogButtonBox.Save).setText("Guardar")
        buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        self.test_btn = QPushButton("Imprimir prueba")
        self.test_btn.clicked.connect(self._test_print)
        buttons.addButton(self.test_btn, QDialogButtonBox.ActionRole)
        root.addWidget(buttons)

        # Estado inicial de visibilidad segun conexion
        self._on_conn_changed()

    def _on_conn_changed(self) -> None:
        """Muestra los campos USB o RED segun el tipo de conexion elegido."""
        is_network = self._current_connection() == "network"
        for w in (self.host_row_label, self.host_edit,
                  self.tcp_row_label, self.tcp_port_spin):
            w.setVisible(is_network)
        for w in (self.driver_row_label, self.driver_combo):
            w.setVisible(not is_network)

    def _current_connection(self) -> str:
        return CONNECTIONS.get(self.conn_combo.currentText(), "usb")

    def _load(self, p: PrinterConfig) -> None:
        self.name_edit.setText(p.name)
        self.conn_combo.setCurrentText(_CONN_LABEL.get(p.connection, list(CONNECTIONS)[0]))
        idx = self.driver_combo.findText(p.windows_printer)
        if idx >= 0:
            self.driver_combo.setCurrentIndex(idx)
        else:
            self.driver_combo.setEditText(p.windows_printer)
        self.host_edit.setText(p.host)
        self.tcp_port_spin.setValue(p.tcp_port)
        self.port_spin.setValue(p.port)
        # Paper width
        for lbl, w in PAPER_WIDTHS.items():
            if w == p.paper_width:
                self.paper_combo.setCurrentText(lbl)
                break
        idx = self.role_combo.findText(p.role)
        if idx >= 0:
            self.role_combo.setCurrentIndex(idx)
        self._on_conn_changed()

    def _suggest_defaults(self) -> None:
        # Sugerir puerto libre siguiente
        used = self.used_ports
        port = 8072
        while port in used:
            port += 1
        self.port_spin.setValue(port)

    def _collect(self) -> Optional[PrinterConfig]:
        """Valida y construye un PrinterConfig, o None si hay error (ya avisado)."""
        name = self.name_edit.text().strip()
        connection = self._current_connection()
        driver = self.driver_combo.currentText().strip()
        host = self.host_edit.text().strip()
        tcp_port = self.tcp_port_spin.value()
        port = self.port_spin.value()
        paper_width = PAPER_WIDTHS.get(self.paper_combo.currentText(), 576)
        role = self.role_combo.currentText()

        if not name:
            QMessageBox.warning(self, "Datos incompletos", "El nombre no puede estar vacio.")
            return None
        if connection == "usb" and not driver:
            QMessageBox.warning(self, "Datos incompletos",
                                "Selecciona o escribe el nombre de la impresora Windows.")
            return None
        if connection == "network" and not host:
            QMessageBox.warning(self, "Datos incompletos",
                                "Escribe la IP de la impresora de red.")
            return None
        if port != self.original_port and port in self.used_ports:
            QMessageBox.warning(self, "Puerto en uso",
                                f"El puerto {port} ya esta asignado a otra impresora.")
            return None
        if name != self.original_name and name in self.used_names:
            QMessageBox.warning(self, "Nombre duplicado",
                                f"Ya existe una impresora llamada '{name}'.")
            return None
        if role not in VALID_ROLES:
            QMessageBox.warning(self, "Rol invalido", f"Rol '{role}' no reconocido.")
            return None

        try:
            return PrinterConfig(
                name=name,
                port=port,
                windows_printer=driver,
                paper_width=paper_width,
                role=role,
                connection=connection,
                host=host,
                tcp_port=tcp_port,
            )
        except ValueError as e:
            QMessageBox.warning(self, "Configuracion invalida", str(e))
            return None

    def _accept(self) -> None:
        result = self._collect()
        if result is None:
            return
        self._result = result
        self.accept()

    def _test_print(self) -> None:
        """Imprime un ticket de prueba con la config actual del formulario."""
        cfg = self._collect()
        if cfg is None:
            return
        from ...daemon.printer_backend import print_test_network, print_test_win32

        try:
            if cfg.connection == "network":
                from ...daemon.printer_backend import probe_network_printer
                if not probe_network_printer(cfg.host, cfg.tcp_port):
                    QMessageBox.warning(
                        self, "Sin conexion",
                        f"No responde {cfg.host}:{cfg.tcp_port}. Verifica IP, "
                        f"cable de red y que la impresora este encendida.",
                    )
                    return
                print_test_network(cfg.host, cfg.tcp_port)
            else:
                print_test_win32(cfg.windows_printer)
        except Exception as e:
            QMessageBox.critical(self, "Error al imprimir prueba", str(e))
            return
        QMessageBox.information(
            self, "Prueba enviada",
            "Se envio el ticket de prueba. Revisa la impresora.",
        )

    def result_printer(self) -> PrinterConfig:
        return self._result
