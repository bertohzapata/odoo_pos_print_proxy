"""
Printer backend for Windows using win32print.
Sends ESC/POS raster image commands to thermal printers via the Windows print spooler.
"""

import io
import socket
import struct
import logging

from PIL import Image

logger = logging.getLogger("pos_print_proxy")

# ESC/POS commands
ESC = b"\x1b"
GS = b"\x1d"
INIT = ESC + b"@"  # Initialize printer
CUT = GS + b"V" + b"\x00"  # Full cut
FEED = ESC + b"d" + b"\x03"  # Feed 3 lines

# Puerto estandar RAW/JetDirect de impresoras de red (ESC/POS crudo)
DEFAULT_TCP_PORT = 9100


def image_to_escpos_raster(image: Image.Image, paper_width: int = 576) -> bytes:
    """
    Convert a PIL Image to ESC/POS raster bit-image commands.

    Args:
        image: PIL Image (any mode, will be converted to 1-bit)
        paper_width: Width in pixels (576 for 80mm @ 203dpi)

    Returns:
        bytes: ESC/POS raster commands ready to send to printer
    """
    # Resize to paper width maintaining aspect ratio
    if image.width != paper_width:
        ratio = paper_width / image.width
        new_height = int(image.height * ratio)
        image = image.resize((paper_width, new_height), Image.LANCZOS)

    # Convert to 1-bit (black and white)
    image = image.convert("1")

    width = image.width
    height = image.height
    pixels = image.load()

    # Bytes per line (8 pixels per byte)
    bytes_per_line = (width + 7) // 8

    # Build raster data using GS v 0 (print raster bit image)
    # GS v 0 m xL xH yL yH [data]
    # m = 0 (normal), xL xH = bytes per line, yL yH = number of lines
    data = bytearray()
    data += INIT
    data += GS + b"v0" + struct.pack("<B", 0)
    data += struct.pack("<H", bytes_per_line)
    data += struct.pack("<H", height)

    for y in range(height):
        for x_byte in range(bytes_per_line):
            byte_val = 0
            for bit in range(8):
                x = x_byte * 8 + bit
                if x < width:
                    pixel = pixels[x, y]
                    if pixel == 0:  # black
                        byte_val |= 1 << (7 - bit)
            data.append(byte_val)

    data += FEED
    data += CUT

    return bytes(data)


def print_image_win32(image_bytes: bytes, printer_name: str, paper_width: int = 576) -> bool:
    """
    Print a JPEG/PNG image to a Windows printer using ESC/POS commands.

    Args:
        image_bytes: Raw image file bytes (JPEG or PNG)
        printer_name: Name of the printer as it appears in Windows
        paper_width: Paper width in pixels

    Returns:
        True if printing succeeded
    """
    import win32print

    image = Image.open(io.BytesIO(image_bytes))
    escpos_data = image_to_escpos_raster(image, paper_width)

    printer_handle = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(printer_handle, 1, ("POS Receipt", None, "RAW"))
        try:
            win32print.StartPagePrinter(printer_handle)
            win32print.WritePrinter(printer_handle, escpos_data)
            win32print.EndPagePrinter(printer_handle)
        finally:
            win32print.EndDocPrinter(printer_handle)
    finally:
        win32print.ClosePrinter(printer_handle)

    logger.info(f"Printed to '{printer_name}' ({len(escpos_data)} bytes)")
    return True


def open_cashbox_win32(printer_name: str) -> bool:
    """Send cash drawer open command to the printer."""
    import win32print

    cashbox_cmd = INIT + ESC + b"p" + bytes([0, 25, 250])

    printer_handle = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(printer_handle, 1, ("Cashbox", None, "RAW"))
        try:
            win32print.StartPagePrinter(printer_handle)
            win32print.WritePrinter(printer_handle, cashbox_cmd)
            win32print.EndPagePrinter(printer_handle)
        finally:
            win32print.EndDocPrinter(printer_handle)
    finally:
        win32print.ClosePrinter(printer_handle)

    logger.info(f"Cashbox opened on '{printer_name}'")
    return True


def list_printers() -> list[str]:
    """List available printers on this Windows system."""
    import win32print

    printers = win32print.EnumPrinters(2)  # PRINTER_ENUM_LOCAL
    return [p[2] for p in printers]


# ============================================================================
# Backend de RED (raw ESC/POS sobre TCP, puerto 9100 / JetDirect)
# ============================================================================
# Multiplataforma: no depende de win32print. Sirve para impresoras termicas
# genericas con Ethernet/WiFi que aceptan ESC/POS crudo en el puerto 9100.
# El pipeline imagen -> ESC/POS raster (image_to_escpos_raster) es el mismo
# que el backend USB; solo cambia el transporte (socket en vez de spooler).


def _send_raw(host: str, port: int, data: bytes, timeout: float = 10.0) -> None:
    """
    Abre una conexion TCP corta a la impresora de red y envia bytes crudos.

    Conexion corta (una por trabajo) a proposito: el puerto 9100 atiende una
    conexion a la vez, asi que mantenerla abierta bloquearia a otros
    dispositivos. La cola/serializacion la maneja la capa superior (Printer).
    """
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(data)


def print_image_network(
    image_bytes: bytes,
    host: str,
    port: int = DEFAULT_TCP_PORT,
    paper_width: int = 576,
    timeout: float = 10.0,
) -> bool:
    """
    Imprime una imagen JPEG/PNG en una impresora de red via ESC/POS raster.

    Args:
        image_bytes: bytes crudos del archivo de imagen (JPEG o PNG)
        host: IP o hostname de la impresora de red
        port: puerto TCP (default 9100)
        paper_width: ancho de papel en pixeles (576 = 80mm, 384 = 58mm)

    Returns:
        True si el envio tuvo exito.
    """
    image = Image.open(io.BytesIO(image_bytes))
    escpos_data = image_to_escpos_raster(image, paper_width)
    _send_raw(host, port, escpos_data, timeout)
    logger.info(f"Printed to {host}:{port} ({len(escpos_data)} bytes)")
    return True


def open_cashbox_network(
    host: str,
    port: int = DEFAULT_TCP_PORT,
    timeout: float = 10.0,
) -> bool:
    """Envia el comando de apertura de cajon a una impresora de red."""
    cashbox_cmd = INIT + ESC + b"p" + bytes([0, 25, 250])
    _send_raw(host, port, cashbox_cmd, timeout)
    logger.info(f"Cashbox opened on {host}:{port}")
    return True


def probe_network_printer(
    host: str,
    port: int = DEFAULT_TCP_PORT,
    timeout: float = 3.0,
) -> bool:
    """
    Verifica conectividad TCP con la impresora de red (no imprime nada).
    Retorna True si el puerto acepta la conexion.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ============================================================================
# Ticket de prueba (usado por el boton "Imprimir prueba" de la GUI)
# ============================================================================

def _build_test_ticket() -> bytes:
    """Ticket de texto simple, sin depender de una imagen."""
    import time

    align_center = ESC + b"a" + b"\x01"
    align_left = ESC + b"a" + b"\x00"
    bold_on = ESC + b"E" + b"\x01"
    bold_off = ESC + b"E" + b"\x00"

    t = bytearray()
    t += INIT
    t += align_center + bold_on
    t += b"POS PRINT PROXY\n"
    t += b"Impresion de prueba\n"
    t += bold_off + align_left
    t += b"--------------------------------\n"
    t += time.strftime("%Y-%m-%d %H:%M:%S\n").encode("ascii", "replace")
    t += b"Si lees esto, la impresora\n"
    t += b"esta configurada correctamente.\n"
    t += FEED
    t += CUT
    return bytes(t)


def print_test_network(host: str, port: int = DEFAULT_TCP_PORT, timeout: float = 8.0) -> bool:
    """Imprime un ticket de prueba en una impresora de red."""
    _send_raw(host, port, _build_test_ticket(), timeout)
    logger.info(f"Test print sent to {host}:{port}")
    return True


def print_test_win32(printer_name: str) -> bool:
    """Imprime un ticket de prueba en una impresora USB (spooler Windows)."""
    import win32print

    data = _build_test_ticket()
    handle = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(handle, 1, ("POS Test", None, "RAW"))
        try:
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, data)
            win32print.EndPagePrinter(handle)
        finally:
            win32print.EndDocPrinter(handle)
    finally:
        win32print.ClosePrinter(handle)
    logger.info(f"Test print sent to '{printer_name}'")
    return True
