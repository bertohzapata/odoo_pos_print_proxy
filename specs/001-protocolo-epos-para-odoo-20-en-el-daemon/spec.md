# Feature Specification: Protocolo ePOS para Odoo 20 en el daemon

**Feature**: `001-protocolo-epos-para-odoo-20-en-el-daemon` | **Creada**: 2026-09-25 |
**Brief**: `backlog/001-protocolo-epos-para-odoo-20-en-el-daemon.md` | **Flujo**: estándar |
**Módulo**: `daemon` (+ GUI mínima declarada en FR-016)

## Qué se construye

Las tiendas con **Odoo 20 Community** no pueden imprimir con el proxy: Odoo 20 ya no tiene
cliente IoT Box y solo imprime hablando **Epson ePOS** directo desde el navegador. Esta feature
hace que cada puerto de impresora del proxy responda **también** como una impresora Epson ePOS,
sin dejar de responder como IoT Box, para que el mismo proxy instalado sirva a la vez a tiendas
en Odoo 19 y en Odoo 20 con impresoras térmicas genéricas (USB por spooler de Windows o red TCP
9100), sin que el usuario elija versión. Incluye el arranque seguro (no matar procesos ajenos
que ocupen un puerto) y la versión 2.1.0. Vive en `posprintproxy/daemon/`.

## Clarifications

### Session 2026-09-25

- Q: ¿La imagen ePOS se imprime a su ancho nativo centrada o se reescala a `paper_width`? → A: Ancho nativo, centrada; solo se reduce si excede `paper_width`.
- Q: ¿Una impresora sin `http_port` escucha por HTTP automáticamente? → A: No; solo si está configurado. El daemon no escribe la config del usuario.
- Q: Si otro programa ocupa el puerto de una impresora, ¿qué arranca y dónde se avisa? → A: Solo ese puerto queda fuera; el resto arranca; aviso en el estado del daemon y en el log.
- Q: ¿Se aceptan los supuestos S1–S6? → A: S1, S2, S5 y S6 sí. S3 no: `odoo_domain` pasa a lista de dominios (FR-020). S4 no: el texto respeta estilos básicos (negrita, subrayado, doble ancho/alto, alineación).

## Historias de usuario

### H1 — Odoo 20 imprime recibos y comandas (P1) 🎯 MVP

**Como** cajero de una tienda en Odoo 20, **quiero** que mis recibos y comandas salgan completos
en mi impresora genérica (red 9100 o USB), **para** operar igual que las tiendas en Odoo 19.
**Se valida así**: con la impresora de Odoo 20 apuntando a `127.0.0.1:<puerto>`, se cobra una
orden y se envía una comanda; ambos tickets salen completos y cortados, en red y en USB.

### H2 — Cajón y botón "Test" desde Odoo 20 (P1)

**Como** encargado de tienda, **quiero** que el cajón abra al cobrar y que el botón "Test" del
formulario de impresora de Odoo 20 imprima, **para** comprobar la instalación sin vender.
**Se valida así**: el botón "Test" imprime su ticket de texto sin mostrar aviso de error; al
cobrar en efectivo con cajón vinculado, el cajón abre.

### H3 — Odoo 20 en línea con "Use Local Network Access" (P2)

**Como** tienda con Odoo 20 en línea (dominio público HTTPS), **quiero** marcar "Use Local
Network Access" y apuntar a un puerto HTTP del proxy, **para** imprimir sin instalar
certificados en cada navegador.
**Se valida así**: con LNA marcado e IP `127.0.0.1:<puerto HTTP>`, un recibo y una comanda salen.

### H4 — Los fallos se ven en Odoo 20 y Odoo 19 no cambia (P1)

**Como** cajero, **quiero** que Odoo me avise cuando la impresora falla, **y** las tiendas en
Odoo 19 no notan ningún cambio, **para** no perder tickets en silencio ni romper lo que ya anda.
**Se valida así**: con la impresora apagada, Odoo 20 muestra el diálogo de error de impresión;
una tienda o entorno en Odoo 19 imprime recibo, comanda y cajón igual que con v2.0.2.

### H5 — Arranque seguro con puertos ocupados (P2)

**Como** usuario con Docker/WSL u otro programa en la máquina, **quiero** que el proxy no mate
procesos ajenos al arrancar, **para** no tumbar servicios que no son suyos.
**Se valida así**: con un programa ajeno escuchando en el puerto de una impresora, al iniciar
el proxy ese programa sigue vivo y el proxy informa qué programa ocupa el puerto.

## Requisitos

**Protocolo ePOS**

- **FR-001**: Cada puerto de impresora MUST aceptar peticiones de impresión Epson ePOS en la ruta
  `/cgi-bin/epos/service.cgi` (con los parámetros de query `devid` y `timeout` que envía Odoo 20),
  **además** de todas las rutas IoT Box actuales, siempre ambas activas y sin configuración. Cada
  puerto MUST aceptar conexiones por `127.0.0.1` (IPv4, la que exige Odoo 20) y por `::1`/`localhost`.
- **FR-002**: El sistema MUST interpretar el documento ePOS dentro del sobre SOAP identificando los
  elementos por su namespace (`http://www.epson-pos.com/schemas/2011/03/epos-print`), sin depender
  del prefijo que traiga, y aceptar el cuerpo sin importar el `Content-Type` de la petición
  (Odoo envía texto plano).
- **FR-003**: El sistema MUST imprimir el elemento imagen: raster de 1 bit, MSB primero, 1 = negro,
  bits **contiguos sin relleno por fila**, con `width` y `height` del elemento, incluidos anchos
  que no son múltiplo de 8 (Odoo 20 usa, entre otros, 375 px). La imagen MUST imprimirse a su
  ancho nativo, centrada en el ancho de papel (`paper_width`), sin reescalar; solo si su ancho
  supera `paper_width` MUST reducirse para caber.
- **FR-004**: El sistema MUST ejecutar el corte (`cut`), la apertura de cajón (`pulse`), el texto
  (`text`, con alineación, saltos de línea, negrita, subrayado y doble ancho/alto; el resto de
  atributos de estilo se ignora con log según FR-005) y el avance de líneas (`feed`), cubriendo todo lo
  que envía el botón "Test" de Odoo 20.
- **FR-005**: Un elemento ePOS no reconocido MUST ignorarse y registrarse en el log (con su nombre)
  sin hacer fallar la impresión del resto del documento.
- **FR-006**: Un documento ePOS mal formado (XML inválido, sin elemento `epos-print`, imagen con
  datos inconsistentes con `width`×`height`) MUST responderse como error, con causa en el log.
  Un cuerpo de más de 8 MiB o con DTD/declaración de entidades MUST rechazarse igual, sin parsearlo.
- **FR-007**: El sistema MUST responder con un sobre SOAP que contenga un elemento `response` con
  los atributos `success`, `code` y `status`. En éxito: `success="true"` y `code=""` (**vacío,
  no ausente**: el botón "Test" trata un `code` ausente como fallo).
- **FR-008**: Un fallo al entregar a la impresora (red caída, USB ausente, spooler) MUST responderse
  `success="false"` con un código de error Epson no vacío, y quedar en el log con causa. Nunca un
  éxito sin haber entregado el trabajo (Principio IV).
- **FR-009**: El sistema MUST responder antes de que venza el `timeout` (ms) pedido por Odoo; si la
  entrega a la impresora no termina a tiempo, MUST responder error de tiempo agotado en vez de
  dejar que el navegador aborte sin respuesta.
  Sin `timeout` en la petición (botón "Test") se asume 15 000 ms, el abort de Odoo. Si el plazo
  vence con el trabajo ya en curso, se responde el error igualmente: un posible ticket duplicado
  al reintentar es preferible a un éxito no comprobado (Principio IV).
- **FR-010**: Los trabajos ePOS e IoT Box hacia una misma impresora MUST serializarse entre sí
  (varias cajas, una impresora), igual que hoy.

**Conexión y navegador**

- **FR-011**: El puerto actual de cada impresora MUST atender ePOS por HTTPS con el certificado que
  ya gestiona el proxy (Odoo local, o impresora sin LNA).
- **FR-012**: Cada impresora MUST poder tener un **puerto HTTP adicional** opcional que atiende los
  mismos protocolos sin TLS, para Odoo en línea con LNA. Sin `http_port` en la config
  MUST NOT abrirse ningún puerto HTTP adicional; el daemon MUST NOT escribir `http_port` en la
  config del usuario (se configura a mano en el YAML hasta que la feature 002 lo lleve a la GUI).
- **FR-013**: Las respuestas ePOS MUST ser legibles por el POS desde el origen Odoo configurado:
  cabeceras CORS para los orígenes configurados (FR-020) en la respuesta y en el preflight, incluidas las que exija el
  acceso a red local/loopback del navegador, sin abrir el acceso a otros orígenes.

- **FR-020**: `odoo_domain` MUST aceptar uno o varios dominios (lista); un valor único de configs
  existentes MUST seguir siendo válido. CORS MUST permitir exactamente esos orígenes y ningún otro.
  La GUI mínima (FR-016) MUST conservar la lista al guardar.

**Arranque y configuración**

- **FR-014**: Al arrancar, el sistema MUST cerrar solo procesos anteriores del propio POS Print
  Proxy que ocupen sus puertos. Si un puerto lo ocupa otro programa, MUST NOT tocarlo y MUST
  registrar en el log el nombre del programa y su PID. Solo ese puerto queda fuera: las
  demás impresoras y puertos MUST arrancar, y el estado del daemon (el que ya muestran panel y
  bandeja, sin GUI nueva) MUST reportar "puerto N ocupado por X" además del log. Un programa que
  escuche en ese puerto en cualquier dirección (p. ej. solo `127.0.0.1`) cuenta como ocupante. Si el
  dueño no puede identificarse, se reporta "programa desconocido" y no se toca. Si no arranca
  ningún puerto, el daemon MUST quedar en estado de error con la causa.
- **FR-015**: La config MUST aceptar un campo opcional de puerto HTTP por impresora. Las configs
  existentes (formato nuevo y legacy) MUST cargar y funcionar sin cambios ni migración. Los puertos
  (HTTPS y HTTP de todas las impresoras) MUST ser únicos; un conflicto MUST rechazarse con un
  mensaje que diga qué puertos chocan. Antes de escuchar, el sistema MUST verificar que el puerto
  está libre y, si no, aplicar FR-014.
- **FR-016**: **GUI mínima** (única excepción al alcance del daemon): guardar la config desde la GUI
  y editar una impresora MUST conservar el puerto HTTP y la lista de `odoo_domain` (FR-020) (hoy la GUI reescribe el YAML y descartaría
  el campo nuevo). Una impresora **nueva** MUST proponer puertos en un rango que no choque con Odoo
  (p. ej. 18072 en adelante) en lugar de 8072. Ningún otro cambio de GUI entra aquí (feature 002),
  salvo el texto de aviso de FR-014 en las etiquetas existentes de panel y bandeja, y la edición de
  varios dominios en el campo de dominio existente (FR-020).
- **FR-017**: El reposo MUST seguir siendo despreciable con ambos protocolos y el puerto HTTP activos:
  sin sondeos periódicos ni hilos por petición nuevos.

**Versión y documentación**

- **FR-018**: La versión MUST ser 2.1.0 en todos los lugares donde el proxy la muestra o la reporta
  (app, daemon CLI, servidor, installer). README y HITOS MUST decir "Odoo 19 y 20" e incluir cómo
  configurar la impresora en cada versión, con el aviso de que en Odoo 20 la IP lleva puntos
  (`127.0.0.1:PUERTO`, nunca `localhost`).
- **FR-019**: El protocolo ePOS MUST vivir en su propio módulo dentro de `posprintproxy/daemon/`,
  aislado del protocolo IoT Box; la lógica compartida (raster ESC/POS, transporte USB/red) MUST NOT
  depender de ningún protocolo concreto ni duplicarse (Principio III).

## Datos y configuración

| Campo | Modelo | Tipo | Default | Para qué |
|---|---|---|---|---|
| `http_port` | impresora en `config.yaml` (`PrinterConfig`) | entero 1–65535, opcional | ausente = sin puerto HTTP (FR-012) | puerto HTTP sin TLS para Odoo 20 con LNA |
| `odoo_domain` | config global (existente) | texto o lista de textos | valor actual | orígenes permitidos por CORS (FR-020) |
| `port` | ídem (existente) | entero | 8072 hoy; nuevas: rango 18072+ (FR-016) | HTTPS: IoT Box (Odoo 19) y ePOS (Odoo 20 sin LNA) |

Respuesta ePOS (contrato con Odoo 20, `epson_printer.js:178-187`, `test_epos.js:116-121`):

| Atributo | Éxito | Fallo |
|---|---|---|
| `success` | `"true"` | `"false"` |
| `code` | `""` | código Epson no vacío (S1) |
| `status` | entero; `0` aceptable | entero; bits de papel opcionales |

## Criterios de éxito

- **CE-001**: En Odoo 20 local, recibo y comanda salen completos y legibles en la impresora de red
  real (192.168.1.100) y en una USB, por HTTPS y por el puerto HTTP con LNA.
- **CE-002**: El botón "Test" de Odoo 20 imprime sin aviso de error y el cajón abre.
- **CE-003**: Con la impresora apagada, Odoo 20 muestra error de impresión en el 100 % de los
  intentos; nunca informa éxito.
- **CE-004**: Odoo 19 imprime recibo, comanda y cajón igual que con v2.0.2, y las pruebas
  automáticas existentes del protocolo IoT Box siguen pasando sin modificarlas.
- **CE-005**: Con un programa ajeno (p. ej. reenvío de WSL/Docker) en un puerto configurado, ese
  programa sigue vivo tras arrancar el proxy, las demás impresoras imprimen y el log y el
  estado del daemon nombran puerto y programa.
- **CE-006**: En reposo con 3 impresoras, CPU ≈ 0 % y menos de 10 MB de RAM extra frente a v2.0.2.
- **CE-007**: Un `config.yaml` de v2.0.2 (formato nuevo y legacy) arranca sin editarlo y la
  actualización automática desde v2.0.2 conserva config y certificados.

## Fuera de alcance

- Cambios de GUI más allá de FR-016 (indicadores, "Configurar en Odoo 20", ping, autodiagnóstico):
  feature 002. Rediseño UI/UX.
- Addon Odoo de comandas offline para Odoo 20 (repo de Odoo 20). App móvil.
- Renombrar la rama por defecto en GitHub.
- Impresoras Zebra/etiquetas (`paper_size = label`, ruta `/pstprnt`): Odoo 20 no usa ePOS para ellas.
- Estados reales de papel/tapa de la impresora (el transporte 9100/spooler no los lee hoy).

## Supuestos

- **S1** (confirmado): Código de error ante fallo de entrega: `EX_BADPORT` (Odoo lo traduce a "dispositivo no
  conectado"); tiempo agotado: `EX_TIMEOUT`; documento inválido: código genérico de error de
  impresión. `status="0"` siempre.
- **S2** (confirmado): Sin certificado disponible, el puerto principal sirve HTTP como hoy (`has_ssl`); el
  puerto HTTP adicional funciona igual con o sin certificado.
- **S3** (confirmado con cambio): ver FR-020; `odoo_domain` admite varios dominios.
- **S4** (confirmado con cambio): ver FR-004; el resto de atributos de texto se ignora con log (FR-005).
- **S5** (confirmado): El consumo en reposo (CE-006) lo mide el propietario en Windows (Administrador de
  tareas) con v2.0.2 y v2.1.0 en la misma máquina; no se automatiza.
- **S6** (confirmado): Un proceso "propio" (FR-014) se reconoce por el ejecutable `POSPrintProxy.exe` o por el
  intérprete de Python ejecutando el paquete `posprintproxy`; el daemon no puede matarse a sí mismo.
- **S7 (spike)**: Que Chrome con LNA acepte la respuesta de `http://127.0.0.1` sin preflight CORS
  (el POST va como `text/plain`, petición simple) no está comprobado: se verifica en el E2E de H3.
- **S8**: El puerto HTTP adicional escucha en todas las interfaces, igual que el HTTPS de hoy, así que
  queda visible en la LAN sin TLS. Riesgo aceptado a validar en el Gate 1: solo expone impresión y CORS.

## Referencias externas verificadas

Odoo 20 (`~/odoo20/src/addons/point_of_sale/`):
- `static/src/app/utils/printer/epson_printer.js:27-96` — `canvasToRaster`/`encodeRaster` (raster
  contiguo; el último byte parcial queda alineado a la derecha, ver research.md).
- `.../epson_printer.js:101-116` — `processCanvas`: `<image width height align="center">` + `<cut type="feed"/>`.
- `.../epson_printer.js:131-134` — URL `http:`(LNA)/`https:` + `?devid=local_printer&timeout=N`.
- `.../epson_printer.js:150-153` — `openCashbox`: `<pulse/>`.
- `.../epson_printer.js:158-196` — POST sin `Content-Type`; lee `success`/`code`/`status`; cualquier
  excepción → `PRINTER_NOT_REACHABLE`.
- `static/src/backend/test_epos/test_epos.js:34-46,97-121` — ticket de texto; éxito exige `code === ""`.
- `static/src/app/components/epos_templates.xml:3-9` — sobre SOAP y namespace.
- `static/src/app/utils/init_lna.js:57-68` — `127.0.0.1`/`localhost` → `loopback`.
- `static/src/app/utils/printer/base_printer.js:21-26` — ancho de canvas: 512 (80 mm), 360 (58 mm).
- `models/pos_printer.py:10-26` — IP sin puntos → dominio `*.omnilinkcert.epson.biz`.

Este repo (`posprintproxy/`):
- `daemon/printer_backend.py:26` `image_to_escpos_raster`; `:151` `_send_raw`; `:202`
  `probe_network_printer`; `:222` `_build_test_ticket`.
- `daemon/printer_manager.py:27` `Printer` (con `_lock` por impresora).
- `daemon/proxy_server.py:110` `create_app`; `:139` middleware CORS/PNA.
- `daemon/daemon.py:64` `kill_zombies_on_port`; `:219` `_run_thread`; `:252` `_serve_all`.
- `daemon/config_manager.py:44` `PrinterConfig`; `:132` `_parse` (unicidad de puertos).
- `gui/controllers/config_ctrl.py:95` `_printer_to_dict`; `gui/dialogs/printer_dialog.py:181`
  `_suggest_defaults`, `:189` `_collect`.
