"""
Printer backend for Windows using win32print.
Sends ESC/POS raster image commands to thermal printers via the Windows print spooler.
"""

import io
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
