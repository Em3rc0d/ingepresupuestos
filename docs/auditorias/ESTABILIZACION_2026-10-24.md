# MK2 · Estabilización técnica del fork — 24/10/2026

**Propietario:** [Em3rc0d/ingepresupuestos](https://github.com/Em3rc0d/ingepresupuestos).  
**Rama:** `fix/fork-stabilization-20261024`.  
**Límite:** todo el desarrollo, CI, decisiones y documentación se realizan EN ESTE FORK. Sin mensajes/issues/PR al repositorio externo. Conservación de GPL-3.0-or-later, autoría y avisos.

**Estado provisional:** correcciones de CI/UX/distribución implementadas y validadas parcialmente; **no se ha demostrado RELEASE READY**. Consultar pruebas y estados exactos antes de integrar esta rama en `main`.

## 1. Línea de base y comparabilidad

Auditoría previa (en `docs/auditorias/AUDITORIA_TECNICA_2026-10-24.md`):
- Código principal heredado: **392 PASS / 17 FAIL / 6 SKIP** en ejecución conjunta (run [40104951309](https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40104951309)).
- Rama del generador ACU puro: **409 PASS / 17 FAIL / 6 SKIP**, mismo conjunto de fallos (run [40104342431](https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40104342431)).
- Prototipo ACU puro: 17/17 pruebas; **NO está fusionado** a `main` ni a esta rama. Es una funcionalidad aparte.
- Causa de múltiples fallos: los tests heredados cambian `core.database.DB_PATH` y `core.config.DB_PATH` **durante el import**, contaminando otras pruebas ejecutadas en el mismo intérprete. Las pruebas por archivo demuestran una diferencia reproducible. 
- Excepciones: fallos específicos de Flatpak y un píxel en editor, comportamiento del ciclo de vida de Qt. No asumir que el aislamiento arregla todas las causas.

## 2. Cambios realizados

| Componente | Acción implementada | Verificación / restricción |
|---|---|---|
| `scripts/audit_test_files.py` | Cada archivo de pytest corre en proceso aislado con `XDG_DATA_HOME`/`APPDATA`/`HOME` temporales; timeout y resultado estructurado. **No omite fallos, errores de salida ni segfaults** | [Actions 40107565245](https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40107565245): **8/8 módulos críticos terminan con exit code 0** tanto en PySide6 6.11.1 como 6.12.0; en ambos se aprueban 40 tests críticos de negocio. |
| `views/_catalogo_base.py` | Extiende en 1 px ambos bordes del editor durante edición, para evitar corte de cifras con las métricas de Qt | `tests/test_indices_inei.py`: **40 PASS** por módulo en ambas versiones Qt, incluido test 56 vs 57 px heredado |
| `tests/test_appimage.py` | Comprueba icono PNG 256×256 correcto en manifiestos; hace cierre explícito de vistas temporales de Acerca de | Módulo con **6 PASS y exit 0**, tanto Qt 6.11.1 como 6.12.0; no equivale a compilar Flatpak/AppImage |
| `core/update_manager.py` | Eliminado feed del productor original como valor por defecto; habilitar solamente con `INGEPRESUPUESTOS_VERSION_URL` HTTPS opt-in. No anuncia versiones cacheadas ajenas si está inactivo. | 5 tests nuevos de política de actualización pasan en ambas versiones; la configuración propia es para futuro release, NO disponible todavía |
| `.github/workflows/build-linux.yml`, `build-windows.yml`, `indices-inei.yml`, `publish-flatpak.yml` | Jobs heredados de publicación automática y destinos R2 bloqueados para repos distintos del origen. `update-version-json.yml` ya tenía guard upstream. | Job de políticas PASS: no subidas, no releases, no escrituras por cron desde el fork. **No** se validaron builds de instaladores |
| `scripts/audit_seed.py` | Abre seed SQLite `mode=ro&immutable=1`; comprueba integridad y FKs, genera indicadores de columnas potencialmente sensibles sin imprimir valores | [Actions 40107975566](https://github.com/Em3rc0d/ingepresupuestos/actions/runs/40107975566): **integrity_check=ok**, FK violations **0**, **26** tablas, **4.366.336 B**; se observaron campos `cliente` y `nombre` poblados. No prueba anonimato |
| `.github/workflows/fork-stabilization.yml` | Matriz Linux de versiones Qt y seguridad; solo lectura | Resultado confirmado PASS en run 40107565245 |
| `.github/workflows/fork-full-audit.yml` | Línea de regresión completa: todos los archivos de tests ejecutados individualmente + inspección de seed | **Resultado completo pendiente** al redactar: run 40107975566 |
| `README.md` | Aviso de fork independiente, no avalado ni distribuible como release verificado | Atribución/branding básico; faltan revisar pantallas, dominio y otros enlaces propios al preparar lanzamiento |

## 3. Riesgos reales todavía abiertos

1. **Suite conjunta monolítica:** sigue teniendo contaminación de variables SQLite por diseño de tests import-time. La arquitectura del test runner aislado sustituye al comando monolítico como gate de CI, pero no reestructura por sí sola los 39 archivos heredados. Documentarlo.
2. **Qt y cierre:** los 8 módulos problemáticos terminan correctamente en el entorno aislado, en ambas versiones; sigue pendiente reproducir ciclo completo con ventana principal, múltiples diálogos y Gantt antes de certificar estabilidad.
3. **Dependencias:** `requirements.txt` permite actualizaciones `>=` y no usa lock transitorio completo por SO; se probaron 6.11.1 y 6.12.0, pero eso NO demuestra que cualquier versión futura funcione. Decidir constraints/lock y actualizar avisos antes de distribuir.
4. **Seed:** integridad estructural confirmada, pero hay nombres/cliente no vacío; el scan no descubre PII en valores ni certifica dataset público/sanitizado. Antes de publicar binarios, revisar procedencia y licencia de catálogos/semilla.
5. **Identidad y distribución:** workflows de publicación neutralizados; se requiere construir nuestros propios canales/dominios, revisar `THIRD-PARTY-NOTICES.txt` y cumplimiento Qt LGPL, y ejecutar packaging Smoke. Todavía existen enlaces e identidad del origen en pantallas/scripts/manifiestos heredados. Evitar confusión con versión oficial.
6. **Seguridad aplicación:** pendientes revisión de `utils/auth.py`, estado de sesión, permisos de proyecto, consultas SQL, backups y restauración en datos reales. No existe pentest.
7. **Calidad legado:** 1.859 observaciones Ruff en auditoría original son reglas mixtas, no 1.859 vulnerabilidades. No ejecutar autorewrites masivas sin pruebas.
8. **ACU paramétrico:** sigue aislado en [PR #1](https://github.com/Em3rc0d/ingepresupuestos/pull/1); aún no hay mapeo a `recurso_id`, persistencia, interfaz, diff/rollback ni oráculo profesional para calculadora de obra.

## 4. Criterios de aceptación de esta estabilización

- [x] Fork propio verificado y atribuciones intactas.
- [x] 8 grupos históricamente inestables salen 0 en proceso aislado con dos versiones Qt.
- [x] Los tests críticos `test_reglas_negocio.py` y `test_core.py` pasan (40) en ambas versiones.
- [x] Pruebas de updater propio y política CI PASS.
- [x] Integridad SQLite del seed y FK PASS, sin extracción de valores de usuarios.
- [ ] **Ejecución completa** de tests aislados sobre todos los archivos y resultados categorizados.
- [ ] Lock de dependencias revisado e instaladores comprobados.
- [ ] Cierre Qt real en integración GUI/e2e y regresión multiOS.
- [ ] Auditoría de privacidad y derechos del seed para posible distribución.
- [ ] Validación profesional de ACU y protección transaccional antes de integrarlo.

### Regla de merge
Aprobamos mejoras de **seguridad y pruebas reproducibles** solo con evidencia suficiente; **NO** mezclar desarrollo paramétrico experimental ni afirmar que el software está listo para contratos o release mientras existan gates abiertos.

## 5. Próxima decisión

Revisar `full-isolated-results.json` del run integral y las brechas de cobertura. Si suite aislada pasa, podemos fusionar la estabilización (CI + updater + UX + pruebas) con anotación explícita de riesgos pendientes. Después de ello abordar la arquitectura de integración ACU y auditar instaladores/datos bajo su propia rama.
