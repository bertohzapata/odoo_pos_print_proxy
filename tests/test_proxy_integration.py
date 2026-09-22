"""
Integracion end-to-end: POS (JSON-RPC hw_proxy) -> proxy FastAPI -> Printer
-> backend de red -> impresora simulada. Sin uvicorn: se usa el transporte
ASGI de httpx. Cubre el flujo real que manda Odoo y la concurrencia (S4).
"""
import asyncio
import base64
import io

import httpx
from PIL import Image

from posprintproxy.daemon.printer_manager import Printer
from posprintproxy.daemon.proxy_server import create_app


ORIGIN = "https://tienda.com"


def _receipt_b64(w=180, h=60) -> str:
    img = Image.new("RGB", (w, h), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _make_app(fake_printer):
    printer = Printer(
        name="Cocina",
        role="kitchen",
        connection="network",
        host=fake_printer.host,
        tcp_port=fake_printer.port,
        paper_width=576,
    )
    return create_app(printer, ORIGIN, port=8073)


def _print_payload():
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "params": {"data": {"action": "print_receipt", "receipt": _receipt_b64()}},
    }


def test_print_receipt_reaches_network_printer(fake_printer):
    app = _make_app(fake_printer)

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/hw_proxy/default_printer_action",
                             json=_print_payload(), headers={"origin": ORIGIN})
            assert r.status_code == 200
            assert r.json()["result"] is True

    asyncio.run(run())
    assert fake_printer.wait_for_jobs(1)
    data = fake_printer.jobs[0]
    assert data.startswith(b"\x1b@")            # INIT
    assert b"\x1dv0" in data                     # GS v 0 raster


def test_cashbox_reaches_network_printer(fake_printer):
    app = _make_app(fake_printer)
    payload = {"jsonrpc": "2.0", "id": 2, "params": {"data": {"action": "cashbox"}}}

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/hw_proxy/default_printer_action",
                             json=payload, headers={"origin": ORIGIN})
            assert r.json()["result"] is True

    asyncio.run(run())
    assert fake_printer.wait_for_jobs(1)
    assert b"\x1bp" in fake_printer.jobs[0]       # ESC p (cajon)


def test_concurrent_devices_same_printer(fake_printer):
    """S4: N dispositivos imprimiendo simultaneo a la misma impresora 9100."""
    app = _make_app(fake_printer)
    N = 8

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            async def one(i):
                r = await c.post("/hw_proxy/default_printer_action",
                                 json=_print_payload(), headers={"origin": ORIGIN})
                assert r.status_code == 200
                assert r.json()["result"] is True
            await asyncio.gather(*(one(i) for i in range(N)))

    asyncio.run(run())
    assert fake_printer.wait_for_jobs(N, timeout=10.0)
    assert len(fake_printer.jobs) == N
    # Cada trabajo debe ser un ESC/POS completo e intacto (no intercalado):
    # empieza en INIT y contiene el raster.
    for job in fake_printer.jobs:
        assert job.startswith(b"\x1b@")
        assert b"\x1dv0" in job
