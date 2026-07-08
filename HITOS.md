# Hitos y Roadmap — POS Print Proxy

> Documento vivo. Se actualiza al final de cada sesion de trabajo agregando:
> hitos completados, bugs descubiertos/resueltos, decisiones tomadas y notas
> de sesion en el changelog. Para definicion estatica de la app, ver
> [ESPECIFICACIONES.md](ESPECIFICACIONES.md).

---

## Estado actual

- **Version**: 2.0.1
- **Ultima actualizacion**: 2026-07-08
- **Resumen**: v2.0.1 corrige tres bugs de primer arranque en produccion
  encontrados al probar el installer real: (1) uvicorn fallando por
  `sys.stdout=None` en PyInstaller windowed, (2) `netstat -ano` con
  timeout muy corto congelando la GUI, (3) subprocess flasheando ventanas
  CMD por falta de CREATE_NO_WINDOW.

Fase 2 completada. App GUI nativa PySide6 con dashboard, gestion
  de impresoras, visor de logs en tiempo real, gestor de certificado con
  renovacion en un click, panel de sistema (auto-inicio, verbose, retencion),
  y auto-actualizacion via GitHub Releases con notificacion en la bandeja del
  sistema. System tray icon con menu completo. Codigo empaquetable como .exe
  via PyInstaller + Inno Setup (build local y CI listos). El daemon FastAPI/
  uvicorn de v1.4 vive ahora embebido y controlado por hilos worker. Se
  descartan `config.yaml`/consola/`start_proxy.bat` como interfaz de usuario;
  quedan como fallback para desarrollo.

---

## Hitos completados

### v2.0.1 — Fixes de primer arranque en produccion

Al probar el `.exe` real generado por el CI, tres bugs sobre PyInstaller
`--windowed` bloquearon el arranque del daemon:

- **Uvicorn crasheaba con `Unable to configure formatter 'default'`**:
  uvicorn intenta configurar un ColourizedFormatter que llama
  `sys.stdout.isatty()`, pero en modo `--windowed` `sys.stdout` es `None`
  y falla con `AttributeError`. Fix: pasar `log_config=None` a
  `uvicorn.Config` (ya tenemos nuestro propio logger)
- **`sys.stdout`/`sys.stderr` = None** rompiendo prints tempranos de
  `config_manager.py`. Fix: guard global en `posprintproxy/__main__.py`
  que reemplaza streams None con buffers en memoria
- **`netstat -ano` timeout de 5s** demasiado corto para Windows con muchas
  conexiones. Fix: subido a 30s + `CREATE_NO_WINDOW` para no flashear CMDs
- **`kill_zombies_on_port` bloqueaba la GUI** hasta 15s. Fix: movido al
  hilo worker (`_run_thread`) para que `daemon.start()` retorne inmediato
- **`mkcert` flasheaba CMD** al instalar CA y generar cert. Fix: mismo
  `CREATE_NO_WINDOW` en `cert_ctrl.py`

### v2.0.0 — Fase 2: app nativa PySide6 + tray + auto-update + installer

Cierre completo de Fase 2 del roadmap. Salto de version mayor porque cambia
la superficie de instalacion, la forma de configurar y la manera de arrancar.

**Reestructura a paquete Python**:
- Todo el codigo v1.4 se mueve dentro del paquete `posprintproxy/` con
  subpaquetes `daemon/`, `gui/`, `util/`
- Root del repo queda con `main.py` (shim retrocompat), `config.yaml.default`
  (plantilla para el installer), `installer/`, `.github/workflows/`
- Entry point unificado: `python -m posprintproxy` lanza la GUI;
  `python -m posprintproxy --daemon` corre solo el daemon (retrocompat v1.4)

**Daemon embebible (`posprintproxy.daemon.ProxyDaemon`)**:
- Antes: `asyncio.run(...)` bloqueante como main
- Ahora: clase con `start()/stop()/restart()` que corre uvicorn en un thread
  worker con su propio event loop, controlable desde la GUI
- Estado observable via `snapshot() -> DaemonSnapshot(status, running_ports, last_error)`
- Enum `DaemonStatus`: STOPPED / STARTING / RUNNING / STOPPING / ERROR

**GUI PySide6 con look propio (no template AI)**:
- Tema dark custom en `theme.qss`, ~350 lineas: paleta oscura con acento
  turquesa `#40c2b2`, tipografia Segoe UI, mono Cascadia para logs,
  cards con radio 8px, sidebar con borde-acento en estado activo
- Ventana con sidebar de 5 vistas: Dashboard / Impresoras / Logs / Certificado / Sistema
- Cierre a bandeja (X esconde en tray, no cierra; salir real desde menu tray)

**Dashboard (`views/dashboard_view.py`)**:
- Estado del daemon en tiempo real con badge de color + dot indicator
- Botones grandes Iniciar / Detener / Reiniciar (habilitados segun estado)
- Card de resumen: dominio Odoo + numero de impresoras + puertos activos

**Impresoras (`views/printers_view.py`)**:
- Tabla con Nombre / Puerto / Windows Printer / Ancho / Rol
- Botones Agregar / Editar / Eliminar
- Dialogo modal `PrinterDialog` con autocomplete de impresoras Windows
  detectadas + validacion (puerto libre, nombre unico, rol valido)
- Guardado en config.yaml en tiempo real. Advertencia si el daemon esta
  corriendo (requiere reinicio para tomar efecto)

**Logs en tiempo real (`views/logs_view.py`)**:
- Subscripcion al logger raiz via `QtLogHandler` que emite senales Qt
- Ring buffer de 2000 lineas; filtro por nivel (Todos / INFO+ / WARN+ / ERROR)
- Auto-scroll toggleable, colores por nivel, boton exportar a TXT

**Certificado (`views/cert_view.py`, `controllers/cert_ctrl.py`)**:
- Inspeccion con `cryptography`: sujeto, emisor, fechas, dias restantes
- Alerta visual si expira en <30 dias o ya expiro
- Boton "Renovar ahora": corre mkcert en QThread, muestra progreso, feedback
- Auto-descarga de `mkcert.exe` si no esta bundleado

**Sistema (`views/system_view.py`)**:
- Toggle auto-inicio con Windows (via registro HKCU\\Run), sin admin
- Toggle verbose + spin de retencion de logs, guardado a config
- Botones "Abrir carpeta de logs" / "Abrir carpeta de datos"
- Panel de actualizaciones: version actual + estado consulta + boton "Buscar ahora"

**System tray (`gui/tray.py`)**:
- Icono dinamico (verde=running, gris=stopped, rojo=error) generado en runtime
- Menu contextual: Estado / Abrir dashboard / Iniciar / Detener / Reiniciar /
  Ver logs / Certificado / (Actualizacion disponible) / Salir
- Click izquierdo abre el dashboard; tooltip muestra estado + puertos activos
- Notificacion nativa cuando hay update disponible

**Auto-actualizacion (`controllers/update_ctrl.py`)**:
- Consulta GitHub Releases API 1 min despues del arranque, luego cada 24h
- Parseo semver (`util/version.py`), comparacion segura
- Emite `update_found` con `UpdateInfo(latest_version, download_url, notes)`
- Tray muestra item "Actualizar a vX.Y.Z" + notificacion nativa Windows

**Persistencia y paths (`util/paths.py`)**:
- Instalado: `%APPDATA%\\POSPrintProxy\\{config.yaml, certs/, logs/}`
- Dev (repo clonado): todo relativo al cwd
- Deteccion via `sys.frozen` (PyInstaller flag)
- Certs persisten en desinstalacion (preservados para renovacion futura)

**Auto-inicio Windows (`util/autostart.py`)**:
- Habilita/deshabilita entrada en `HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run`
- Flag `--minimized` para arrancar en la bandeja sin abrir dashboard
- Sin admin requerido

**Installer y CI**:
- `installer/build_exe.py`: wrapper de PyInstaller, descarga mkcert.exe si falta
- `installer/posprintproxy.spec`: spec explicito de PyInstaller
- `installer/setup.iss`: Inno Setup 6, espanol+ingles, detecta version previa
  y la desinstala silenciosa antes, preserva `%APPDATA%\\POSPrintProxy\\`
- `installer/build_local.bat`: build end-to-end local (Windows + Python + Inno)
- `.github/workflows/release.yml`: CI que en cada tag `v2.*` bundlea el
  installer y lo sube a Releases

**Dependencias nuevas**:
- `PySide6>=6.6.0`, `cryptography>=42.0`
- Dev: `pyinstaller>=6.6.0`

**Retirado / reemplazado**:
- `setup_https.bat` (reemplazado por el boton "Renovar" en la vista Cert)
- Los modulos flat `app.py`, `config_manager.py`, `logger_setup.py`,
  `printer_manager.py`, `proxy_server.py`, `printer_backend.py` en la raiz
  (todos migrados a `posprintproxy/daemon/`)
- Edicion manual de `config.yaml` como UX principal (queda solo como
  fallback en dev; la GUI escribe el YAML por ti)

**Validacion realizada en esta sesion**:
- Sintaxis Python de los 20 modulos del paquete: OK
- Imports cruzados del paquete completo (mock de win32print): OK
- Instanciacion headless de la GUI (QT_QPA_PLATFORM=offscreen): OK
- Renderizado de las 5 vistas capturadas como PNG para validar tema: OK
- Config legacy (v1.4 formato) sigue cargando por retrocompat automatica

### v1.4.0 — Fase 1: refactor modular + multi-impresora + logs archivo

Cierre completo de Fase 1 del roadmap.

**Refactor modular**:
- `main.py` (290 lineas monoliticas) partido en 5 modulos con responsabilidad
  clara:
  - `app.py` — entry point, orquestacion, banner, cert self-test, zombie kill
  - `config_manager.py` — parseo + validacion + retrocompat legacy
  - `logger_setup.py` — consola + archivo rotativo + silenciado de terceros
  - `printer_manager.py` — Printer dataclass + detect_or_warn
  - `proxy_server.py` — fabrica de FastAPI por impresora + middleware + endpoints
- `main.py` queda como shim delgado que llama a `app.main()` (retrocompat con
  `start_proxy.bat` y docs existentes)

**Multi-impresora**:
- Nuevo esquema `printers:` en config.yaml con lista de impresoras. Cada una
  con `name`, `port`, `windows_printer`, `paper_width`, `role`
- Roles informativos: `receipt` / `kitchen` / `bar` / `both` (etiquetas para
  logs, la asignacion real la hace Odoo via `product_categories_ids`)
- Cada impresora arranca su propia instancia FastAPI en su puerto. Todas se
  levantan en paralelo con `asyncio.gather()`
- Validacion de puertos y nombres unicos al arrancar
- Retrocompat automatica: si config.yaml tiene el formato legacy (`printer_name`
  + `kitchen_printer_name` en el top-level), se convierte internamente al
  esquema nuevo sin que el usuario tenga que migrar

**Logs a archivo con rotacion**:
- `TimedRotatingFileHandler` a `logs/proxy.log`, rota a medianoche
- Retencion configurable (`log_retention_days`, default 30)
- Formato de archivo con timestamp completo `YYYY-MM-DD HH:MM:SS` y nombre de
  logger (util con multi-impresora)
- Formato de consola compacto `HH:MM:SS` como antes
- Si no se puede escribir a archivo (permisos, disco), sigue con consola y
  emite `WARN` una sola vez

**Testing**:
- Nuevo `TESTS.md` con 11 tests manuales (A-K) cubriendo arranque, hello,
  handshake, impresion recibos, impresion cocina, cajon, modo offline,
  recuperacion de zombies, retrocompat legacy, multi-impresora paralela,
  y logs persistentes

**Ajustes globales nuevos en config.yaml**:
- `verbose: false` (ya existia, ahora tambien afecta el archivo de log)
- `log_dir: "logs"`
- `log_retention_days: 30`
- `kill_zombies_on_startup: true`

### v1.3.1 — Bind dual-stack + proteccion contra zombies

- Cambio de `host="127.0.0.1"` a `host="::"` en el bind de uvicorn. En
  Windows 11 (25H2 confirmado) el navegador puede resolver `localhost` a
  `::1` (IPv6). Con bind exclusivo a IPv4 el proxy se volvia inalcanzable
  desde el navegador aunque el proceso siguiera arriba
- `start_proxy.bat` ahora detecta y mata cualquier proceso zombie que este
  escuchando en el puerto 8072 antes de arrancar el nuevo. Esto previene
  la acumulacion de instancias huerfanas cuando el usuario cierra la
  ventana CMD sin `Ctrl+C` (uvicorn en Windows no siempre limpia sockets)
- Version banner actualizada a v1.3.1 con nota "bind dual-stack IPv4+IPv6"

### v1.3 — Estabilidad y logs limpios

- Cambio del event loop a `WindowsSelectorEventLoopPolicy` para suprimir
  los `ConnectionResetError [WinError 10054]` del Proactor con TLS
- Exception handler custom en el lifespan de FastAPI como respaldo
  (silencia `ConnectionResetError`, `ConnectionAbortedError`,
  `BrokenPipeError` en la fuente, no via filtro fragil de logging)
- Logging estructurado por niveles: INFO por default, DEBUG opcional con
  `verbose: true` en config.yaml
- Logger de `uvicorn.access` desactivado; `asyncio` silenciado a CRITICAL
- Mensajes informativos: "POS conectado" una sola vez, "Impreso en X (N bytes)"
  por cada trabajo
- Self-test del certificado HTTPS al arrancar (valida que `localhost.pem`
  y `localhost-key.pem` cargan correctamente)
- Bind a `127.0.0.1` en lugar de `0.0.0.0` (mas seguro, evita exposicion LAN)
- Hostname del equipo loggeado al iniciar (ayuda a identificar tienda en
  soporte multi-sucursal)

### v1.2 — HTTPS local con mkcert

- Script `setup_https.bat` que automatiza la descarga de `mkcert.exe` desde
  GitHub, instala la CA local en el almacen de confianza de Windows
  (`mkcert -install`) y genera el certificado para `localhost` y `127.0.0.1`
- `main.py` detecta `localhost.pem` y `localhost-key.pem` automaticamente y
  arranca en HTTPS si existen, sino fallback a HTTP con warning explicito
- `start_proxy.bat` advierte si faltan los certs y sugiere correr el setup
- Documentacion del Paso 4 (Activar HTTPS local) en INSTALL_WINDOWS.md

### v1.1 — Middleware Private Network Access (PNA)

- Reemplazo del `CORSMiddleware` estandar de FastAPI por un middleware
  custom que ademas del CORS clasico devuelve
  `Access-Control-Allow-Private-Network: true` en preflight OPTIONS
- Manejo explicito de preflight OPTIONS para responder 204 con todos los
  headers necesarios (Origin, Methods, Headers, PNA, Max-Age, Vary)
- Echo del origen recibido (validado contra `odoo_domain` configurado)
- Normalizacion automatica de `odoo_domain` quitando barra final

### v1.0 — Proxy basico funcional

- Servidor FastAPI con los 4 endpoints del protocolo IoT Box:
  `/hw_proxy/hello`, `/hw_proxy/handshake`, `/hw_proxy/status_json`,
  `/hw_proxy/default_printer_action`
- Endpoint utilitario `/printers` para listar impresoras detectadas (debug)
- `printer_backend.py` con conversion JPEG/PNG -> ESC/POS raster usando
  Pillow + comandos GS v 0
- Envio RAW al spooler de Windows con `win32print`
- Soporte de apertura de cajon de dinero (`ESC p 0 25 250`)
- `config.yaml` con dominio Odoo, puerto, nombre de impresora, ancho papel
- `start_proxy.bat` que verifica Python instalado, instala deps si falta,
  y arranca el proxy
- Documentacion completa: README.md, INSTALL_WINDOWS.md

---

## Bugs resueltos (con causa raiz)

### Recibos no imprimian aunque la cocina si funcionaba

- **Causa raiz**: Odoo 19 tiene DOS rutas de impresion completamente
  separadas. La cocina usa `pos.printer` records individuales que se crean
  en `pos_store.js:438-446` independientemente de cualquier flag global.
  El recibo en cambio usa `hardware_proxy.printer` que solo se inicializa
  si `useProxy` retorna true (`pos_config.js:76-84`), lo cual requiere
  `is_posbox=True` AND alguna flag de hardware (incluido
  `iface_print_via_proxy`)
- **Solucion**: documentar como configuracion obligatoria en
  INSTALL_WINDOWS.md activar TANTO la seccion "IoT Box" como
  "Receipt Printer" en Ajustes POS > Connected Devices. La casilla de
  "tickets" dentro de "Impresoras de preparacion" NO sirve para recibos

### "CORS error" / "provisional request headers" en DevTools

- **Causa raiz**: el navegador hacia preflight OPTIONS con
  `Access-Control-Request-Private-Network: true` y el `CORSMiddleware`
  estandar de FastAPI no incluye el header de respuesta correspondiente.
  Chrome bloqueaba antes de enviar la peticion real, por eso aparecian
  "provisional headers" sin "response headers"
- **Solucion**: middleware custom que maneja explicitamente el preflight
  PNA con `Access-Control-Allow-Private-Network: true`

### Ruido constante de `ConnectionResetError [WinError 10054]`

- **Causa raiz**: el `ProactorEventLoop` (default en Python Windows 3.8+)
  intenta `socket.shutdown(SHUT_RDWR)` despues de que el cliente cierra
  una conexion HTTPS keep-alive de forma abrupta (RST en vez de FIN). La
  respuesta HTTP ya fue entregada correctamente, pero el cleanup falla
- **Solucion fragil intentada primero**: filtro de logging por texto del
  mensaje. No funciono porque el error sale del exception handler del
  loop, no del logger normal
- **Solucion definitiva**: cambio a `WindowsSelectorEventLoopPolicy` antes
  de arrancar uvicorn, mas un exception handler custom en el lifespan de
  FastAPI que ignora `ConnectionResetError`, `ConnectionAbortedError` y
  `BrokenPipeError`

### "Mixed Content" blocking del navegador

- **Causa raiz**: Odoo se servia por HTTPS, el proxy local en HTTP. Chrome
  bloquea cualquier peticion HTTP desde una pagina HTTPS sin excepcion
- **Solucion**: el proxy ahora corre en HTTPS local con cert mkcert
  firmado por una CA en el almacen de confianza de Windows. Ambos lados
  HTTPS = sin mixed content

### Conflicto entre `point_of_sale.use_lna=1` y HTTPS local

- **Causa raiz**: cuando se activaba el parametro del sistema
  `point_of_sale.use_lna` para hacer funcionar PNA (antes de tener HTTPS
  local), Odoo forzaba el protocolo a HTTP en `deduceUrl()` de
  `utils.js:25-26`. Al pasar el proxy a HTTPS, ese forzado a HTTP rompia
  el setup
- **Solucion**: documentar que con el proxy en HTTPS NO se debe activar
  `use_lna`. Si esta activado de antes, hay que borrar el parametro del
  sistema o ponerlo en `0`. Cerrar y reabrir la sesion POS

### El proxy "dejo de funcionar solo" despues de semanas de no usarlo

- **Sintoma**: en el equipo de desarrollo (Win 11 25H2) el proxy arrancaba
  correctamente (log v1.3 sin errores, cert valido, self-test OK) pero al
  abrir `https://localhost:8072/hw_proxy/hello` en el navegador no cargaba
  nada. Ni ping, ni JSON. Sin cambios previos al codigo ni a la config
- **Causa raiz**: dos problemas superpuestos:
  1. **Bind exclusivo a IPv4**: en v1.3 se cambio el host de `0.0.0.0` a
     `127.0.0.1` por seguridad (evitar exponer LAN). Pero en Windows 11
     25H2 el navegador resuelve `localhost` a `::1` (IPv6). Ninguna
     conexion llegaba al proceso porque escuchaba solo en IPv4
  2. **Procesos zombie acumulados**: sesiones previas de proxy cerradas
     con la X (sin Ctrl+C) dejaron 3 procesos zombie escuchando en
     distintos bindings (uno en `0.0.0.0`, otro en `[::1]`, otro en
     `127.0.0.1`). El sistema enrutaba las conexiones IPv6 al zombie con
     bind `[::1]` que no respondia correctamente (30 conexiones en
     `TIME_WAIT` visibles en netstat)
- **Como se diagnostico**: `netstat -ano | findstr :8072` mostro tres PIDs
  distintos LISTENING en el mismo puerto con diferentes bindings, y una
  larga lista de conexiones fallidas en `TIME_WAIT` desde `[::1]` — prueba
  concluyente de que el navegador conectaba por IPv6 y el proxy activo
  (nuestro v1.3) no lo veia
- **Solucion**:
  - Cambio a `host="::"` en uvicorn (dual-stack: escucha IPv6 e IPv4
    simultaneamente)
  - `start_proxy.bat` mata cualquier proceso zombie en el puerto antes
    de arrancar
- **Documentado en**: v1.3.1

### Certificados copiados entre PCs no funcionaban

- **Causa raiz**: cada PC tiene su propia CA mkcert privada. Si se copian
  los `.pem` de una PC a otra, el cert esta firmado por una CA que la PC
  destino no tiene en su almacen de confianza, asi que el navegador
  rechaza el TLS
- **Solucion**: documentar que el cert es por maquina. Ejecutar
  `setup_https.bat` en cada PC nueva, NO copiar los `.pem`

---

## Bugs abiertos

### Windows 10: "status errors" pese a cert valido y `/hello` OK

- **Sintoma**: en una PC con Windows 10, el `setup_https.bat` se ejecuto
  correctamente, `https://localhost:8072/hw_proxy/hello` muestra "ping"
  sin warning de seguridad. Aun asi, al abrir el POS desde el navegador
  aparecen "errores en el status" y la impresion no funciona
- **Hipotesis a verificar**:
  1. El `odoo_domain` en `config.yaml` no coincide EXACTAMENTE con el
     origen que envia el navegador (subdominio distinto, puerto explicito,
     barra final)
  2. La sesion POS en esa maquina tiene `iface_print_via_proxy` desactivado
     o `is_posbox=False`
  3. Hay un cache viejo del POS con configuracion previa
  4. El parametro `point_of_sale.use_lna` esta activado y forzando HTTP
  5. Diferencia de version Chrome/Edge entre Win10 y Win11
- **Plan de diagnostico**: pedir al usuario que abra DevTools en esa
  maquina, filtre Network por `hw_proxy`, mande captura de las peticiones
  fallidas con su pestana Headers/Response

### "Impresion sin conexion" no habilitada en todos los dispositivos

- **Sintoma**: el modo offline del POS de Odoo funciona en algunos equipos
  y en otros no. No es del proxy, es del POS
- **Hipotesis**: probablemente depende de si el POS se abre como PWA
  instalada o como pestana normal del navegador. La PWA registra un
  service worker que cachea recursos para offline; la pestana normal puede
  no hacerlo del todo
- **Plan**: investigar como se habilita la PWA del POS de Odoo 19 y
  documentar el paso en INSTALL_WINDOWS.md como recomendacion

---

## Roadmap por fases

### Fase 1 — Estabilizacion + refactor + multi-impresora ✅ COMPLETADA en v1.4.0

**Objetivo**: dejar el codigo modular y soportar N impresoras antes de
empezar la GUI.

- [x] Refactor `main.py` en modulos (`app.py`, `config_manager.py`,
  `logger_setup.py`, `printer_manager.py`, `proxy_server.py`)
- [x] Migrar `config.yaml` al esquema multi-impresora con roles
- [x] Retrocompat automatica del formato legacy (sin migracion forzada)
- [x] Logs a archivo con rotacion diaria
- [x] Tests end-to-end documentados (TESTS.md, 11 tests A-K)
- [ ] Ejecutar la suite TESTS.md en equipo de desarrollo con v1.4.0
- [ ] **Pausado por decision del usuario**: diagnosticar bug de Windows 10
  (se retomara con menor riesgo, probablemente en Fase 2 con la GUI que
  facilita capturar estado sin depender de DevTools)
- [ ] **Pausado por decision del usuario**: validacion en Win10 con cert
  recien generado

### Fase 2 — App nativa Windows (tray + dashboard + auto-start) ✅ COMPLETADA en v2.0.0

**Objetivo**: dejar de ser un script CMD y convertirse en una app con UX
para perfil no tecnico. Se hizo con **PySide6/Qt** (no CustomTkinter como
se contemplaba antes) para tener un look profesional lejos del "template AI".

- [x] System tray icon con icono dinamico verde/gris/rojo segun estado
- [x] Menu contextual del tray completo (estado, dashboard, iniciar/detener/
  reiniciar, ver logs, cert, salir)
- [x] Dashboard PySide6 con sidebar en vez de tabs (mas moderno):
  - **Dashboard**: estado del daemon con boton grande de arranque + resumen
  - **Impresoras**: tabla CRUD + dialogo modal con validacion + autodetect
  - **Logs**: stream en vivo con filtro por nivel + auto-scroll + exportar
  - **Certificado**: inspeccion + renovacion en un click (mkcert en QThread)
  - **Sistema**: auto-start toggle + verbose + retencion + updates + abrir carpetas
- [x] Auto-start via HKCU (sin admin), con flag `--minimized`
- [x] Funcionalidades avanzadas de config editables en tiempo real desde GUI
- [x] Renovacion facil de certificado (boton "Renovar ahora" que dispara mkcert)
- [x] Auto-update via GitHub Releases con notificacion en la bandeja
- [x] Cierre a bandeja (X esconde, Salir del tray termina proceso)

### Fase 3 — Empaquetado .exe + installer ✅ COMPLETADA en v2.0.0

Fusionada con Fase 2 dado que el installer era pre-requisito de "instalar
encima de la version anterior".

**Objetivo**: distribucion de un solo `.exe` que cualquier persona instala
con doble click.

- [x] PyInstaller con `--onedir` (rapido al iniciar) + spec dedicado
- [x] Bundle incluye Python embebido + PySide6 + FastAPI + uvicorn +
  cryptography + PyYAML + Pillow + `mkcert.exe`
- [x] Inno Setup 6 con `installer/setup.iss`:
  - Copia archivos a `C:\Program Files\POSPrintProxy\` (o AppData si sin admin)
  - Crea acceso directo en menu inicio + opcional en escritorio
  - Detecta version previa (por AppId) y la desinstala silenciosa antes
  - Preserva `%APPDATA%\POSPrintProxy\` (config + certs + logs) al reinstalar
  - Tasks opcionales: "Iniciar con Windows" y "Iniciar ahora"
- [x] Idiomas espanol + ingles
- [x] `installer/build_local.bat` para build local (Windows + Python + Inno)
- [x] `.github/workflows/release.yml` para build en CI, sube a Releases

**Pendiente (post-release):**
- [ ] Probar el installer en una VM Win10 limpia y una VM Win11 limpia
- [ ] Firma de codigo (opcional, elimina el warning SmartScreen)
- [ ] Distribucion controlada a las 5+ tiendas
- [ ] Iconos `installer/app.ico` y tray SVG (por ahora se generan runtime)

### Fase 4 — macOS

**Objetivo**: replicar la experiencia en Mac para tiendas con iMac/Mac mini.

- [ ] Reemplazar `win32print` por `pycups` (CUPS nativo en macOS)
- [ ] Reemplazar `WindowsSelectorEventLoopPolicy` por loop default (no
  aplica en Mac)
- [ ] Tray con `pystray` (multiplataforma) o `rumps` (mas nativo Mac)
- [ ] Auto-start con LaunchAgent en `~/Library/LaunchAgents/`
- [ ] Empaquetado: `py2app` (mejor para Mac que PyInstaller) -> `.app` bundle
- [ ] DMG installer con drag-to-Applications
- [ ] (Opcional) Firma de codigo + notarizacion Apple ($99/ano dev account)
  para evitar el warning "app de desarrollador no identificado"

---

## Decisiones pendientes

Estas decisiones se deben tomar antes de o durante Fase 2:

- **Auto-start: solo HKCU o tambien opcion de servicio Windows con NSSM?**
  Trade-off: HKCU es suficiente para 99% de los casos; servicio Windows
  da mas robustez pero complica el installer y requiere admin
- **Logs persistentes a archivo?** Con rotacion? Hoy todo va a la ventana
  CMD y se pierde al cerrar. Para soporte multi-tienda conviene tener
  archivo con rotacion automatica
- **Telemetria/diagnostico remoto opt-in?** Util para soporte de 5+ tiendas
  pero requiere consideraciones de privacidad y un endpoint donde recibir
  los logs
- **Auto-actualizacion del proxy?** Endpoint en VPS o GitHub releases que
  la app consulta una vez al dia. Notificacion en tray si hay version nueva
- **Stack GUI confirmado**: CustomTkinter es la recomendacion. Si se
  prefiere look mas profesional (a costa de bundle pesado), considerar
  PySide6 antes de empezar Fase 2
- **Multi-impresora: roles fijos o asignacion libre por categoria?** Los
  roles (`receipt`/`kitchen`/`bar`/`both`) son simples pero ambiguos en
  setups complejos. Asignar impresoras por categoria de producto seria
  mas flexible pero requiere mas configuracion

---

## Notas de sesion (changelog tecnico)

### 2026-07-07 — Sesion v2.0.0 (noche)

- Fase 2 completada en un solo salto grande. Version 2.0 porque cambia el
  contrato (installer, sin YAML manual, tray, GUI). Fase 3 fusionada porque
  el installer era pre-requisito de "instalar encima de la anterior"
- Decisiones del sprint (respondidas por el usuario):
  - GUI: **PySide6/Qt** (no CustomTkinter). Bundle mas pesado pero look
    profesional muy lejos del template AI
  - Installer: **CI + scripts locales** (ambos). GitHub Actions produce
    releases; `build_local.bat` para dev iterativo
  - Auto-update: **si, con aviso en tray** via GitHub Releases API
- Reestructura completa a paquete Python `posprintproxy/` con subpaquetes
  `daemon/`, `gui/`, `util/`. Los archivos flat de v1.4 se movieron. La
  raiz del repo queda casi vacia (solo `main.py` shim + `installer/` + docs)
- Codigo escrito en esta sesion: ~2800 lineas Python en 20 modulos, ~500
  lineas QSS para el tema custom, ~200 lineas de scripts de build/CI
- Validacion offscreen del GUI headless: todos los widgets se instancian sin
  crash, las 5 vistas renderizan y los screenshots muestran el look correcto
- El daemon v1.4 (que ya funcionaba en produccion) queda intacto en
  `posprintproxy/daemon/`. Solo se agrego una clase `ProxyDaemon` que lo
  envuelve para ser controlable desde otro thread
- Retrocompat de config.yaml legacy sigue funcionando: si un usuario de v1.4
  actualiza a v2.0, su config con `printer_name` se carga sin migracion,
  y en la primera edicion desde la GUI se reescribe en formato nuevo
- Los certs mkcert existentes se preservan si el installer detecta el path
  `%APPDATA%\POSPrintProxy\certs\`; no hay que renovar tras el upgrade

### 2026-07-07 — Sesion v1.4.0 (tarde)

- Fase 1 del roadmap completada
- Decisiones tomadas antes del sprint:
  1. Alcance: refactor + multi-impresora en el mismo sprint (opcion
     recomendada)
  2. Logs: consola + archivo rotativo diario, retencion 30 dias
  3. Config legacy: retrocompat automatica (sin migracion forzada)
- Refactor a 5 modulos + shim main.py. Sintaxis validada, imports validados,
  parseo validado con 5 casos (legacy simple, legacy con cocina, formato
  nuevo, puertos duplicados rechazados, config.yaml real)
- Multi-impresora via `asyncio.gather()` de multiples uvicorn.Server, uno
  por impresora. Cada uno con su propio FastAPI, middleware y state
- Suite TESTS.md con 11 tests manuales A-K creada
- Pendiente para la proxima sesion: correr TESTS.md en Windows real con
  v1.4.0 para confirmar que el refactor no introdujo regresiones

### 2026-07-07 — Sesion v1.3.1

- Diagnostico local: el proxy en el equipo de desarrollo dejo de responder
  en `localhost` sin cambios previos
- Con `netstat -ano | findstr :8072` se descubrieron 3 procesos zombie
  escuchando en el mismo puerto con distintos bindings, y decenas de
  conexiones fallidas en `TIME_WAIT` desde `[::1]` — evidencia definitiva
  de que el navegador conecta por IPv6 y el bind exclusivo a IPv4 dejaba
  el proxy silenciosamente inalcanzable
- Fix aplicado: bind dual-stack `"::"` en uvicorn + protector anti-zombies
  en `start_proxy.bat`
- Actualizada plantilla DIAGNOSTICO.md con el nuevo test recomendado
  (`netstat -ano | findstr :8072`) que resulta ser mas util que muchas
  otras validaciones porque expone directo si hay instancias zombie o
  bindings incorrectos

### 2026-06-24

- Creados ESPECIFICACIONES.md y HITOS.md como documentos oficiales del proyecto
- Confirmado que el bug de Win10 NO es por copia de `.pem` (el usuario
  ejecuto `setup_https.bat` en esa maquina y `/hello` muestra ping sin
  warning). Pendiente abrir DevTools en esa maquina para diagnosticar
  origen CORS / config POS

### 2026-05 — Sesion v1.3

- Cambio a `WindowsSelectorEventLoopPolicy` para suprimir
  ConnectionResetError del Proactor
- Exception handler en lifespan FastAPI como respaldo
- Logs limpios con niveles + flag `verbose`
- Self-test de cert al arrancar
- Bind a 127.0.0.1
- Hostname en log de arranque

### 2026-05 — Sesion v1.2

- HTTPS local con mkcert
- Script `setup_https.bat` automatizado (descarga mkcert, instala CA,
  genera certs)
- Documentacion del paso obligatorio HTTPS en INSTALL_WINDOWS.md
- Resuelto el bug de conflicto con `use_lna=1`: con HTTPS local NO se
  activa use_lna

### 2026-05 — Sesion v1.1

- Middleware custom CORS + Private Network Access
- Resuelto el "provisional headers" / CORS error de Chrome al hablar
  HTTPS publica -> HTTP local

### 2026-05 — Sesion v1.0

- Arranque del proyecto. Exploracion del codigo de Odoo POS para
  entender protocolo IoT Box
- Descubrimiento clave: getter `useProxy` en `pos_config.js:76-84` que
  exige `is_posbox` AND alguna flag de hardware. Sin esto,
  `connectToProxy()` nunca se llama y el handshake nunca ocurre
- Las dos rutas de impresion (recibos via `hardware_proxy.printer`,
  cocina via `pos.printer` records) son completamente independientes
- Modulos OCA `report-print-send` descartados por incompatibilidad con
  VPS remoto + impresoras locales
- Arquitectura A (tunel) y B (WebSocket outbound) descartadas por romper
  modo offline del POS. Elegida arquitectura C (HTTPS local)
- Proxy basico v1.0 funcional en Win11

---

## Documentos relacionados

- [ESPECIFICACIONES.md](ESPECIFICACIONES.md) — Definicion estatica de la app
- [README.md](README.md) — Vista general y referencia rapida
- [INSTALL_WINDOWS.md](INSTALL_WINDOWS.md) — Guia operativa paso a paso
