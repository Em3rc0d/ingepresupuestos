# Contrato de QA posterior — NO EJECUTADO

Esta entrega fue CODING ONLY por orden explícita del propietario. **Ningún comando de este documento fue ejecutado. No existen pruebas nuevas de Ventas todavía.** Este plan corresponde a otra sesión con autorización de QA. No ejecutar contra la base real, no abrir/copiar encima de la semilla y no activar GitHub Actions/releases por defecto.

## Preparación independiente

1. Fijar SHA remoto de la rama entregada. Leer mandato, decisiones y estado. No integrar PR #1/#3 para ocultar o confundir fallos.
2. Usar directorio de datos desechable (`XDG_DATA_HOME` en Linux; `APPDATA` en Windows), base SQLite temporal explícita para `SalesService(path, actor, readonly)`. Preparar una base vacía con sqlite3 para el dominio: `SalesStore` usa `mode=rw` y deliberadamente no crea archivos inexistentes.
3. Para integración con Construcción, crear fixture sintético del esquema real o una copia consentida con respaldo. El esquema comercial no necesita seed ni tablas de obra en pruebas de servicios. Nunca imprimir PII de fixtures reales.
4. Registrar Python/Qt/SQLite/OS/dependencias. Instalar dependencias solo en esa sesión. Crear tests de Ventas en `tests/ventas/` con fixtures propias; no cambiar `core.database.DB_PATH` durante imports.
5. La suite heredada tiene contaminación import-time documentada. Separar baseline idéntico de nuevos fallos; la herramienta de ejecución aislada vive en PR #3, no asumirla aquí.

## Matriz de verificación a escribir y ejecutar

| Grupo | RF / RNF / invariante | Fixture/oráculo y aceptación pendiente |
|---|---|---|
| Q01 decimal | 010,013–015; RNF04 | HALF_UP, USD/PEN/EUR/JPY; rechazo float/bool/NaN/infinito, exponentes y límites; precios de seis decimales y cantidades visibles |
| Q02 geometría | 005,010–012; INV04/08 | m/mm/cm, m²/cm²/mm², m³/L/mL, kg/g; masas incompatibles; filas y piezas; división por cero, valores extremos |
| Q03 cobertura | 011–012; S03 | Datos sintéticos 120 m², 2 manos, 8 m²/L/mano y 10%: 33 L; contenido 4 L, presentación cerrada: 9 envases y 36 L; fuente explícita, restante 3 L; fracciones sin cierre |
| Q04 dinero | 014–015; RNF08 | Descuento por línea/global porcentaje e importe; 100%, 0%, negativos, descuento mayor que base, líneas cero, varias tasas, inclusive/exclusive; mayor resto con empate por posición y conciliación exacta por unidad monetaria |
| Q05 catálogo | 007–008,013,034 | SKU repetido case-insensitive, SKU estable, variantes sin ciclos, desactivados fuera de selector, tarifas PEN/USD separadas y costo desconocido; no confundir costo y precio |
| Q06 paquetes | 020 | Un nivel, componentes duplicados, servicios, rechazo ciclo/paquete anidado; sumar precio comercial una vez; stock agregado por SKU de componentes |
| Q07 migración | 025,030–032,035; RNF02/03 | Base temporal sin Ventas → migrar dos veces; hash/version ajena; fallo tras DDL parcial → rollback; obra idéntica; archivo inexistente/protegido/bloqueado/sin espacio → error manejado |
| Q08 números | 001,025 | Dos conexiones compitiendo; secuencia anual única sin MAX+1 exterior; error de guardado no deja cabecera/líneas/eventos/contador parcial |
| Q09 inventario | 016–019,035 | Sin seguimiento ≠ no verificado ≠ cero registrado; entrada 6, salida 2, ajuste ±; motivo obligatorio; invitado bloqueado; negativos rechazados; eventos append-only; cambio de unidad con ledger bloqueado |
| Q10 no efectos | 017,029–030,032,035; INV02/05 | Hash/conteo de movimientos comerciales y todas tablas obra antes/después de crear/guardar/emitir/exportar/aceptar. Esperado: ninguna mutación del ledger ni obra |
| Q11 emisión | 003,015,021–025; RNF06 | Borrador sin impuesto admitido; emisión sin regla/emisor/cantidad/cliente bloqueada. Guardar→preview→emitir mismo fingerprint. Cambio concurrente de borrador bloquea emisión; cambio catálogo/cliente no altera snapshot previsualizado |
| Q12 inmutabilidad | 022,027; INV06 | Intentar SQL UPDATE/DELETE a revisión emitida y líneas; INSERT en revisión emitida; mover línea entre revisiones; todos bloqueados por trigger. Modificación externa detectada por sello al abrir/exportar |
| Q13 revisiones | 022,024,026–027 | V1 emitida, modificar precio catálogo, V2 borrador/editada/emitida; V1 mantiene mismo SHA/importes/cliente; diff de cantidades/unidad/precio/orden/tasa/cabecera. Transiciones inválidas/aceptar vencida rechazadas |
| Q14 exportación | 021,023; RNF08 | PDF/XLSX de V1/V2 elegidas; mismos textos, importes, moneda, condiciones, impuesto y versión que snapshot; costos internos/componentes excluidos. Texto `=HYPERLINK(...)` queda texto en XLSX |
| Q15 formato | 023; RNF07/08 | Descripciones largas/200 líneas/acento/ñ/símbolos/no latinos; paginación, ancho/filas, sello; Excel decimales textuales exactos. Ruta cancelada, extensión, sobrescritura consentida, permisos y destino abierto; error deja original íntegro |
| Q16 UI | 001–008,021,025–026,031; RNF07 | Login existente → Ventas → cliente → catálogo → línea libre/SKU/servicio/medidas → cálculo → guardar → reabrir → preview → emisión → PDF. Cerrar/Escape/logout con cambios conserva o pregunta; ningún botón inerte |
| Q17 accesibilidad | RNF07 | Solo teclado, Tab/Shift+Tab/Escape, etiquetas, lector de pantalla, contraste, redimensionamiento/zoom, scrollbar de formularios y sidebar en ventana pequeña |
| Q18 offline | RNF01; INV12 | Red bloqueada: todos los flujos de Ventas operan sin API/IA. Informar llamadas remotas heredadas si aparecen sin atribuirlas a Ventas |
| Q19 fallo aislado | 030–031; INV01 | Forzar migración incompatible/exception de widget; aparece reparación y reintento; Construcción abre y conserva proyectos sin crear registros comerciales |
| Q20 restauración | RNF03/12 | Backup existente incluye ventas; restaurar en copia y abrir Construcción/Ventas. Verificar semilla sin modificación, no exponer contenidos |
| Q21 rendimiento | RNF09 | 5.000 SKU, 200 líneas, historial extenso de movimientos; tiempos y bloqueo de event loop medidos en PC objetivo, sin umbrales inventados |
| Q22 legado | 030; INV01/03 | Abrir/crear/editar proyecto, ACU, metrado, cronograma, control obra, exportaciones y logout; golden valores idénticos al source_ref |

## Comandos orientativos PARA OTRA SESIÓN

No se han creado `tests/ventas` ni ejecutado estos comandos. Son rutas de trabajo propuestas para el auditor, después de escribir fixtures y revisar el entorno:

```bash
# Solo en QA, con datos temporales y después de crear los tests:
python -m pytest tests/ventas -q
# Analizadores/compilación solo si la nueva sesión los autoriza:
python -m compileall -q core/ventas views/ventas
# Ejecutar cada módulo heredado en su propio proceso con aislamiento de datos;
# no usar el resultado monolítico como prueba concluyente de regresión.
python -m pytest tests/test_core.py -q
python -m pytest tests/test_reglas_negocio.py -q
```

El arranque `python main.py` también pertenece exclusivamente al QA posterior, configurando primero datos desechables. No abrir la app con la base personal para comprobar si migra.

## Evidencia de salida requerida

SHA exacto, OS/Python/Qt/SQLite, fixtures, comandos reales, logs, resultados y fallos separados de baseline; archivos de comparación PDF/XLSX e invariantes de obra/ledger. Marcar cada fila PASS/FAIL/BLOCKED con evidencia; no convertir lectura de código en PASS.

Gate actual: **HOLD — UNVERIFIED**. No merge, release ni piloto con datos operativos hasta aprobación independiente. RF-009, RF-033 y adjuntos de RF-028 son backlog, no fallos que se puedan esconder bajo pruebas omitidas.
