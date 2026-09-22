"""Tests del esquema de config para impresoras de red."""
import pytest

from posprintproxy.daemon.config_manager import (
    PrinterConfig,
    _parse_printer,
    _parse,
)


def test_infers_network_from_host():
    p = _parse_printer({"name": "Cocina", "port": 8073, "host": "192.168.1.50"})
    assert p.connection == "network"
    assert p.host == "192.168.1.50"
    assert p.tcp_port == 9100
    assert p.windows_printer == ""


def test_printer_ip_alias():
    p = _parse_printer({"name": "Bar", "port": 8074, "printer_ip": "10.0.0.9", "tcp_port": 9101})
    assert p.connection == "network"
    assert p.host == "10.0.0.9"
    assert p.tcp_port == 9101


def test_usb_still_default():
    p = _parse_printer({"name": "Caja", "port": 8072, "windows_printer": "POS-80"})
    assert p.connection == "usb"
    assert p.windows_printer == "POS-80"


def test_explicit_network_connection():
    p = _parse_printer({
        "name": "Cocina", "port": 8073, "connection": "network",
        "host": "192.168.1.50", "tcp_port": 9100,
    })
    assert p.connection == "network"


def test_network_without_host_raises():
    with pytest.raises(ValueError, match="host"):
        PrinterConfig(name="X", port=8073, connection="network", host="")


def test_usb_without_driver_raises():
    with pytest.raises(ValueError, match="windows_printer"):
        PrinterConfig(name="X", port=8072, connection="usb", windows_printer="")


def test_invalid_connection_raises():
    with pytest.raises(ValueError, match="connection"):
        PrinterConfig(name="X", port=8072, connection="bluetooth", host="1.2.3.4")


def test_invalid_tcp_port_raises():
    with pytest.raises(ValueError, match="tcp_port"):
        PrinterConfig(name="X", port=8073, connection="network", host="1.2.3.4", tcp_port=0)


def test_full_config_mixed_usb_and_network():
    raw = {
        "odoo_domain": "https://tienda.com",
        "printers": [
            {"name": "Caja", "port": 8072, "windows_printer": "POS-80", "role": "receipt"},
            {"name": "Cocina", "port": 8073, "host": "192.168.1.50", "role": "kitchen"},
        ],
    }
    cfg = _parse(raw)
    assert len(cfg.printers) == 2
    assert cfg.printers[0].connection == "usb"
    assert cfg.printers[1].connection == "network"
    assert cfg.printers[1].host == "192.168.1.50"
