# Entrega de implementación Ventas — UNVERIFIED

Fecha: 2026-10-24. Repositorio exclusivo `Em3rc0d/ingepresupuestos`.
Base: `design/multi-sector-quotations-mk0-20261024` en `88ca463343430e091eb0835ce51316753480e2f3`, PR #4 abierto.
Rama: `feat/ventas-v1-astra-work-20261024`.

**Código implementado, NO VERIFICADO.** No se ejecutaron aplicación, pruebas, linters, typechecks, compilaciones, builds, exportaciones, instaladores, migraciones ni Actions. Tampoco se crearon archivos de pruebas, PR, tags o releases. La revisión de esta entrega consistió exclusivamente en lectura y edición de fuentes/diffs. La autorización coding-only del mandato vigente supera los avisos históricos HOLD de los documentos candidatos; no acredita cierre de gates de QA o mercado.

| Lote | Estado real |
|---|---|
| P0 | Lectura dirigida; decisiones operativas documentadas; rama separada |
| P1 | Dominio decimal, unidades, fórmulas, precios, estados y ledger escritos; UNVERIFIED |
| P2 | Migración, repositorios, servicios y snapshots escritos; UNVERIFIED |
| P3 | Pantallas PySide6 y navegación conectadas por código; UNVERIFIED |
| P4 | Vista previa, emisión sellada y PDF/XLSX escritos; UNVERIFIED |
| P5 | Solo protocolo tipado. Implementación del adaptador ACU NO INICIADA |
| P6 | Matriz y contrato QA redactados; publicación de rama mediante GitHub; sin PR |

## Descubrimiento → decisión

| Fuente leída | Hallazgo y decisión |
|---|---|
| `views/main_window.py` | Índices de navegación heredados fijos; Ventas se agrega al final con QPushButton accesible por teclado. Carga perezosa en `_crear_vista`; excepción aislada con reintento |
| `main.py`, `core/config.py` | `init_db` y ruta SQLite activa existentes. Ventas no se inicializa en arranque global ni abre/copia seed |
| `core/database.py` | Dinero heredado usa float y reglas ACU; dominio nuevo independiente, sin tocar `_recalcular_pu` ni extraer shared kernel no caracterizado |
| `core/almacen.py`, `core/requerimientos.py` | Stock/consumo por obra y redondeos propios: no reutilizados para SKU |
| `core/backup.py` | SQLite backup del archivo activo: incluye tablas nuevas sin modificar su API; restauración pendiente de QA |
| `views/_catalogo_base.py`, `utils/theme.py`, `utils/i18n.py`, `utils/formatting.py` | Se usan tokens de tema y tr; no se heredan CRUD ligados al catálogo de obra ni formateadores que convierten dinero a float |
| `requirements.txt`, `core/exporter.py`, fuentes Inter | ReportLab/openpyxl ya declarados; exportador comercial separado con misma fuente empaquetada. Ninguna dependencia instalada |
| `.github/workflows/` | Cinco workflows; push de rama no coincide con triggers de tags/manual/cron. Ningún archivo CI modificado |
| Auditoría y documento de estabilización PR #3 | Deuda y riesgos heredados siguen abiertos; no se fusiona estabilización ni se atribuyen aquí sus resultados anteriores |

## RF → implementación

Todos los estados “escrito” significan **IMPLEMENTED — UNVERIFIED**, sin prueba de funcionamiento.

| RF | Archivos (relativos a raíz) | Estado / límite |
|---|---|---|
| 001 | `core/ventas/application/services.py`, `infrastructure/repositories.py` dentro de `core/ventas` | UUID, secuencia anual transaccional, moneda/fechas/cliente: escrito |
| 002 | `domain/models.py`, `views/ventas/editor.py` | Línea libre sin SKU: escrito |
| 003 | `application/services.py`, `infrastructure/repositories.py`, `views/ventas/editor.py` | Selección catálogo + snapshot: escrito |
| 004 | `domain/quantity.py`, `views/ventas/editor.py` | h/jornada/evento/tarifa, sin cuadrillas: escrito |
| 005 | `domain/formulas.py`, `views/ventas/quantity.py` | Longitud/área/volumen y sumatorias: escrito |
| 006 | `domain/models.py`, `views/ventas/editor.py` | Líneas mixtas: escrito. Referencia ACU: pendiente |
| 007 | `domain/models.py`, `application/services.py`, `views/ventas/catalog.py` | CRUD/archivo, precio/costo/tasa explícita: escrito |
| 008 | `ventas_items.parent_id/attributes`, `views/ventas/catalog.py` | Variante como SKU vendible propio, sin jerarquía recursiva: escrito |
| 009 | — | Importación CSV NO INICIADA; fuera de A–G obligatorios del mandato |
| 010 | `domain/quantity.py` | Registro/conversión dimensional y límites: escrito |
| 011 | `domain/formulas.py`, `views/ventas/catalog.py`, `quantity.py` | Cobertura por mano y fuente/supuesto: escrito |
| 012 | `domain/formulas.py`, `views/ventas/editor.py` | Requerido vs vendible vs equivalente físico/restante, cierre explícito: escrito |
| 013 | `domain/money.py`, `views/ventas/editor.py`, `infrastructure/repositories.py` | Tarifa/costo separados, margen de referencia solo con costo: escrito |
| 014 | `domain/pricing.py` | Descuentos por línea/global; reparto por mayor resto: escrito |
| 015 | `domain/pricing.py`, `views/ventas/common.py` | Impuesto explícito incluso cero; sin configurar bloquea emisión: escrito |
| 016 | `application/services.py`, `views/ventas/inventory.py` | Consulta almacén local por SKU: escrito |
| 017 | `application/services.py` | Guardar/emitir/aceptar/exportar sin llamadas a movimientos: escrito, invariante NO PROBADO |
| 018 | `domain/inventory.py`, `infrastructure/repositories.py`, `views/ventas/inventory.py` | Movimientos firmados, motivo, actor, no negativos: escrito |
| 019 | `application/services.py`, `views/ventas/editor.py` | Requerido agregado, faltante, físico/disponible; reservado=0 sin reservas: escrito |
| 020 | `domain/models.py`, `application/services.py`, `views/ventas/catalog.py` | Paquete de un nivel; componentes internos y precio externo explícito: escrito |
| 021 | `infrastructure/exporters.py`, `views/ventas/editor.py` | Preview de revisión guardada y comparación de contenido antes de emitir: escrito |
| 022 | `infrastructure/migrations.py`, `repositories.py`, `application/services.py` | Revisiones, SHA256, triggers y diff: escrito |
| 023 | `infrastructure/exporters.py`, `views/ventas/editor.py` | PDF y XLSX por revisión: escrito. No se generaron archivos para comprobarlo |
| 024 | `domain/quote_states.py`, `application/services.py`, `views/ventas/shell.py` | Estados y eventos con actor/motivo/fecha: escrito |
| 025 | `infrastructure/sqlite.py`, `application/services.py` | Persistencia local transaccional: escrito |
| 026 | `views/ventas/shell.py` | Filtros número/título/receptor, cliente, fecha, estado y selector de revisión: escrito |
| 027 | `application/services.py`, `views/ventas/editor.py` | Nueva revisión y diferencias, preservando emitida: escrito |
| 028 | `domain/formulas.py`, `views/ventas/catalog.py`, `quantity.py` | Referencia textual/fuente y supuesto no validado: escrito. Adjuntos de fichas NO implementados |
| 029 | `application/services.py` | No existe conversión a orden ni movimiento automático; límite por diseño, NO PROBADO |
| 030 | `views/main_window.py` | Único archivo heredado de runtime editado; resto de Construcción sin cambios de fuente. Regresión NO EJECUTADA |
| 031 | `views/main_window.py`, `views/ventas/shell.py` | Entrada Ventas independiente, error de bootstrap aislado: escrito |
| 032 | `infrastructure/migrations.py` | Tablas ventas independientes y UUID propios: escrito |
| 033 | `application/construction_adapter.py` | Solo dataclass + Protocol. Sin lector SQLite, sin botón de importación. PENDIENTE |
| 034 | `infrastructure/repositories.py` | Historial append-only de tarifas por moneda + snapshots de condiciones: escrito. Listas avanzadas pendientes |
| 035 | `infrastructure/migrations.py`, `repositories.py` | Ledger comercial propio, sin escrituras a almacén de obra: escrito, NO PROBADO |

Los paths abreviados `domain/*`, `application/*`, `infrastructure/*` corresponden a `core/ventas/`.

## Invariantes y límites de evidencia

- INV-01/02/07/09/12: separación de tablas, bootstrap perezoso y núcleo sin Qt/red; requieren pruebas de regresión, rollback y offline.
- INV-03/04/08: costos/precios explícitos y fórmulas cerradas/decimales; requieren oráculos numéricos independientes.
- INV-05: cotizaciones no invocan escritura de movimientos; requiere comparar ledger y obra antes/después.
- INV-06: triggers/SHA256 y exportación desde snapshot; requiere ataques de mutación, comparación de documentos y verificación visual.
- INV-10: esta rama no modifica infraestructura, updater ni workflows. Los problemas heredados de PR #3 continúan pendientes; no se afirma que INV-10 esté cerrado globalmente.
- INV-11: no hay pruebas ni evidencia de producción. Sin GO a merge/release/comercialización.

## Riesgos y pendientes concretos

1. No se ha comprobado ni siquiera importación/sintaxis del incremento, por prohibición expresa. Revisar en QA cada señal/slot Qt, migración, SQL y flujo antes de usarlo con datos reales.
2. No se ejecutó la migración en base vacía/copias ni se verificó backup/restauración o coexistencia con proyectos de obra.
3. No hay validación visual PDF/XLSX, paginación de descripciones extensas, caracteres no latinos ni diferencias Windows/Linux. XLSX guarda decimales exactos como texto para evitar la pérdida de precisión de Excel; no contiene fórmulas ni cálculo de hoja.
4. Falta medir rendimiento de 5.000 SKU/200 líneas; el editor consulta disponibilidad local y vuelve a presentar tablas al recalcular. No se afirma RNF-09 satisfecho.
5. Accesibilidad/contraste/zoom/cierre de diálogos y tamaño mínimo requieren interacción real. Invitados se bloquean en servicios para escrituras de negocio; no es seguridad online ni segregación avanzada de roles.
6. La referencia del ledger indica cuándo se registró el último movimiento, no certifica un conteo físico ni sincronización con otros dispositivos.
7. SKU estable; para cambiar unidad o seguimiento tras movimientos se exige nuevo SKU. El almacén de v1 es único; no hay reservas ni devoluciones con órdenes.
8. Fichas solo referenciadas por texto. Sin adjuntos, sin importación CSV y sin conector ACU implementado. Sin SUNAT/POS/pedidos/API/IA/cloud.
9. PR #1/#3 siguen separados. Persisten riesgos de updater/identidad/semilla/dependencias del baseline; no corregidos por este incremento.
10. Los modelos nuevos son independientes, sin extracción de shared kernel de Construcción: no hubo caracterización de equivalencia que autorice reutilizar su cálculo.

Contrato siguiente: [QA-POST-ASTRA-PENDIENTE.md](QA-POST-ASTRA-PENDIENTE.md). Guía de uso: [VENTAS-GUIA-V1.md](VENTAS-GUIA-V1.md).

## Commits publicados de código

Los SHA siguientes corresponden a GitHub; el envío directo por Git no disponía de credenciales y los commits se recrearon mediante el conector, conservando exactamente el árbol de fuentes local. La comparación de árboles es integridad de transferencia, no prueba del software.

| SHA remoto | Cambio |
|---|---|
| `4e4a48af29290f594d248edb13bb6d3db9d8a5a2` | Dominio y decisiones operativas |
| `33a5084c1aecb3fd1f87eddda59660f95db9f379` | Migración, repositorios y servicios |
| `7c028fdefbce9ec2b570c94bccf47b9c8da8f53e` | Exportación y emisión ligada a preview |
| `6b5ba49d4bb2eb58330c32be6f83f66138997284` | UI y navegación |
| `278e7461f2ca22070a6808d05c0e64b97226a5b6` | SKU estable y cantidades históricas |
| `ef2d262c6ba33c768076ffee91f4277ee3713f2b` | Unidad/tipo de línea del catálogo |
| `de59cf3bc3081bff2884577c034c5b9aa30b32bf` | Moneda y cierre de formularios anidados |

El commit contenedor de este documento completa el handoff documental. Inventario completo de archivos: [ASTRA-HANDOFF.yaml](ASTRA-HANDOFF.yaml).
