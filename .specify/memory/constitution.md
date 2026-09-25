<!--
Sync Impact Report
- Versión: 1.0.0 → 2.0.0 (MAJOR: se redefine el Principio III y el modelo de ramas de forma
  incompatible con la regla anterior de "una rama por versión de Odoo").
- Principios modificados:
  - III. "Contrato con el POS de Odoo por Versión" → "Contratos por Versión de Odoo en una Sola Línea"
- Secciones modificadas: Restricciones Técnicas (Prohibido), Flujo de Desarrollo → Modelo de
  ramas, Cierre → Commits.
- Secciones añadidas: ninguna. Secciones eliminadas: ninguna.
- Motivo: Odoo 19 y 20 conviven a largo plazo en las tiendas; Odoo 20 Community ya no tiene
  cliente IoT Box y solo imprime por Epson ePOS. Una rama por versión duplicaría GUI, backend e
  installer, y el auto-update (`releases/latest` de un solo repo) llevaría tiendas de 19 a builds
  solo de 20.
- Plan de migración: renombrar `odoo_v19` → `main` (local y remoto, con confirmación del
  propietario); `harness/scripts/lint.sh` PPP_BASE_BRANCH → `main`; AGENTS.md §9 y CLAUDE.md
  alineados en el mismo cambio. Tags v2.0.x y canal de releases no cambian.
- Plantillas dependientes: sin cambios (leen la constitución en tiempo de ejecución).
- TODOs diferidos: ninguno.
-->
# POS Print Proxy Constitution

## Core Principles

### I. Validación Manual Primero, Pruebas Acotadas

Ninguna funcionalidad se considera terminada sin que el propietario la haya validado a mano.

- La **validación manual de Humberto Zapata es la puerta de calidad principal**. El tester
  escribe una guía de **máximo 10 pasos**; el propietario la ejecuta; su resultado decide el
  cierre.
- Todo módulo MUST instalar/arrancar limpio desde cero (`test-env.sh instalar <modulo>`) y pasar
  `harness/scripts/lint.sh`. Esas son las comprobaciones automáticas obligatorias por defecto.
- Las pruebas automatizadas MUST limitarse a lo que la validación manual **no puede observar**:
  valores por defecto, comportamiento sin una dependencia opcional, validaciones que deben
  rechazar. Ajusta aquí un techo de volumen si tu proyecto lo necesita (ej. "no más del 25% de
  las líneas de código funcional del módulo").
- Escribir una prueba end-to-end por cada historia de usuario está **desaconsejado** por
  defecto: se justifica por escrito, caso por caso.
- Cada entrega MUST reportar el comando exacto ejecutado y su salida real. Declarar "los tests
  pasan" sin haberlos corrido es una violación de esta constitución.

**Rationale**: la automatización exhaustiva tiene un costo cierto (tiempo de cómputo, líneas de
prueba que mantener) contra un riesgo esperado que casi siempre es menor de lo que parece antes
de medirlo. La validación manual acotada, hecha por quien de verdad usa el producto, encuentra
lo que importa más rápido que una suite que nadie termina de correr.

### II. Verificar, No Asumir

Toda afirmación sobre factibilidad o comportamiento (offline, compatibilidad con una versión de
Odoo, soporte de una impresora) MUST estar respaldada por código leído, documentación oficial o
una prueba ejecutada, citada en `research.md`. Lo no comprobado se marca como **supuesto/spike**,
nunca como hecho.

**Rationale**: el propietario perdió confianza cuando se afirmó que el proxy "preservaba el modo
offline" sin validarlo. Un supuesto marcado cuesta una línea; uno escondido cuesta una tienda.

### III. Contratos por Versión de Odoo en una Sola Línea

Una sola base de código e installer atiende todas las versiones de Odoo soportadas (hoy 19 y 20).
El contrato HTTP que consume el POS es por versión y MUST vivir en su propio módulo de protocolo
dentro de `posprintproxy/daemon/` (IoT Box `/hw_proxy/*` para Odoo 19; Epson ePOS
`/cgi-bin/epos/service.cgi` para Odoo 20), aislado de los demás.

- Un cambio a un contrato MUST citar el código JS de Odoo de **esa** versión que lo consume.
- Añadir o cambiar un protocolo MUST NOT romper los otros: cada protocolo conserva sus pruebas
  y toda entrega verifica la regresión de las versiones ya soportadas.
- La lógica compartida (raster ESC/POS, transporte USB/red, config, GUI) no depende de ningún
  protocolo concreto.
- Los addons Odoo de apoyo MUST vivir en el repo de su versión de Odoo (hoy
  `~/odoo19_community/ixim_addons/` para 19), no en este repo.

### IV. La Impresión No Se Pierde

Un fallo de impresora (red caída, USB desconectado, spooler) MUST reportarse al POS como error
y quedar en el log con causa; nunca un éxito silencioso. Toda ruta de impresión nueva (USB,
red 9100, Android) MUST poder ejercitarse sin hardware: con `tools/fake_9100_printer.py` o un
doble equivalente, en `test-env.sh levantar`.

## Restricciones Técnicas

- **Stack**: Python ≥3.11, FastAPI + uvicorn (daemon), PySide6 (GUI), Pillow (raster ESC/POS),
  PyInstaller + Inno Setup (installer Windows). Plataforma objetivo: Windows 10/11; desarrollo y
  pruebas automáticas en WSL/Linux.
- **Layout**: `posprintproxy/{daemon,gui,util}` (código), `tests/` (pytest), `tools/`
  (diagnóstico), `installer/`, `harness/` (arnés SDD).
- **Dependencias**: toda dependencia nueva de runtime MUST entrar en `requirements.txt` **y**
  empaquetarse en `installer/posprintproxy.spec`; una que solo exista en Windows va con marcador
  `sys_platform == 'win32'` y el código MUST importar sin ella en Linux.

- **Prohibido**: crear o editar módulos Odoo en este repo: los addons de soporte viven en el repo de su versión de Odoo (con su propio arnés); `custom_addons/` es legado en migración y no recibe código nuevo. Tampoco se tocan `.venv/`, `harness/.sandbox/` ni artefactos de build.

## Flujo de Desarrollo y Puertas de Calidad

### Modelo de ramas

- Hay **una** rama de integración, `main`, que soporta a la vez todas las versiones de Odoo
  vigentes y MUST estar siempre en estado instalable/desplegable. Los releases salen de `main`
  con tags `vX.Y.Z` y un único canal de auto-update.
- Toda feature MUST desarrollarse en la rama `<NNN>-<slug>` que crea `create-new-feature.sh`.
  El identificador `NNN` ata rama, `specs/NNN-slug/`, `backlog/NNN-slug.md` y la entrada de
  `feature_list.json`: cuatro artefactos, un solo nombre.

### Las puertas

Cada módulo atraviesa estas puertas en orden. Ninguna se omite.

1. **Especificación**, según el flujo de la feature (`AGENTS.md` §3):
   - **light**: `/speckit-specify` -> `/speckit-tasks`, sin `/speckit-plan`, con los
     presupuestos duros de §3.
   - **estándar**: `/speckit-specify` -> `/speckit-clarify` -> `/speckit-plan` ->
     `/speckit-checklist` -> `/speckit-tasks` -> `/speckit-analyze`, con presupuestos
     ampliados. `/speckit-analyze` MUST cerrar sin hallazgos CRITICAL antes del Gate 1.

   En **ambos**, la especificación MUST partir de una investigación del código existente en el
   grafo de codebase-memory (o grep, si el grafo no está disponible), y cada gate humano MUST ir
   precedido de un interrogatorio con grill-me registrado en `grill.md`. El flujo se fija al dar
   de alta la feature y MUST NOT cambiar una vez que sale de `backlog`.
2. **Rama**: la crea `/speckit-specify` como `<NNN>-<slug>`.
3. **Implementación** en `posprintproxy/<modulo>/`, cumpliendo los principios de este documento,
   precedida de un análisis de impacto (`## Impacto` en `research.md`).
4. **Lint**: `harness/scripts/lint.sh` sin errores.
5. **Tests automatizados**: MUST ejecutarse y pasar, reportando la salida real.

   ```bash
   harness/scripts/test-env.sh instalar <modulo>
   harness/scripts/test-env.sh probar <modulo>
   ```

6. **Verificación manual**: el módulo MUST ejercitarse a mano antes de fusionar. Instalar no es
   funcionar.

   ```bash
   harness/scripts/test-env.sh levantar <modulo>
   ```

### Cierre

- **Merge**: con `--no-ff` para conservar el módulo como una unidad identificable en el
  historial.
- **Push**: MUST NOT hacerse con puertas pendientes.
- **Commits**: Conventional Commits en español (`feat:`, `fix:`, `docs:`, `chore:`,
  `refactor:`, `test:`), asunto corto en imperativo y cuerpo con el porqué. Los commits MUST NOT
  incluir líneas de coautoría de asistentes de IA (`Co-Authored-By` de modelos).

**Revisión**: todo merge a la rama de integración verifica explícitamente el cumplimiento de
los principios de este documento. Una desviación se acepta solo si queda documentada la
alternativa simple descartada y por qué no sirve.

## Governance

Esta constitución tiene precedencia sobre cualquier otra práctica, hábito o preferencia
puntual del equipo. Ante conflicto entre este documento y una guía de referencia, prevalece
este documento; la guía se corrige.

**Enmiendas**: toda modificación MUST proponerse como cambio a este archivo, con justificación
escrita del problema que resuelve y del impacto sobre módulos existentes. Una enmienda que
invalide código ya entregado MUST incluir el plan de migración.

**Versionado semántico**:

- **MAJOR**: se elimina o redefine un principio de forma incompatible con lo ya construido.
- **MINOR**: se añade un principio o sección, o se amplía materialmente una regla existente.
- **PATCH**: aclaraciones, redacción, correcciones sin cambio de obligación.

**Cumplimiento**: la conformidad se verifica en cada merge a la rama de integración. Los
incumplimientos detectados se corrigen antes de fusionar, no se registran como deuda. La
complejidad añadida MUST justificarse: si una regla estorba de forma recurrente, se enmienda
la constitución en lugar de ignorarla.

**Arnés de ejecución**: `AGENTS.md` define el arnés multi-agente (orquestador, especificador,
implementador, tester), la máquina de estados de `feature_list.json`, los dos gates humanos y
los dos flujos (light y estándar) que comparten esa máquina.
Es subordinado a este documento: ante conflicto, gana la constitución.

**Version**: 2.0.0 | **Ratified**: 2026-09-23 | **Last Amended**: 2026-09-24
