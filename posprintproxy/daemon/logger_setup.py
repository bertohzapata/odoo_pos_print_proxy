"""
Setup del logging.

En v2.0 hay dos consumidores:
- Consola / archivo (como v1.4)
- La GUI de PySide6 (via un handler que emite QSignals)

Este modulo solo configura los handlers base. La GUI adjunta su propio
handler despues de que este setup termine.
"""
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


CONSOLE_FMT = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

FILE_FMT = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def setup_logging(
    log_dir: Path,
    retention_days: int = 30,
    verbose: bool = False,
    console: bool = True,
) -> logging.Logger:
    """
    Configura el logging global.

    Args:
        log_dir: carpeta para el archivo rotativo
        retention_days: cuantos dias mantener rotados
        verbose: si True baja el nivel a DEBUG
        console: si True agrega handler de consola (util cuando corres CLI;
            desactivar cuando corres como app GUI empaquetada sin ventana CMD)
    """
    level = logging.DEBUG if verbose else logging.INFO

    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        root.removeHandler(h)

    if console:
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(CONSOLE_FMT)
        root.addHandler(ch)

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = TimedRotatingFileHandler(
            log_dir / "proxy.log",
            when="midnight",
            backupCount=retention_days,
            encoding="utf-8",
        )
        fh.setLevel(level)
        fh.setFormatter(FILE_FMT)
        root.addHandler(fh)
    except Exception as e:
        # No bloqueamos el arranque por permisos/disco. Aviso una vez.
        print(f"WARN: no se pudo abrir el log a archivo ({log_dir}): {e}")

    # Silenciar loggers ruidosos de terceros
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)

    return logging.getLogger("pos_print_proxy")
