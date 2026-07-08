"""Nucleo del proxy: FastAPI + orquestacion. Puede correr embebido o standalone."""

from .daemon import ProxyDaemon, DaemonStatus
from .config_manager import load_config, AppConfig, PrinterConfig

__all__ = ["ProxyDaemon", "DaemonStatus", "load_config", "AppConfig", "PrinterConfig"]
