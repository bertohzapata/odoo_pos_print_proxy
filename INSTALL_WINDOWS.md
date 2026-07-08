# POS Print Proxy - Instalacion en Windows (v2.0)

Guia para instalar POS Print Proxy 2.0 desde el installer `.exe`. Para
actualizaciones desde v1.x, ver la seccion "Migrar desde v1.x" al final.

## Requisitos

- **Windows 10 o Windows 11** (x64)
- Un usuario con permisos de instalacion (no requiere admin para instalar
  en AppData; si eliges Program Files, Windows pedira confirmacion UAC)
- Impresora termica USB reconocida por Windows (driver Generic/Text Only o
  el del fabricante)
- Navegador Chrome o Edge para el POS de Odoo

## Paso 1: Descargar el installer

1. Ir a [Releases del proyecto](https://github.com/bertohzapata/odoo_pos_print_proxy/releases/latest)
2. Descargar `POSPrintProxySetup-<version>.exe`
3. Si Windows SmartScreen bloquea: **Mas informacion** > **Ejecutar de todos modos**
   (el ejecutable no esta firmado por ahora; una firma de codigo esta en el roadmap)

## Paso 2: Ejecutar el installer

1. Doble click en el `.exe`
2. Elegir idioma (Espanol o English)
3. Aceptar el destino sugerido (`C:\Program Files\POSPrintProxy\`) o cambiarlo
4. En la pantalla de **Tareas adicionales** marcar segun preferencia:
   - **Crear acceso directo en el escritorio** (opcional)
   - **Iniciar POS Print Proxy al iniciar sesion** (recomendado para operacion diaria)
5. Click en **Instalar**
6. Al terminar, dejar marcado **Iniciar POS Print Proxy ahora** y click en **Finalizar**

Si detecta una version previa (v1.x o v2.x anterior), te preguntara
si desinstalarla antes. **La configuracion y los certificados HTTPS se
conservan siempre** en `%APPDATA%\POSPrintProxy\`.

## Paso 3: Configuracion inicial desde la GUI

La ventana principal se abre en el **Dashboard**. Sigue estos pasos en orden:

### 3.1 Vista **Certificado**

1. Click en **Certificado** en el sidebar
2. Si el estado dice "No instalado" (primera vez), click en **Renovar ahora**
3. Aparecera una ventana de UAC pidiendo permiso para instalar la CA local
   en el almacen de certificados de Windows. Aceptar
4. Despues de 5-15 segundos veras "Certificado renovado con exito"
5. El estado ahora dira "Valido" con fecha de expiracion

### 3.2 Vista **Impresoras**

1. Click en **Impresoras** en el sidebar
2. En **Dominio Odoo permitido**, escribir la URL exacta de tu Odoo:
   `https://tudominio.com` (sin barra final, sin path)
3. Click en **Guardar dominio**
4. En la tabla veras la impresora "Caja" por defecto (puerto 8072, driver "POS-80")
5. Click en la fila y luego **Editar** para ajustar el nombre real de tu impresora
   Windows (el dropdown lista todas las que Windows detecta)
6. Si necesitas una segunda impresora para cocina/bar, click en **Agregar impresora**
7. Los cambios se guardan en tiempo real

### 3.3 Dashboard

1. Volver a **Dashboard**
2. Click en el boton grande **Iniciar**
3. El indicador debe cambiar a verde con el texto "En ejecucion" y los puertos activos

### 3.4 Validar desde el navegador

1. En Chrome/Edge (mismo equipo), visitar: `https://localhost:8072/hw_proxy/hello`
2. Debe mostrar `ping` sin advertencias de seguridad (candado verde)

## Paso 4: Configurar Odoo POS

> **IMPORTANTE — leer antes de configurar**: En Odoo 19 los recibos de venta
> y los pedidos de cocina viajan por DOS rutas distintas que se configuran en
> lugares diferentes. Hay que activar AMBAS para que todo funcione:
>
> - **Recibos de venta**: seccion "IoT Box" de los Ajustes del POS
> - **Pedidos de cocina**: "Impresoras de preparacion" (otro menu)

### 4.1 Impresora de recibos

1. Ir a **Punto de Venta > Configuracion > Ajustes** (NO "Puntos de Venta")
2. Seleccionar el POS correcto si tienes varios
3. Bajar a **Connected Devices**
4. Activar **IoT Box** con IP: `localhost:8072`
5. Activar **Receipt Printer**
6. Subir a **Receipts** y activar **Automatic Receipt Printing**
7. Guardar

### 4.2 Impresoras de preparacion (opcional)

1. Ir a **Punto de Venta > Configuracion > Impresoras de preparacion**
2. Crear una impresora por cada rol (cocina, bar):
   - **Tipo**: "Usar una impresora conectada al IoT Box"
   - **Direccion del IoT Box**: `localhost:8073` (o el puerto que hayas configurado)
   - **Categorias de productos**: las que aplican

### 4.3 Cerrar y reabrir sesion POS

Los cambios en Ajustes se cargan al abrir sesion. Cerrar la sesion actual
y volver a entrar.

## Paso 5: Usar la app

- Al terminar el paso 4, la impresion funciona sola. Al cerrar una venta
  el ticket sale directo. Al enviar a cocina, la comanda sale directo.
- La GUI del proxy se puede cerrar con la X: se minimiza a la bandeja y
  el daemon sigue corriendo
- Para volver a abrirla, click en el icono de la bandeja (esquina inferior
  derecha) o click derecho > **Abrir dashboard**
- Para salir realmente, click derecho en el icono de la bandeja > **Salir**

## Actualizaciones

La app consulta GitHub Releases una vez al dia. Si aparece una version
nueva:

1. Notificacion en la bandeja del sistema
2. En el icono de la bandeja, click derecho > "Actualizar a vX.Y.Z"
3. Se abre la vista Sistema con detalles y boton "Abrir release"
4. Descargar el nuevo `.exe` y ejecutar como el paso 2 de arriba
5. El installer detecta la version previa y la desinstala automaticamente,
   preservando tu configuracion y certificados

## Migrar desde v1.x

Si tienes v1.x instalada (con `main.py`, `config.yaml` editado a mano,
`start_proxy.bat` en el escritorio, etc.):

1. Descargar el installer v2.0 y ejecutarlo. Detectara la carpeta v1.x
   por su AppId y ofrecera migrarla
2. Antes de aceptar, si tenias tu `config.yaml` en una ruta custom, copialo
   a `%APPDATA%\POSPrintProxy\config.yaml` para que v2.0 lo detecte
3. Los certificados en la carpeta v1.x (`localhost.pem`, `localhost-key.pem`)
   NO se migran automaticamente. Al arrancar v2.0, ir a la vista Certificado
   y click en **Renovar ahora** para generar unos nuevos en la ubicacion nueva
4. La CA mkcert previamente instalada en Windows sigue siendo valida y no
   necesita reinstalarse
5. Verificar que el POS reconecte tras el upgrade

## Estructura de archivos tras la instalacion

```
C:\Program Files\POSPrintProxy\         (o carpeta elegida)
├── POSPrintProxy.exe                   ← el ejecutable
├── bin\mkcert.exe                      ← herramienta de certificados
├── config.yaml.default                 ← plantilla inicial
├── posprintproxy\theme.qss             ← estilos GUI
└── _internal\                          ← runtime Python + libs

%APPDATA%\POSPrintProxy\                (perfil del usuario)
├── config.yaml                         ← configuracion editable desde la GUI
├── certs\
│   ├── localhost.pem
│   ├── localhost-key.pem
│   └── mkcert.exe                      ← copia local (opcional)
└── logs\
    └── proxy.log                       ← rotado a diario, retencion 30 dias
```

## Solucion de problemas

Antes de nada: abrir la vista **Logs** de la GUI para ver los mensajes en
vivo. Si el problema requiere reiniciar el daemon, la GUI tiene el boton
Reiniciar en el dashboard.

### El dashboard esta en gris/rojo despues de "Iniciar"

- Ver la vista **Logs**: buscar lineas ERROR o WARNING
- Causa mas comun: no hay certificado HTTPS. Ir a **Certificado** > **Renovar ahora**
- Segunda causa: puerto ocupado. La app mata zombies automaticamente al
  iniciar, pero si tienes un netstat con `LISTENING` en el puerto de otra
  app, reasignalo desde **Impresoras** > **Editar**

### El POS no ve el proxy en el navegador

Ver `README.md` seccion "Solucion de problemas" - los pasos son los mismos
que en v1.x. Los mas comunes:

1. **`is_posbox` y `iface_print_via_proxy` no activos en Odoo** (ver paso 4.1)
2. **Cert no confiable**: abrir `https://localhost:8072/hw_proxy/hello` directo
   en el navegador; si el candado esta rojo, renovar el cert desde la GUI
3. **Cache del navegador**: `Ctrl+Shift+R` para recarga forzada
4. **`use_lna=1` residual en Odoo**: con HTTPS local no se usa. Ver el
   parametro del sistema `point_of_sale.use_lna` y ponerlo en 0 o borrarlo

### Error "El certificado HTTPS existe pero NO es valido"

- Ir a **Certificado** > **Renovar ahora**
- Si sigue fallando, borrar `%APPDATA%\POSPrintProxy\certs\` y volver a
  renovar (obliga a regenerar la CA)

### La app no arranca despues del installer

- Verificar que Windows Defender no haya bloqueado el `.exe`
- Abrir `%APPDATA%\POSPrintProxy\logs\proxy.log` con el Bloc de notas
- Reinstalar seleccionando otra carpeta (evitar caracteres especiales
  en la ruta)

### Auto-inicio no funciona

- La vista **Sistema** tiene un checkbox "Iniciar POS Print Proxy al iniciar
  sesion". Toggle off y on de nuevo
- Verificar en `regedit` que existe la clave:
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\POSPrintProxy`

## Documentos relacionados

- [README.md](README.md) - vista general y arquitectura
- [ESPECIFICACIONES.md](ESPECIFICACIONES.md) - decisiones tecnicas
- [HITOS.md](HITOS.md) - historial de versiones
- [TESTS.md](TESTS.md) - suite de pruebas manuales
