"""
Carga y valida config.yaml.

Soporta dos formatos:

FORMATO NUEVO (recomendado, multi-impresora):
    odoo_domain: "https://midominio.com"
    printers:
      - name: "Caja"
        port: 8072
        windows_printer: "POS-80"
        paper_width: 576
        role: receipt
      - name: "Cocina"
        port: 8073
        windows_printer: "KITCHEN-80"
        paper_width: 576
        role: kitchen

FORMATO LEGACY (una sola impresora, retrocompat automatica):
    odoo_domain: "https://midominio.com"
    port: 8072
    printer_name: "POS-80"
    paper_width: 576
    # Opcional segunda impresora:
    kitchen_printer_name: "KITCHEN-80"
    kitchen_port: 8073

Al leer el legacy, se convierte internamente al esquema nuevo. El usuario no
tiene que migrar su config.yaml antiguo; sigue funcionando como antes.
"""
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml


VALID_ROLES = {"receipt", "kitchen", "bar", "both"}


@dataclass
class PrinterConfig:
    """Configuracion de una impresora individual."""
    name: str
    port: int
    windows_printer: str
    paper_width: int = 576
    role: str = "both"

    def __post_init__(self):
        if not isinstance(self.port, int) or not (1 <= self.port <= 65535):
            raise ValueError(
                f"Puerto invalido en impresora '{self.name}': {self.port} "
                f"(debe ser entero entre 1 y 65535)"
            )
        if not self.windows_printer:
            raise ValueError(
                f"Impresora '{self.name}' no tiene 'windows_printer' configurado"
            )
        if self.role not in VALID_ROLES:
            # Warning, no error: el role es informativo, no bloqueante
            print(
                f"WARN: role '{self.role}' no reconocido en impresora "
                f"'{self.name}' (validos: {sorted(VALID_ROLES)}). "
                f"Se acepta pero es solo etiqueta informativa."
            )


@dataclass
class AppConfig:
    """Configuracion global de la app."""
    odoo_domain: str
    printers: list[PrinterConfig] = field(default_factory=list)
    verbose: bool = False
    log_dir: str = "logs"
    log_retention_days: int = 30
    kill_zombies_on_startup: bool = True

    @property
    def allowed_origin(self) -> str:
        """Origen permitido para CORS (dominio Odoo sin barra final)."""
        return self.odoo_domain.rstrip("/")


def load_config(path: Path) -> AppConfig:
    """Lee, valida y retorna la configuracion. Sale con exit(1) si falla."""
    if not path.exists():
        print(f"ERROR: No se encontro {path}")
        print("Verifica que config.yaml exista en la misma carpeta que main.py")
        sys.exit(1)

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        print(f"ERROR: config.yaml tiene sintaxis YAML invalida: {e}")
        sys.exit(1)

    try:
        return _parse(raw)
    except (ValueError, KeyError, TypeError) as e:
        print(f"ERROR: config.yaml es invalido: {e}")
        sys.exit(1)


def _parse(raw: dict) -> AppConfig:
    odoo_domain = raw.get("odoo_domain", "https://tudominio.com")
    verbose = bool(raw.get("verbose", False))
    log_dir = raw.get("log_dir", "logs")
    log_retention_days = int(raw.get("log_retention_days", 30))
    kill_zombies = bool(raw.get("kill_zombies_on_startup", True))

    # Detectar formato: nuevo (con 'printers') o legacy
    printers_raw = raw.get("printers")

    if printers_raw is not None:
        if not isinstance(printers_raw, list):
            raise ValueError("'printers' debe ser una lista")
        printers = [_parse_printer(p) for p in printers_raw]
    else:
        # Formato legacy: printer_name en el top-level
        printers = _parse_legacy(raw)

    if not printers:
        raise ValueError(
            "No hay ninguna impresora configurada. Agrega al menos una entrada "
            "en 'printers:' o define 'printer_name:' en el formato legacy."
        )

    # Validar puertos unicos
    ports = [p.port for p in printers]
    if len(set(ports)) != len(ports):
        raise ValueError(
            f"Hay puertos duplicados en la configuracion de impresoras: {ports}. "
            f"Cada impresora debe tener un puerto distinto."
        )

    # Validar nombres unicos
    names = [p.name for p in printers]
    if len(set(names)) != len(names):
        raise ValueError(
            f"Hay nombres duplicados en la configuracion de impresoras: {names}"
        )

    return AppConfig(
        odoo_domain=odoo_domain,
        printers=printers,
        verbose=verbose,
        log_dir=log_dir,
        log_retention_days=log_retention_days,
        kill_zombies_on_startup=kill_zombies,
    )


def _parse_printer(raw: dict) -> PrinterConfig:
    """Convierte una entrada del formato nuevo a PrinterConfig."""
    if not isinstance(raw, dict):
        raise ValueError(f"Cada impresora debe ser un mapeo/dict, no {type(raw).__name__}")

    return PrinterConfig(
        name=str(raw.get("name") or raw.get("windows_printer") or "Sin nombre"),
        port=int(raw.get("port", 8072)),
        windows_printer=str(raw.get("windows_printer") or raw.get("printer_name") or ""),
        paper_width=int(raw.get("paper_width", 576)),
        role=str(raw.get("role", "both")),
    )


def _parse_legacy(raw: dict) -> list[PrinterConfig]:
    """
    Convierte el formato viejo (una impresora en el top-level, con opcional
    kitchen_printer_name) al esquema nuevo.
    """
    printers: list[PrinterConfig] = []

    # Impresora principal (recibos)
    if raw.get("printer_name"):
        printers.append(PrinterConfig(
            name=str(raw["printer_name"]),
            port=int(raw.get("port", 8072)),
            windows_printer=str(raw["printer_name"]),
            paper_width=int(raw.get("paper_width", 576)),
            role="both",  # legacy default: la misma impresora sirve para todo
        ))

    # Segunda impresora opcional (cocina)
    if raw.get("kitchen_printer_name"):
        printers.append(PrinterConfig(
            name=str(raw["kitchen_printer_name"]),
            port=int(raw.get("kitchen_port", 8073)),
            windows_printer=str(raw["kitchen_printer_name"]),
            paper_width=int(raw.get("paper_width", 576)),
            role="kitchen",
        ))

    return printers
