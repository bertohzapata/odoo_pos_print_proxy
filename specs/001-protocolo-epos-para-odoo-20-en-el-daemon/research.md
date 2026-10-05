# Research: 001 — Protocolo ePOS para Odoo 20 en el daemon

Fase A (especificador). Grafo codebase-memory disponible (`home-bertohzapata-pos_print_proxy`);
lecturas directas para el daemon (≈1 300 líneas) y para Odoo 20 (fuera del grafo).

## Qué existe hoy (verificado)

- **Un servidor por impresora**: `daemon.py:252` `_serve_all` crea un `uvicorn.Server` por
  impresora (`host="::"`, `port=printer_cfg.port`, TLS si `has_ssl()`), todos en **un** event loop
  del hilo `ProxyDaemon` (`asyncio.gather`, `:312`). Sin cert, el puerto sirve HTTP (`:254-255`).
- **App FastAPI por impresora**: `proxy_server.py:110` `create_app(printer, allowed_origin,
  debug_save_getter, port)`. Rutas `/hw_proxy/{hello,status_json,handshake,default_printer_action}`
  y `/printers`. Callers (grafo): `_serve_all` y `tests/test_proxy_integration.py::_make_app`.
- **CORS/PNA**: middleware `proxy_server.py:139`. Solo el origen exacto `allowed_origin`
  (`odoo_domain` sin barra). `OPTIONS` de origen permitido → 204 con `Allow-Methods GET, POST,
  OPTIONS`, `Allow-Headers Content-Type, Authorization`, `Allow-Private-Network: true`. Otro
  origen → 403. En respuestas normales añade `Allow-Origin`, `Allow-Private-Network`, `Vary`.
- **Printer** (`printer_manager.py:27`): `print_receipt(b64)` (JPEG/PNG → raster) y
  `open_cashbox()`, ambos bajo `self._lock` y despachando a red (`print_image_network`,
  `open_cashbox_network`) o USB (`print_image_win32`, `open_cashbox_win32`). No hay método para
  enviar bytes ESC/POS ya construidos.
- **Raster** (`printer_backend.py:26` `image_to_escpos_raster`): reescala a `paper_width` con
  LANCZOS, convierte a `"1"`, empaqueta filas con relleno a byte (MSB primero, negro = 1) y emite
  `INIT` + `GS v 0` + datos + `FEED` + `CUT`. El empaquetado pixel→bit está acoplado a PIL; no hay
  helper "bits → ESC/POS" separable todavía.
- **Transporte red** `_send_raw` (`:151`, conexión corta, timeout 10 s). USB: `win32print` con
  documento RAW, duplicado en 3 funciones (`print_image_win32`, `open_cashbox_win32`,
  `print_test_win32`). Cajón: `INIT + ESC p 0 25 250`.
- **Ticket de prueba de texto** `_build_test_ticket` (`:222`): ya usa `ESC a` (alineación),
  `ESC E` (negrita), `FEED`, `CUT` — referencia para el texto ePOS.
- **Zombies** `daemon.py:64` `kill_zombies_on_port`: solo win32; `netstat -ano`, toma todo PID en
  `LISTENING` con `:{port} ` y hace `taskkill /F` **sin mirar qué proceso es**. Único caller:
  `_run_thread` (`:219`), si `kill_zombies_on_startup` (default True). Es el bug que tumbó el
  reenvío de WSL/Docker. `netstat` puede tardar 8-12 s (comentario `:72`).
- **Config** `config_manager.py:44` `PrinterConfig(name, port, windows_printer, paper_width, role,
  connection, host, tcp_port)`; `_parse` (`:132`) valida puertos y nombres únicos; `_parse_printer`
  (`:183`) default `port` 8072; legacy `_parse_legacy` (`:205`) 8072/8073. Errores de config →
  `sys.exit(1)` en `load_config`.
- **Estado para la GUI**: `DaemonSnapshot(status, running_ports, last_error)` (`daemon.py:44`);
  lo pintan `gui/tray.py:131-135` y `gui/views/dashboard_view.py:153-156`. `running_ports` = los
  `port` de todas las impresoras si RUNNING (no refleja puertos que fallaron).
- **Versión**: `posprintproxy/__init__.py:3` `2.0.2`; `proxy_server.py:129` `version="2.0.2"`;
  `daemon.py:336` log `v2.0.0` (desfasado); `installer/setup.iss:22` `AppVersion "2.0.0"`.
- **Ya hecho por la enmienda v2.0.0** (no es trabajo de 001): `lint.sh:12` base `main`;
  `AGENTS.md:288-292` regla de línea única.
- **Sandbox** `test-env.sh levantar`: config con `kill_zombies_on_startup: false`, proxy en 8172,
  impresora falsa 9100 (`tools/fake_9100_printer.py`), `odoo_domain: http://localhost:8069`.
- **Pruebas existentes**: `tests/test_config_network.py` (8 casos de `PrinterConfig`),
  `tests/test_network_backend.py`, `tests/test_proxy_integration.py` (FakePrinter TCP en
  `conftest.py`; prueba impresión, cajón y concurrencia contra `create_app`).

## Contrato Odoo 20 (leído en `~/odoo20/src/addons/point_of_sale/`)

- **URL** (`epson_printer.js:131-134`): `{http: si use_lna | https:}//{printer_ip}/cgi-bin/epos/
  service.cgi?devid=local_printer&timeout={ms}`; `timeout` default 15000 ms (`:128`), el fetch
  aborta a los `timeout` ms (`:170`).
- **Petición** (`:167-176`): `POST`, body = string XML, **sin cabecera `Content-Type`** → el
  navegador manda `text/plain;charset=UTF-8` (petición CORS simple, sin preflight clásico). Con
  LNA añade `targetAddressSpace` (`init_lna.js:57-68`: `127.0.0.1`/`localhost` → `loopback`).
- **Sobre** (`components/epos_templates.xml:3-9`): `<s:Envelope xmlns:s="http://schemas.xmlsoap.
  org/soap/envelope/"><s:Body><epos-print xmlns="http://www.epson-pos.com/schemas/2011/03/
  epos-print"/>`. `ePOSPrint` quita `xmlns=""` de los hijos (`:15-21`): los hijos quedan en el
  namespace por defecto de `epos-print`.
- **Recibo/comanda** (`processCanvas`, `:101-116`): `<image width=W height=H align="center">B64
  </image><cut type="feed"/>`. Canvas generado a `maxWidth` del `STYLE_MAPPING`
  (`pos_ticket_printer_plugin.js:542,573-580`, `pixelRatio: 1`): 512 (80 mm), 360 (58 mm), y
  modelos Epson 200/180/150/400/380/**375**/240 (`epson_printer.js:136-147`).
- **Cajón** (`:150-153`): `<pulse/>` sin atributos, resultado no se espera (`sendPrintingJob` sin await).
- **Botón Test** (`backend/test_epos/test_epos.js:34-46`): `<feed line="1"/><text align="center">
  Test print for printer NAME&#10;</text><feed line="3"/><cut type="feed"/>`. URL **sin**
  `timeout`; protocolo `http:` con LNA o `window.location.protocol` sin LNA (`:99-100`); abort a
  15 s. Éxito solo si `success === "true"` **y** `code === ""` (`:119-121`).
- **Respuesta** (`epson_printer.js:177-195`): `DOMParser(application/xml)` →
  `querySelector("response")` → `success`, `code`, `parseInt(status) || 0`. Cualquier excepción
  (red, CORS, XML sin `response` → `null.getAttribute`) → `PRINTER_NOT_REACHABLE`.
  Bits de estado: `0x00080000` sin papel, `0x00020000` casi sin papel (`:7-8`).
- **Códigos que Odoo traduce** (`test_epos.js:8-22`, `epson_printer.js:225-241`): `DeviceNotFound`,
  `EPTR_COVER_OPEN`, `EPTR_REC_EMPTY`, `EX_BADPORT`, `EX_TIMEOUT`, etc.; otros → mensaje genérico
  con el código.
- **IP** (`models/pos_printer.py:10-26`): `printer_ip` sin punto → dominio
  `*.omnilinkcert.epson.biz`. `127.0.0.1:18072` es válido; `localhost:18072` no.
- `paper_size == "label"` va a Zebra `/pstprnt` (`test_epos.js:143-160`): fuera de alcance.

## El hueco real

1. No hay ruta `/cgi-bin/epos/service.cgi`, ni parser ePOS, ni respuesta SOAP.
2. No hay forma de enviar ESC/POS arbitrario a una `Printer` (solo imagen JPEG o cajón).
3. Un solo listener por impresora (TLS o no); falta el listener HTTP adicional.
4. El arranque mata cualquier proceso del puerto.
5. `http_port` no existe en config, y la GUI lo perdería al guardar (ver trampas).

## Integraciones concretas (verificadas)

- Nuevo módulo de protocolo en `posprintproxy/daemon/` (Principio III), llamado desde
  `create_app` como router adicional; el middleware CORS actual ya cubre `OPTIONS` para cualquier
  ruta, así que la ruta ePOS lo hereda.
- `Printer` necesita un envío de bytes ESC/POS bajo el mismo `_lock` (FR-010).
- Extraer de `image_to_escpos_raster` el empaquetado filas-de-bits → `GS v 0` para que lo usen el
  JPEG (Odoo 19) y el raster ePOS (Odoo 20) sin duplicar; salida de Odoo 19 debe quedar
  byte-idéntica (regresión, CE-004).
- `_serve_all`: segundo `uvicorn.Server` por impresora sobre la misma app, mismo loop.
- `config_manager`: campo opcional + unicidad sobre el conjunto `port ∪ http_port`.
- GUI mínima: `config_ctrl._printer_to_dict` (`:95`), `printer_dialog._collect` (`:189`) y
  `_suggest_defaults` (`:181`), `config_ctrl._create_default` (`:55`, puerto 8072).

## Dependencias

Ninguna de runtime nueva. XML con `xml.etree.ElementTree` (stdlib; ⚠ ver trampa XXE abajo).
Identificar el proceso dueño de un puerto en Windows: `netstat -ano` ya da el PID; el nombre sale
de `tasklist /FI "PID eq N"` (stdlib + comando de Windows). `psutil` resolvería ambos pero sería
dependencia nueva (requirements + installer): decisión del plan.

## Trampas conocidas

- **Último byte del raster**: `encodeRaster` toma trozos de 8 caracteres y hace `parseInt(sub, 2)`;
  si `W×H` no es múltiplo de 8, el último trozo (<8 bits) queda **alineado a la derecha**, no MSB.
  Afecta solo a los últimos píxeles del ticket, pero el parser no debe desalinear ni fallar por
  ello. Filas: sin relleno, cada fila empieza en el bit `y×W`.
- **Longitud esperada**: `ceil(W×H/8)` bytes. Más o menos → documento inválido (FR-006).
- **`code` vacío**: si falta el atributo, `getAttribute` da `null` y el botón Test avisa fallo.
- **XML sin `response`** hace lanzar a Odoo → `PRINTER_NOT_REACHABLE`, que oculta la causa real:
  toda respuesta, incluso de error, debe llevar `response`.
- **Bucle bloqueante**: los handlers son `async def` que llaman a impresión bloqueante (socket/
  spooler) dentro del único event loop (`proxy_server.py:231,235`). Una impresión lenta congela
  todos los puertos, incluido el HTTP nuevo, y hace imposible cumplir FR-009 (timeout). Ya pasa
  con Odoo 19; ePOS no debe empeorarlo. Decisión del plan (p. ej. ejecutar en hilo).
- **Timeout de red** `_send_raw` = 10 s < 15 s de Odoo; el botón Test no manda `timeout`.
- **GUI pierde campos**: `_printer_to_dict` escribe una lista cerrada de claves y `_collect`
  construye `PrinterConfig` sin `http_port`: guardar o editar desde la GUI borraría el campo.
- **Puerto 8072 por defecto** choca con Odoo (longpolling/websocket); el sandbox ya usa 8172 por eso.
- **Puerto ocupado hoy**: uvicorn, al fallar el bind, hace `sys.exit(STARTUP_FAILURE)`
  (`.venv/.../uvicorn/server.py:180-183`). `SystemExit` no es `Exception`: el `except` de
  `_run_thread` (`daemon.py:241`) no lo atrapa, el hilo muere y el estado **se queda en RUNNING**
  (se fijó en `:308` antes del `gather`), con `running_ports` listando todos los puertos. Con
  2 listeners por impresora el riesgo se duplica. Relevante para FR-014.
- **XXE / bomba de entidades**: `ElementTree` expande entidades internas; el endpoint escucha en
  `::` (todas las interfaces). Rechazar DTD o limitar tamaño del cuerpo: decisión del plan.
- **`host="::"`**: el HTTP sin TLS también queda expuesto en la LAN, no solo en loopback.
- **Filtro de procesos propios**: en dev el proceso es `python`, igual que otros pythons ajenos;
  hay que distinguir por línea de comandos, no solo por nombre.
- **Versión desfasada** en `daemon.py:336` y `setup.iss:22`: unificar en 2.1.0.

## Qué puede romperse (actualización)

- Odoo 19: cambios en `create_app`, middleware CORS, `Printer`, raster y `_serve_all`. Red de
  seguridad: `tests/test_proxy_integration.py` sin modificar + E2E Odoo 19.
- Configs v2.0.2 (nuevo y legacy): `tests/test_config_network.py` sin modificar.
- Arranque en Windows si el nuevo filtro de zombies falla o tarda (`netstat` + consulta de nombre).
- Auto-update: `gui/controllers/update_ctrl.py` compara versión; el tag debe ser `v2.1.0`.

## Abierto para el clarify

Marcado en spec.md: FR-003 (ancho del raster), FR-012 (http_port automático o manual), FR-014
(puerto ajeno: alcance del fallo y visibilidad). Supuestos ⚠ S1-S6 a confirmar; S7 es spike.

## Clarify

2026-09-25 — 4 preguntas (ancho de imagen, http_port explícito, puerto ocupado, supuestos S1–S6: S3→lista de dominios FR-020, S4→estilos básicos); registradas en spec.md `## Clarifications`.

## Plan (fase B)

Grafo: `get_architecture` sobre `posprintproxy/daemon` (78 nodos) y `trace_path` de `create_app`
(callers: `_serve_all` y 3 pruebas de `test_proxy_integration.py`). Además, lectura directa de
`proxy_server.py`, `daemon.py`, `printer_manager.py`, `config_manager.py`, `printer_backend.py`,
`config_ctrl.py`, `printer_dialog.py` y `printers_view.py`. Decisiones en `plan.md` D1-D9.

Hallazgos verificados en esta fase:
- **`host="::"` no es dual-stack** (D6). `asyncio/base_events.py:1554-1558` fija
  `IPV6_V6ONLY=True` en los sockets AF_INET6. Comprobado ejecutando en el venv: `create_server(
  host="::", port=18999)` → `127.0.0.1` "Connection refused" y `::1` OK. Odoo 20 exige `127.0.0.1`.
  Windows: inferido del mismo código (sin rama de plataforma), se confirma en el E2E.
- **uvicorn 0.52.4** (`server.py`): con `serve(sockets=[...])` usa `create_server(sock=...,
  ssl=config.ssl)` (`:126-148`) y no pasa por el `sys.exit(STARTUP_FAILURE)` del bind (`:173-183`).
- **expat 2.6.1** en el venv (≥2.4: con protección de amplificación). De todos modos, D3 rechaza DTD.
- **`psutil` 7.2.2** tiene wheel abi3 para Linux (descargada) y existe para win_amd64. No está
  en el venv: `ModuleNotFoundError`.
- Versiones del venv: FastAPI 0.141.1, Starlette 1.6.0, uvicorn 0.52.4, Python 3.12.3.
- Odoo 20 traduce `DeviceNotFound`, `EPTR_*`, `EX_BADPORT` y `EX_TIMEOUT` (`test_epos.js:8-22`).
  Cualquier otro código (p. ej. `SchemaError`) sale como mensaje genérico con el código
  (`epson_printer.js:236-241`).
- Usos de `allowed_origin`: `daemon.py:276,337` y `dashboard_view.py:181`. `odoo_domain` como
  texto: `printers_view.py:128,160`, `config_ctrl.py:79,121` y `system_view.py:229`.
- `running_ports` y `last_error` solo se pintan en `tray.py:131-135` y `dashboard_view.py:153-156`.

Supuesto nuevo (no verificado): el nombre de la cabecera del preflight de Local Network Access
de Chrome (`Access-Control-Request-Local-Network` o `-Private-Network`). D8 responde a ambas.
Va con el spike S7.

## Analyze

`/speckit-analyze` corrido el 2026-09-25 sobre `spec.md` (237 líneas), `plan.md` (249) y `tasks.md` (32 tareas).
Cobertura: 20 de 20 FR tienen tarea o decisión de plan. FR-017 no tiene tarea propia: lo cubren
plan D1 (sin hilos nuevos) y el paso manual 9. Los CE-001…007 quedan en la verificación manual.
Resultado: **0 CRITICAL, 0 HIGH, 3 MEDIUM, 4 LOW**.
- M1 (corregido): FR-011 (TLS en el puerto principal con el socket pre-enlazado) no se citaba
  en T008. Ahora T008 lo dice.
- M2 (corregido): el refactor USB compartido (T003) toca Odoo 19. El paso manual 2 exige ahora red **y** USB.
- M3 (abierto, para el Gate 1): S8. El puerto HTTP sin TLS queda visible en la LAN; lo acepta o
  lo rechaza el propietario.
- L1: el nombre de la cabecera del preflight LNA no está verificado (va con el spike S7).
- L2: `contracts/epos.md` añade `battery="0"` a la respuesta. Es inocuo y Odoo no lo lee.
- L3: `psutil` es multiplataforma, así que el cierre de procesos propios también actúa en Linux.
  El sandbox usa `kill_zombies_on_startup: false`.
- L4: la release o tag `v2.1.0` para el auto-update (CE-007) es trabajo de cierre, no de tarea.
Constitución: sin conflictos. Las pruebas son 3 archivos, solo de lo no observable. `psutil`
está justificada y va en `requirements` y en el spec de PyInstaller. Los protocolos quedan en
módulos separados y la 9100 falsa se usa en `levantar`.
Checklist `checklists/protocolo.md` (20 ítems): CHK001-003, 011, 014-017 y 019 se cerraron
editando la spec (FR-001, 006, 009, 014 y 016, más S8). El resto queda para el revisor.
