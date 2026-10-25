# Auditoría independiente — Cotizaciones de Ventas Fase 2

**Fecha:** 2026-10-25  
**Estado:** **59/59 pruebas seleccionadas PASS en Linux y Windows; RELEASE / MERGE GATE = HOLD**.  
**Origen evaluado, sin cambios funcionales:** `feat/ventas-v1-astra-work-20261024@2a33651125a4eb81d8245d26cba1af270be95073`.  
**Repositorio exclusivo:** `Em3rc0d/ingepresupuestos`. Ninguna prueba sobre instalaciones, datos, seed ni perfiles reales.

## Alcance de la evidencia

Astra entregó en Fase 2 módulos de importación CSV, adaptador ACU de solo lectura, fichas técnicas y paquete de respaldo; **no ejecutó QA**, cumpliendo el mandato coding-only. El PR #5 se fusionó **solo a la rama feature**, no a `main`. Los 52 Windows PASS mencionados en el handoff eran **anteriores** a Fase 2.

Esta auditoría creó dos ramas de prueba derivadas del MISMO commit 2a33651, dejando la feature y `main` sin modificaciones:

1. `audit/ventas-phase2-independent-20261025` — script `tests/ventas/test_phase2_independent.py` con siete contratos sintéticos y workflow corto Linux.
2. `audit/ventas-phase2-windows-20261025` — mismo script y fuentes, workflow Windows para repetir batería crítica.
3. Este informe vive en `audit/ventas-phase2-evidence-20261025`, separada, para no volver a activar CI al guardar resultados.

## Resultados reproducibles

| Grupo de QA | Linux Ubuntu 24.04 Python 3.12 | Windows 2025 Python 3.12 |
|---|---:|---:|
| Sintaxis del incremento Ventas, vistas y `MainWindow` | PASS | PASS |
| Nuevos contratos Fase 2 (7) | **7 PASS** | **7 PASS** |
| Contratos anteriores Ventas (10) | **10 PASS** | **10 PASS** |
| Reglas críticas Construcción (40) | **40 PASS** | **40 PASS** |
| UI Qt/PDF/XLSX anterior (2) | **2 PASS** | **2 PASS** |
| **Total de pruebas pytest seleccionadas** | **59 PASS** | **59 PASS** |

**Evidencia Linux:** [Actions 40229995527](https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40229995527), job PASS. Logs: 7 passed en 0.25s, 10 passed en 0.13s, 40 passed en 1.89s, 2 passed en 1.13s.  
**Evidencia Windows:** [Actions 40230170649](https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40230170649), job PASS. Logs: 7 passed en 2.18s, 10 passed en 4.33s, 40 passed en 2.34s, 2 passed en 5.01s.

Nota de cómputo: **59 pruebas seleccionadas ejecutadas en cada sistema**, no «118 casos diferentes» y no cobertura total. No se probó compilación de instaladores ni lanzamiento de una app empaquetada. Los dos workflows fueron sesiones de QA independientes, no ejecución de pruebas por Astra.

## Qué comprueban las 7 pruebas nuevas

| ID | Contrato verificado en fixture |
|---|---|
| F2-QA-01 | CSV con previsualización de solo lectura, confirmación atómica, alta de artículo y cero movimientos de stock |
| F2-QA-02 | CSV con SKU duplicados sin distinción mayúsculas: bloquea confirmación y no crea artículos |
| F2-QA-03 | Conflicto tras cambiar catálogo entre preview y confirmación: rechaza importación obsoleta |
| F2-QA-04 | Base ventas schema v1 mínima con checksum conocido: migración a v2 preserva hash y repetición idempotente |
| F2-QA-05 | Proyecto autorizado vs ajeno en esquema sintético, snapshot de partida/ACU, precio comercial explícito y sin escrituras en las cinco tablas de obra usadas en fixture |
| F2-QA-06 | Inspección/copia de PDF sintético, SHA256, referencia, ZIP con SQLite y ficha, retiro con referencia histórica |
| F2-QA-07 | Alterar archivo entre inspección y asociación bloquea la ficha sin escribir una referencia |

Los tests heredados de Ventas incluyen cotización, snapshot, emisión, inmutabilidad, stock por movimiento explícito y GUI/export básico. **No son garantía** de completar la matriz original de 21 escenarios de Fase 2.

## Revisión estática y límites contractuales

- **Construcción**: no se modificó lógica de `core/database.py`, `core/almacen.py` ni almacén de obra para Fase 2. El lector usa SQLite `mode=ro` y `PRAGMA query_only=ON`, con filtro por `usuario_id` solo cuando esa columna existe; el control de acceso sin esa columna y en escenarios de proyecto compartido exige revisión funcional específica.
- **Cotizaciones**: crear/importar/ver ficha no llama a movimientos de stock por diseño, y la prueba sintética comprueba cero movimientos del escenario CSV. No se hizo una prueba combinatoria con todas las transiciones y todas las tablas de obra reales.
- **ACU**: utiliza el precio unitario de partida **almacenado** y conserva procedencia; NO calcula PU de nuevo, NO certifica ingeniería y NO fija precio de venta automáticamente. Importes REAL de Construcción se copian como texto; diferencias con cálculos efectivos requieren revisión técnica.
- **Fichas y backups**: la inspección valida extensión y firma básica, no sanidad de PDF o contenido profesional. Paquete ZIP contiene SQLite completa y fichas históricas de Ventas, pero **excluye uploads/imágenes y otros archivos externos de Construcción**; tampoco está cifrado. La generación de ZIP sintético PASS **no** demuestra restauración ni backup integral de todos los activos.
- **Seguridad**: los controles son locales. No se hizo pentest, threat modeling exhaustivo, verificación de privacidad ni evaluación de permisos avanzada.
- **Rendimiento**: no se midieron 5.000 SKU ni 200 líneas comerciales, ni cargas prolongadas.
- **Compatibilidad**: Linux Qt offscreen y Windows offscreen son QA de widget/servicio; no equivalen a interacción humana real con diálogos, pantallas de alta resolución, accesibilidad, lectores de pantalla o impresoras.

## Gate de publicación: HOLD por riesgos pendientes

**Críticos antes de merge/release**
1. Restauración **real** de ZIP en directorio y base temporales: revisar hash manifest, archivos ausentes/corruptos, restauración del archivo SQLite + fichas; abrir Construcción y Ventas sin cambiar valores. Nunca hacerlo sobre perfil personal.
2. Regresión **integral y aislada** de Construcción: crear/editar/accesar proyecto, ACU, metrado, cronograma, control obra, informes y cierres Qt; comparar fallos heredados existentes contra cambios nuevos. PR #3 continúa aparte.
3. QA Fase 2 de profundidad: importación CSV grande/UTF-8/ambos delimitadores, conflicto a mitad de lote, rollback forzado, atributos/costo por moneda; acceso a obra compartida/sin columna usuario_id; limitaciones de archivos 20MiB/symlinks/adjuntos corruptos; actualización en perfil vacío/v1/con cotizaciones emitidas y respaldos.
4. Prueba GUI Windows **interactiva**: operaciones largas QThread, cerrar ventana durante procesamiento, tabulación, diálogos de confirmación, saltos entre BUs y archivos con nombres Unicode. Los dos smoke existentes no cubren todo.
5. Validación de importes/tributos y política de protección de datos, licencias y marca antes de uso comercial.

**Riesgos reconocidos:** PR #3 estabilización y PR #1 ACU paramétrico permanecen separados. `main` intacta. No se hizo packaging, release, merge, generación real de documentación comercial o carga en servidor.

## Decisión de la auditoría

- **Gate seleccionado «Fase 2: contratos mínimos Linux/Windows» = PASS**.
- **Gate de integridad y recuperación = HOLD**.
- **Gate de regresión total Construcción = HOLD**.
- **Gate de lanzamiento/merge/comercialización = HOLD**.

El resultado respalda que existe una implementación funcional en los escenarios probados, **no** que todo el producto está libre de defectos.

**Enlaces para continuación:** [rama feature](https://github.com/Em3rc0d/ingepresupuestos/tree/feat/ventas-v1-astra-work-20261024) · [QA Linux](https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40229995527) · [QA Windows](https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40230170649) · [Matriz Fase 2 original](../producto-cotizaciones/QA-POST-ASTRA-PENDIENTE.md).

---

## Complemento ejecutado el 25/10/2026: recuperación real en directorios sintéticos

**Commit funcional de Astra bajo prueba: `2a33651125a4eb81d8245d26cba1af270be95073`, sin cambios.**

### Recuperación en Windows (nuevo)

- [QA inicial 40232413882](https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40232413882): 4 PASS / 1 FAIL. El fallo en el caso roundtrip provenía del **test** que no cerraba explícitamente una conexión temporal `sqlite3.connect()` antes de borrar un archivo en Windows: `PermissionError WinError 32`. No prueba corrupción del producto; corregir el harness no cambia código de Ventas.
- [Reintento con conexiones cerradas 40232631879](https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40232631879): **5 PASS / 0 FAIL** en nuevos escenarios de recuperación, más **12 PASS** en regresión de Ventas/UI/exportaciones.
- Rama exclusiva QA: [audit/ventas-phase2-restore-windows-retry-20261025](https://github.com/Em3rc0d/ingepresupuestos/tree/audit/ventas-phase2-restore-windows-retry-20261025).

**Escenarios del reintento:**
1. Crear cliente temporal implícito, artículo, cotización emitida con tasa cero explícita y ficha sintética; añadir fila a tabla `proyectos` temporal, crear ZIP.
2. Eliminar **solo** la base y las fichas temporales de origen. Leer ZIP, verificar todas las rutas relativas permitidas, tamaños y SHA-256 del manifest; reconstruir copia en **otra carpeta temporal**; abrir `SalesService` y SQLite, verificar hash de cotización/importe, ficha retirada históricamente, saldo de datos `proyectos`, `PRAGMA integrity_check`, `PRAGMA foreign_key_check`.
3. Alterar bytes del miembro SQLite en un ZIP de ensayo: verificación del manifest rechaza restauración.
4. Eliminar copia de ficha administrada: paquete de respaldo se rechaza sin sobrescribir un archivo ZIP anterior; la asociación queda marcada no disponible.
5. Inyectar fallo durante segundo `Repository.save_item` de CSV de dos artículos: rollback de ítems, tarifas y asiento de importación en una sola transacción.
6. Inyectar FK inválida: SQLite bloquea escritura parcial.

**Límite importantísimo:** `manual_verified_restore()` es **procedimiento programático del TEST**, no una función de restauración de la aplicación. No hay asistente de restauración automático, no se han probado backups de usuarios reales ni carpetas externas de Construcción. ZIP no está cifrado. El respaldo portable sigue excluyendo imágenes/uploads externos de Construcción. Debe restaurarse con la app cerrada y sobre copia verificada.

### Regresión integral heredada: intento inicial interrumpido

- [Acción 40232413882](https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40232413882): sweep por fichero, **37 módulos previstos**. Se completaron los tres primeros en PASS (`test_acerca.py`, `test_acu_aire.py`, `test_almacen.py`); `test_appimage.py` reportó **1 FAIL / 5 PASS**, aserción heredada de ruta de icono Flatpak ya citada en la auditoría original. Al empezar `test_arbol_niveles_y_duplicar.py`, el runner recibió **shutdown signal (143)**. Por tanto, **NO** hubo barrido integral ni se puede llamar regresión total completada.
- Reintento acotado en [audit/ventas-construction-sweep-fast-20261025](https://github.com/Em3rc0d/ingepresupuestos/tree/audit/ventas-construction-sweep-fast-20261025), con 15 segundos máximos por módulo y cuatro minutos de presupuesto, [Actions 40232885323](https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40232885323). **Resultado final:** 37 de 37 módulos ejecutados/intentados; **32 PASS, 3 FAIL, 2 TIMEOUT, 0 NOT_EXECUTED**. Los FAIL: `test_appimage.py` (Flatpak icono, heredado), `test_indices_inei.py` (píxel visual 56/57, heredado), `test_i18n.py` (122 cadenas nuevas de Ventas faltantes en `pt_BR`, REGRESIÓN confirmada). TIMEOUT a 15 s por módulo: `test_arbol_niveles_y_duplicar.py` y `test_diccionario_iu.py`, resultados INCONCLUSOS por límite deliberado, no FAIL demostrado. La suite integral no es PASS.

**Gate al escribir este complemento:** recuperación sintética Windows PASS; regresión integral y validación gráfica manual Windows HOLD; merge `main` y release HOLD. Escribir tests/scripts de QA en ramas de auditoría no concede autorización de modificar tablas, cálculos o política comercial de Construcción.

### Corrección de regresión nueva, sin editar Construcción

- Rama aislada: [fix/ventas-pt-br-localization-20261025](https://github.com/Em3rc0d/ingepresupuestos/tree/fix/ventas-pt-br-localization-20261025).
- [PR #6 DRAFT a la rama de Astra](https://github.com/Em3rc0d/ingepresupuestos/pull/6): traducción portugués brasileño de **122 cadenas** de Ventas en `resources/i18n/pt_BR.json`. Solo cambia el catálogo de traducciones; no los módulos de Construcción ni sus políticas económicas. Se eliminó el workflow temporal de QA del branch antes de proponer merge.
- [Test CI 40233563926](https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40233563926) **PASS: 7/7 internacionalización, 10/10 contratos anteriores de Ventas**. Valida que no faltan claves literales `tr()`/`N_()` en pt_BR, JSON sin traducciones vacías, preservación de marcadores `.format` y ausencia de traducciones a import-time. No equivale a una revisión lingüística profesional.
- **Importante:** PR #6 no está fusionado a la feature, por lo que el commit entregado `2a33651` sigue mostrando el FAIL i18n. No afirmar que ese SHA está corregido. La corrección propuesta requiere revisión/merge dirigido solo a feature cuando se autorice; `main` continúa intacta.

### Gate final consolidado — ejecución de este expediente

| Gate | Evidencia | Decisión |
|---|---|---|
| F2 contratos mínimos Linux/Windows | 59/59 cada OS, Actions 40229995527 y 40230170649 | PASS de casos seleccionados |
| Recuperación ZIP **sintética** Windows | 5/5 recuperación + 12/12 regresión, Actions 40232631879 | PASS del procedimiento probado, no restaurador de producto |
| CSV rollback/concurrencia y fichas históricas | pruebas independientes 40232631879 | PASS de fixtures; adversarial/performance restante |
| Cobertura heredada por módulos | 37 intentados: 32 PASS, 3 FAIL, 2 TIMEOUT, Actions 40232885323 | HOLD / no suite verde |
| Traducciones portugués, rama fix | 7/7 i18n + 10/10 Ventas, Actions 40233563926 | PASS en fix, sin merge |
| GUI humana Windows: cierres Qt durante trabajo, teclado, lector pantalla, visual | no se dispone de sesión interactiva Windows en esta auditoría | NOT RUN |
| Backup integral activos externos de Construcción y restore automático | no implementado; ZIP excluye uploads/imágenes Construcción | FUERA DE ALCANCE / NO CERTIFICADO |
| Merge a `main`, instalador, release, negocio | sin evidencia suficiente | HOLD |

**No corregir aserciones de Flatpak ni INEI por silenciar la suite**; ambos son fallos existentes con auditoría anterior. Revisar por separado las dos suites temporizadas, con capacidad de observar Qt real, antes de declarar regresión total sin pendientes.

### Validación gráfica manual Windows (pendiente por no disponer de escritorio interactivo)

Con **copia aislada** de la base y un `APPDATA` temporal: abrir sesión y las dos BUs; en Ventas importar CSV válido e inválido (comprobar preview y cancelación); adjuntar, retirar y exportar ficha; elegir ACU de un proyecto autorizado, verificar PU técnico y precio comercial distintos; guardar borrador, emitir y versionar; exportar PDF/XLSX y comparar importes; revisar stock antes/después; crear ZIP, cerrar app y restaurar solo en copia con manifest validado; abrir Construcción, editar/mtrar/ACU/informes, comprobar ventanas y teclado. **No realizar estas pruebas sobre datos del usuario ni afirmar PASS sin evidencia de sesión.**
