#!/usr/bin/env bash
# Entorno de pruebas del proyecto POS Print Proxy. Contrato fijo que usan los agentes,
# skills y AGENTS.md — NO cambies los nombres de los subcomandos, solo su implementación:
#
#   test-env.sh arriba              prepara el venv (.venv) con requirements-dev
#   test-env.sh abajo               detiene el sandbox (daemon + impresora simulada)
#   test-env.sh instalar <modulo>   instalacion limpia: deps + caches borradas + import del modulo
#   test-env.sh probar <modulo>     corre la suite pytest (tests/)
#   test-env.sh levantar [<modulo>] daemon headless + impresora 9100 simulada, para verificar a mano
#   test-env.sh limpiar <modulo>    borra el sandbox (config, capturas, logs)
#   test-env.sh estado              dice si esta encendido
#
# Modulos validos: subpaquetes de posprintproxy/ (daemon, gui, util) o "app" (todo el paquete).
# Los addons Odoo NO se prueban aqui: viven en el repo de su version (odoo19_community).
# Ciclo de vida: lo enciende el orquestador al arrancar un ciclo y lo apaga al cerrarlo.
# Ver AGENTS.md (rol tester) y la constitucion.
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
VENV="$RAIZ/.venv"
PY="$VENV/bin/python"
SANDBOX="$RAIZ/harness/.sandbox"
PROXY_PORT="${PPP_PROXY_PORT:-8172}"     # 8072 lo ocupa el Odoo local de Docker
FAKE_PORT="${PPP_FAKE_PORT:-9101}"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"   # importar la GUI sin display

modulo_valido() {
  case "${1:-}" in
    app) ;;
    daemon|gui|util) [ -d "$RAIZ/posprintproxy/$1" ] || { echo "ERROR: no existe posprintproxy/$1" >&2; exit 1; } ;;
    *) echo "ERROR: modulo '${1:-}' invalido. Usa: app | daemon | gui | util" >&2; exit 1 ;;
  esac
}

vivo() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }

arriba() {
  if [ ! -x "$PY" ]; then
    python3 -m venv "$VENV"
  fi
  "$PY" -m pip install -q -r "$RAIZ/requirements-dev.txt"
  echo "venv listo: $("$PY" --version) en $VENV"
}

abajo() {
  for p in daemon fake; do
    if vivo "$SANDBOX/$p.pid"; then kill "$(cat "$SANDBOX/$p.pid")" && echo "detenido: $p"; fi
    rm -f "$SANDBOX/$p.pid"
  done
  echo "sandbox apagado"
}

estado() {
  local ok=0
  if [ -x "$PY" ] && "$PY" -c "import fastapi, uvicorn, PIL, yaml, pytest" 2>/dev/null; then
    echo "venv: OK"
  else
    echo "venv: NO LISTO (falta 'arriba')"; ok=1
  fi
  vivo "$SANDBOX/fake.pid"   && echo "impresora simulada: encendida (127.0.0.1:$FAKE_PORT)" || echo "impresora simulada: apagada"
  vivo "$SANDBOX/daemon.pid" && echo "daemon sandbox: encendido (puerto $PROXY_PORT)"        || echo "daemon sandbox: apagado"
  return $ok
}

instalar() {
  modulo_valido "${1:-}"
  [ -x "$PY" ] || arriba
  "$PY" -m pip install -q -r "$RAIZ/requirements-dev.txt"
  # Limpio = sin bytecode ni cache de pytest que escondan un fallo real.
  find "$RAIZ/posprintproxy" "$RAIZ/tests" -type d -name __pycache__ -prune -exec rm -rf {} +
  rm -rf "$RAIZ/.pytest_cache"
  local objetivo="posprintproxy"
  [ "$1" != "app" ] && objetivo="posprintproxy.$1"
  cd "$RAIZ"
  "$PY" - "$objetivo" <<'EOF'
import importlib, pkgutil, sys
raiz = importlib.import_module(sys.argv[1])
n = 1
if hasattr(raiz, "__path__"):
    for m in pkgutil.walk_packages(raiz.__path__, raiz.__name__ + "."):
        if m.name.endswith("__main__"):
            continue
        importlib.import_module(m.name)
        n += 1
print(f"import limpio OK: {sys.argv[1]} ({n} modulos)")
EOF
}

probar() {
  modulo_valido "${1:-}"
  [ -x "$PY" ] || arriba
  cd "$RAIZ"
  # La suite es chica (segundos): se corre completa para cualquier modulo.
  "$PY" -m pytest tests -q
}

levantar() {
  [ -x "$PY" ] || arriba
  mkdir -p "$SANDBOX/captures"
  if [ ! -f "$SANDBOX/config.yaml" ]; then
    cat > "$SANDBOX/config.yaml" <<EOF
# Config del sandbox de desarrollo (generado por test-env.sh). Editable.
odoo_domain: "http://localhost:8069"
verbose: true
log_dir: "logs"
log_retention_days: 3
kill_zombies_on_startup: false
printers:
  - name: "Sandbox-Red"
    port: $PROXY_PORT
    connection: network
    host: "127.0.0.1"
    tcp_port: $FAKE_PORT
    paper_width: 576
    role: both
EOF
  fi
  if ! vivo "$SANDBOX/fake.pid"; then
    nohup "$PY" "$RAIZ/tools/fake_9100_printer.py" --host 127.0.0.1 --port "$FAKE_PORT" \
      --outdir "$SANDBOX/captures" < /dev/null > "$SANDBOX/fake.log" 2>&1 &
    echo $! > "$SANDBOX/fake.pid"
  fi
  if ! vivo "$SANDBOX/daemon.pid"; then
    # En desarrollo el daemon lee config.yaml del cwd (util/paths.py): cwd = sandbox.
    # env -C hace exec: el pid guardado es el del python (no un subshell que retenga el pipe).
    PYTHONPATH="$RAIZ" nohup env -C "$SANDBOX" "$PY" -m posprintproxy --daemon \
      < /dev/null > "$SANDBOX/daemon.log" 2>&1 &
    echo $! > "$SANDBOX/daemon.pid"
  fi
  sleep 3
  vivo "$SANDBOX/fake.pid"   || { echo "ERROR: la impresora simulada no arranco:"; tail -20 "$SANDBOX/fake.log"; exit 1; }
  vivo "$SANDBOX/daemon.pid" || { echo "ERROR: el daemon no arranco:"; tail -30 "$SANDBOX/daemon.log"; exit 1; }
  echo "sandbox arriba:"
  echo "  proxy:     puerto $PROXY_PORT  (prueba: curl -sk http(s)://localhost:$PROXY_PORT/hw_proxy/hello)"
  echo "  impresora: 127.0.0.1:$FAKE_PORT  -> capturas ESC/POS en $SANDBOX/captures"
  echo "  logs:      $SANDBOX/daemon.log, $SANDBOX/fake.log"
  echo "  GUI (solo en Windows/escritorio): python -m posprintproxy"
}

limpiar() {
  abajo >/dev/null
  rm -rf "$SANDBOX"
  echo "sandbox borrado"
}

case "${1:-}" in
  arriba)   arriba ;;
  estado)   estado ;;
  abajo)    abajo ;;
  instalar) instalar "${2:-}" ;;
  probar)   probar "${2:-}" ;;
  levantar) levantar ;;
  limpiar)  limpiar ;;
  *) sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
