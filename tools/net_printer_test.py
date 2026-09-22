#!/usr/bin/env python3
"""
net_printer_test.py - Prueba de conectividad e impresion contra una impresora
termica de RED (raw ESC/POS, puerto 9100 / JetDirect).

Es la validacion literal de "la impresora Ethernet con IP fija imprime".
Corre en cualquier equipo de la LAN (Windows/Linux/Mac) sin instalar nada:
solo usa la libreria estandar. El test de imagen (--image) requiere Pillow.

Uso:
    python net_printer_test.py 192.168.1.50
    python net_printer_test.py 192.168.1.50 --port 9100 --width 576
    python net_printer_test.py 192.168.1.50 --image ticket.png
    python net_printer_test.py 192.168.1.50 --probe-only

Codigos de salida: 0 = OK, 1 = fallo de conexion/envio, 2 = args invalidos.
"""
import argparse
import socket
import sys
import time

ESC = b"\x1b"
GS = b"\x1d"
INIT = ESC + b"@"
CUT = GS + b"V" + b"\x00"
FEED3 = ESC + b"d" + b"\x03"
ALIGN_CENTER = ESC + b"a" + b"\x01"
ALIGN_LEFT = ESC + b"a" + b"\x00"
BOLD_ON = ESC + b"E" + b"\x01"
BOLD_OFF = ESC + b"E" + b"\x00"


def build_text_ticket() -> bytes:
    """Ticket de prueba simple, sin depender de Pillow."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    lines = bytearray()
    lines += INIT
    lines += ALIGN_CENTER + BOLD_ON
    lines += b"POS PRINT PROXY\n"
    lines += b"Test de impresora de red\n"
    lines += BOLD_OFF + ALIGN_LEFT
    lines += b"--------------------------------\n"
    lines += f"Fecha:  {ts}\n".encode("ascii", "replace")
    lines += b"Puerto: 9100 (raw ESC/POS)\n"
    lines += b"Estado: CONECTADO OK\n"
    lines += b"--------------------------------\n"
    lines += b"Si lees esto, la conectividad\n"
    lines += b"de red a la impresora funciona.\n"
    lines += FEED3
    lines += CUT
    return bytes(lines)


def build_image_ticket(path: str, width: int) -> bytes:
    """Rasteriza una imagen a ESC/POS (GS v 0). Requiere Pillow."""
    try:
        from PIL import Image
    except ImportError:
        print("ERROR: --image requiere Pillow (pip install Pillow).", file=sys.stderr)
        sys.exit(2)
    import struct

    image = Image.open(path)
    if image.width != width:
        ratio = width / image.width
        image = image.resize((width, int(image.height * ratio)), Image.LANCZOS)
    image = image.convert("1")
    w, h = image.width, image.height
    px = image.load()
    bpl = (w + 7) // 8

    data = bytearray()
    data += INIT
    data += GS + b"v0" + struct.pack("<B", 0)
    data += struct.pack("<H", bpl)
    data += struct.pack("<H", h)
    for y in range(h):
        for xb in range(bpl):
            byte = 0
            for bit in range(8):
                x = xb * 8 + bit
                if x < w and px[x, y] == 0:
                    byte |= 1 << (7 - bit)
            data.append(byte)
    data += FEED3
    data += CUT
    return bytes(data)


def main() -> int:
    ap = argparse.ArgumentParser(description="Prueba de impresora de red 9100")
    ap.add_argument("host", help="IP o hostname de la impresora")
    ap.add_argument("--port", type=int, default=9100, help="Puerto TCP (default 9100)")
    ap.add_argument("--width", type=int, default=576, help="Ancho papel px (576=80mm)")
    ap.add_argument("--image", help="Ruta a PNG/JPG a imprimir (requiere Pillow)")
    ap.add_argument("--timeout", type=float, default=8.0, help="Timeout socket (s)")
    ap.add_argument("--probe-only", action="store_true",
                    help="Solo verifica el puerto TCP, no imprime nada")
    args = ap.parse_args()

    # 1) Probe de conectividad
    print(f"[1/2] Conectando a {args.host}:{args.port} ...")
    t0 = time.time()
    try:
        conn = socket.create_connection((args.host, args.port), timeout=args.timeout)
    except OSError as e:
        dt = (time.time() - t0) * 1000
        print(f"  FALLO en {dt:.0f} ms: {e}", file=sys.stderr)
        print("\nRESULTADO: NO se pudo conectar. Revisa:", file=sys.stderr)
        print("  - IP correcta y fija (imprimir hoja de auto-test de la impresora)", file=sys.stderr)
        print("  - Cable Ethernet / misma subred / firewall", file=sys.stderr)
        print("  - Que la impresora acepte RAW en el puerto 9100", file=sys.stderr)
        return 1
    dt = (time.time() - t0) * 1000
    print(f"  OK: conexion establecida en {dt:.0f} ms")

    if args.probe_only:
        conn.close()
        print("\nRESULTADO: puerto alcanzable (probe-only). OK.")
        return 0

    # 2) Envio del trabajo
    payload = build_image_ticket(args.image, args.width) if args.image else build_text_ticket()
    kind = "imagen" if args.image else "ticket de texto"
    print(f"[2/2] Enviando {kind} ({len(payload)} bytes) ...")
    try:
        with conn:
            conn.settimeout(args.timeout)
            conn.sendall(payload)
    except OSError as e:
        print(f"  FALLO al enviar: {e}", file=sys.stderr)
        return 1

    print("  OK: datos enviados.")
    print("\nRESULTADO: revisa la impresora; debe haber salido un ticket. OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
