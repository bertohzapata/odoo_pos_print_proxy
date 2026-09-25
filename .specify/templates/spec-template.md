# Feature Specification: [NOMBRE]

**Feature**: `[NNN-slug]` | **Creada**: [FECHA] | **Brief**: `backlog/[NNN-slug].md`

> **PRESUPUESTO: 150 LINEAS.** Es un limite duro (AGENTS.md §3). Cada agente del ciclo relee
> esta spec entera en cada arranque, asi que cada linea de mas se paga muchas veces. Si no cabe,
> **recorta el alcance y dilo** — nunca el presupuesto.
>
> Describe **que** y **para quien**, nunca el como. Prosa en espanol; terminos tecnicos del
> dominio o del stack en su forma original, jamas traducidos.
>
> Borra estas instrucciones al escribir.

## Que se construye

[2-4 frases: que resuelve, para quien, y donde vive el modulo.]

## Historias de usuario

> Una por comportamiento observable, **maximo 5**. Prioriza P1/P2/P3. La P1 es el MVP.
> Cada una debe poder validarse a mano en pocos pasos: si no se puede ver, no es una historia.

### H1 — [Titulo] (P1) 🎯 MVP

**Como** [quien], **quiero** [que], **para** [por que].
**Se valida asi**: [lo que el propietario hace y ve. Una o dos frases.]

### H2 — [Titulo] (P2)

...

## Requisitos

> Numerados FR-001... **Maximo 20.** Uno por regla verificable; agrupa lo que sea del mismo
> comportamiento en vez de partirlo. Si necesitas mas de 20, el alcance es demasiado grande.

- **FR-001**: El sistema MUST ...

## Datos y configuracion

> Solo si la feature anade campos o modelos. Tabla, no prosa. Si no anade nada, borra la seccion.

| Campo | Modelo | Tipo | Default | Para que |
|---|---|---|---|---|

## Criterios de exito

> **Maximo 8**, medibles y observables por el propietario. Nada de metricas que nadie va a medir.

- **CE-001**: ...

## Fuera de alcance

- [Lo que explicitamente no entra.]

## Supuestos

> Solo decisiones que el brief dejaba ambiguas. Marca con ⚠ las que el propietario debe
> confirmar en el gate. Si no hay ninguna, borra la seccion.

- **⚠ S1**: ...

## Referencias externas verificadas

> Interfaces, funciones, tablas o IDs de fuera del modulo que esta spec da por existentes,
> **verificados con grep/lectura**, con ruta y linea. Una referencia supuesta rompe la
> implementacion.

- `<ruta>` — [que es y para que se usa]
