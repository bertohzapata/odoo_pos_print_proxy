"""
Vista de logs en tiempo real. Ring buffer para que la memoria no explote,
autoscroll opcional, filtro por nivel, boton para exportar y limpiar.
"""
import logging
from collections import deque
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


LEVEL_COLORS = {
    logging.DEBUG: QColor("#7c8593"),
    logging.INFO: QColor("#c8d0da"),
    logging.WARNING: QColor("#e0b04d"),
    logging.ERROR: QColor("#e57171"),
    logging.CRITICAL: QColor("#ff5c5c"),
}

LEVEL_NAMES = {
    "Todos": 0,
    "Solo INFO+": logging.INFO,
    "Solo WARN+": logging.WARNING,
    "Solo ERROR": logging.ERROR,
}


class LogsView(QWidget):
    """Consumidor del QtLogBridge para pintar logs en tiempo real."""

    MAX_LINES = 2000

    def __init__(self, log_bridge, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.log_bridge = log_bridge
        self._buffer: deque = deque(maxlen=self.MAX_LINES)
        self._level_filter = 0
        self._autoscroll = True

        self._build_ui()
        self._connect()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(12)

        title = QLabel("Logs")
        title.setObjectName("H1")
        root.addWidget(title)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        toolbar.addWidget(QLabel("Filtro:"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(list(LEVEL_NAMES.keys()))
        toolbar.addWidget(self.level_combo)

        self.autoscroll_chk = QCheckBox("Auto-scroll")
        self.autoscroll_chk.setChecked(True)
        toolbar.addWidget(self.autoscroll_chk)

        toolbar.addStretch(1)

        self.btn_clear = QPushButton("Limpiar")
        self.btn_clear.setObjectName("Ghost")
        self.btn_export = QPushButton("Exportar")
        toolbar.addWidget(self.btn_clear)
        toolbar.addWidget(self.btn_export)
        root.addLayout(toolbar)

        # Log view
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("LogView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(self.MAX_LINES)
        root.addWidget(self.log_view, 1)

        # Contador de lineas
        self.status_label = QLabel("0 lineas")
        self.status_label.setObjectName("Muted")
        root.addWidget(self.status_label)

    def _connect(self) -> None:
        self.log_bridge.line.connect(self._on_log_line)
        self.level_combo.currentTextChanged.connect(self._on_filter_change)
        self.autoscroll_chk.toggled.connect(self._on_autoscroll)
        self.btn_clear.clicked.connect(self._clear)
        self.btn_export.clicked.connect(self._export)

    # --- Handlers ---

    def _on_log_line(self, msg: str, level: int) -> None:
        self._buffer.append((msg, level))
        if level >= self._level_filter:
            self._append(msg, level)

    def _on_filter_change(self, text: str) -> None:
        self._level_filter = LEVEL_NAMES.get(text, 0)
        # Repintar todo con el filtro nuevo
        self.log_view.clear()
        for msg, level in self._buffer:
            if level >= self._level_filter:
                self._append(msg, level, defer_scroll=True)
        if self._autoscroll:
            self._scroll_to_bottom()

    def _on_autoscroll(self, checked: bool) -> None:
        self._autoscroll = checked
        if checked:
            self._scroll_to_bottom()

    def _clear(self) -> None:
        answer = QMessageBox.question(
            self, "Limpiar logs",
            "¿Vaciar el visor de logs? El archivo persistente en disco no se ve afectado.",
        )
        if answer == QMessageBox.Yes:
            self._buffer.clear()
            self.log_view.clear()
            self._update_status()

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar logs",
            "posprintproxy_logs.txt",
            "Texto (*.txt)",
        )
        if not path:
            return
        try:
            Path(path).write_text(
                "\n".join(msg for msg, _ in self._buffer),
                encoding="utf-8",
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo exportar: {e}")

    # --- Helpers ---

    def _append(self, msg: str, level: int, defer_scroll: bool = False) -> None:
        color = LEVEL_COLORS.get(level, QColor("#c8d0da"))
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        cursor.setCharFormat(fmt)
        cursor.insertText(msg + "\n")
        if self._autoscroll and not defer_scroll:
            self._scroll_to_bottom()
        self._update_status()

    def _scroll_to_bottom(self) -> None:
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _update_status(self) -> None:
        n = len(self._buffer)
        self.status_label.setText(
            f"{n} lineas (buffer max {self.MAX_LINES})"
        )
