# POS Print Proxy - Guia de Instalacion para Windows 11

## Que es esto y por que lo necesito

Cuando usas Odoo POS desde un navegador, el sistema normalmente no puede
comunicarse directamente con la impresora termica conectada a tu computadora.
Odoo esta disenado para usar un dispositivo especial llamado "IoT Box" (que
cuesta mas de $200 USD) o impresoras Epson especificas.

**Este programa resuelve ese problema.** Es un pequeno servicio que corre en tu
computadora Windows y actua como puente entre el navegador (donde usas Odoo
POS) y tu impresora termica USB. El POS cree que esta hablando con un IoT Box,
pero en realidad esta hablando con este programa, que a su vez envia la
impresion a tu impresora local.

### Diagrama simple:

```
Tu navegador (Odoo POS)
     |
     | "Oye IoT Box, imprime esto"
     v
POS Print Proxy (este programa, corriendo en tu misma PC)
     |
     | Envia los datos a la impresora
     v
Tu impresora termica USB
```

### Resultado:
- Los tickets se imprimen directamente al cerrar una orden (sin previsualizacion)
- Los pedidos de cocina se imprimen automaticamente al enviarlos
- Funciona con cualquier impresora termica generica (no solo Epson)
- Funciona en modo offline del POS (la impresora no necesita internet)
- No necesitas comprar un IoT Box

---

# PASOS OBLIGATORIOS

Estos pasos son necesarios para que el sistema funcione. Seguirlos en orden.

---

## Paso 1: Instalar Python en la computadora

Python es el lenguaje en el que esta escrito este programa. Una sola vez.

1. Abrir el navegador y ir a: https://www.python.org/downloads/
2. Hacer click en el boton amarillo "Download Python 3.1x.x"
3. Ejecutar el archivo descargado
4. **MUY IMPORTANTE**: En la primera pantalla del instalador, marcar la casilla
   **"Add python.exe to PATH"** (esta abajo, es facil no verla)
5. Click en "Install Now"
6. Esperar a que termine y cerrar

### Verificar que se instalo bien:

1. Presionar las teclas `Win + R`
2. Escribir `cmd` y presionar Enter (se abre una ventana negra)
3. Escribir: `python --version` y presionar Enter
4. Debe aparecer algo como: `Python 3.12.4`

Si aparece "no se reconoce el comando", desinstalar Python y volver a
instalarlo asegurandose de marcar "Add to PATH".

---

## Paso 2: Verificar que la impresora esta instalada en Windows

1. Conectar la impresora termica por USB y encenderla
2. Ir a **Configuracion de Windows > Bluetooth y dispositivos > Impresoras y escaneres**
3. Tu impresora debe aparecer en la lista (ej: "POS-80", "XP-80C", etc.)
4. **Anotar el nombre exacto** tal como aparece (con mayusculas, espacios, guiones)

Si no aparece:
- Instalar el driver que vino con la impresora
- Algunos modelos funcionan con "Generic / Text Only" de Windows

---

## Paso 3: Copiar y configurar el programa

1. Copiar la carpeta `pos_print_proxy` a la PC. Recomendacion: `C:\pos_print_proxy\`
2. Abrir `config.yaml` con el Bloc de Notas (click derecho > Abrir con > Bloc de notas)
3. Modificar:

```yaml
# Direccion web de tu Odoo (con https://, sin barra final)
odoo_domain: "https://tudominio.com"

# No cambiar a menos que indiquen
port: 8072

# Nombre EXACTO de tu impresora (Paso 2)
printer_name: "POS-80"

# 576 si es 80mm, 384 si es 58mm
paper_width: 576
```

4. Guardar (Ctrl + S)

---

## Paso 4: Activar HTTPS local (CRITICO)

Si tu Odoo se sirve por HTTPS (ej: `https://tudominio.com`), el navegador
bloquea por seguridad cualquier comunicacion entre la pagina HTTPS y un
servicio HTTP local. Esto se llama "Mixed Content blocking" y NO se puede
desactivar via configuracion de Odoo. La solucion es que el proxy tambien
hable HTTPS.

Este paso instala una autoridad certificadora local en Windows y genera un
certificado HTTPS para `localhost`. **Es obligatorio.**

### Como ejecutarlo:

1. Ir a la carpeta `C:\pos_print_proxy\`
2. **Click derecho** en el archivo `setup_https.bat`
3. Seleccionar **"Ejecutar como administrador"**
4. Si Windows pregunta si permitir, click en **Si**
5. Si aparece otra ventana de Windows pidiendo confirmar instalar la CA,
   click en **Si**
6. Esperar a que diga "Setup HTTPS completado con exito"
7. Cerrar esa ventana

Si todo salio bien, en la carpeta apareceran dos archivos nuevos:
- `localhost.pem` (certificado)
- `localhost-key.pem` (clave privada)

### Para que sirve esto

`mkcert` (la herramienta que descarga el script) crea una "CA local" — una
autoridad de certificacion que solo existe en tu PC. La instala en el almacen
de certificados de Windows como autoridad de confianza. Despues genera un
certificado HTTPS para `localhost` firmado por esa CA. Como Windows confia
en la CA, los navegadores Chrome y Edge confiaran en el certificado de
`localhost` sin warnings.

Es el mismo metodo que usan profesionales de desarrollo web para hacer
HTTPS en local.

---

## Paso 5: Ejecutar el programa por primera vez

1. **Doble click** en `start_proxy.bat`
2. Se abre una ventana negra (CMD)
3. La primera vez instalara componentes adicionales (1-2 min)
4. Cuando termine debe aparecer:

```
============================================================
POS Print Proxy v1.2 (HTTPS local + PNA)
  Modo: HTTPS (recomendado)
  Dominio Odoo permitido: https://tudominio.com
  Puerto: 8072
  Impresora: POS-80
  ...
============================================================
Proxy listo en https://localhost:8072
```

5. **Verificar**: Abrir el navegador y escribir:
   `https://localhost:8072/hw_proxy/hello`
   Debe aparecer la palabra: `ping` (sin warnings de seguridad)

6. **NO CERRAR** la ventana negra. Debe seguir corriendo mientras uses el POS.

---

## Paso 6: Configurar Odoo POS

Abrir tu Odoo en el navegador (ej: https://tudominio.com) e iniciar sesion
como administrador.

> **IMPORTANTE — leer antes de configurar**: En Odoo 19 los recibos de venta
> y los pedidos de cocina viajan por DOS rutas distintas que se configuran en
> lugares diferentes. Hay que activar AMBAS para que todo funcione:
>
> - **Recibos de venta** se configuran en la seccion "IoT Box" de los Ajustes del POS
> - **Pedidos de cocina** se configuran en "Impresoras de preparacion" (otro menu)
>
> Si solo configuras una, solo funcionara una. Es el error mas comun.

### 6A. Configurar la impresion de RECIBOS de venta

1. Ir a **Punto de Venta > Configuracion > Ajustes** (NO "Puntos de Venta")
2. Si tienes mas de un POS, seleccionar el correcto en el dropdown
3. Bajar a la seccion **"Connected Devices"**
4. Activar el checkbox **"IoT Box"**
5. En **"IoT Box IP Address"** escribir: `localhost:8072`
6. Activar el checkbox **"Receipt Printer"** (CRITICO — esto es lo que activa el envio del recibo al proxy)
7. Subir a la seccion **"Receipts"**
8. Activar **"Automatic Receipt Printing"** (para imprimir sin previsualizacion)
9. Verificar **"Skip Preview Screen"** activado
10. Click en **Guardar**

### 6B. Configurar impresora de COCINA (opcional)

Si tu tienda tiene cocina:

1. Ir a **Punto de Venta > Configuracion > Impresoras de preparacion**
2. Click en **"Nuevo"**
3. Llenar:
   - **Nombre**: Cocina
   - **Tipo de impresora**: "Usar una impresora conectada al IoT Box"
   - **Direccion del IoT Box**: `localhost:8072` (la misma — la misma impresora puede servir para ambos)
   - **Categorias de productos**: Seleccionar las de comida/bebida
4. Click en **Guardar**

### 6C. Cerrar y reabrir la sesion del POS

Despues de cualquier cambio, cerrar la sesion abierta y volver a abrirla.
Los flags se cargan al inicio.

---

## Paso 7: Probar

1. Verificar que la ventana negra del proxy sigue corriendo
2. Abrir el POS en el navegador (`https://tudominio.com`)
3. El icono de conexion debe estar en VERDE
4. Crear una venta y cobrar
5. El ticket debe imprimirse automaticamente

Si no funciona, ver "Solucion de problemas" mas abajo.

---

# PASOS OPCIONALES

---

## Opcional 1: Inicio automatico con Windows

Para que el proxy inicie solo al encender la PC:

### Metodo facil (acceso directo):

1. Presionar `Win + R`, escribir `shell:startup` y Enter
2. Click derecho en espacio vacio > **Nuevo > Acceso directo**
3. Ubicacion: `C:\pos_print_proxy\start_proxy.bat`
4. Siguiente, nombre "POS Print Proxy", Finalizar

### Metodo avanzado (servicio Windows con NSSM):

Mas robusto, no se cierra si alguien cierra la ventana. Requiere NSSM
(https://nssm.cc/download).

```
nssm install POSPrintProxy "C:\Python312\python.exe" "C:\pos_print_proxy\main.py"
nssm set POSPrintProxy AppDirectory "C:\pos_print_proxy"
nssm start POSPrintProxy
```

---

## Opcional 2: Segunda impresora para cocina

Si tu tienda tiene impresora separada fisicamente para cocina:

1. Conectar la segunda impresora e instalar driver
2. Anotar nombre Windows (ej: "KITCHEN-80")
3. Editar `config.yaml` y descomentar:
   ```yaml
   kitchen_printer_name: "KITCHEN-80"
   kitchen_port: 8073
   ```
4. Reiniciar el proxy
5. En Odoo, cambiar direccion de cocina a: `localhost:8073`

---

## Opcional 3: Ver impresoras detectadas

`https://localhost:8072/printers` en el navegador

Mostrara algo como:
```
{"printers": ["POS-80", "Microsoft Print to PDF"], "configured": "POS-80"}
```

---

# SOLUCION DE PROBLEMAS

---

## Problema: "Mixed Content" blocked / "CORS error" en DevTools

**Sintoma**: En DevTools (F12) > Network filtrando `hw_proxy`, peticiones a
`hello` fallan con "CORS error" o "blocked by client". Aparece "provisional
request headers" sin "response headers".

**Causa**: El proxy esta corriendo en HTTP pero Odoo en HTTPS, o no se
ejecuto el setup de HTTPS.

**Solucion**:
1. Verificar que existen los archivos `localhost.pem` y `localhost-key.pem`
   en la carpeta del proxy
2. Si NO existen: ejecutar `setup_https.bat` como administrador (Paso 4)
3. Si SI existen: verificar el log de inicio del proxy — debe decir
   "Modo: HTTPS (recomendado)". Si dice "HTTP (legacy)", reiniciar el proxy.
4. En Odoo, la direccion debe ser solo `localhost:8072` (sin `http://` ni `https://`)
5. Recargar el POS con `Ctrl+Shift+R` (recarga forzada)
6. En DevTools > Network deberia ver:
   - `OPTIONS https://localhost:8072/hw_proxy/hello` -> 204
   - `GET https://localhost:8072/hw_proxy/hello` -> 200 con texto "ping"

---

## Problema: Warning de certificado en `https://localhost:8072`

**Sintoma**: Al visitar `https://localhost:8072/hw_proxy/hello` en el navegador
aparece "Tu conexion no es privada" / "NET::ERR_CERT_AUTHORITY_INVALID".

**Causa**: La CA local no se instalo correctamente en Windows.

**Solucion**:
1. Volver a ejecutar `setup_https.bat` como administrador
2. Cuando aparezca la ventana de Windows pidiendo confirmar instalar el cert,
   asegurarse de hacer click en "Si"
3. Cerrar TODAS las ventanas de Chrome/Edge y volver a abrir
4. Probar de nuevo

---

## Problema: La cocina imprime bien pero los recibos NO

**Sintoma**: Al hacer pedidos con items de cocina la comanda sale, pero al
cerrar la venta el recibo no se imprime, o aparece la ventana de impresion
del navegador.

**Causa**: En Odoo 19 los recibos y la cocina viajan por dos rutas distintas
y se configuran en lugares diferentes. La casilla de "tickets" dentro de
"Impresoras de preparacion" NO sirve para el recibo.

**Solucion**: Revisar el Paso 6A:
1. **Punto de Venta > Configuracion > Ajustes**
2. **"Connected Devices"** > activar **IoT Box** + IP `localhost:8072` + activar **Receipt Printer**
3. **"Receipts"** > activar **Automatic Receipt Printing**
4. Guardar y cerrar/reabrir la sesion POS

**Verificacion tecnica**: Abrir DevTools (F12) > Network > filtrar `hw_proxy`.
Al abrir el POS deberian aparecer:
- Peticiones a `hello`, `handshake` (al inicio)
- `status_json` cada 5 segundos (mantenimiento de conexion)

Si solo ves `default_printer_action` (cocina), falta activar `is_posbox` y
`iface_print_via_proxy` en Odoo (= "IoT Box" + "Receipt Printer" en la UI).

---

## Problema: El POS muestra el icono de conexion en rojo/gris

**Causa**: El navegador no puede comunicarse con el proxy.

**Soluciones**:
1. Verificar que la ventana CMD del proxy esta corriendo
2. Abrir `https://localhost:8072/hw_proxy/hello` directamente. Si no carga,
   el proxy no esta corriendo
3. Verificar el config.yaml: `odoo_domain` debe coincidir EXACTAMENTE con la
   barra del navegador (sin barra final)
4. En Chrome `chrome://flags`, verificar que "Block insecure private network
   requests" no este "Enabled" (debe estar "Default" o "Disabled")

---

## Problema: El proxy inicia pero dice "ATENCION: impresora no encontrada"

**Causa**: El nombre en config.yaml no coincide con Windows.

**Solucion**:
1. CMD (Win + R > cmd > Enter):
   ```
   python -c "import win32print; print([p[2] for p in win32print.EnumPrinters(2)])"
   ```
2. Copiar el nombre EXACTO al config.yaml
3. Reiniciar el proxy

---

## Problema: El ticket no se imprime (icono verde)

**Soluciones**:
1. Verificar impresora encendida, con papel
2. Revisar la ventana CMD del proxy: debe aparecer "Recibido trabajo de impresion"
   - Si no aparece: el POS no esta enviando (revisar configuracion Odoo)
   - Si aparece pero hay error rojo: la impresora no esta respondiendo
3. Probar imprimir pagina de prueba desde Windows (Configuracion > Impresoras)

---

## Problema: La impresora imprime simbolos raros

**Causa**: Driver incorrecto.

**Solucion**:
1. Driver debe ser POS generico del fabricante o "Generic / Text Only"
2. NO usar drivers PCL/PostScript de impresoras de oficina
3. Reinstalar driver desde el sitio del fabricante

---

## Problema: setup_https.bat falla descargando mkcert

**Causa**: Sin internet, o firewall corporativo bloqueando GitHub.

**Solucion manual**:
1. En otra PC con internet, ir a https://github.com/FiloSottile/mkcert/releases/latest
2. Descargar `mkcert-vX.X.X-windows-amd64.exe`
3. Renombrar a `mkcert.exe`
4. Copiarlo a la carpeta `pos_print_proxy`
5. Volver a ejecutar `setup_https.bat` como admin

---

## Problema: "python no se reconoce como comando"

**Solucion**:
1. Desinstalar Python (Configuracion > Aplicaciones)
2. Reinstalar marcando **"Add python.exe to PATH"**
3. Reiniciar la PC

---

## Problema: Error de CORS en consola del navegador

**Solucion**: Verificar `odoo_domain` en config.yaml:
- Debe incluir `https://`
- NO debe tener barra final
- Debe coincidir con la barra del navegador

---

# EXPLICACION TECNICA

Esta seccion es para entender como funciona internamente. No necesaria para usarlo.

---

## Arquitectura general

```
                INTERNET                          RED LOCAL (tienda)
                   |                                       |
+------------------+------------------+      +-------------+-------------+
|   VPS                               |      |   PC Windows 11           |
|                                     |      |                           |
|   Odoo 19 CE                        |      |   Navegador (Chrome/Edge) |
|   - https://tudominio.com           |<---->|   - Sesion POS abierta    |
|   - DB, ORM, modulos POS            |      |        |                  |
|   - Renderizado de recibos en HTML  |      |        | HTTPS local      |
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

## Por que HTTPS local

Cuando una pagina HTTPS (`https://tudominio.com`) intenta hacer fetch a un
servicio HTTP (`http://localhost:8072`), los navegadores Chrome y Edge lo
bloquean por dos razones:

1. **Mixed Content**: una pagina segura no puede pedir recursos inseguros
2. **Private Network Access (PNA)**: una pagina publica que accede a red
   privada/loopback necesita preflight OPTIONS con headers especiales

La solucion es servir el proxy en HTTPS con un certificado en el que el
navegador confie. Para esto usamos `mkcert`:
- Crea una "CA local" (autoridad de certificacion privada de tu PC)
- La instala en el almacen de certificados de confianza de Windows
- Genera certificados firmados por esa CA para `localhost`
- Los navegadores aceptan el certificado sin warnings

## Compatibilidad con modo offline del POS

Esta es la principal razon de elegir HTTPS local en vez de un tunel via VPS:

- El proxy corre en la MISMA PC que el navegador
- Aunque se caiga internet, el browser sigue pudiendo llamar a localhost
- El POS de Odoo cachea la sesion en IndexedDB
- Las ventas continuan, los recibos siguen imprimiendose
- Cuando regresa internet, las ventas se sincronizan al servidor

Cualquier arquitectura que requiera salir a internet para imprimir un ticket
romperia esta capacidad offline. Por eso se descartaron tunel inverso y
WebSocket outbound.

## Las dos rutas de impresion en Odoo POS

Odoo 19 imprime recibos y cocina por rutas DISTINTAS:

| Aspecto | Recibos | Cocina |
|---------|---------|--------|
| Modelo backend | `pos.config` (un solo IoT Box global) | `pos.printer` records |
| Driver frontend | `hardware_proxy.printer` (instancia unica) | `pos_store.unwatched.printers[]` |
| Trigger | `printReceipt()` al cerrar orden | `sendOrderInPreparation()` al modificar |
| Activacion | `is_posbox + iface_print_via_proxy + proxy_ip` en pos.config | Cada `pos.printer` con su `proxy_ip` |
| UI Odoo | Ajustes > Connected Devices > IoT Box | Configuracion > Impresoras de preparacion |

## Protocolo de comunicacion

El POS habla **JSON-RPC 2.0** (excepto `/hello` que es texto plano):

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "id": 1,
  "params": {
    "data": {
      "action": "print_receipt",
      "receipt": "<base64_de_la_imagen>"
    }
  }
}
```

## Que es ESC/POS

ESC/POS es un lenguaje de comandos creado por Epson que se convirtio en
estandar de facto. La gran mayoria de impresoras termicas lo soportan,
sin importar marca.

## Archivos del programa

| Archivo | Que hace |
|---------|----------|
| `main.py` | Servidor con 4 endpoints que imitan al IoT Box. Detecta certs HTTPS automaticamente |
| `printer_backend.py` | Convierte imagenes a comandos ESC/POS y los envia a la impresora |
| `config.yaml` | Configuracion de la tienda |
| `requirements.txt` | Dependencias Python |
| `start_proxy.bat` | Script para iniciar con doble click |
| `setup_https.bat` | Instala CA local y genera certs HTTPS (ejecutar UNA VEZ como admin) |
| `localhost.pem` + `localhost-key.pem` | Certificados generados por setup_https.bat |
| `mkcert.exe` | Herramienta para certificados (descargada por setup_https.bat) |

## Tecnologias utilizadas

| Tecnologia | Para que se usa |
|------------|-----------------|
| **Python** | Lenguaje del proxy |
| **FastAPI** | Framework web para los endpoints HTTP |
| **Uvicorn** | Servidor ASGI con soporte SSL |
| **Pillow** | Procesamiento de imagenes |
| **pywin32** | Acceso al sistema de impresion de Windows |
| **PyYAML** | Lectura de config.yaml |
| **mkcert** | Generacion de certificados HTTPS de confianza local |

## Puertos utilizados

| Puerto | Quien lo usa | Para que |
|--------|-------------|----------|
| 8072 | POS Print Proxy | Recibir trabajos de impresion (HTTPS) |
| 8073 | POS Print Proxy (opcional) | Segunda impresora si la hay |
| 443 | Odoo (VPS) | Conexion HTTPS al sistema Odoo |
