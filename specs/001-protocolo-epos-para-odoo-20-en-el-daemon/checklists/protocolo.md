# Protocolo y arranque — Checklist: Protocolo ePOS para Odoo 20 en el daemon

**Purpose**: calidad de los requisitos del contrato ePOS y del arranque de puertos (FR-001…FR-020), para el revisor del Gate 1.
**Created**: 2026-09-25
**Feature**: `spec.md` (+ `plan.md`, `contracts/epos.md`)

**Note**: generado por `/speckit-checklist` en modo no interactivo (foco: protocolo + robustez de arranque; profundidad estándar; audiencia: revisor del gate).
**Review Ownership**: artefacto del revisor. Marca `[x]` solo cuando el revisor dé el criterio por cumplido.
**Marker Semantics**: `[x]` = requisito bien escrito, no implementación terminada.

## Completitud del contrato

- [ ] CHK001 - ¿La spec exige que el puerto acepte conexiones a `127.0.0.1` (IPv4), dirección que Odoo 20 obliga a usar, y no solo `localhost`? [Gap, Spec §FR-001, §FR-011; Plan D6]
- [ ] CHK002 - ¿Está definido el plazo que se aplica cuando la petición no trae `timeout` (botón "Test")? [Gap, Spec §FR-009]
- [ ] CHK003 - ¿Hay un requisito sobre el tamaño máximo del cuerpo y el rechazo de DTD/entidades en el documento ePOS? [Gap, Security, Spec §FR-006; Plan D3]
- [ ] CHK004 - ¿Está definido el código de error de un documento inválido con la misma precisión que `EX_BADPORT`/`EX_TIMEOUT`? [Clarity, Spec §S1]
- [ ] CHK005 - ¿Está especificada la codificación/página de códigos del texto ePOS (acentos, ñ)? [Gap, Spec §FR-004]
- [ ] CHK006 - ¿Queda claro el comportamiento de `cut` cuando el documento ya trae un `feed` (evitar papel en blanco doble)? [Clarity, Spec §FR-004]

## Claridad y medibilidad

- [ ] CHK007 - ¿"Reducirse para caber" (FR-003) especifica que se conserva la proporción y cuál es el ancho destino? [Clarity, Spec §FR-003]
- [ ] CHK008 - ¿"Responder antes de que venza el timeout" (FR-009) fija un margen medible frente al abort del navegador? [Measurability, Spec §FR-009]
- [ ] CHK009 - ¿Se sabe qué cabeceras concretas exige el acceso a red local/loopback del navegador, o se admite que es supuesto (S7)? [Ambiguity, Spec §FR-013, §S7]
- [ ] CHK010 - ¿El umbral "menos de 10 MB de RAM extra" (CE-006) define cómo y cuándo se mide (tras cuánto tiempo en reposo)? [Measurability, Spec §CE-006, §S5]

## Consistencia

- [ ] CHK011 - ¿FR-014 (aviso en panel y bandeja) es consistente con FR-016 ("ningún otro cambio de GUI")? ¿Está explícita la excepción? [Conflict, Spec §FR-014, §FR-016]
- [ ] CHK012 - ¿La representación de la lista `odoo_domain` en la GUI (FR-020) cabe dentro de la "GUI mínima" de FR-016? [Consistency, Spec §FR-016, §FR-020]
- [ ] CHK013 - ¿La tabla "Datos y configuración" y FR-015 coinciden en si el formato legacy admite `http_port`? [Consistency, Spec §FR-015]

## Escenarios de excepción y recuperación

- [ ] CHK014 - ¿Está especificado qué ocurre si el timeout vence con el trabajo ya en curso (posible ticket duplicado en el reintento)? [Gap, Exception Flow, Spec §FR-008, §FR-009]
- [ ] CHK015 - ¿Está definido el estado del daemon cuando **ningún** puerto pudo abrirse? [Gap, Spec §FR-014]
- [ ] CHK016 - ¿Está definido qué pasa si el dueño de un puerto ocupado no puede identificarse (sin permisos)? [Edge Case, Spec §FR-014, §S6]
- [ ] CHK017 - ¿Se trata el caso de un programa ajeno que escucha solo en `127.0.0.1` mientras el proxy enlaza todas las interfaces? [Edge Case, Spec §FR-014; Plan D5]
- [ ] CHK018 - ¿Se cubre la concurrencia de ePOS por HTTPS y por HTTP sobre la misma impresora (FR-010 con dos listeners)? [Coverage, Spec §FR-010, §FR-012]

## No funcionales y supuestos

- [ ] CHK019 - ¿Se documenta que el puerto HTTP sin TLS queda expuesto en la LAN (y no solo en loopback), y se acepta ese riesgo? [Gap, Security, Spec §FR-012]
- [ ] CHK020 - ¿Está justificada contra la constitución la dependencia nueva que exige el reconocimiento de procesos de S6? [Dependency, Spec §S6; Plan D4]

## Notes

- Solo el revisor marca `[x]`. Si un ítem sigue pendiente de aclaración o de corrección, se deja sin marcar.
