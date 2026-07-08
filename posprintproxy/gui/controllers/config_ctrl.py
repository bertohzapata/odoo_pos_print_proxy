"""
Controlador de la configuracion. Encapsula lectura, escritura y validacion
del config.yaml. Emite senial cuando cambia para que la GUI se refresque.
"""
import logging
from pathlib import Path
from typing import Optional

import yaml
from PySide6.QtCore import QObject, Signal

from ...daemon.config_manager import AppConfig, PrinterConfig, load_config


logger = logging.getLogger("pos_print_proxy.gui.config")


class ConfigController(QObject):
    """Gestor de la configuracion editable en tiempo real."""

    config_changed = Signal(object)  # nueva AppConfig
    save_failed = Signal(str)        # mensaje de error

    def __init__(self, config_path: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.config_path = config_path
        self._config: Optional[AppConfig] = None

    def load(self) -> AppConfig:
        """Carga la config del disco. Si no existe, crea una por defecto."""
        if not self.config_path.exists():
            self._create_default()
        self._config = load_config(self.config_path)
        return self._config

    def current(self) -> AppConfig:
        if self._config is None:
            return self.load()
        return self._config

    def update(self, new_config: AppConfig) -> bool:
        """Persiste la nueva config a disco y notifica."""
        try:
            self._write(new_config)
            self._config = new_config
            self.config_changed.emit(new_config)
            return True
        except Exception as e:
            logger.exception("Error escribiendo config.yaml")
            self.save_failed.emit(str(e))
            return False

    # --- Escritura ---

    def _create_default(self) -> None:
        """Crea un config.yaml minimal para primera ejecucion."""
        default = {
            "odoo_domain": "https://tudominio.com",
            "verbose": False,
            "log_dir": "logs",
            "log_retention_days": 30,
            "kill_zombies_on_startup": True,
            "printers": [
                {
                    "name": "Caja",
                    "port": 8072,
                    "windows_printer": "POS-80",
                    "paper_width": 576,
                    "role": "both",
                }
            ],
        }
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(default, f, sort_keys=False, allow_unicode=True)

    def _write(self, config: AppConfig) -> None:
        data = {
            "odoo_domain": config.odoo_domain,
            "verbose": config.verbose,
            "log_dir": config.log_dir,
            "log_retention_days": config.log_retention_days,
            "kill_zombies_on_startup": config.kill_zombies_on_startup,
            "printers": [
                {
                    "name": p.name,
                    "port": p.port,
                    "windows_printer": p.windows_printer,
                    "paper_width": p.paper_width,
                    "role": p.role,
                }
                for p in config.printers
            ],
        }
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        # Escribir a archivo temporal y renombrar (atomico en Windows y Linux)
        tmp = self.config_path.with_suffix(".yaml.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
        tmp.replace(self.config_path)

    # --- Helpers de mutacion (para la UI) ---

    def with_odoo_domain(self, domain: str) -> AppConfig:
        cur = self.current()
        return AppConfig(
            odoo_domain=domain,
            printers=list(cur.printers),
            verbose=cur.verbose,
            log_dir=cur.log_dir,
            log_retention_days=cur.log_retention_days,
            kill_zombies_on_startup=cur.kill_zombies_on_startup,
        )

    def with_printers(self, printers: list[PrinterConfig]) -> AppConfig:
        cur = self.current()
        return AppConfig(
            odoo_domain=cur.odoo_domain,
            printers=printers,
            verbose=cur.verbose,
            log_dir=cur.log_dir,
            log_retention_days=cur.log_retention_days,
            kill_zombies_on_startup=cur.kill_zombies_on_startup,
        )

    def with_verbose(self, verbose: bool) -> AppConfig:
        cur = self.current()
        return AppConfig(
            odoo_domain=cur.odoo_domain,
            printers=list(cur.printers),
            verbose=verbose,
            log_dir=cur.log_dir,
            log_retention_days=cur.log_retention_days,
            kill_zombies_on_startup=cur.kill_zombies_on_startup,
        )
