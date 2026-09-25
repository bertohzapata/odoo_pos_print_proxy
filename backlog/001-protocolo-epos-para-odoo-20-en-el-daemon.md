# Protocolo ePOS para Odoo 20 en el daemon

> Brief en prosa. Describe el QUE y el PARA QUIEN; la solución técnica la decide el ciclo.

## Línea de versión

Rama de integración `main` (constitución v2.0.0, Principio III). Versiones de Odoo que toca:
**agrega Odoo 20** y **no debe romper Odoo 19**. Sin addon Odoo en esta feature; el addon de
comandas offline para Odoo 20 es una fase posterior y vivirá en el repo de Odoo 20.

## Qué hace falta

Que una tienda con **Odoo 20 Community** pueda imprimir recibos y comandas en impresoras
térmicas **genéricas** (USB por spooler de Windows o red TCP 9100) a través del proxy, igual
que hoy lo hacen las tiendas con Odoo 19. El mismo proxy instalado debe servir para tiendas en
19 y en 20 al mismo tiempo, sin que el usuario elija versión.

## Por qué

Odoo 20 Community ya no tiene cliente IoT Box: `/hw_proxy` y `proxy_ip` no existen en
`point_of_sale`. Solo imprime por **Epson ePOS**, directo desde el navegador:
`POST {http|https}://<printer_ip>/cgi-bin/epos/service.cgi?devid=local_printer&timeout=N`
(`addons/point_of_sale/static/src/app/utils/printer/epson_printer.js:131`). Con Odoo 20 el proxy
actual no imprime nada. Las impresoras genéricas (p. ej. 192.168.1.100, solo puerto 9100, sin
servicio ePOS) quedan inutilizables.

## Alcance

- Incluye:
  - Responder como una impresora Epson ePOS en cada puerto de impresora, **además** del
    protocolo IoT Box actual. Ambos siempre activos: el consumo en reposo debe seguir siendo
    despreciable (se mide).
  - Soportar lo que Odoo 20 envía:
    - recibo o comanda como imagen raster;
    - corte;
    - apertura de cajón;
    - el ticket de texto del botón "Test" del formulario de impresora de Odoo.
  - Responder a Odoo en el formato que espera (éxito o error con código). Un fallo de impresora
    se reporta como error, nunca como éxito (Principio IV).
  - Dos formas de conexión desde Odoo 20:
    - **HTTPS** en el puerto actual (Odoo local, o impresora sin "Use Local Network Access"),
      con el certificado que ya gestiona el proxy;
    - **HTTP** en un puerto adicional por impresora, para cuando la impresora tiene LNA (Odoo en
      línea con SSL).
  - Arranque seguro: al iniciar solo se cierran procesos viejos del propio POS Print Proxy. Si
    el puerto lo ocupa otro programa, no se toca y se informa cuál es (hoy el `taskkill` tumbó el
    reenvío de puertos de WSL/Docker).
  - Config: el puerto HTTP por impresora es opcional.
    - Las configs existentes siguen funcionando sin cambios.
    - Las impresoras nuevas proponen un rango de puertos que no choque con Odoo (p. ej. 18072+).
    - Se valida que el puerto esté libre antes de usarlo.
  - Versión 2.1.0; README y HITOS con "Odoo 19 y 20".
- No incluye:
  - Cambios de GUI (feature 002), salvo lo mínimo para que el daemon arranque con la config nueva.
  - Rediseño UI/UX.
  - Addon Odoo de comandas offline.
  - App móvil.
  - Renombrar la rama en GitHub (se hace aparte, con confirmación).

## Casos y detalles

- El raster de Odoo 20 es de 1 bit, MSB primero, 1 = negro, con **bits contiguos sin relleno por
  fila** (`canvasToRaster`/`encodeRaster`, `epson_printer.js:21-80`). Hay que manejar anchos que
  no son múltiplo de 8.
- El XML viene en un sobre SOAP con namespace `http://www.epson-pos.com/schemas/2011/03/epos-print`
  (`components/epos_templates.xml`). No depender de prefijos.
- Odoo lee `success`, `code` y `status` de la respuesta (`epson_printer.js:178-187`). Los bits
  de estado de papel (`0x00080000` sin papel, `0x00020000` casi sin papel) se pueden omitir si
  no se conocen.
- Elementos ePOS desconocidos: se ignoran y se registran en el log, sin fallar la impresión.
- En Odoo, el campo "IP" debe llevar puntos (`127.0.0.1:PUERTO`). Si no los lleva, Odoo lo
  convierte en un dominio `*.omnilinkcert.epson.biz` (`pos_printer.py:10`). Es solo
  documentación; la GUI lo mostrará en la feature 002.
- CORS/LNA: el POS en línea (dominio público HTTPS) llama a `http://127.0.0.1:PUERTO` con
  `targetAddressSpace: "loopback"` (`init_lna.js:57`).
- Varias cajas y una misma impresora: se conserva la serialización por impresora que ya existe.

## Cómo se ve que funciona

1. **Odoo 20 local** (`~/odoo20`), impresora con `127.0.0.1:<puerto>`:
   - un recibo y una comanda salen completos en la impresora de red real 192.168.1.100 y en
     una USB;
   - el botón "Test" del formulario de Odoo imprime;
   - el cajón abre.
2. Lo mismo con LNA marcado y el puerto HTTP.
3. **Tienda o entorno Odoo 19:** imprime exactamente igual que con v2.0.2.
4. Con la impresora apagada, Odoo 20 muestra error de impresión, no éxito.
5. Con Docker/WSL ocupando un puerto, el proxy no lo mata y avisa quién lo ocupa.
6. **Consumo en reposo** con 3 impresoras: CPU ≈ 0% y menos de 10 MB de RAM extra frente a
   v2.0.2.

## Referencias

- Plan aprobado: `~/.claude/plans/continuando-con-lo-que-goofy-cat.md`.
- Código de Odoo 20: `~/odoo20/src/addons/point_of_sale/static/src/app/utils/printer/epson_printer.js`,
  `.../app/utils/init_lna.js`, `.../backend/test_epos/test_epos.js`, `.../models/pos_printer.py`.
- Reutilizar:
  - `image_to_escpos_raster` (`printer_backend.py:26`);
  - `_send_raw` (`:151`);
  - `Printer` (`printer_manager.py:27`);
  - middleware CORS/PNA (`proxy_server.py:139`);
  - `kill_zombies_on_port` (`daemon.py:64`).
