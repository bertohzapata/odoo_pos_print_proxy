"""
Entry point de la aplicacion GUI. Orquesta:
- QApplication
- Config
- Logger (con bridge Qt)
- Daemon + controller
- Tray
- Main window
- Auto-update
"""
import argparse
import logging
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from .. import __version__, __app_id__, __app_name__
from ..daemon import ProxyDaemon
from ..daemon.config_manager import load_config
from ..daemon.logger_setup import setup_logging
from ..util.paths import (
    app_data_dir,
    cert_dir,
    cert_pem,
    cert_key,
    config_path,
    is_frozen,
    logs_dir,
    mkcert_binary,
)
from .controllers.cert_ctrl import CertController
from .controllers.config_ctrl import ConfigController
from .controllers.daemon_ctrl import DaemonController
from .controllers.update_ctrl import UpdateController
from .main_window import MainWindow
from .qt_log_handler import QtLogBridge, QtLogHandler
from .tray import TrayIcon


logger = logging.getLogger("pos_print_proxy.gui")


def _load_stylesheet() -> str:
    qss_path = Path(__file__).parent / "theme.qss"
    if qss_path.exists():
        try:
            return qss_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"WARN: no se pudo leer theme.qss: {e}")
    return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="posprintproxy")
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="Iniciar en la bandeja del sistema, sin mostrar la ventana",
    )
    parser.add_argument(
        "--no-autostart-daemon",
        action="store_true",
        help="No arrancar el daemon al inicio (dejarlo detenido)",
    )
    args = parser.parse_args(argv)

    # 1. QApplication
    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName(__app_name__)
    app.setApplicationDisplayName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("bertohzapata")
    app.setDesktopFileName(__app_id__)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(_load_stylesheet())

    # 2. Config
    cfg_path = config_path()
    config_ctrl = ConfigController(cfg_path)
    try:
        config = config_ctrl.load()
    except SystemExit:
        QMessageBox.critical(
            None,
            "Configuracion invalida",
            f"El archivo {cfg_path} tiene errores. Revisa la carpeta de datos "
            f"y edita el archivo, o borralo para regenerarlo al reabrir la app."
        )
        return 1
    except Exception as e:
        QMessageBox.critical(None, "Error", f"No se pudo cargar la configuracion: {e}")
        return 1

    # 3. Logging (consola off cuando somos GUI empaquetada; on en dev)
    log_bridge = QtLogBridge()
    setup_logging(
        log_dir=logs_dir(),
        retention_days=config.log_retention_days,
        verbose=config.verbose,
        console=not is_frozen(),
    )
    # Enchufar el handler Qt al logger raiz para que la vista de logs vea todo
    qt_handler = QtLogHandler(log_bridge)
    qt_handler.setLevel(logging.DEBUG if config.verbose else logging.INFO)
    logging.getLogger().addHandler(qt_handler)

    logger.info("=" * 60)
    logger.info(f"{__app_name__} v{__version__} (GUI)")
    logger.info(f"  Config: {cfg_path}")
    logger.info(f"  Logs:   {logs_dir()}")
    logger.info(f"  Certs:  {cert_dir()}")
    logger.info("=" * 60)

    # 4. Daemon
    daemon = ProxyDaemon(config, cert_pem(), cert_key())
    daemon_ctrl = DaemonController(daemon, parent=app)

    # 5. Cert controller
    cert_ctrl = CertController(
        cert_path=cert_pem(),
        key_path=cert_key(),
        cert_dir=cert_dir(),
        mkcert_binary=mkcert_binary(),
        parent=app,
    )

    # 6. Update controller
    update_ctrl = UpdateController(current_version=__version__, parent=app)

    # 7. Ventana + tray
    window = MainWindow(daemon_ctrl, config_ctrl, cert_ctrl, update_ctrl, log_bridge)
    tray = TrayIcon(daemon_ctrl, parent=app)

    if not tray.is_supported():
        # Sistemas sin bandeja: no cerrar en X (o mostrar ventana siempre)
        logger.warning("El sistema no soporta bandeja del sistema; el cierre "
                       "de la ventana terminara la app.")
        app.setQuitOnLastWindowClosed(True)

    tray.show()

    # Conexiones tray <-> window
    tray.show_window_requested.connect(_bring_to_front(window))
    tray.quit_requested.connect(lambda: _handle_quit(app, daemon, window))
    tray.open_view_requested.connect(lambda key: _open_view(window, key))

    # Notificacion de update
    update_ctrl.update_found.connect(tray.show_update_available)

    # 8. Actualizar config del daemon si cambia
    def _on_config_saved(new_cfg):
        daemon.update_config(new_cfg)
    config_ctrl.config_changed.connect(_on_config_saved)

    # 9. Iniciar daemon salvo que se pida lo contrario
    if not args.no_autostart_daemon:
        daemon_ctrl.start()

    # 10. Mostrar ventana o no
    if args.minimized:
        window.hide()
    else:
        window.show()

    # 11. Conectar refresco de cert al inicio
    cert_ctrl.inspect()

    exit_code = app.exec()

    # Cleanup
    try:
        daemon.stop(timeout=3)
    except Exception:
        pass

    return exit_code


def _bring_to_front(window: MainWindow):
    def _fn():
        window.show()
        window.raise_()
        window.activateWindow()
    return _fn


def _open_view(window: MainWindow, key: str) -> None:
    window.show_view(key)
    window.show()
    window.raise_()
    window.activateWindow()


def _handle_quit(app: QApplication, daemon: ProxyDaemon, window: MainWindow) -> None:
    window.request_quit()
    try:
        daemon.stop(timeout=3)
    except Exception:
        pass
    app.quit()


if __name__ == "__main__":
    sys.exit(main())
