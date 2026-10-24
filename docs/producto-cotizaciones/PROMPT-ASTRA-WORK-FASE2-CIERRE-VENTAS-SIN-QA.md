# MANDATO ASTRA WORK — FASE 2
## Correcciones verificadas + cierre de funcionalidades pendientes de Cotizaciones de Ventas

**Fecha de corte:** 2026-10-24  
**Modalidad:** CODING ONLY / NO QA / NO BUILD / NO RELEASE  
**Repositorio único autorizado:** `Em3rc0d/ingepresupuestos`  
**Rama de implementación que debes continuar:** `feat/ventas-v1-astra-work-20261024` (referencia inicial observada: `ea195c787db5fc176ba2745334c0fbab00ab1ccb`)  
**PR de correcciones independientes:** [PR #5](https://github.com/Em3rc0d/ingepresupuestos/pull/5), rama `audit/ventas-v1-state-closure-20261024`, dirigido a la feature de Ventas, no a `main`.  
**Rama principal:** `main`, actualmente `d09afecdae5b130363111943c229e3c5d3fe9639` al momento de redactar. Releer estado efectivo antes de actuar.

> **INSTRUCCIÓN EJECUTIVA:** Ya programaste el primer incremento de Ventas. **NO vuelvas a construirlo, NO crees otro cotizador y NO reescribas Construcción.** Continúa tu propio trabajo: incorpora las reparaciones descubiertas por QA, completa el backlog funcional relevante y deja todo listo para auditoría independiente posterior. Dedica recursos a código real e integración, no a suites automatizadas.
>
> **PROHIBIDO EN ESTA EJECUCIÓN:** ejecutar pytest/unittest, pruebas manuales, smoke, E2E, benchmarks, `compileall`, ruff, mypy, build, empaquetados, `pip install`, usar GitHub Actions, revisar runners, arrancar Qt para probarlo, generar PDF para comprobarlo, migrar DB reales o publicar releases/tags. **No declarar PASS ni "sistema funcional comprobado".** Puedes LEER reportes históricos de QA y código; eso no ejecuta pruebas. No crear suites nuevas para esta delegación (las existentes ya están en PR #5).

---

# 0. Qué ha ocurrido — CONTEXTO NECESARIO ANTES DE ESCRIBIR CÓDIGO

Astra entregó, a fecha 24/10/2026, **8 commits y 36 archivos** dentro de `feat/ventas-v1-astra-work-20261024`: dominio Decimal/Quantity/pricing, clientes, catálogo SKU, inventario comercial, revisiones/snapshots, PDF/XLSX y pantallas PySide6. Cierre: `ASTRA-HANDOFF.yaml`, `ASTRA-IMPLEMENTACION-ESTADO.md`, `QA-POST-ASTRA-PENDIENTE.md`; **UNVERIFIED**.

Luego se efectuó una **auditoría independiente fuera de tu encargo**:
1. Se encontró un defecto real de SQLite: `ventas_items` define **9 columnas**, pero `core/ventas/infrastructure/repositories.py` intentaba `INSERT` con **10 marcadores**. Corrección puntual en PR #5.
2. Se encontró defecto de flujo: `SalesService.new_revision` abría revisión desde `ACEPTADA`, `RECHAZADA`, `VENCIDA` o `ANULADA` al comprobar solamente que la revisión estuviera `EMITIDA`, reabriendo indebidamente un estado terminal. Corrección `doc['state'] == 'EMITIDA'` en PR #5.
3. La prueba gráfica inicialmente falló por un **fixture incorrecto** (faltaba inicializar `configuracion` de Construcción). El QA corrigió la preparación reproduciendo el arranque real, NO parcheando Ventas.
4. Se comprobó con datos temporales en **Linux** [run 40132968254](https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40132968254): **9 QA Ventas + 40 reglas críticas Construcción + 2 smoke Qt/PDF/XLSX = 51/51 PASS** con el arreglo SQL.
5. Se comprobó en **Windows** [run 40133111381](https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40133111381): **51/51 PASS** con el arreglo SQL.
6. Se verificaron **ambas reparaciones** en Windows [run 40133369044](https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40133369044): **10 QA Ventas + 40 Construcción + 2 Qt/PDF/XLSX = 52/52 PASS**.
7. Estas pruebas **NO certifican** toda la aplicación, la suite heredada completa, accesibilidad, migraciones/backups reales, rendimiento ni release. No apliques el sello "PASS" a tus cambios NUEVOS hasta otra auditoría.

**Hecho clave:** PR #5 está en borrador, base `feat/ventas-v1-astra-work-20261024`. `main` y la rama original de Astra permanecían sin las reparaciones al corte indicado. Otros trabajos separados: [PR #1 ACU paramétrico](https://github.com/Em3rc0d/ingepresupuestos/pull/1), [PR #3 estabilización Qt/SQLite](https://github.com/Em3rc0d/ingepresupuestos/pull/3), [PR #4 documentación de producto](https://github.com/Em3rc0d/ingepresupuestos/pull/4).

# 1. Lectura obligatoria — no gastes tiempo escaneando todo el repositorio

**Orden de lectura y verificación:**

1. Confirmar HEAD actual de `feat/ventas-v1-astra-work-20261024`, compararlo con el SHA original y leer PR #5 (archivos afectados y diff).
2. Leer `docs/producto-cotizaciones/ASTRA-HANDOFF.yaml` y `ASTRA-IMPLEMENTACION-ESTADO.md` en la feature.
3. Leer `docs/producto-cotizaciones/VENTAS-GUIA-V1.md` y `ASTRA-DECISIONES-OPERATIVAS.md`.
4. Leer `docs/producto-cotizaciones/CONTEXTO-MAESTRO-Y-DIAGRAMAS.md`, `ADR-002-DOS-UNIDADES-DE-NEGOCIO.md`, `MK1-SRS-CANDIDATO.md` con foco en RF-009 (CSV), RF-028 (fichas), RF-033 (ACU), RF-017 (stock) y RF-030–035 (dos BUs).
5. Consultar `docs/producto-cotizaciones/QA-POST-ASTRA-PENDIENTE.md` para saber qué dejar a QA. Los tests nuevos están en PR #5: `tests/ventas/test_sales_contracts.py`, `test_sales_ui_exports.py`; no ejecutarlos aquí.
6. Inspeccionar solo código que editarás: `core/ventas/application/services.py`, `construction_adapter.py`, `infrastructure/migrations.py`, `repositories.py`, `sqlite.py`, `views/ventas/catalog.py`, `editor.py`, `shell.py`, `views/main_window.py`.
7. Para conectar ACU, inspeccionar SELECT/estructuras efectivos en `core/database.py`: `proyectos`, `partidas`, `acu_items`, precios de recursos **por proyecto**, unidades y metrado. `core/almacen.py` es almacén POR OBRA, nunca inventario de Ventas. No ejecutar funciones mutadoras para obtener un costo.

**Pista:** el contrato de importación del conector todavía es un `Protocol` y `dataclass` en `core/ventas/application/construction_adapter.py`; no hay lector real ni botón de importación. CSV, adjuntos y ese lector están pendientes, no son fallos que el primer QA haya pretendido verificar.

# 2. Ramas y cambios — conservar el trabajo ya hecho

- **Trabajar dentro del mismo fork** y preferentemente **continuar la rama feature**. Nunca crear un repositorio nuevo, ni migrar a Next/Angular/SaaS por iniciativa propia.
- **Primera acción de código:** integrar **los cambios de PR #5** en la feature. Puedes hacer merge del PR #5 cuyo **base** es la propia feature, o trasladar el delta exacto de código/protecciones y pruebas. **NO mezclar PR #5 contra `main`**, y NO ejecutar tests. Preservar autores, contexto de commits y archivos de QA si fusionas el PR. No duplicar ni sobrescribir los tests y workflows ya existentes; sus triggers son específicos de ramas de auditoría.
- Si PR #5 ya fue integrado por otra persona, confirma el delta efectivo y no vuelvas a aplicar cambios.
- No integrar PR #1 ni PR #3 enteros. Deben permanecer independientes para evitar alterar el baseline de Construcción.
- **Aislar el resto en commits reconocibles**: CSV, adaptador ACU, fichas, integración UI y documentación/handoff. No modificar `main`, no release, no tags, no PR nuevo.
- No tocar seed/datos reales ni usar credenciales/updater/workflows externos.

# 3. Prioridad P0 — Asegurar los dos fixes verificados

En `core/ventas/infrastructure/repositories.py`, `Repository.save_item`: garantizar SQL `INSERT INTO ventas_items` con **9 placeholders** para las 9 columnas observadas en `ventas_items`; preferentemente usar lista explícita de columnas para evitar reincidencias por el orden del esquema.

En `core/ventas/application/services.py`, `SalesService.new_revision`: permitir nueva revisión solo si el estado global actual es `EMITIDA` y la revisión actual está `EMITIDA`, además de comprobar el `token` optimista. Estados `ACEPTADA`, `RECHAZADA`, `VENCIDA`, `ANULADA` son terminales conforme a la máquina de estados v1. **No cambiar silenciosamente estas reglas por comodidad.**

En la UI, confirmar que los controles "Nueva revisión" se deshabilitan o explican por qué no están disponibles para estados terminales. Mantener error de servicio como defensa última.

**Evidencia previa:** PR #5 contiene cambios probados contra 52 contratos seleccionados de Windows, pero el sistema completo aún NO está certificado. No volver a ejecutar pruebas dentro de este encargo.

# 4. Prioridad P1 — Importación CSV real de catálogo (RF-009)

**Implementar el flujo completo, no solo un `csv.reader` desconectado:**

1. Botón **"Importar CSV"** en `views/ventas/catalog.py` o una vista auxiliar claramente integrada. Abrir archivo **seleccionado por el usuario**, nunca leer automáticamente carpetas.
2. Formato documentado y descargable/generable de plantilla: `sku,nombre,tipo,unidad,unidad_fisica,precio,moneda,costo,controla_stock,descripcion` más impuestos y variantes si son seguros. Encabezados obligatorios definidos; permite columnas opcionales y reporte de ausencias.
3. Normalización: UTF-8, UTF-8 BOM, separador coma/punto y coma explícito o autodetección validada; cotizar no debe depender de configuración regional implícita. Rechazar valores no numéricos, `float` inválido, unidad incompatible, monedas no soportadas, SKU vacío, SKU repetido **dentro del archivo** y colisiones case-insensitive contra DB sin política de actualización clara.
4. **Previsualizar**: número de registros, nuevos, actualización de tarifa/datos, omitidos y errores por fila, con detalle `fila,campo,causa`. No escribir en DB durante preview.
5. **Confirmación explícita** del usuario, con estrategia `CREAR SOLO` por defecto; alternativa `ACTUALIZAR EXISTENTES` solo si valida invariantes de SKU/variantes, unidad/stock y precios. Distinguir qué campos son inmutables si hay movimientos históricos.
6. Guardado de lote en **una única transacción** mediante repositorio/servicio, sin invocar `save_item` que abra una transacción por fila. Ante fallo/duplicado tardío: rollback del lote, sin estado parcial. Registrar resumen y actor local cuando esté disponible.
7. Importar productos NO crea entradas, salidas, ajustes ni reservas de inventario. Cantidades de stock iniciales requieren pantalla de movimientos por separado, **no campo oculto dentro del CSV**.
8. Proteger ante CSV de gran tamaño con límite configurable/documentado y evitar congelar la UI al parsear. No instalar paquetes nuevos si `csv` de Python basta.
9. Documentar ejemplo sintético con varias filas y una colisión; sin precios reales de terceros.

**Definition of Done CODE ONLY:** botón conectado → seleccionar CSV → validar/previsualizar → confirmar → escritura de lote atómica → ver catálogo actualizado. No afirmar que ese flujo pasó hasta QA.

# 5. Prioridad P2 — Reutilización ACU de Construcción como origen de una venta (RF-033)

Esta es la diferenciación técnica que conecta ambas BUs sin destruir la separación de dominio. Hacerla **solo lectura y optativa**:

**Entrada:** desde editor de cotización, opción **"Añadir desde Construcción"**, idealmente diálogo que lista proyectos/partidas existentes y permite elegir una partida.

**Adaptador técnico:** implementar `ConstructionSnapshotReader` o clase concreta similar en `core/ventas/application/construction_adapter.py`, separando consulta SQL de mapping de dominio. Usar conexión SQLite `mode=ro` (o contrato read-only verificable), SELECT parametrizados, comprobación de que la partida pertenece al proyecto y cierre correcto. **Nunca** llamar `_recalcular_pu` si esa función actualiza tablas, ni escribir en `partidas`, `acu_items`, `recursos`, `almacen_ingreso`, `parte_diario_recurso`, `proyectos` u otras entidades de Construcción.

**Salida:** `ConstructionEstimateSnapshot` con `source_project_id`, `source_partida_id`, `source_hash`, `captured_at`, `source_version`, descripción, unidad, cantidad de referencia y costo técnico **opcional** con moneda conocida y procedencia. El `source_hash` debe surgir de un snapshot canónico suficientemente completo (costos relevantes, unidad, cantidad/partida y referencia), no de un `hash()` inestable. Guardar ese snapshot en la línea comercial **como dato inmutable**, por ejemplo en un campo de provenance tipado/JSON de la línea que actualmente no se use para fórmulas dimensionales; documentar nuevas columnas/migración si realmente se necesitan.

**Política:** **costo técnico ≠ precio de venta**. Nunca copiar el costo al precio unitario comercial sin consentimiento. Exigir `precio de venta` introducido explícitamente por usuario o tarifa comercial validada. Si no puedes determinar moneda, unidad compatible o si la partida es un agrupador/no cotizable, bloquear selección explicando el motivo; no aplicar conversiones por intuición. Una línea con fuente ACU no recalcula ni muta la cotización emitida cuando se modifica la obra.

**Interfaz:** diálogo de selección de proyecto/partida y vista previa de procedencia/importe técnico; confirmar → se crea línea comercial editable (precio exigido) con provenance congelada, no una relación viva ni una nueva partida en el proyecto.

**Resiliencia:** si no hay proyectos, permiso de lectura o formato heredado compatible, el selector informa estado y el cotizador comercial sigue funcionando. No introducir dependencia obligatoria de Construcción durante el bootstrap de Ventas.

**Regla de prioridad:** si el costo de implementación requiere cambiar cálculos del ACU o migraciones destructivas, **detener únicamente P2**, dejar adaptador parcial seguro y documentar bloqueo técnico explícito. No usar PR #1 paramétrico como sustituto de lector de partidas reales.

# 6. Prioridad P3 — Fichas y documentación técnica (RF-028)

El módulo ya conserva referencias textuales/supuestos de cobertura. Ahora cubrir también evidencia documental sin introducir un DMS empresarial:

- En catálogo y/o línea medible, permitir **asociar ficha técnica de producto** (PDF/imagen) seleccionada voluntariamente por usuario, con metadatos: `item_id` o `line_id`, `filename`, `mime`, tamaño permitido, hash SHA-256, fecha/fuente y actor.
- Separar **fuente original** de **supuesto no validado**. No extraer rendimientos automáticamente de PDF/imagen ni inventar cobertura; el usuario sigue introduciendo/validando el valor.
- Preferir un **almacén de archivos administrado** dentro de `USER_DATA_DIR`, con nombre seguro aleatorio/por hash y sin rutas relativas traversal. SQLite guarda solo metadatos/ruta interna, no archivos arbitrarios en directorio de código. **No copiar archivos** hasta confirmación del usuario. Limitar MIME/extensión y tamaño; no ejecutar adjuntos.
- Definir comportamiento si ficha original se mueve/borra o el usuario restaura backup: mostrar `ARCHIVO NO DISPONIBLE`, sin romper visualización de cotización ni su snapshot monetario.
- **Punto crítico:** el backup SQLite actual NO incluye automáticamente adjuntos guardados fuera de SQLite. NO afirmar que "el respaldo existente incluye fichas". Si implementas archivos administrados, añade contrato claro de backup/exportación del paquete de datos **sin modificar agresivamente backups heredados**, o deja la ficha como enlace local **NO PORTABLE** con advertencia explícita. Elegir una estrategia honesta y documentarla.
- Al emitir una cotización, la línea mantiene **referencia textual y hash de la ficha usada**, sin que modificar la ficha más tarde altere V1; no exponer rutas privadas ni costos en PDF al cliente. Adjuntar al PDF comercial solo si usuario lo solicita y se autoriza el documento.
- Migraciones `ventas_*` versionadas y no destructivas, evitando modificar el checksum de esquema ya aplicado `version=1` silenciosamente. Crear migración `version=2` con idempotencia/transacción si cambias DB. Mantener interoperabilidad con Ventas v1 existente.

**Si P3 amenaza respaldo/integridad y no puede cerrarse:** implementar solo referencias de evidencia locales con advertencia no portable y dejar adjuntos binarios `DEFERRED`, en lugar de simular que los archivos se respaldan.

# 7. Prioridad P4 — Integración UX, política de estados y seguridad de datos

- Mantener **Construcción** operando igual: `views/main_window.py` cambios mínimos; nada de reemplazar `DashboardView`, ACU, metrado, control de obra, almacén de obra o reportes.
- Ventas: "Nueva cotización", CSV, "Desde Construcción", ficha adjunta o referencia documental, revisión, versión, exportaciones y stock deben quedar en rutas de pantalla comprensibles, con controles de errores y cancelación **sin efectos secundarios**.
- No habilitar botones de funciones incompletas como si existieran: si P2/P3 quedan `DEFERRED`, etiquetarlos así o mantenerlos ocultos.
- Manejar estados de Qt, cierre de diálogo y modificaciones sin guardar. Evitar cambios masivos a la arquitectura/UI heredada.
- Separación visual entre "costo estimado" (interno) y "precio de venta" (cliente); snapshot de versión no editable; mensajes explícitos cuando impuestos no configurados impiden emitir.
- No sumar stock de Construcción al comercial, ni reservar/consumir stock al emitir, aceptar, exportar o cerrar una cotización.
- No necesitar internet, credenciales externas, nuevo login, servidor, base cloud ni LLM para estos flujos.
- Si añades importación/adjuntos, no llevar datos sensibles o fichas de terceros a logs, commits o fixtures reales.

# 8. Límites de arquitectura y migraciones

- Todo cambio comercial en `core/ventas/`, `views/ventas/` y, cuando sea estrictamente necesario, hooks de navegación de `views/main_window.py`. Mantener SQL en `infrastructure`, servicios en `application`, matemáticas puras en `domain`.
- Nuevas migraciones de SQLite `ventas_*` serán **versionadas incrementalmente**. Prohibido editar de forma incompatible la DDL ya aplicada con hash de versión 1 sin estrategia de upgrade segura.
- No modificar bases reales, seed, tabla `proyectos`, `partidas`, `acu_items`, `recursos`, sus importes ni el inventario por obra.
- Mantener `Decimal` y snapshots monetarios; rechazar cambios de unidad/SKU que invaliden histórico, sin tocar cotizaciones emitidas.
- Mantener GPL-3.0-or-later, avisos y atribución; no infraestructura/updater del productor original.
- No crear POS, SUNAT, facturación, ERP, pedidos, pasarela, SaaS, online multiusuario ni sincronización mientras no se autorice por separado.

# 9. Orden de ejecución — commits claros y sin QA

**Lote 1 — Incorporar PR #5:** registrar SHA origen/destino y dos fixes; no reescribir los contratos que ya pasaron 52 tests.

**Lote 2 — Importación CSV:** parser + validador y servicio transaccional + preview + UI conectada; commit `feat(ventas): import catalog CSV with atomic preview and confirmation`.

**Lote 3 — Adaptador ACU:** lectura real de Construcción con provenance y UI, o registro preciso de bloqueo seguro; commit `feat(ventas): read-only construction cost snapshot adapter`.

**Lote 4 — Fichas:** referencia/adjuntos gestionados y política de portabilidad/backup, o alcance seguro documentado; commit `feat(ventas): attach auditable material datasheets`.

**Lote 5 — Acabado de flujo:** controles de estados terminales, errores, formulario/UI, coherencia de snapshots; commit `fix(ventas): finalize cross-module UX and data safeguards`.

**Lote 6 — Handoff:** actualizar `docs/producto-cotizaciones/ASTRA-HANDOFF.yaml`, `ASTRA-IMPLEMENTACION-ESTADO.md`, `ASTRA-DECISIONES-OPERATIVAS.md`, `VENTAS-GUIA-V1.md` y **`QA-POST-ASTRA-PENDIENTE.md`** con matriz de pruebas NUEVAS pendientes (CSV, API de adaptador, no mutación, adjuntos, backup, migración v2, Windows, cierre). No escribir "PASS" sobre funcionalidad nueva.

**No hacer durante estos lotes:** `pytest`, import/run, `compileall`, lint, Actions, builds, screenshots automáticos, pruebas de escritorio, merges a main, releases/tags y despliegues. Puedes inspeccionar código y diffs estáticamente, pero eso no sustituye QA.

# 10. Definition of Done **de programación**, NO de QA

| Entregable | Estado esperado en código | Evidencia válida |
|---|---|---|
| PR #5 | Reparaciones integradas o ya existentes verificadas por diff | Commit/sha/diff y procedencia; las 52 pruebas son evidencia ANTERIOR |
| CSV | Parser/validación/preview, confirmación, lote atomic, UI y resumen | Rutas/classes/commits; resultados de ejecución pendientes |
| ACU | Adaptador read-only/provenance + selección UI, o bloqueo explícito | Métodos reales y límites; NO afirmar lectura si solo quedó `Protocol` |
| Fichas | Adjuntos o referencias seguras; recuperación/backup expresos | Contrato de almacenamiento, avisos y archivos |
| Construcción | No alterar tablas ni cálculos; independencia conceptual | Análisis de diff solamente; no decir "regresión PASS" sin nuevo QA |
| Cotizaciones | Mantener snapshots, estados terminales, no mutación inventario | Código y trazabilidad; nuevos casos por probar |
| QA posterior | Matriz específica para nuevo alcance y seguridad | Documento `QA-POST-ASTRA-PENDIENTE.md` actualizado |
| GitHub | Feature actualizada, commits claros; main intacta | Branch URL + SHA verificable, NO release |

**No recodificar todo el sistema** para alcanzar un "DONE". Si una funcionalidad no alcanza nivel utilizable sin sacrificar integridad, marcar `DEFERRED/BLOCKED` y entregar lo hecho con transparencia. Mantener los flujos comercial existentes y todo Construcción; no inventar "completitud".

# 11. Plantilla obligatoria de salida de Astra

```yaml
phase_2_handoff:
  repository: Em3rc0d/ingepresupuestos
  branch: feat/ventas-v1-astra-work-20261024
  head_sha: "<sha completo>"
  upstream_base: "<ref exacto; no main merge>"
  pr5:
    status: "integrated | already_present | blocked"
    code_fixes: ["ventas_items 9 columnas", "estados terminales"]
  functionality:
    csv: "IMPLEMENTED_UNVERIFIED | PARTIAL_UNVERIFIED | BLOCKED"
    acu_readonly: "IMPLEMENTED_UNVERIFIED | PARTIAL_UNVERIFIED | BLOCKED"
    datasheets: "IMPLEMENTED_UNVERIFIED | REFERENCE_ONLY | BLOCKED"
    ui_integration: "IMPLEMENTED_UNVERIFIED | PARTIAL_UNVERIFIED"
  migrations:
    versions_changed: []
    backup_compatibility: "NOT VERIFIED"
  changed_files: []
  commits: []
  constraints:
    construction_tables_written: false # only if defensible by code diff; execution not run
    quote_changes_stock: false # only if defensible by code diff; execution not run
  qa:
    current_phase_tests: "NOT RUN - user instruction"
    current_phase_build: "NOT RUN - user instruction"
    current_phase_actions: "NOT TRIGGERED MANUALLY"
    old_qa: "Windows 52 selected PASS before these feature additions"
    status: "UNVERIFIED"
  unresolved: []
  next_gate: "Independent post-Astra QA on temporary SQLite + Linux/Windows and full legacy regression"
```

**La fase queda entregada cuando hay cambios reales guardados en GitHub y el handoff completo.** No contactar upstream. Si el acceso a GitHub impide escribir, no sustituyas repo ni simules commits; declara el bloqueo exacto.

---

## Instrucción de arranque

**ASTRA: ABRE ESTE ARCHIVO, confirma las ramas, lee el PR #5 y el handoff anterior, incorpora los dos fixes y PROGRAMÁ P1 → P4 en `feat/ventas-v1-astra-work-20261024` sin ejecutar nada.** Entrega código y documentación de QA futura, manteniendo `main` intacta.