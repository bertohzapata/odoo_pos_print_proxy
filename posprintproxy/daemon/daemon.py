"""
Clase ProxyDaemon: encapsula todo el runtime del proxy y expone start/stop
para que la GUI lo controle.

Contexto: en v1.4 el proxy era un `asyncio.run()` que ocupaba el hilo principal.
En v2.0 la GUI (PySide6) ocupa el hilo principal, y el daemon vive en un hilo
worker. Este modulo hace posible ese aislamiento.
"""
import asyncio
import logging
import socket
import ssl
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import uvicorn

from .config_manager import AppConfig
from .printer_manager import Printer, detect_or_warn
from .proxy_server import create_app


logger = logging.getLogger("pos_print_proxy.daemon")


# ============================================================================
# Estados del daemon
# ============================================================================

class DaemonStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class DaemonSnapshot:
    """Snapshot ligero del estado, para pintar en la GUI."""
    status: DaemonStatus = DaemonStatus.STOPPED
    running_ports: list[int] = field(default_factory=list)
    last_error: str = ""


# ============================================================================
# Utilidades de arranque
# ============================================================================

# En PyInstaller --windowed, cualquier subprocess.run sin este flag mostraria
# una ventana CMD parpadeando en la barra de tareas. CREATE_NO_WINDOW la oculta.
if sys.platform == "win32":
    _CREATE_NO_WINDOW = 0x08000000
    _WIN_SUBPROC = {"creationflags": _CREATE_NO_WINDOW}
else:
    _WIN_SUBPROC = {}


def kill_zombies_on_port(port: int) -> list[int]:
    """
    Mata cualquier proceso que este escuchando en el puerto dado.
    Retorna la lista de PIDs matados.
    """
    if sys.platform != "win32":
        return []

    # netstat con muchas conexiones puede tardar 8-12s en algunos Windows;
    # 30s da margen suficiente sin bloquear la GUI (corre en thread worker).
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=30,
            **_WIN_SUBPROC,
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"netstat tardo mas de 30s verificando puerto {port}; se salta la limpieza de zombies")
        return []
    except Exception as e:
        logger.warning(f"No se pudo ejecutar netstat para verificar puerto {port}: {e}")
        return []

    pids: set[str] = set()
    for line in result.stdout.splitlines():
        if f":{port} " in line and "LISTENING" in line:
            parts = line.split()
            if parts:
                pids.add(parts[-1])

    killed = []
    for pid in pids:
        try:
            r = subprocess.run(
                ["taskkill", "/F", "/PID", pid],
                capture_output=True, timeout=5,
                **_WIN_SUBPROC,
            )
            if r.returncode == 0:
                killed.append(int(pid))
        except Exception as e:
            logger.warning(f"No se pudo matar PID {pid}: {e}")

    if killed:
        time.sleep(2)  # dar tiempo al SO a liberar el socket

    return killed


def self_test_cert(cert_path: Path, key_path: Path) -> tuple[bool, str]:
    """Retorna (ok, mensaje). ok=False si el cert no carga."""
    if not (cert_path.exists() and key_path.exists()):
        return False, "No hay archivos de certificado"
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
        return True, ""
    except Exception as e:
        return False, str(e)


# ============================================================================
# El daemon
# ============================================================================

class ProxyDaemon:
    """
    Envuelve el runtime del proxy. Puede correr:
    - Embebido en la GUI (en un hilo aparte, controlado desde el main thread)
    - Standalone (via `posprintproxy.daemon.main`)
    """

    def __init__(
        self,
        config: AppConfig,
        cert_path: Path,
        key_path: Path,
    ):
        self.config = config
        self.cert_path = cert_path
        self.key_path = key_path

        self._status = DaemonStatus.STOPPED
        self._last_error = ""
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._servers: list[uvicorn.Server] = []
        self._status_lock = threading.Lock()

    # --- API publica ---

    def snapshot(self) -> DaemonSnapshot:
        with self._status_lock:
            return DaemonSnapshot(
                status=self._status,
                running_ports=[p.port for p in self.config.printers] if self._status == DaemonStatus.RUNNING else [],
                last_error=self._last_error,
            )

    def has_ssl(self) -> bool:
        return self.cert_path.exists() and self.key_path.exists()

    def is_running(self) -> bool:
        return self._status in (DaemonStatus.STARTING, DaemonStatus.RUNNING)

    def start(self) -> None:
        """Arranca el daemon en background. No bloquea la GUI."""
        if self.is_running():
            logger.info("start() ignorado: el daemon ya esta corriendo")
            return

        self._set_status(DaemonStatus.STARTING)
        self._last_error = ""

        # Nota: el kill de zombies se hace DENTRO del thread worker
        # (_run_thread) para que la GUI no se bloquee durante los ~15s
        # que puede tardar netstat con muchas conexiones abiertas.

        self._thread = threading.Thread(target=self._run_thread, name="ProxyDaemon", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Detiene el daemon. Espera hasta `timeout` segundos a que baje."""
        if not self.is_running():
            return

        self._set_status(DaemonStatus.STOPPING)

        # Senializar shutdown a todos los uvicorn.Server
        for server in self._servers:
            server.should_exit = True

        # Esperar a que el hilo termine
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

        self._set_status(DaemonStatus.STOPPED)
        self._servers = []
        self._loop = None
        self._thread = None

    def restart(self) -> None:
        self.stop()
        self.start()

    def update_config(self, new_config: AppConfig) -> None:
        """Cambia la config. Requiere restart para tomar efecto."""
        self.config = new_config

    # --- Interno ---

    def _set_status(self, status: DaemonStatus) -> None:
        with self._status_lock:
            self._status = status

    def _run_thread(self) -> None:
        """Corre dentro del hilo del daemon."""
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        # Kill zombies aqui (en el thread worker) para no bloquear la GUI
        if self.config.kill_zombies_on_startup:
            for printer_cfg in self.config.printers:
                try:
                    killed = kill_zombies_on_port(printer_cfg.port)
                    if killed:
                        logger.info(
                            f"  Puerto {printer_cfg.port}: matados {len(killed)} zombie(s) PID={killed}"
                        )
                except Exception as e:
                    logger.warning(f"Error limpiando zombies en puerto {printer_cfg.port}: {e}")

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._serve_all())
        except Exception as e:
            logger.exception(f"Daemon fallo: {e}")
            with self._status_lock:
                self._last_error = str(e)
                self._status = DaemonStatus.ERROR
        finally:
            try:
                self._loop.close()
            except Exception:
                pass

    async def _serve_all(self) -> None:
        """Levanta un uvicorn.Server por impresora y los corre en paralelo."""
        has_ssl = self.has_ssl()
        protocol = "https" if has_ssl else "http"

        self._servers = []

        for printer_cfg in self.config.printers:
            printer = Printer(
                name=printer_cfg.name,
                windows_printer=printer_cfg.windows_printer,
                paper_width=printer_cfg.paper_width,
                role=printer_cfg.role,
            )
            detect_or_warn(printer)

            app = create_app(printer, self.config.allowed_origin)

            uv_cfg = uvicorn.Config(
                app,
                host="::",  # dual-stack IPv6+IPv4
                port=printer_cfg.port,
                # log_config=None desactiva el logging por defecto de uvicorn.
                # En PyInstaller --windowed, sys.stdout es None y el formatter
                # default de uvicorn llama sys.stdout.isatty() -> AttributeError.
                # Nosotros ya tenemos nuestro logger propio (consola + archivo
                # rotativo + puente Qt), asi que uvicorn no necesita configurar
                # nada.
                log_config=None,
                log_level="warning",
                access_log=False,
                loop="asyncio",
                ssl_certfile=str(self.cert_path) if has_ssl else None,
                ssl_keyfile=str(self.key_path) if has_ssl else None,
            )
            server = uvicorn.Server(uv_cfg)
            self._servers.append(server)

            logger.info(
                f"  Impresora '{printer.name}' escuchando en "
                f"{protocol}://localhost:{printer_cfg.port} "
                f"(role={printer.role}, driver='{printer.windows_printer}')"
            )

        # Marcar RUNNING justo antes de servir
        self._set_status(DaemonStatus.RUNNING)
        logger.info("Daemon activo. Ctrl+C o Detener desde la GUI para bajar.")

        try:
            await asyncio.gather(*(s.serve() for s in self._servers))
        finally:
            logger.info("Daemon detenido.")


# ============================================================================
# Entry point standalone (CLI, para compatibilidad con v1.4)
# ============================================================================

def main() -> None:
    """Arranca el daemon en modo CLI (bloqueante). Retrocompat con v1.4."""
    from ..util.paths import config_path, cert_pem, cert_key, logs_dir
    from .config_manager import load_config
    from .logger_setup import setup_logging

    config = load_config(config_path())
    log_ = setup_logging(
        log_dir=logs_dir(),
        retention_days=config.log_retention_days,
        verbose=config.verbose,
        console=True,
    )

    log_.info("=" * 68)
    log_.info("POS Print Proxy v2.0.0 (daemon CLI)")
    log_.info(f"  Dominio Odoo: {config.allowed_origin}")
    log_.info(f"  Impresoras: {len(config.printers)}")
    try:
        log_.info(f"  Equipo: {socket.gethostname()}")
    except Exception:
        pass
    log_.info("=" * 68)

    daemon = ProxyDaemon(config, cert_pem(), cert_key())

    ok, err = self_test_cert(cert_pem(), cert_key())
    if not ok:
        log_.warning(f"  Cert HTTPS: {err}")

    daemon.start()

    try:
        while daemon.is_running():
            time.sleep(0.5)
    except KeyboardInterrupt:
        log_.info("Ctrl+C recibido, deteniendo daemon...")
        daemon.stop()


if __name__ == "__main__":
    main()
