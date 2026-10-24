# CONTRATO PARA AGENTES — IngePresupuestos / Construcción + Ventas

> Archivo de handoff para LLM, agentes de arquitectura, implementación, QA y documentación.  
> **Versión contextual:** 2026-10-24 · **Actualización de implementación:** el mandato `PROMPT-ASTRA-WORK-IMPLEMENTACION-SIN-QA.md` autorizó código v1 en rama aislada, sin QA/merge/release. Consultar `ASTRA-IMPLEMENTACION-ESTADO.md`; los gates de prueba y mercado siguen abiertos.  
> **Documento maestro con diagramas:** [CONTEXTO-MAESTRO-Y-DIAGRAMAS.md](CONTEXTO-MAESTRO-Y-DIAGRAMAS.md).  
> **Repositorio permitido:** `Em3rc0d/ingepresupuestos`; ningún otro repositorio.

## 1. System context (determinista y explícito)

```yaml
project:
  identity: "Em3rc0d/ingepresupuestos"
  type: "Fork derivado GPL-3.0-or-later"
  date_context: "2026-10-24"
  name: "IngePresupuestos (nombre heredado; branding futuro abierto)"
  platform_current: "Python 3 / PySide6 (Qt) / SQLite local"
  platform_future_web: "NO APROBADO"
  release_ready: false
  commercial_viability_proven: false

product_architecture:
  status: "ACCEPTED - PRODUCT SCOPE ONLY"
  topology: "una aplicación con dos unidades de negocio independientes"
  business_units:
    - key: "construction"
      label: "Construcción"
      status: "EXISTING; preservar y estabilizar"
      owns: [proyectos, partidas, ACU, metrados, recursos, cronogramas, control_de_obra, almacen_por_proyecto, reportes]
    - key: "sales"
      label: "Cotizaciones de Ventas"
      status: "IMPLEMENTED SOURCE - UNVERIFIED; isolated implementation branch"
      owns: [clientes, cotizaciones, revisiones, lineas_mixtas, catalogo_SKU, precios_comerciales, stock_comercial, documentos]
  reuse: "shared kernel mínimo, funciones puras caracterizadas y adaptadores explícitos"
  cross_unit_rules:
    writes_sales_to_construction: "PROHIBIDO"
    writes_construction_to_sales: "PROHIBIDO por defecto"
    adapter_construction_to_sales: "PROPUESTO, solo lectura y snapshot"
    universal_quote_is_construction_project: false
    stock_by_project_equals_commercial_stock: false

repository_state:
  baseline_main:
    tests: "392 PASS, 17 FAIL, 6 SKIP (monolítico original, 2026-10-24)"
    evidence: "docs/auditorias/AUDITORIA_TECNICA_2026-10-24.md"
  prs:
    - id: 1
      scope: "motor ACU parametrico PURO; PROTOTYPE"
      status_at_cutoff: "DRAFT / OPEN"
      tests: "17 nuevos PASS sobre suite original; NO UI, NO BD"
    - id: 3
      scope: "estabilizacion Qt/SQLite, updater y controles de fork"
      status_at_cutoff: "DRAFT / OPEN; QA Linux/Windows no completamente verde"
    - id: 4
      scope: "ADR-002, MK0/MK1, contexto visual y contrato de agentes"
      status_at_cutoff: "DRAFT / OPEN; docs ONLY"
  production_sales_module_exists: false
  unverified_sales_source_exists: true

gates:
  decided:
    - "dos unidades de negocio al mismo nivel"
    - "conservar funcionalidades y datos de Construcción"
    - "añadir Ventas sin reinterpretar tablas de Construcción"
    - "investigar reutilización de cálculos/unidades/exports, no asumirla"
    - "solo en el fork; sin comunicación upstream"
  open:
    - "segmento comercial validado"
    - "SRS de Ventas congelado"
    - "estados y numeración comercial"
    - "inventario comercial: fuente y granularidad"
    - "impuestos y políticas de redondeo"
    - "roles y permisos"
    - "contratos shared kernel y adaptador"
    - "estrategia migraciones/backup"
    - "QA de PR #3 y empaquetado"
  authorization_to_implement_sales: true
  implementation_authority: "Explicit owner mandate PROMPT-ASTRA-WORK-IMPLEMENTACION-SIN-QA.md; P0-P4 only, P5 optional"
  qa_execution_authorized_this_delivery: false
  merge_release_authorized: false
```

**La autorización de implementación está limitada al mandato coding-only. No convierte el SRS candidato en aprobado comercialmente ni cierra pruebas/mercado. Las reglas históricas que impedían crear modelos/pantallas quedan supersedidas para este incremento por la instrucción explícita del propietario; las restricciones de separación de BUs y no publicación siguen vigentes.**

## 2. Fuentes a leer en orden

1. [ADR-002-DOS-UNIDADES-DE-NEGOCIO.md](ADR-002-DOS-UNIDADES-DE-NEGOCIO.md) — decisión de primer nivel (autoridad producto).
2. [CONTEXTO-MAESTRO-Y-DIAGRAMAS.md](CONTEXTO-MAESTRO-Y-DIAGRAMAS.md) — contexto total, diagrams y estados.
3. [MK0-VISION-Y-ALCANCE.md](MK0-VISION-Y-ALCANCE.md) — hipótesis, alcance y viabilidad (no resultados reales de mercado).
4. [MK1-SRS-CANDIDATO.md](MK1-SRS-CANDIDATO.md) — RF-001..RF-035, RNF-01..RNF-12, reglas RB, tests (NO congelado).
5. [AUDITORIA_TECNICA_2026-10-24.md](../auditorias/AUDITORIA_TECNICA_2026-10-24.md) — CI y defectos observados, con links a Actions.
6. Código real **en `main`** para comprobar comportamiento actual: `main.py`, `core/database.py`, `core/config.py`, `core/almacen.py`, `core/requerimientos.py`, `views/proyecto_view.py`, `views/metrados_view.py`, `utils/formatting.py`.
7. PR #1 para código ACU paramétrico aislado y PR #3 para estabilización, siempre desde sus ramas respectivas. Evitar asumir que están fusionados.

## 3. Terminología canónica y equivalencias prohibidas

| Término | Definición contractual | No confundir con |
|---|---|---|
| Presupuesto de obra | Estimación técnico-económica por proyecto/partida | Cotización comercial con cliente/vigencia |
| ACU | Recursos y cantidades de una unidad de partida | Un SKU o una línea de venta arbitraria |
| Recurso de Construcción | `recursos` (MO/MAT/EQ/SC), costo por proyecto | Producto comercial SKU y variante |
| Metrado | Medida técnica que cuantifica una partida | Cantidad de unidades comercializables sin conversión |
| Catálogo comercial | Ítems comercializables, precios de venta, variantes | Biblioteca de costos unitarios de obra |
| Costo | Gasto técnico/comercial estimado | Precio de venta al cliente |
| Precio de venta | Importe ofertado por unidad comercial | Precio unitario de ACU automáticamente |
| Stock de obra | Ingreso menos consumo registrado por proyecto | Stock de un almacén de venta |
| Stock disponible comercial | Existencia física menos reservas explícitas si aplican | Cantidad de cotización o stock no sincronizado |
| Cotización | Oferta comercial versionable, no vinculante con inventario | Orden, salida, comprobante tributario |
| Consumo previsto | Cantidad técnica estimada de material | Envases o unidades vendidas |
| Revisión emitida | Snapshot inmutable y exportable | Borrador editable |
| Shared kernel | Primitivas transversales puras y tipadas | Mezcla de tablas, modelos y vistas gigantes |
| Fuente de verdad | Código o contrato vigente según estado | Una propuesta de documento sin aprobación |

## 4. Reglas duras para cambios de código

**MUST:**
- Conservar licencia GPL-3.0-or-later, autoría, avisos, fuentes y derechos; no presentarse como versión avalada.
- Trabajar **únicamente** en fork Em3rc0d y ramas propias; mantener PR #1 y #3 separados del PR #4.
- Inspeccionar código real antes de crear adaptadores; no confiar en nombres de funciones o documentos abstractos.
- Mantener APIs heredadas y resultados de ACU, metrado, costos, redondeos y valores almacenados.
- Modelar comercial con identidades/catálogos/tablas independientes; eventual unificación solo por ADR posterior.
- Documentar snapshots y origen de cualquier copia de obra a ventas.
- Probar atomicidad, reversibilidad, consistencia PDF/DB/GUI y ausencia de mutaciones cross-BU.
- Expresar las cantidades/montos de venta con `Decimal`, unidad y moneda; convertir dimensiones solo con fórmula verificable.
- Distinguir `CURRENT` vs `TARGET` vs `EXPERIMENTAL` y vincular evidencia.

**MUST NOT:**
- Reemplazar Construcción por cotizador genérico o convertirla en plugin subordinado de Ventas.
- Utilizar `almacen_ingreso` de obra como inventario comercial sin nuevo contrato aprobado.
- Hacer que crear/emitir/aceptar/exportar una cotización descuente o reserve stock.
- Tomar precio técnico de ACU como precio comercial sin consentimiento/regla explícita.
- Afirmar que `core/acu_parametrico.py` ya está integrado con GUI, SQLite o precios.
- Ejecutar workflows de publicación heredados con R2/dominio/tiendas del autor original.
- Añadir SUNAT, POS, caja, CRM completo, e-commerce, multiusuario cloud o predicción IA por iniciativa del agente.
- Declarar un KPI, coste, entrevista, prueba o aceptación como realizado sin salida verificable.
- Usar `eval`, tasas de impuestos fijas no sustentadas, fórmulas de rendimientos inventadas o pérdida no documentada.
- Fusionar a `main` funcionalidades experimentales sin gates demostrados.

## 5. Interfaz propuesta de contexto compartido — *no implementada*

```python
# SOLO CONTRATOS ILUSTRATIVOS: NO son interfaces existentes ni listas para implementar.
@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

@dataclass(frozen=True)
class Quantity:
    value: Decimal
    unit_code: str
    dimension: str

@dataclass(frozen=True)
class ConstructionEstimateSnapshot:
    project_id: str
    partida_id: str
    source_revision_hash: str
    description: str
    output_quantity: Quantity
    technical_cost: Money | None
    calculation_origin: str

@dataclass(frozen=True)
class SalesLineSnapshot:
    line_type: str
    description: str
    billable_quantity: Quantity
    sale_price: Money
    cost_reference: Money | None
    construction_origin: ConstructionEstimateSnapshot | None
```

Estos contratos no son código listo para producción. Primero se decide `Money` (moneda, escalas, redondeos, impuestos), `Quantity` (catálogo de unidades, prefijos y dimensionado), la persistencia de snapshots y permisos. En Construcción, tipos y moneda existentes no deben cambiar implícitamente por declarar estas interfaces.

## 6. Cadena de trazabilidad deseada

```text
Necesidad del usuario (N)
  → RF o RNF concreto
  → Regla de negocio RB / invariante INV
  → Decisión arquitectónica ADR
  → Diagrama/flujo/contrato
  → Implementación PR controlado
  → Test unitario + integración + E2E
  → Evidencia Actions + revisión
  → Gate PASS / HOLD / PIVOT / KILL
```

No se permite aprobar una implementación solo por compilar o por pasar un único test aislado. Ejemplo: **RF-017** (emitir sin descontar stock) → RB-01/INV-05 → diseño inventario ledger → test DB transaccional compara movimientos antes/después → evidencia de resultado CI con commit y OS → PASS solo si no hay escrituras.

## 7. Formato obligatorio de respuesta / handoff del agente

Para cada bloque de trabajo que modifique arquitectura, código o SRS, producir:

```yaml
handoff:
  area: "construction | sales | shared | infra | documentation"
  goal: "Objetivo único verificable"
  source_branch: "rama inspeccionada"
  target_branch: "rama de trabajo"
  decisions:
    approved: []
    proposed: []
    blocked: []
  affected_files: []
  requirements: ["RF-nnn", "RNF-nn"]
  invariants: ["INV-nn"]
  changes: []
  tests:
    executed: []
    results: []
    not_executed: []
  risks_remaining: []
  evidence_links: []
  gate: "PASS | HOLD | PIVOT | KILL"
  next_step: "una acción verificable; no inventar tareas ya hechas"
```

**Ejemplo de declaración correcta:** "RF-017 tiene contrato propuesto y fixtures pendientes; stock comercial aún NO existe. HOLD."  
**Ejemplo incorrecto:** "El inventario de ventas ya funciona porque `core/almacen.py` gestiona stock."

## 8. Preguntas que deben resolverse antes de BUILD de Ventas

- Producto/cliente objetivo inicial con evidencia de workflow; no elegir cinco segmentos a la vez.
- Numeración, estado de cotización, versiones simultáneas, autorización de descuentos y política de aceptación.
- Unidad canónica por SKU, presentación por caja/envase, fracciones, returns y tolerancias de stock.
- Inventario mínimo de una ubicación o importación manual; definición de saldo y reserva (inicialmente ninguna).
- Costos y precios: escalas, lista, moneda, fecha y tributos por documento; cómo se muestran importes sin costo.
- Catálogo y entidades: SKU, variante, servicio, material medible, paquete, item libre; duplicidad, bajas y vigencia.
- El contrato de adapter de solo lectura desde ACU (si entra en el primer incremento).
- Migraciones SQLite, backup, rollback, perfiles de datos, codificación regional.
- UX Qt accesible y contrato de errores; pruebas gráficas de Windows y Linux.
- Licencias, recursos de terceros, identidad del fork, datos/seed antes de empaquetar.

**Cuando estas decisiones estén formalizadas:** cerrar nodos del grafo → congelar MK1/SRS → autorizar BUILD por incrementos pequeños. No inventar aprobación del propietario.

## 9. Glosario de estados de evidencia

- **OFFICIAL/DECIDIDO:** declaración expresa del propietario o ADR explícitamente aceptada.
- **OBSERVED/EXISTENTE:** verificado en código o en ejecución reproducible.
- **INFERRED/PROPUESTO:** recomendación técnica, por validar; no convertirla en hecho.
- **GENERATED:** fixture o ejemplo sintético, jamás precio ni ficha técnica de mercado.
- **EXPERIMENTAL/PROTOTIPO:** test aislado o spike sin integración.
- **UNVERIFIED/ABIERTO:** no disponible, falla de QA o decisión sin evidencia.
- **BLOCKED/HOLD:** no avanzar a merge o release hasta prueba/gate.

**FIN.** Mantener este contrato y el contexto maestro sincronizados con cambios futuros; una modificación del código no reescribe por sí sola la visión aprobada de dos unidades de negocio.
