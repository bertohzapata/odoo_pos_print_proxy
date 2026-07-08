"""
Controlador de certificados HTTPS.

Responsabilidades:
- Detectar si hay cert instalado y valido
- Leer fecha de expiracion
- Renovar (regenerar) via mkcert
- Instalar la CA raiz de mkcert si es la primera vez

La renovacion es "un click" desde la GUI. Corre en un QThread para no
bloquear la UI.
"""
import datetime as _dt
import logging
import shutil
import ssl
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal


logger = logging.getLogger("pos_print_proxy.gui.cert")


MKCERT_VERSION = "v1.4.4"
MKCERT_URL = (
    f"https://github.com/FiloSottile/mkcert/releases/download/{MKCERT_VERSION}/"
    "mkcert-v1.4.4-windows-amd64.exe"
)


# ============================================================================
# Info de cert
# ============================================================================

@dataclass(frozen=True)
class CertInfo:
    exists: bool
    valid: bool
    subject: str = ""
    issuer: str = ""
    not_before: _dt.datetime | None = None
    not_after: _dt.datetime | None = None
    error: str = ""

    @property
    def days_left(self) -> int:
        if not self.not_after:
            return 0
        return max(0, (self.not_after - _dt.datetime.utcnow()).days)

    @property
    def expires_soon(self) -> bool:
        return 0 < self.days_left < 30

    @property
    def expired(self) -> bool:
        return self.exists and self.days_left <= 0


def inspect_cert(cert_path: Path, key_path: Path) -> CertInfo:
    """Analiza el cert y retorna metadatos utiles."""
    if not cert_path.exists():
        return CertInfo(exists=False, valid=False, error="No hay cert instalado")

    try:
        # Verificar que carga con la key
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    except Exception as e:
        return CertInfo(exists=True, valid=False, error=str(e))

    # Parsear el cert para leer subject/issuer/fechas
    try:
        pem = cert_path.read_bytes()
        cert = ssl.PEM_cert_to_DER_cert(pem.decode("utf-8"))
        info = _parse_cert(cert)
        return CertInfo(
            exists=True,
            valid=True,
            subject=info.get("subject", ""),
            issuer=info.get("issuer", ""),
            not_before=info.get("not_before"),
            not_after=info.get("not_after"),
        )
    except Exception as e:
        return CertInfo(exists=True, valid=True, error=f"Cert valido pero no parseable: {e}")


def _parse_cert(der: bytes) -> dict:
    """Parsea un cert DER usando ssl standard library."""
    try:
        # ssl no expone _test_decode_cert de forma publica, usamos cryptography
        # si esta disponible; fallback a leer con openssl
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend

        pem = ssl.DER_cert_to_PEM_cert(der).encode()
        cert = x509.load_pem_x509_certificate(pem, default_backend())
        return {
            "subject": cert.subject.rfc4514_string(),
            "issuer": cert.issuer.rfc4514_string(),
            "not_before": cert.not_valid_before_utc.replace(tzinfo=None),
            "not_after": cert.not_valid_after_utc.replace(tzinfo=None),
        }
    except ImportError:
        # Fallback muy simple: al menos la fecha aproximada del PEM
        return {}


# ============================================================================
# Renovacion en background (QThread)
# ============================================================================

class CertRenewWorker(QThread):
    """
    Renueva/regenera el cert en un thread aparte. Emite `progress` con texto
    para pintarlo en la UI y `finished_ok`/`failed` al terminar.
    """

    progress = Signal(str)
    finished_ok = Signal()
    failed = Signal(str)

    def __init__(
        self,
        mkcert_binary: Path,
        cert_dir: Path,
        cert_path: Path,
        key_path: Path,
        install_ca: bool = True,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.mkcert_binary = mkcert_binary
        self.cert_dir = cert_dir
        self.cert_path = cert_path
        self.key_path = key_path
        self.install_ca = install_ca

    def run(self) -> None:
        try:
            self._ensure_mkcert()
            if self.install_ca:
                self._install_ca()
            self._generate_cert()
            self.finished_ok.emit()
        except Exception as e:
            logger.exception("Error renovando cert")
            self.failed.emit(str(e))

    def _ensure_mkcert(self) -> None:
        if self.mkcert_binary.exists():
            return
        self.progress.emit("Descargando mkcert desde GitHub...")
        self.mkcert_binary.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(MKCERT_URL, timeout=30) as r:
                with open(self.mkcert_binary, "wb") as f:
                    shutil.copyfileobj(r, f)
        except Exception as e:
            raise RuntimeError(
                f"No se pudo descargar mkcert. Verifica tu conexion o "
                f"descarga manualmente desde {MKCERT_URL}: {e}"
            )

    def _install_ca(self) -> None:
        self.progress.emit("Instalando CA local en Windows...")
        result = subprocess.run(
            [str(self.mkcert_binary), "-install"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"mkcert -install fallo. "
                f"Puede requerir permisos de administrador. "
                f"Salida: {result.stderr or result.stdout}"
            )

    def _generate_cert(self) -> None:
        self.progress.emit("Generando certificado para localhost...")
        self.cert_dir.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [
                str(self.mkcert_binary),
                "-cert-file", str(self.cert_path),
                "-key-file", str(self.key_path),
                "localhost", "127.0.0.1", "::1",
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"mkcert fallo generando certificado: {result.stderr or result.stdout}"
            )


# ============================================================================
# Controller para la UI
# ============================================================================

class CertController(QObject):
    """API para la UI: inspeccionar cert, disparar renovacion."""

    renew_started = Signal()
    renew_progress = Signal(str)
    renew_finished = Signal(bool, str)  # (ok, mensaje)
    info_changed = Signal(object)       # CertInfo

    def __init__(
        self,
        cert_path: Path,
        key_path: Path,
        cert_dir: Path,
        mkcert_binary: Path,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.cert_path = cert_path
        self.key_path = key_path
        self.cert_dir = cert_dir
        self.mkcert_binary = mkcert_binary
        self._worker: CertRenewWorker | None = None

    def inspect(self) -> CertInfo:
        info = inspect_cert(self.cert_path, self.key_path)
        self.info_changed.emit(info)
        return info

    def renew(self, install_ca: bool = True) -> None:
        """Dispara la renovacion en background."""
        if self._worker and self._worker.isRunning():
            logger.info("renew() ignorado: ya hay una renovacion en curso")
            return

        self.renew_started.emit()

        worker = CertRenewWorker(
            mkcert_binary=self.mkcert_binary,
            cert_dir=self.cert_dir,
            cert_path=self.cert_path,
            key_path=self.key_path,
            install_ca=install_ca,
        )
        worker.progress.connect(self.renew_progress.emit)
        worker.finished_ok.connect(lambda: self._on_done(True, "Certificado renovado con exito"))
        worker.failed.connect(lambda msg: self._on_done(False, msg))
        self._worker = worker
        worker.start()

    def _on_done(self, ok: bool, msg: str) -> None:
        self.renew_finished.emit(ok, msg)
        # Refrescar info
        self.inspect()
