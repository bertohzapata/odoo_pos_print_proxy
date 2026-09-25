---
description: Dar de alta o gestionar una feature del arnés SDD — un módulo nuevo o la actualización de uno existente. Escribe el brief preguntando lo que falte.
user-invocable: true
allowed-tools: Bash, Read, Write, Edit, AskUserQuestion, mcp__codebase-memory-mcp__search_graph, mcp__codebase-memory-mcp__get_architecture
---

# /feature — intake del backlog

**Petición**: $ARGUMENTS

Lee `AGENTS.md` antes de actuar. El propietario **nunca** ejecuta scripts: los corres tú.

## Formas de invocación

| Invocación | Qué hace |
|---|---|
| `/feature nuevo <modulo> "<titulo>" [light\|estandar]` | alta con `tipo: nuevo` |
| `/feature actualizar <modulo> "<titulo>" [light\|estandar]` | alta con `tipo: actualizacion` |
| `/feature listar` | muestra el backlog |
| `/feature editar <id>` | cambia campos de una feature en `backlog` |
| `/feature ver <id>` | muestra la entrada y su brief |
| `/feature config` | muestra el flujo por defecto del proyecto y si se pregunta en cada alta |
| `/feature config flujo_default <light\|estandar>` / `flujo_preguntar <si\|no>` | cambia esa configuración (`estado.sh config ...`) |

Si la petición viene en lenguaje natural ("un módulo nuevo para tickets múltiples"),
interprétala: deduce el tipo, propón el nombre técnico del módulo en `snake_case` y confírmalo
antes de dar de alta.

## Alta de una feature

### 1. Determinar el tipo — verifícalo, no lo asumas

```bash
ls posprintproxy/<modulo> 2>/dev/null
```

Existe → `actualizacion`. No existe → `nuevo`. Si el usuario dijo lo contrario de lo que
muestra el disco, **díselo** antes de continuar.

### 2. Elegir el flujo (AGENTS.md §3)

```bash
harness/scripts/estado.sh config
```

- Si el propietario lo dijo en la invocación, ese.
- Si no, y `flujo_preguntar = si`: pregúntalo con `AskUserQuestion` (opciones `light` y
  `estandar`) y **marca tu recomendación**: `estandar` si hay arquitectura que decidir (módulo
  nuevo con varios componentes, integraciones, datos compartidos con otros módulos, riesgo de
  regresión alto); `light` para cambios acotados. Una línea de por qué.
- Si no, y `flujo_preguntar = no`: usa `flujo_default` sin preguntar, y díselo en el resumen.

Ambos flujos usan codebase-memory y grill-me; lo que cambia es la amplitud de Spec Kit y el
tamaño de los artefactos. El flujo **no se puede cambiar** una vez que la feature sale de
`backlog`.

### 3. Dar de alta

```bash
harness/scripts/estado.sh agregar --titulo "<titulo>" --tipo <nuevo|actualizacion> \
  --modulo <modulo> --prioridad <n> --flujo <light|estandar>
```

La prioridad: si no la dio, mira el backlog y propón la siguiente libre.

### 4. Escribir el brief preguntando lo que falte

El script creó `backlog/NNN-slug.md` con la plantilla. **No se la mandes a rellenar.**
Hazle 3-4 preguntas concretas en la conversación, sobre lo que realmente no puedas deducir:

- Qué tiene que hacer y para quién (si no quedó claro)
- Qué queda explícitamente **fuera** del alcance
- Casos borde o reglas de negocio que importen
- Cómo se comprueba a mano que quedó bien

Usa `AskUserQuestion` cuando haya opciones discretas; conversación normal si es abierto.

Para `actualizacion`, investiga **antes** de preguntar: lee el módulo (con `search_graph` /
`get_architecture` si hay grafo) y llega con contexto (qué hace hoy, qué tocaría el cambio). Preguntar lo que puedes leer es hacerle perder tiempo.

Luego escribe el archivo completo y **muéstraselo** para que lo revise. Deja marcado como
`<TU DECIDES: ...>` solo lo que sea genuinamente una decisión suya pendiente.

### 5. Confirmar

Di qué id quedó, con qué flujo, en qué archivo, y que puede arrancar con `/ciclo`.

## Reglas

- `feature_list.json` **nunca** se edita a mano, solo vía `estado.sh`.
- Una feature en `done` no se edita: lo que le faltó es una feature nueva de reparación.
- Una feature que ya salió de `backlog` solo se edita con `--ciclo` y como paso documentado.
  El campo `flujo` ni eso: solo se cambia en `backlog`.
- El módulo destino siempre en `posprintproxy/`. Nunca en un directorio marcado como
  solo-lectura o de terceros (ver AGENTS.md de este proyecto).
