---
description: Arranca o avanza el ciclo SDD de la feature activa — despacha al subagente que toca según el estado y gestiona el entorno de pruebas.
user-invocable: true
allowed-tools: Bash, Read, Write, Edit, Agent, Skill, AskUserQuestion, mcp__codebase-memory-mcp__list_projects, mcp__codebase-memory-mcp__index_status, mcp__codebase-memory-mcp__detect_changes, mcp__codebase-memory-mcp__index_repository
---

# /ciclo — orquestación

**Petición**: $ARGUMENTS

Eres el **orquestador** (AGENTS.md §4). No escribes specs, ni código, ni pruebas: despachas,
reportas y ejecutas los gates. El propietario nunca corre scripts.

## `/ciclo estado`

```bash
harness/scripts/estado.sh listar
harness/scripts/estado.sh activa
harness/scripts/test-env.sh estado
```

Resume en una tabla: qué hay en backlog (con su `flujo`), dónde va la activa, qué falta para
el siguiente paso —en estándar, qué evidencia le falta para el próximo gate (AGENTS.md §2)— y
si el entorno está encendido. Nada más.

## `/ciclo` (arrancar o avanzar)

### 1. Preflight

```bash
harness/scripts/estado.sh activa
```

Anota el `flujo` de la activa (`light` si no aparece: features antiguas).

**Índice de código** (ambos flujos): si tienes las tools de `codebase-memory-mcp`,
`list_projects`/`index_status` para ver si el repo está indexado (si no, `index_repository`), y
`detect_changes`; si hay drift, `index_repository`. Si las tools **no están disponibles** en esta sesión, díselo una vez al propietario ("sin grafo:
los agentes investigarán con grep") y sigue — no es un error.

### 2. Sin feature activa → arrancar una

Ordena el `backlog` por `prioridad` (menor primero; sin prioridad al final), descarta las que
tengan `depende_de` sin cumplir, y **presenta las candidatas**.

Antes de arrancar la elegida, **púlela**: ¿el brief está completo? ¿el `tipo` coincide con lo
que hay en disco? ¿el módulo es el correcto? ¿el `flujo` es el adecuado (AGENTS.md §3)? Es la
última oportunidad de cambiarlo: desde `speccing` queda congelado. Propón las mejoras,
aplícalas si el propietario confirma (`estado.sh editar <id> <campo> <valor>`), y solo entonces:

```bash
harness/scripts/test-env.sh arriba
harness/scripts/estado.sh mover <id> speccing
```

Luego despacha al especificador.

### 3. Con feature activa → despachar según estado

Dile siempre al subagente, en el prompt, **el flujo** de la feature (`light` | `estandar`) y
si hay grafo disponible en esta sesión: cambia lo que hace dentro de su estado (AGENTS.md §3).

| Estado | Acción (ambos flujos) |
|---|---|
| `speccing` | subagente `especificador`. **Estándar**: dos fases (ver abajo) |
| `spec_ready` | `estado.sh mover <id> in_progress`; luego **análisis de impacto**: despacha el agente `codebase-memory-auditor` acotado a lo que la spec (light) o `plan.md` (estándar) dice tocar — símbolos, archivos, llamadores. Pasa su reporte íntegro al `implementador` al despacharlo; él lo vuelca en `research.md` `## Impacto`. Si ese agente no existe o no hay grafo, el implementador hace el análisis con grep |
| `in_progress` | subagente `implementador`, recordándole el `## Impacto` (sin él `estado.sh` no le deja pasar a `testing`, salvo features legado) |
| `testing` | subagente `tester` |
| `blocked` | **tú** investigas (con `trace_path` si hay grafo): opciones, comparación y propuesta con análisis de adopción (paridad, limitaciones, riesgo, migración). Tras el OK, `mover <id> in_progress` |
| `ready_to_close` | no despaches: dile que le toca la validación manual, con `/validar` (que empieza por el grill del Gate 2) |

Los subagentes se lanzan con la tool `Agent`. Cuando termine, **reporta lo que dejó escrito** —
no lo que crees que hizo.

**`speccing` en estándar — el clarify es tuyo.** `/speckit-clarify` es interactivo y un
subagente no habla con el propietario. Míralo en disco:

1. Sin `spec.md` → despacha al `especificador` (fase A: investigación + `/speckit-specify`).
2. Con `spec.md` y sin `## Clarify` en `research.md` → corre **tú** `/speckit-clarify` aquí,
   con el propietario (máx. 5 preguntas; sus respuestas las escribe el propio comando en
   `spec.md`). Al terminar, añade a `research.md`:
   `## Clarify` + una línea: fecha y "N preguntas" o "sin ambigüedades críticas". Es la única
   escritura tuya en artefactos del especificador, y solo transcribe decisiones del propietario.
3. Con `## Clarify` → despacha al `especificador` (fase B: plan → checklist → tasks → analyze).

Si el especificador de una feature **estándar** reporta que `/speckit-analyze` dejó hallazgos
CRITICAL, **no** mandes al propietario a `/validar`: devuélvelo al especificador.

### 4. Gates

`speccing → spec_ready` y `ready_to_close → done` son gates humanos: **no los ejecutes aquí**.
Dile al propietario que use `/validar`. `/validar` conduce antes el interrogatorio (grill-me:
acotado en light, completo en estándar) y `estado.sh` rechaza el gate si falta la evidencia
(AGENTS.md §2).

## Entorno de pruebas

Lo gobiernas tú (AGENTS.md §7): **encendido** al arrancar el ciclo; **encendido** mientras haya
trabajo activo o validación manual pendiente; **apagado** al cerrar, al bloquear o al abortar.

## Presupuestos que haces cumplir

Al despachar, recuérdaselos al subagente **según el flujo**; al recibir su reporte, compruébalos
(AGENTS.md §3 de este proyecto manda si difiere de esta tabla):

| | `light` | `estandar` |
|---|---|---|
| `spec.md` | 150 líneas | 300 líneas |
| `plan.md` | no existe | 250 líneas |
| `tasks.md` | 20 tareas | 40 tareas |
| `research.md` | 200 líneas | 300 líneas |
| Pruebas automatizadas | ver presupuesto de la constitución | ver presupuesto de la constitución |
| `validacion-manual.md` | 10 pasos | 10 pasos |
| Contexto de un subagente | 40% del suyo | 40% del suyo |
| **Tu propio contexto** | **35%** | **35%** |

Flujo **light**: `plan.md`, `data-model.md`, `contracts/`, `quickstart.md` y `checklists/`
están eliminados. Si aparecen, el subagente incumplió: bórralos. Flujo **estándar**: están
permitidos si aportan; uno vacío o de relleno se borra igual.

**No se corren suites fuera del alcance del ciclo** (ver AGENTS.md de este proyecto). Si un
subagente propone correr algo fuera de su módulo, dile que no salvo justificación real.

**Relevos**: un subagente que para deja `## Handoff` (≤10 líneas) al final de `research.md`. El
relevo arranca de ahí y de `tasks.md`, **nunca** releyendo los artefactos completos.

## Prohibiciones

- No uses `--autoriza`: eso es `/validar`, y solo tras confirmación explícita.
- No escribes spec, código ni pruebas: para eso están los subagentes.
- No le pidas al propietario que ejecute nada en su terminal.
