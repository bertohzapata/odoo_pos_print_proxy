#!/usr/bin/env python3
"""
scan_printers.py - Descubre impresoras termicas de RED en la LAN.

Escanea un rango de IPs buscando cuales tienen abierto el puerto 9100
(RAW/JetDirect ESC/POS). Sirve para saber que IP tiene cada impresora sin
adivinar, antes de configurarlas en la app.

Solo usa la libreria estandar. Correr en un equipo de la MISMA red que las
impresoras (no desde WSL si tu WSL no ve la LAN).

Uso:
    python scan_printers.py 192.168.1              # escanea .1 a .254
    python scan_printers.py 192.168.1.0/24
    python scan_printers.py 192.168.1 --port 9100 --timeout 0.4
    python scan_printers.py 192.168.1 --from 100 --to 130

Sugerencia: cada impresora imprime una hoja de auto-test con su IP y MAC al
encenderla (o al mantener 'FEED' mientras enciende). Con la MAC, en el router
puedes fijar la IP por reserva DHCP para que no cambie nunca.
"""
import argparse
import concurrent.futures as cf
import socket
import sys


def check(ip: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def parse_targets(base: str, lo: int, hi: int) -> tuple[str, list[int]]:
    """Acepta '192.168.1', '192.168.1.0/24' o '192.168.1.x'. Devuelve (prefijo, hosts)."""
    base = base.strip()
    if "/" in base:  # CIDR: solo soportamos /24
        net, bits = base.split("/")
        if bits != "24":
            print("Solo se soporta /24 (una subred clase C).", file=sys.stderr)
            sys.exit(2)
        parts = net.split(".")
        prefix = ".".join(parts[:3])
    else:
        parts = base.split(".")
        prefix = ".".join(parts[:3])
    return prefix, list(range(lo, hi + 1))


def main() -> int:
    ap = argparse.ArgumentParser(description="Escaner de impresoras de red (puerto 9100)")
    ap.add_argument("subnet", help="Prefijo de red, ej: 192.168.1  (o 192.168.1.0/24)")
    ap.add_argument("--port", type=int, default=9100)
    ap.add_argument("--timeout", type=float, default=0.4, help="Timeout por host (s)")
    ap.add_argument("--from", dest="lo", type=int, default=1, help="Ultimo octeto inicial")
    ap.add_argument("--to", dest="hi", type=int, default=254, help="Ultimo octeto final")
    ap.add_argument("--workers", type=int, default=128)
    args = ap.parse_args()

    prefix, hosts = parse_targets(args.subnet, args.lo, args.hi)
    print(f"Escaneando {prefix}.{args.lo}-{args.hi} en el puerto {args.port} ...\n")

    found: list[str] = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {
            ex.submit(check, f"{prefix}.{h}", args.port, args.timeout): f"{prefix}.{h}"
            for h in hosts
        }
        for fut in cf.as_completed(futs):
            ip = futs[fut]
            if fut.result():
                found.append(ip)
                print(f"  IMPRESORA: {ip}:{args.port}  (puerto 9100 abierto)")

    print()
    if found:
        found.sort(key=lambda ip: int(ip.split(".")[-1]))
        print(f"Encontradas {len(found)} impresora(s):")
        for ip in found:
            print(f"  - {ip}")
        print("\nSiguiente paso: reserva estas IPs por MAC en el router (reserva DHCP)")
        print("y agregalas en la app (Impresoras > Agregar > Red).")
    else:
        print("No se encontro ninguna impresora con el puerto 9100 abierto.")
        print("Revisa: misma subred, impresoras encendidas, cable de red, firewall.")
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
