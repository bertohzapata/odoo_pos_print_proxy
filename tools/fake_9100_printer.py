#!/usr/bin/env python3
"""
fake_9100_printer.py - Impresora termica de RED SIMULADA.

Escucha en un puerto TCP (default 9100) haciendo de "sink": acepta cada
conexion, lee todos los bytes ESC/POS que le manden, los guarda a un archivo
y loguea un resumen (bytes, si empieza con INIT, si trae GS v 0, si termina en
corte). Permite validar el backend de red y el flujo completo Odoo->proxy->
impresora en WSL, sin hardware fisico.

Uso:
    python fake_9100_printer.py                 # 0.0.0.0:9100, guarda en ./captures
    python fake_9100_printer.py --port 9101
    python fake_9100_printer.py --outdir /tmp/caps --quiet

Maneja conexiones concurrentes (un hilo por conexion) para probar impresion
multi-dispositivo simultanea.
"""
import argparse
import datetime as dt
import itertools
import socket
import threading
from pathlib import Path

ESC = b"\x1b"
GS = b"\x1d"
INIT = ESC + b"@"
GSV0 = GS + b"v0"
CUT = GS + b"V"  # cualquier variante de corte GS V ...

_counter = itertools.count(1)
_print_lock = threading.Lock()


def _summary(data: bytes) -> str:
    checks = [
        ("INIT(ESC @)", data.startswith(INIT) or INIT in data[:8]),
        ("GS v 0 raster", GSV0 in data),
        ("corte(GS V)", CUT in data[-8:]),
    ]
    return "  ".join(f"{name}={'si' if ok else 'NO'}" for name, ok in checks)


def handle(conn: socket.socket, addr, outdir: Path, quiet: bool) -> None:
    n = next(_counter)
    chunks = bytearray()
    try:
        conn.settimeout(10.0)
        while True:
            buf = conn.recv(65536)
            if not buf:
                break
            chunks += buf
    except OSError:
        pass
    finally:
        conn.close()

    data = bytes(chunks)
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    fname = outdir / f"job_{ts}_{n:04d}_{addr[0].replace(':', '_')}.escpos"
    fname.write_bytes(data)

    with _print_lock:
        if not quiet:
            print(f"[job {n:04d}] {addr[0]}:{addr[1]}  {len(data)} bytes  -> {fname.name}")
            print(f"           {_summary(data)}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Impresora de red 9100 simulada (sink)")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=9100)
    ap.add_argument("--outdir", default="captures", help="Carpeta donde guardar los trabajos")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.host, args.port))
    srv.listen(16)
    print(f"Impresora simulada escuchando en {args.host}:{args.port}")
    print(f"Guardando trabajos en: {outdir.resolve()}")
    print("Ctrl+C para detener.\n")

    try:
        while True:
            conn, addr = srv.accept()
            threading.Thread(
                target=handle, args=(conn, addr, outdir, args.quiet), daemon=True
            ).start()
    except KeyboardInterrupt:
        print("\nDetenido.")
    finally:
        srv.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
