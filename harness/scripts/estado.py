#!/usr/bin/env python3
"""Motor de estado del arnes SDD.

feature_list.json NO se edita a mano. Este script es el unico camino de mutacion:
valida las transiciones, exige autorizacion humana en los gates y aplica el
principio de congelamiento (lo que un agente ya leyo no cambia debajo de el).

Dos flujos conviven sobre la MISMA maquina de estados y los MISMOS gates:
  - light    (default): specify -> tasks, presupuestos duros.
  - estandar: spec-kit completo (clarify, plan, checklist, analyze...).
Ambos usan codebase-memory (investigacion + impacto) y grill-me (antes de cada
gate), asi que ambos exigen evidencia en disco para ciertos estados; estandar
exige ademas plan.md.

Retrocompatibilidad: una feature SIN campo `flujo` (creada con la version
anterior del arnes) se trata como light LEGADO: no se le exige evidencia y sus
transiciones son exactamente las de siempre. Las features nuevas siempre llevan
`flujo` explicito.

Ver AGENTS.md para el reglamento completo.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
LISTA = RAIZ / "feature_list.json"
BACKLOG = RAIZ / "backlog"
PLANTILLA = BACKLOG / "_PLANTILLA.md"

# Estados y transiciones legales. GATES exige --autoriza.
TRANSICIONES = {
    "backlog":         {"speccing"},
    "speccing":        {"spec_ready", "backlog"},
    "spec_ready":      {"in_progress"},
    "in_progress":     {"testing", "blocked"},
    "blocked":         {"in_progress"},
    "testing":         {"ready_to_close", "in_progress"},
    "ready_to_close":  {"done"},
    "done":            set(),
}
GATES = {"spec_ready", "done"}
ACTIVOS = {"speccing", "spec_ready", "in_progress", "blocked", "testing", "ready_to_close"}
TIPOS = {"nuevo", "actualizacion"}
FLUJOS = {"light", "estandar"}
FLUJO_POR_DEFECTO = "light"   # lista sin flujo_default, o feature sin campo => light
CAMPOS_EDITABLES = {
    "titulo", "descripcion", "tipo", "modulo", "prioridad", "depende_de",
    "notas", "tarea_actual", "bloqueo", "spec_dir", "rama", "flujo",
}
# Campos que solo se editan mientras nadie ha leido la feature (backlog), ni
# siquiera con --ciclo: cambian el carril entero.
SOLO_EN_BACKLOG = {"flujo"}
# Configuracion del proyecto (claves de primer nivel de feature_list.json).
CONFIG = {
    "flujo_default": FLUJOS,          # flujo que recibe una feature si no se indica
    "flujo_preguntar": {"si", "no"},  # /feature pregunta el flujo en cada alta
}

# Evidencia que cada flujo exige en disco para ENTRAR a un estado.
# (archivo relativo a spec_dir, texto que debe contener o None = basta que exista)
# grill.md lo escribe el orquestador en /validar (grill-me antes de cada gate);
# "## Impacto" lo escribe el implementador (codebase-memory) antes de soltar.
_COMUN = {
    "spec_ready": [("spec.md", None), ("tasks.md", None), ("grill.md", "## Gate 1")],
    "testing":    [("research.md", "## Impacto")],
    "done":       [("validacion-manual.md", None), ("grill.md", "## Gate 2")],
}
EVIDENCIA = {
    "light": _COMUN,
    "estandar": {**_COMUN, "spec_ready": [("plan.md", None)] + _COMUN["spec_ready"]},
}


def ahora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def morir(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def cargar():
    if not LISTA.exists():
        morir(f"no existe {LISTA}")
    return json.loads(LISTA.read_text(encoding="utf-8"))


def guardar(d):
    LISTA.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def buscar(d, fid):
    for f in d["features"]:
        if f["id"] == fid:
            return f
    morir(f"no existe la feature {fid}")


def flujo_de(f):
    return f.get("flujo") or FLUJO_POR_DEFECTO


def es_legado(f):
    """Feature creada antes de que existiera el campo flujo."""
    return "flujo" not in f


def config_de(d, clave):
    if clave == "flujo_default":
        return d.get("flujo_default") or FLUJO_POR_DEFECTO
    if clave == "flujo_preguntar":
        return d.get("flujo_preguntar") or "no"
    morir(f"clave de config desconocida '{clave}'")


def validar_flujo(valor):
    if valor not in FLUJOS:
        morir(f"flujo invalido '{valor}': usa {' o '.join(sorted(FLUJOS))}")


def exigir_evidencia(f, destino):
    """La transicion exige artefactos en disco segun el flujo. Legado: nada."""
    if es_legado(f):
        return
    flujo = flujo_de(f)
    reglas = EVIDENCIA[flujo].get(destino)
    if not reglas:
        return
    if not f.get("spec_dir"):
        morir(f"flujo {flujo}: '{destino}' exige spec_dir registrado "
              "(estado.sh editar <id> spec_dir specs/<NNN-slug> --ciclo)")
    base = RAIZ / f["spec_dir"]
    faltan = []
    for nombre, marca in reglas:
        ruta = base / nombre
        if not ruta.exists():
            faltan.append(f"{f['spec_dir']}/{nombre} (no existe)")
        elif marca and marca not in ruta.read_text(encoding="utf-8"):
            faltan.append(f"{f['spec_dir']}/{nombre} (falta la seccion '{marca}')")
    if faltan:
        morir(f"flujo {flujo}: '{destino}' exige evidencia que no esta:\n  - "
              + "\n  - ".join(faltan))


def slug(texto):
    s = texto.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)[:40].rstrip("-")
    return s or "feature"


# --------------------------------------------------------------------------- #
def cmd_agregar(a):
    d = cargar()
    if a.tipo not in TIPOS:
        morir(f"tipo invalido '{a.tipo}': usa {' o '.join(sorted(TIPOS))}")
    flujo = a.flujo or config_de(d, "flujo_default")
    validar_flujo(flujo)
    usados = [int(f["id"]) for f in d["features"]]
    fid = f"{(max(usados) + 1) if usados else 1:03d}"
    nombre = f"{fid}-{slug(a.titulo)}"
    brief = BACKLOG / f"{nombre}.md"
    if not brief.exists():
        base = PLANTILLA.read_text(encoding="utf-8") if PLANTILLA.exists() else "# {titulo}\n"
        brief.write_text(base.replace("<Titulo de la feature>", a.titulo), encoding="utf-8")
    d["features"].append({
        "id": fid,
        "titulo": a.titulo,
        "tipo": a.tipo,
        "flujo": flujo,
        "modulo": a.modulo,
        "estado": "backlog",
        "prioridad": a.prioridad,
        "depende_de": [x for x in (a.depende_de or "").split(",") if x],
        "brief": str(brief.relative_to(RAIZ)),
        "spec_dir": None,
        "rama": None,
        "tarea_actual": None,
        "bloqueo": None,
        "notas": a.notas,
        "validaciones": [],
        "creada": ahora(),
        "actualizada": ahora(),
    })
    guardar(d)
    print(f"OK  feature {fid} '{a.titulo}' ({a.tipo}, flujo {flujo}) en backlog")
    print(f"    brief: {brief.relative_to(RAIZ)}  <- describe aqui la funcionalidad")


def cmd_mover(a):
    d = cargar()
    f = buscar(d, a.id)
    origen, destino = f["estado"], a.estado
    if destino not in TRANSICIONES:
        morir(f"estado desconocido '{destino}'")
    if destino not in TRANSICIONES[origen]:
        legales = ", ".join(sorted(TRANSICIONES[origen])) or "ninguna (estado terminal)"
        morir(f"transicion ilegal {origen} -> {destino}. Desde {origen} solo: {legales}")
    if destino in GATES and not a.autoriza:
        morir(f"'{destino}' es un gate humano: exige --autoriza \"<nombre>\". "
              "Ningun subagente puede usarlo; solo el lider tras confirmacion explicita.")
    if destino in ACTIVOS and d["feature_activa"] not in (None, f["id"]):
        morir(f"ya hay una feature activa ({d['feature_activa']}): solo una a la vez")
    exigir_evidencia(f, destino)

    f["estado"] = destino
    f["actualizada"] = ahora()
    if a.autoriza:
        f["validaciones"].append({
            "gate": destino, "autoriza": a.autoriza,
            "fecha": ahora(), "nota": a.nota,
        })
    d["feature_activa"] = f["id"] if destino in ACTIVOS else None
    if destino == "done":
        f["tarea_actual"] = None
        f["bloqueo"] = None
    guardar(d)
    marca = "  [GATE autorizado por " + a.autoriza + "]" if a.autoriza else ""
    etiqueta = "light legado" if es_legado(f) else flujo_de(f)
    print(f"OK  {f['id']}  {origen} -> {destino}  [flujo {etiqueta}]{marca}")


def cmd_editar(a):
    d = cargar()
    f = buscar(d, a.id)
    if a.campo not in CAMPOS_EDITABLES:
        morir(f"campo no editable '{a.campo}'. Permitidos: {', '.join(sorted(CAMPOS_EDITABLES))}")
    if f["estado"] == "done":
        morir("una feature 'done' no se edita jamas: lo que le falto es una feature "
              "nueva de reparacion que la cite")
    if a.campo in SOLO_EN_BACKLOG and f["estado"] != "backlog":
        morir(f"'{a.campo}' solo se cambia en backlog (la feature esta en "
              f"'{f['estado']}'): cambia el carril entero. Aborta a backlog primero")
    if f["estado"] != "backlog" and not a.ciclo:
        morir(f"la feature esta en '{f['estado']}' (ya leida por el ciclo). Editarla "
              "exige --ciclo y queda como paso documentado del agente")
    valor = a.valor
    if a.campo == "depende_de":
        valor = [x for x in valor.split(",") if x]
    elif a.campo == "prioridad":
        valor = int(valor) if valor else None
    elif a.campo == "flujo":
        validar_flujo(valor)
    elif a.campo == "tipo" and valor not in TIPOS:
        morir(f"tipo invalido '{valor}': usa {' o '.join(sorted(TIPOS))}")
    f[a.campo] = valor
    f["actualizada"] = ahora()
    guardar(d)
    print(f"OK  {f['id']}.{a.campo} = {valor}")


def cmd_listar(a):
    d = cargar()
    act = d["feature_activa"]
    print(f"feature activa: {act or '(ninguna)'}   "
          f"flujo por defecto: {config_de(d, 'flujo_default')}\n")
    if not d["features"]:
        print("(backlog vacio - usa: estado.sh agregar --titulo ... --tipo ... --modulo ...)")
        return
    orden = sorted(
        d["features"],
        key=lambda f: (f["estado"] == "done", f["prioridad"] is None, f["prioridad"] or 0, f["id"]),
    )
    print(f"{'ID':<5} {'ESTADO':<15} {'TIPO':<14} {'FLUJO':<9} {'PRI':<4} {'MODULO':<26} TITULO")
    print("-" * 110)
    for f in orden:
        marca = "*" if f["id"] == act else " "
        pri = str(f["prioridad"]) if f["prioridad"] is not None else "-"
        flujo = flujo_de(f) + ("*" if es_legado(f) else "")
        print(f"{marca}{f['id']:<4} {f['estado']:<15} {f['tipo']:<14} {flujo:<9} {pri:<4} "
              f"{(f['modulo'] or '-'):<26} {f['titulo']}")
    if any(es_legado(f) for f in d["features"]):
        print("\n* legado: creada sin campo flujo; no se le exige evidencia (retrocompat)")


def cmd_activa(a):
    d = cargar()
    if not d["feature_activa"]:
        print("(ninguna feature activa)")
        return
    f = dict(buscar(d, d["feature_activa"]))
    if es_legado(f):   # explicito al leer; no se escribe en disco
        f["flujo"] = FLUJO_POR_DEFECTO
        f["legado"] = True
    print(json.dumps(f, indent=2, ensure_ascii=False))


def cmd_config(a):
    d = cargar()
    if a.clave is None:
        for k in sorted(CONFIG):
            print(f"{k} = {config_de(d, k)}")
        return
    if a.clave not in CONFIG:
        morir(f"clave desconocida '{a.clave}'. Permitidas: {', '.join(sorted(CONFIG))}")
    if a.valor is None:
        print(config_de(d, a.clave))
        return
    if a.valor not in CONFIG[a.clave]:
        morir(f"valor invalido '{a.valor}' para {a.clave}: usa {' o '.join(sorted(CONFIG[a.clave]))}")
    d[a.clave] = a.valor
    guardar(d)
    print(f"OK  config {a.clave} = {a.valor}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("agregar", help="alta de una feature en el backlog")
    a.add_argument("--titulo", required=True)
    a.add_argument("--tipo", required=True, help="nuevo | actualizacion")
    a.add_argument("--modulo", required=True, help="modulo destino (subdirectorio del codigo del proyecto)")
    a.add_argument("--prioridad", type=int, default=None, help="menor = antes")
    a.add_argument("--depende-de", dest="depende_de", default="", help="ids separados por coma")
    a.add_argument("--notas", default=None)
    a.add_argument("--flujo", default=None,
                   help="light | estandar (si se omite: flujo_default del proyecto, o light)")
    a.set_defaults(func=cmd_agregar)

    m = sub.add_parser("mover", help="transicion de estado")
    m.add_argument("id")
    m.add_argument("estado")
    m.add_argument("--autoriza", default=None, help="SOLO el lider, en gates, tras OK humano")
    m.add_argument("--nota", default=None)
    m.set_defaults(func=cmd_mover)

    e = sub.add_parser("editar", help="editar un campo")
    e.add_argument("id"); e.add_argument("campo"); e.add_argument("valor")
    e.add_argument("--ciclo", action="store_true", help="permite editar una feature ya en ciclo")
    e.set_defaults(func=cmd_editar)

    sub.add_parser("listar", help="ver el backlog").set_defaults(func=cmd_listar)
    sub.add_parser("activa", help="ver la feature activa").set_defaults(func=cmd_activa)

    c = sub.add_parser("config", help="ver o fijar la config del proyecto (flujo_default, flujo_preguntar)")
    c.add_argument("clave", nargs="?")
    c.add_argument("valor", nargs="?")
    c.set_defaults(func=cmd_config)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
