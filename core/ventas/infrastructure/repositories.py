# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
import json
from uuid import uuid4

from ..domain.errors import ConflictError, StorageError, ValidationError
from ..domain.money import ZERO


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def fingerprint(header, lines, totals):
    return sha256(dumps({'header': header, 'lines': lines, 'totals': totals}).encode('utf-8')).hexdigest()


class Repository:
    def __init__(self, connection):
        self.connection = connection

    def clients(self, include_inactive=False):
        return [json.loads(r['data_json']) for r in self.connection.execute(
            'SELECT data_json FROM ventas_clientes WHERE activo=1 OR ? ORDER BY nombre COLLATE NOCASE', (include_inactive,))]

    def client(self, client_id):
        row = self.connection.execute('SELECT data_json FROM ventas_clientes WHERE id=?', (client_id,)).fetchone()
        if not row:
            raise ValidationError('Cliente no encontrado.')
        return json.loads(row['data_json'])

    def save_client(self, client):
        self.connection.execute(
            'INSERT INTO ventas_clientes VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET nombre=excluded.nombre, documento=excluded.documento, activo=excluded.activo, data_json=excluded.data_json',
            (client.id, client.name, client.document, int(client.active), dumps(asdict(client))))

    def items(self, include_inactive=False, code=None):
        items = [json.loads(r['data_json']) for r in self.connection.execute(
            'SELECT data_json FROM ventas_items WHERE activo=1 OR ? ORDER BY nombre COLLATE NOCASE', (include_inactive,))]
        if code:
            prices = {r['item_id']: dict(r) for r in self.connection.execute(
                'SELECT p.* FROM ventas_precios p JOIN (SELECT item_id, MAX(id) id FROM ventas_precios WHERE moneda=? GROUP BY item_id) latest ON latest.id=p.id', (code,))}
            for item in items:
                p = prices.get(item['id'])
                item.update(price=p['precio_decimal'] if p else None, cost=p['costo_decimal'] if p else None, currency=code)
        return items

    def item(self, item_id, code=None):
        row = self.connection.execute('SELECT data_json FROM ventas_items WHERE id=?', (item_id,)).fetchone()
        if row is None:
            raise ValidationError('Artículo no encontrado.')
        item = json.loads(row['data_json'])
        if code:
            price = self.connection.execute('SELECT precio_decimal,costo_decimal FROM ventas_precios WHERE item_id=? AND moneda=? ORDER BY id DESC LIMIT 1', (item_id, code)).fetchone()
            item.update(price=price['precio_decimal'] if price else None, cost=price['costo_decimal'] if price else None, currency=code)
        return item

    def save_item(self, item, actor, now):
        # Changing the unit/tracking with movement history would reinterpret the ledger.
        previous = self.connection.execute('SELECT sku, tipo, unidad, controla_stock FROM ventas_items WHERE id=?', (item.id,)).fetchone()
        if previous and previous['sku'] != item.sku.strip():
            raise ValidationError('El SKU es estable. Archive este artículo y cree otro para cambiar código.')
        has_children = self.connection.execute('SELECT 1 FROM ventas_items WHERE parent_id=? LIMIT 1', (item.id,)).fetchone()
        if has_children and (item.parent_id or previous and previous['tipo'] != item.kind):
            raise ValidationError('Un artículo con variantes no puede convertirse en variante ni cambiar de tipo.')
        if previous and (previous['unidad'] != item.unit or bool(previous['controla_stock']) != item.tracks_stock):
            if self.connection.execute('SELECT 1 FROM ventas_movimientos WHERE item_id=? LIMIT 1', (item.id,)).fetchone():
                raise ValidationError('Unidad/seguimiento con movimientos no se cambia; cree otro SKU.')
        self.connection.execute(
            'INSERT INTO ventas_items VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET sku=excluded.sku, nombre=excluded.nombre, tipo=excluded.tipo, unidad=excluded.unidad, controla_stock=excluded.controla_stock, activo=excluded.activo, parent_id=excluded.parent_id, data_json=excluded.data_json',
            (item.id, item.sku.strip(), item.name, item.kind, item.unit, int(item.tracks_stock), int(item.active), item.parent_id, dumps(asdict(item))))
        self.connection.execute('INSERT INTO ventas_precios (item_id,moneda,precio_decimal,costo_decimal,vigente_desde,actor) VALUES (?,?,?,?,?,?)',
                                (item.id, item.currency, item.price, item.cost, now, actor))

    def movements(self, item_id=None):
        return [dict(r) for r in self.connection.execute(
            'SELECT m.*, i.sku FROM ventas_movimientos m JOIN ventas_items i ON i.id=m.item_id WHERE (? IS NULL OR m.item_id=?) ORDER BY m.registrado_en,m.id', (item_id, item_id))]

    def balances(self):
        result = {}
        for row in self.connection.execute('SELECT item_id,cantidad_decimal,registrado_en FROM ventas_movimientos ORDER BY registrado_en,id'):
            current = result.setdefault(row['item_id'], {'physical': ZERO, 'verified': True, 'at': row['registrado_en']})
            current['physical'] += Decimal(row['cantidad_decimal'])
            current['at'] = row['registrado_en']
            if current['physical'] < 0:
                raise StorageError('Ledger comercial inconsistente: saldo negativo. Requiere conciliación.')
        return result

    def add_movement(self, item, kind, delta, date, reason, actor, now):
        self.connection.execute('INSERT INTO ventas_movimientos VALUES (?,?,?,?,?,?,?,?,?,?)',
                                (str(uuid4()), 1, item['id'], kind, str(delta), item['unit'], date, reason, actor, now))

    def config(self):
        return {r['clave']: r['valor'] for r in self.connection.execute('SELECT * FROM ventas_configuracion')}

    def set_config(self, key, value):
        self.connection.execute('INSERT INTO ventas_configuracion VALUES (?,?) ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor', (key, value))

    def next_number(self, year):
        row = self.connection.execute('SELECT siguiente FROM ventas_contadores WHERE anio=?', (year,)).fetchone()
        value = row['siguiente'] if row else 1
        self.connection.execute('INSERT INTO ventas_contadores VALUES (?,?) ON CONFLICT(anio) DO UPDATE SET siguiente=excluded.siguiente', (year, value + 1))
        return f'COT-{year}-{value:06d}'

    def quotes(self):
        return [dict(r) for r in self.connection.execute(
            'SELECT q.*, r.version, r.id revision_id, r.totales_json, r.cabecera_json FROM ventas_cotizaciones q JOIN ventas_revisiones r ON r.cotizacion_id=q.id WHERE r.version=(SELECT MAX(version) FROM ventas_revisiones WHERE cotizacion_id=q.id) ORDER BY q.actualizado_en DESC')]

    def quote_row(self, quote_id):
        row = self.connection.execute('SELECT * FROM ventas_cotizaciones WHERE id=?', (quote_id,)).fetchone()
        if not row:
            raise ValidationError('Cotización no encontrada.')
        return dict(row)

    def versions(self, quote_id):
        return [dict(r) for r in self.connection.execute('SELECT id,version,estado,fecha_emision,firma FROM ventas_revisiones WHERE cotizacion_id=? ORDER BY version DESC', (quote_id,))]

    def document(self, quote_id, revision_id=None):
        quote = self.quote_row(quote_id)
        if revision_id:
            row = self.connection.execute('SELECT * FROM ventas_revisiones WHERE id=? AND cotizacion_id=?', (revision_id, quote_id)).fetchone()
        else:
            row = self.connection.execute('SELECT * FROM ventas_revisiones WHERE cotizacion_id=? ORDER BY version DESC LIMIT 1', (quote_id,)).fetchone()
        if not row:
            raise ValidationError('Revisión no encontrada.')
        lines = [json.loads(r['data_json']) for r in self.connection.execute('SELECT data_json FROM ventas_lineas WHERE revision_id=? ORDER BY posicion', (row['id'],))]
        header, totals = json.loads(row['cabecera_json']), json.loads(row['totales_json'])
        if row['estado'] == 'EMITIDA' and row['firma'] != fingerprint(header, lines, totals):
            raise StorageError('El sello de esta revisión no coincide. No emitir ni exportar; revisar respaldo.')
        return {'id': quote_id, 'number': quote['numero'], 'state': quote['estado'], 'token': quote['lock_version'],
                'revision_id': row['id'], 'version': row['version'], 'revision_state': row['estado'],
                'issued_at': row['fecha_emision'], 'hash': row['firma'], 'header': header, 'lines': lines, 'totals': totals}

    def create_quote(self, document, now):
        h = document['header']
        self.connection.execute('INSERT INTO ventas_cotizaciones VALUES (?,?,?,?,?,?,?,?,?,?)',
                                (document['id'], document['number'], h.get('client_id'), h['currency'], 'BORRADOR', h['date'], h['valid_until'], h['title'], now, 0))

    def update_quote(self, document, state, now):
        h = document['header']
        cursor = self.connection.execute(
            'UPDATE ventas_cotizaciones SET cliente_id=?,moneda=?,estado=?,fecha=?,vencimiento=?,titulo=?,actualizado_en=?,lock_version=lock_version+1 WHERE id=? AND lock_version=?',
            (h.get('client_id'), h['currency'], state, h['date'], h['valid_until'], h['title'], now, document['id'], document['token']))
        if cursor.rowcount != 1:
            raise ConflictError('Cotización modificada en otra ventana. Reabra antes de guardar.')

    def write_revision(self, document):
        rid = document['revision_id']
        self.connection.execute(
            'INSERT INTO ventas_revisiones (id,cotizacion_id,version,estado,cabecera_json,totales_json) VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET cabecera_json=excluded.cabecera_json,totales_json=excluded.totales_json',
            (rid, document['id'], document['version'], 'BORRADOR', dumps(document['header']), dumps(document['totals'])))
        self.connection.execute('DELETE FROM ventas_lineas WHERE revision_id=?', (rid,))
        for i, (line, result) in enumerate(zip(document['lines'], document['totals']['lines'])):
            self.connection.execute('INSERT INTO ventas_lineas VALUES (?,?,?,?,?,?)', (str(uuid4()), rid, i, line.get('item_id'), dumps(line), dumps(result)))

    def freeze(self, document, now):
        digest = fingerprint(document['header'], document['lines'], document['totals'])
        self.connection.execute('UPDATE ventas_revisiones SET estado=?,fecha_emision=?,firma=? WHERE id=? AND estado=?', ('EMITIDA', now, digest, document['revision_id'], 'BORRADOR'))

    def event(self, document, kind, actor, now, detail):
        self.connection.execute('INSERT INTO ventas_eventos VALUES (?,?,?,?,?,?,?)',
                                (str(uuid4()), document['id'], document['revision_id'], kind, now, actor, dumps(detail)))

    def events(self, quote_id):
        return [dict(r) for r in self.connection.execute('SELECT tipo,fecha,actor,detalle_json,revision_id FROM ventas_eventos WHERE cotizacion_id=? ORDER BY fecha,id', (quote_id,))]
