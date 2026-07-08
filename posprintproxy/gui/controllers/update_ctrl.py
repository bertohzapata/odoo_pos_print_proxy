"""
Verificacion de actualizaciones via GitHub Releases.

- Se consulta al arrancar (con un delay para no bloquear el startup)
- Y luego cada 24h en background
- Si hay version nueva, emite senial que la GUI/tray muestra como notificacion
"""
import json
import logging
import urllib.request
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from ...util.version import Version


logger = logging.getLogger("pos_print_proxy.gui.update")


# GitHub repo: se puede sobreescribir en runtime desde config
DEFAULT_RELEASES_URL = (
    "https://api.github.com/repos/bertohzapata/odoo_pos_print_proxy/releases/latest"
)


@dataclass(frozen=True)
class UpdateInfo:
    available: bool
    latest_version: str = ""
    current_version: str = ""
    download_url: str = ""
    release_notes: str = ""
    error: str = ""


class UpdateCheckWorker(QThread):
    """Consulta el endpoint de GitHub Releases en background."""

    result = Signal(object)  # UpdateInfo

    def __init__(self, current_version: str, releases_url: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.current_version = current_version
        self.releases_url = releases_url

    def run(self) -> None:
        try:
            info = self._check()
            self.result.emit(info)
        except Exception as e:
            logger.warning(f"No se pudo consultar GitHub Releases: {e}")
            self.result.emit(UpdateInfo(
                available=False,
                current_version=self.current_version,
                error=str(e),
            ))

    def _check(self) -> UpdateInfo:
        req = urllib.request.Request(
            self.releases_url,
            headers={"Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)

        tag = data.get("tag_name", "")
        latest = Version.parse(tag)
        current = Version.parse(self.current_version)

        if not latest or not current:
            return UpdateInfo(
                available=False,
                latest_version=str(latest) if latest else tag,
                current_version=str(current) if current else self.current_version,
                error="No se pudo parsear semver",
            )

        # Buscar el asset .exe del installer
        download_url = ""
        for asset in data.get("assets", []):
            name = asset.get("name", "").lower()
            if name.endswith(".exe") and "setup" in name:
                download_url = asset.get("browser_download_url", "")
                break

        return UpdateInfo(
            available=latest > current,
            latest_version=str(latest),
            current_version=str(current),
            download_url=download_url,
            release_notes=data.get("body", ""),
        )


class UpdateController(QObject):
    """Controla el chequeo periodico y notifica cuando hay update."""

    update_found = Signal(object)   # UpdateInfo (solo cuando hay algo nuevo)
    check_finished = Signal(object) # UpdateInfo (siempre, para refrescar UI)

    CHECK_INTERVAL_MS = 24 * 60 * 60 * 1000  # 24 horas
    INITIAL_DELAY_MS = 60 * 1000             # 1 minuto tras arranque

    def __init__(
        self,
        current_version: str,
        releases_url: str = DEFAULT_RELEASES_URL,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.current_version = current_version
        self.releases_url = releases_url
        self._worker: Optional[UpdateCheckWorker] = None
        self._last_result: Optional[UpdateInfo] = None

        # Timer inicial: consulta 1min despues del arranque
        self._initial_timer = QTimer(self)
        self._initial_timer.setSingleShot(True)
        self._initial_timer.timeout.connect(self.check_now)
        self._initial_timer.start(self.INITIAL_DELAY_MS)

        # Timer periodico: cada 24h
        self._periodic = QTimer(self)
        self._periodic.setInterval(self.CHECK_INTERVAL_MS)
        self._periodic.timeout.connect(self.check_now)
        self._periodic.start()

    def check_now(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        worker = UpdateCheckWorker(self.current_version, self.releases_url, self)
        worker.result.connect(self._on_result)
        self._worker = worker
        worker.start()

    def last_result(self) -> Optional[UpdateInfo]:
        return self._last_result

    def _on_result(self, info: UpdateInfo) -> None:
        self._last_result = info
        self.check_finished.emit(info)
        if info.available:
            self.update_found.emit(info)
