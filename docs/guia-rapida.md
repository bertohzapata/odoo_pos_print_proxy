# Guía rápida — crear o actualizar un módulo en POS Print Proxy

Tu manual de operación. **Todo se hace desde la sesión de Claude Code: cuatro comandos.**
Nunca necesitas abrir una terminal ni ejecutar scripts. El reglamento interno está en
`AGENTS.md`; esta guía es solo para ti.

---

## Los cuatro comandos

| Comando | Para qué |
|---|---|
| `/feature` | dar de alta lo que quieres construir |
| `/ciclo` | arrancar y avanzar el trabajo |
| `/validar` | tus dos momentos de revisión |
| `/probar` | probar un módulo suelto, sin ciclo |

---

## Dos flujos: light y estándar

Cada feature va por **uno** de dos flujos. Los cuatro comandos son los mismos, tus dos
revisiones también, y en los dos se investiga el código con el grafo (**codebase-memory**) y se
te hace un interrogatorio (**grill-me**) antes de cada revisión. Cambia cuánto se escribe antes
del código.

| | **light** | **estándar** |
|---|---|---|
| Úsalo para | cambios acotados, módulos pequeños, ir rápido | arquitectura no obvia, muchas piezas, riesgo de romper otra cosa |
| Qué se escribe antes del código | `spec.md` + `tasks.md` (+ `research.md`) | lo del light + `plan.md`, y si aportan `data-model.md`, `contracts/`, `quickstart.md`, checklists |
| Comandos de Spec Kit que corren los agentes | `/speckit-specify` -> `/speckit-tasks` -> `/speckit-implement` | `/speckit-specify` -> `/speckit-clarify` -> `/speckit-plan` -> `/speckit-checklist` -> `/speckit-tasks` -> `/speckit-analyze` -> `/speckit-implement` (+ `/speckit-converge` si quedó algo) |
| Límites de tamaño | spec 150 líneas, 20 tareas, research 200 líneas | spec 300, plan 250, 40 tareas, research 300 |
| Investigación del código (codebase-memory) | sí | sí, más vista de arquitectura para el plan |
| Análisis de impacto antes de programar | sí (`## Impacto` en `research.md`) | sí |
| Interrogatorio antes de cada revisión (grill-me) | corto: una ronda, máx. 5 preguntas | completo: rondas hasta que no quede nada por decidir |
| Tus revisiones (`/validar`) | 2 | las mismas 2 |
| Validación manual | máx. 10 pasos | máx. 10 pasos |

El flujo se elige al dar de alta la feature y **no cambia** una vez arrancada. Si no dices
nada, se usa el del proyecto (`/feature config` lo muestra). Si en tu equipo no está instalado
el grafo de código (p. ej. Windows nativo), los dos flujos siguen funcionando con búsqueda de
texto: se te avisa, no se bloquea.

---

## 1. Decir qué quieres — `/feature`

```
/feature nuevo <modulo> "<titulo>"
/feature actualizar <modulo> "<titulo>"
```

O simplemente descríbelo en lenguaje natural. Se deduce el tipo, se propone el nombre técnico
y se confirma contigo.

**Nuevo** si el módulo no existe todavía; **actualizar** si ya está en `posprintproxy/`. No hace
falta que lo verifiques: se comprueba en disco y se te avisa si no cuadra.

Puedes indicar el flujo: `/feature nuevo <modulo> "<titulo>" estandar` (o `light`). Si el
proyecto está configurado para preguntar, se te pregunta con una recomendación.

Después vienen **3 o 4 preguntas** sobre lo que no se pueda deducir. Respondes conversando y se
escribe el brief por ti. Lo revisas antes de arrancar.

```
/feature listar        ver todo el backlog
/feature ver 001       una feature y su brief
/feature editar 001    cambiar algo antes de arrancarla (incluido el flujo)
/feature config        ver o cambiar el flujo por defecto del proyecto
```

---

## 2. Arrancar — `/ciclo`

```
/ciclo
```

Se ordena el backlog por prioridad, se te proponen las candidatas, se pule la elegida contigo y
arranca. El entorno de pruebas se enciende solo.

A partir de ahí el trabajo avanza y **para dos veces**: la especificación y el cierre.

```
/ciclo estado    dónde va todo ahora mismo
```

---

## 🛑 3. Tus dos revisiones — `/validar`

```
/validar
```

Detecta cuál de los dos gates toca y te lo presenta. Es el único comando que cierra fases, y
solo lo hace después de que confirmes explícitamente.

Antes de pedirte el OK de cada revisión se te hace un **interrogatorio** (grill-me): preguntas
numeradas, cada una con la respuesta que se recomienda (una ronda corta en light; las rondas
que hagan falta en estándar). Contestas, se ajusta lo que haga falta, y cuando no quedan
preguntas abiertas se te pide el OK. Queda registrado en `specs/NNN-slug/grill.md`.

### Gate 1 — la especificación

Te llega un **resumen** de qué se va a construir y con qué tareas (en estándar, también el plan
y el análisis del código existente). No te toca leer los archivos
enteros, aunque están en `specs/NNN-slug/` si quieres. Tus cambios son ley.

### Gate 2 — el cierre

Llega con las pruebas automáticas en verde. Falta lo que ninguna máquina hace: usarlo. Se te
presentan los pasos de validación numerados. Si funciona, se cierra y se apaga el entorno. Si
no, vuelve al implementador.

---

## 4. Probar algo suelto — `/probar`

```
/probar <modulo>              instala/arranca limpio y corre la suite
/probar levantar <modulo>     arranca para verificar a mano
/probar estado                ¿encendido?
/probar apagar
```

---

## Dónde vive cada cosa

```
backlog/NNN-slug.md      ← tu brief (se escribe preguntándote)
feature_list.json        ← el estado; no se toca a mano
specs/NNN-slug/          ← lo que produce el ciclo; lo revisas en el Gate 1
specs/NNN-slug/grill.md  ← tus respuestas a los interrogatorios
posprintproxy/<modulo>/   ← tu código
AGENTS.md                ← el reglamento interno
```

---

## Qué NO pasa nunca

- No se cierra una feature sin ti. Las dos revisiones son tuyas y no se saltan.
- No se editan features en `done`. Si a una cerrada le faltó algo, nace una de reparación.
- **No se te pide que ejecutes comandos fuera de la sesión.** Si hay que correr algo, se corre
  aquí.
