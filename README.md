# POS Print Proxy

> Impresion directa en Odoo 19 POS con impresoras termicas USB genericas, sin
> IoT Box, manteniendo el modo offline del POS.

Un puente HTTPS local que impersona el protocolo del Odoo IoT Box, permitiendo
imprimir tickets y comandas directamente desde el navegador hacia cualquier
impresora termica USB conectada a la PC de la tienda.

---

## Tabla de Contenidos

- [El problema](#el-problema)
- [La solucion](#la-solucion)
- [Caracteristicas](#caracteristicas)
- [Por que HTTPS local y no un tunel al servidor](#por-que-https-local-y-no-un-tunel-al-servidor)
- [Arquitectura](#arquitectura)
- [Como funciona](#como-funciona)
- [Inicio rapido](#inicio-rapido)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Referencia de configuracion](#referencia-de-configuracion)
- [Endpoints expuestos](#endpoints-expuestos)
- [Compatibilidad de impresoras](#compatibilidad-de-impresoras)
- [Comparacion con alternativas](#comparacion-con-alternativas)
- [Solucion de problemas](#solucion-de-problemas)
- [Desarrollo](#desarrollo)
- [Despliegue en multiples tiendas](#despliegue-en-multiples-tiendas)
- [Roadmap](#roadmap)
- [Licencia](#licencia)

---

## El problema

Odoo 19 Community Edition POS solo soporta nativamente dos tipos de impresoras:

1. **Odoo IoT Box** — Hardware oficial, $200+ USD por tienda
2. **Impresoras Epson ePOS** — Modelos especificos con SDK propietario

Si tu Odoo corre en un VPS remoto (lo normal en Odoo CE), las soluciones
basadas en CUPS server-side (modulos OCA `report-print-send`) no funcionan
porque el servidor no puede ver las impresoras locales de cada tienda.

Adicionalmente, **el POS de Odoo tiene modo offline**: si se cae internet, el
cajero puede seguir vendiendo y debe poder seguir imprimiendo recibos. Esto
limita las soluciones — cualquier arquitectura que requiera salir a internet
para imprimir un ticket rompe esa funcionalidad critica.

## La solucion

Un proxy HTTP**S** local en Python que:

- Corre en la misma PC Windows donde se usa el POS
- Impersona el protocolo del Odoo IoT Box (4 endpoints HTTP)
- Recibe la imagen del recibo del POS y la convierte a comandos ESC/POS
- La envia a la impresora termica via USB usando el spooler de Windows

```
Antes:                                Despues:

[POS] -> [IoT Box $$$] -> [Impr.]    [POS] -> [Print Proxy gratis] -> [Impr.]
                                              (HTTPS local, mismo PC)
```

## Caracteristicas

- **Impresion directa** sin previsualizacion del navegador
- **Compatible con cualquier impresora termica ESC/POS** (no solo Epson)
- **Funciona en modo offline del POS** (no depende de internet)
- **HTTPS local** con certificado de confianza generado automaticamente
- **Soporte de tickets y comandas de cocina** simultaneo
- **Apertura de cajon de dinero** mediante comando estandar ESC/POS
- **Cero modificaciones a Odoo** — solo configuracion via UI
- **CORS estricto + Private Network Access** — solo el dominio Odoo configurado puede usarlo
- **Configurable por tienda** mediante `config.yaml`
- **Multi-instancia** para tiendas con multiples impresoras
- **Replicable** para multiples tiendas con el mismo paquete

## Por que HTTPS local y no un tunel al servidor

Se evaluaron tres arquitecturas. Solo una preserva el modo offline del POS:

| Arquitectura | Funciona offline | Razon |
|---|---|---|
| Tunel inverso (PC -> VPS Traefik) | ❌ NO | Sin internet, el browser no puede resolver el subdominio publico ni llegar al VPS |
| WebSocket outbound (proxy -> VPS) | ❌ NO | El browser depende del VPS para encolar el job. Sin internet no llega |
| **HTTPS local (proxy en localhost)** | ✅ SI | El browser y el proxy estan en la misma PC. Sin internet siguen comunicandose |

Cualquier solucion que requiera salir a internet para imprimir un ticket
degrada la capacidad offline del POS — inaceptable para retail. Por eso este
proyecto usa HTTPS local con certificado auto-confiable, generado por la
herramienta `mkcert` que instala una CA local en el almacen de certificados
de Windows.

## Arquitectura

```
                INTERNET                          RED LOCAL (tienda)
                   |                                       |
+------------------+------------------+      +-------------+-------------+
|   VPS                               |      |   PC Windows 11           |
|                                     |      |                           |
|   Odoo 19 CE                        |      |   Navegador (Chrome/Edge) |
|   - https://tudominio.com           |<---->|   - Sesion POS abierta    |
|   - DB, ORM, modulos POS            |      |        |                  |
|   - Renderizado de recibos en HTML  |      |        | HTTPS localhost  |
|                                     |      |        v                  |
+-------------------------------------+      |   POS Print Proxy         |
                                             |   - FastAPI :8072 (HTTPS) |
                                             |   - Endpoints IoT Box     |
                                             |        |                  |
                                             |        | win32print RAW   |
                                             |        v                  |
                                             |   Impresora termica USB   |
                                             |   - Driver generico POS   |
                                             +---------------------------+
```

Cuando se cae internet en la tienda:
- La conexion `Browser <-> Odoo VPS` se interrumpe
- La conexion `Browser <-> Proxy local` sigue funcionando (todo en una sola PC)
- El POS entra en modo offline, sigue cobrando y sigue imprimiendo

## Como funciona

### Las dos rutas de impresion de Odoo POS

Odoo 19 POS imprime recibos y comandas de cocina por **dos rutas distintas**:

| Aspecto | Recibos de venta | Comandas de cocina |
|---------|------------------|---------------------|
| Modelo backend | `pos.config` (un IoT Box global) | `pos.printer` records |
| Driver frontend | `hardware_proxy.printer` (instancia unica) | `pos_store.unwatched.printers[]` |
| Trigger | `printReceipt()` al cerrar orden | `sendOrderInPreparation()` al modificar |
| Activacion | `is_posbox + iface_print_via_proxy + proxy_ip` en pos.config | Cada `pos.printer` con su `proxy_ip` |
| UI Odoo | Ajustes POS > Connected Devices > IoT Box | Configuracion > Impresoras de preparacion |

**Implicacion practica**: configurar las "Impresoras de preparacion" NO activa
los recibos. Hay que activar tambien la seccion "IoT Box" de los Ajustes del
POS. Ambas rutas convergen en el proxy: usan el mismo endpoint
`/hw_proxy/default_printer_action` con el mismo formato JSON-RPC.

### Protocolo IoT Box que implementamos

| Endpoint | Metodo | Cuando lo usa el POS |
|----------|--------|----------------------|
| `/hw_proxy/hello` | GET | Health check inicial (texto plano "ping") |
| `/hw_proxy/handshake` | POST | Apreton de manos JSON-RPC |
| `/hw_proxy/status_json` | POST | Cada 5s para mantener conexion viva |
| `/hw_proxy/default_printer_action` | POST | Imprime un ticket o abre el cajon |

### Flujo de impresion completo

```
1. Usuario cobra una venta en el POS
                |
                v
2. POS renderiza el recibo en HTML usando un componente OWL
                |
                v
3. POS convierte el HTML a canvas, luego a imagen JPEG, luego a base64
                |
                v
4. POS envia POST a https://localhost:8072/hw_proxy/default_printer_action
   con JSON-RPC: { params: { data: { action: "print_receipt", receipt: "<b64>" }}}
                |
                v
5. Proxy decodifica el base64 y obtiene los bytes JPEG
                |
                v
6. Proxy redimensiona la imagen al ancho del papel (576px para 80mm)
                |
                v
7. Proxy convierte la imagen a 1 bit (blanco/negro)
                |
                v
8. Proxy genera comandos ESC/POS de tipo "raster image" (GS v 0)
                |
                v
9. Proxy envia los comandos RAW al spooler de Windows usando win32print
                |
                v
10. Windows entrega los datos a la impresora por USB sin modificarlos
                |
                v
11. La impresora interpreta los comandos ESC/POS e imprime el ticket
                |
                v
12. Comando final ESC/POS de corte automatico de papel
```

### Por que HTTPS local con certificado de confianza

Cuando una pagina HTTPS publica (`https://tudominio.com`) intenta hablar con
un servicio HTTP local, los navegadores aplican dos capas de seguridad que
bloquean la peticion:

1. **Mixed Content blocking**: paginas HTTPS no pueden cargar recursos HTTP
2. **Private Network Access (PNA)**: paginas publicas que acceden a red
   privada/loopback necesitan headers especiales en el preflight

La solucion definitiva es servir el proxy en HTTPS con un certificado en el
que el navegador confie. El proyecto usa `mkcert`:

- Crea una "CA local" privada de la PC
- La instala en el almacen de certificados de confianza de Windows
- Genera certificados firmados por esa CA para `localhost` y `127.0.0.1`
- Los navegadores aceptan el certificado sin warnings (no es self-signed)

Es el mismo metodo que usan profesionales de desarrollo web para HTTPS local.

### Por que funciona con cualquier impresora termica

ESC/POS es un estandar de facto creado por Epson en los 90s adoptado por
practicamente todos los fabricantes de impresoras termicas POS: Star, Bixolon,
Citizen, Custom, Xprinter, Gprinter, 3nStar, etc. El proxy genera comandos
ESC/POS estandar.

## Inicio rapido

> Para instrucciones detalladas paso a paso, ver [INSTALL_WINDOWS.md](INSTALL_WINDOWS.md)

### En la PC Windows 11 de la tienda:

1. Instalar Python 3.11+ desde python.org (marcar "Add to PATH")
2. Copiar la carpeta `pos_print_proxy` a `C:\pos_print_proxy\`
3. Editar `config.yaml` con el dominio Odoo y nombre de impresora
4. **Click derecho en `setup_https.bat` > Ejecutar como administrador** (una vez)
5. Doble click en `start_proxy.bat`
6. Verificar `https://localhost:8072/hw_proxy/hello` → muestra "ping"

### En Odoo (UI web):

> En Odoo 19 los recibos y la cocina se configuran en lugares diferentes.
> Hay que activar AMBOS si se quieren usar ambos.

1. **POS > Configuracion > Ajustes** (NO "Puntos de Venta"):
   - Seccion **Connected Devices**: activar **IoT Box**, IP `localhost:8072`, activar **Receipt Printer**
   - Seccion **Receipts**: activar **Automatic Receipt Printing**
2. **POS > Configuracion > Impresoras de preparacion** (solo si necesitas comandas):
   crear impresora tipo IoT Box con direccion `localhost:8072` y categorias
3. **Cerrar y reabrir la sesion POS**

## Estructura del proyecto

```
pos_print_proxy/
|
|-- main.py                 # Servidor FastAPI con los 4 endpoints IoT Box (HTTPS opcional)
|-- printer_backend.py      # Conversion de imagen a ESC/POS + envio a Windows
|-- config.yaml             # Configuracion editable por tienda
|-- requirements.txt        # Dependencias Python
|-- start_proxy.bat         # Inicio rapido por doble click
|-- setup_https.bat         # Setup unico de HTTPS local (descarga mkcert, genera certs)
|-- README.md               # Este archivo
|-- INSTALL_WINDOWS.md      # Guia de instalacion paso a paso para usuarios finales
|
|-- (generados por setup_https.bat)
|-- localhost.pem           # Certificado HTTPS publico
|-- localhost-key.pem       # Clave privada (no compartir)
`-- mkcert.exe              # Herramienta de gestion de certificados
```

## Referencia de configuracion

Archivo: `config.yaml`

| Parametro | Tipo | Default | Descripcion |
|-----------|------|---------|-------------|
| `odoo_domain` | string | `https://tudominio.com` | URL completa del Odoo. Solo este dominio podra enviar trabajos al proxy (CORS). Sin barra final, con protocolo |
| `port` | int | `8072` | Puerto del proxy. Debe coincidir con la direccion en Odoo |
| `printer_name` | string | `POS-80` | Nombre EXACTO de la impresora en Windows |
| `paper_width` | int | `576` | Ancho en pixeles. `576` para 80mm, `384` para 58mm |
| `kitchen_printer_name` | string (opcional) | — | Segunda impresora dedicada a cocina |
| `kitchen_port` | int (opcional) | — | Puerto de la segunda instancia |

### Ejemplo: tienda con una sola impresora (recibos + cocina compartida)

```yaml
odoo_domain: "https://mitienda.com"
port: 8072
printer_name: "Xprinter XP-80"
paper_width: 576
```

### Ejemplo: tienda con impresora separada para cocina

```yaml
odoo_domain: "https://mitienda.com"
port: 8072
printer_name: "Xprinter XP-80"
paper_width: 576

kitchen_printer_name: "Bixolon SRP-350"
kitchen_port: 8073
```

## Endpoints expuestos

### Endpoints del protocolo IoT Box

#### `GET /hw_proxy/hello`

Health check. El POS hace fetch simple esperando texto plano.

**Respuesta**: `200 OK` con cuerpo `ping`

#### `POST /hw_proxy/handshake`

Apreton de manos JSON-RPC inicial.

**Respuesta**: `{ "jsonrpc": "2.0", "id": 1, "result": true }`

#### `POST /hw_proxy/status_json`

Status check periodico (cada 5s).

**Respuesta**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": { "printer": { "status": "connected" } }
}
```

#### `POST /hw_proxy/default_printer_action`

Endpoint principal de impresion.

```json
// Imprimir ticket
{
  "params": {
    "data": {
      "action": "print_receipt",
      "receipt": "<imagen_base64_JPEG_o_PNG>"
    }
  }
}

// Abrir cajon de dinero
{
  "params": {
    "data": { "action": "cashbox" }
  }
}
```

### Endpoint utilitario (debug)

#### `GET /printers`

Lista las impresoras disponibles en el sistema. Util para verificar que el
nombre en `config.yaml` esta bien escrito.

```json
{
  "printers": ["POS-80", "Microsoft Print to PDF", "Fax"],
  "configured": "POS-80"
}
```

## Compatibilidad de impresoras

### Marcas/modelos compatibles (ESC/POS)

Cualquier impresora termica de 58mm o 80mm que soporte ESC/POS:

- **Epson** — TM-T20, TM-T88, etc.
- **Star Micronics** — TSP100, TSP143, TSP650, etc.
- **Bixolon** — SRP-350, SRP-330, SRP-Q300, etc.
- **Citizen** — CT-S310, CT-S651, CT-S801, etc.
- **Xprinter** — XP-80C, XP-T80A, XP-T58K, etc.
- **3nStar** — RPT008, RPT006, etc.
- **Gprinter** — GP-U80300I, GP-80250II, etc.
- **Custom** — VKP80II, K3, etc.
- **Genericas chinas** — la mayoria del mercado mexicano/latinoamericano

### Requisitos minimos

- Soporte de comandos ESC/POS (la mayoria los soportan)
- Driver "Generic / Text Only" o driver POS del fabricante en Windows
- Conexion USB (o de red, configurada como impresora local en Windows)

### NO funcionara con

- Impresoras de oficina (HP LaserJet, Canon, etc.) — usan PCL/PostScript
- Matriciales antiguas que no soporten ESC/POS
- Solo Bluetooth sin emulacion USB

## Comparacion con alternativas

| Solucion | Costo | Hardware extra | Cualquier impresora | Modificar Odoo | Funciona offline |
|----------|-------|----------------|---------------------|----------------|------------------|
| **POS Print Proxy** (este proyecto) | Gratis | Ninguno | Si | No | Si |
| Odoo IoT Box | $200+/tienda | Si | Si | No | Si |
| Impresora Epson ePOS | $250-400 | Si (especifica) | No | No | Si |
| OCA `base_report_to_printer_cups` | Gratis | Servidor CUPS | Si | Si | No |
| QZ Tray | $/licencia firma | Ninguno | Si | Si (modulo) | Si |
| Imprimir desde el navegador | Gratis | Ninguno | Si (con dialogo) | No | Si |
| Tunel inverso (frp/ngrok) | $0-$ | Ninguno extra | Si | No | **No** |
| Outbound WebSocket al VPS | Gratis | Ninguno extra | Si | Si (modulo) | **No** |

## Solucion de problemas

> Para troubleshooting detallado, ver [INSTALL_WINDOWS.md](INSTALL_WINDOWS.md#solucion-de-problemas)

### Resumen rapido

| Sintoma | Causa probable | Solucion |
|---------|---------------|----------|
| "Mixed Content" / CORS error en DevTools | Proxy en HTTP, Odoo en HTTPS | Ejecutar `setup_https.bat` como admin |
| Cocina si imprime, recibos no | Falta `is_posbox` y/o `iface_print_via_proxy` | Activar **IoT Box** + **Receipt Printer** en Ajustes POS |
| Icono POS rojo/gris | Proxy no corriendo | Verificar ventana CMD, abrir `https://localhost:8072/hw_proxy/hello` |
| Imprime caracteres raros | Driver incorrecto | Cambiar a "Generic / Text Only" o driver POS del fabricante |
| Warning de cert en navegador | CA no instalada | Re-ejecutar `setup_https.bat` como admin |
| `python` no se reconoce | Python no esta en PATH | Reinstalar marcando "Add to PATH" |

### Ver impresoras disponibles

```cmd
python -c "import win32print; print([p[2] for p in win32print.EnumPrinters(2)])"
```

O abrir en el navegador: `https://localhost:8072/printers`

### Ver logs en vivo

La ventana CMD donde corre `start_proxy.bat` muestra todas las peticiones en
tiempo real. Buscar:
- `Recibido trabajo de impresion (NNNN bytes)` → el POS si esta enviando
- `Printed to 'NOMBRE' (NNNN bytes)` → la impresora recibio los datos
- `Error al imprimir: ...` → algo fallo en el envio a Windows

## Desarrollo

### Setup de desarrollo

```bash
git clone <este-repo>
cd pos_print_proxy
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt
# Generar certs HTTPS (una vez, requiere admin)
setup_https.bat
python main.py
```

### Ejecutar en modo debug

```bash
uvicorn main:app --host 0.0.0.0 --port 8072 \
  --ssl-certfile localhost.pem --ssl-keyfile localhost-key.pem \
  --reload --log-level debug
```

### Probar impresion sin POS

```python
# test_print.py
import base64
from printer_backend import print_image_win32

with open("test_image.jpg", "rb") as f:
    img_bytes = f.read()

print_image_win32(img_bytes, "POS-80", paper_width=576)
```

### Tecnologias utilizadas

| Tecnologia | Para que |
|------------|----------|
| **Python 3.11+** | Lenguaje del proxy |
| **FastAPI** | Framework web async |
| **Uvicorn** | ASGI server con soporte SSL |
| **Pillow (PIL)** | Procesamiento de imagenes |
| **pywin32** | Acceso al subsistema de impresion de Windows |
| **PyYAML** | Parseo del archivo de configuracion |
| **mkcert** | Generacion de certificados HTTPS de confianza local |

## Despliegue en multiples tiendas

Este proyecto esta disenado para escalar a multiples tiendas con minima friccion.

### Estrategia recomendada

1. **Crear un paquete maestro**: la carpeta `pos_print_proxy/` con todo el codigo
2. **Por cada tienda**:
   - Copiar el paquete a la PC
   - Editar `config.yaml` con los datos especificos
   - Ejecutar `setup_https.bat` como admin (una vez)
   - Ejecutar `start_proxy.bat`
3. **Documentar en una hoja de calculo**:
   - Tienda → IP de la PC → Nombre de impresora → Dominio Odoo

### Empaquetado futuro como .exe

Cuando la solucion este validada, empaquetar con PyInstaller:

```bash
pip install pyinstaller
pyinstaller --onefile --add-data "config.yaml;." \
            --add-data "localhost.pem;." --add-data "localhost-key.pem;." \
            --name pos_print_proxy main.py
```

`config.yaml` queda externo al .exe para que cada tienda pueda personalizarlo.

Para servicio Windows con auto-restart:
```cmd
nssm install POSPrintProxy "C:\pos_print_proxy\pos_print_proxy.exe"
nssm set POSPrintProxy AppDirectory "C:\pos_print_proxy"
nssm start POSPrintProxy
```

## Roadmap

- [x] Servidor FastAPI con endpoints IoT Box
- [x] Conversion de imagen a ESC/POS raster
- [x] Soporte de cajon de dinero
- [x] CORS configurable por dominio
- [x] Soporte de impresora de cocina separada
- [x] Middleware de Private Network Access (PNA)
- [x] HTTPS local con certificado mkcert auto-confiable
- [x] Setup automatizado HTTPS (`setup_https.bat`)
- [ ] Empaquetado como ejecutable .exe con PyInstaller
- [ ] Instalador MSI con servicio Windows preconfigurado
- [ ] Panel web local para monitoreo (`/dashboard`)
- [ ] Soporte de impresoras de red por TCP:9100
- [ ] Auto-discovery de impresoras nuevas
- [ ] Modulo Odoo opcional con tipo "Print Proxy" en la UI
- [ ] Auto-actualizacion del proxy

## Licencia

Uso libre para fines comerciales y privados.

## Creditos

Desarrollado para resolver la limitacion de Odoo 19 CE POS con impresoras
no-Epson en arquitecturas con VPS remoto y multiples tiendas, manteniendo la
capacidad offline del POS.

Inspirado en el protocolo del Odoo IoT Box, implementado por reverse-engineering
del codigo de:
- `addons/point_of_sale/static/src/app/utils/printer/hw_printer.js`
- `addons/point_of_sale/static/src/app/services/hardware_proxy_service.js`
- `addons/point_of_sale/static/src/app/models/pos_config.js` (getter `useProxy`)

Usa `mkcert` (https://github.com/FiloSottile/mkcert) para certificados HTTPS
locales de confianza.
