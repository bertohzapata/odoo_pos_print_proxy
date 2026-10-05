# Tasks: Protocolo ePOS para Odoo 20 en el daemon

**Feature**: `001-protocolo-epos-para-odoo-20-en-el-daemon` | **Spec**: `spec.md` | **Plan**: `plan.md` |
**Contrato**: `contracts/epos.md` | **Módulo**: `posprintproxy/daemon` (+ GUI mínima, FR-014/016/020)

Presupuesto estándar: 40 tareas; aquí hay 32. `[P]` = archivos distintos, sin dependencias pendientes.
Historias: US1 = H1 (recibos/comandas), US2 = H2 (cajón + Test), US3 = H4 (errores + Odoo 19 intacto),
US4 = H3 (HTTP/LNA), US5 = H5 (arranque seguro).

## Fase 1 — Base

- [ ] T001 Añadir `psutil>=5.9` (sin marcador de plataforma) a `requirements.txt` y `psutil` a `hiddenimports` en `installer/posprintproxy.spec`; instalar en el venv con `harness/scripts/test-env.sh instalar app` (plan D4)

## Fase 2 — Cimientos (bloquean todas las historias)

- [ ] T002 [P] Config en `posprintproxy/daemon/config_manager.py`: `PrinterConfig.http_port: int | None = None` (validado 1–65535, leído en `_parse_printer` solo si existe, nunca en legacy); unicidad sobre `port ∪ http_port` con mensaje que nombre los puertos que chocan; `AppConfig.odoo_domain: str | list[str]` conservando la forma leída; property `allowed_origins -> list[str]` (sin barra final, sin vacíos) que sustituye a `allowed_origin` (plan D8)
- [ ] T003 [P] Compartido en `posprintproxy/daemon/printer_backend.py`: extraer `raster_to_escpos(rows: bytes, bytes_per_line: int, height: int) -> bytes` (bloque `GS v 0`) y hacer que `image_to_escpos_raster` lo use con salida **byte-idéntica**; `_send_raw` acepta el `timeout` del llamador; nuevo `send_raw_win32(printer_name, data, doc_name)` usado por `print_image_win32`, `open_cashbox_win32` y `print_test_win32` (plan D7)
- [ ] T004 `Printer.send_escpos(data: bytes, deadline: float | None = None)` en `posprintproxy/daemon/printer_manager.py`: `_lock.acquire(timeout=restante)` (si no se obtiene, lanza un `TimeoutError` propio sin enviar nada), despacho a `_send_raw(timeout=restante)` o `send_raw_win32`, y log con destino (plan D1; depende de T003)
- [ ] T005 [P] Nuevo `posprintproxy/daemon/ports.py`: `bind_listener(port) -> socket` con AF_INET6 e `IPV6_V6ONLY=0` (fallback AF_INET `0.0.0.0`), `SO_EXCLUSIVEADDRUSE` en Windows y `SO_REUSEADDR` en POSIX; `port_owner(port)` con `psutil.net_connections` (LISTEN en cualquier dirección) devolviendo PID, nombre y cmdline, y "programa desconocido" si hay `AccessDenied`; función pura `is_own_process(name, cmdline, pid)` según S6, que excluye `os.getpid()` (plan D2, D4, D5, D6)
- [ ] T006 Mover las rutas IoT Box (`/hw_proxy/*`, `/printers`, `_save_debug_print`, `_jsonrpc_response`) de `posprintproxy/daemon/proxy_server.py` a un `APIRouter` en el nuevo `posprintproxy/daemon/iotbox.py`, sin cambiar el contrato; envolver `printer.print_receipt` y `printer.open_cashbox` en `await asyncio.to_thread(...)` (plan D1). `proxy_server.create_app(printer, allowed_origins, debug_save_getter, port)` queda como fábrica: lifespan, CORS e `include_router` (depende de T002)
- [ ] T007 CORS en `posprintproxy/daemon/proxy_server.py`: `origin in allowed_origins`; en preflight de origen permitido conservar las cabeceras actuales y añadir `Access-Control-Allow-Local-Network: true` si llega `Access-Control-Request-Local-Network` (S7); otro origen → 403 como hoy (FR-013, FR-020, plan D8)
- [ ] T008 Daemon en `posprintproxy/daemon/daemon.py`: por cada impresora, `ports.bind_listener(port)` y `server.serve(sockets=[sock])`; cada `serve()` envuelto en una corrutina que captura `BaseException` salvo `CancelledError`; conservar TLS en el puerto principal si `has_ssl()` y HTTP si no (FR-011, S2); pasar `self.config.allowed_origins` a `create_app` y al log de `main()` (plan D2, D6; depende de T002, T005, T006)

**Checkpoint**: `tests/test_proxy_integration.py` y `tests/test_config_network.py` pasan **sin modificarlos**, y el proxy del sandbox responde por `127.0.0.1` y por `::1`.

## Fase 3 — US1: Odoo 20 imprime recibos y comandas (P1) 🎯 MVP

**Prueba independiente**: con la impresora de Odoo 20 en `127.0.0.1:<puerto>`, un recibo y una comanda salen completos y cortados en la 9100 falsa del sandbox.

- [ ] T009 [US1] Parser en el nuevo `posprintproxy/daemon/epos.py`: localizar `{http://www.epson-pos.com/schemas/2011/03/epos-print}epos-print` en cualquier nivel, sin importar el prefijo; rechazar cuerpo >8 MiB y cualquier `<!DOCTYPE`/`<!ENTITY` antes de `ElementTree.fromstring`; recorrer los hijos en orden y devolver una lista de comandos; los elementos y atributos desconocidos se ignoran con log (FR-002, FR-005, FR-006, plan D3, D7)
- [ ] T010 [US1] Imagen en `posprintproxy/daemon/epos.py`: validar `ceil(W·H/8)` bytes; desempaquetar los bits contiguos MSB-first con el último byte parcial alineado a la derecha; reempaquetar en filas con relleno de byte; centrar rellenando en blanco hasta `paper_width` y, solo si `W > paper_width`, reducir proporcionalmente con Pillow; emitir con `raster_to_escpos` y `cut` → avance + `GS V 0` (FR-003, plan D7; depende de T003)
- [ ] T011 [US1] Respuesta y ruta en `posprintproxy/daemon/epos.py`: `soap_response(success, code)` según `contracts/epos.md`, siempre con `<response success code status="0">`, HTTP 200 y `text/xml; charset=utf-8`; `APIRouter` `POST /cgi-bin/epos/service.cgi` que lee `await request.body()` sin mirar `Content-Type`, construye un solo buffer `INIT`+comandos y lo entrega con `asyncio.wait_for(asyncio.to_thread(printer.send_escpos, data, deadline), plazo)` (FR-001, FR-007, FR-010, plan D1)
- [ ] T012 [US1] Incluir el router ePOS en `create_app` (`posprintproxy/daemon/proxy_server.py`) junto al de IoT Box; ambos siempre activos y sin configuración (FR-001, FR-019)

## Fase 4 — US2: Cajón y botón "Test" desde Odoo 20 (P1)

**Prueba independiente**: el botón "Test" de Odoo 20 imprime su ticket sin aviso; `<pulse/>` abre el cajón.

- [ ] T013 [US2] `pulse` → `ESC p 0 25 250` (reutilizar la constante del cajón de `printer_backend.py`, sin duplicarla) y `feed line=N` → `ESC d N` en `posprintproxy/daemon/epos.py` (FR-004)
- [ ] T014 [US2] `text` en `posprintproxy/daemon/epos.py`: `align` → `ESC a`, `em` → `ESC E`, `ul` → `ESC -`, `dw`/`dh` → `GS !`; `&#10;` → salto de línea; codificación `cp437` con `errors="replace"`; restaurar los estilos tras cada elemento; otros atributos se ignoran con log (FR-004, FR-005)

## Fase 5 — US3: Los fallos se ven en Odoo 20 y Odoo 19 no cambia (P1)

**Prueba independiente**: con la impresora apagada, Odoo 20 muestra error; Odoo 19 imprime recibo, comanda y cajón como con v2.0.2.

- [ ] T015 [US3] Mapeo de errores en la ruta de `posprintproxy/daemon/epos.py`: `OSError`/error del spooler → `EX_BADPORT`; `TimeoutError` (lock o envío) o vencimiento del `wait_for` → `EX_TIMEOUT`; documento inválido → `SchemaError`; plazo `min(timeout or 15000, 60000)/1000 − 1.5 s`; toda causa al log con el nombre de la impresora (FR-006, FR-008, FR-009, S1)
- [ ] T016 [US3] Revisar la regresión de Odoo 19: en `posprintproxy/daemon/iotbox.py`, las respuestas JSON-RPC, el log "POS conectado" y el guardado debug quedan idénticos a v2.0.2 (diff del contrato frente a `proxy_server.py` de `main`)

## Fase 6 — US4: Odoo 20 en línea con "Use Local Network Access" (P2)

**Prueba independiente**: con LNA e IP `127.0.0.1:<http_port>`, un recibo y una comanda salen.

- [ ] T017 [US4] Listener HTTP en `posprintproxy/daemon/daemon.py`: si `printer_cfg.http_port` existe, segundo `uvicorn.Server` **sin TLS** sobre la misma app y el mismo loop, con su propio `bind_listener`; log con ambas URLs (FR-012; depende de T008)
- [ ] T018 [P] [US4] GUI mínima en `posprintproxy/gui/controllers/config_ctrl.py`: `_printer_to_dict` escribe `http_port` si existe; `_write` escribe `odoo_domain` con la forma que tenga (texto o lista); `_create_default` usa el puerto 18072 (FR-016, FR-020)
- [ ] T019 [P] [US4] GUI mínima en `posprintproxy/gui/dialogs/printer_dialog.py`: `_collect` conserva el `http_port` del `PrinterConfig` original y rechaza un `port` que choque con cualquier `http_port` usado; `_suggest_defaults` empieza en 18072 (FR-016)
- [ ] T020 [P] [US4] `posprintproxy/gui/views/printers_view.py`: el campo de dominio muestra `", ".join(dominios)`; al guardar separa por comas (un dominio → texto, varios → lista), y `dashboard_view.py:181` muestra `allowed_origins` unidos (FR-020)

## Fase 7 — US5: Arranque seguro con puertos ocupados (P2)

**Prueba independiente**: con un programa ajeno en el puerto de una impresora, sigue vivo; las demás impresoras arrancan y el panel nombra puerto y programa.

- [ ] T021 [US5] En `posprintproxy/daemon/daemon.py`, sustituir `kill_zombies_on_port` (netstat/taskkill) por la secuencia de plan D5 en `_run_thread`: para cada `port`/`http_port`, `port_owner`; si es propio y `kill_zombies_on_startup` está activo → `terminate()`/`wait(3)`/`kill()`; si es ajeno o desconocido → aviso "puerto N ocupado por X (PID p)" y ese listener no arranca; un fallo de `bind_listener` → el mismo aviso (FR-014, FR-015)
- [ ] T022 [US5] Estado en `posprintproxy/daemon/daemon.py`: `DaemonSnapshot.port_warnings: list[str]`; `running_ports` = los puertos realmente enlazados; `RUNNING` si arrancó al menos uno, `ERROR` con `last_error` si ninguno (FR-014, plan D2)
- [ ] T023 [P] [US5] Mostrar `snap.port_warnings` en los textos existentes de `posprintproxy/gui/tray.py:131` y `posprintproxy/gui/views/dashboard_view.py:153`, sin widgets nuevos (FR-014)

## Fase final — Cierre

- [ ] T024 [P] Versión 2.1.0 en `posprintproxy/__init__.py`, en `version=` de `create_app` (leída de `__version__`), en el log de `main()` de `daemon.py` y en `AppVersion` de `installer/setup.iss` (FR-018)
- [ ] T025 [P] `README.md` y `HITOS.md`: "Odoo 19 y 20", configuración de la impresora en cada versión (19: IoT Box; 20: impresora Epson con IP `127.0.0.1:PUERTO`, nunca `localhost`; LNA con `http_port` en el YAML) (FR-018)
- [ ] T026 Arranque limpio: `harness/scripts/test-env.sh instalar app` y `harness/scripts/test-env.sh levantar`; `curl` al ePOS del sandbox por `127.0.0.1:8172` con un documento de `contracts/epos.md` → bytes en la 9100 falsa
- [ ] T027 `harness/scripts/lint.sh` sin errores
- [ ] T028 Registrar en `research.md` las desviaciones que aparecieron (y el resultado del spike S7 cuando llegue el E2E)

## Pruebas

Solo las de plan D9: lo que la validación manual no puede observar. Las pruebas existentes **no se modifican** (CE-004).

- [ ] T029 [P] `tests/test_epos.py` (unitarias, sin red): bits con `W=375` y último byte parcial alineado a la derecha; longitud inválida, XML inválido, `DOCTYPE`, `epos-print` ausente y cuerpo >8 MiB → `SchemaError`; namespace con prefijo arbitrario; elemento desconocido ignorado; en éxito `code=""` presente
- [ ] T030 [P] `tests/test_epos_integration.py` (ASGI + 9100 falsa de `tests/conftest.py`): recibo → bytes en la impresora y `success="true"`; impresora caída → `EX_BADPORT`; plazo corto con impresora lenta → `EX_TIMEOUT` antes del plazo; CORS de un segundo dominio permitido y de otro rechazado; `image_to_escpos_raster` byte-idéntico a un vector fijo
- [ ] T031 [P] `tests/test_config_ports.py`: `http_port` ausente/presente; choque `port`/`http_port` rechazado; `odoo_domain` como texto y como lista; `is_own_process` (propio exe, python con `posprintproxy`, python ajeno, PID propio); `bind_listener` acepta `127.0.0.1` y `::1`; un puerto ocupado deja los demás arriba y aparece en `port_warnings`
- [ ] T032 Correr `harness/scripts/test-env.sh probar app` y pegar el comando y la salida real en el reporte

## Verificación manual (borrador para `validacion-manual.md`, máx. 10 pasos)

1. Instalar v2.1.0 sobre una v2.0.2 en Windows: la config y los certificados siguen, y el panel arranca sin editar nada.
2. Odoo 19: cobrar una orden (recibo + cajón) y mandar una comanda, con una impresora de red y otra USB; salen igual que antes.
3. Odoo 20 local: impresora Epson con IP `127.0.0.1:<puerto>`; botón "Test": imprime sin aviso.
4. Odoo 20: cobrar en efectivo; el recibo sale completo y el cajón abre. Mandar una comanda: sale completa.
5. Repetir el paso 4 con la impresora USB.
6. Apagar la impresora y cobrar: Odoo 20 muestra un error de impresión.
7. Odoo 20 en línea: poner `http_port` en el YAML, marcar LNA con `127.0.0.1:<http_port>` e imprimir un recibo.
8. Con WSL/Docker escuchando en el puerto de una impresora: arrancar el proxy; el otro programa sigue vivo, las demás impresoras imprimen y el panel dice qué programa ocupa el puerto.
9. Dejar el proxy en reposo 10 min con 3 impresoras: CPU ≈ 0 % y RAM comparable a v2.0.2 (Administrador de tareas).

## Dependencias

- T001 → T005. T002 → T006 → T008. T003 → T004 → T011. T005 → T008.
- Fase 2 completa antes de las historias. US1 (T009-T012) antes de US2 y US3, que extienden `epos.py`.
- US4 (T017) necesita T008; T018-T020 solo necesitan T002. US5 necesita T005 y T008.
- Pruebas: T029 tras T009-T014; T030 tras T015 y T007; T031 tras T002, T005 y T022.

## Estrategia

MVP = Fases 1-3 (US1) por el puerto HTTPS actual. Después US2 + US3 (los P1) y, al final, US4 y US5 (P2).
Paralelo: T002, T003 y T005 a la vez; en US4, T018-T020; en el cierre, T024, T025 y T029-T031.
