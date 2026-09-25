---
description: Instala, prueba o levanta un módulo en el entorno del repositorio, sin pasar por el ciclo SDD.
user-invocable: true
allowed-tools: Bash, Read, Grep, Glob
---

# /probar — entorno de pruebas

**Petición**: $ARGUMENTS

Las pruebas corren **contra el árbol de trabajo real**, no contra una copia desplegada. Un verde
aquí prueba el código del repositorio. El propietario nunca ejecuta estos comandos: los corres
tú.

## Formas de invocación

| Invocación | Qué hace |
|---|---|
| `/probar <modulo>` | instala/arranca limpio y corre la suite |
| `/probar levantar <modulo>` | arranca el servidor/proceso para verificar a mano |
| `/probar apagar` | apaga el entorno |
| `/probar estado` | dice si está encendido |

## Instalar y probar

```bash
harness/scripts/test-env.sh instalar <modulo>
harness/scripts/test-env.sh probar <modulo>
```

`arriba` se ejecuta solo si hace falta: el script lo gestiona.

**Reporta la salida real.** Si algo falla, muestra el error concreto y localiza la causa antes
de opinar.

Nunca digas que las pruebas pasan sin haberlas corrido: viola la constitución del proyecto.

## Levantar para verificación manual

```bash
harness/scripts/test-env.sh levantar <modulo>
```

Lánzalo en segundo plano y dale al propietario la URL o el comando para ejercitarlo.

## Ciclo de vida

Si hay una feature activa, el entorno lo gobierna `/ciclo` — no lo apagues por tu cuenta.
Fuera de un ciclo, apágalo al terminar salvo que te digan lo contrario.
