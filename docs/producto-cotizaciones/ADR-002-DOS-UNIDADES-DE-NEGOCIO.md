# ADR-002 — Dos unidades de negocio, una aplicación y reutilización controlada

**Fecha:** 2026-10-24
**Estado:** ACCEPTED — dirección de alcance y límites del producto confirmados por el propietario. La arquitectura detallada, contratos y SRS continúan en evaluación; **no autoriza BUILD**.
**Repositorio exclusivo:** [Em3rc0d/ingepresupuestos](https://github.com/Em3rc0d/ingepresupuestos). No contacto ni PR al proyecto de origen. Mantener GPL-3.0-or-later y atribuciones.

## Decisión innegociable

La aplicación contendrá **dos unidades de negocio (BU) de primer nivel**, con navegación, datos y flujos diferenciados:

1. **BU Construcción:** conservar el software existente de presupuestos de construcción, incluyendo proyectos, partidas, metrados, ACU, recursos, cronogramas, reportes, requerimientos, almacén/kárdex de obra y funcionalidades afines. No reemplazar el modelo actual por un cotizador genérico ni degradar el comportamiento existente.
2. **BU Cotizaciones de Ventas:** introducir un dominio nuevo para cotizar bienes, servicios, materiales dimensionados, instalaciones, paquetes y combinaciones; con clientes, catálogo comercial, listas de precios, inventario comercial, revisiones, vigencia y exportación. Construcción NO es un submódulo de Ventas y Ventas NO es un tipo de partida de construcción.
3. **Shared kernel mínimo:** compartir solamente funciones técnicas **desacopladas y verificadas**: validación y conversión de unidades, política decimal común donde las reglas coincidan, formatos/exportación, utilidades UI, capacidades de respaldo/migración y mapeos de recursos voluntarios. Mantener políticas de negocio y persistencia por BU. La decisión de extraer código exige caracterización previa: **reuse ≠ copiar llamadas a funciones con efectos laterales**.

No se creará un tercer producto independiente ni un nuevo repositorio. El primer alcance será **una sola aplicación desktop PySide6/SQLite**, con evolución a servicios/web solo si se justifica por demanda y contratos tecnológicos. Preservar compatibilidad de datos y capacidad offline de Construcción.

## Topología conceptual

\`\`\`text
IngePresupuestos (fork Em3rc0d)
├── Navegación/identidad local/ajustes generales (shell)
├── BU CONSTRUCCIÓN [EXISTENTE — preservar]
│   ├── Proyecto, Partidas, ACU, Metrados y Precios por proyecto
│   ├── Cronograma, Informes, Control de Obra, Requerimientos
│   └── Almacén de obra y Kardex por proyecto
├── BU COTIZACIONES DE VENTAS [NUEVA]
│   ├── Cliente y Cotización Comercial + Revisiones
│   ├── Líneas: SKU, Servicios, Materiales medibles y Paquetes
│   ├── Catálogo/Precio de venta/Costos y Tarifas
│   ├── Inventario comercial con entradas/salidas/reservas (por fase)
│   └── Propuestas PDF/XLSX y eventos del ciclo comercial
└── Shared kernel MINIMAL, con contratos versionados
    ├── Unidades / Decimal / Money / reglas explícitas de redondeo
    ├── Interfaces de exportación y presentación
    └── Adaptadores opcionales de Construcción → Ventas (snapshot)
\`\`\`

## Reutilización: análisis por capacidad, con evidencia de código

| Fuente del fork actual | Qué hace realmente | Reutilización candidata | Riesgo / límite |
|---|---|---|---|
| \`core/database.py\` — \`partidas\`, \`acu_items\`, \`_recalcular_pu\`, \`precio_recurso_en_proyecto\` | Mantiene precio unitario, recurso, rendimiento MO/EQ y precio específico **por proyecto** | Exponer un adaptador **de solo lectura** para cotizar servicios de construcción con snapshot de costos y cantidades | Nunca pasar \`CotizacionLinea\` como \`partida\` ni mutar ACU/PU de obra desde Ventas |
| \`core/database.py\` — \`_r2\`, \`_rn\`, \`cantidad_acu\`, \`parcial_wysiwyg\` | Redondeo HALF_UP pero funciones actuales convierten números a \`float\`; reglas de cantidad ACU específicas de obra | Caracterizar mediante golden tests. Extraer **nuevos primitives Decimal** con política explícita sin cambiar los resultados de Construcción | No reutilizar directamente \`float\` para importes comerciales ni aplicar reglas WYSIWYG de metrado al subtotal de venta |
| \`views/metrados_view.py\` y \`metrados_detalle\` | Metrados de partidas y acero en obras | Extraer funciones **puras** de geometría/validación, si se prueban, para cantidad comercial | No reutilizar su vista Qt completa, ni conversión estructural acero→peso sin validación técnica |
| \`core/almacen.py\` + \`core/requerimientos.py\` | Ingresos, salidas/consumos, kardex y requerimientos **por proyecto de obra** | Inspiración de ledger, pruebas y reutilización futura de helpers puros tras abstraer unidades | **NO** sustituye inventario de venta por SKU, variante, depósito, reservado, disponible y devoluciones |
| \`recursos\` + \`views/recursos_view.py\` | Catálogo de recursos MO/MAT/EQ/SC, precio del catálogo y del proyecto | Importador/mapeador explícito de insumos de construcción a ítems comercializables; componentes UI genéricos tras extraerlos | **NO** es un catálogo comercial de SKU/variantes/impuestos. \`tipo\` MO/MAT/EQ/SC no equivale a PRODUCTO/SERVICIO |
| \`utils/formatting.py\`, exportadores de documentos, \`utils\` y componentes UI | Formateo numérico/multimoneda, PDF/Excel y helpers de interfaz | Reusar APIs generales solo tras pruebas de normalización, formatos, moneda y exportación | Formato visual ≠ corrección fiscal; no mezclar moneda del proyecto con cotización |
| PR #1 \`core/acu_parametrico.py\` | Evalúa cantidades sintéticas por unidad de partida; no precios, inventario ni persistencia | Extraer/mantener un evaluador físico puro y adaptadores separados a ACU de obra o líneas comercializables | PR #1 sigue DRAFT; no moverlo al shared kernel sin contratos, fórmula y unidad correctos |
| PR #3 \`fix/fork-stabilization-20261024\` | Estabilización Qt/SQLite y controles de independencia del fork | Continuar de forma separada y verificar antes de merge | No mezclar trabajo de estabilización con migraciones de nuevos agregados |

La tabla establece **candidatos**, no certifica APIs compartidas ni compatibilidad futura.

## Contratos de dominio / anticorrupción

- Construcción publica opcionalmente una vista **de lectura** \`ConstructionEstimateSnapshot\` con \`source_project_id\`, \`source_revision_or_hash\`, \`source_partida_ids\`, \`quantity\`, \`unit\`, \`cost_basis\`, \`cost_version_or_timestamp\` y procedencia.
- Ventas crea \`QuoteLine\` **nueva** y guarda descripción, unidad, cantidad, costo estimado **opcional**, precio de venta, política de tributos y snapshot del origen; no retiene referencias activas que recalculen documentos emitidos.
- Convertir un ACU a línea de venta **no significa vender automáticamente al costo**. Precio comercial se define explícitamente (tarifa, margen o override aprobado). Si el costo es desconocido: mostrarlo, no inventar margen.
- Un cambio en ACU, lista de precios o stock después de emitir una cotización **no modifica la versión emitida**. Un recálculo requiere revisión propuesta y confirmación.
- Las cantidades comerciales pueden combinar **consumo** físico con **presentación vendible**: 33 L estimados vs 9 envases de 4 L (36 L comercializables). Unidad, remanente y regla de redondeo deben quedar visibles.
- La consulta de stock comercial muestra físico/reservado/disponible/fecha; **cotizar, emitir, exportar o aceptar NO mueve stock**, y la acción posterior de reserva/salida requerirá entidad/permiso/transacción propios.
- **Toda escritura** pertenece a la BU respectiva y a su transacción SQLite. El shared kernel no posee tablas económicas ni muta las bases de ninguna BU.
- Posible integración inversa (ventas→construcción) queda fuera del MVP; cualquier futura orden de obra será un proceso explícito, no un acoplamiento bidireccional implícito.

## Delimitación del almacenamiento

Recomendación inicial: **mismo archivo SQLite local**, con tablas separadas y nombres por contexto (\`ventas_cotizaciones\`, \`ventas_cotizacion_lineas\`, \`ventas_catalogo\`, \`ventas_inventario_movimientos\`, \`ventas_cotizacion_revisiones\`, etc.), sujeto a análisis de migraciones. **No crear tablas en este ADR.**

- Clientes comerciales y roles no se mezclarán con \`proyectos\` ni \`usuarios\` sin contrato explícito.
- La tabla \`recursos\` de Construcción no será reinterpretada como productos comerciales.
- Idempotencia, FK, snapshots, transacciones y actualizaciones sin pérdida de datos son obligatorias.
- Se necesitará decidir si un catálogo base físico reutiliza identificador abstracto \`Item\` o una relación mapeada; **no hay decisión de unificar tablas**.
- Evitar forzar un \`proyecto_id\` artificial a cotizaciones de servicios TI, artículos, pintura o cualquier otro rubro.

## Criterios de preservación de Construcción (non-regression)

1. El usuario sigue pudiendo abrir proyectos y usar árbol de partidas/ACU/metrado, cálculo, cronograma y control de obra sin pasar por Ventas.
2. \`_recalcular_pu\`, \`precio_recurso_en_proyecto\`, rendimientos de cuadrilla, \`cantidad_acu\`, redondeos y totales WYSIWYG se mantienen conforme a golden fixtures de Construcción.
3. No se modifican ni migran destructivamente \`proyectos\`, \`partidas\`, \`recursos\`, \`acu_items\`, \`metrado_detalle\` ni históricos del usuario.
4. Si Ventas falla al abrir, no debe impedir entrar a Construcción ni modificar sus datos.
5. Copias/restauraciones y exportaciones de Construcción mantienen compatibilidad. El instalador no crea servidor obligatorio.

## Decisiones cerradas versus abiertas

**Cerrado (producto):** dos BUs de primer nivel dentro de **una** aplicación, Construcción se preserva íntegra, Ventas se añade, se busca reutilización responsable, stock comercial separado de almacén de obra, sin reescritura web, sin contacto upstream.

**Abierto (ingeniería/comercial):** segmento piloto, numeración/cliente/estados de cotización, inventario comercial de un almacén o consulta importada, impuestos, unidades y moneda por línea, contratos de shared kernel, políticas de precio y tasa de impuesto, esquema y migraciones; ejecución completa de tests CI. No justificar con “todos los tipos de negocio” una implementación universal inmediata.

## Gating y orden de trabajo

- Gate A: finalizar PR #3 de estabilización (o documentar aislamiento temporal), baseline seguro para Construcción.
- Gate B: SRS por BU y diseño del shared kernel + catálogo de ventas; fijar oráculos para cálculos, moneda e inventario.
- Gate C: prototipo **de venta pura** (cliente + SKU + servicio + línea de área + total + PDF) sin persistencia cruzada con obra.
- Gate D: conexión **optativa de solo lectura** de partidas/ACU al cotizador con snapshot y tests de no mutación.
- Gate E: inventario comercial auditado, disponible y no decrementado por cotización; demo y validación pagadora después.

**Invariante rector:** jamás sacrificar estabilidad de Construcción por la velocidad del nuevo cotizador.