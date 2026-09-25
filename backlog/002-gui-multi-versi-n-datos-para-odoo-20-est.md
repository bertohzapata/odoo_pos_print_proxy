# GUI multi-versión: datos para Odoo 20, estado y autodiagnóstico

> Brief en prosa. Describe el QUE y el PARA QUIEN; la solución técnica la decide el ciclo.

## Línea de versión

Rama `main`. Versiones de Odoo: 19 y 20. **Depende de 001** (protocolo ePOS en el daemon).
Sin addon Odoo.

## Qué hace falta

Que quien instala el proxy en una tienda sepa, sin abrir el navegador ni leer documentación:
- qué escribir en Odoo 19 y qué en Odoo 20 para cada impresora;
- si cada impresora está viva;
- si el proxy responde como lo espera Odoo.

## Por qué

Hoy la GUI solo habla de Odoo 19. Con Odoo 20 hay dos formas de configurar (con o sin LNA),
un campo que se reescribe solo si no lleva puntos, y ningún modo de probar el puente sin abrir
el POS. Los errores de configuración se descubren en la tienda, con clientes esperando.

## Alcance

- Incluye:
  - **Diálogo de impresora:** sección "Configurar en Odoo 19" y "Configurar en Odoo 20", con
    botón copiar.
    - Para 20: `127.0.0.1:<puerto HTTP>` con "Use Local Network Access" marcado, o
      `127.0.0.1:<puerto HTTPS>` sin LNA.
    - Aviso: nunca `localhost`, porque Odoo lo convierte en dominio Epson.
    - Campo del puerto HTTP, con el nuevo rango por defecto y validación de puerto libre.
  - **Panel principal:** estado por impresora (verde, rojo o gris) y botón **Ping** que no
    imprime. Red: conexión al 9100. USB: la impresora existe en el spooler.
  - **Autodiagnóstico POS→puente:** con un clic, simula lo que hace Odoo 19 y Odoo 20 contra el
    propio proxy, sin imprimir. Informa por separado:
    - puerto;
    - certificado;
    - CORS/LNA;
    - respuesta ePOS;
    - respuesta IoT Box.
  - Textos de la GUI: "Odoo 19 y 20" donde hoy dice solo 19.
- No incluye:
  - Rediseño visual (fase posterior con la skill UI/UX Pro Max).
  - Cambios al protocolo (feature 001).
  - App móvil.

## Casos y detalles

- Ping y autodiagnóstico no deben congelar la GUI: se ejecutan fuera del hilo de Qt, como ya se
  hace con `kill_zombies`.
- El estado del panel se refresca al pulsar Ping y al arrancar o detener el proxy. Un sondeo
  periódico solo si es barato (Principio de consumo mínimo de 001).
- El botón "Imprimir prueba" actual se conserva (`gui/dialogs/printer_dialog.py:250`).

## Cómo se ve que funciona

1. En el diálogo de una impresora se copian los datos de Odoo 20 y, pegados en Odoo, la
   impresora imprime al primer intento.
2. Con la impresora de red apagada, el panel la muestra en rojo al pulsar Ping, sin imprimir
   nada. Encendida, en verde.
3. El autodiagnóstico pasa en verde con el proxy arriba. Al detener el proxy, falla indicando la
   causa.
4. La GUI no se congela durante Ping ni durante el autodiagnóstico.

## Referencias

- Plan aprobado: `~/.claude/plans/continuando-con-lo-que-goofy-cat.md`.
- Reutilizar:
  - `probe_network_printer` (`printer_backend.py:202`);
  - `list_printers` (`:134`);
  - `print_test_*` (`:246,253`).
