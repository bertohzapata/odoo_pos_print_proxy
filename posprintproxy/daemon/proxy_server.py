"""
Fabrica una instancia FastAPI por impresora, con los endpoints del protocolo
IoT Box de Odoo. Cada instancia:

- Escucha en su propio puerto
- Tiene su propio middleware CORS+PNA
- Tiene su propio "state" (para loggear "POS conectado" una sola vez)
- Dispatcha las impresiones a su Printer especifico
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse, Response

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


def create_app(printer: Printer, allowed_origin: str) -> FastAPI:
    """Fabrica una FastAPI dedicada a una impresora."""
    app = FastAPI(
        title=f"POS Print Proxy - {printer.name}",
        version="2.0.0",
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
