{
    "name": "POS Offline Print Safe",
    "version": "19.0.1.0.0",
    "summary": "Garantiza impresion del ticket cuando el sync al servidor falla",
    "description": """
        Parchea OrderPaymentValidation.handleValidationError para tratar
        RPCError como ConnectionLostError en el flujo de impresion.

        Contexto del bug (Odoo 19 CE):
            En order_payment_validation.js:223-234, cuando syncAllOrders
            devuelve ConnectionLostError el POS imprime el ticket igual.
            Pero cuando el error es RPCError (respuesta 4xx/5xx del
            servidor, sesion expirada, DNS transiente, timeout de red,
            etc.), la orden vuelve a state='draft' y NO se imprime.

        En produccion los cortes de internet raramente son limpios; suelen
        ser conexiones degradadas que producen RPCError. Resultado: el
        cajero cobra pero no puede entregar el ticket, y la orden queda
        medio muerta en draft.

        Fix:
            Tratar RPCError y ConnectionLostError por igual en el flujo
            de impresion. La orden se queda en 'paid' (que es lo real: el
            cajero ya cobro), se imprime el ticket, y el sync se
            reintenta despues via la cola unsyncData que Odoo ya tiene.

        Trade-off:
            Si el RPCError venia de un problema genuino (producto
            eliminado, precio cambiado), la orden persistira en 'paid'
            sin sync y requiere revision manual en el backoffice. En la
            practica esto es raro y es un downside aceptable frente al
            problema real que causa perdida de ventas.
    """,
    "author": "Humberto Zapata",
    "website": "https://github.com/bertohzapata/odoo_pos_print_proxy",
    "category": "Sales/Point of Sale",
    "license": "LGPL-3",
    "depends": ["point_of_sale"],
    "data": [],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_offline_print_safe/static/src/overrides/order_payment_validation.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
