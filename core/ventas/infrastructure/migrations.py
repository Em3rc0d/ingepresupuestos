# SPDX-License-Identifier: GPL-3.0-or-later
"""DDL only. Importing this module does not open a database."""
from hashlib import sha256

DDL = (
    "CREATE TABLE IF NOT EXISTS ventas_schema_migrations (version INTEGER PRIMARY KEY, aplicada_en TEXT NOT NULL, hash TEXT NOT NULL)",
    "CREATE TABLE ventas_clientes (id TEXT PRIMARY KEY, nombre TEXT NOT NULL, documento TEXT NOT NULL, activo INTEGER NOT NULL CHECK(activo IN (0,1)), data_json TEXT NOT NULL)",
    "CREATE TABLE ventas_items (id TEXT PRIMARY KEY, sku TEXT NOT NULL UNIQUE COLLATE NOCASE, nombre TEXT NOT NULL, tipo TEXT NOT NULL, unidad TEXT NOT NULL, controla_stock INTEGER NOT NULL CHECK(controla_stock IN (0,1)), activo INTEGER NOT NULL CHECK(activo IN (0,1)), parent_id TEXT REFERENCES ventas_items(id), data_json TEXT NOT NULL)",
    "CREATE TABLE ventas_precios (id INTEGER PRIMARY KEY, item_id TEXT NOT NULL REFERENCES ventas_items(id), moneda TEXT NOT NULL, precio_decimal TEXT NOT NULL, costo_decimal TEXT, vigente_desde TEXT NOT NULL, actor TEXT NOT NULL)",
    "CREATE INDEX ventas_precios_item ON ventas_precios(item_id, moneda, id)",
    "CREATE TABLE ventas_almacenes (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, activo INTEGER NOT NULL)",
    "INSERT INTO ventas_almacenes VALUES (1, 'Almacén comercial local', 1)",
    "CREATE TABLE ventas_movimientos (id TEXT PRIMARY KEY, almacen_id INTEGER NOT NULL REFERENCES ventas_almacenes(id), item_id TEXT NOT NULL REFERENCES ventas_items(id), tipo TEXT NOT NULL CHECK(tipo IN ('ENTRADA','SALIDA','AJUSTE')), cantidad_decimal TEXT NOT NULL, unidad TEXT NOT NULL, fecha TEXT NOT NULL, motivo TEXT NOT NULL, actor TEXT NOT NULL, registrado_en TEXT NOT NULL)",
    "CREATE INDEX ventas_movimientos_item ON ventas_movimientos(item_id, registrado_en)",
    "CREATE TABLE ventas_contadores (anio INTEGER PRIMARY KEY, siguiente INTEGER NOT NULL)",
    "CREATE TABLE ventas_cotizaciones (id TEXT PRIMARY KEY, numero TEXT NOT NULL UNIQUE, cliente_id TEXT REFERENCES ventas_clientes(id), moneda TEXT NOT NULL, estado TEXT NOT NULL, fecha TEXT NOT NULL, vencimiento TEXT NOT NULL, titulo TEXT NOT NULL, actualizado_en TEXT NOT NULL, lock_version INTEGER NOT NULL DEFAULT 0)",
    "CREATE INDEX ventas_cotizaciones_filtro ON ventas_cotizaciones(cliente_id, estado, fecha)",
    "CREATE TABLE ventas_revisiones (id TEXT PRIMARY KEY, cotizacion_id TEXT NOT NULL REFERENCES ventas_cotizaciones(id), version INTEGER NOT NULL, estado TEXT NOT NULL CHECK(estado IN ('BORRADOR','EMITIDA')), fecha_emision TEXT, cabecera_json TEXT NOT NULL, totales_json TEXT NOT NULL, firma TEXT, UNIQUE(cotizacion_id, version))",
    "CREATE TABLE ventas_lineas (id TEXT PRIMARY KEY, revision_id TEXT NOT NULL REFERENCES ventas_revisiones(id), posicion INTEGER NOT NULL, item_id TEXT REFERENCES ventas_items(id), data_json TEXT NOT NULL, importe_json TEXT NOT NULL, UNIQUE(revision_id, posicion))",
    "CREATE TABLE ventas_eventos (id TEXT PRIMARY KEY, cotizacion_id TEXT NOT NULL REFERENCES ventas_cotizaciones(id), revision_id TEXT REFERENCES ventas_revisiones(id), tipo TEXT NOT NULL, fecha TEXT NOT NULL, actor TEXT NOT NULL, detalle_json TEXT NOT NULL)",
    "CREATE TABLE ventas_configuracion (clave TEXT PRIMARY KEY, valor TEXT NOT NULL)",
    "CREATE TRIGGER ventas_revision_no_update BEFORE UPDATE ON ventas_revisiones WHEN OLD.estado='EMITIDA' BEGIN SELECT RAISE(ABORT, 'Revisión emitida inmutable'); END",
    "CREATE TRIGGER ventas_revision_no_delete BEFORE DELETE ON ventas_revisiones WHEN OLD.estado='EMITIDA' BEGIN SELECT RAISE(ABORT, 'Revisión emitida inmutable'); END",
    "CREATE TRIGGER ventas_linea_no_insert BEFORE INSERT ON ventas_lineas WHEN (SELECT estado FROM ventas_revisiones WHERE id=NEW.revision_id)='EMITIDA' BEGIN SELECT RAISE(ABORT, 'Línea emitida inmutable'); END",
    "CREATE TRIGGER ventas_linea_no_update BEFORE UPDATE ON ventas_lineas WHEN (SELECT estado FROM ventas_revisiones WHERE id=OLD.revision_id)='EMITIDA' OR (SELECT estado FROM ventas_revisiones WHERE id=NEW.revision_id)='EMITIDA' BEGIN SELECT RAISE(ABORT, 'Línea emitida inmutable'); END",
    "CREATE TRIGGER ventas_linea_no_delete BEFORE DELETE ON ventas_lineas WHEN (SELECT estado FROM ventas_revisiones WHERE id=OLD.revision_id)='EMITIDA' BEGIN SELECT RAISE(ABORT, 'Línea emitida inmutable'); END",
)
for _table in ('ventas_movimientos', 'ventas_eventos', 'ventas_precios'):
    for _operation in ('UPDATE', 'DELETE'):
        DDL += (f"CREATE TRIGGER {_table}_no_{_operation.lower()} BEFORE {_operation} ON {_table} BEGIN SELECT RAISE(ABORT, 'Registro append-only'); END",)
CHECKSUM = sha256('\n'.join(DDL).encode('utf-8')).hexdigest()

DDL_V2 = (
    "CREATE TABLE ventas_importaciones (id TEXT PRIMARY KEY, archivo TEXT NOT NULL, sha256 TEXT NOT NULL, estrategia TEXT NOT NULL, resumen_json TEXT NOT NULL, actor TEXT NOT NULL, fecha TEXT NOT NULL)",
    "CREATE TABLE ventas_fichas (id TEXT PRIMARY KEY, item_id TEXT NOT NULL REFERENCES ventas_items(id), nombre TEXT NOT NULL, mime TEXT NOT NULL, tamano INTEGER NOT NULL, sha256 TEXT NOT NULL, ruta_interna TEXT NOT NULL, fecha_documento TEXT NOT NULL, fuente_tipo TEXT NOT NULL, referencia TEXT NOT NULL, actor TEXT NOT NULL, registrada_en TEXT NOT NULL)",
    "CREATE INDEX ventas_fichas_item ON ventas_fichas(item_id, registrada_en)",
    "CREATE TABLE ventas_fichas_eventos (id TEXT PRIMARY KEY, ficha_id TEXT NOT NULL REFERENCES ventas_fichas(id), tipo TEXT NOT NULL CHECK(tipo IN ('ASOCIADA','RETIRADA')), actor TEXT NOT NULL, fecha TEXT NOT NULL)",
)
for _table in ('ventas_importaciones', 'ventas_fichas', 'ventas_fichas_eventos'):
    for _operation in ('UPDATE', 'DELETE'):
        DDL_V2 += (f"CREATE TRIGGER {_table}_no_{_operation.lower()} BEFORE {_operation} ON {_table} BEGIN SELECT RAISE(ABORT, 'Registro append-only'); END",)
CHECKSUM_V2 = sha256('\n'.join(DDL_V2).encode('utf-8')).hexdigest()


def migrate(connection, now):
    # Caller owns transaction; executescript would implicitly commit and is forbidden here.
    connection.execute(DDL[0])
    rows = connection.execute('SELECT version, hash FROM ventas_schema_migrations ORDER BY version').fetchall()
    versions = {row['version']: row['hash'] for row in rows}
    expected = {1: CHECKSUM, 2: CHECKSUM_V2}
    if sorted(versions) != list(range(1, len(versions) + 1)) or any(expected.get(v) != h for v, h in versions.items()):
        from ..domain.errors import StorageError
        raise StorageError('Esquema Ventas incompatible: requiere revisión de migraciones.')
    for version, statements in ((1, DDL[1:]), (2, DDL_V2)):
        if version not in versions:
            for statement in statements:
                connection.execute(statement)
            connection.execute('INSERT INTO ventas_schema_migrations VALUES (?, ?, ?)', (version, now, expected[version]))
