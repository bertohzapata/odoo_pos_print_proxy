# Tasks: [NOMBRE]

**Feature**: `[NNN-slug]` | **Spec**: `spec.md` | **Modulo**: `posprintproxy/[modulo]`

> **PRESUPUESTO: 20 TAREAS.** Limite duro (AGENTS.md §3). Una tarea = **una unidad que deja el
> modulo funcionando**, no un archivo ni una linea. Si necesitas mas de 20, el alcance es
> demasiado grande: dilo en vez de partir el trabajo en migajas.
>
> En la feature 002 fueron 53 tareas para 870 lineas de codigo — una tarea cada 16 lineas, y
> cada una costo leerla, marcarla y actualizar `tarea_actual`.
>
> `[P]` = puede ir en paralelo (archivos distintos, sin dependencias pendientes).
> Borra estas instrucciones al escribir.

## Fase 1 — Base

> Estructura del modulo y lo que todo lo demas necesita (manifest/config inicial, modelos base).

- [ ] T001 ...

## Fase 2 — [Historia 1] (P1) 🎯 MVP

> Al terminar esta fase el modulo hace algo util y validable a mano.

- [ ] T00N ...

## Fase 3 — [Historia 2] (P2)

- [ ] T00N ...

## Fase final — Cierre

- [ ] T0NN Instalacion/arranque limpio: `harness/scripts/test-env.sh instalar <modulo>`
- [ ] T0NN `harness/scripts/lint.sh`
- [ ] T0NN Registrar en `research.md` las desviaciones que aparecieron

## Pruebas

> **Presupuesto de pruebas: ver la constitucion** (Principio de Validacion Manual).
>
> **Prohibido un tour por historia.** Solo se prueba lo que la validacion manual **no puede
> observar**: valores por defecto, comportamiento sin una dependencia opcional, validaciones
> que deben rechazar. Todo lo demas lo ve el propietario a ojo, mas barato y mejor.
>
> **Prohibido correr suites fuera del alcance del ciclo** (ver AGENTS.md de este proyecto).

- [ ] T0NN [si aplica] ...

## Verificacion manual

> Los pasos que ejecutara el propietario. **Maximo 10**, en su lenguaje — nada de codigos FR/CE.
> El tester los pule en `validacion-manual.md`; aqui van en borrador.

1. ...

## Dependencias

> Solo lo que de verdad bloquea. Si el orden es obvio, borra la seccion.

- Fase 1 antes que todo lo demas.
