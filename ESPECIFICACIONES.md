# Especificaciones — POS Print Proxy

> Documento estatico que define el QUE y el POR QUE de la aplicacion. Se
> actualiza solo cuando hay cambios mayores de arquitectura, requisitos o
> decisiones de diseno. Para tracking de progreso, ver [HITOS.md](HITOS.md).

---

## Tabla de contenidos

1. [Proposito y alcance](#1-proposito-y-alcance)
2. [Glosario](#2-glosario)
3. [Aspectos no tecnicos (requisitos funcionales)](#3-aspectos-no-tecnicos)
4. [Aspectos tecnicos (requisitos no funcionales)](#4-aspectos-tecnicos)
5. [Decisiones de diseno con justificacion](#5-decisiones-de-diseno)
6. [Compatibilidad](#6-compatibilidad)
7. [Restricciones y supuestos](#7-restricciones-y-supuestos)
8. [Las dos rutas de impresion de Odoo POS](#8-las-dos-rutas-de-impresion-de-odoo-pos)

---

## 1. Proposito y alcance

**Que es**: un servicio HTTPS local que corre en la misma PC donde se usa el
POS de Odoo, impersona el protocolo del IoT Box de Odoo, y dirige los
trabajos de impresion a impresoras termicas USB usando el subsistema de
impresion del sistema operativo (Windows hoy, macOS en el roadmap).

**Que NO es**:
- No es un fork ni una modificacion de Odoo. No toca codigo del servidor
- No es un servicio en la nube. Vive en localhost para preservar el modo
  offline del POS
- No es un driver de impresora. Usa los drivers genericos POS de Windows
- No es un IoT Box. Es una emulacion del protocolo HTTP del IoT Box

**Alcance del producto**: la totalidad del recorrido desde que un cajero
cierra una venta hasta que la impresora termica corta el papel. Tambien
cubre comandas de cocina (pedidos enviados a preparacion) y apertura del
cajon de dinero. El renderizado del recibo lo sigue haciendo Odoo; la
impresion fisica la hace este proxy.

---

## 2. Glosario

| Termino | Significado |
|---|---|
| POS | Point of Sale (Punto de Venta) |
| Odoo CE | Odoo Community Edition |
| IoT Box | Dispositivo hardware oficial de Odoo (Raspberry Pi preconfigurada) que actua de puente entre el POS y perifericos. Cuesta $200+ USD |
| ESC/POS | Estandar de comandos creado por Epson, adoptado por casi todas las impresoras termicas POS |
| ePOS | Protocolo XML propietario de Epson sobre HTTP |
| PNA | Private Network Access. Capa de seguridad de Chromium que bloquea peticiones desde origen publico hacia red privada/loopback salvo que el servidor responda headers especiales |
| CORS | Cross-Origin Resource Sharing. Capa de seguridad del navegador |
| mkcert | Herramienta open-source que crea una CA local de confianza y firma certificados HTTPS para desarrollo/uso interno |
| Mixed Content | Bloqueo del navegador cuando una pagina HTTPS intenta cargar recursos HTTP |
| pos.printer | Modelo en Odoo para impresoras de preparacion (cocina, bar) |
| pos.config | Modelo en Odoo para la configuracion del Punto de Venta. Aqui vive la conexion al "IoT Box principal" para recibos |
| hardware_proxy.printer | Servicio frontend del POS. Instancia unica que se usa para imprimir recibos |
| Modo offline del POS | Capacidad del POS de seguir operando (cobrando, imprimiendo recibos, registrando ventas en IndexedDB) cuando se cae el internet de la tienda |

---

## 3. Aspectos no tecnicos

### 3.1 Problema que resuelve

Odoo 19 CE solo soporta nativamente dos tipos de impresoras en el POS:

1. **Odoo IoT Box** — Hardware oficial. ~$200+ USD por tienda. Hay que
   comprar uno por sucursal
2. **Impresoras Epson ePOS** — Modelos especificos de Epson con SDK
   propietario. Limita drasticamente la eleccion de hardware

Si el Odoo CE corre en un VPS remoto (caso comun), las soluciones
server-side como los modulos OCA `report-print-send` (con CUPS en el
servidor) no funcionan porque el servidor remoto no puede ver las
impresoras locales de cada tienda.

El resultado es que la mayoria de comercios con Odoo CE caen en uno de
tres caminos malos:
- Comprar un IoT Box por cada tienda (caro a escala)
- Limitarse a Epson (caro y restrictivo)
- Aceptar la previsualizacion de impresion del navegador (lento, mala UX)

### 3.2 Publico objetivo

- **Operadores**: cajeros, baristas, meseros. Perfil no tecnico. Solo
  interactuan con el POS, no con el proxy
- **Administradores de tienda**: gerentes con perfil tecnico bajo. Necesitan
  instalar y configurar la app sin saber programar
- **Operadores de la marca multi-tienda**: 5+ tiendas, cada una con su
  PC Windows USB + impresora termica. Necesitan un setup replicable

### 3.3 Casos de uso

**CU-1: Imprimir recibo al cerrar venta**
- El cajero cierra/cobra una orden en el POS
- El recibo se imprime directamente en la impresora termica de caja, sin
  abrir ventana de previsualizacion del navegador

**CU-2: Imprimir comanda a cocina**
- El cajero/mesero agrega items con categoria de cocina y envia el pedido
- La impresora de cocina (puede ser la misma de caja, o una segunda fisica)
  imprime la comanda con los items nuevos/cambiados/cancelados

**CU-3: Abrir cajon de dinero**
- Al cobrar en efectivo, el POS dispara el comando ESC/POS para abrir el
  cajon conectado a la impresora termica

**CU-4: Imprimir recibo cuando NO hay internet**
- Caja sigue cobrando con el modo offline del POS (datos en IndexedDB)
- El recibo igualmente sale, porque el proxy esta en la misma PC y no
  requiere internet para imprimir
- Cuando regresa internet, las ventas se sincronizan al servidor

### 3.4 Capacidades obligatorias (v1.3 actual)

- Impresion directa de recibos, sin previsualizacion del navegador
- Soporte de comandas de cocina con filtrado por categorias
- Soporte de apertura de cajon
- Compatibilidad con impresoras genericas ESC/POS (no solo Epson)
- Funcionamiento offline (modo critico para retail)
- HTTPS local con certificado de confianza, sin warnings del navegador
- CORS estricto: solo el dominio Odoo configurado puede invocar la impresora
- Bind a loopback (127.0.0.1): nadie en la LAN puede invocar el proxy
- Cero modificaciones al codigo de Odoo. Solo configuracion via UI
- Configuracion por archivo `config.yaml` editable por la tienda

### 3.5 Capacidades futuras (Fase 2-4)

**Fase 2 — App nativa Windows con GUI** (planificado):
- System tray icon persistente (estado verde/rojo)
- Dashboard de configuracion con tabs (Impresoras / Conexion Odoo / Sistema / Logs)
- Configuracion multi-impresora desde GUI con roles
- Toggle de auto-start con Windows desde el dashboard
- Boton de "Imprimir pagina de prueba" por impresora

**Fase 3 — Empaquetado** (planificado):
- Distribucion como `.exe` autocontenido (no requiere Python instalado)
- Installer guiado tipo Inno Setup
- Instalacion automatica del certificado HTTPS por el installer
- Atajos en menu inicio / escritorio

**Fase 4 — macOS** (planificado):
- Misma funcionalidad sobre CUPS en lugar de win32print
- Empaquetado `.app` + DMG installer
- Auto-start via LaunchAgent

### 3.6 Restricciones de UX

- Un cajero NO debe nunca interactuar con la ventana del proxy. El proxy
  debe ser invisible
- El administrador de la tienda debe poder instalar la app con un perfil
  no tecnico siguiendo INSTALL_WINDOWS.md
- Los logs deben ser legibles: eventos importantes (conexion, impresion,
  errores), no ruido de bajo nivel
- Los errores deben sugerir la accion correctiva, no solo describir el sintoma

---

## 4. Aspectos tecnicos

### 4.1 Stack tecnologico

| Pieza | Tecnologia | Razon |
|---|---|---|
| Lenguaje | Python 3.11+ | Estandar para herramientas multi-plataforma con buen ecosistema |
| Framework HTTP | FastAPI | Async nativo, middleware sencillo, JSON-RPC trivial |
| Servidor ASGI | uvicorn | Soporte SSL listo, integracion FastAPI |
| Procesamiento de imagen | Pillow | Conversion JPEG/PNG -> 1bpp para ESC/POS raster |
| Impresion Windows | pywin32 (`win32print`) | API nativa, soporta envio RAW al spooler |
| Impresion macOS (futuro) | pycups | CUPS es nativo en macOS |
| Configuracion | PyYAML | Legible para humanos, mas amigable que JSON |
| Certificados HTTPS | mkcert | Genera CA local y certs firmados de confianza |
| GUI (Fase 2) | CustomTkinter | Bundle ligero, look moderno, basado en Tkinter (incluido en Python) |
| Tray (Fase 2) | pystray | Cross-platform (Win + Linux + Mac) |
| Empaquetado (Fase 3) | PyInstaller `--onedir` | Estandar, arranque rapido, distribucion confiable |
| Installer (Fase 3) | Inno Setup | Gratis, popular en Windows, scripts simples |

### 4.2 Plataformas soportadas

- **Windows 10** y **Windows 11** (objetivo principal hoy)
- **macOS 12+** (objetivo Fase 4)
- Linux teoricamente posible (mismo stack + CUPS) pero no priorizado

Navegadores soportados:
- **Chrome 130+** y **Edge 130+** — soporte completo de PNA
- **Firefox** — NO soportado actualmente. La validacion del cert mkcert
  requiere instalar la CA en el almacen NSS de Firefox por separado, y el
  comportamiento de Private Network Access difiere. No prioritario

### 4.3 Arquitectura general

```
                INTERNET                              RED LOCAL (tienda)
                   |                                          |
+------------------+------------------+         +-------------+-------------+
|   VPS                               |         |   PC Windows (10/11)      |
|                                     |         |                           |
|   Odoo 19 CE                        |         |   Navegador (Chrome/Edge) |
|   - https://midominio.com           | <-----> |   - Sesion POS abierta    |
|   - DB, ORM, modulos POS            |         |        |                  |
|   - Renderizado de recibos en HTML  |         |        | HTTPS localhost  |
|                                     |         |        v                  |
+-------------------------------------+         |   POS Print Proxy         |
                                                |   - FastAPI :8072 (HTTPS) |
                                                |   - Endpoints IoT Box     |
                                                |        |                  |
                                                |        | win32print RAW   |
                                                |        v                  |
                                                |   Impresora termica USB   |
                                                |   - Driver generico POS   |
                                                +---------------------------+
```

**Cuando se cae internet**: la conexion `Browser <-> Odoo VPS` se interrumpe,
el POS entra en modo offline (cachea ventas en IndexedDB), pero la conexion
`Browser <-> Proxy local` sigue funcionando porque ambos estan en la misma
PC. Los recibos siguen imprimiendo y el negocio sigue operando.

### 4.4 Protocolo de comunicacion (IoT Box impersonation)

El proxy implementa 4 endpoints HTTP que imitan el protocolo del Odoo
IoT Box. Desde el punto de vista de Odoo, el proxy es un IoT Box mas.

| Endpoint | Metodo | Formato | Funcion |
|---|---|---|---|
| `/hw_proxy/hello` | GET | texto plano | Health check, retorna `"ping"` |
| `/hw_proxy/handshake` | POST | JSON-RPC 2.0 | Saludo inicial, retorna `true` |
| `/hw_proxy/status_json` | POST | JSON-RPC 2.0 | Keep-alive cada 5s, retorna estado de drivers |
| `/hw_proxy/default_printer_action` | POST | JSON-RPC 2.0 | Recibe trabajo de impresion o cajon |

Tambien expone un endpoint utilitario (no parte del protocolo IoT Box):
- `GET /printers` — Lista las impresoras detectadas en el sistema (debug)

**Acciones soportadas por `default_printer_action`**:
```json
// Imprimir recibo (la imagen viene como JPEG en base64)
{"params": {"data": {"action": "print_receipt", "receipt": "<base64>"}}}

// Abrir cajon de dinero
{"params": {"data": {"action": "cashbox"}}}
```

**Flujo end-to-end de una impresion**:
1. El POS renderiza el recibo con un componente OWL
2. Lo convierte a canvas -> JPEG -> base64
3. Hace POST a `/hw_proxy/default_printer_action`
4. El proxy decodifica base64 -> bytes JPEG
5. Redimensiona al ancho del papel (576px para 80mm, 384px para 58mm)
6. Convierte a 1bpp con dithering
7. Genera comandos ESC/POS raster (GS v 0)
8. Envia RAW al spooler de Windows con `win32print`
9. Windows entrega los bytes a la impresora sin modificar
10. La impresora interpreta ESC/POS, imprime y corta

### 4.5 Seguridad

**CORS estricto**:
- El proxy solo acepta peticiones con header `Origin` igual al dominio
  Odoo configurado en `config.yaml`
- Cualquier otro origen recibe `403 Forbidden` en el preflight

**Private Network Access (PNA)**:
- Chrome/Edge envian preflight OPTIONS con
  `Access-Control-Request-Private-Network: true` cuando una pagina publica
  intenta hablar con loopback
- El proxy responde con `Access-Control-Allow-Private-Network: true`
- Middleware custom porque el `CORSMiddleware` estandar de FastAPI no
  incluye este header

**HTTPS local**:
- mkcert crea una CA local privada en cada PC
- Instala esa CA en el almacen de certificados de confianza de Windows
- Genera un certificado para `localhost` y `127.0.0.1` firmado por esa CA
- Los navegadores aceptan el cert sin warnings porque la CA esta en el
  almacen de confianza

**Cert por maquina**:
- La CA mkcert es UNICA por equipo. NO se pueden copiar los archivos `.pem`
  entre PCs porque la CA del equipo origen no esta en el equipo destino
- Cada PC nueva tiene que ejecutar `setup_https.bat` (que llama
  `mkcert -install` + genera certs propios)

**Bind a loopback**:
- El proxy escucha solo en `127.0.0.1`, NO en `0.0.0.0`
- Nadie en la LAN puede invocar la impresora aunque conozca el puerto
- Solo procesos en la propia PC pueden conectarse

### 4.6 Concurrencia y estabilidad

**Event loop en Windows**:
- Se fuerza `WindowsSelectorEventLoopPolicy` antes de arrancar uvicorn
- El loop por defecto (`Proactor`) genera `ConnectionResetError [WinError
  10054]` cuando el navegador cierra conexiones HTTPS keep-alive de forma
  abrupta. La respuesta HTTP ya se entrego correctamente, pero el cleanup
  del socket falla
- Selector es mas estable para I/O ligero (un proxy de impresion no
  necesita las features avanzadas del Proactor)

**Exception handler de respaldo**:
- En el lifespan de FastAPI se instala un exception handler custom en el
  loop que silenciosamente ignora `ConnectionResetError`,
  `ConnectionAbortedError` y `BrokenPipeError`
- Asi, aunque uvicorn o el SO usen Proactor por alguna razon, el ruido
  se intercepta en la fuente

**Spooler de Windows**:
- `win32print` envia los bytes RAW al spooler. El spooler serializa los
  trabajos por impresora, no hay riesgo de mezclar bytes de dos impresiones
  concurrentes

### 4.7 Logging

**Niveles**:
- **INFO** por defecto: eventos relevantes (POS conectado, impresion
  ejecutada, errores de impresion)
- **DEBUG** opcional (config `verbose: true`): incluye cada keep-alive
  `status_json`. Util para diagnostico

**Loggers silenciados**:
- `uvicorn.access`: desactivado (sino llenaria con 1 log/5s por keep-alive)
- `uvicorn.error`: nivel WARNING (deja pasar errores reales)
- `asyncio`: nivel CRITICAL (los `ConnectionResetError` no se logguean)

**Formato**:
```
HH:MM:SS [NIVEL] mensaje
```

**Eventos importantes**:
- Banner de arranque: version, modo HTTPS/HTTP, dominio Odoo, puerto,
  impresora configurada, impresoras detectadas, hostname
- Self-test del certificado al arrancar
- "POS conectado" una sola vez al recibir el primer handshake o status
- "Impreso en 'POS-80' (N bytes)" por cada impresion exitosa
- "ERROR al imprimir en 'POS-80': <razon>" por cada fallo

### 4.8 Configuracion (`config.yaml`)

```yaml
# Dominio Odoo permitido (CORS). EXACTAMENTE igual al de la barra del
# navegador (con https://, sin barra final, sin path)
odoo_domain: "https://midominio.com"

# Puerto donde escucha el proxy
port: 8072

# Nombre EXACTO de la impresora en Windows
printer_name: "POS-80"

# Ancho de impresion en pixeles (576 para 80mm, 384 para 58mm)
paper_width: 576

# Logs detallados: false = solo eventos importantes (default)
verbose: false

# (Futuro Fase 1) Multi-impresora con roles:
# printers:
#   - name: "Caja"
#     port: 8072
#     windows_printer: "POS-80"
#     paper_width: 576
#     role: receipt
#   - name: "Cocina"
#     port: 8073
#     windows_printer: "KITCHEN-80"
#     paper_width: 576
#     role: kitchen
```

### 4.9 Endpoints expuestos (resumen tecnico)

Ver detalle en seccion 4.4. Todos bajo `/hw_proxy/*` excepto `/printers`
que es utilitario interno.

---

## 5. Decisiones de diseno

Esta seccion documenta el QUE y POR QUE de cada decision arquitectural,
para que futuras discusiones de trade-offs partan del contexto correcto.

### 5.1 HTTPS local vs tunel inverso vs WebSocket outbound

**Opciones evaluadas**:

| Arquitectura | Funciona offline | Razon |
|---|---|---|
| Tunel inverso (PC -> VPS Traefik) | NO | Sin internet, el browser no resuelve DNS publico ni llega al VPS |
| WebSocket outbound (proxy -> VPS) | NO | El browser depende del VPS para encolar el job de impresion |
| **HTTPS local (proxy en localhost)** | **SI** | Browser y proxy en la misma PC, no requieren internet |

**Decision: HTTPS local**

**Razon**: la capacidad offline del POS es CRITICA para retail. Un cajero
no puede decir "espere a que regrese el internet para darle su recibo".
Cualquier solucion que dependa de salir a internet para imprimir degrada
una funcionalidad que el POS ya tiene de fabrica.

### 5.2 mkcert vs OpenSSL self-signed

**Decision: mkcert**

**Razon**: con OpenSSL self-signed el navegador muestra warning "Tu
conexion no es privada" y hay que aceptar manualmente la excepcion. Con
mkcert se instala una CA local en el almacen de confianza del SO, y el
cert firmado por esa CA es aceptado sin warnings.

Es el mismo metodo que usan profesionales de desarrollo web para HTTPS
local. Es robusto, gratuito, multiplataforma.

### 5.3 CustomTkinter vs PySide6 (Fase 2)

**Decision: CustomTkinter**

**Razon**: el bundle final con PySide6 agrega ~50MB de runtime Qt al
ejecutable. CustomTkinter agrega ~5MB. Para una app de configuracion con
pocas tabs y tablas, la potencia de Qt esta sobredimensionada. Tkinter
ademas viene incluido en Python, lo que simplifica el empaquetado.

### 5.4 pystray (cross-platform)

**Decision: pystray para el icono de bandeja**

**Razon**: aunque hubiera podido usar el tray nativo de Qt (si fueramos
con PySide6), pystray funciona en Windows, Linux y macOS con la misma
API. Esto facilita la Fase 4 (macOS) sin reescribir el tray.

### 5.5 Auto-start HKCU vs servicio Windows

**Decision: Auto-start via registro HKCU por default**

**Razon**: instalar la app como servicio Windows requiere admin, complica
el installer y aumenta la fragilidad (un servicio mal configurado puede
no arrancar). El registro `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
es la forma estandar de "iniciar con Windows" sin admin, funciona
identico en Win10 y Win11.

Opcion para usuarios avanzados: NSSM bundleado para los que quieran el
servicio de verdad.

### 5.6 Selector event loop vs Proactor en Windows

**Decision: WindowsSelectorEventLoopPolicy**

**Razon**: el ProactorEventLoop (default en Python 3.8+ Windows) genera
`ConnectionResetError [WinError 10054]` recurrentemente con conexiones
HTTPS keep-alive cerradas abruptamente. La respuesta HTTP ya esta
entregada, pero el cleanup del socket falla en Proactor. Selector no
tiene este problema y es perfectamente adecuado para I/O ligero.

### 5.7 Bind a 127.0.0.1 vs 0.0.0.0

**Decision: 127.0.0.1**

**Razon**: el proxy esta pensado para ser invocado solo por el navegador
en la misma PC. Bindear a 0.0.0.0 expondria la impresora a cualquier
dispositivo en la LAN, lo que es un riesgo de seguridad sin beneficio
funcional. El cert mkcert tampoco es valido para IPs LAN, asi que aunque
quisieras llamarlo remotamente, fallaria la validacion TLS.

---

## 6. Compatibilidad

### 6.1 Impresoras

**Soportadas (cualquier impresora ESC/POS)**:
- Epson — TM-T20, TM-T88, etc.
- Star Micronics — TSP100, TSP143, TSP650, etc.
- Bixolon — SRP-350, SRP-330, SRP-Q300
- Citizen — CT-S310, CT-S651, CT-S801
- Xprinter — XP-80C, XP-T80A, XP-T58K
- 3nStar — RPT008, RPT006
- Gprinter — GP-U80300I, GP-80250II
- Custom — VKP80II, K3
- Genericas chinas en general (las del mercado latinoamericano)

**Requisitos minimos**:
- Soporte de comandos ESC/POS (mayoria del mercado)
- Driver "Generic / Text Only" o driver POS del fabricante instalado en Windows
- Conexion USB (o configurada como impresora local de Windows)

**NO soportadas**:
- Impresoras de oficina (HP LaserJet, Canon, Brother oficina): usan
  PCL/PostScript, no ESC/POS
- Matriciales antiguas sin ESC/POS
- Solo-Bluetooth sin emulacion USB

### 6.2 Navegadores

- **Chrome 130+** y **Edge 130+** — soporte completo
- **Firefox** — no soportado actualmente (incompatibilidad con NSS
  store + Private Network Access)
- **Safari** — Windows: no aplica. macOS Fase 4: por evaluar

### 6.3 Versiones Odoo

- **Odoo 19 CE** — soporte confirmado y probado
- Versiones anteriores (15, 16, 17, 18): el protocolo IoT Box ha sido
  estable historicamente, deberia funcionar pero no esta verificado

---

## 7. Restricciones y supuestos

**Restricciones de despliegue**:
- Una PC Windows por tienda (la misma donde corre el navegador del POS)
- Una impresora termica USB conectada y reconocida por Windows
- Permisos de admin la primera vez para `mkcert -install`
- Conexion saliente a GitHub la primera vez (descarga `mkcert.exe`)

**Restricciones funcionales**:
- El cert es valido solo para `localhost` y `127.0.0.1`. No funciona si
  se intenta invocar desde otra IP de la LAN
- El proxy NO autentica por API key (la autenticacion es por origen CORS).
  Esto es suficiente porque vive en loopback
- El proxy no maneja colas persistentes: si Windows o el proxy se cuelgan
  durante una impresion, el trabajo se pierde. El POS reintenta segun su
  propia logica

**Supuestos sobre el POS**:
- `is_posbox=True` debe estar marcado en Ajustes POS > Connected Devices
  para que los recibos viajen al proxy
- `iface_print_via_proxy=True` debe estar marcado para activar la conexion
- `iface_print_auto=True` para imprimir sin previsualizacion
- `proxy_ip=localhost:8072` debe coincidir con el puerto del proxy
- `point_of_sale.use_lna` **NO** debe estar activado (con HTTPS local
  use_lna fuerza HTTP, que rompe el setup)

---

## 8. Las dos rutas de impresion de Odoo POS

Es critico entenderlas porque cada una se configura en un lugar diferente
de Odoo. Es el error mas comun al instalar.

| Aspecto | Recibos de venta | Comandas de cocina |
|---|---|---|
| Modelo backend Odoo | `pos.config` (un IoT Box global) | `pos.printer` records (multiples) |
| Driver frontend | `hardware_proxy.printer` (instancia unica) | `pos_store.unwatched.printers[]` |
| Trigger | `printReceipt()` al cerrar orden | `sendOrderInPreparation()` al modificar |
| Activacion | `is_posbox` + `iface_print_via_proxy` + `proxy_ip` en pos.config | Cada `pos.printer` con su propio `proxy_ip` |
| UI Odoo | Ajustes POS > Connected Devices > IoT Box | Configuracion > Impresoras de preparacion |
| Filtrado | Imprime siempre el recibo completo | Filtra por categoria de producto |

**Implicacion practica**: configurar solo "Impresoras de preparacion" NO
activa el recibo. Hay que activar tambien la seccion "IoT Box" de los
Ajustes del POS. Ambas rutas convergen en el proxy: usan el mismo
endpoint `/hw_proxy/default_printer_action` con el mismo formato JSON-RPC.

**Codigo fuente Odoo de referencia**:
- `addons/point_of_sale/static/src/app/models/pos_config.js:76-84`
  (getter `useProxy` que requiere `is_posbox` AND alguna flag de hardware)
- `addons/point_of_sale/static/src/app/services/pos_store.js:173-175`
  (gate `if (this.config.useProxy) await this.connectToProxy()`)
- `addons/point_of_sale/static/src/app/services/hardware_proxy_service.js:51-72`
  (`connectToPrinter()` solo si `iface_print_via_proxy=True`)

---

## Documentos relacionados

- [README.md](README.md) — Vista general y referencia rapida
- [INSTALL_WINDOWS.md](INSTALL_WINDOWS.md) — Guia operativa paso a paso
- [HITOS.md](HITOS.md) — Estado actual, hitos completados, roadmap y bugs abiertos
