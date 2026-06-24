# Hitos y Roadmap — POS Print Proxy

> Documento vivo. Se actualiza al final de cada sesion de trabajo agregando:
> hitos completados, bugs descubiertos/resueltos, decisiones tomadas y notas
> de sesion en el changelog. Para definicion estatica de la app, ver
> [ESPECIFICACIONES.md](ESPECIFICACIONES.md).

---

## Estado actual

- **Version**: 1.3.0
- **Ultima actualizacion**: 2026-06-24
- **Resumen**: La app funciona end-to-end en Windows 11 (recibos, cocina y
  cajon de dinero) con HTTPS local. Logs limpios. Existe un bug abierto en
  Windows 10 ("status errors" pese a cert valido y `/hello` OK) que necesita
  diagnostico antes de iniciar Fase 1.

---

## Hitos completados

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

### Fase 1 — Estabilizacion + refactor + multi-impresora

**Objetivo**: dejar el codigo modular y soportar N impresoras antes de
empezar la GUI.

- [ ] Diagnosticar y resolver el bug de Windows 10 (precondicion)
- [ ] Refactor `main.py` en modulos:
  - `proxy_server.py` — solo el servidor FastAPI con sus endpoints
  - `printer_manager.py` — gestion de impresoras multiples
  - `config_manager.py` — lectura/escritura/validacion de `config.yaml`
  - `app.py` — entry point que orquesta todo
- [ ] Migrar `config.yaml` al esquema multi-impresora con roles:
  ```yaml
  printers:
    - name: "Caja"
      port: 8072
      windows_printer: "POS-80"
      paper_width: 576
      role: receipt   # receipt | kitchen | bar | both
  ```
- [ ] Documentar la migracion (config viejo sigue funcionando como fallback)
- [ ] Tests end-to-end documentados (manuales, paso a paso)
- [ ] Validar funcionalidad en Win10 + Win11 con cert recien generado

### Fase 2 — App nativa Windows (tray + dashboard + auto-start)

**Objetivo**: dejar de ser un script CMD y convertirse en una app con UX
para perfil no tecnico.

- [ ] System tray icon (pystray) con icono verde/rojo segun estado
- [ ] Menu contextual del tray:
  - Estado en texto: "Activo en puerto 8072"
  - Abrir Dashboard
  - Reiniciar / Detener / Iniciar daemon
  - Toggle "Iniciar con Windows"
  - Acerca de / Salir
- [ ] Dashboard GUI (CustomTkinter) con tabs:
  - **Impresoras**: tabla con CRUD, modal de edicion con dropdown autodetectado
    de impresoras Windows, boton "Imprimir pagina de prueba"
  - **Conexion Odoo**: campo dominio, boton "Probar conectividad", indicador
    de estado del cert HTTPS, boton "Reinstalar certificado"
  - **Sistema**: toggle auto-start, toggle "iniciar minimizado", abrir
    carpeta de logs, version + buscar actualizaciones
  - **Logs en vivo**: stream de los ultimos N mensajes, boton "Limpiar" y
    "Exportar a archivo"
- [ ] Auto-start con Windows via registro
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` (sin admin)
- [ ] Funciona identico en Win10 y Win11

### Fase 3 — Empaquetado .exe + installer

**Objetivo**: distribucion de un solo `.exe` que cualquier persona instala
con doble click.

- [ ] PyInstaller con `--onedir` (mas rapido al iniciar que `--onefile`)
- [ ] Bundle incluye:
  - Runtime Python embebido
  - Todas las dependencias (FastAPI, uvicorn, customtkinter, pystray, etc.)
  - `mkcert.exe` precargado
  - Iconos del tray
- [ ] Installer con Inno Setup (`POSPrintProxySetup.exe`) que:
  - Copia archivos a `C:\Program Files\POSPrintProxy\`
  - Crea acceso directo en menu inicio + escritorio
  - Pregunta: instalar certificado HTTPS (si por default)
  - Pregunta: iniciar con Windows (si por default)
  - Pregunta: iniciar el servicio ahora (si por default)
- [ ] Probar el installer en una VM Win10 limpia y una VM Win11 limpia
- [ ] Distribucion controlada a las 5+ tiendas

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
