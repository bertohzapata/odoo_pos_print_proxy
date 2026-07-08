# Tests End-to-End — POS Print Proxy

> Checklist manual para validar cada release. Ejecutar en Windows con una
> impresora termica conectada y una sesion POS de Odoo abierta.

## Preparacion previa (una sola vez por equipo)

- [ ] Python 3.11+ instalado (verificar con `python --version`)
- [ ] Carpeta `pos_print_proxy` copiada al equipo
- [ ] `config.yaml` editado con `odoo_domain` y `printer_name` correctos
- [ ] `setup_https.bat` ejecutado como administrador (genera `localhost.pem`)
- [ ] En Odoo: `is_posbox` + `iface_print_via_proxy` activos + `proxy_ip` = `localhost:8072`
- [ ] En Odoo: `iface_print_auto` + `iface_print_skip_screen` activos
- [ ] Parametro del sistema `point_of_sale.use_lna` NO existe o esta en `0`

---

## Test A — Arranque limpio del proxy

**Objetivo**: verificar que `start_proxy.bat` deja el sistema en estado funcional.

Pasos:
1. Cerrar cualquier ventana CMD previa del proxy
2. Doble click en `start_proxy.bat`

Verificar en el log de arranque:

- [ ] Aparece `POS Print Proxy v1.4.0` (o superior)
- [ ] Aparece `Modo: HTTPS (correcto)` (NO `HTTP (INCORRECTO)`)
- [ ] Aparece `Dominio Odoo permitido: <tu dominio>`
- [ ] Aparece `Impresoras configuradas: N` (N = numero de impresoras en config.yaml)
- [ ] Aparece linea `Impresora 'X' escuchando en https://localhost:807X` por cada impresora
- [ ] NO aparece `ATENCION: certificado HTTPS invalido`
- [ ] NO aparece `ATENCION: 'X' no esta en la lista de impresoras de Windows`
- [ ] Aparece `Todas las impresoras listas. Presiona Ctrl+C para detener.`

En otra CMD:
- [ ] `netstat -ano | findstr ":8072 "` muestra UN solo PID escuchando

Verificar archivo:
- [ ] Existe la carpeta `logs/` con `proxy.log` dentro
- [ ] `proxy.log` tiene el mismo banner que la consola

---

## Test B — Endpoint `/hello` responde

**Objetivo**: proxy alcanzable via HTTPS local sin warnings.

Pasos:
1. Abrir en el navegador del POS (Chrome/Edge): `https://localhost:8072/hw_proxy/hello`

Verificar:
- [ ] Muestra el texto `ping`
- [ ] La barra de direcciones muestra el candado sin tachar (cert valido)
- [ ] Click en el candado > "Conexion es segura" > cert emitido por `mkcert development CA`

Test bypass CLI:
- [ ] `curl.exe -k https://localhost:8072/hw_proxy/hello` retorna `ping`

Si hay multi-impresora, repetir para cada puerto (8073, 8074, etc.).

---

## Test C — Handshake y keep-alive desde el POS

**Objetivo**: el POS de Odoo establece conexion con el proxy correctamente.

Pasos:
1. Abrir el POS en el navegador (`https://tudominio.com/pos/ui`)
2. F12 > pestana Network > filtrar por `hw_proxy` > marcar "Preserve log"
3. Ctrl+Shift+R para recargar sin cache

Verificar en Network:
- [ ] `OPTIONS /hw_proxy/hello` -> 204
- [ ] `GET /hw_proxy/hello` -> 200 con body `ping`
- [ ] `OPTIONS /hw_proxy/handshake` -> 204
- [ ] `POST /hw_proxy/handshake` -> 200 con JSON-RPC `result: true`
- [ ] `POST /hw_proxy/status_json` -> 200, se repite cada ~5 segundos

Verificar en el log del proxy:
- [ ] Aparece `[<nombre>] POS conectado (handshake OK)`
- [ ] NO aparecen lineas `[ERROR]`
- [ ] NO aparecen lineas `Origen no permitido`

---

## Test D — Impresion de recibo

**Objetivo**: al cerrar una venta, el ticket sale sin previsualizacion.

Pasos:
1. En el POS, crear una orden con UN producto SIN categoria de cocina
2. Cobrar y confirmar la orden

Verificar:
- [ ] El ticket sale por la impresora termica
- [ ] NO aparece la pantalla de previsualizacion del navegador
- [ ] NO aparece el dialog nativo de Chrome ("Imprimir")

Verificar en log del proxy:
- [ ] Aparece `[<nombre>] Impreso (N bytes) -> '<windows_printer>'`
- [ ] Aparece esa linea en `logs/proxy.log` tambien

---

## Test E — Impresion de comanda a cocina

**Objetivo**: en tienda con multi-impresora, la cocina se imprime en su
puerto separado.

Requiere: config.yaml con al menos 2 impresoras (nueva o legacy con
`kitchen_printer_name`), y en Odoo una impresora de preparacion apuntando
a `localhost:8073` con categorias de comida asociadas.

Pasos:
1. Crear una orden con UN producto de categoria de cocina
2. Enviar el pedido a preparacion (boton "Enviar" o cerrar orden)

Verificar:
- [ ] La comanda sale en la impresora de cocina (no en la de recibos)
- [ ] En el log del proxy aparece `[Cocina] Impreso ...` (nombre de la impresora de cocina)
- [ ] En Network del navegador aparece `POST https://localhost:8073/hw_proxy/default_printer_action`

---

## Test F — Apertura de cajon de dinero

Requiere: cajon conectado fisicamente a la impresora y `iface_cashdrawer`
activado en Ajustes POS > Connected Devices.

Pasos:
1. Cobrar una venta en efectivo

Verificar:
- [ ] El cajon se abre
- [ ] En el log: `[<nombre>] Cajon abierto -> '<windows_printer>'`

---

## Test G — Modo offline

**Objetivo**: verificar que la impresion NO depende de internet.

Pasos:
1. Con el POS abierto y conectado, desconectar internet del equipo
   (WiFi off o cable desenchufado)
2. Verificar que el POS entra en modo offline (indicador en la UI)
3. Cobrar una venta en efectivo

Verificar:
- [ ] El ticket sale por la impresora
- [ ] En el log del proxy aparece `[<nombre>] Impreso ...`
- [ ] La orden queda pendiente de sincronizar en el POS

Reconectar internet:
- [ ] La orden se sincroniza al servidor sin errores

---

## Test H — Recuperacion de zombies

**Objetivo**: si un proceso anterior quedo escuchando en el puerto, el
proxy nuevo debe matarlo y arrancar limpio.

Pasos:
1. Con el proxy arriba, cerrar la ventana CMD con la X (NO Ctrl+C)
2. Verificar que el proceso Python quedo huerfano:
   `netstat -ano | findstr ":8072 "` -> muestra un PID LISTENING
3. Doble click en `start_proxy.bat`

Verificar:
- [ ] En el log de arranque aparece `Puerto 8072: matando N zombie(s) PID=...`
- [ ] Despues del arranque, `netstat -ano | findstr ":8072 "` muestra UN solo PID
  (el nuevo, no el zombie)

---

## Test I — Config legacy sigue funcionando (retrocompat)

**Objetivo**: usuarios con config.yaml del formato v1.3 no tienen que migrar.

Pasos:
1. En un config.yaml, tener SOLO campos legacy en el top-level:
   ```yaml
   odoo_domain: "https://tudominio.com"
   port: 8072
   printer_name: "POS-80"
   paper_width: 576
   ```
2. Arrancar el proxy

Verificar:
- [ ] Arranca sin errores
- [ ] Log muestra `Impresoras configuradas: 1`
- [ ] Los tests A-G pasan igual que con formato nuevo

Si el legacy tenia `kitchen_printer_name`:
- [ ] Log muestra `Impresoras configuradas: 2`
- [ ] Ambos puertos escuchan

---

## Test J — Multi-impresora en paralelo

**Objetivo**: con >= 2 impresoras configuradas, todas responden simultaneamente.

Requiere: config.yaml con formato nuevo y 2+ impresoras.

Pasos:
1. Arrancar el proxy
2. En 2 pestanas del navegador, abrir cada puerto:
   - `https://localhost:8072/hw_proxy/hello`
   - `https://localhost:8073/hw_proxy/hello`

Verificar:
- [ ] Ambas muestran `ping`
- [ ] `netstat -ano | findstr ":807"` muestra 2 procesos distintos (o el mismo PID escuchando en 2 puertos si estamos en un solo proceso con multiple servers)

Actualmente los servidores corren en el mismo proceso Python (asyncio.gather), asi
que debe haber UN solo PID con 2+ puertos LISTENING.

---

## Test K — Logs a archivo persisten

**Objetivo**: aunque la CMD se cierre, los eventos quedan registrados.

Pasos:
1. Arrancar el proxy, hacer una impresion, cerrar la CMD
2. Abrir `logs/proxy.log` con Bloc de Notas

Verificar:
- [ ] Contiene el banner de arranque
- [ ] Contiene `POS conectado (handshake OK)`
- [ ] Contiene `Impreso ... -> ...`
- [ ] Timestamps con fecha completa (formato `YYYY-MM-DD HH:MM:SS`)

Al pasar 24h+, verificar rotacion:
- [ ] Aparece un archivo `proxy.log.YYYY-MM-DD` con los logs del dia anterior
- [ ] `proxy.log` queda con los logs del dia actual

---

## Registro de ejecucion

Al ejecutar esta suite en una release nueva, dejar en HITOS.md:
- Fecha de ejecucion
- Version testeada
- Equipo (Win10 / Win11 / build)
- Tests que pasaron y fallaron
- Bugs descubiertos con link a issue si aplica
