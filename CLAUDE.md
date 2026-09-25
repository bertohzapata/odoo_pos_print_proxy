# CLAUDE.md

Este repo se desarrolla con el arnés SDD: **lee `AGENTS.md` antes de actuar** (reglamento,
máquina de estados, roles) y `.specify/memory/constitution.md` (reglas no negociables).
Interfaz del propietario: `/feature`, `/ciclo`, `/validar`, `/probar` — ver `docs/guia-rapida.md`.

Datos rápidos:

- App: `python -m posprintproxy` (GUI) o `--daemon` (headless). Código en `posprintproxy/`.
- Pruebas: `harness/scripts/test-env.sh probar app`; sandbox con impresora 9100 simulada:
  `harness/scripts/test-env.sh levantar` (proxy en `:8172`, porque el Odoo local de Docker usa `:8072`).
- Lint: `harness/scripts/lint.sh` (solo archivos cambiados vs la rama de integración).
- Ramas: una línea por versión de Odoo (`odoo_v19` hoy). Los addons Odoo van en el repo de su
  versión (`~/odoo19_community/ixim_addons/`), no aquí.
- Historia y roadmap: `HITOS.md`; definición de la app: `ESPECIFICACIONES.md`.
