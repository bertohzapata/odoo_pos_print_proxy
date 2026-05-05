"""
POS Print Proxy - Impersona un IoT Box de Odoo para imprimir en impresoras
termicas locales. Soporta HTTPS local (recomendado) para evitar bloqueos de
"Mixed Content" del navegador cuando Odoo se sirve por HTTPS.

Ejecutar:
    python main.py
"""

import base64
import logging
import sys
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

# --- SSL/TLS ---
# Si existen los certificados generados por setup_https.bat (mkcert), el proxy
# arranca en HTTPS. Esto es OBLIGATORIO cuando Odoo se sirve por HTTPS, porque
# los navegadores bloquean por "Mixed Content" si una pagina HTTPS intenta
# hablar con un servicio HTTP local.
SSL_CERT = Path(__file__).parent / "localhost.pem"
SSL_KEY = Path(__file__).parent / "localhost-key.pem"
HAS_SSL = SSL_CERT.exists() and SSL_KEY.exists()

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pos_print_proxy")


# Silenciar el ruido de ConnectionResetError [WinError 10054] que asyncio en
# Windows produce cuando Chrome cierra conexiones HTTPS keep-alive de forma
# abrupta. La respuesta HTTP ya fue entregada correctamente antes del cleanup,
# asi que es solo ruido en el log, sin impacto funcional.
class _SilenceConnectionResetFilter(logging.Filter):
    def filter(self, record):
        if record.exc_info and record.exc_info[0] is ConnectionResetError:
            return False
        msg = record.getMessage()
        if "ConnectionResetError" in msg or "WinError 10054" in msg:
            return False
        return True


logging.getLogger("asyncio").addFilter(_SilenceConnectionResetFilter())

# --- FastAPI app ---
app = FastAPI(title="POS Print Proxy", version="1.2.0")


# --- Custom CORS + Private Network Access middleware ---
#
# Chrome/Edge implementan Private Network Access (PNA): cuando una pagina
# publica intenta acceder a un servicio en red privada/loopback, el navegador
# envia un preflight OPTIONS con `Access-Control-Request-Private-Network: true`
# y exige `Access-Control-Allow-Private-Network: true` en la respuesta.
# El CORSMiddleware estandar de FastAPI no incluye este header.

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
        logger.warning(f"OPTIONS preflight rechazado de origen no permitido: {origin!r}")
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
    """Status check via JSON-RPC POST. POS lo llama cada 5s para mantener viva la conexion."""
    body = await request.json()
    request_id = body.get("id")
    drivers = {"printer": {"status": "connected"}}
    return jsonrpc_response(drivers, request_id)


@app.post("/hw_proxy/handshake")
async def handshake(request: Request):
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
            logger.info(f"Recibido trabajo de impresion ({len(image_bytes)} bytes)")

            print_image_win32(image_bytes, PRINTER_NAME, PAPER_WIDTH)
            return jsonrpc_response(True, request_id)

        elif action == "cashbox":
            open_cashbox_win32(PRINTER_NAME)
            return jsonrpc_response(True, request_id)

        else:
            logger.warning(f"Accion desconocida: {action}")
            return jsonrpc_response(False, request_id)

    except Exception as e:
        logger.error(f"Error al imprimir: {e}")
        return jsonrpc_response(False, request_id)


# --- Utility endpoint (no es parte del protocolo IoT, solo para debug) ---

@app.get("/printers")
async def get_printers():
    """List available printers on this system."""
    try:
        printers = list_printers()
        return {"printers": printers, "configured": PRINTER_NAME}
    except Exception as e:
        return {"error": str(e)}


# --- Main ---

if __name__ == "__main__":
    import uvicorn

    protocol = "https" if HAS_SSL else "http"

    logger.info("=" * 60)
    logger.info("POS Print Proxy v1.2 (HTTPS local + PNA)")
    logger.info(f"  Modo: {'HTTPS (recomendado)' if HAS_SSL else 'HTTP (legacy - puede fallar con Odoo HTTPS)'}")
    logger.info(f"  Dominio Odoo permitido: {ALLOWED_ORIGIN}")
    logger.info(f"  Puerto: {PORT}")
    logger.info(f"  Impresora: {PRINTER_NAME}")
    logger.info(f"  Ancho papel: {PAPER_WIDTH}px")
    logger.info("=" * 60)

    if not HAS_SSL:
        logger.warning("")
        logger.warning("  >>> NO HAY CERTIFICADOS HTTPS <<<")
        logger.warning("  Si Odoo se sirve por HTTPS, el navegador bloqueara las peticiones")
        logger.warning("  por 'Mixed Content'. Para activar HTTPS local:")
        logger.warning("  1. Click derecho en setup_https.bat > Ejecutar como administrador")
        logger.warning("  2. Reiniciar este proxy")
        logger.warning("")

    try:
        printers = list_printers()
        logger.info(f"  Impresoras disponibles: {printers}")
        if PRINTER_NAME not in printers:
            logger.warning(
                f"  ATENCION: '{PRINTER_NAME}' no encontrada. Disponibles: {printers}"
            )
    except Exception:
        logger.warning("  No se pudo listar impresoras (win32print no disponible)")

    logger.info("")
    logger.info(f"Proxy listo en {protocol}://localhost:{PORT}")
    logger.info("Presiona Ctrl+C para detener")
    logger.info("")

    uvicorn_kwargs = {
        "host": "0.0.0.0",
        "port": PORT,
        "log_level": "warning",
    }
    if HAS_SSL:
        uvicorn_kwargs["ssl_certfile"] = str(SSL_CERT)
        uvicorn_kwargs["ssl_keyfile"] = str(SSL_KEY)

    uvicorn.run(app, **uvicorn_kwargs)
