# Contrato ePOS — lo que consume Odoo 20

Fuente: `~/odoo20/src/addons/point_of_sale/` (citas en `spec.md` › Referencias). Todo lo que
no está aquí se ignora con log (FR-005).

## Petición

```
POST {http|https}://127.0.0.1:{port|http_port}/cgi-bin/epos/service.cgi?devid=local_printer&timeout=15000
Origin: <uno de odoo_domain>
Content-Type: text/plain;charset=UTF-8        (o ausente: no se valida, FR-002)

<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>
  <epos-print xmlns="http://www.epson-pos.com/schemas/2011/03/epos-print">
    ...hijos...
  </epos-print>
</s:Body></s:Envelope>
```

- `devid` se acepta y no se valida. `timeout` (ms) es opcional; el botón "Test" no lo envía.
  Plazo interno: `min(timeout or 15000, 60000) − 1500 ms` (plan D1).
- Límite de cuerpo: 8 MiB. Un cuerpo con `<!DOCTYPE` o `<!ENTITY` → `SchemaError` (plan D3).

## Hijos de `epos-print` (namespace por defecto, cualquier prefijo)

| Elemento | Emisor en Odoo 20 | ESC/POS |
|---|---|---|
| `<image width="W" height="H" align="center">B64</image>` | recibo/comanda (`processCanvas`) | raster `GS v 0`, centrado a `paper_width`, reducido solo si `W > paper_width` |
| `<cut type="feed"/>` | recibo/comanda, Test | avance + `GS V 0` |
| `<pulse/>` | cajón (`openCashbox`) | `ESC p 0 25 250` |
| `<feed line="N"/>` | Test | `ESC d N` |
| `<text align em ul dw dh>…&#10;</text>` | Test | `ESC a`, `ESC E`, `ESC -`, `GS !`; texto `cp437` |

Datos de `image`: `ceil(W·H/8)` bytes, bits contiguos sin relleno por fila, MSB primero,
1 = negro; el último byte parcial va alineado a la derecha. Otra longitud → `SchemaError`.

## Respuesta (siempre HTTP 200, `Content-Type: text/xml; charset=utf-8`)

```
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>
  <response xmlns="http://www.epson-pos.com/schemas/2011/03/epos-print"
            success="true" code="" status="0" battery="0"/>
</s:Body></s:Envelope>
```

| Caso | `success` | `code` |
|---|---|---|
| Entregado a la impresora | `true` | `""` (presente y vacío) |
| Red caída, USB ausente, error del spooler | `false` | `EX_BADPORT` |
| Plazo vencido (lock o envío) | `false` | `EX_TIMEOUT` |
| XML inválido, sin `epos-print`, imagen inconsistente, DTD, >8 MiB | `false` | `SchemaError` |

`status` es siempre `"0"`: el transporte no lee el estado de la impresora (fuera de alcance).
Odoo lee `querySelector("response")`: el elemento debe existir en **toda** respuesta.

## CORS

Origen en `odoo_domain` (lista, FR-020) → `Access-Control-Allow-Origin: <origen>`,
`Access-Control-Allow-Private-Network: true` y `Vary: Origin`. Otro origen en `OPTIONS` → 403.
El preflight LNA es un supuesto (S7).
