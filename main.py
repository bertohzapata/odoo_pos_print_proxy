"""
POS Print Proxy - Impersona un IoT Box de Odoo para imprimir en impresoras
termicas locales. Soporta HTTPS local (recomendado) para evitar bloqueos de
"Mixed Content" del navegador cuando Odoo se sirve por HTTPS.

Ejecutar:
    python main.py
"""

import asyncio
import base64
import logging
import socket
import ssl
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse, Response

from printer_backend import print_image_win32, open_cashbox_win32, list_printers

# --- Load config ---
CONFIG_PATH = Path(__file__).parent / "config.yaml"

if not CONFIG_PATH.exists():
    print(f"ERROR: No se encontro {CONFIG_PATH}")
    print("Verifica que config.yaml exista en la misma carpeta que main.py")
    sys.exit(1)

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

ODOO_DOMAIN = config.get("odoo_domain", "https://tudominio.com")
PORT = config.get("port", 8072)
PRINTER_NAME = config.get("printer_name", "POS-80")
PAPER_WIDTH = config.get("paper_width", 576)
# verbose=True muestra cada status_json (util para depurar). Por defecto false
# para que el log solo muestre eventos relevantes (conexion, impresion, errores).
VERBOSE = bool(config.get("verbose", False))

# --- SSL/TLS ---
# Si existen los certificados generados por setup_https.bat (mkcert), el proxy
# arranca en HTTPS. Obligatorio cuando Odoo se sirve por HTTPS (mixed content).
SSL_CERT = Path(__file__).parent / "localhost.pem"
SSL_KEY = Path(__file__).parent / "localhost-key.pem"
HAS_SSL = SSL_CERT.exists() and SSL_KEY.exists()

# --- Logging ---
logging.basicConfig(
    level=logging.DEBUG if VERBOSE else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pos_print_proxy")

# Silenciar el ruido de uvicorn (access logs y reportes de bajo nivel).
logging.getLogger("uvicorn.access").disabled = True
logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
# El logger de asyncio es de donde salen los ConnectionResetError: subimos su
# umbral a CRITICAL para que ni siquiera intente formatearlos. La supresion
# real ocurre en el exception handler del loop (ver lifespan mas abajo).
logging.getLogger("asyncio").setLevel(logging.CRITICAL)


# --- Estado de conexion (para loggear "POS conectado" una sola vez) ---
class _State:
    pos_connected = False


STATE = _State()


# --- Supresion en la fuente del ConnectionResetError [WinError 10054] ---
#
# En Windows, cuando el navegador cierra una conexion HTTPS keep-alive de forma
# abrupta (RST en vez de FIN), el ProactorEventLoop intenta socket.shutdown()
# sobre un socket ya cerrado y lanza ConnectionResetError. La respuesta HTTP ya
# fue entregada correctamente; es solo ruido del cleanup. Lo interceptamos en
# el exception handler del loop, que es el unico punto fiable para silenciarlo.
def _quiet_exception_handler(loop, context):
    exc = context.get("exception")
    if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
        return  # ignorar: el cliente cerro la conexion, no es un error real
    loop.default_exception_handler(context)


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(_quiet_exception_handler)
    yield


# --- FastAPI app ---
app = FastAPI(title="POS Print Proxy", version="1.3.0", lifespan=lifespan)


# --- Custom CORS + Private Network Access middleware ---
ALLOWED_ORIGIN = ODOO_DOMAIN.rstrip("/")  # normalizar (sin barra final)


@app.middleware("http")
async def pna_cors_middleware(request: Request, call_next):
    origin = request.headers.get("origin", "")
    is_allowed = origin == ALLOWED_ORIGIN

    # Preflight OPTIONS
    if request.method == "OPTIONS":
        if is_allowed:
            return Response(
                status_code=204,
                headers={
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization",
                    "Access-Control-Allow-Private-Network": "true",
                    "Access-Control-Max-Age": "86400",
                    "Vary": "Origin",
                },
            )
        # Solo advertir si hay un origen presente y distinto (no para peticiones
        # locales directas sin Origin, como abrir la URL en el navegador).
        if origin:
            logger.warning(f"Origen no permitido (revisar odoo_domain): {origin!r}")
        return Response(status_code=403)

    response = await call_next(request)
    if is_allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Private-Network"] = "true"
        response.headers["Vary"] = "Origin"
    return response


def jsonrpc_response(result, request_id=None):
    """Wrap result in JSON-RPC 2.0 response format."""
    return JSONResponse({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    })


# --- Endpoints (protocolo IoT Box) ---

@app.get("/hw_proxy/hello")
async def hello():
    """Health check - el POS usa fetch() simple, espera texto plano."""
    return PlainTextResponse("ping")


@app.post("/hw_proxy/hello")
async def hello_post():
    return PlainTextResponse("ping")


@app.get("/hw_proxy/status_json")
async def status_json_get():
    return {"status": "connected", "drivers": {"printer": {"status": "connected"}}}


@app.post("/hw_proxy/status_json")
async def status_json_post(request: Request):
    """Keep-alive: el POS lo llama cada 5s. Solo se loggea en modo verbose."""
    if not STATE.pos_connected:
        STATE.pos_connected = True
        logger.info("POS conectado (keep-alive activo)")
    if VERBOSE:
        logger.debug("status_json")
    body = await request.json()
    request_id = body.get("id")
    return jsonrpc_response({"printer": {"status": "connected"}}, request_id)


@app.post("/hw_proxy/handshake")
async def handshake(request: Request):
    logger.info("POS conectado (handshake OK)")
    STATE.pos_connected = True
    body = await request.json()
    request_id = body.get("id")
    return jsonrpc_response(True, request_id)


@app.post("/hw_proxy/default_printer_action")
async def printer_action(request: Request):
    """
    Endpoint principal de impresion.

    Body JSON-RPC:
    {
      "jsonrpc": "2.0", "method": "call", "id": <int>,
      "params": {"data": {"action": "print_receipt"|"cashbox", "receipt": "<base64>"}}
    }
    """
    body = await request.json()
    request_id = body.get("id")
    params = body.get("params", {})
    data = params.get("data", {})

    action = data.get("action", "")

    try:
        if action == "print_receipt":
            receipt_b64 = data.get("receipt", "")
            if not receipt_b64:
                logger.warning("print_receipt llamado sin datos de imagen")
                return jsonrpc_response(False, request_id)

            image_bytes = base64.b64decode(receipt_b64)
            print_image_win32(image_bytes, PRINTER_NAME, PAPER_WIDTH)
            logger.info(f"Impreso en '{PRINTER_NAME}' ({len(image_bytes)} bytes)")
            return jsonrpc_response(True, request_id)

        elif action == "cashbox":
            open_cashbox_win32(PRINTER_NAME)
            logger.info(f"Cajon abierto en '{PRINTER_NAME}'")
            return jsonrpc_response(True, request_id)

        else:
            logger.warning(f"Accion desconocida: {action}")
            return jsonrpc_response(False, request_id)

    except Exception as e:
        logger.error(f"ERROR al imprimir en '{PRINTER_NAME}': {e}")
        return jsonrpc_response(False, request_id)


# --- Utility endpoint (debug) ---

@app.get("/printers")
async def get_printers():
    """List available printers on this system."""
    try:
        printers = list_printers()
        return {"printers": printers, "configured": PRINTER_NAME}
    except Exception as e:
        return {"error": str(e)}


# --- Self-test de arranque ---

def _self_test_cert():
    """Verifica que el certificado HTTPS sea cargable. Ayuda a diagnosticar."""
    if not HAS_SSL:
        return
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=str(SSL_CERT), keyfile=str(SSL_KEY))
    except Exception as e:
        logger.error(f"  ATENCION: el certificado HTTPS existe pero NO es valido: {e}")
        logger.error("  Vuelve a ejecutar setup_https.bat como administrador.")


# --- Main ---

if __name__ == "__main__":
    import uvicorn

    # En Windows, usar SelectorEventLoop en lugar del Proactor por defecto.
    # El Proactor es el que genera los ConnectionResetError al cerrar conexiones
    # HTTPS. Para un proxy de impresion (I/O ligero) el Selector es mas estable.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    protocol = "https" if HAS_SSL else "http"

    logger.info("=" * 60)
    logger.info("POS Print Proxy v1.3")
    logger.info(f"  Modo: {'HTTPS (correcto)' if HAS_SSL else 'HTTP (INCORRECTO si Odoo es HTTPS)'}")
    logger.info(f"  Dominio Odoo permitido: {ALLOWED_ORIGIN}")
    logger.info(f"  Puerto: {PORT}")
    logger.info(f"  Impresora: {PRINTER_NAME}")
    logger.info(f"  Ancho papel: {PAPER_WIDTH}px")
    logger.info("=" * 60)

    if not HAS_SSL:
        logger.warning("")
        logger.warning("  >>> NO HAY CERTIFICADOS HTTPS <<<")
        logger.warning("  Si Odoo se sirve por HTTPS, el navegador bloqueara las peticiones.")
        logger.warning("  Solucion: click derecho en setup_https.bat > Ejecutar como administrador")
        logger.warning("")
    else:
        _self_test_cert()

    try:
        printers = list_printers()
        logger.info(f"  Impresoras detectadas: {printers}")
        if PRINTER_NAME not in printers:
            logger.warning(
                f"  ATENCION: '{PRINTER_NAME}' NO esta en la lista. "
                f"Revisa printer_name en config.yaml."
            )
    except Exception:
        logger.warning("  No se pudo listar impresoras (win32print no disponible)")

    # Hostname de la PC (ayuda a confirmar en que equipo corre)
    try:
        logger.info(f"  Equipo: {socket.gethostname()}")
    except Exception:
        pass

    logger.info("")
    logger.info(f"Proxy listo en {protocol}://localhost:{PORT}")
    logger.info("Presiona Ctrl+C para detener")
    logger.info("")

    uvicorn_kwargs = {
        "host": "127.0.0.1",
        "port": PORT,
        "log_level": "warning",
        "access_log": False,
        "loop": "asyncio",
    }
    if HAS_SSL:
        uvicorn_kwargs["ssl_certfile"] = str(SSL_CERT)
        uvicorn_kwargs["ssl_keyfile"] = str(SSL_KEY)

    try:
        uvicorn.run(app, **uvicorn_kwargs)
    except KeyboardInterrupt:
        logger.info("Proxy detenido.")
