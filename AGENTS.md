# AGENTS.md — Arnés SDD de POS Print Proxy

> **El repositorio es el sistema.** Este archivo es el reglamento del arnés multi-agente que
> conduce el ciclo Spec-Driven Development. Todo agente (incluida la sesión principal) lo lee
> **antes** de actuar. Se subordina a la constitución (`.specify/memory/constitution.md`);
> ante conflicto, gana la constitución.

## 1. Piezas del sistema

| Pieza | Ubicación | Qué es | Quién escribe |
|---|---|---|---|
| Backlog + estado | `feature_list.json` | Fuente canónica de features y memoria del ciclo | **Nadie a mano**: solo `harness/scripts/estado.sh` |
| Brief de cada feature | `backlog/NNN-slug.md` | Lo que quieres, en prosa. Alimenta la spec | El propietario |
| Reglamento | `AGENTS.md` | Este archivo | Humano; el líder propone mejoras al cerrar ciclo |
| Specs | `specs/NNN-slug/` | Ciclo Spec Kit (spec, tasks, research, validacion-manual, `grill.md`; en flujo estándar además plan, data-model, contracts, quickstart, checklists) | especificador, implementador, tester según fase; `grill.md` el orquestador en `/validar` |
| Constitución | `.specify/memory/constitution.md` | Reglas no negociables | Humano (enmienda formal) |
| Motor de estado | `harness/scripts/estado.sh` | Transiciones validadas | Humano/líder |
| Entorno de pruebas | `harness/scripts/test-env.sh` | Instala/arranca/prueba el módulo contra el árbol real | Humano/líder |
| Comandos | `.claude/skills/{feature,ciclo,validar,probar}/` | La interfaz del propietario | Humano |

## 1.b La interfaz: cuatro comandos

**El propietario no ejecuta scripts.** Nunca. `estado.sh` y `test-env.sh` son el motor interno
—lo que hace auditable el estado y hace fallar las transiciones ilegales— pero los invoca
siempre un agente, jamás una persona en su terminal.

| Comando | Rol | Qué hace |
|---|---|---|
| `/feature` | intake | alta y edición de features; escribe el brief **preguntando** lo que falte |
| `/ciclo` | orquestador | arranca y avanza; despacha subagentes; gobierna el entorno |
| `/validar` | gates | los dos momentos humanos; **único** lugar donde se usa `--autoriza` |
| `/probar` | pruebas | instalar, probar o levantar un módulo fuera del ciclo |

Regla dura: **ningún agente le pide al propietario que ejecute un comando fuera de la sesión.**
Si algo hay que correr, lo corre el agente y reporta la salida real.

El propietario puede lanzar los comandos de Spec Kit (`/speckit-*`) directamente si quiere; el
arnés no se lo impide. En el flujo **estándar** (§3) son precisamente esos comandos los que
corren los agentes, en orden completo.

## 2. Máquina de estados

```
backlog → speccing → spec_ready ⛔ → in_progress ⇄ blocked
        → testing → ready_to_close ⛔ → done
                 ↘ in_progress   (el tester rechaza y devuelve)
```

Reglas duras:

1. **`feature_list.json` no se edita a mano — nunca, nadie.** Toda mutación pasa por
   `harness/scripts/estado.sh`, que rechaza transiciones ilegales y aplica el **principio de
   congelamiento**: *lo que un agente ya leyó no cambia debajo de él* —
   - las features **`done`** no se editan jamás; si les faltó algo, es una feature nueva de
     reparación que cita a la anterior;
   - la feature **activa** solo la tocan los agentes del ciclo con `editar --ciclo`, como paso
     documentado;
   - las features en **`backlog`** se agregan, editan y repriorizan en cualquier momento: nadie
     las ha leído aún.
2. **⛔ = gate humano.** Exige `--autoriza "<nombre>"`. **Ningún subagente usa `--autoriza`,
   nunca.** Solo el líder, después de que el propietario confirme explícitamente en la
   conversación. Son dos: `spec_ready` (validas la spec) y `done` (validas el cierre).
3. Solo puede haber **una** feature activa a la vez. El script lo impone.
4. Cada agente **valida su estado de entrada antes de trabajar** y aborta si no corresponde.
   El agente anterior le da paso al siguiente únicamente a través del estado.
5. **Los dos flujos (§3) comparten esta máquina y estos gates.** El campo `flujo` de la feature
   (`light` | `estandar`) no añade estados: cambia qué hace cada agente dentro de su estado y
   qué **evidencia en disco** exige `estado.sh` para entrar a ciertos estados:

   | Para entrar a | `light` exige en `spec_dir` | `estandar` exige además |
   |---|---|---|
   | `spec_ready` ⛔ | `spec.md`, `tasks.md` y `grill.md` con sección `## Gate 1` | `plan.md` |
   | `testing` | `research.md` con sección `## Impacto` | — |
   | `done` ⛔ | `validacion-manual.md` y `grill.md` con sección `## Gate 2` | — |

   El `flujo` se fija en `backlog` y **no cambia después** (ni con `--ciclo`): cambiar de flujo
   a mitad es cambiar de carril. Si hace falta, se aborta a `backlog` y se cambia ahí.

   **Retrocompatibilidad**: una feature **sin** campo `flujo` (creada con una versión anterior
   del arnés) es *light legado*: `estado.sh` no le exige evidencia y sus transiciones son las de
   siempre. `listar` la marca con `*`. Toda feature nueva lleva `flujo` explícito.

## 3. Dos flujos, una máquina de estados

Cada feature recorre **uno** de dos flujos. El propietario lo elige en `/feature` (o se aplica
el `flujo_default` del proyecto: `estado.sh config`). El `tipo` (`nuevo`/`actualizacion`) solo
dice si el módulo existe; es independiente del flujo.

**Lo que comparten** (no es opcional en ninguno): la máquina de estados, los dos gates
humanos, la investigación de código con **codebase-memory** antes de especificar, el
**análisis de impacto** antes de implementar, el **interrogatorio con grill-me** antes de cada
gate y la validación manual de máximo 10 pasos. **Lo que cambia** es la amplitud de Spec Kit
y el tamaño de los artefactos:

| | **light** (por defecto) | **estándar** |
|---|---|---|
| Para qué | cambios acotados, módulos pequeños, iteración rápida | arquitectura no obvia, varios componentes, alto riesgo de regresión |
| Comandos del especificador | `/speckit-specify` -> `/speckit-tasks` | fase A: `/speckit-specify`; **el orquestador** corre `/speckit-clarify` con el propietario (interactivo); fase B: `/speckit-plan` -> `/speckit-checklist` -> `/speckit-tasks` -> `/speckit-analyze` (sin CRITICAL, resumen en `research.md` `## Analyze`) |
| Artefactos | `spec.md`, `tasks.md`, `research.md` | los del light + `plan.md`, y **si aportan** `data-model.md`, `contracts/`, `quickstart.md`, `checklists/` |
| Investigación de código | codebase-memory + grep donde el grafo no llega | igual, más `get_architecture` para el plan |
| grill-me antes de cada gate | **acotado**: una ronda, máx. 5 preguntas | **completo**: rondas hasta vaciar la frontera de decisiones |
| Análisis de impacto (`## Impacto`) | sí, de lo que la spec dice tocar | sí, de lo que `plan.md` dice tocar |
| Implementación | `/speckit-implement` | `/speckit-implement` (y `/speckit-converge` si quedó trabajo sin construir) |
| Gates humanos | `spec_ready`, `done` | los mismos; `estado.sh` exige además `plan.md` (§2) |
| Presupuestos | duros (tabla abajo) | ampliados (tabla abajo) |

**Qué es un "módulo" aquí**: un subpaquete de `posprintproxy/` (`daemon`, `gui`, `util`) o `app`
(el paquete completo) — es el argumento de `test-env.sh`. Cambios en `installer/`, `tools/` o
`.github/` entran en la feature cuyo módulo los necesite; la spec los declara.

**Features que cruzan repos**: si una feature necesita un addon Odoo (p.ej. un override del POS),
el addon **no se escribe aquí**. Se da de alta como feature en el repo de la versión de Odoo
(`~/odoo19_community`, con su propio `/feature` y su propio ciclo) y la feature de este repo lo
cita en `depende_de`/`notas`. Cada repo cierra su ciclo por separado.

Opcional en estándar, a petición del propietario: `/speckit-taskstoissues` (tasks -> issues de
GitHub) y `/speckit-constitution` (enmienda formal de la constitución; nunca por iniciativa de
un agente).

### Presupuestos (regla dura — ajusta los números si tu proyecto lo justifica, pero por escrito)

| Presupuesto | light | estándar | Por qué |
|---|---|---|---|
| `spec.md` | **150 líneas** | **300 líneas** | cada agente la relee entera en cada arranque |
| `plan.md` | no existe | **250 líneas** | arquitectura y decisiones, no narración |
| `tasks.md` | **20 tareas** | **40 tareas** | una tarea = una unidad que deja el módulo funcionando |
| `research.md` | **200 líneas** | **300 líneas** | solo hallazgos verificados (incluye `## Impacto`) |
| `grill.md` | 1 ronda por gate | sin tope de rondas | registro de decisiones, no transcripción |
| `data-model.md`, `contracts/`, `quickstart.md`, `checklists/` | eliminados | permitidos **solo si aportan**; sin tope de líneas, pero el relevo no los relee | un artefacto de relleno es ruido |
| Pruebas automatizadas | ver constitución | ver constitución | limitar el costo de automatizar de más |
| `validacion-manual.md` | **10 pasos** | **10 pasos** | la validación manual es la puerta principal |
| Contexto de un subagente | **40%** | **40%** | ver §9 |
| Contexto del orquestador | **35%** | **35%** | ver §9 |

Los presupuestos de contexto y de validación manual **no se relajan** en estándar: el flujo
estándar da más espacio a los artefactos, no a los agentes.

**Flujo light — artefactos eliminados**: `plan.md`, `data-model.md`, `contracts/`,
`quickstart.md` y `checklists/`. El modelo de datos va como tabla dentro de `spec.md`; los pasos
de verificación, como última sección de `tasks.md`. Si aparecen en una feature light, se borran.

### Dónde entran codebase-memory y grill-me (ambos flujos)

| Momento | Herramienta | Quién | Deja |
|---|---|---|---|
| Preflight de `/ciclo` | `list_projects`/`index_status`, `detect_changes`, `index_repository` (MCP) | orquestador | índice fresco |
| `speccing`, antes de `/speckit-specify` (y de `/speckit-plan` en estándar) | `search_graph`, `trace_path`, `get_code_snippet`, `get_architecture`, `check_index_coverage` | especificador | hallazgos en `research.md` |
| Gate 1, antes de pedir `--autoriza` | **grill-me** sobre spec + tasks (+ plan en estándar) | orquestador con el propietario (`/validar`) | `grill.md` `## Gate 1` |
| `spec_ready -> in_progress` | agente `codebase-memory-auditor` (o las tools directas) sobre lo que la spec/plan dice tocar | orquestador despacha, implementador escribe | `research.md` `## Impacto` |
| `in_progress -> testing` | `detect_changes` sobre el diff | implementador | `## Impacto` actualizado |
| `testing` | `detect_changes`, `trace_path` | tester | que no haya impacto no declarado |
| Gate 2, antes de pedir `--autoriza` | **grill-me** sobre desviaciones de `research.md` + `validacion-manual.md` | orquestador con el propietario (`/validar`) | `grill.md` `## Gate 2` |

**Degradación (regla dura)**: si el MCP `codebase-memory-mcp` no está disponible (por ejemplo
en Windows nativo), ningún flujo falla: se avisa una vez al propietario, se usa
`Grep`/`Glob`/`Read` en su lugar y se anota en `research.md` "sin grafo: análisis por grep". Si
la skill `grill-me` (o `grilling`, a la que delega) no está instalada, el orquestador conduce el
interrogatorio igual siguiendo el protocolo de `/validar`. Lo que **no** se degrada es la
evidencia: `grill.md` y `## Impacto` se escriben siempre.

Prohibido: crear o editar módulos Odoo en este repo: los addons de soporte viven en el repo de su versión de Odoo (hoy `~/odoo19_community/ixim_addons/`, con su propio arnés); `custom_addons/` es legado en migración y no recibe código nuevo. Tampoco se tocan `.venv/`, `harness/.sandbox/` ni artefactos de build.

## 4. Roles

### orquestador (la sesión principal — no es subagente)

El propietario arranca con "inicia el ciclo". El orquestador:

1. Lee este archivo y `feature_list.json`. Anota el `flujo` de la feature activa (§3).
2. **Entorno de pruebas arriba:** `harness/scripts/test-env.sh arriba` — el ciclo lo va a
   necesitar desde la primera task.
3. Si no hay feature activa: ordena el `backlog` por `prioridad` (menor = antes; sin prioridad
   al final), verifica `depende_de`, y presenta las candidatas al propietario. Antes de
   arrancar, **pule la candidata**: ¿el brief está completo? ¿el `modulo` es correcto? ¿el
   `tipo` refleja si existe o no? Propone las mejoras y las aplica cuando el propietario
   confirme — la feature entra al ciclo ya pulida y desde `speccing` queda congelada.
4. Despacha al subagente que toca (tabla §5) y **reporta al propietario** lo que dejó escrito.
5. En los gates ⛔: presenta el artefacto, conduce antes el **grill** (acotado en light,
   completo en estándar) y lo registra en `grill.md`, espera la validación literal, y solo entonces ejecuta la transición
   con `--autoriza`.
6. Con una feature `blocked`: investiga las opciones, compara y propone la mejor a largo plazo
   con análisis de adopción (paridad, limitaciones, riesgo, migración), espera validación y
   devuelve la feature a `in_progress`.
7. Al cerrar: verifica `git status` limpio, **apaga el entorno de pruebas**
   (`test-env.sh abajo`) y propone mejoras al arnés.

El orquestador **no** escribe specs, ni código, ni prueba: para eso están los subagentes.
Dos excepciones acotadas, porque son conversaciones con el propietario que un subagente no
puede tener: corre `/speckit-clarify` en flujo estándar (y deja `## Clarify` en `research.md`)
y escribe `grill.md` en `/validar`.

### especificador (`.claude/agents/especificador.md`)

Entrada válida: `speccing`. Investiga el código existente **antes** de especificar y corre los
comandos del flujo de la feature (§3): en light, `/speckit-specify` y `/speckit-tasks`, **tres**
artefactos y ninguno más; en estándar, la cadena completa. En ambos investiga con
codebase-memory, respeta los presupuestos de §3 y PARA en el gate. No implementa.

### implementador (`.claude/agents/implementador.md`)

Entrada válida: **`in_progress` únicamente**. Ejecuta `/speckit-implement` task por task,
mantiene `tarea_actual` y `tasks.md`, escribe pruebas, registra desviaciones en `research.md`
y termina en `testing` o `blocked`. Antes de la primera task deja el `## Impacto` en
`research.md` y lo actualiza con `detect_changes` antes de soltar (ambos flujos). **Tiene prohibido declarar la feature terminada.**

### tester (`.claude/agents/tester.md`)

Entrada válida: `testing`. Su trabajo es **barato y acotado**:

1. `harness/scripts/test-env.sh instalar <modulo>` — instalación/arranque limpio desde cero.
2. `harness/scripts/lint.sh` sobre el módulo.
3. La suite **del módulo** (`test-env.sh probar <modulo>`), corta por presupuesto.
4. `validacion-manual.md` con **máximo 10 pasos**, en lenguaje del propietario.

Verifica las tasks con evidencia (una `[x]` se reproduce o se desmarca) y termina en
`ready_to_close` o devuelve a `in_progress`. **No marca `done`**: eso es el gate humano.

## 5. Despacho por estado

| Estado | Quién actúa | Deja | Notas por flujo |
|---|---|---|---|
| `backlog` | orquestador (propone candidata) | `speccing` | — |
| `speccing` | especificador (en estándar: fase A, clarify del orquestador, fase B) | `spec_ready` ⛔ | ambos: grill en `/validar` |
| `spec_ready` | orquestador (despacha) | `in_progress` | ambos: despacha `codebase-memory-auditor` para el impacto |
| `in_progress` | implementador | `testing` o `blocked` | ambos: `## Impacto` en `research.md` |
| `blocked` | orquestador (investiga y propone) | `in_progress` | — |
| `testing` | tester | `ready_to_close` o `in_progress` | ambos: `detect_changes` contra `## Impacto` |
| `ready_to_close` | propietario + orquestador | `done` ⛔ | ambos: grill `## Gate 2` en `/validar` |

## 6. Propiedad de archivos

| Archivo | especificador | implementador | tester | orquestador | humano |
|---|---|---|---|---|---|
| `feature_list.json` | vía `estado.sh` | vía `estado.sh` | vía `estado.sh` | vía `estado.sh` (único con `--autoriza`) | vía `estado.sh` (nunca a mano) |
| `backlog/NNN-*.md` | lee | lee | lee | propone mejoras | ✍️ |
| `specs/NNN/spec.md`, `tasks.md` | ✍️ | marca tasks | verifica y desmarca | — | valida en el gate |
| `specs/NNN/plan.md`, `data-model.md`, `contracts/`, `quickstart.md`, `checklists/` (solo estándar) | ✍️ | lee | lee | — | valida en el gate |
| `specs/NNN/grill.md` | lee | lee | lee | ✍️ (en `/validar`) | responde |
| Código en `posprintproxy/` | — | ✍️ | corre pruebas | — | — |
| `specs/NNN/research.md` | ✍️ | ✍️ | verifica | — | — |
| `specs/NNN/validacion-manual.md` | — | — | ✍️ | — | ejecuta |
| `AGENTS.md`, constitución, scripts | — | — | — | propone | aprueba |

## 7. Entorno de pruebas

```bash
harness/scripts/test-env.sh arriba            # levanta lo que haga falta
harness/scripts/test-env.sh estado            # encendido o apagado
harness/scripts/test-env.sh instalar <modulo> # instalacion/arranque limpio
harness/scripts/test-env.sh probar <modulo>   # la suite
harness/scripts/test-env.sh levantar <modulo> # servidor/proceso para verificar a mano
harness/scripts/test-env.sh abajo             # apagar
```

### Ciclo de vida del entorno (regla dura)

| Momento | Entorno |
|---|---|
| El orquestador arranca un ciclo (`backlog → speccing`) | **se enciende** |
| Durante `speccing`, `in_progress`, `testing` | sigue encendido: los agentes lo usan |
| El tester deja `ready_to_close` | **se queda encendido**: falta tu validación manual |
| El orquestador marca `done` | **se apaga** |
| La feature queda `blocked`, o el ciclo se aborta a `backlog` | **se apaga**: nadie lo está usando |

Dicho corto: **encendido solo mientras haya trabajo activo o validación manual pendiente.**

## 8. Índice de código (codebase-memory)

Ambos flujos usan el MCP `codebase-memory-mcp` (grafo de código) y los agentes globales
`codebase-memory-scout` / `codebase-memory` / `codebase-memory-auditor` (ver §3 para cuándo).
`sdd-init` lo actualiza a la última versión estable cada vez que inicializa o actualiza el
arnés.

- **Refrescar**: preflight de `/ciclo` (`detect_changes`; si hay drift, `index_repository`), al
  terminar la implementación y al cerrar.
- **Límites**: el grafo cubre lenguajes soportados; plantillas, XML, CSS y assets estáticos
  suelen quedar fuera. Un resultado vacío del grafo **no prueba ausencia**: usa
  `check_index_coverage` y repite con grep antes de concluir.
- **Sin MCP**: ver "Degradación" en §3.

Límites concretos de este proyecto: `tools/`, `diagosticos/` y `.venv/` están excluidos del
índice; el grafo no ve el contrato HTTP que consume el POS de Odoo (JS en otro repo): ese contrato
se verifica leyendo `proxy_server.py` y el código de Odoo de la versión objetivo.

## 9. Reglas transversales

- **Una sola línea para todas las versiones de Odoo** (constitución, Principio III): la rama de
  integración es **`main`** y soporta a la vez Odoo 19 (protocolo IoT Box) y Odoo 20 (protocolo
  Epson ePOS). Cada feature declara en su brief qué versiones de Odoo toca. Antes de
  `/speckit-specify` se hace checkout de `main`: Spec Kit crea `NNN-slug` desde HEAD. Se fusiona
  de vuelta a `main` con `--no-ff`. `harness/scripts/lint.sh` compara contra `PPP_BASE_BRANCH`
  (default `main`).
- **Commits:** Conventional Commits en español (`feat:`, `fix:`, `docs:`, `chore:`,
  `refactor:`, `test:`), y versión en `posprintproxy/util/version.py` + `HITOS.md` al liberar.
  **Nunca** llevan líneas `Co-Authored-By` de modelos de IA (constitución, Cierre).
- **Lint:** `harness/scripts/lint.sh` corre ruff (config `ruff.toml`) **solo sobre los `.py`
  que cambia la feature**; la deuda heredada (`lint.sh --todo`) no bloquea el ciclo.
- **Lo que solo el propietario puede validar**: impresora física real, Windows real (GUI,
  installer, spooler USB) y el Odoo en línea. El sandbox (`test-env.sh levantar`: daemon +
  impresora 9100 simulada) cubre el resto desde WSL. `validacion-manual.md` separa ambos.
- Toda desviación de spec o plan se escribe en `research.md` **en el momento en que ocurre**.
  Una desviación no escrita es deuda invisible.
- Las decisiones de implementación exigen análisis de adopción (paridad, limitaciones, riesgo,
  migración), no solo justificación de descarte.

### Contexto y relevos

La degradación por contexto largo es continua, no un acantilado: todo modelo frontier pierde
exactitud según crece su entrada, y el efecto es **peor en tareas de varios pasos** — que es
justo lo que hace un implementador.

| Rol | Límite de su propio contexto |
|---|---|
| Subagente (especificador, implementador, tester) — cualquier flujo | **40%** |
| Orquestador | **35%** |

Al alcanzarlo: **parar en un punto limpio**, dejar `tasks.md` y `tarea_actual` al día, y
reportar. Nunca agotarse. Nunca quedarse trabado: si algo no avanza, se para, se documenta y se
reporta.

### Handoff de relevo

Un agente que para escribe al final de `research.md` un bloque **`## Handoff`, máximo 10
líneas**: qué hizo, dónde quedó exactamente, qué falta, qué trampa encontró. El relevo lee
**ese bloque y `tasks.md`**, no los artefactos completos.
