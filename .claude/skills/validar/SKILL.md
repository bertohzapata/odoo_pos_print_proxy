---
description: Resuelve el gate humano pendiente del ciclo SDD — validación de la especificación o cierre de la feature.
user-invocable: true
allowed-tools: Bash, Read, Write, Edit, AskUserQuestion, Skill, Agent, mcp__codebase-memory-mcp__search_graph, mcp__codebase-memory-mcp__check_index_coverage, mcp__codebase-memory-mcp__index_repository
---

# /validar — los gates humanos

**Petición**: $ARGUMENTS

Los dos únicos momentos en que el ciclo para y decide el propietario. `--autoriza` solo se usa
**aquí**, y solo después de una confirmación explícita suya en la conversación.

## 1. Detectar qué gate toca

```bash
harness/scripts/estado.sh activa
```

- `speccing` → **Gate 1: la especificación**
- `ready_to_close` → **Gate 2: el cierre**
- Cualquier otro → no hay gate pendiente. Dile en qué estado está y qué falta. Para.

Anota el `flujo` (`light` | `estandar`; si la salida trae `"legado": true`, es una feature
anterior a los flujos: haz el grill igual, pero `estado.sh` no lo exigirá).

---

## El grill — antes de pedir `--autoriza`, en los dos gates y los dos flujos

Antes de pedir la confirmación de cualquier gate, **interroga al propietario** sobre lo que se
va a validar. Invoca la skill `grilling` (tool `Skill`): es a la que delega `grill-me`, que
tiene la invocación por modelo desactivada y solo la puede lanzar el propietario tecleando
`/grill-me`. Si `grilling` no está disponible, aplica tú el mismo protocolo:

- Preguntas **numeradas**, cada una con **tu respuesta recomendada**; espera sus respuestas
  antes de la siguiente ronda. Una pregunta que depende de otra aún abierta va a la ronda
  siguiente.
- Los **hechos** los buscas tú (lee el código, o despacha un subagente `codebase-memory-scout`
  si hay grafo); al propietario solo le preguntas **decisiones**.
- **light**: **una ronda, máximo 5 preguntas**, las de más riesgo. **estándar**: rondas hasta
  que no quede ninguna decisión abierta.

Registra el resultado en `<spec_dir>/grill.md` (créalo si no existe) bajo el encabezado exacto
del gate — `estado.sh` busca ese texto:

```markdown
## Gate 1            (o "## Gate 2")
Fecha: YYYY-MM-DD · Flujo: light|estandar · Rondas: N
- Q1 <pregunta corta> -> <decisión del propietario> [cambio aplicado en spec.md §X | sin cambio]
- ...
```

Una línea por pregunta: es un registro de decisiones, no una transcripción. Las decisiones que
cambian artefactos se aplican **antes** de pedir el OK del gate.

---

## Gate 1 — la especificación

Lee lo que escribió el especificador en `spec_dir` y **preséntaselo resumido**, no le pegues
los archivos enteros:

| Artefacto | Cuándo | Qué resumir |
|---|---|---|
| `spec.md` | siempre | qué se va a construir y el alcance |
| `tasks.md` | siempre | cuántas tasks y qué cubren |
| `plan.md` | estándar | arquitectura elegida y alternativas descartadas |
| `## Analyze` en `research.md` | estándar | resultado de `/speckit-analyze`: que no quedó ningún CRITICAL (si quedó, no hay gate: devuélvelo al especificador) |
| `research.md` | siempre | los hallazgos: qué encontró en el código existente que no era obvio |

**Verifica tú antes de presentar**: cualquier referencia concreta que la spec dé por existente
(un endpoint, un XML ID, una función, una tabla) debe existir de verdad — con `search_graph`
si hay grafo (y `check_index_coverage` antes de concluir que algo no existe), con grep si no.
Una referencia inventada no falla en revisión, falla en implementación con el código ya
escrito.

Si algo no existe, **dilo como hallazgo**, no como detalle.

Señala también lo que quedó ambiguo y las decisiones que tomó el especificador por su cuenta:
son el material del grill.

**Grill del Gate 1** (ver arriba) sobre spec + tasks (+ plan en estándar). Escribe
`## Gate 1` en `grill.md`.

Si el propietario pide cambios: aplícalos (sus cambios son ley) y vuelve a presentar. Cuando
confirme:

```bash
harness/scripts/estado.sh mover <id> spec_ready --autoriza "Humberto Zapata" --nota "<que valido>"
```

Si `estado.sh` rechaza el gate por evidencia faltante (AGENTS.md §2), **no** lo rodees: pega
el error, completa lo que falta (o devuélvelo al especificador si es su artefacto) y vuelve a
pedir la transición.

Luego ofrécele continuar con `/ciclo`.

---

## Gate 2 — el cierre

Antes de nada, comprueba que el tester dejó su trabajo hecho:

```bash
cat specs/<NNN-slug>/validacion-manual.md
harness/scripts/test-env.sh estado
```

El entorno debe estar **encendido** (el tester lo dejó así a propósito). Si no lo está,
enciéndelo: `harness/scripts/test-env.sh arriba`.

Preséntale los pasos de validación manual **en la conversación**, numerados, y levanta el
servidor por él:

```bash
harness/scripts/test-env.sh levantar <modulo>
```

Él prueba y te dice qué pasó. Nunca le pidas que ejecute nada.

**Esta validación es la puerta de calidad principal** (ver constitución), no un trámite sobre
una suite ya verde. Si los pasos superan los 10, el tester incumplió su presupuesto: preséntale
los 10 que más importan.

- **Funciona** → antes de cerrar, **grill del Gate 2** (ver arriba) sobre las desviaciones
  registradas en `research.md`, el `## Impacto` frente a lo que realmente cambió y lo que la
  validación manual no cubrió. Escribe `## Gate 2` en `grill.md`. Si el grill destapa algo que
  hay que arreglar, trátalo como "no funciona". Si no, cierra:
  ```bash
  harness/scripts/estado.sh mover <id> done --autoriza "Humberto Zapata" --nota "<que valido>"
  harness/scripts/test-env.sh abajo
  ```
  Después: `git status` limpio, re-indexar el grafo si lo hay (`index_repository`), y proponer
  mejoras al arnés.

- **No funciona** → recoge el detalle, escríbelo donde corresponda y devuelve:
  ```bash
  harness/scripts/estado.sh mover <id> in_progress
  ```
  El entorno se queda encendido: hay trabajo pendiente.

## Prohibiciones

- **Nunca** uses `--autoriza` sin una confirmación literal del propietario en esta conversación.
- Un gate autorizado no autoriza el siguiente.
- No valides tú en su lugar: la verificación manual es suya por definición.
