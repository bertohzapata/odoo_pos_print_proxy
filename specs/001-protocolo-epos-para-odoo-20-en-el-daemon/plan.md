# Implementation Plan: Protocolo ePOS para Odoo 20 en el daemon

**Branch**: `001-protocolo-epos-para-odoo-20-en-el-daemon` | **Fecha**: 2026-09-25 |
**Spec**: `spec.md` | **Investigación**: `research.md` (fase A + `## Plan`) | **Contrato**: `contracts/epos.md`

## Resumen

Cada impresora sirve, en el mismo puerto y la misma app FastAPI, dos protocolos aislados:
IoT Box (Odoo 19, se mueve tal cual a su propio módulo) y Epson ePOS (Odoo 20, módulo nuevo).
El ePOS se traduce a ESC/POS con la lógica compartida de `printer_backend` (raster y
transporte) y se entrega con el lock de la `Printer`. El daemon enlaza él mismo los sockets
(dual-stack, porque hoy **no** acepta `127.0.0.1`, ver D6), añade un listener HTTP opcional
(`http_port`) y deja de matar procesos ajenos.

## Contexto técnico

- **Lenguaje**: Python ≥3.11 (venv de dev: 3.12.3). **Deps**: FastAPI 0.141, Starlette 1.6,
  uvicorn 0.52.4, Pillow, PyYAML, pywin32 (win32), PySide6; **nueva: `psutil`** (D4).
- **XML**: `xml.etree.ElementTree` de la stdlib (expat 2.6.1 en el venv).
- **Pruebas**: pytest + httpx (ASGI) en `tests/`; impresora 9100 simulada en `conftest.py` y
  `tools/fake_9100_printer.py`. Suite: `harness/scripts/test-env.sh probar app`.
- **Plataforma**: Windows 10/11 (producción), WSL/Linux (dev y pruebas automáticas).
- **Tipo**: servicio local HTTP(S) + GUI de escritorio. **Escala**: 1–5 impresoras, 1–4 cajas.
- **Restricciones**: reposo ≈ 0 % CPU y <10 MB extra (CE-006); respuesta antes del
  `timeout` de Odoo (FR-009, 15 s por defecto); ninguna migración de config (CE-007).

## Constitution Check

| Principio | Cumplimiento | Estado |
|---|---|---|
| I. Validación manual primero | 3 archivos de prueba nuevos, solo lo no observable a mano (parser/bits, respuesta SOAP, config/puertos); E2E lo hace el propietario | ✅ |
| II. Verificar, no asumir | Contrato leído en Odoo 20 (citas en spec/research); D6 comprobado ejecutando; S7 queda como spike | ✅ |
| III. Contratos por versión | `epos.py` y `iotbox.py` separados; `printer_backend` sin conocimiento de protocolo; pruebas IoT Box sin modificar (CE-004) | ✅ |
| IV. La impresión no se pierde | Error SOAP con código en todo fallo de entrega o timeout; nunca éxito sin `sendall`/spooler OK; ruta ePOS ejercitable con la 9100 falsa en `levantar` | ✅ |
| Dependencias | `psutil` en `requirements.txt` **y** en `installer/posprintproxy.spec` (D4) | ✅ justificada |
| Prohibido | Ningún addon Odoo aquí; no se tocan `.venv/`, `harness/.sandbox/` | ✅ |

Re-evaluado tras el diseño: sin violaciones; no hace falta `Complexity Tracking`.

## Decisiones

### D1 — Handlers bloqueantes vs. timeout (FR-009, FR-010, FR-017)

**Decisión**: toda entrega a la impresora (ePOS **e** IoT Box) sale del event loop con
`asyncio.to_thread`. En ePOS se envuelve en `asyncio.wait_for` con un plazo
`deadline = min(timeout_ms or 15000, 60000)/1000 − 1.5 s` (margen para que la respuesta llegue
antes del `abort` del navegador). El plazo baja a la `Printer`:
- `Printer.send_escpos(data, deadline)` adquiere `_lock` con `acquire(timeout=restante)`; si
  no lo obtiene → `EX_TIMEOUT` sin enviar nada.
- En red, `_send_raw` usa `timeout = restante` (hoy fijo 10 s).
- USB (spooler) no es interrumpible: `wait_for` responde `EX_TIMEOUT` y el hilo termina solo.

**Por qué**: los handlers actuales son `async def` que bloquean el único loop del daemon
(`proxy_server.py:231,235`); con dos listeners por impresora, una impresión lenta congela todos
los puertos y no hay forma de responder a tiempo. `to_thread` usa el executor por defecto del
loop: hilos reutilizados y acotados (`min(32, cpu+4)`), creados solo al primer trabajo y
dormidos en una cola en reposo, así que no hay "hilos por petición nuevos" ni sondeos
(FR-017). El `_lock` sigue serializando ePOS e IoT Box (FR-010).
**Costo aceptado**: si el timeout vence con el trabajo ya en curso, el ticket puede salir
después de reportar `EX_TIMEOUT` y, si la cajera reintenta, salir duplicado. Un duplicado
es preferible a una pérdida silenciosa (Principio IV). IoT Box conserva su semántica (sin
plazo nuevo), pero deja de congelar el loop; sus pruebas no cambian.
**Descartado**: dejar el bloqueo (incumple FR-009), un hilo o cola propia por impresora
(más código y hilos permanentes, con el mismo resultado), `run_in_executor` con pool propio
(sin ventaja frente al executor por defecto).

### D2 — `SystemExit` de uvicorn con bind fallido (FR-014, FR-015)

**Decisión**: el daemon enlaza él mismo cada socket (`_bind_listener(port)`) **antes** de crear
el `uvicorn.Server` y llama a `server.serve(sockets=[sock])`. Con sockets ya enlazados, uvicorn
no pasa por la rama que hace `sys.exit(STARTUP_FAILURE)` (`uvicorn/server.py:173-183`; la
rama `sockets` en `:126-148` acepta `ssl`). Un `OSError` de bind lo captura el daemon, aplica
D5 (dueño del puerto) y deja fuera **solo** ese listener. Por defensa, cada `serve()` va
envuelto en una corrutina que captura `BaseException` salvo `CancelledError` y lo registra
como fallo de ese puerto. Así `gather` no se cae entero.
**Estado**: `DaemonSnapshot` gana `port_warnings: list[str]` ("puerto 18072 ocupado por
wslrelay.exe (PID 4321)"). `running_ports` pasa a listar solo los puertos realmente
enlazados. `RUNNING` si al menos un listener arrancó; `ERROR` (con `last_error`) si ninguno.
`tray.py:131` y `dashboard_view.py:153` añaden las advertencias al texto que ya muestran
(FR-014 lo exige: no es GUI nueva, ver nota de alcance en `## Estructura`).
**Descartado**: capturar `SystemExit` alrededor de `serve()` sin pre-bind. Deja una carrera
entre la comprobación y el bind, y no resuelve D6.

### D3 — Protección XXE / bomba de entidades (FR-006)

**Decisión**: sin dependencia nueva. Antes de parsear, el handler ePOS (a) rechaza cuerpos de
más de **8 MiB** (por `Content-Length` y leyendo en streaming con corte), y (b) rechaza cualquier
cuerpo que contenga `<!DOCTYPE` o `<!ENTITY`. Ambos casos → error ePOS (FR-006) con causa en
el log. Después, `ElementTree.fromstring`.
**Por qué**: Odoo nunca manda DTD (`epos_templates.xml:3-9`); sin DTD no hay entidades que
expandir ni recursos externos. La stdlib no resuelve entidades externas y expat ≥2.4 limita la
amplificación, pero rechazar el DTD cierra la clase entera sin depender de la versión de expat
del build de Windows. 8 MiB cubre de sobra un ticket largo: 512×10 000 px = 640 KB en base64.
**Descartado**: `defusedxml` (dependencia nueva para algo que dos comprobaciones resuelven).

### D4 — `tasklist` vs. `psutil` (FR-014, S6)

**Decisión**: `psutil` (≥5.9, **sin** marcador de plataforma) en `requirements.txt` y como
`hiddenimport` en `installer/posprintproxy.spec`. Sustituye `netstat -ano` + `taskkill`:
`psutil.net_connections("tcp")` para ver quién escucha en el puerto, y `Process(pid).name()`,
`.exe()` y `.cmdline()` para clasificarlo. Un proceso es propio si su nombre es
`POSPrintProxy.exe`, o si es un intérprete Python cuya línea de comandos contiene
`posprintproxy` (S6). Nunca se toca el PID actual. Un proceso propio se termina con
`terminate()`/`wait(3)` y luego `kill()`. Si falta permiso (`AccessDenied`) o el PID no se
ve, el dueño es "programa desconocido" y **no** se toca.
**Por qué** (contra la constitución: "toda dependencia nueva requiere justificarla"):
S6 exige distinguir un `python.exe` propio de uno ajeno, y eso pide la línea de comandos.
`tasklist` solo da el nombre de imagen. `wmic` está retirado en Windows 11 24H2 y PowerShell
`Get-CimInstance` tarda 1-3 s por consulta y abre otro proceso. `netstat` ya tarda 8-12 s
(`daemon.py:72`). `psutil` resuelve PID, nombre y línea de comandos en milisegundos y funciona
igual en Linux, lo que permite ejercitar FR-014 en el sandbox de WSL (CE-005 sin Windows).
Ocupa ≈0,5 MB en el installer y no añade hilos ni carga en reposo (solo se usa al arrancar).
**Descartado**: `tasklist` más la regla "todo `python.exe` es ajeno". Viola S6 en desarrollo y
deja zombies propios del modo dev ocupando puertos.

### D5 — Arranque de puertos (FR-014, FR-015)

Por cada puerto de la config (`port` y `http_port` de cada impresora), en el hilo del daemon y
antes del loop:
1. `psutil` busca listeners **de cualquier dirección** en ese puerto. Si el dueño es un
   proceso propio anterior y `kill_zombies_on_startup` está activo, se cierra. Si es ajeno,
   se registra en `port_warnings` y en el log (nombre + PID) y ese listener no arranca.
2. `_bind_listener(port)`; si falla → mismo aviso, con el dueño si `psutil` lo encuentra.
El paso 1 es necesario en Windows. Allí un listener ajeno en `127.0.0.1:P` (p. ej. el reenvío
de WSL) no impide enlazar `[::]:P` sin `SO_EXCLUSIVEADDRUSE`, y el tráfico a `127.0.0.1` lo
seguiría recibiendo el otro programa. El socket propio usa `SO_EXCLUSIVEADDRUSE` en Windows y
`SO_REUSEADDR` en POSIX.

### D6 — Hallazgo: el listener actual no acepta IPv4 (bloqueante para Odoo 20)

`host="::"` se comenta como "dual-stack", pero `asyncio` fija `IPV6_V6ONLY=True` en todo
socket AF_INET6 que crea (`asyncio/base_events.py:1554-1558`, sin rama por plataforma).
**Comprobado ejecutando** en el venv: un `create_server(host="::")` rechaza `127.0.0.1` y acepta
`::1`. Odoo 19 funciona porque el navegador resuelve `localhost` a `::1`. Odoo 20 exige
`127.0.0.1` (`pos_printer.py:10-26`), así que hoy recibiría "connection refused". En Windows se
infiere por lectura del mismo código de stdlib; se confirma en el E2E.
**Decisión**: `_bind_listener` crea `AF_INET6` con `IPV6_V6ONLY=0` (dual-stack, soportado en
Windows ≥Vista y Linux). Si IPv6 no está disponible, recurre a `AF_INET` en `0.0.0.0`. Para
Odoo 19 es un cambio aditivo: `::1` sigue funcionando.

### D7 — Formato ePOS → ESC/POS (FR-002…FR-006, clarify)

- **Parser** (`epos.py`): busca `{ns}epos-print` en cualquier nivel del sobre, sin importar el
  prefijo. Recorre los hijos en orden y produce una lista de comandos:
  `image | text | feed | cut | pulse`. Un elemento desconocido o un atributo de texto no
  soportado se registra en el log y se ignora (FR-005). El cuerpo se lee como bytes con
  `await request.body()`, sin mirar `Content-Type` (FR-002).
- **Imagen**: `ceil(W×H/8)` bytes exactos; si no, error FR-006. El desempaquetado lee el bit
  `i = y·W + x` MSB-first. El último byte parcial (`W·H mod 8 = r ≠ 0`) está **alineado a la
  derecha** (`encodeRaster`): sus `r` bits válidos son los `r` menos significativos. Se reempaqueta
  a filas con relleno de byte, se centra rellenando en blanco a `paper_width` y, solo si
  `W > paper_width`, se reduce proporcionalmente con Pillow (modo `"1"`, invirtiendo la
  polaridad: en ePOS 1 = negro).
- **Compartido** (`printer_backend.py`): se extrae `raster_to_escpos(rows, bytes_per_line,
  height) -> bytes` (bloque `GS v 0`). `image_to_escpos_raster` lo usa y su salida para Odoo 19
  queda **byte-idéntica** (se verifica con una prueba de igualdad frente a la implementación
  anterior, D9). Nuevo `send_raw_win32(printer_name, data, doc_name)`: los tres
  duplicados `win32print` existentes pasan a llamarlo.
- **Texto**: `ESC a n` (alineación: left/center/right), `ESC E` (negrita, `em`), `ESC -`
  (subrayado, `ul`), `GS ! n` (doble ancho/alto, `dw`/`dh`). `&#10;` → `\n`. Codificación
  `cp437` con `errors="replace"` (página de códigos por defecto de ESC/POS; cubre á é í ó ú ñ
  ¿ ¡). **`feed line=N`** → `ESC d N`. **`cut`** → avance + `GS V 0` (sin `FEED` extra si ya hay
  un `feed` previo). **`pulse`** → `ESC p 0 25 250`, el mismo del cajón IoT Box.
- Un documento produce **un** buffer (`INIT` + comandos) y **una** entrega bajo el lock.
- **Respuesta**: siempre un sobre SOAP con `<response success code status="0"/>` (FR-007, S1),
  HTTP 200 incluso en error, porque Odoo lee el XML y no el status HTTP. Códigos: éxito `""`;
  entrega fallida `EX_BADPORT`; plazo vencido `EX_TIMEOUT`; documento inválido `SchemaError`
  (código genérico que Odoo muestra tal cual). `Content-Type: text/xml; charset=utf-8`.
  Detalle en `contracts/epos.md`.

### D8 — Config, CORS y GUI mínima (FR-012, FR-013, FR-015, FR-016, FR-020)

- `PrinterConfig.http_port: int | None = None`, validado 1–65535. `_parse_printer` lo lee solo si
  está presente (legacy: nunca). Unicidad sobre `port ∪ http_port` de todas las impresoras, con un
  mensaje que nombra los puertos que chocan. El daemon **no** escribe la config.
- `AppConfig.odoo_domain: str | list[str]` conserva la forma leída (se reescribe igual).
  `allowed_origin` se sustituye por `allowed_origins -> list[str]` (sin barra final, sin
  vacíos). Callers: `daemon.py:276,337` y `dashboard_view.py:181`.
- CORS (`proxy_server.py:139`): `origin in allowed_origins`. En preflight añade `Allow-Headers`
  al actual y conserva `Allow-Private-Network: true`. Para LNA (S7), si el preflight trae
  `Access-Control-Request-Private-Network`/`-Local-Network`, se refleja `Allow-Local-Network:
  true`. Otros orígenes → 403, como hoy.
- Listener HTTP: si `http_port` está definido, se crea un segundo `uvicorn.Server` **sin TLS**
  sobre **la misma app** en el mismo loop.
- GUI (FR-016): `_printer_to_dict` escribe `http_port` si existe; `printer_dialog._collect`
  lo conserva del `PrinterConfig` original (sin campo nuevo en el diálogo) y valida el choque de
  `port` contra los `http_port` usados. `_suggest_defaults` y `_create_default` pasan a 18072.
  `printers_view` muestra los dominios unidos por `, ` y al guardar separa por coma
  (un dominio → texto; varios → lista), lo que conserva la lista (FR-020).

### D9 — Pruebas automatizadas (presupuesto de la constitución)

Solo lo que la validación manual no puede observar. **3 archivos nuevos, ~18 casos**. Los
existentes no se modifican (CE-004):
- `tests/test_epos.py`: bits con `W=375` y último byte parcial alineado a la derecha; longitud
  inválida, XML inválido, DOCTYPE, `epos-print` ausente y cuerpo >8 MiB → error; namespace con
  prefijo arbitrario; elemento desconocido ignorado; `code=""` presente en éxito.
- `tests/test_epos_integration.py` (ASGI + 9100 falsa de `conftest.py`): documento de
  recibo → bytes en la impresora falsa y `success="true"`; impresora caída → `EX_BADPORT`;
  plazo corto con impresora lenta → `EX_TIMEOUT` antes del plazo; CORS de un segundo dominio
  permitido y de otro rechazado; `image_to_escpos_raster` byte-idéntico a un vector fijo.
- `tests/test_config_ports.py`: `http_port` ausente/presente; choque `port`/`http_port` rechazado;
  `odoo_domain` texto y lista; clasificación propio/ajeno (función pura sobre nombre y cmdline);
  `_bind_listener` acepta `127.0.0.1` y `::1`; un puerto ocupado deja los demás arriba.

## Estructura

```text
specs/001-protocolo-epos-para-odoo-20-en-el-daemon/
├── spec.md  research.md  plan.md  tasks.md
└── contracts/epos.md        # petición/respuesta ePOS exactas (lo que consume Odoo 20)

posprintproxy/
├── __init__.py              # __version__ = "2.1.0"
├── daemon/
│   ├── epos.py              # NUEVO: parser ePOS, render ESC/POS, respuesta SOAP, router
│   ├── iotbox.py            # NUEVO: rutas /hw_proxy/* y /printers movidas sin cambios de contrato
│   ├── proxy_server.py      # fábrica de app: lifespan, CORS multi-origen, incluye ambos routers
│   ├── printer_backend.py   # + raster_to_escpos, send_raw_win32, timeout en _send_raw
│   ├── printer_manager.py   # + Printer.send_escpos(data, deadline)
│   ├── ports.py             # NUEVO: dueño del puerto (psutil), propio/ajeno, _bind_listener
│   ├── daemon.py            # D2/D5: pre-bind, http_port, port_warnings, versión 2.1.0
│   └── config_manager.py    # http_port, odoo_domain lista, unicidad de puertos
└── gui/
    ├── controllers/config_ctrl.py   # _printer_to_dict, _create_default (18072)
    ├── dialogs/printer_dialog.py    # _suggest_defaults, _collect conserva http_port
    ├── views/printers_view.py       # dominios separados por coma
    ├── views/dashboard_view.py      # allowed_origins, port_warnings en el texto existente
    └── tray.py                      # port_warnings en el tooltip existente
installer/setup.iss (2.1.0) · installer/posprintproxy.spec (psutil) · requirements.txt
README.md · HITOS.md (Odoo 19 y 20, IP con puntos) · tests/ (3 archivos nuevos)
```

**Nota de alcance GUI**: los cambios en `dashboard_view.py` y `tray.py` solo añaden
texto a etiquetas existentes, porque FR-014 exige el aviso en panel y bandeja. `printers_view`
se toca por FR-020. Ningún widget nuevo (FR-016).

**Orden** (dependencias): config y puertos → compartido (raster/transporte/`send_escpos`) →
`iotbox.py` (mover) → `epos.py` → app/CORS → daemon (pre-bind, HTTP, avisos) → GUI mínima →
versión/docs. El MVP (H1) se alcanza tras `epos.py` + app, con el puerto HTTPS actual.

## Riesgos

- **S7 (spike)**: que Chrome con LNA acepte `http://127.0.0.1` sin preflight. Se prueba en el E2E
  de H3. Si Chrome exige preflight, D8 ya lo responde.
- **D6 en Windows**: inferido de la stdlib, se confirma en el E2E (Odoo 20 con `127.0.0.1`).
- **Refactor USB** (`send_raw_win32`): solo se valida en Windows. Lo cubre el E2E de H4 (Odoo 19
  USB: recibo y cajón).
- **Timeout vencido con el trabajo en curso**: puede producir un ticket duplicado (D1, aceptado).
