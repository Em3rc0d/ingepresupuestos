# SPDX-License-Identifier: GPL-3.0-or-later
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
from uuid import uuid4

from ..domain.errors import ConflictError, ValidationError
from ..domain.models import Item
from ..domain.money import precise
from ..infrastructure.catalog_csv import read_csv, write_template
from ..infrastructure.repositories import dumps
from ..infrastructure.sqlite import now

MODES = ('CREAR_SOLO', 'ACTUALIZAR_EXISTENTES')


def boolean(text, field):
    if text.lower() not in ('0', '1', 'true', 'false', 'si', 'sí', 'no'):
        raise ValidationError(field + ': use 1/0, true/false o sí/no explícitos.')
    return text.lower() in ('1', 'true', 'si', 'sí')


def numeric(text, field):
    if ',' in text:
        raise ValidationError(field + ': use punto decimal; no se infiere configuración regional.')
    return str(precise(text, field))


class CatalogImportMixin:
    def catalog_template(self, path, delimiter=','):
        write_template(path, delimiter)

    def preview_catalog_csv(self, path, mode='CREAR_SOLO', delimiter=None):
        self.writable()
        if mode not in MODES:
            raise ValidationError('Estrategia de importación no soportada.')
        parsed = read_csv(path, delimiter)
        report = {k: parsed[k] for k in ('filename', 'sha256', 'delimiter')}
        report.update(mode=mode, rows=[], errors=list(parsed['errors']), created=0, updated=0, skipped=0)
        with self.store.transaction() as repo:
            catalog = {item['sku'].casefold(): item for item in repo.items(True)}
            report['catalog_token'] = repo.catalog_token()
            seen = set()
            for record in parsed['records']:
                values, number = record['values'], record['row']
                sku = values['sku'].strip()
                key = sku.casefold()
                if not sku or key in seen:
                    report['errors'].append({'row': number, 'field': 'sku', 'cause': 'SKU vacío o repetido dentro del archivo (sin distinguir mayúsculas).'})
                    continue
                seen.add(key)
                previous = catalog.get(key)
                if previous and mode == 'CREAR_SOLO':
                    report['skipped'] += 1
                    report['rows'].append({'row': number, 'sku': sku, 'operation': 'OMITIDA_EXISTENTE', 'item': None})
                    continue
                try:
                    data = deepcopy(previous) if previous else dict(id=str(uuid4()))
                    data.update(sku=previous['sku'] if previous else sku, name=values['nombre'], kind=values['tipo'].upper(),
                                unit=values['unidad'], physical_unit=values['unidad_fisica'],
                                price=numeric(values['precio'], 'precio'), currency=values['moneda'].upper())
                    if previous and 'costo' not in values:
                        # Never carry a PEN cost into a new USD tariff (or vice versa).
                        data['cost'] = repo.item(previous['id'], data['currency'])['cost']
                    for column, target in (('costo', 'cost'), ('descripcion', 'description')):
                        if column in values:
                            data[target] = numeric(values[column], column) if column == 'costo' and values[column] else (None if column == 'costo' else values[column])
                    for column, target, default in (('controla_stock', 'tracks_stock', False), ('activo', 'active', True)):
                        if column in values:
                            data[target] = boolean(values[column], column)
                        elif not previous:
                            data[target] = default
                    attributes = deepcopy(data.get('attributes', {}))
                    for column, target in (('color', 'color'), ('presentacion', 'size')):
                        if column in values:
                            attributes[target] = values[column]
                    data['attributes'] = attributes
                    if 'sku_padre' in values:
                        parent_sku = values['sku_padre'].casefold()
                        if parent_sku and parent_sku not in catalog:
                            raise ValidationError('sku_padre: cree el artículo principal antes de importar sus variantes.')
                        data['parent_id'] = catalog[parent_sku]['id'] if parent_sku else None
                    tax_columns = ('impuesto_nombre', 'impuesto_tasa', 'impuesto_modo')
                    if any(column in values for column in tax_columns):
                        supplied = [values.get(column, '') for column in tax_columns]
                        if any(supplied) and not all(supplied):
                            raise ValidationError('impuesto: nombre, tasa y modalidad deben venir juntos; vacío = sin configurar.')
                        data['tax'] = {'name': supplied[0], 'rate': numeric(supplied[1], 'impuesto_tasa'), 'mode': supplied[2].upper()} if all(supplied) else None
                    item = Item(**data)
                    self._validate_item(repo, item)
                    operation = 'ACTUALIZAR' if previous else 'CREAR'
                    report['updated' if previous else 'created'] += 1
                    report['rows'].append({'row': number, 'sku': item.sku, 'operation': operation, 'item': asdict(item)})
                except (ValidationError, KeyError, TypeError) as exc:
                    cause = str(exc)
                    field = cause.split(':', 1)[0] if ':' in cause else 'registro'
                    report['errors'].append({'row': number, 'field': field, 'cause': cause})
        report['preview_hash'] = sha256(dumps(report).encode('utf-8')).hexdigest()
        return report

    def apply_catalog_import(self, preview):
        self.writable()
        report = deepcopy(preview)
        digest = report.pop('preview_hash', None)
        if digest != sha256(dumps(report).encode('utf-8')).hexdigest():
            raise ConflictError('Vista previa alterada. Vuelva a leer el CSV.')
        if report['errors'] or report['mode'] not in MODES or not 1 <= len(report['rows']) <= 5000:
            raise ValidationError('Corrija todos los errores del CSV antes de confirmar; no se importa parcialmente.')
        rows = [row for row in report['rows'] if row['operation'] in ('CREAR', 'ACTUALIZAR')]
        if not rows:
            raise ValidationError('No hay altas ni actualizaciones para confirmar.')
        stamp = now()
        with self.store.transaction(True) as repo:
            if repo.catalog_token() != report['catalog_token']:
                raise ConflictError('El catálogo/tarifas/inventario cambió desde la vista previa. Vuelva a previsualizar.')
            for row in rows:
                item = Item(**row['item'])
                self._validate_item(repo, item)
                repo.save_item(item, self.actor, stamp)
            summary = {key: report[key] for key in ('created', 'updated', 'skipped')}
            repo.record_import(str(uuid4()), report['filename'], report['sha256'], report['mode'], summary, self.actor, stamp)
        return summary
