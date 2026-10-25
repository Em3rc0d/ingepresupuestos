# Contrato de auditoría posterior a Fase 2 — NO EJECUTADO

**2026-10-25 · Gate HOLD / UNVERIFIED.** Durante Fase 2 no se ejecutó prueba alguna, importación de módulos, Qt, build, compilación, linter, instalación de dependencias ni GitHub Actions. No se crearon tests nuevos. Los contratos existentes `tests/ventas/test_sales_contracts.py` y `test_sales_ui_exports.py` fueron incorporados sin cambios desde PR #5, con su historial/workflows.

El PR #5 reportó previamente **52 pruebas seleccionadas Windows aprobadas** (10 Ventas, 40 Construcción, 2 UI/exportación) con SQL/estados corregidos. Ese resultado no cubre esta implementación nueva ni es certificación global. No consultar/relanzar runners para suplir QA de esta fase.

## Preparación del auditor

1. Fijar SHA exacto de la feature entregada. Leer estado, decisiones y guía. No mezclar PR #1/#3 para cambiar el baseline.
2. Bases, directorios y archivos **sintéticos y temporales**. Para servicios, crear archivo SQLite temporal explícito; SalesStore usa `mode=rw`. Para GUI, reproducir `core.database.init_db()` en una copia aislada, como hace el fixture del PR #5. No usar DB_PATH personal ni tocar seed.
3. Registrar OS/Python/Qt/SQLite/dependencias y SHA. Preparar fixtures de esquema v1 exacto y construcción realista: precios `acu_items.precio` por proyecto, unidades/monedas válidas/ambiguas, usuarios, proyectos compartidos/ajenos y archivos PDF/PNG/JPEG sintéticos.
4. Autorizar QA en una sesión independiente antes de ejecutar herramientas. Conservar tests heredados; crear pruebas nuevas de Fase 2 solo en esa sesión. Separar fallos del baseline de las regresiones nuevas.

## Matriz nueva obligatoria

| ID | Contrato / RF | Prueba y oráculo pendientes |
|---|---|---|
| F2-01 | PR #5, estados | Repetir contratos existentes; ACEPTADA/RECHAZADA/VENCIDA/ANULADA rechazan revisión con token actual y no mutan evento/estado/snapshot. EMITIDA permite V2. UI deshabilita revisión terminal; duplicación crea otro documento |
| F2-02 | RF-009, CSV | UTF-8/BOM, coma/punto y coma, comillas/acentos/saltos de línea; encabezados ausentes/duplicados/desconocidos, CSV vacío/malformado. Preview no crea artículos/precios/importaciones ni movimientos |
| F2-03 | RF-009, números | Punto decimal, rechazo de coma decimal, vacíos, NaN/infinito/exponentes/float/negativos/seis decimales, unidad/moneda/tipo inválidos; stock inicial/columnas ocultas rechazadas |
| F2-04 | RF-009, identidad | SKU vacío/repetido case-insensitive dentro del archivo. Crear solo omite existentes de manera visible. Actualizar respeta SKU estable, variantes/padre, movimientos anteriores y paquetes. Padre del mismo lote se rechaza; paquete sin componentes no se crea |
| F2-05 | RF-009/013/034 | Actualizar PEN/USD sin heredar costo de otra moneda. Opcionales ausentes conservan lo permitido; impuesto parcial se rechaza, impuesto vacío queda sin configurar. Histórico V1 no cambia |
| F2-06 | RF-009, atomicidad | Error a mitad de lote/colisión tardía/disco ocupado → rollback de artículos/tarifas/resumen. Cambio concurrente de catálogo/precios/ledger invalida token de preview. Registrar resumen/actor/hash al confirmar una sola transacción |
| F2-07 | RNF-09, CSV | Límites 5 MiB/5000 filas/celda 8192 caracteres. Archivo mayor se rechaza. Parseo en worker, UI recibe resultado en hilo GUI; cancelar selección/preview no escribe; confirmar no admite doble ejecución |
| F2-08 | RF-033, permisos | Proyecto/partida pertenecientes, títulos, proyectos ajenos/compartidos, admin, moneda y unidad desconocidas. Schemas heredados sin columnas opcionales producen fallback documentado o error aislado |
| F2-09 | RF-033, solo lectura | Inspeccionar `mode=ro`/query_only. Capturar hash/conteos de TODAS tablas de Construcción y ledger comercial antes/después de listar/previsualizar/importar/guardar/emitir. Ninguna escritura. Prohibir llamada a `_recalcular_pu` y otros mutadores |
| F2-10 | RF-033, costo | Distintas tarifas de recurso por proyecto, fallback a catálogo y PU guardado divergente del recalculado: el snapshot etiqueta GUARDADO, incluye datos relevantes y no simula equivalencia. Precio de venta nunca autocompletado desde costo; costo no representable no produce margen inventado |
| F2-11 | RF-022/027/033 | Hash canónico estable sin timestamp de captura; cambia con metrado/unidad/costo/ACU/reglas relevantes. Cambio de obra tras V1 no altera V1 ni exportación. Modificación de provenance, unidad o moneda bloqueada al guardar |
| F2-12 | RF-028, selección | PDF/PNG/JPEG sintéticos válidos y firmas incompatibles, SVG/HTML/executable rechazados, vacío, >20 MiB, nombre/traversal/symlink. Inspección no copia; cancelar no asocia. Máximo 10 fichas activas por artículo/línea |
| F2-13 | RF-028, confirmación | Archivo cambiado/movido antes de confirmar bloquea. Confirmación conserva SHA/tamaño/MIME/fecha/fuente/actor, nombre interno por hash. Reuso de mismo contenido entre artículos no lo borra. Fallo DB tras copia deja a lo sumo blob huérfano, sin asociación parcial |
| F2-14 | RF-028, histórico | Retirar asociación agrega evento, no borra metadatos/archivo/histórico. Capturar fichas en borrador es explícito. V1 congela referencias; borrar/alterar original no afecta copia. Borrar/alterar copia → ARCHIVO NO DISPONIBLE, revisión/totales todavía accesibles |
| F2-15 | RF-021/023, export | Preview/PDF/XLSX de revisión elegida con cifras idénticas, referencias nombre/hash separadas, sin rutas privadas/costos/provenance interna ni adjuntos automáticos. Fórmulas Excel siguen texto. Descripciones/refs largas y paginación/acentos por comprobar |
| F2-16 | Migración v2 | Fixture v1 con checksum original exacto y documentos emitidos → upgrade2, repetir sin efecto, preservar firmas/IDs/totales/ledger. Esquema vacío →1→2. Checksum ajeno, hueco de versiones o fallo entre DDL → rollback íntegro |
| F2-17 | RNF-03, respaldo | Backup SQLite habitual no contiene archivos, advertencia visible. Paquete admin incluye SQLite consistente y TODAS fichas históricas, manifest/hash/tamaño; no incluye otros uploads de Construcción y lo declara. Invitado/no admin bloqueados |
| F2-18 | Respaldo/recuperación | Restaurar paquete en directorio temporal con app cerrada; verificar hashes/paths y reabrir ambas BUs, documentos y refs. Ficha ausente/alterada, ruta cambiada, >512 MiB/>10000 refs, permisos y disco lleno bloquean paquete completo sin reemplazar destino anterior |
| F2-19 | Qt/cierre | Recorridos CSV/ACU/fichas/paquete completos en Windows y Linux. Diálogos modales, Tab/Escape, errores, campos sin guardar, selección cancelada, slots y cierre/logout mientras worker activo. No destruir/terminar QThread activo; no acciones dobles ni callbacks a widgets destruidos |
| F2-20 | RF-017/030/035 | Repetir 40 reglas críticas base y regresión real crear/abrir/editar ACU/metrar/programar/control obra/exportar. Importar CSV/ACU/fichas/cotizar/emitir/aceptar/exportar nunca crea salida ni reserva comercial o de obra |
| F2-21 | RNF-01/07/09 | Flujos offline, lector de pantalla, teclado, contraste, zoom/redimensión, 5000 SKU/200 líneas y referencias extensas. Medir bloqueos/tiempos reales; no inferir cumplimiento por usar threads |

## Ejecución sugerida SOLO PARA LA SIGUIENTE SESIÓN

No se corrió ninguno de estos comandos. Los archivos de tests Fase 2 aún deben ser escritos por el auditor:

```bash
# Datos temporales/aislados preparados antes de cualquier arranque:
python -m pytest tests/ventas/test_sales_contracts.py -q
python -m pytest tests/test_reglas_negocio.py tests/test_core.py -q
python -m pytest tests/ventas/test_sales_ui_exports.py -q
# Luego ejecutar la suite nueva de CSV/ACU/fichas/paquetes/migración2 que cree QA.
```

La suite heredada puede contaminar DB_PATH durante imports; aislar procesos/datos y contrastar baseline. `compileall`, linters, instalación de dependencias y arranque `python main.py` quedan a criterio/autorización de esa nueva sesión; no se realizaron aquí. No activar Actions ni empaquetados como sustituto de pruebas de datos.

## Resultado exigible

SHA, OS/versiones, fixtures, comandos y resultados reales por fila PASS/FAIL/BLOCKED; comparación de datos/hashes antes/después, documentos exportados y evidencia de restauración/cierre Qt. Si un oráculo de costo de obra no coincide, preservar la referencia guardada y reportar el límite: no modificar Construcción para que el test pase. No hay GO a main/release/piloto operativo en esta entrega.
