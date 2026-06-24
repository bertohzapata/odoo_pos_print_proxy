# Plantilla de Diagnostico — POS Print Proxy

> Esta plantilla recolecta TODOS los datos necesarios para diagnosticar
> diferencias entre equipos. Aplicarla identicamente en cada PC.

## Como usar

1. Copia este archivo y renombralo segun el equipo:
   - `DIAGNOSTICO-equipo1-win11-funciona.md`
   - `DIAGNOSTICO-equipo2-win11-laptop.md`
   - `DIAGNOSTICO-equipo3-win10.md`
2. Llena cada bloque marcado con `> Resultado:` o `[CAPTURA: ...]`
3. Al final, manda los 3 archivos completados (zip o pega aqui)

**Importante**: ejecutar TODO el setup desde cero antes de empezar el
diagnostico (borrar carpeta, volver a copiar v1.3, correr setup_https.bat,
arrancar start_proxy.bat). Asi todos parten del mismo punto.

---

# BLOQUE 1 — Datos del equipo

## 1.1 Identificacion

| Campo | Valor |
|---|---|
| Alias del equipo | `[ej: laptop-iromochis-tienda1]` |
| Rol esperado | `[ej: control que funciona / falla con error X / nuevo]` |
| Fecha del diagnostico | `[YYYY-MM-DD HH:MM]` |

## 1.2 Sistema Operativo

Ejecuta en CMD/PowerShell:
```
winver
```
> Resultado: `[ej: Windows 11 Pro 24H2 build 26100]`

```
systeminfo | findstr /B /C:"OS Name" /C:"OS Version" /C:"System Type"
```
> Resultado:
```
[pegar salida]
```

## 1.3 Navegador

Abre en el navegador que se usa para el POS: `chrome://version` o `edge://version`

> Navegador y version: `[ej: Chrome 131.0.6778.86 (Build oficial) 64 bits]`

> Modo de uso del POS:
> - [ ] Pestana normal del navegador
> - [ ] PWA instalada (icono en escritorio/menu inicio)
> - [ ] Modo "Aplicacion" (Edge: ... > Aplicaciones > Instalar)

## 1.4 Usuario Windows

Ejecuta en CMD:
```
whoami
net user %USERNAME% | findstr /C:"Privilegios locales" /C:"Local Group Memberships"
```
> Resultado:
```
[pegar salida — interesa saber si el usuario es Administrador o Estandar]
```

## 1.5 Python

```
python --version
where python
```
> Resultado:
```
[pegar salida]
```

---

# BLOQUE 2 — Estado del proxy local

## 2.1 Archivos en la carpeta del proxy

Asumiendo ruta `C:\pos_print_proxy\`:

```
dir C:\pos_print_proxy
```
> Resultado:
```
[pegar listado completo]
```

Confirmar que existen estos archivos (marcar con X):
- [ ] `main.py`
- [ ] `printer_backend.py`
- [ ] `config.yaml`
- [ ] `requirements.txt`
- [ ] `setup_https.bat`
- [ ] `start_proxy.bat`
- [ ] `localhost.pem`        (generado por setup_https)
- [ ] `localhost-key.pem`    (generado por setup_https)
- [ ] `mkcert.exe`           (descargado por setup_https)

## 2.2 Contenido EXACTO de `config.yaml`

```
type C:\pos_print_proxy\config.yaml
```
> Contenido:
```yaml
[pegar contenido completo, INCLUYENDO comentarios]
```

## 2.3 Log completo de arranque del proxy

1. Si hay una ventana CMD del proxy abierta, cerrarla
2. Doble click en `start_proxy.bat`
3. Esperar 10 segundos hasta que muestre "Proxy listo en ..."
4. Click derecho en la barra de titulo de la ventana CMD > Editar > Seleccionar todo > Enter (copia)
5. Pegar abajo:

> Log de arranque:
```
[pegar TODO el log desde la primera linea hasta "Proxy listo"]
```

Datos clave que deben aparecer (marcar):
- [ ] `POS Print Proxy v1.3` (o version actual)
- [ ] `Modo: HTTPS (correcto)` (NO `HTTP (INCORRECTO)`)
- [ ] `Dominio Odoo permitido: https://...` con el valor correcto
- [ ] `Puerto: 8072`
- [ ] `Impresora: NOMBRE`
- [ ] `Impresoras detectadas: [...]` (con NOMBRE en la lista)
- [ ] `Equipo: HOSTNAME`
- [ ] `Proxy listo en https://localhost:8072`

---

# BLOQUE 3 — Certificado HTTPS

## 3.1 CA mkcert en el almacen de Windows

PowerShell:
```
Get-ChildItem -Path Cert:\CurrentUser\Root | Where-Object {$_.Subject -like '*mkcert*'} | Format-List Subject, Thumbprint, NotAfter
Get-ChildItem -Path Cert:\LocalMachine\Root | Where-Object {$_.Subject -like '*mkcert*'} | Format-List Subject, Thumbprint, NotAfter
```
> Resultado:
```
[pegar salida. Debe haber al menos UN cert con Subject que diga 'mkcert development CA' y un Thumbprint]
```

Si el resultado esta vacio, mkcert NO instalo la CA correctamente.

## 3.2 Ubicacion de la CA mkcert

```
cd C:\pos_print_proxy
.\mkcert.exe -CAROOT
```
> Ruta CAROOT: `[ej: C:\Users\humbe\AppData\Local\mkcert]`

```
dir <ruta-de-arriba>
```
> Contenido:
```
[debe haber: rootCA.pem, rootCA-key.pem]
```

## 3.3 Detalles del cert de localhost

```
.\mkcert.exe -verify localhost
```
Si ese comando no existe, usar openssl o ver con:
```
powershell "Get-PfxCertificate localhost.pem | Format-List Subject, NotAfter, NotBefore, Issuer"
```
> Resultado:
```
[pegar salida — interesa que Issuer = 'mkcert development CA ...']
```

## 3.4 Self-test del proxy

En el log de arranque del proxy (Bloque 2.3), verificar que NO aparezca este
mensaje:
```
ATENCION: el certificado HTTPS existe pero NO es valido
```

> Aparece este error?
> - [ ] No (correcto)
> - [ ] Si — copiar mensaje exacto:
```
[pegar mensaje]
```

---

# BLOQUE 4 — Validacion directa del proxy (sin Odoo)

Estas pruebas validan SOLO el proxy, sin pasar por la app POS de Odoo.

## 4.1 Test `/hello` en el mismo navegador que usa el POS

Abrir nueva pestana en el navegador del POS y visitar:
```
https://localhost:8072/hw_proxy/hello
```

Resultado:
- [ ] Muestra `ping` sin warning ni candado tachado (CORRECTO)
- [ ] Muestra `ping` pero el navegador dice "No seguro" / candado tachado
- [ ] Muestra "Tu conexion no es privada" / NET::ERR_CERT_AUTHORITY_INVALID
- [ ] No carga / timeout / ERR_CONNECTION_REFUSED
- [ ] Otro: `[describir]`

[CAPTURA 4.1: pantallazo de esa pestana mostrando la URL + resultado]

## 4.2 Test `/printers` (debug)

```
https://localhost:8072/printers
```
> Resultado JSON:
```
[pegar el JSON que muestra]
```

## 4.3 Click en el candado HTTPS

En la pestana con `/hello` abierta, click en el candado de la barra de URL,
luego "Conexion es segura" > "El certificado es valido":

> Detalles del cert que muestra el navegador:
> - Emitido para: `[ej: localhost]`
> - Emitido por: `[ej: mkcert development CA ...]`
> - Valido hasta: `[fecha]`

[CAPTURA 4.3: pantallazo del detalle del cert]

---

# BLOQUE 5 — Configuracion de Odoo

## 5.1 URL exacta del POS

Acceder al POS en Odoo. Antes de entrar al POS, ya en la sesion logueada,
copiar la URL completa de la barra del navegador:

> URL exacta: `[ej: https://midominio.com/web#action=...&model=pos.session]`

> Dominio normalizado (solo `https://midominio.com`): `[__]`

Validar que este dominio coincide EXACTAMENTE con `odoo_domain` en `config.yaml`
(sin barra final, mismo protocolo, mismo subdominio).

## 5.2 Configuracion del Punto de Venta

[CAPTURA 5.2A: Ajustes POS > Connected Devices, mostrando:]
- [ ] Checkbox **IoT Box** activado
- [ ] Campo **IoT Box IP Address**: `localhost:8072`
- [ ] Checkbox **Receipt Printer** activado
- [ ] Checkbox **Cashdrawer** activado (si aplica)

[CAPTURA 5.2B: Ajustes POS > Receipts, mostrando:]
- [ ] Checkbox **Automatic Receipt Printing** activado
- [ ] Checkbox **Skip Preview Screen** activado

## 5.3 Impresoras de preparacion (cocina)

[CAPTURA 5.3: Punto de Venta > Configuracion > Impresoras de preparacion, lista]

Para cada impresora de preparacion configurada:
- Nombre: `[__]`
- Tipo: `[__]`
- Direccion del IoT Box: `[__]`
- Categorias: `[__]`

## 5.4 Parametro del sistema `use_lna`

Ajustes > Tecnico > Parametros del sistema, buscar `point_of_sale.use_lna`:

> Estado:
> - [ ] NO existe (correcto, con HTTPS local no se necesita)
> - [ ] Existe con valor `0` o `False` (correcto)
> - [ ] Existe con valor `1` o `True` (INCORRECTO con HTTPS local — debe borrarse)
> - [ ] Otro: `[__]`

## 5.5 Cookies / Sesion

Boton para hacer logout y volver a entrar (limpia cualquier cache de sesion):

- [ ] He hecho logout y vuelto a entrar antes del diagnostico

---

# BLOQUE 6 — DevTools mientras se prueba

**Importante**: hacer esto despues de los Bloques 4 y 5 (proxy ya arrancado,
Odoo configurado, sesion POS reabierta).

## 6.1 Setup de la captura

1. Cerrar la sesion POS si esta abierta
2. Abrir el POS en una pestana nueva
3. ANTES de entrar al POS o tan pronto cargue la pantalla principal,
   abrir DevTools (F12)
4. Pestana **Network**
5. Marcar la casilla **Preserve log** (arriba de la lista)
6. En el filtro de Network, escribir: `hw_proxy`
7. Recargar la pestana con `Ctrl+Shift+R` (recarga forzada sin cache)
8. Esperar 30 segundos

## 6.2 Resumen de Network

> Lista de peticiones a `hw_proxy/*` que aparecieron (con metodo + URL + status):
```
[ej:
OPTIONS https://localhost:8072/hw_proxy/hello       204
GET     https://localhost:8072/hw_proxy/hello       200
OPTIONS https://localhost:8072/hw_proxy/handshake   204
POST    https://localhost:8072/hw_proxy/handshake   200
OPTIONS https://localhost:8072/hw_proxy/status_json 204
POST    https://localhost:8072/hw_proxy/status_json 200
POST    https://localhost:8072/hw_proxy/status_json 200    (cada 5s)
...]
```

[CAPTURA 6.2: pantallazo de la pestana Network con el filtro `hw_proxy`,
mostrando todas las peticiones]

## 6.3 Detalle de cada tipo de peticion

Para CADA peticion unica de la lista anterior (no repetir status_json),
click derecho > Copy > Copy as cURL (Windows) y pegar.

Tambien click en la peticion > pestana **Headers** y capturar:

### 6.3.1 `OPTIONS /hw_proxy/hello` (preflight)

> Status: `[__]`

> Request Headers (los importantes):
```
Origin: [__]
Access-Control-Request-Method: [__]
Access-Control-Request-Headers: [__]
Access-Control-Request-Private-Network: [__]
Sec-Fetch-Site: [__]
Sec-Fetch-Mode: [__]
```

> Response Headers (los importantes):
```
Access-Control-Allow-Origin: [__]
Access-Control-Allow-Methods: [__]
Access-Control-Allow-Headers: [__]
Access-Control-Allow-Private-Network: [__]
```

### 6.3.2 `GET /hw_proxy/hello`

> Status: `[__]`

> Response body: `[__]` (esperado: `ping`)

### 6.3.3 `POST /hw_proxy/handshake`

> Status: `[__]`

> Response body: `[__]` (esperado: `{"jsonrpc":"2.0","id":N,"result":true}`)

### 6.3.4 `POST /hw_proxy/status_json` (uno cualquiera)

> Status: `[__]`

> Response body: `[__]` (esperado: `{"jsonrpc":"2.0","id":N,"result":{"printer":...}}`)

## 6.4 Peticiones que FALLAN

Si alguna peticion esta en rojo o tiene status >= 400 o aparece como "(failed)":

Para cada peticion fallida:

> Peticion: `[ej: GET https://localhost:8072/hw_proxy/hello]`

> Status: `[ej: (failed) / 0 / CORS error / Mixed Content]`

> Mensaje en la pestana Headers (arriba):
```
[ej: "Failed to load resource: net::ERR_FAILED" o "CORS error"]
```

> Si dice "provisional headers were shown", marcar: [ ]

[CAPTURA 6.4: pantallazo de cada peticion fallida con sus headers]

## 6.5 Consola del navegador

Pestana **Console** de DevTools (con el filtro en "Errors" y "Warnings"):

> Mensajes en consola relacionados con `hw_proxy`, `proxy`, `iot`, `printer`,
> `CORS`, `Mixed Content`, `Private Network`:
```
[pegar mensajes — borrar timestamps si quieres pero conservar el texto]
```

---

# BLOQUE 7 — Logs del proxy durante la prueba

Al mismo tiempo que se hace el Bloque 6, capturar lo que aparece en la
ventana CMD del proxy:

> Logs del proxy desde "Proxy listo" hasta 30 segundos despues de
> entrar al POS:
```
[pegar todo lo nuevo que aparece]
```

Datos clave que deberian aparecer:
- [ ] `POS conectado (handshake OK)` — significa que /handshake llego y respondio
- [ ] `POS conectado (keep-alive activo)` — fallback si solo llego status_json
- [ ] Sin lineas con `[ERROR]`
- [ ] Sin lineas con `Origen no permitido` (eso indicaria CORS mal configurado)

---

# BLOQUE 8 — Test funcional de impresion

## 8.1 Venta sin productos de cocina

1. Crear una orden con UN producto que NO este en ninguna categoria de
   impresora de preparacion
2. Cobrar y cerrar la orden

> Resultado:
> - [ ] El recibo se imprime automaticamente sin previsualizacion
> - [ ] Aparece la pantalla de recibo pero al hacer click en "Imprimir"
>   sale por la impresora termica
> - [ ] Aparece la pantalla de impresion del navegador (ventana modal de Chrome)
> - [ ] No imprime nada y aparece error: `[copiar texto del error]`

> Log del proxy mientras se hizo la prueba:
```
[pegar log entre "cobrar" y "imprime/falla"]
```

[CAPTURA 8.1: foto del ticket impreso, o screenshot del error]

## 8.2 Venta con producto de cocina

1. Crear una orden con UN producto de categoria configurada para cocina
2. Enviar a cocina (boton de envio a preparacion)

> Resultado:
> - [ ] La comanda sale en la impresora
> - [ ] No sale nada
> - [ ] Otro: `[describir]`

> Log del proxy:
```
[pegar]
```

## 8.3 Apertura de cajon (si aplica)

> Resultado:
> - [ ] El cajon se abre al cobrar en efectivo
> - [ ] No se abre
> - [ ] No aplica (no hay cajon conectado)

---

# BLOQUE 9 — Datos extras

## 9.1 Firewall / antivirus

> Hay firewall corporativo / antivirus activo distinto de Windows Defender?
> - [ ] No, solo Windows Defender
> - [ ] Si: `[nombre del antivirus o firewall, ej: McAfee, Kaspersky, Norton, Sophos]`

## 9.2 Red

```
ipconfig | findstr /C:"IPv4" /C:"IPv6"
```
> Resultado:
```
[pegar — interesa saber si hay configuracion IPv6 activa que pueda interferir
con localhost]
```

## 9.3 Proxy HTTP del sistema (no nuestro proxy)

```
netsh winhttp show proxy
```
> Resultado:
```
[pegar — esperado: "Direct access (no proxy server)"]
```

## 9.4 Resolucion de localhost

```
ping -n 1 localhost
ping -4 -n 1 localhost
ping -6 -n 1 localhost
```
> Resultado:
```
[pegar — interesa saber si localhost resuelve a 127.0.0.1 o a ::1]
```

---

# Notas libres

> Cualquier observacion que el usuario quiera anotar (cosas raras vistas, pasos
> que se hicieron diferente, errores previos, etc.):
```
[texto libre]
```

---

# Como enviarme los resultados

Comprime los 3 archivos completados (`DIAGNOSTICO-equipo1-...md`,
`DIAGNOSTICO-equipo2-...md`, `DIAGNOSTICO-equipo3-...md`) y todas las capturas
en un zip. O pega el contenido de cada archivo directo en el chat.

Con eso puedo comparar lado a lado los 3 equipos y aislar el delta exacto que
hace que el equipo problematico falle.
