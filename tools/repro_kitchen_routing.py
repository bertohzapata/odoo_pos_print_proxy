#!/usr/bin/env python3
"""
repro_kitchen_routing.py - Reproduce el enrutado de comandas de Odoo POS a
impresoras de preparacion, usando impresoras de RED simuladas + el backend
real del proxy (posprintproxy.daemon.printer_manager.Printer).

Objetivo: demostrar, con evidencia, que:
  1) La CATEGORIA de cada pos.printer decide QUE imprime (filtro estricto).
  2) El proxy_ip/PUERTO decide DONDE imprime.
  3) La duplicacion "cada item 2 veces" aparece cuando dos pos.printer
     comparten categorias (solapadas) y/o el mismo puerto fisico.

La logica de filtrado espeja la real de Odoo 19:
  point_of_sale/static/src/app/services/pos_store.js
    -> printChanges(): for (printer) { changes = filter por printer.categorias }
    -> filterChangeByCategories(): una linea pasa si la categoria del producto
       esta en las categorias de esa impresora.
"""
import base64
import io
import socket
import sys
import threading
import time
from pathlib import Path

# Permitir importar el paquete del proxy
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402
from posprintproxy.daemon.printer_manager import Printer  # noqa: E402


# ----------------------------------------------------------------------------
# Impresora de red simulada (sink TCP) con puerto efimero
# ----------------------------------------------------------------------------
class Sink:
    def __init__(self, label: str):
        self.label = label
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(8)
        self.host, self.port = self._srv.getsockname()
        self.jobs: list[int] = []  # bytes por trabajo
        self._stop = False
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while not self._stop:
            try:
                c, _ = self._srv.accept()
            except OSError:
                break
            threading.Thread(target=self._recv, args=(c,), daemon=True).start()

    def _recv(self, c):
        data = bytearray()
        c.settimeout(3.0)
        try:
            while True:
                b = c.recv(65536)
                if not b:
                    break
                data += b
        except OSError:
            pass
        finally:
            c.close()
        self.jobs.append(len(data))

    def close(self):
        self._stop = True
        self._srv.close()


# ----------------------------------------------------------------------------
# Logica de Odoo (espejo de filterChangeByCategories)
# ----------------------------------------------------------------------------
def odoo_filter(order_lines, printer_cats):
    """Devuelve las lineas cuya categoria esta en las categorias de la impresora."""
    return [ln for ln in order_lines if ln["cat"] in printer_cats]


def render_ticket(lines) -> str:
    """Renderiza un ticket (imagen) con los nombres, como hace Odoo. Devuelve b64."""
    img = Image.new("RGB", (384, 30 + 24 * len(lines)), "white")
    d = ImageDraw.Draw(img)
    d.text((8, 6), "COMANDA", fill="black")
    for i, ln in enumerate(lines):
        d.text((8, 30 + 24 * i), f"1x {ln['name']}", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ----------------------------------------------------------------------------
# Escenario
# ----------------------------------------------------------------------------
def run_scenario(title, printers_spec, order):
    """
    printers_spec: lista de dicts {name, cats, sink}
    Imprime el enrutado (decision de Odoo) y envia por el backend real del proxy.
    """
    print("=" * 70)
    print(title)
    print("-" * 70)
    print(f"Pedido: {[l['name']+'('+l['cat']+')' for l in order]}")
    print()

    # Contadores de cuantas veces se imprime cada item en TODO el sistema
    item_prints: dict[str, int] = {l["name"]: 0 for l in order}

    for spec in printers_spec:
        lines = odoo_filter(order, spec["cats"])
        sink = spec["sink"]
        if not lines:
            print(f"  [{spec['name']:7} cats={spec['cats']!s:16}] -> nada que imprimir")
            continue
        names = [l["name"] for l in lines]
        for n in names:
            item_prints[n] += 1
        # Enviar por el backend REAL del proxy (socket ESC/POS a la simulada)
        printer = Printer(name=spec["name"], connection="network",
                          host=sink.host, tcp_port=sink.port, paper_width=384)
        printer.print_receipt(render_ticket(lines))
        print(f"  [{spec['name']:7} cats={spec['cats']!s:16}] -> "
              f"impresora simulada '{sink.label}' (puerto {sink.port}): {names}")

    time.sleep(0.3)  # dejar que las simuladas registren
    print()
    print("  Resultado en las impresoras fisicas simuladas:")
    seen = {}
    for spec in printers_spec:
        s = spec["sink"]
        if s.label not in seen:
            seen[s.label] = s
    for label, s in seen.items():
        print(f"    - '{label}' (puerto {s.port}): {len(s.jobs)} ticket(s) recibido(s)")

    print()
    print("  Veces que se imprime cada item en el sistema:")
    dup = False
    for name, n in item_prints.items():
        flag = "  <-- DUPLICADO" if n > 1 else ""
        if n > 1:
            dup = True
        print(f"    - {name}: {n}{flag}")
    print()
    if dup:
        print("  >>> HAY DUPLICACION.")
    else:
        print("  >>> Sin duplicacion: cada item sale exactamente una vez.")
    print()


def main():
    order = [{"name": "Mochi", "cat": "food"}, {"name": "Bebida", "cat": "drink"}]

    # Sinks (impresoras fisicas simuladas). Uno fresco por escenario para que
    # el conteo de tickets no se acumule entre escenarios.
    cocina = Sink("Cocina-fisica")
    barra = Sink("Barra-fisica")
    una_sola = Sink("UNA-fisica")
    una_sola3 = Sink("UNA-fisica")

    try:
        # ------------------------------------------------------------------
        run_scenario(
            "ESCENARIO 1 - CORRECTO: 1 categoria por impresora, PUERTOS distintos",
            [
                {"name": "Cocina", "cats": ["food"], "sink": cocina},
                {"name": "Barra", "cats": ["drink"], "sink": barra},
            ],
            order,
        )

        # ------------------------------------------------------------------
        run_scenario(
            "ESCENARIO 2 - TU BUG PROBABLE: categorias SOLAPADAS + MISMO puerto\n"
            "(2 pos.printer, ambas con food+drink, ambas a la misma impresora fisica)",
            [
                {"name": "Prep1", "cats": ["food", "drink"], "sink": una_sola},
                {"name": "Prep2", "cats": ["food", "drink"], "sink": una_sola},
            ],
            order,
        )

        # ------------------------------------------------------------------
        run_scenario(
            "ESCENARIO 3 - categorias correctas pero MISMO puerto (1 impresora fisica)\n"
            "(2 tickets salen de la misma impresora, pero cada item una sola vez)",
            [
                {"name": "Cocina", "cats": ["food"], "sink": una_sola3},
                {"name": "Barra", "cats": ["drink"], "sink": una_sola3},
            ],
            order,
        )

        print("=" * 70)
        print("CONCLUSION")
        print("-" * 70)
        print("- El trago (drink) SOLO llega a la impresora cuya categoria lo incluye.")
        print("  Una impresora de solo 'food' NUNCA imprime 'drink' (Escenario 1).")
        print("- La duplicacion 'cada item 2 veces' NO viene de tener 1 puerto:")
        print("  viene de CATEGORIAS SOLAPADAS (Escenario 2). Revisa que cada")
        print("  pos.printer en linea tenga UNA sola categoria distinta y que ningun")
        print("  producto este en dos categorias que ambas impresoras impriman.")
    finally:
        cocina.close()
        barra.close()
        una_sola.close()
        una_sola3.close()


if __name__ == "__main__":
    main()
