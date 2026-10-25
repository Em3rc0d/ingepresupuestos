# Estado de implementación — Fase 2 — UNVERIFIED

**Fecha:** 2026-10-25. **Repositorio:** `Em3rc0d/ingepresupuestos`. **Rama:** `feat/ventas-v1-astra-work-20261024`.

Base de Fase 1: `ea195c787db5fc176ba2745334c0fbab00ab1ccb`. Correcciones incorporadas desde PR #5, cabeza `5bdceb4012408e4de3fd0f26c54b3b32ad292995`, mediante merge dirigido exclusivamente a la feature. Sus commits, autores, dos archivos de pruebas y dos workflows se conservan en la ascendencia. Los workflows solo escuchan sus ramas de auditoría; no se ejecutaron ni modificaron durante esta entrega.

El PR #5 documenta **52 pruebas seleccionadas de Windows aprobadas antes de estas adiciones**. Es evidencia histórica del arreglo, no validación de CSV, conector o fichas. En Fase 2 **no se ejecutó** aplicación, importación de módulos, pruebas, Qt, linters, compilaciones, builds, instalación de dependencias, migraciones, PDF de comprobación ni Actions. No se crearon pruebas nuevas ni se escribió en bases reales/seed. Revisión exclusivamente por lectura/edición de fuentes y diffs.

## Alcance entregado por código

| Prioridad / requisito | Estado | Archivos y contrato |
|---|---|---|
| P0 / PR #5 | INTEGRATED | Merge de `5bdceb4`; INSERT con 9 columnas explícitas; servicio y UI permiten revisar únicamente estado global y revisión EMITIDA, con token. Estados terminales no se reabren |
| P1 / RF-009 | IMPLEMENTED_UNVERIFIED | `infrastructure/catalog_csv.py`, `application/catalog_import.py`, `views/ventas/csv_import.py`: lectura acotada, plantilla, errores por fila, preview sin escrituras, confirmación y lote atómico con control de concurrencia |
| P2 / RF-033 | IMPLEMENTED_UNVERIFIED | `infrastructure/construction_reader.py`, `application/construction_adapter.py`, `construction.py`, `views/ventas/construction.py`: SQLite `mode=ro`, `query_only`, pertenencia/proyecto/usuario, metrado/unidad/moneda/costo guardado y ACU por proyecto, procedencia SHA256 congelada. Precio comercial explícito |
| P3 / RF-028 | IMPLEMENTED_UNVERIFIED | `infrastructure/datasheets.py`, `data_package.py`, `application/datasheets.py`, `views/ventas/datasheets.py`: documentos administrados, metadatos/eventos append-only, retirada sin borrar histórico, copias/exportación y respaldo ZIP explícito |
| P4 / RF-021/022/023/027/031 | IMPLEMENTED_UNVERIFIED | Catálogo, editor de línea/cotización e Inicio Ventas conectados; captura explícita de referencias; exportación de nombre/hash sin rutas privadas ni costos. Diálogos de archivos usan worker Qt para IO/parseo |
| RF-017/019/029/035 | PRESERVED_BY_DESIGN | CSV y ACU/fichas no registran movimientos ni reservas. Requeridos/disponibles siguen separados de inventario de obra. Comparación de ledger pendiente de QA |
| RF-030/032/034 | PRESERVED_BY_DESIGN | Sin cambios nuevos en `core/database.py`, `core/almacen.py`, seed o `views/main_window.py`. Tarifas siguen en tablas Ventas. La preservación por diff no acredita regresión funcional |
| RF restantes de Fase 1 | CARRY_FORWARD_UNVERIFIED | Se conserva la primera implementación y sus contratos; no se reescribió el cotizador. QA completo sigue abierto |

Los paths de `application/` e `infrastructure/` son relativos a `core/ventas/`.

## Decisiones concretas y límites

- CSV: 5 MiB/5000 registros, UTF-8/BOM, coma o punto y coma con detección por encabezados; punto decimal. `CREAR_SOLO` omite SKU ya existentes; duplicados dentro del archivo son error. Actualización explícita conserva identidad/atributos/fórmulas no presentes en columnas opcionales, respeta historial y recupera costo de la misma moneda, nunca de otra tarifa. Variantes requieren padre ya existente; paquetes nuevos con componentes se crean por UI, no por CSV. Todos los errores bloquean el lote.
- El preview conserva fingerprint del catálogo/tarifas/ledger. Confirmación exige que no cambien y revalida dentro de `BEGIN IMMEDIATE`; resumen/actor/hash CSV en `ventas_importaciones`. No hay stock inicial en CSV.
- ACU: se usa el **PU técnico almacenado**, no se ejecuta `_recalcular_pu` ni se certifica equivalencia con un ACU recién recalculado. Se capturan `ai.precio` efectivo por proyecto, fallback de catálogo, cantidades/cuadrillas, recursos, ajustes de precisión y contexto de proyecto. Los REAL heredados cruzan como texto SQLite. Costo no representable a seis decimales se conserva íntegro en procedencia y no produce un margen ficticio.
- Conector opcional y perezoso: no interviene en bootstrap. Unidad/moneda no reconocidas, agrupador o proyecto no autorizado bloquean solo esa selección. Sin FX. Sin PR #1 ni PR #3 integrados.
- Fichas: PDF/PNG/JPEG, firma y extensión, 20 MiB por archivo, hasta 10 referencias activas por artículo/línea. Almacén `USER_DATA_DIR/ventas/fichas/<sha256>.<ext>`; inspección no copia, confirmación sí. No OCR, extracción de rendimiento ni ejecución de archivos. Metadatos y procedencia quedan congelados en la línea.
- Ficha original eliminada: la copia administrada continúa independiente. Copia administrada ausente/alterada: estado `ARCHIVO NO DISPONIBLE`; el snapshot monetario y las exportaciones históricas no dependen de abrir ese archivo.
- Retirada es evento append-only; archivos históricos se retienen. Un fallo DB después de copiar puede dejar un blob sin referencia, nunca una falsa asociación confirmada. No se eliminan huérfanos automáticamente por riesgo de afectar referencias concurrentes.
- Backup habitual: incluye SQLite, **NO las fichas**. Paquete ZIP explícito para administrador incluye snapshot completo de ambas BUs/usuarios, todas las fichas históricas y manifest SHA256. Máximo 512 MiB y 10000 referencias; si falta una ficha, se rechaza el paquete incompleto. Sin cifrado. Restauración guiada en copia, sin importador destructivo automático.
- Migración **2 añadida**, DDL y checksum de versión **1 intactos**. Añade `ventas_importaciones`, `ventas_fichas`, `ventas_fichas_eventos`, índices/triggers; no altera registros emitidos ni tablas de Construcción. Upgrade/rollback/backup todavía NO PROBADOS.

## Commits remotos de programación de Fase 2

| SHA | Cambio |
|---|---|
| `5ccc80b0898b5dea3620be003af3ea1d90146c53` | Merge PR #5 a feature conservando ascendencia |
| `02128eee4daf9744d864ecafadefb17c46feb3e4` | Columnas explícitas y controles de estados |
| `9e88f523e02151a441636173156488431290a93a` | CSV con preview y lote atómico |
| `35b2c24f3e1525c081694981d00adf592ca43995` | Conector ACU de solo lectura |
| `3b96dcd01d641c27f4be2f125a17a5d6e9bd2b9d` | Fichas administradas, snapshots y paquete de respaldo |
| `753986ef6248fd2873cb98e345965d4a1ce0cc4e` | Límites de archivos y moneda de costos en CSV |
| `4df6dd37c9c630ccebdb7597458762ef73f74f67` | Procedencia de Construcción visible en editor |

Los commits fueron publicados mediante el conector GitHub; el árbol de fuentes remoto coincide con el local. Esto solo demuestra integridad de transferencia. El commit contenedor de este documento cierra el handoff documental.

## Pendientes explícitos

1. QA independiente: sintaxis/importación, contratos previos, flujos nuevos, concurrencia, rollback, upgrade v1→v2, Linux/Windows y cierre de workers. No hay resultado nuevo que permita declarar PASS.
2. Restauración real del ZIP, firmas/hashes, recuperación de fichas ausentes, permisos y copia consistente de base activa; por ahora existe generación y guía, no asistente de restauración automática.
3. Equivalencia profesional de costos de obra: el conector muestra referencias guardadas, no recalcula ni valida ingeniería. Unidades ambiguas quedan bloqueadas; no se incluye optimización de corte ni motor paramétrico del PR #1.
4. Importación de paquetes con composición dentro del CSV y variantes cuyo padre se cree en el mismo lote no soportadas; usar alta previa/paquetes por UI. Aprobaciones/descuentos avanzados, reservas, multi-almacén, SUNAT/POS/cloud siguen fuera.
5. Accesibilidad, rendimiento 5000 SKU/200 líneas, paginación PDF, cierre multiventana y protección del ciclo de vida de threads requieren QA real.
6. Estabilización PR #3, licencias/privacidad de seed, dependencias/updater/identidad y gate comercial siguen separados. Ningún merge a `main`, tag, release o nuevo PR en esta entrega.

[Guía de uso](VENTAS-GUIA-V1.md) · [QA posterior](QA-POST-ASTRA-PENDIENTE.md) · [Handoff YAML](ASTRA-HANDOFF.yaml).

Actualización de alcance del paquete: `f915b7dc4ed9aa28227e6c2b765aea0a987449fd` explicita en UI/manifest que no incluye uploads/imágenes ni otros archivos externos de Construcción. Es respaldo de SQLite y fichas, no un empaquetado de todos los activos de la aplicación. El downgrade a runtime v1 requiere copia anterior compatible, sin borrar tablas ni forzar checksums.
