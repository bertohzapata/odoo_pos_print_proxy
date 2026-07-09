/**
 * Patch de OrderPaymentValidation.handleValidationError
 *
 * Bug original (order_payment_validation.js:223-234):
 *   - ConnectionLostError => imprime el ticket y sigue
 *   - RPCError            => vuelve la orden a state="draft" y NO imprime
 *
 * En produccion los cortes de internet raramente son limpios; casi siempre
 * son conexiones degradadas que producen RPCError (respuesta 4xx/5xx del
 * servidor, sesion expirada, timeout, DNS transiente). Resultado: el cajero
 * cobra pero no puede entregar el ticket, y la orden queda medio muerta.
 *
 * Fix: tratar RPCError como ConnectionLostError en el flujo de impresion.
 * La orden se queda en 'paid' (que es la realidad), se imprime el ticket,
 * y el sync se reintenta despues via la cola unsyncData de data_service.
 */

import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";
import { ConnectionLostError, RPCError } from "@web/core/network/rpc";
import { handleRPCError } from "@point_of_sale/app/utils/error_handlers";

patch(OrderPaymentValidation.prototype, {
    handleValidationError(error) {
        if (error instanceof ConnectionLostError) {
            // Caso original: sin cambio de comportamiento.
            this.afterOrderValidation();
            Promise.reject(error);
            return error;
        }

        if (error instanceof RPCError) {
            // Fix: NO revertir a draft. Imprimir el ticket igual.
            // La orden se sincronizara despues por unsyncData.
            console.warn(
                "[pos_offline_print_safe] RPCError durante syncAllOrders. " +
                    "El ticket se imprime igual y la orden queda en 'paid' " +
                    "esperando sync posterior:",
                error
            );

            // Disparar la impresion como si fuera un ConnectionLostError.
            this.afterOrderValidation();

            // Mostrar el dialogo de error igual, para que el usuario sepa
            // que el sync fallo (no ocultamos informacion).
            handleRPCError(error, this.pos.dialog);
            return error;
        }

        // Cualquier otro tipo de error: delegar al comportamiento original
        // (que hace `throw error`).
        return super.handleValidationError(error);
    },
});
