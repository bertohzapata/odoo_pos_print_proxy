"""Tests del backend de impresion de red (raw ESC/POS TCP 9100)."""
import io

from PIL import Image

from posprintproxy.daemon.printer_backend import (
    INIT,
    GS,
    print_image_network,
    open_cashbox_network,
    probe_network_printer,
    print_test_network,
)


def _png_bytes(w=200, h=80) -> bytes:
    img = Image.new("RGB", (w, h), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_print_image_network_sends_valid_escpos(fake_printer):
    ok = print_image_network(_png_bytes(), fake_printer.host, fake_printer.port, paper_width=576)
    assert ok
    assert fake_printer.wait_for_jobs(1)
    data = fake_printer.jobs[0]
    # Empieza con INIT (ESC @)
    assert data.startswith(INIT)
    # Contiene el comando raster GS v 0
    assert GS + b"v0" in data
    # Termina con corte GS V
    assert GS + b"V" in data[-8:]


def test_open_cashbox_network(fake_printer):
    ok = open_cashbox_network(fake_printer.host, fake_printer.port)
    assert ok
    assert fake_printer.wait_for_jobs(1)
    data = fake_printer.jobs[0]
    # Comando de cajon: ESC p 0 25 250
    assert b"\x1bp" in data


def test_test_ticket_network(fake_printer):
    assert print_test_network(fake_printer.host, fake_printer.port)
    assert fake_printer.wait_for_jobs(1)
    assert fake_printer.jobs[0].startswith(INIT)


def test_probe_reachable(fake_printer):
    assert probe_network_printer(fake_printer.host, fake_printer.port, timeout=2.0) is True


def test_probe_unreachable():
    # Puerto cerrado (nada escuchando)
    assert probe_network_printer("127.0.0.1", 1, timeout=1.0) is False
