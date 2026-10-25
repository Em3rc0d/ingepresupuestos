# SPDX-License-Identifier: GPL-3.0-or-later
from copy import deepcopy
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from ..domain.errors import ConflictError, ValidationError
from ..domain.formulas import calculate as calculate_quantity
from ..domain.inventory import movement_delta, next_balance
from ..domain.models import Client, Item, Package, QuoteLine
from ..domain.money import ZERO, currency, decimal, precise
from ..domain.pricing import calculate
from ..domain.quantity import UnitRegistry
from ..domain.quote_states import transition
from ..infrastructure.sqlite import SalesStore, now
from ..infrastructure.repositories import fingerprint


def valid_date(value, label):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValidationError(f'{label}: fecha ISO requerida (AAAA-MM-DD).') from None


class SalesService:
    """Single application boundary for views; all SQL stays in infrastructure."""
    def __init__(self, path, actor='Usuario local', readonly=False):
        self.store = SalesStore(path)
        self.actor = str(actor or 'Usuario local')
        self.readonly = readonly
        self.store.initialize()

    def writable(self):
        if self.readonly:
            raise ValidationError('Sesión de invitado: solo consulta de Ventas.')

    def clients(self, include_inactive=False):
        with self.store.transaction() as repo:
            return repo.clients(include_inactive)

    def save_client(self, data):
        self.writable()
        client = Client(**data)
        with self.store.transaction(True) as repo:
            repo.save_client(client)
        return asdict(client)

    def items(self, include_inactive=False, code=None):
        with self.store.transaction() as repo:
            return repo.items(include_inactive, code)

    def save_item(self, data):
        self.writable()
        item = Item(**data)
        # Validate tax even when item has not yet been quoted.
        calculate([QuoteLine(item.name, '1', item.unit, item.price, tax=item.tax)], item.currency, {'kind': 'PERCENT', 'value': '0'})
        with self.store.transaction(True) as repo:
            if item.parent_id:
                parent = repo.item(item.parent_id)
                if parent['parent_id'] or parent['id'] == item.id or parent['kind'] != item.kind:
                    raise ValidationError('Variante: padre simple del mismo tipo requerido.')
            if item.components:
                Package(item.components)
                for component in item.components:
                    source = repo.item(component['item_id'])
                    if source['id'] == item.id or source['kind'] == 'PAQUETE':
                        raise ValidationError('Paquete cíclico/anidado no permitido.')
                    if not source['active']:
                        raise ValidationError('Componente de paquete inactivo.')
            elif item.kind == 'PAQUETE':
                raise ValidationError('Paquete sin componentes.')
            repo.save_item(item, self.actor, now())
        return asdict(item)

    def config(self):
        with self.store.transaction() as repo:
            return repo.config()

    def configure(self, issuer):
        self.writable()
        if not issuer.strip():
            raise ValidationError('Identidad textual del emisor requerida.')
        with self.store.transaction(True) as repo:
            repo.set_config('issuer', issuer.strip())

    def inventory(self):
        with self.store.transaction() as repo:
            balances = repo.balances()
            result = []
            for item in repo.items(True):
                balance = balances.get(item['id'])
                known = item['tracks_stock'] and balance is not None
                result.append({'item': item, 'verified': known, 'physical': str(balance['physical']) if known else None,
                               'reserved': '0', 'available': str(balance['physical']) if known else None,
                               'at': balance['at'] if balance else '', 'status': 'Verificado por ledger' if known else ('No verificado' if item['tracks_stock'] else 'Sin seguimiento')})
            return result

    def movements(self, item_id=None):
        with self.store.transaction() as repo:
            return repo.movements(item_id)

    def register_movement(self, item_id, kind, quantity, movement_date, reason):
        self.writable()
        valid_date(movement_date, 'Fecha de movimiento')
        if not reason.strip():
            raise ValidationError('Indique motivo del movimiento.')
        delta = movement_delta(kind, quantity)
        # Keep exact ledger precision, including signed adjustments.
        precise(abs(delta), 'Cantidad de movimiento')
        with self.store.transaction(True) as repo:
            item = repo.item(item_id)
            if not item['active'] or not item['tracks_stock']:
                raise ValidationError('El SKU debe estar activo y controlar stock.')
            balance = repo.balances().get(item_id)
            next_balance(balance['physical'] if balance else ZERO, delta, balance is not None)
            repo.add_movement(item, kind, delta, movement_date, reason.strip(), self.actor, now())

    def new_document(self):
        today = date.today()
        return {'id': None, 'number': 'Se asigna al guardar', 'state': 'BORRADOR', 'revision_id': None, 'version': 1, 'token': 0,
                'revision_state': 'BORRADOR', 'header': {'client_id': None, 'customer': {}, 'currency': 'PEN',
                'date': today.isoformat(), 'valid_until': (today + timedelta(days=15)).isoformat(), 'title': '',
                'conditions': '', 'notes': '', 'issuer': self.config().get('issuer', ''),
                'global_discount': {'kind': 'PERCENT', 'value': '0'}}, 'lines': []}

    def line_from_item(self, item_id, code):
        with self.store.transaction() as repo:
            item = repo.item(item_id, code)
            if not item['active'] or item['price'] is None:
                raise ValidationError('Artículo inactivo o sin tarifa en esta moneda; configure precio explícito.')
            components = []
            for component in item['components']:
                source = repo.item(component['item_id'], code)
                components.append({'item_id': source['id'], 'sku': source['sku'], 'description': source['name'],
                                   'kind': source['kind'], 'unit': source['unit'], 'quantity': component['quantity']})
            return asdict(QuoteLine(description=item['description'] or item['name'], quantity='1', unit=item['unit'],
                                    price=item['price'], kind=item['kind'], item_id=item['id'], sku=item['sku'], cost=item['cost'],
                                    tax=item['tax'], components=components))

    def calculate(self, document):
        lines = [QuoteLine(**line) for line in document['lines']]
        return calculate(lines, document['header']['currency'], document['header']['global_discount'])

    def _normalize(self, document, repo, issue, refresh_customer=True):
        h = document['header']
        currency(h['currency'])
        start = valid_date(h['date'], 'Fecha')
        until = valid_date(h['valid_until'], 'Vigencia')
        if until < start:
            raise ValidationError('Vigencia anterior a la fecha de cotización.')
        if h.get('client_id') and refresh_customer:
            client = repo.client(h['client_id'])
            if not client['active']:
                raise ValidationError('Cliente archivado: seleccione otro o use receptor ocasional.')
            h['customer'] = client
        if not h.get('customer', {}).get('name', '').strip():
            raise ValidationError('Seleccione cliente o escriba un receptor ocasional.')
        if not h.get('title', '').strip():
            raise ValidationError('Título/referencia requerida.')
        for line in document['lines']:
            formula = line.get('formula')
            if formula:
                evaluated = calculate_quantity(formula['method'], formula['params'], line['unit'])
                if decimal(evaluated['quantity']) != decimal(line['quantity']):
                    raise ValidationError('Cantidad no coincide con su fórmula; recalcule o seleccione manual.')
                line['formula'] = evaluated
            if line.get('components'):
                Package(line['components'])
            if issue and decimal(line['quantity']) <= 0:
                raise ValidationError('Emisión requiere cantidades mayores que cero.')
        document['totals'] = self.calculate(document)
        if issue:
            if not h.get('issuer', '').strip():
                raise ValidationError('Configure identidad textual del emisor antes de emitir.')
            if not document['lines'] or not document['totals']['tax_configured']:
                raise ValidationError('Emisión requiere líneas e impuestos explícitos (incluido cero).')
            if until < date.today():
                raise ValidationError('La cotización ya venció. Actualice su vigencia.')

    def save_draft(self, source, issue=False):
        self.writable()
        doc = deepcopy(source)
        stamp = now()
        with self.store.transaction(True) as repo:
            current = None
            if doc['id']:
                current = repo.document(doc['id'])
                if current['revision_id'] != doc['revision_id'] or current['revision_state'] != 'BORRADOR' or current['state'] != 'BORRADOR':
                    raise ConflictError('Documento protegido. Cree una nueva revisión para editar.')
                if current['token'] != doc['token']:
                    raise ConflictError('Borrador modificado por otra ventana. Reabra el documento.')
                if current['header']['currency'] != doc['header']['currency'] and (current['lines'] or doc['lines']):
                    raise ValidationError('Moneda con líneas existentes: no hay conversión automática. Cree otra cotización con tarifas explícitas.')
            if issue and current is None:
                raise ValidationError('Guarde y previsualice la revisión antes de emitir.')
            self._normalize(doc, repo, issue, refresh_customer=not issue)
            if not doc['id']:
                doc.update(id=str(uuid4()), revision_id=str(uuid4()), number=repo.next_number(valid_date(doc['header']['date'], 'Fecha').year))
                repo.create_quote(doc, stamp)
            doc['header'].update(number=doc['number'], version=doc['version'])
            if issue:
                if fingerprint(doc['header'], doc['lines'], doc['totals']) != fingerprint(current['header'], current['lines'], current['totals']):
                    raise ConflictError('La revisión cambió desde la vista previa. Guarde y previsualice de nuevo.')
                repo.freeze(doc, stamp)
            else:
                repo.write_revision(doc)
            repo.update_quote(doc, 'EMITIDA' if issue else 'BORRADOR', stamp)
            repo.event(doc, 'EMITIDA' if issue else 'GUARDADA', self.actor, stamp, {})
            return repo.document(doc['id'])

    def quotes(self):
        with self.store.transaction() as repo:
            return repo.quotes()

    def open_document(self, quote_id, revision_id=None):
        with self.store.transaction() as repo:
            return repo.document(quote_id, revision_id)

    def versions(self, quote_id):
        with self.store.transaction() as repo:
            return repo.versions(quote_id)

    def events(self, quote_id):
        with self.store.transaction() as repo:
            return repo.events(quote_id)

    def new_revision(self, quote_id, token):
        self.writable()
        with self.store.transaction(True) as repo:
            doc = repo.document(quote_id)
            if doc['token'] != token or doc['revision_state'] != 'EMITIDA' or doc['state'] != 'EMITIDA':
                raise ConflictError('Solo se permite revisar una cotización emitida y vigente en estado EMITIDA. Los estados finales no se reabren.')
            previous = doc['revision_id']
            doc.update(revision_id=str(uuid4()), version=doc['version'] + 1, revision_state='BORRADOR')
            # IDs identify lines across revisions for the diff; SQL rows have separate IDs.
            doc['header']['version'] = doc['version']
            repo.write_revision(doc)
            repo.update_quote(doc, 'BORRADOR', now())
            repo.event(doc, 'NUEVA_REVISION', self.actor, now(), {'source_revision': previous, 'previous_state': doc['state']})
            return repo.document(quote_id)

    def duplicate(self, quote_id, revision_id=None):
        source = self.open_document(quote_id, revision_id)
        document = self.new_document()
        document['header'].update(deepcopy(source['header']))
        fresh = self.new_document()['header']
        for key in ('date', 'valid_until', 'issuer'):
            document['header'][key] = fresh[key]
        document['header'].pop('number', None)
        document['header'].pop('version', None)
        document['lines'] = deepcopy(source['lines'])
        for line in document['lines']:
            line['id'] = str(uuid4())
        return document

    def change_state(self, quote_id, token, target, reason):
        self.writable()
        if not reason.strip():
            raise ValidationError('Motivo/constancia de cambio requerido.')
        with self.store.transaction(True) as repo:
            doc = repo.document(quote_id)
            if doc['token'] != token:
                raise ConflictError('Estado modificado en otra ventana; reabra.')
            if target == 'EMITIDA':
                raise ValidationError('Use la acción de emisión con vista previa.')
            transition(doc['state'], target)
            if target == 'VENCIDA' and valid_date(doc['header']['valid_until'], 'Vigencia') >= date.today():
                raise ValidationError('La fecha de vigencia aún no ha vencido.')
            if target == 'ACEPTADA' and valid_date(doc['header']['valid_until'], 'Vigencia') < date.today():
                raise ValidationError('Documento vencido; registre vencimiento o cree nueva revisión.')
            repo.update_quote(doc, target, now())
            repo.event(doc, target, self.actor, now(), {'reason': reason})
            return repo.document(quote_id)

    def stock_warnings(self, lines):
        inventory = {entry['item']['id']: entry for entry in self.inventory()}
        needs = {}
        for line in lines:
            sources = line.get('components') or [{'item_id': line.get('item_id'), 'quantity': '1', 'unit': line['unit']}]
            for source in sources:
                item_id = source['item_id']
                if item_id:
                    qty = decimal(line['quantity']) * decimal(source['quantity'])
                    entry = inventory.get(item_id)
                    if entry and source['unit'] != entry['item']['unit']:
                        try:
                            qty = UnitRegistry.convert(str(qty), source['unit'], entry['item']['unit'])
                        except ValidationError:
                            needs[item_id] = None
                            continue
                    if item_id in needs and needs[item_id] is None:
                        continue
                    needs[item_id] = needs.get(item_id, ZERO) + qty
        warnings = []
        for item_id, required in needs.items():
            entry = inventory.get(item_id)
            if not entry:
                warnings.append('SKU histórico sin disponibilidad verificable.')
                continue
            item = entry['item']
            if required is None:
                warnings.append(f"{item['sku']}: unidad histórica incompatible con el catálogo actual; disponibilidad no verificable. La línea conserva su snapshot.")
                continue
            text = f"{item['sku']}: requerido {required} {item['unit']} · {entry['status']}"
            if entry['verified']:
                available = Decimal(entry['available'])
                text += f' · disponible {available} · faltante {max(ZERO, required - available)} · referencia {entry["at"]}'
            warnings.append(text)
        return warnings

    @staticmethod
    def diff(old, new):
        changes = []
        for key in ('currency', 'customer', 'title', 'date', 'valid_until', 'conditions', 'notes', 'global_discount', 'issuer'):
            if old['header'].get(key) != new['header'].get(key):
                changes.append(f'Cabecera: {key}')
        before = {line['id']: line for line in old['lines']}
        after = {line['id']: line for line in new['lines']}
        for key in before.keys() | after.keys():
            if before.get(key) != after.get(key):
                line = after.get(key) or before[key]
                changes.append('Línea: ' + line['description'])
        if [l['id'] for l in old['lines']] != [l['id'] for l in new['lines']]:
            changes.append('Orden/composición de líneas')
        changes.append(f"Total: {old.get('totals', {}).get('total', '—')} → {new.get('totals', {}).get('total', '—')}")
        return changes
