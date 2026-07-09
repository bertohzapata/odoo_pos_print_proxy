"""
Fabrica una instancia FastAPI por impresora, con los endpoints del protocolo
IoT Box de Odoo. Cada instancia:

- Escucha en su propio puerto
- Tiene su propio middleware CORS+PNA
- Tiene su propio "state" (para loggear "POS conectado" una sola vez)
- Dispatcha las impresiones a su Printer especifico
"""
import asyncio
import base64
import binascii
import datetime as _dt
import itertools
import json
import logging
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse, Response

from ..util.paths import debug_dir
from .printer_backend import list_printers
from .printer_manager import Printer


logger = logging.getLogger("pos_print_proxy.server")


def _quiet_exception_handler(loop, context):
    """
    Silencia ConnectionResetError [WinError 10054] y familia. Ver detalle en
    posprintproxy/daemon/daemon.py.
    """
    exc = context.get("exception")
    if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
        return
    loop.default_exception_handler(context)


@asynccontextmanager
async def _lifespan(_: FastAPI):
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(_quiet_exception_handler)
    yield


def _jsonrpc_response(result, request_id=None) -> JSONResponse:
    return JSONResponse({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    })


# Contador atomico para desambiguar impresiones que llegan en el mismo segundo.
_debug_counter = itertools.count()


def _save_debug_print(
    receipt_b64: str,
    printer_name: str,
    port: int,
    origin: str,
    action: str,
) -> None:
    """
    Guarda una copia del JPEG entrante + metadata JSON en la carpeta debug.
    Cualquier error se loggea pero no se propaga: el debug NUNCA debe
    bloquear la impresion real.
    """
    try:
        # Decodificar base64 (tolerar padding faltante y URL-safe)
        try:
            img_bytes = base64.b64decode(receipt_b64, validate=False)
        except binascii.Error:
            logger.warning("[debug] base64 invalido; se salta el guardado")
            return

        ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        seq = next(_debug_counter)
        # Sanitizar el nombre de la impresora para el filename
        safe_printer = "".join(c if c.isalnum() or c in "._-" else "_" for c in printer_name)

        base_name = f"{ts}_p{port}_{safe_printer}_{seq:04d}"
        target_dir = debug_dir()
        img_path = target_dir / f"{base_name}.jpg"
        meta_path = target_dir / f"{base_name}.json"

        img_path.write_bytes(img_bytes)

        meta = {
            "timestamp_iso": _dt.datetime.now().isoformat(),
            "printer_name": printer_name,
            "port": port,
            "action": action,
            "origin": origin,
            "size_bytes": len(img_bytes),
            "seq": seq,
        }
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info(f"[debug] Guardado {img_path.name} ({len(img_bytes)} bytes)")
    except Exception as e:
        # Debug NUNCA debe romper la impresion real.
        logger.warning(f"[debug] Error guardando print: {e}")


def create_app(
    printer: Printer,
    allowed_origin: str,
    debug_save_getter: Callable[[], bool] = lambda: False,
    port: int = 0,
) -> FastAPI:
    """
    Fabrica una FastAPI dedicada a una impresora.

    Args:
        printer: instancia de Printer con logica de impresion
        allowed_origin: dominio Odoo permitido para CORS
        debug_save_getter: callable que retorna True si se debe guardar
            cada impresion como archivo. Se lee en cada request para
            reflejar cambios en caliente del toggle de la GUI.
        port: puerto de la instancia (solo para nombres de archivos debug)
    """
    app = FastAPI(
        title=f"POS Print Proxy - {printer.name}",
        version="2.0.2",
        lifespan=_lifespan,
    )

    class _State:
        pos_connected = False

    state = _State()

    @app.middleware("http")
    async def pna_cors_middleware(request: Request, call_next):
        origin = request.headers.get("origin", "")
        is_allowed = origin == allowed_origin

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
            if origin:
                logger.warning(
                    f"[{printer.name}] Origen no permitido (revisar odoo_domain): {origin!r}"
                )
            return Response(status_code=403)

        response = await call_next(request)
        if is_allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Private-Network"] = "true"
            response.headers["Vary"] = "Origin"
        return response

    @app.get("/hw_proxy/hello")
    async def hello():
        return PlainTextResponse("ping")

    @app.post("/hw_proxy/hello")
    async def hello_post():
        return PlainTextResponse("ping")

    @app.get("/hw_proxy/status_json")
    async def status_json_get():
        return {"status": "connected", "drivers": {"printer": {"status": "connected"}}}

    @app.post("/hw_proxy/status_json")
    async def status_json_post(request: Request):
        if not state.pos_connected:
            state.pos_connected = True
            logger.info(f"[{printer.name}] POS conectado (keep-alive activo)")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"[{printer.name}] status_json")
        body = await request.json()
        return _jsonrpc_response(
            {"printer": {"status": "connected"}},
            body.get("id"),
        )

    @app.post("/hw_proxy/handshake")
    async def handshake(request: Request):
        logger.info(f"[{printer.name}] POS conectado (handshake OK)")
        state.pos_connected = True
        body = await request.json()
        return _jsonrpc_response(True, body.get("id"))

    @app.post("/hw_proxy/default_printer_action")
    async def printer_action(request: Request):
        body = await request.json()
        request_id = body.get("id")
        params = body.get("params", {})
        data = params.get("data", {})
        action = data.get("action", "")

        try:
            if action == "print_receipt":
                receipt_b64 = data.get("receipt", "")
                if not receipt_b64:
                    logger.warning(f"[{printer.name}] print_receipt sin datos de imagen")
                    return _jsonrpc_response(False, request_id)

                # Debug: guardar copia del JPEG entrante si el toggle esta activo.
                # El helper es tolerante a fallos: si algo revienta, se loggea
                # pero la impresion real continua.
                try:
                    if debug_save_getter():
                        _save_debug_print(
                            receipt_b64=receipt_b64,
                            printer_name=printer.name,
                            port=port,
                            origin=request.headers.get("origin", ""),
                            action=action,
                        )
                except Exception as e:
                    logger.warning(f"[{printer.name}] debug getter fallo: {e}")

                printer.print_receipt(receipt_b64)
                return _jsonrpc_response(True, request_id)

            elif action == "cashbox":
                printer.open_cashbox()
                return _jsonrpc_response(True, request_id)

            else:
                logger.warning(f"[{printer.name}] Accion desconocida: {action!r}")
                return _jsonrpc_response(False, request_id)

        except Exception as e:
            logger.error(f"[{printer.name}] ERROR al imprimir: {e}")
            return _jsonrpc_response(False, request_id)

    @app.get("/printers")
    async def get_printers():
        try:
            return {
                "printer": {
                    "name": printer.name,
                    "windows_printer": printer.windows_printer,
                    "role": printer.role,
                    "paper_width": printer.paper_width,
                },
                "all_detected_in_system": list_printers(),
            }
        except Exception as e:
            return {"error": str(e)}

    return app
