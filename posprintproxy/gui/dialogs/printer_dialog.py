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
    QSpinBox,
    QVBoxLayout,
)

from ...daemon.config_manager import PrinterConfig, VALID_ROLES


PAPER_WIDTHS = {
    "80mm (576px)": 576,
    "58mm (384px)": 384,
}


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

        self.driver_combo = QComboBox()
        self.driver_combo.setEditable(True)
        if detected:
            self.driver_combo.addItems(detected)
        self.driver_combo.setPlaceholderText("ej: POS-80")
        form.addRow("Impresora Windows:", self.driver_combo)

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(8072)
        form.addRow("Puerto:", self.port_spin)

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
        root.addWidget(buttons)

    def _load(self, p: PrinterConfig) -> None:
        self.name_edit.setText(p.name)
        idx = self.driver_combo.findText(p.windows_printer)
        if idx >= 0:
            self.driver_combo.setCurrentIndex(idx)
        else:
            self.driver_combo.setEditText(p.windows_printer)
        self.port_spin.setValue(p.port)
        # Paper width
        for lbl, w in PAPER_WIDTHS.items():
            if w == p.paper_width:
                self.paper_combo.setCurrentText(lbl)
                break
        idx = self.role_combo.findText(p.role)
        if idx >= 0:
            self.role_combo.setCurrentIndex(idx)

    def _suggest_defaults(self) -> None:
        # Sugerir puerto libre siguiente
        used = self.used_ports
        port = 8072
        while port in used:
            port += 1
        self.port_spin.setValue(port)

    def _accept(self) -> None:
        name = self.name_edit.text().strip()
        driver = self.driver_combo.currentText().strip()
        port = self.port_spin.value()
        paper_width = PAPER_WIDTHS.get(self.paper_combo.currentText(), 576)
        role = self.role_combo.currentText()

        # Validaciones
        if not name:
            QMessageBox.warning(self, "Datos incompletos", "El nombre no puede estar vacio.")
            return
        if not driver:
            QMessageBox.warning(self, "Datos incompletos", "Selecciona o escribe el nombre de la impresora Windows.")
            return
        if port != self.original_port and port in self.used_ports:
            QMessageBox.warning(self, "Puerto en uso", f"El puerto {port} ya esta asignado a otra impresora.")
            return
        if name != self.original_name and name in self.used_names:
            QMessageBox.warning(self, "Nombre duplicado", f"Ya existe una impresora llamada '{name}'.")
            return
        if role not in VALID_ROLES:
            QMessageBox.warning(self, "Rol invalido", f"Rol '{role}' no reconocido.")
            return

        try:
            self._result = PrinterConfig(
                name=name,
                port=port,
                windows_printer=driver,
                paper_width=paper_width,
                role=role,
            )
        except ValueError as e:
            QMessageBox.warning(self, "Configuracion invalida", str(e))
            return

        self.accept()

    def result_printer(self) -> PrinterConfig:
        return self._result
