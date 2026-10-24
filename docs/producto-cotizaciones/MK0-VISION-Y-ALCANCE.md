# MK0 — Dos unidades de negocio: Construcción + Cotizaciones de Ventas

**Fecha:** 2026-10-24 · **Estado:** arquitectura de producto **DECIDIDA** en [ADR-002](ADR-002-DOS-UNIDADES-DE-NEGOCIO.md); diferenciación y viabilidad comercial **DRAFT/no validadas**.  
**Repositorio único de trabajo:** [Em3rc0d/ingepresupuestos](https://github.com/Em3rc0d/ingepresupuestos). No contactar repositorios ni autores externos. Respetar GPL-3.0-or-later y atribuciones existentes.

## 1. Corrección explícita del alcance

**DECISIÓN DE PRODUCTO: la aplicación tiene DOS unidades de negocio al mismo nivel, sin sustituirse entre sí.**

1. **Construcción (BU-01):** mantener íntegro el sistema actual de presupuestos de obra: proyectos, partidas, ACU, metrados, acero, cronogramas, informes, requerimientos y control de obra. Conservar comportamiento y datos originales.
2. **Cotizaciones de Ventas (BU-02):** nuevo módulo que cotiza productos físicos (SKU, variante, unidad), materiales medibles (largo, área, volumen, cobertura), servicios y mano de obra comercial, paquetes/ensambles y conceptos personalizados. Tendrá clientes, precios de venta y disponibilidad comercial propios.
3. **Interoperabilidad opcional:** reutilizar **lógica técnica pura** tras validación y, cuando aporte valor, incorporar una partida/ACU de Construcción como línea de venta mediante **adaptador de lectura + snapshot**; no acoplar directamente tablas ni mutar partidas. Más detalles y evidencias en [ADR-002](ADR-002-DOS-UNIDADES-DE-NEGOCIO.md).

**No confundir:** un presupuesto técnico de obra estima recursos/costos; una cotización comercial ofrece un precio bajo condiciones (cliente, vigencia, impuestos, plazos, disponibilidad, condiciones de pago). Son documentos relacionados pero NO el mismo agregado ni estados del negocio.

## 2. Tesis diferencial candidata

**Cotizaciones trazables de productos, materiales y servicios que vinculen cálculo dimensional, catálogo, disponibilidad referencial y control de cambios, sin esconder los supuestos.**

La diferenciación NO es «generar una cotización», «tener stock», «exportar PDF» ni «usar IA». Eso ya existe en soluciones establecidas:
- [Odoo: cotizaciones de ventas](https://www.odoo.com/documentation/18.0/applications/sales/sales/sales_quotations.html) y [creación con catálogo](https://www.odoo.com/documentation/18.0/applications/sales/sales/sales_quotations/create_quotations.html).
- [Alegra: cotización](https://ayuda.alegra.com/dom/crear-una-cotizacion): aclara que la cotización por sí misma NO descuenta inventario.
- [Bsale: inventario/POS](https://www.bsale.com/sheet/sistemadeinventario): la integración entre inventario y ventas es una capacidad competida.

**Hipótesis evaluable:** ahorrar retrabajo al cotizar combinaciones dimensionadas y servicios, mostrando la procedencia de cantidades, versión de tarifas, advertencia de stock y diferencias entre revisiones. No está probado que exista demanda pagadora.

## 3. Estado REAL de nuestra base

Inspección de main (2026-10-24):
- `core/database.py` tiene `proyectos`, `partidas`, `recursos`, `acu_items`, `metrados_detalle`, reglas específicas de cuadrillas/rendimientos y precios por proyecto.
- `views/metrados_view.py` contiene la planilla específica de obra.
- `core/almacen.py` calcula saldo de materiales **POR PROYECTO** a partir de `almacen_ingreso` y consumo de `parte_diario_recurso`; **NO** es un inventario comercial multi-almacén de productos/SKU con reservas.
- La aplicación actual usa PySide6 + SQLite local. No hay servicio web/multiusuario en la base.
- PR #1 contiene un cálculo aislado de cantidades de zapata/pintura, **NO** cotizaciones ni persistencia.
- PR #3 aborda estabilización y seguridad del fork, **NO** amplía el producto a cotizaciones.
- No hay evidencia en la base inspeccionada de un documento universal de cotización con cliente, versiones, líneas mixtas, márgenes, vigencia y aceptación convertido en orden.

**Evaluación de reutilización:** dos contextos delimitados **de primer nivel** (Construcción y Ventas) más utilidades compartidas mínimas. Crear tablas/clases comerciales nuevas cuando el contrato lo exija; NO renombrar `partidas`, NO reinterpretar `recursos` como SKU y NO extender `almacen_ingreso` como inventario global sin SRS. **Construcción permanece operativa por sí sola**. Ver [matriz de reutilización](ADR-002-DOS-UNIDADES-DE-NEGOCIO.md).

## 4. Dominios posibles (no equivale a implementar todo)

| Segmento | Ejemplo de combinación | Necesidad a validar |
|---|---|---|
| Distribución de pintura/materiales | galones, baldes y accesorios; cobertura/m²; transporte | cotizar por consumo, unidades de venta y stock |
| Metal/melamina/vidrio | largo×ancho×espesor, cortes, herrajes, instalación | despieces sin error y mermas definidas |
| Reformas y acabados | partidas, materiales, jornales, acabados | combinar ACU de obra con propuestas comerciales |
| Servicios TI y mantenimiento | horas, licencias, equipos, soporte | ítems mixtos, versiones, condiciones |
| Comercio mayorista | SKU, descuentos escalonados, disponibilidad | velocidad al cotizar, versiones y catálogo |

**No asumir que todos tienen el mismo comprador, costo de adquisición o criterios de validación.** Seleccionar un segmento piloto por evidencia; mantener arquitectura configurable sin desarrollar cinco verticales de una vez.

## 5. Modelo funcional recomendado

### Catálogo
`Producto` (SKU, nombre, unidad de almacenamiento, unidad de venta, costo de referencia, tarifa comercial, moneda, impuesto/clasificación, atributos/variantes, vigencia, estado); `Servicio` (unidad facturable, tarifa, costo estimado opcional); `RecursoMedible` con variables y fórmulas versionadas; `Paquete` con componentes y relaciones. Catálogo no equivale a existencias.

### Cantidades y unidades
Cada línea define `tipo`, `cantidad`, `unidad`, `metodo_calculo`, `variables`, `resultado` y `origen/regla`. Usar aritmética decimal y conversiones dimensionadas (m↔cm, m²↔cm², L↔galón según definición oficial, kg↔g). **No** convertir kg a L sin densidad documentada ni m² a litros sin ficha de cobertura.

### Inventario y disponibilidad
Separar **stock físico**, **reservado**, **disponible**, **en tránsito** y **cantidad requerida por cotización**. `disponible=físico-reservado` solo cuando existe un contrato de inventario que lo sustente. La cotización es *no vinculante con inventario*: consultar disponibilidad **no descuenta stock ni crea reservas automáticamente**. Reserva y salida requieren flujo explícito posterior. Mantener sellado de hora/fuente, almacén/ubicación y advertencias de desactualización.

### Documento comercial
`Cotización` (emisor/cliente, numeración, fechas, vigencia, moneda, lista de precios, validez, condiciones, estado); `Línea` (producto/material/servicio/paquete, descripción congelada, cantidad/unidad, precio de venta congelado, descuentos/impuestos, nota/alternativa); `Revisión` (diff y motivo); `PDF` o exportación; `Evento` de estado y autorizaciones. Cotizar NO implica facturar ni mover stock.

### Precio y rentabilidad
Diferenciar **costo** de **precio de venta**, **markup** (recargo sobre costo) de **margen** (utilidad sobre precio de venta), y precio neto de tributos. Salida de margen estimado solo si tenemos costo fiable; de otro modo mostrar `margen desconocido`. Considerar redondeo por línea y total y snapshot de impuesto aplicable a la fecha/operación. Política fiscal por país debe investigarse aparte.

## 6. Escenario demostrativo sin cifras comerciales reales

Una superficie de pintura requiere área 120 m², dos manos, cobertura SINTÉTICA 8 m²/L/mano y 10 % de consumo **adicional sobre teórico**: 33 L de consumo previsto. Si se vende exclusivamente en envases sellados de 4 L, requeriría 9 envases = 36 L; esos 3 L son diferencia compra/consumo, **no** «merma» ni producto automáticamente devuelto al almacén. Si el stock disponible registrado es 6 envases, faltan 3: el sistema debe ofrecer aviso de disponibilidad y plazo/alternativa, no rebajar existencias al emitir una cotización.

Este ejemplo NO certifica rendimiento de pintura alguna ni representa un contrato de obra.

## 7. Límites del MVP

**IN:**
1. Catálogo local de productos/servicios (CSV/import inicial y edición), unidades y listas de precios.
2. Cotización con cliente, fechas/vigencia, ítems mixtos, cantidad manual o calculada, descuento/impuestos configurables, total, estado borrador/emitida/aceptada/rechazada/vencida, revisión.
3. Cálculo dimensional acotado (área/volumen/longitud, cobertura por ficha como variable) y unidades comerciales/paquetes, sin recetas ingenieriles inventadas.
4. Indicador **referencial** de disponibilidad del catálogo en **un almacén local**, con registro auditado de entrada/salida si se implementa inventario; stock NO reservado ni descontado por cotización.
5. PDF y CSV/Excel de propuesta y registro de cambios, con validación de montos y redondeos.

**OUT MVP:** facturación electrónica/SUNAT, POS, cajas, CRM completo, pedidos automáticos, compras/proveedores, multi-almacén avanzado, lotes/series, sincronización cloud, multiusuario SaaS, IA que inventa precios, optimización de corte, diseño estructural, promesas de cumplimiento tributario y stock en tiempo real entre equipos. Pueden evaluarse después por demanda comprobada.

## 8. Riesgos y puertas de decisión

| Gate | Pregunta | Evidencia de salida |
|---|---|---|
| G0/mercado | ¿Qué segmento repetitivo paga por esta diferencia? | 5–10 observaciones de flujos reales, alternativas usadas, precio/disposición de pago; todavía pendiente |
| G1/producto | ¿Cotización comercial requiere contexto distinto de ACU de obra? | SRS y flujos extremos firmados, reglas de documento cerradas |
| G2/arquitectura | ¿Reutilizamos la aplicación Qt/SQLite o resulta mejor otro núcleo? | Spike de catálogos + documento + stock aislado, integración sin romper obra |
| G3/cálculos | ¿Conversiones y cantidades son verificables? | fixtures de unidades, redondeos, stock, precio, impuestos, paquetes |
| G4/operaciones | ¿Una cotización modifica inventario o costes ajenos? | pruebas que demuestran **cero mutaciones** no autorizadas, historial, atomicidad |
| G5/distribución | ¿El fork puede circular sin confusión con el productor? | licencias/avisos/activos/branding, sin llamadas/publicaciones al origen |
| G6/comercial | ¿Alguien paga más que los costes de atenderlo? | pilotos y pagos verificables; si no, PIVOT/KILL |

**Decisión tomada por propietario:** GO a la **arquitectura de producto de dos BUs** y a la especificación de Venta; HOLD para codificar nuevas tablas/UI hasta cerrar contratos y regresión. PR #1 (spike ACU) y PR #3 (estabilización) siguen separados. No exigir demostrar rentabilidad antes de diseñar, pero **sí** antes de aprobar comercialización/escala.

## 9. Secuencia de implementación si se aprueba

`MK0 mercado+brecha` → `MK1 modelo funcional SRS` → `MK1 modelo de datos + UX cotización` → `MK2 motor cantidades/importe puro` → `MK2 catálogo + stock transaccional` → `MK3 documento PDF y flujo` → `MK3 pruebas E2E` → `GO/PIVOT/KILL`.

**Decisión final de alcance:** Construcción **no será un plugin subordinado** ni se reescribirá como Cotizaciones. Ventas tendrá navegación, lógica y persistencia independientes y compartirá utilidades solo cuando las pruebas demuestren equivalencia de contratos. Se preservan las licencias y atribuciones originales. El paso de diseño siguiente es [ADR-002](ADR-002-DOS-UNIDADES-DE-NEGOCIO.md), no una reconstrucción del shell.
