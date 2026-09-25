#!/usr/bin/env bash
# Puerta de lint del arnes: ruff SOLO sobre los .py que cambia la feature respecto a la
# rama de integracion (la deuda heredada no bloquea). Uso:
#   harness/scripts/lint.sh            # diff contra la rama de integracion + cambios sin commitear
#   harness/scripts/lint.sh --todo     # todo el repo (informativo, para medir la deuda)
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$RAIZ"
RUFF="$RAIZ/.venv/bin/ruff"
[ -x "$RUFF" ] || "$RAIZ/.venv/bin/python" -m pip install -q "ruff>=0.6"
# Rama de integracion unica (main) para todas las versiones de Odoo soportadas.
BASE="${PPP_BASE_BRANCH:-main}"

if [ "${1:-}" = "--todo" ]; then
  exec "$RUFF" check posprintproxy tests tools
fi

mapfile -t ARCHIVOS < <( { git diff --name-only --diff-filter=d "$BASE"...HEAD; git diff --name-only --diff-filter=d HEAD; git ls-files --others --exclude-standard; } \
  | grep -E '\.py$' | grep -v '^harness/' | sort -u || true)
if [ ${#ARCHIVOS[@]} -eq 0 ]; then
  echo "lint: sin archivos .py cambiados respecto a $BASE"; exit 0
fi
echo "lint: ${#ARCHIVOS[@]} archivo(s) cambiados respecto a $BASE"
exec "$RUFF" check "${ARCHIVOS[@]}"
