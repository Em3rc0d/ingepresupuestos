# Guía de Ventas v1 y Fase 2

La Fase 1 recibió QA seleccionado independiente en PR #5; las adiciones de Fase 2 están implementadas y **NO VERIFICADAS**. Esta guía describe controles programados, sin certificar el sistema completo. Probar primero con datos desechables según el contrato QA.

- Acceso: login local existente → **Ventas** en el menú lateral. **Inicio** conserva Construcción/Proyectos. Si Ventas no puede iniciarse, se muestra reparación/reintento; la navegación de Construcción sigue disponible por diseño.
- **Inicio Ventas:** resumen de cotizaciones, últimas propuestas, alertas de vigencia y configuración textual del emisor. No se inventa marca ni identidad del negocio.
- **Clientes:** nuevo/editar, contacto y dirección, desactivar sin borrar históricos. El editor también admite receptor ocasional sin ficha obligatoria.
- **Productos y servicios:** SKU estable, tipo, unidad, precio comercial y costo opcional separados, impuesto explícito o sin configurar, activo y control de stock. Cada variante tiene SKU propio y un artículo principal. Al elegir otra moneda se carga su tarifa guardada o queda vacía; no hay FX.
- Para pintura: usar unidad de venta `envase`, referencia física `L`, contenido por envase y cobertura respaldada por ficha o marcada como supuesto. Paquetes: añadir componentes de un nivel y fijar precio comercial propio; sus componentes no se duplican en el total externo.
- **Inventario:** seleccionar SKU → registrar ENTRADA, SALIDA o AJUSTE. AJUSTE es una diferencia firmada, no un saldo a sobrescribir. Motivo obligatorio. Un ajuste inicial 0 registra saldo cero conocido. Sin movimientos se muestra no verificado; sin seguimiento se distingue del cero. Reservado siempre 0 porque no hay reservas. Cotizaciones no generan movimientos.
- **Cotizaciones:** filtrar por cliente, número/referencia, estado y fecha; crear/abrir/duplicar; elegir revisión guardada para ver/exportar. Los borradores se editan; las emitidas requieren una revisión nueva.
- **Editor:** completar receptor, moneda, fechas, emisor y referencia; añadir líneas libres o del catálogo, servicios o paquetes; editar cantidad/precio/descuento/impuesto. El botón de medidas abre longitud/área/volumen por filas o cobertura. Se muestran requerido, vendible y equivalente físico. Descuentos globales se distribuyen proporcionalmente, con política de mayor resto.
- **Guardar y vista previa:** persiste el borrador y muestra exactamente esa revisión. Impuestos sin configurar permiten borrador con total provisional y bloquean emisión. Tasa cero requiere nombre, porcentaje 0 y modalidad explícitos. La confirmación congela el snapshot y registra evento; no emite comprobante tributario.
- **Versiones:** V1 conserva descripción, unidades, variables, precios, tasas, cliente y condiciones aunque cambie catálogo. Nueva revisión crea otro borrador. “Ver diferencias” compara contra versión anterior o último guardado. Aceptación/rechazo/vencimiento/anulación se registran con motivo y actor local.
- **PDF/Excel:** se exporta la revisión elegida, con importes exactos del snapshot. Excel conserva números decimales como texto para no cambiar su precisión; no lleva fórmulas. Se excluyen costos internos y componentes de paquete. Si falla la escritura se procura preservar el destino mediante temporal y reemplazo atómico.
- Cierre/Escape de formularios con cambios pregunta por descarte. Los datos guardados permanecen en la SQLite activa y entran en el respaldo existente. Invitados solo consultan, sin segundo login.

Pendientes al corte histórico de v1: conector ACU, CSV y fichas (implementados después en Fase 2). Permanecen fuera reservas/listas avanzadas; QA de rendimiento/accesibilidad/exportaciones pendiente. SUNAT, POS, órdenes, cloud e IA fuera del incremento.

## Fase 2 — nuevos controles (código sin verificar, 2026-10-25)

Las notas anteriores describían v1. CSV, conector y fichas ahora tienen implementación; el resultado de esta fase sigue **UNVERIFIED**. Las 52 pruebas de Windows del PR #5 preceden estas funcionalidades.

**Importación CSV:** Productos y servicios → Importar CSV → guardar plantilla o seleccionar archivo → estrategia (Crear solo por defecto) → validar y previsualizar → corregir todos los errores → confirmar lote. Coma/punto y coma; UTF-8 o BOM; punto decimal; hasta 5 MiB/5000 filas. Los existentes se omiten en Crear solo; en Actualizar se muestran las modificaciones propuestas y se conserva identidad/histórico. Cualquier cambio concurrente obliga a regenerar el preview. No existe columna de stock inicial: use Inventario y movimiento explícito.

Encabezados obligatorios: `sku,nombre,tipo,unidad,unidad_fisica,precio,moneda`. Opcionales: `costo,controla_stock,descripcion,activo,impuesto_nombre,impuesto_tasa,impuesto_modo,sku_padre,color,presentacion`. No se aceptan columnas desconocidas. Unidad/moneda deben ser del registro configurado; impuestos requieren nombre/tasa/modalidad juntos, o quedan sin configurar. Padre de variante debe existir previamente. Paquetes con componentes se crean en la pantalla de catálogo.

Ejemplo **sintético** con colisión deliberada: el tercer SKU repite el primero sin distinguir mayúsculas y bloquea todo el lote; elimine/corrija esa fila antes de importar. Los números no son precios de mercado:

```csv
sku,nombre,tipo,unidad,unidad_fisica,precio,moneda,controla_stock
DEMO-MAT-001,Material sintético,MATERIAL_MEDIBLE,envase,L,20.00,PEN,1
DEMO-SRV-001,Servicio sintético,SERVICIO,h,h,10.00,PEN,0
demo-mat-001,Colisión deliberada,PRODUCTO,envase,L,25.00,PEN,1
```

**Desde Construcción:** editor de cotización → Añadir desde Construcción → elegir proyecto accesible → buscar partida → previsualizar → ingresar cantidad y **precio de venta** → añadir copia. No selecciona títulos. Se muestra costo técnico guardado y hash de procedencia; no se ejecuta recálculo ACU ni se modifica la obra. Moneda distinta o unidad sin mapeo bloquean la selección. Puede revisar procedencia en el editor de línea. Los impuestos se configuran después en esa línea; no se copian reglas fiscales de la obra.

**Fichas técnicas:** catálogo → seleccionar artículo guardado → Fichas técnicas. Seleccionar PDF/PNG/JPEG, revisar hash/tamaño, indicar fecha si se conoce, fuente/tipo y confirmar asociación. Seleccionar no copia; confirmar guarda una copia administrada. No se interpretan documentos ni se infieren coberturas. Retirar la asociación mantiene archivo e histórico. Guardar copia exporta el archivo sin abrirlo/ejecutarlo.

Al cargar un SKU en una línea se capturan sus fichas activas. Para un borrador ya abierto, usar “Capturar fichas actuales para esta línea” de forma explícita; no se cambia V1 por modificar el catálogo. PDF/XLSX incluyen nombre/hash como referencias, sin rutas privadas, fuentes internas, costos técnicos ni archivos adjuntados automáticamente. Si falta el archivo administrado, el gestor lo marca ARCHIVO NO DISPONIBLE; la revisión conserva texto/hash e importes.

**Respaldo completo con fichas:** Inicio Ventas → Respaldo completo con fichas (administrador). Confirmar que el ZIP contendrá la SQLite completa de Construcción/Ventas/usuarios y documentos históricos, sin cifrado. El backup habitual SQLite **NO incluye las fichas**. Si falta un documento, el paquete se rechaza para no declararlo completo. Máximos: 512 MiB y 10000 referencias históricas.

**Restauración — contrato manual, no probada:** trabajar primero sobre una copia con la app cerrada. Inspeccionar `manifest.json`; verificar SHA256 y tamaño de `database/presupuestos.db` y cada entrada `fichas/<hash>.<ext>` contra el manifest. No extraer rutas externas, absolutas ni con `..`. Preparar un directorio de datos separado con la base y `ventas/fichas/` conservando nombres por hash; validar allí ambas BUs y documentos antes de reemplazar cualquier dato real. Preservar siempre la base y carpeta anteriores. Esta entrega no incorpora asistente automático de restauración ni demuestra que el proceso haya pasado QA.

El manifest declara expresamente que el paquete cubre SQLite y fichas de Ventas; **no incluye otros archivos externos de Construcción**, como uploads/imágenes/recursos. Conservarlos por separado si existen. Volver al runtime de Ventas v1 después de migrar a v2 requiere recuperar una copia anterior compatible; no borrar tablas ni modificar hashes de migración para forzar la apertura.
