"""Vista Sistema: auto-inicio, verbose, retencion, updates, abrir logs."""
import logging
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ... import __version__
from ...util import autostart
from ...util.paths import logs_dir, app_data_dir, debug_dir
from ..controllers.config_ctrl import ConfigController
from ..controllers.update_ctrl import UpdateController, UpdateInfo


logger = logging.getLogger("pos_print_proxy.gui.system")


class SystemView(QWidget):

    def __init__(
        self,
        config_ctrl: ConfigController,
        update_ctrl: UpdateController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config_ctrl = config_ctrl
        self.update_ctrl = update_ctrl
        self._build_ui()
        self._connect()
        self._load()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(16)

        title = QLabel("Sistema")
        title.setObjectName("H1")
        root.addWidget(title)

        # --- Auto-inicio ---
        auto_box = QGroupBox("Inicio con Windows")
        auto_layout = QVBoxLayout(auto_box)
        auto_layout.setContentsMargins(20, 22, 20, 20)
        auto_layout.setSpacing(10)

        self.autostart_check = QCheckBox("Iniciar POS Print Proxy al iniciar sesion en Windows")
        auto_layout.addWidget(self.autostart_check)

        self.autostart_minimized = QCheckBox("Iniciar minimizado en la bandeja del sistema")
        auto_layout.addWidget(self.autostart_minimized)

        note = QLabel("Se activa via HKCU (no requiere permisos de administrador).")
        note.setObjectName("Muted")
        auto_layout.addWidget(note)

        root.addWidget(auto_box)

        # --- Diagnostico / logs ---
        log_box = QGroupBox("Logs y diagnostico")
        log_layout = QVBoxLayout(log_box)
        log_layout.setContentsMargins(20, 22, 20, 20)
        log_layout.setSpacing(10)

        self.verbose_check = QCheckBox("Logs verbosos (incluye keep-alive de status_json)")
        log_layout.addWidget(self.verbose_check)

        retention_row = QHBoxLayout()
        retention_row.addWidget(QLabel("Retencion de archivos rotados (dias):"))
        self.retention_spin = QSpinBox()
        self.retention_spin.setRange(1, 365)
        self.retention_spin.setValue(30)
        retention_row.addWidget(self.retention_spin)
        retention_row.addStretch(1)
        log_layout.addLayout(retention_row)

        buttons = QHBoxLayout()
        self.btn_open_logs = QPushButton("Abrir carpeta de logs")
        self.btn_open_data = QPushButton("Abrir carpeta de datos")
        self.btn_save_log_settings = QPushButton("Guardar cambios")
        self.btn_save_log_settings.setObjectName("Primary")
        buttons.addWidget(self.btn_open_logs)
        buttons.addWidget(self.btn_open_data)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_save_log_settings)
        log_layout.addLayout(buttons)

        root.addWidget(log_box)

        # --- Diagnostico avanzado (debug) ---
        debug_box = QGroupBox("Diagnostico avanzado")
        debug_layout = QVBoxLayout(debug_box)
        debug_layout.setContentsMargins(20, 22, 20, 20)
        debug_layout.setSpacing(10)

        self.debug_check = QCheckBox(
            "Guardar cada impresion como archivo (para diagnostico)"
        )
        debug_layout.addWidget(self.debug_check)

        debug_hint = QLabel(
            "Cuando esta activo, el proxy guarda una copia de cada JPEG que "
            "llega en la carpeta debug junto a un JSON con metadata. Sirve "
            "para verificar exactamente que imagen envio Odoo cuando hay "
            "un problema. Los archivos ocupan disco hasta que los borres "
            "manualmente. Solo actives esto durante un diagnostico."
        )
        debug_hint.setObjectName("Muted")
        debug_hint.setWordWrap(True)
        debug_layout.addWidget(debug_hint)

        debug_buttons = QHBoxLayout()
        self.btn_open_debug = QPushButton("Abrir carpeta debug")
        self.btn_save_debug = QPushButton("Guardar cambio")
        self.btn_save_debug.setObjectName("Primary")
        debug_buttons.addWidget(self.btn_open_debug)
        debug_buttons.addStretch(1)
        debug_buttons.addWidget(self.btn_save_debug)
        debug_layout.addLayout(debug_buttons)

        root.addWidget(debug_box)

        # --- Actualizaciones ---
        upd_box = QGroupBox("Actualizaciones")
        upd_layout = QVBoxLayout(upd_box)
        upd_layout.setContentsMargins(20, 22, 20, 20)
        upd_layout.setSpacing(10)

        self.version_label = QLabel(f"Version actual: v{__version__}")
        self.version_label.setObjectName("H2")
        upd_layout.addWidget(self.version_label)

        self.update_status_label = QLabel("Consultando...")
        self.update_status_label.setObjectName("Muted")
        self.update_status_label.setWordWrap(True)
        upd_layout.addWidget(self.update_status_label)

        upd_buttons = QHBoxLayout()
        self.btn_check_now = QPushButton("Buscar ahora")
        self.btn_open_release = QPushButton("Abrir release")
        self.btn_open_release.setEnabled(False)
        upd_buttons.addWidget(self.btn_check_now)
        upd_buttons.addWidget(self.btn_open_release)
        upd_buttons.addStretch(1)
        upd_layout.addLayout(upd_buttons)

        root.addWidget(upd_box)
        root.addStretch(1)

    def _connect(self) -> None:
        self.autostart_check.toggled.connect(self._on_autostart_toggled)
        self.autostart_minimized.toggled.connect(self._on_autostart_toggled)
        self.btn_open_logs.clicked.connect(lambda: self._open_folder(logs_dir()))
        self.btn_open_data.clicked.connect(lambda: self._open_folder(app_data_dir()))
        self.btn_save_log_settings.clicked.connect(self._save_log_settings)
        self.btn_open_debug.clicked.connect(lambda: self._open_folder(debug_dir()))
        self.btn_save_debug.clicked.connect(self._save_debug_setting)
        self.btn_check_now.clicked.connect(self.update_ctrl.check_now)
        self.btn_open_release.clicked.connect(self._open_release)
        self.update_ctrl.check_finished.connect(self._render_update_info)

    # --- Load / render ---

    def _load(self) -> None:
        cfg = self.config_ctrl.current()
        self.verbose_check.setChecked(cfg.verbose)
        self.retention_spin.setValue(cfg.log_retention_days)
        self.debug_check.setChecked(cfg.debug_save_prints)

        cmd = autostart.current_command()
        self.autostart_check.setChecked(cmd is not None and cmd != "")
        self.autostart_minimized.setChecked(cmd is not None and "--minimized" in cmd)

    def _render_update_info(self, info: UpdateInfo) -> None:
        if info.error:
            self.update_status_label.setText(f"No se pudo consultar: {info.error}")
            self.btn_open_release.setEnabled(False)
        elif info.available:
            self.update_status_label.setText(
                f"Hay una version nueva: v{info.latest_version}. "
                f"Estas ejecutando v{info.current_version}."
            )
            self._release_url = info.download_url
            self.btn_open_release.setEnabled(bool(info.download_url))
        else:
            self.update_status_label.setText(f"Estas en la ultima version (v{info.current_version}).")
            self.btn_open_release.setEnabled(False)

    # --- Handlers ---

    def _on_autostart_toggled(self, *_) -> None:
        # No aplicar cambio inmediatamente si estan en checkboxes distintos:
        # aplicamos cuando ambos estan estables al guardar. Pero como es
        # toggle inmediato y no hay boton "guardar autostart", persistimos.
        enabled = self.autostart_check.isChecked()
        minimized = self.autostart_minimized.isChecked()
        if enabled:
            ok = autostart.enable(minimized=minimized)
            if not ok:
                QMessageBox.warning(
                    self, "Auto-inicio",
                    "No se pudo activar el auto-inicio (revisa el registro de Windows)."
                )
        else:
            autostart.disable()
            self.autostart_minimized.setEnabled(False)
        # Sincronizar el "minimized" a solo estar habilitado si autostart esta ON
        self.autostart_minimized.setEnabled(enabled)

    def _save_log_settings(self) -> None:
        cfg = self.config_ctrl.current()
        from ...daemon.config_manager import AppConfig
        new_cfg = AppConfig(
            odoo_domain=cfg.odoo_domain,
            printers=list(cfg.printers),
            verbose=self.verbose_check.isChecked(),
            log_dir=cfg.log_dir,
            log_retention_days=self.retention_spin.value(),
            kill_zombies_on_startup=cfg.kill_zombies_on_startup,
            debug_save_prints=cfg.debug_save_prints,
        )
        if self.config_ctrl.update(new_cfg):
            QMessageBox.information(
                self, "Ajustes guardados",
                "Los cambios se aplicaran al reiniciar el daemon.",
            )

    def _save_debug_setting(self) -> None:
        """Guarda el toggle de debug. El cambio se aplica EN CALIENTE
        (sin reiniciar el daemon) porque el handler lee el flag en cada request.
        """
        enabled = self.debug_check.isChecked()
        new_cfg = self.config_ctrl.with_debug(enabled)
        if self.config_ctrl.update(new_cfg):
            msg = (
                "Modo debug activado. Cada impresion se guardara en la carpeta debug."
                if enabled
                else "Modo debug desactivado. No se guardaran mas archivos."
            )
            QMessageBox.information(self, "Debug", msg)

    def _open_folder(self, path: Path) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo abrir la carpeta: {e}")

    def _open_release(self) -> None:
        url = getattr(self, "_release_url", "")
        if not url:
            return
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))
