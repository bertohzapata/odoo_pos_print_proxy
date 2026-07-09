# POS Offline Print Safe

Modulo Odoo 19 CE que garantiza que el ticket de venta se imprima aunque
el sync al servidor falle por conexion degradada (WiFi intermitente,
servidor lento, sesion expirada, DNS transiente).

## El problema que arregla

Odoo 19 POS trata dos tipos de error de sync de forma opuesta:

| Error del sync | Comportamiento base de Odoo |
|---|---|
| `ConnectionLostError` (sin red) | Imprime el ticket, marca orden `paid` |
| `RPCError` (servidor responde error) | Vuelve orden a `draft`, **no imprime** |

En produccion los cortes de internet raramente son limpios. Casi siempre
son conexiones degradadas que producen `RPCError`. Resultado: el cajero
cobra el efectivo (o marca "tarjeta"), pero el ticket **no sale por la
impresora** y la orden queda en estado `draft` a medio hacer.

Referencia al codigo original:
`addons/point_of_sale/static/src/app/utils/order_payment_validation.js:223-234`

## Que hace este modulo

Un patch de 20 lineas a `OrderPaymentValidation.handleValidationError`
que trata `RPCError` igual que `ConnectionLostError` para el flujo de
impresion:

- La orden se queda en `paid` (la realidad: el cajero ya cobro)
- El ticket se imprime
- El dialogo de error del sync se sigue mostrando (no se oculta info)
- El sync se reintenta despues por la cola `unsyncData` que Odoo ya tiene

## Instalacion

1. Copiar la carpeta `pos_offline_print_safe/` al `addons_path` de tu Odoo:

   ```bash
   cp -r pos_offline_print_safe /path/to/odoo/custom_addons/
   ```

2. Reiniciar Odoo con `--update=pos_offline_print_safe`, o desde la UI:
   Apps > Actualizar lista de aplicaciones > buscar "POS Offline Print
   Safe" > Instalar.

3. En cada terminal del POS, recargar con `Ctrl+Shift+R` (recarga
   forzada sin cache).

No hay configuracion adicional. El fix aplica desde el momento en que
el modulo esta instalado.

## Como probar que funciona

**Test A - offline puro (baseline, ya funcionaba antes)**:
- Desconectar WiFi de la PC
- Hacer una venta > el ticket sale

**Test B - degradado (lo que este modulo arregla)**:
- Con WiFi conectado, apagar el Odoo (o bloquear el dominio en el firewall
  de la PC)
- Hacer una venta > **el ticket debe salir igual**
- Restaurar Odoo > la orden se sincroniza sin intervencion manual

## Trade-offs aceptados

- Si el `RPCError` venia de un problema genuino (producto eliminado,
  precio cambiado, permiso invalido), la orden persistira en `paid` sin
  sync y requerira revision manual en el backoffice. En la practica esto
  es raro. Es un downside aceptable frente a la perdida de ventas por
  tickets no impresos.

- El dialogo de error del `RPCError` sigue apareciendo al cajero. Es
  intencional: no queremos ocultar que hubo un problema con el sync.

## Compatibilidad

- Odoo 19 CE, EE (probable)
- No conflicta con otros modulos que patchen `OrderPaymentValidation`
  (`pos_restaurant`, `l10n_pe_pos`, etc. patchean otros metodos)

## Licencia

LGPL-3
