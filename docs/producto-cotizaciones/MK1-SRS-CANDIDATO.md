# MK1 — SRS candidato · BU Cotizaciones de Ventas en una aplicación con BU Construcción

> **Actualización de ejecución:** el mandato explícito `PROMPT-ASTRA-WORK-IMPLEMENTACION-SIN-QA.md` autorizó implementar P0–P4 sin ejecutar QA. La matriz de código real y pendientes está en [ASTRA-IMPLEMENTACION-ESTADO.md](ASTRA-IMPLEMENTACION-ESTADO.md). El SRS completo sigue candidato; sus avisos históricos de no implementación no describen el estado actual de esta rama. Ninguna aceptación funcional está probada.

**Fecha:** 2026-10-24 · **Estado:** DRAFT, NO FROZEN, NO IMPLEMENTED · Dentro de una aplicación de **DOS unidades de negocio** ([ADR-002](ADR-002-DOS-UNIDADES-DE-NEGOCIO.md)). La decisión de mantener Construcción y añadir Ventas está aprobada; los detalles comerciales y técnicos de Ventas aún no.  
**Restricción:** no modificar schema, stock ni precios productivos hasta validar reglas, transacciones y compatibilidad con los proyectos de construcción. Todo trabajo en `Em3rc0d/ingepresupuestos`.

## Actores y entidades

- **Cotizador**: prepara, revisa, emite y revisa versiones de cotizaciones.
- **Responsable comercial**: autoriza descuentos cuando la política lo requiera.
- **Responsable de inventario**: registra/ajusta existencias si se habilita ese módulo.
- **Cliente**: recibe una cotización; aceptación inicialmente se registra manualmente, NO como firma contractual electrónica.
- **Catálogo**: `ItemComercial` tipado (`PRODUCTO`, `SERVICIO`, `MATERIAL_MEDIBLE`, `PAQUETE`).
- **Cotización**: documento comercial y sus `LineaCotizacion`, `Revision`, `SnapshotPrecio` y `ReglaCantidad`.
- **Existencias**: `MovimientoInventario` y `SaldoDisponible`, por almacén si se habilita; no son lo mismo que el `core/almacen.py` del control de obra.

## Requisitos funcionales (propuestos)

| ID | Requisito | Aceptación mínima |
|---|---|---|
| RF-001 | Crear cotizaciones con identificador único, cliente, moneda, vigencia y estado | Duplicados imposibles para el ámbito de numeración configurado |
| RF-002 | Admitir líneas libres sin producto catalogado | Descripción, unidad, cantidad y precio capturados explícitamente |
| RF-003 | Vincular líneas a SKU, variante y unidad de venta del catálogo | Descripción/precio no cambian en versiones emitidas aunque cambie catálogo |
| RF-004 | Cotizar servicios por hora, jornada, evento o tarifa fija | Validación de unidad y tipo; cero/negativos según política explícita |
| RF-005 | Cotizar materiales por metro lineal, m², m³, L o kg | Guardar fórmula, variables, unidad base y resultado reproducible |
| RF-006 | Combinar en una cotización productos, materiales y servicios comerciales; **opcionalmente** incorporar una referencia congelada de partida/ACU de Construcción por adaptador explícito | Totales correctos; Ventas NO muta la partida/ACU y no hereda indebidamente reglas MO/EQ a servicios comerciales |
| RF-007 | Catálogo de productos y servicios con SKU, precio, costo opcional, unidad, impuestos y estado | Insumos desactivados no se ofrecen por defecto; quedan en cotizaciones anteriores |
| RF-008 | Variantes de artículo como color, presentación o medida | Cada variante tiene identidad comercial inequívoca y stock propio si aplica |
| RF-009 | Cargar productos mediante CSV validado con previsualización de cambios | Errores por fila, sin escritura parcial no autorizada |
| RF-010 | Manejar unidades y conversiones compatibles con dimensiones | Rechazar conversiones físicas inválidas y tarifas sin unidad |
| RF-011 | Reglas de cobertura/rendimiento para materiales consumibles | Ficha o fuente opcional/obligatoria según dominio; ninguna cifra inventada por defecto |
| RF-012 | Representar unidades de compra/envase separadas del consumo estimado | Cálculo de envases enteros con regla de redondeo y resultado explicable |
| RF-013 | Registrar tarifas/precios de venta independientes del costo | Distinguir margen y markup; margen omitido si costo desconocido |
| RF-014 | Aplicar descuentos globales y por línea bajo política verificable | Resumen explica orden de descuento/impuestos |
| RF-015 | Aplicar tributos configurables con snapshot de tasas y reglas | No asumir una tasa tributaria fija o exención universal |
| RF-016 | Consultar stock comercial disponible por SKU y ubicación soportada | Mostrar cantidad/unidad/fuente/fecha; advertir cantidad insuficiente |
| RF-017 | No descontar ni reservar inventario al crear o emitir cotización | Test compara saldo/movimientos antes y después: no cambia |
| RF-018 | Registrar entradas, salidas y ajustes de inventario con motivo y auditoría | Movimientos consistentes, sin stock negativo salvo política definida |
| RF-019 | Distinguir stock físico, reservado, disponible, requerido y faltante | Fórmulas documentadas y conversión de unidades válida |
| RF-020 | Crear paquetes con componentes para estimación interna y presentación externa | Prohibir ciclos en composición; evitar doble sumar unidades/precios |
| RF-021 | Generar preview legible antes de emitir, con líneas e importes | Vista previa usa exactamente los datos congelados de la revisión |
| RF-022 | Mantener revisiones con diferencias sobre líneas, unidades, tarifas y totales | Cotización emitida no se modifica in situ: nueva versión |
| RF-023 | Exportar cotización a PDF y al menos CSV o XLSX | Importes/monedas/condiciones coinciden con la revisión guardada |
| RF-024 | Registrar cambios de estado: borrador, emitida, aceptada, rechazada, vencida, anulada | Transiciones inválidas se rechazan; aceptación registrada con identidad/fecha |
| RF-025 | Guardar y abrir una cotización offline sin internet | SQLite local y transacciones; duplicidad/snapshot seguros |
| RF-026 | Gestionar cotizaciones por cliente, fecha, estado y versión | Búsqueda no altera ningún documento |
| RF-027 | Recalcular cantidades y mostrar diff sin mutar el documento emitido | Confirmación crea nueva revisión; cancelar preserva anterior |
| RF-028 | Permitir adjuntar o referenciar ficha técnica/supuesto sin integraciones externas obligatorias | Ausencia de ficha se marca como supuesto no validado, no se inventa fuente |
| RF-029 | Permitir convertir una cotización aceptada en orden SOLO en fase posterior | MVP no crea órdenes, facturas ni descuenta stock en la aceptación |
| RF-030 | Preservar íntegra la **BU Construcción existente** e independiente de Ventas | Crear/editar/abrir proyecto, ACU, metrados, cronograma, control de obra, exportaciones y backups funciona sin habilitar Ventas; golden tests sin regresiones |
| RF-031 | Permitir navegación explícita por **Construcción** y **Cotizaciones de Ventas** en una única app | Entrar a Construcción no crea documentos de Ventas; fallo en Ventas no bloquea proyectos |
| RF-032 | Garantizar datos operativos separados por BU y mapeos explícitos de recursos | Un SKU comercial no reutiliza accidentalmente el ID de `recursos` ni altera precio de proyecto |
| RF-033 | Exponer snapshot **solo lectura** de una partida/ACU de obra para usarla como referencia de venta, si se autoriza el conector | Snapshot incluye unidad, cantidad, costo base y procedencia; modificar cotización deja partida/ACU original idéntica |
| RF-034 | Versionar las tarifas y condiciones comerciales sin afectar costos unitarios de obra | Variar lista de precios comercial no cambia `precio_unitario` de partidas ni `precios_proyecto` |
| RF-035 | Separar expresamente stock comercial por SKU de almacén de obra por `proyecto_id` | Registrar movimiento de almacén comercial no toca `almacen_ingreso` ni `parte_diario_recurso`; cotizar no mueve ninguno |

## Reglas de negocio innegociables

- **RB-01:** `Cotización != pedido != factura != salida de stock`. Emitir, aceptar o exportar no altera existencias, salvo operación separada de reserva/venta si en el futuro se diseña, aprueba y prueba.
- **RB-02:** `cantidad a consumir` puede diferir de `cantidad a comprar/vender` por presentaciones comerciales enteras; ambas se muestran por separado. No llamar «merma» a ambas.
- **RB-03:** Precio histórico/snapshot protegido en toda cotización emitida. El catálogo cambiante no recalcula silenciosamente documentos anteriores.
- **RB-04:** Unidad y dimensión física estrictas. m², m³, kg, L, unidad y horas NO son intercambiables sin una transformación documentada.
- **RB-05:** costo ≠ precio ≠ utilidad; margen = (precio−costo)/precio si precio>0; markup=(precio−costo)/costo si costo>0. Si no hay costo, no inferir rentabilidad.
- **RB-06:** las tarifas de mano de obra en cotización no siguen automáticamente `cuadrilla/rendimiento × jornada` de ACU; son tipos distintos salvo adaptación declarada.
- **RB-07:** exportación PDF debe conservar estados de impuestos y redondeo por línea/total que mostró el editor.
- **RB-08:** ninguna herramienta IA tiene facultad de generar precios de catálogo, existencias ni fichas comerciales sin evidencia.
- **RB-09:** utilizar `Decimal` / política única de redondeo; evitar flotantes binarios para importes comerciales.
- **RB-10:** datos de cliente, costos, margen y precios comerciales permanecen locales, sin telemetría o publicación predeterminada.
- **RB-11:** Construcción y Ventas son dos BUs equivalentes dentro de la misma app, con límites de datos, estado y navegación. No crear proyectos de obra ficticios para almacenar ventas.
- **RB-12:** importar como referencia una partida/ACU crea un snapshot comercial, no una relación de escritura que actualiza la obra. Costo técnico ≠ precio de venta; sin precio comercial aprobado, NO emitir la línea como si fuera margen válido.
- **RB-13:** el stock `core/almacen.py` representa materiales por proyecto de obra, NO inventario de productos comerciales. Prohibido usar su saldo como stock comercial sin contrato y conciliación de almacenes.

## Requisitos no funcionales

| ID | Requisito verificable candidato |
|---|---|
| RNF-01 | Disponibilidad offline para crear, abrir, modificar borradores y exportar |
| RNF-02 | Operaciones SQLite atómicas; ante error de guardado no hay documento parcial |
| RNF-03 | Migración no destructiva desde bases del módulo de construcción; backup y rollback probados |
| RNF-04 | Validación central de entradas, decimales, unidades y estados; nunca `eval` de fórmulas del usuario |
| RNF-05 | Identidad local y permisos mínimos para usuarios si existe autenticación; no afirmar seguridad multiusuario |
| RNF-06 | Historial/versiones inmutables en emisión; integridad de líneas y moneda |
| RNF-07 | Accesibilidad de teclado, foco, etiquetas y mensajes de error en PySide6 |
| RNF-08 | Generación PDF/XLSX con reconciliación exacta de montos y moneda de la versión |
| RNF-09 | Rendimiento objetivo inicial: catálogo 5.000 SKU y cotización de 200 líneas, sin bloqueo perceptible; presupuesto y medición REAL pendientes |
| RNF-10 | Atribuciones y GPL del código de origen conservadas, sin URLs de updates/release al productor original |
| RNF-11 | Pruebas unitarias puras, DB aislada, integration fixture, Golden PDF y regresión de construcción en CI |
| RNF-12 | Auditoría de datos iniciales y no divulgación accidental de información comercial/PII |

## Estados y efectos

`DRAFT --emitir--> ISSUED --registrar_aceptación--> ACCEPTED`  
`ISSUED --rechazar--> REJECTED`  
`ISSUED --vencimiento--> EXPIRED`  
`DRAFT/ISSUED --anular--> CANCELLED` según política de auditoría.  
Para editar una propuesta `ISSUED`, crear `REVISION_DRAFT` enlazada; nunca editar `ISSUED` en sitio. `ACCEPTED` todavía **no** es un documento tributario ni orden de venta, y no aplica decremento de stock.

## Pruebas de aceptación mínimas

1. Producto por unidad: 3 unidades × precio indicado, con snapshot antes/después de actualizar catálogo.
2. Material: 120 m² × (2 manos / 8 m² por L por mano) × (1+0.10 consumo adicional) = 33 L consumidos; cobertura sintética por mano, no ficha técnica real.
3. Presentación comercial: envase 4 L, se requieren 9 envases = 36 L vendidos/abastecidos, NO 33 L descontados como venta de nueve envases.
4. Stock: 6 envases disponibles, 9 requeridos → falta 3, emitir cotización **sin** mutar inventario.
5. Servicio: 5 h × tarifa configurable, sin aplicación automática de lógica de cuadrilla de obra.
6. Moneda y tributos: snapshot y redondeos deterministas en líneas, subtotal y exportación.
7. Prueba de dos BUs: crear/emitir cotización y operar Construcción en paralelo; conteos, costos, partidas y fuentes de proyecto intactos.
8. Revisión: cambios de una línea no alteran una versión previamente emitida.
9. CSV inválido: no hay duplicación accidental de SKU, no escrituras parciales.
10. Error de disco/SQLite: rollback, documento íntegro y posibilidad de reintentar.
11. Múltiples ítems mixtos: cantidades, precios y presentación independientes pero total coherente.
12. Acceso offline: catálogo, cotización y PDF sin servicios remotos.
13. Un usuario abre Construcción sin registrar cliente, inventario o cotización; 40 reglas críticas base mantienen valores con golden fixtures.
14. Línea opcional desde ACU: convertir solo lectura a snapshot con nuevo precio de venta, congelar source ID/hash; edición posterior de obra no cambia documento emitido.
15. Producto con `SKU=MAT-001` e insumo `recursos.id=1`: sus identidades, unidades y precios no se confunden; movimientos inventario comercial no alteran `almacen_ingreso`.
16. Falla de migración Ventas: rollback de sus nuevas tablas; DB de Construcción restaura y opera sin pérdida de datos.

## Preguntas y gates abiertos (no esconder)

1. ¿Segmento inicial pagador: distribuidores de materiales, instaladores, oficinas técnicas, talleres, servicios TI u otro? «Todos» como arquitectura, **no** como marketing inicial.
2. ¿Stock comercial en primera versión será mínimo de **un almacén** (con movimientos) o lectura manual/importada? Diferencia de costos importante.
3. ¿Cotización solo informativa o flujo de aprobación comercial con varios roles?
4. ¿Ámbito de impuestos, moneda y documentos requerido en Perú y otros países? Validar con especialista antes de prometer cumplimiento.
5. ¿Cuál es el contrato exacto para reutilizar `recurso`, `partida` y `ACU` sin contaminar operaciones comerciales?
6. ¿Los precios se ingresan manualmente, por lista por cliente o con importaciones? ¿Se requieren descuentos por tramo?
7. ¿Decisión de producto: PySide6+SQLite durante piloto, o separar dominio para migración web futura? **No autorizar reescritura web automática**.

**Estado de aprobación:** **aprobado únicamente el direccionamiento de dos unidades de negocio**, no los contratos de implementación. El SRS de BU Ventas sigue candidato. No se permiten migraciones/UI comerciales hasta cerrar los nodos críticos. PR #3 estabilización y PR #1 ACU siguen separados; no hay razón para contactar al autor original.
