"""Vista de gestion de impresoras: tabla + CRUD + guardado en config.yaml."""
import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...daemon.config_manager import PrinterConfig
from ...daemon.printer_backend import list_printers
from ..controllers.config_ctrl import ConfigController
from ..controllers.daemon_ctrl import DaemonController
from ..dialogs.printer_dialog import PrinterDialog


logger = logging.getLogger("pos_print_proxy.gui.printers")


class PrintersView(QWidget):

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
        self._load_from_config()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(14)

        title = QLabel("Impresoras")
        title.setObjectName("H1")
        root.addWidget(title)

        subtitle = QLabel(
            "Cada impresora escucha en su propio puerto. En Odoo configura los "
            "pos.printer records apuntando a localhost:PUERTO."
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        # --- Dominio Odoo ---
        domain_row = QHBoxLayout()
        domain_row.setSpacing(10)
        lbl = QLabel("Dominio Odoo permitido:")
        lbl.setObjectName("Muted")
        self.domain_edit = QLineEdit()
        self.domain_edit.setPlaceholderText("https://midominio.com")
        self.btn_save_domain = QPushButton("Guardar dominio")
        self.btn_save_domain.setObjectName("Primary")
        domain_row.addWidget(lbl)
        domain_row.addWidget(self.domain_edit, 1)
        domain_row.addWidget(self.btn_save_domain)
        root.addLayout(domain_row)

        # --- Tabla ---
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            "Nombre", "Puerto", "Impresora Windows", "Ancho", "Rol",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setMinimumHeight(260)
        root.addWidget(self.table, 1)

        # --- Botones CRUD ---
        crud = QHBoxLayout()
        self.btn_add = QPushButton("Agregar impresora")
        self.btn_add.setObjectName("Primary")
        self.btn_edit = QPushButton("Editar")
        self.btn_delete = QPushButton("Eliminar")
        self.btn_delete.setObjectName("Danger")
        crud.addWidget(self.btn_add)
        crud.addWidget(self.btn_edit)
        crud.addWidget(self.btn_delete)
        crud.addStretch(1)
        root.addLayout(crud)

        # --- Nota final ---
        note = QLabel(
            "Los cambios en impresoras requieren reiniciar el daemon para tomar efecto."
        )
        note.setObjectName("Muted")
        root.addWidget(note)

    def _connect(self) -> None:
        self.btn_save_domain.clicked.connect(self._save_domain)
        self.btn_add.clicked.connect(self._add_printer)
        self.btn_edit.clicked.connect(self._edit_printer)
        self.btn_delete.clicked.connect(self._delete_printer)
        self.table.doubleClicked.connect(lambda _: self._edit_printer())
        self.config_ctrl.config_changed.connect(lambda _: self._load_from_config())

    # --- Carga y render ---

    def _load_from_config(self) -> None:
        cfg = self.config_ctrl.current()
        self.domain_edit.setText(cfg.odoo_domain)

        self.table.setRowCount(len(cfg.printers))
        for row, p in enumerate(cfg.printers):
            self._fill_row(row, p)

    def _fill_row(self, row: int, p: PrinterConfig) -> None:
        self.table.setItem(row, 0, QTableWidgetItem(p.name))
        self.table.setItem(row, 1, QTableWidgetItem(str(p.port)))
        self.table.setItem(row, 2, QTableWidgetItem(p.windows_printer))
        width_label = "80mm" if p.paper_width == 576 else "58mm" if p.paper_width == 384 else f"{p.paper_width}px"
        self.table.setItem(row, 3, QTableWidgetItem(width_label))
        self.table.setItem(row, 4, QTableWidgetItem(p.role))

    def _current_printer_index(self) -> int:
        row = self.table.currentRow()
        cfg = self.config_ctrl.current()
        if 0 <= row < len(cfg.printers):
            return row
        return -1

    # --- Acciones ---

    def _save_domain(self) -> None:
        domain = self.domain_edit.text().strip()
        if not domain:
            QMessageBox.warning(self, "Dominio invalido", "El dominio no puede estar vacio.")
            return
        new_cfg = self.config_ctrl.with_odoo_domain(domain)
        if self.config_ctrl.update(new_cfg):
            self._toast_restart_required()

    def _add_printer(self) -> None:
        cfg = self.config_ctrl.current()
        try:
            detected = list_printers()
        except Exception:
            detected = []
        dlg = PrinterDialog(
            printer=None,
            used_ports=[p.port for p in cfg.printers],
            used_names=[p.name for p in cfg.printers],
            detected_printers=detected,
            parent=self,
        )
        if dlg.exec():
            new_printer = dlg.result_printer()
            new_list = list(cfg.printers) + [new_printer]
            self.config_ctrl.update(self.config_ctrl.with_printers(new_list))
            self._toast_restart_required()

    def _edit_printer(self) -> None:
        idx = self._current_printer_index()
        if idx < 0:
            QMessageBox.information(self, "Selecciona una impresora", "Elige una fila de la tabla para editar.")
            return
        cfg = self.config_ctrl.current()
        try:
            detected = list_printers()
        except Exception:
            detected = []

        target = cfg.printers[idx]
        used_ports = [p.port for i, p in enumerate(cfg.printers) if i != idx]
        used_names = [p.name for i, p in enumerate(cfg.printers) if i != idx]

        dlg = PrinterDialog(
            printer=target,
            used_ports=used_ports,
            used_names=used_names,
            detected_printers=detected,
            parent=self,
        )
        if dlg.exec():
            edited = dlg.result_printer()
            new_list = list(cfg.printers)
            new_list[idx] = edited
            self.config_ctrl.update(self.config_ctrl.with_printers(new_list))
            self._toast_restart_required()

    def _delete_printer(self) -> None:
        idx = self._current_printer_index()
        if idx < 0:
            QMessageBox.information(self, "Selecciona una impresora", "Elige una fila de la tabla para eliminar.")
            return
        cfg = self.config_ctrl.current()
        if len(cfg.printers) <= 1:
            QMessageBox.warning(
                self, "No se puede eliminar",
                "Debe haber al menos una impresora configurada.",
            )
            return
        target = cfg.printers[idx]
        answer = QMessageBox.question(
            self, "Eliminar impresora",
            f"¿Eliminar la impresora '{target.name}' del puerto {target.port}?",
        )
        if answer != QMessageBox.Yes:
            return

        new_list = [p for i, p in enumerate(cfg.printers) if i != idx]
        self.config_ctrl.update(self.config_ctrl.with_printers(new_list))
        self._toast_restart_required()

    def _toast_restart_required(self) -> None:
        # Si el daemon esta corriendo, avisar. Si no, no molesta.
        if self.daemon_ctrl.snapshot().status.name == "RUNNING":
            QMessageBox.information(
                self, "Cambios guardados",
                "La configuracion se guardo. Reinicia el daemon desde el Dashboard "
                "para aplicar los cambios."
            )
