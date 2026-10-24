# Auditoría técnica de IngePresupuestos — 2026-10-24

**Repositorio auditado:** [Em3rc0d/ingepresupuestos](https://github.com/Em3rc0d/ingepresupuestos) (fork propio, sin ningún contacto con mantenedores externos).  
**Producto de origen:** `ingelibre/ingepresupuestos`, commit heredado `69445b5885aba3cf69bbaa72b9e459569b901785`, GPL-3.0-or-later.  
**Rama de mejora:** `feature/acu-parametrico-spike-mk1`.  
**Rama exclusiva de informe:** `audit/report-20261024`.  
**Resultado general:** **HOLD — suite integral roja, sin habilitar uso profesional ni merge del spike a main**.

**Política de evidencia:** distinguir `PASS real`, `FAIL real`, `observación de código` y `no ejecutado`. Un resultado verde de una sección no certifica la seguridad, despliegue o funcionalidad del producto completo.

## 1. Inventario y fuentes

- App de escritorio Python 3.12 probado en Ubuntu 24.04, PySide6/Qt, SQLite; repositorio ofrece presupuestos, ACU, metrado, cronograma, reportes, importaciones, IA y workflows de build de diferentes sistemas.
- `tests/`: **39 archivos heredados de pruebas**; en la rama de mejora, archivo adicional `tests/test_acu_parametrico.py`.
- `presupuestos_seed.db`: SQLite versionado de **4.366.336 bytes**. En esta auditoría no se inspeccionaron datos fila por fila ni se comprobó la ausencia de información personal o comercial sensible.
- `requirements.txt`: dependencias con rangos `>=`, sin lock exacto; CI resolvió PySide6 **6.12.0**, mientras que `THIRD-PARTY-NOTICES.txt` menciona **6.11.1**. **No hay garantía de resolución reproducible**.
- Workflows heredados `build-linux.yml`, `build-windows.yml`, `indices-inei.yml`, `publish-flatpak.yml`, `update-version-json.yml`; algunos publican binarios/actualizan índices y usan `contents: write` o R2 bajo sus condiciones de disparo. **No se ejecutaron** para esta auditoría.
- Nuevos workflows de auditoría: permisos mínimos `contents: read`, sin credenciales persistidas en checkout, sin release ni modificación de bases activas.

## 2. Evidencia real de GitHub Actions

| Ref | Ejecución | Resultado observable | Alcance |
|---|---|---|---|
| CI-01 | https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40104146283 | **PASS** | Registro de runner, checkout y 17 tests puros del módulo nuevo |
| CI-02 | https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40104342431 | **FAIL** | Dependencias instaladas, `pip check` PASS, 17 tests nuevos PASS; **40 tests críticos PASS**; **suite completa: 17 fail, 409 pass, 6 skip, 8 subtests pass**, además de segfault de Qt/Pytest al salir |
| CI-03 | https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40104530628 | **PASS** | Ruff de archivos nuevos PASS; `pip-audit` sin vulnerabilidades conocidas encontradas para la resolución actual; lint heredado informativo: **1.859 observaciones** |
| CI-04 | https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40105089258 | **FAIL con evidencia de aislamiento** | Casos críticos heredados ejecutados en procesos separados: cinco grupos completos PASS, dos grupos con pruebas fallidas independientes (Qt píxel, Flatpak icono), dos con errores de destrucción Qt |
| CI-05 | https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40104951309 | **PENDIENTE DE LEER RESULTADO** | Ejecución completa sobre commit original `main` sin los dos archivos nuevos, para distinguir regresiones heredadas |

**No interpretar los intentos previos con `0 jobs` como fallos del software:** eran errores de definición del primer workflow, corregidos mediante una corrida mínima real.

### CI-02: fallos de la suite integral
17 tests fallidos en estos dominios:
- Flatpak: 1. `test_appimage.py` exige SVG escalable, pero commit de versión 3.0.18 retiró el icono SVG no cuadrado para solucionar build de Flatpak. La prueba no fue actualizada.
- Cantidad/decimales ACU visual: 4 tests `test_decimales_cantidad_por_tipo.py` → `NoneType`; el módulo completo da **11 PASS** aislado (CI-04).
- Cronograma sin feriados/inicio: 2 `test_dias_no_laborables.py` → `NoneType`; módulo completo **5 PASS** aislado.
- Resumen/sub-presupuestos/Gantt: 3 `test_resumen_sub_y_gantt_columnas.py` → `sqlite3.OperationalError: no such column: ai.orden`; módulo **7 PASS** aislado, pero emitió errores Qt de ciclo de vida al salir.
- Ronda 7: 4 `test_ronda7_david.py` → `no such column: spec_adjuntos` o `ai.orden`; módulo **10 PASS** aislado.
- Orden de insumos ACU: 1 `test_orden_insumos_acu.py` → aserción de reordenamiento; módulo **6 PASS** aislado.
- Gantt/franjas: 1 `test_franjas_imagen.py` → texto/capitalización; módulo **9 PASS** aislado, pero segfault al terminar el proceso.
- Editores INEI: 1 `test_indices_inei.py` → margen visual **56 vs 57 px**; módulo 39 PASS / 1 FAIL aislado.
- `6 SKIP`: bases de datos de importación y listas oficiales no disponibles, según Pytest.

**Causa probable, no cerrada:** pruebas con efectos laterales en *import-time* (`d.DB_PATH = _tmpdb`, `cfg.DB_PATH = _tmpdb`, `d.init_db()`) modifican módulos globales de SQLite para todo el proceso pytest; ejecutar todos los archivos juntos permite colisiones entre fixtures y esquemas. El resultado positivo al ejecutarlos por separado sustenta esta hipótesis, pero no constituye una corrección ni excluye errores reales. Ciclo de vida de PySide/Qt y fuentes disponibles son problemas separados.

### CI-03: interpretación correcta del scan
- **Ruff del spike:** PASS después de corregir cuatro observaciones (imports y concatenación de advertencias).
- **Ruff heredado:** 1.859 observaciones, incluyendo importaciones, excepciones genéricas y otras reglas. NO equivalen a 1.859 vulnerabilidades ni se puede exigir corregirlas todas automáticamente.
- **pip-audit:** `No known vulnerabilities found` en el conjunto de versiones resueltas en ese momento. NO es análisis del binario, SBOM validada, revisión de dependencias empaquetadas o seguridad funcional.
- Versiones `>=` y licencias de terceros sin reconciliar con el entorno hacen que el resultado sea **temporal**; recomendable lock por plataforma/perfil o constraints mantenidos.

## 3. Hallazgos clasificados

| ID | Prioridad | Hallazgo | Evidencia | Acción / gate |
|---|---|---|---|---|
| H01 | **P1** | La suite unificada no es fiable: 17 FAIL; múltiples fallos desaparecen al ejecutar por módulo | CI-02 y CI-04 | Refactorizar aislamiento mediante fixtures con DB por test y restauración de variables de módulo; probar suite limpia; no cambiar aserciones a ciegas |
| H02 | **P1** | Qt muestra fallo de `eventFilter` y segfault al salir; incluso tras tests que pasan | CI-02 y CI-04 | Revisar ciclo de vida de QApplication, `deleteLater`, timers y widgets; separar test GUI con shutdown seguro; repetir Linux y Windows |
| H03 | **P1 — release blocker** | Fork sigue consultando servidor de versión/descargas del proyecto original | `core/update_manager.py`: `VERSION_URL=https://downloads.ingepresupuestos.com/version.json` | Antes de distribuir versión derivada, independizar canal o desactivar comprobación/autodescarga y actualizar documentación e identidad |
| H04 | **P1 — release blocker** | Workflows de publicación heredados tienen destino R2/entorno original y algunos `contents: write`; cron INEI puede escribir al branch si se habilita | 5 workflows de origen | Desacoplar triggers, limitar publicación a recursos del fork, evitar reutilizar secrets/dominios; mantener Actions auditoría `read` |
| H05 | **P2** | Prueba Flatpak contradice comportamiento del build 3.0.18 (SVG no cuadrado eliminado) | CI-02, CI-04 y commit base | Actualizar aserción según contrato real del manifiesto, y ejecutar build Flatpak sin publicación cuando sea viable |
| H06 | **P2** | Prueba visual de ancho de editor sensible a variación de un píxel | CI-02/04 56 vs 57 px | Definir política visual tolerante al entorno o medir con fuente fijada; no alterar UX sin pruebas |
| H07 | **P2** | Dependencias sin lock/constraints, y `THIRD-PARTY-NOTICES` menciona PySide6 6.11.1 mientras CI instala 6.12.0 | requirements + pip logs + Notices | Fijar entorno reproducible y sincronizar SBOM/avisos antes de redistribuir |
| H08 | **P2** | Lint heredado con 1.859 avisos; deuda importante, pero no deben remediarse masivamente sin análisis | CI-03 | Agrupar por regla, priorizar seguridad/bugs/performance y activar tolerancia incremental |
| H09 | **P2** | Seed SQLite de 4,37 MB no revisado en cuanto a contenido privado ni versión de migraciones | GitHub contents API, `core/config.py` y esquemas `core/database.py` | Inspección de esquema, migración en copia y escaneo de datos sensible sin publicar contenidos |
| H10 | **P2** | Archivo local `.session` guarda `user_id` y se restaura sin segunda verificación de contraseña | `utils/auth.py` | Evaluar modelo de amenaza de máquina compartida; cuenta con permisos de mismo usuario podría editar DB; definir si reautenticación o protección OS aplica |
| H11 | **P2** | No se han probado aquí instaladores, distribución LGPL de PySide, ejecutable Windows ni Flatpak | `THIRD-PARTY-NOTICES.txt`, manifests, Actions ejecutados | QA de paquetes sin publicar, runtime smoke y revisión de licencias/atribuciones |
| H12 | **P1 para feature** | ACU paramétrico calcula **cantidades físicas**, no integra `recurso_id`, SQLite, UI, precio unitario o políticas de aprobación | PR #1, `core/acu_parametrico.py`, 17 tests | Mantener PR #1 draft; diseñar preview/diff, control de unidad/recursos, atomicidad/rollback, protección de precios y pruebas con datos técnicos validados |
| H13 | **P3** | README principal apunta a clone/descargas/release del origen; la identidad del fork no está suficientemente marcada | README.md | Añadir aclaración de derivación independiente preservando reconocimiento y GPL, sin aparentar soporte/aval del autor original |
| H14 | **P3** | Un workflow inicial de auditoría tenía YAML inválido (0 jobs) y se corrigió con preflight simple | runs iniciales y CI-01 | Conservar workflows CI simples, agregar validación YAML antes de extenderlos; no confundir 0 jobs con fallo del código |

## 4. Evidencia de diseño de ACU
- Nuevo motor en [core/acu_parametrico.py](../../core/acu_parametrico.py): `Decimal`, validación de cantidades por unidad y dos plantillas sintéticas, ninguna salida de costo/DB.
- Pruebas en [tests/test_acu_parametrico.py](../../tests/test_acu_parametrico.py): 17 PASS, incluidas entradas inválidas y cero confusión entre `m3/und` y `m3` totales.
- Arquitectura existente: `core.database._recalcular_pu`, `cantidad_acu`, `get_acu_items`, `precio_recurso_en_proyecto`, estado editable y metrado; esos módulos son fuente de verdad económica, no copiarlos.
- **No es posible tratar un cálculo geométrico sintético como seguridad estructural certificada ni rendimiento de pintura respaldado por fabricante.**
- El PR #1 debe permanecer abierto/draft hasta controles de integración; no activar builds de producción ni merges prematuros.

## 5. Cobertura real y excluida
**Verificado por Actions:** imports/sintaxis Python, instalación de dependencias Linux, `pip check`, 17 nuevos tests de matemáticas, 40 tests críticos de negocio, suite total y ocho módulos problemáticos aislados, Ruff, pip-audit.

**No demostrado:** todo flujo end-to-end desde UI, pruebas reales de datos privados, integración de ACU paramétrico, seguridad dinámica/pen-test, autorización/roles en todos los flows, calidad de documentos exportados por todos los formatos, firma de binarios, tests Windows/macOS, build Flatpak/installer y obtención de clientes/comercialización. No inventar certificación.

## 6. Siguiente secuencia y gates
1. **G01 — Baseline estable:** resultados de main comparados, eliminar colisiones de `DB_PATH` y teardown Qt; test suite sin segfault ni fallos injustificados en CI.
2. **G02 — Versión reproducible:** constraints de Python/PySide y Pytest, actualizar licencias/avisos y controlar dependencias.
3. **G03 — Seguridad de fork independiente:** desactivar o reemplazar destinos del origin para updater, releases, cron/R2; sanitizar/comprobar seed.
4. **G04 — Compatibilidad real:** probar QA Windows/Linux, runtime mínimo y al menos una exportación; sin subir binarios públicos.
5. **G05 — ACU integrado:** cerrar SRS, adapters DB, mapeo `recurso_id`, rollback, snapshot de precios, UI; 17 tests actuales no bastan.
6. **G06 — Validez profesional/comercial:** oráculo de ingeniería y fichas técnicas, licencias, mercado y usuario/pagador. No GO comercial actualmente.

**Decisión:** mantener `main` original intacta. No mezclar ACU a `main` ni generar release hasta cerrar G01-G05; ninguna comunicación/PR a upstream. Continuar autónomamente en el fork.

## 7. Evidencia pendiente en esta captura
Ejecución de baseline original sin nuestros dos módulos: [Actions run #40104951309](https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40104951309). Actualizar este documento con su recuento final real y verificar si la cantidad/patrón de FAIL coincide con el fork. **No marcar como confirmado por antecedente o probabilidad.**
