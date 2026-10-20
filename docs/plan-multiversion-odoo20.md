# Plan: POS Print Proxy multi-versión (Odoo 19 + 20) para impresoras genéricas

## Context
- `~/pos_print_proxy` (v2.0.2, rama `odoo_v19`, en producción) es una app Windows (PySide6) que imita la IoT Box (`/hw_proxy/*`) e imprime en térmicas genéricas por USB (spooler) o por red (TCP 9100).
- **Odoo 20 Community ya no tiene cliente IoT Box.** No existe `/hw_proxy` ni `proxy_ip` en `point_of_sale`. Solo imprime por **Epson ePOS**, directo desde el navegador:
  - `POST {http|https}://<printer_ip>/cgi-bin/epos/service.cgi?devid=local_printer&timeout=N` (`addons/point_of_sale/static/src/app/utils/printer/epson_printer.js:131`);
  - `http:` + `targetAddressSpace` si la impresora tiene LNA; `https:` si no.
- Con Odoo 20 la impresora genérica del usuario (192.168.1.100, solo 9100) no funciona. El puente actual tampoco, porque solo habla IoT Box.
- Objetivo: que la misma app sirva para tiendas en 19 y en 20 (conviven a largo plazo); después, app móvil sin PC.

## Decisiones (grilling con grill-me → grilling, 4 rondas)
- **Una sola línea de código y un solo instalador** para 19 y 20. Reemplaza la regla de ramas por versión de `AGENTS.md:287`.
  - Motivo: reutiliza ~85% del código, un canal de auto-update y los fixes se hacen una sola vez.
  - Evita el riesgo de que `update_ctrl.py:24` (`releases/latest`) actualice tiendas de 19 a una versión solo de 20.
- **Ambos protocolos siempre activos** en cada puerto (las rutas no chocan). Condición: consumo en reposo despreciable (se mide).
- **HTTPS + HTTP:** HTTPS en el puerto actual (Odoo local o sin LNA, con el certificado actual) y un **puerto HTTP adicional por impresora** para LNA (Odoo en línea).
- **Zombies:** al arrancar solo se matan procesos propios de POSPrintProxy. Si el puerto lo ocupa otro programa, se avisa con su nombre y no se toca. (Esto tumbó el reenvío de WSL.)
- **Puertos:** las configs existentes no se tocan. Las impresoras nuevas proponen un rango que no choque con Odoo (p. ej. 18072+), y se valida que el puerto esté libre antes de guardar.
- **Pruebas en la GUI:**
  - ping sin imprimir;
  - estado por impresora en el panel principal;
  - autodiagnóstico POS→puente (simula la petición de Odoo 19 y 20 contra el propio puente).
- **Versión v2.1.0.** La rama `odoo_v19` se renombra a `main` (o se crea `main` desde ella). README: "Odoo 19 y 20".
- **Flujo:** con el arnés SDD del repo (`/feature` → spec/plan/tasks, rama `NNN-slug`, merge `--no-ff`). Este plan es el brief de entrada.
- **Fases:**
  - **F1:** este plan.
  - **F2:** rediseño UI/UX (instalar antes la skill ui-ux-pro-max) + addon de cocina offline para Odoo 20. Ese addon vive en el repo de Odoo 20, no aquí. Contexto: `pos_store.js:2069` bloquea el envío a cocina sin conexión.
  - **F3:** análisis a fondo de la app móvil. Flutter o nativo por plataforma; Android primero, iOS después. Objetivo: una app para 19 y 20. Si fuera demasiado complejo, dos apps. Sin decisión técnica todavía.

## F1 — Cambios

### 1. Protocolo ePOS (nuevo, junto al de IoT Box)
- **Nuevo módulo `posprintproxy/daemon/epos.py`, lógica pura sin FastAPI:**
  - Parsear el sobre SOAP (`s:Envelope/s:Body/epos-print`, ns `http://www.epson-pos.com/schemas/2011/03/epos-print`), sin depender de prefijos de namespace.
  - Elementos que hay que soportar:
    - `<image width height>`: base64 de un raster de 1 bit, MSB primero, 1 = negro, **bits contiguos sin relleno por fila** (`canvasToRaster`/`encodeRaster`, `epson_printer.js:21-80`).
    - `<cut type="feed">`.
    - `<pulse>` para el cajón (`openCashbox`, `epson_printer.js:150`).
    - `<text>` y `<feed line>`, que usa el botón "Test" del formulario de impresora en Odoo (`backend/test_epos/test_epos.js:34`).
    - Elementos desconocidos: se ignoran y se registran en el log.
  - Construir la respuesta `<response success="true|false" code="" status="N"/>` dentro de un sobre SOAP. Odoo lee `success`, `code` y `status` (`epson_printer.js:178-187`).
- **Conversión a ESC/POS:**
  - Raster ePOS → filas con relleno a byte → `GS v 0`.
  - Reutilizar la lógica de `image_to_escpos_raster` (`printer_backend.py:26`) extrayendo un helper común "bits → ESC/POS". No se duplica.
  - Texto → ESC/POS de texto (alineación, saltos) + corte.
- **`printer_manager.Printer`** (`:27`): añadir `print_escpos(bytes)`, que despacha a USB o red con el mismo `_lock`. Reutiliza `_send_raw` (`printer_backend.py:151`) y el envío win32.

### 2. Servidor
- **`proxy_server.create_app`** (`:110`): registrar además `POST` y `OPTIONS` en `/cgi-bin/epos/service.cgi`.
  - Mismo middleware CORS/PNA (`:139`), ampliado a lo que exige LNA.
  - Content-Type `text/xml`.
  - Respetar `timeout` de la query.
- **`daemon._serve_all`** (`daemon.py:252`): por impresora, un servidor HTTPS (actual) + uno HTTP en `http_port`, ambos en el mismo event loop y con la misma app.
- **`kill_zombies_on_port`** (`daemon.py:64`): filtrar por nombre o ruta del proceso (POSPrintProxy / python del propio bundle). Si es ajeno: warning + estado "puerto ocupado por X".

### 3. Configuración
- **`config_manager.py`:** campo opcional `http_port` por impresora.
  - Si falta, se propone y valida uno libre.
  - Configs existentes: 100% compatibles, sin migración obligatoria.
  - Nuevo rango por defecto para impresoras nuevas.

### 4. GUI mínima (sin rediseño)
- **Diálogo de impresora:** mostrar "Configurar en Odoo 19" (proxy_ip/puerto) y "Configurar en Odoo 20":
  - `127.0.0.1:<http_port>` **con** LNA marcado, o `127.0.0.1:<port>` **sin** LNA;
  - aviso: escribir IP con puntos, nunca `localhost` (Odoo lo convierte en dominio Epson, `pos_printer.py:10`).
  - Botón copiar.
- **Panel principal:** indicador por impresora (verde/rojo/gris) con "Ping" sin imprimir. Reutiliza `probe_network_printer` (`printer_backend.py:202`) y, para USB, la detección del spooler (`list_printers:134`).
- **Autodiagnóstico:** petición local a `/hw_proxy/hello` y a `/cgi-bin/epos/service.cgi`. En ePOS se usa un modo sin impresión (`<epos-print/>` vacío) para validar puerto, certificado, CORS y parser sin gastar papel.

### 5. Documentación y repo
- README ("Odoo 19 y 20", tabla de configuración por versión).
- `AGENTS.md:287` (nueva regla de línea única).
- `harness/scripts/lint.sh`: `PPP_BASE_BRANCH` pasa a `main`.
- `HITOS.md`.
- `version.py` → 2.1.0.
- El renombrado de rama en GitHub (rama por defecto) se hace con confirmación explícita del usuario.

## Verificación
- **Unit (pytest, `tests/`):**
  - parser ePOS con fixtures reales capturados de Odoo 20 (recibo, comanda, test de texto, pulse);
  - raster con ancho no múltiplo de 8;
  - bytes ESC/POS esperados;
  - respuesta XML;
  - filtro de zombies;
  - config con y sin `http_port`.
- **Integración:** sandbox del arnés (`harness/scripts/test-env.sh levantar`, impresora 9100 simulada en `:8172`).
  - POST ePOS por HTTP y HTTPS;
  - `/hw_proxy` sigue pasando los tests existentes (`tests/test_proxy_integration.py`).
- **E2E Odoo 20** (`~/odoo20`, `docker compose up -d`, sin publicar 8072):
  - impresora `127.0.0.1:<http_port>` con LNA → recibo y comanda salen en la real 192.168.1.100:9100 y por USB;
  - botón "Test" del formulario de Odoo;
  - cajón.
- **E2E Odoo 19:** una tienda o entorno 19 imprime igual que con v2.0.2 (regresión).
- **Recursos:** CPU y RAM en reposo de v2.0.2 vs v2.1.0 con 3 impresoras. Criterio: CPU ≈ 0% en reposo y +RAM < 10 MB.
- **Actualización automática:** una instalación v2.0.2 detecta v2.1.0 y conserva su config y sus certificados.
