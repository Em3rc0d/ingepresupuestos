# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import asdict

from ..domain.errors import ValidationError
from ..domain.models import QuoteLine
from ..domain.money import precise
from .construction_adapter import SqliteConstructionSnapshotReader, validate_snapshot


class ConstructionMixin:
    def construction_reader(self):
        return SqliteConstructionSnapshotReader(self.store.path, self.user_id, self.is_admin)

    def construction_projects(self):
        return self.construction_reader().projects()

    def construction_parts(self, project_id, search=''):
        return self.construction_reader().parts(project_id, search)

    def preview_construction(self, project_id, partida_id):
        return asdict(self.construction_reader().read_partida(project_id, partida_id))

    def line_from_construction(self, snapshot, code, sale_price, quantity):
        self.writable()
        validate_snapshot(snapshot)
        if snapshot['cost_currency'] != code:
            raise ValidationError('Moneda de obra distinta de cotización. No hay FX ni conversión de costo implícita.')
        price = precise(sale_price, 'Precio de venta explícito')
        amount = precise(quantity, 'Cantidad de venta')
        if amount <= 0:
            raise ValidationError('Cantidad de venta debe ser positiva.')
        cost = None
        if snapshot['cost_basis'] is not None:
            try:
                cost = str(precise(snapshot['cost_basis'], 'Costo de referencia'))
            except ValidationError:
                # Full unrounded legacy reference remains in provenance, not fake margin.
                pass
        return asdict(QuoteLine(snapshot['description'], str(amount), snapshot['unit'], str(price),
                                kind='SERVICIO', cost=cost, provenance={'kind': 'CONSTRUCTION', 'snapshot': snapshot}))
