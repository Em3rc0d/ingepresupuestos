# SPDX-License-Identifier: GPL-3.0-or-later
"""Typed anticorruption boundary: source quantities/costs never set sale price."""
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Protocol

from ..domain.errors import ValidationError
from ..domain.money import currency, decimal
from ..domain.quantity import UNITS, UnitRegistry
from ..infrastructure.construction_reader import ConstructionRepository
from ..infrastructure.repositories import dumps
from ..infrastructure.sqlite import now

SOURCE_VERSION = 'construction-readonly/stored-pu/1'
CURRENCIES = {'Soles': 'PEN', 'S/': 'PEN', 'S/.': 'PEN', 'PEN': 'PEN', 'Dólares': 'USD', 'Dolares': 'USD', 'USD': 'USD', 'Euros': 'EUR', 'EUR': 'EUR', 'JPY': 'JPY'}
ALIASES = {'m²': 'm2', 'm^2': 'm2', 'm³': 'm3', 'm^3': 'm3', 'und.': 'und', 'unidad': 'und', 'unid': 'und',
           'pza': 'pieza', 'pza.': 'pieza', 'hora': 'h', 'horas': 'h', 'lt': 'L', 'litro': 'L', 'l': 'L', 'kg.': 'kg', 'm.l.': 'm'}


def map_unit(unit):
    value = (unit or '').strip()
    mapped = value if value in UNITS else ALIASES.get(value.casefold(), value.casefold())
    UnitRegistry.get(mapped)
    return mapped


@dataclass(frozen=True)
class ConstructionEstimateSnapshot:
    source_project_id: int
    source_partida_id: int
    source_hash: str
    captured_at: str
    source_version: str
    description: str
    quantity: str
    unit: str
    cost_basis: str | None
    cost_currency: str
    source_data: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)


def validate_snapshot(snapshot):
    if snapshot.get('source_version') != SOURCE_VERSION:
        raise ValidationError('Versión de procedencia de Construcción no soportada.')
    data = snapshot['source_data']
    digest = sha256(dumps({'version': SOURCE_VERSION, 'data': data}).encode('utf-8')).hexdigest()
    if digest != snapshot['source_hash']:
        raise ValidationError('La copia de procedencia ACU fue modificada; vuelva a seleccionar la partida.')
    if data['project']['id'] != snapshot['source_project_id'] or data['partida']['id'] != snapshot['source_partida_id']:
        raise ValidationError('Identificación de procedencia ACU inconsistente.')
    if map_unit(data['partida']['unidad']) != snapshot['unit'] or data['partida']['descripcion'] != snapshot['description']:
        raise ValidationError('Unidad/descripción de procedencia ACU inconsistente.')
    if CURRENCIES.get(data['project']['moneda']) != snapshot['cost_currency']:
        raise ValidationError('Moneda de procedencia ACU inconsistente.')
    if data['partida']['metrado'] != snapshot['quantity'] or data['partida']['precio_unitario'] != snapshot['cost_basis']:
        raise ValidationError('Cantidades/costos de procedencia ACU inconsistentes.')


class ConstructionSnapshotReader(Protocol):
    def read_partida(self, project_id: int, partida_id: int) -> ConstructionEstimateSnapshot: ...


class SqliteConstructionSnapshotReader:
    def __init__(self, path, user_id=None, is_admin=False):
        self.repository = ConstructionRepository(path, user_id, is_admin)

    def projects(self):
        return self.repository.projects()

    def parts(self, project_id, search=''):
        return self.repository.parts(project_id, search)

    def read_partida(self, project_id, partida_id):
        data = self.repository.snapshot_data(project_id, partida_id)
        part, project = data['partida'], data['project']
        unit = map_unit(part['unidad'])
        code = CURRENCIES.get(project['moneda'])
        if code is None:
            raise ValidationError('La moneda de la obra no tiene mapeo inequívoco. No se convierte por intuición.')
        currency(code)
        if not part['descripcion'].strip():
            raise ValidationError('Partida sin descripción comercializable.')
        decimal(part['metrado'], 'Metrado de referencia')
        if part['precio_unitario'] is not None:
            decimal(part['precio_unitario'], 'Costo técnico guardado')
        warnings = ['Costo técnico GUARDADO, no recalculado ni certificado; se conservan precios efectivos del ACU por proyecto.',
                    'Campos REAL heredados se capturan como texto SQLite. No constituyen precio de venta.']
        if not data['acu_items']:
            warnings.append('Partida sin desglose ACU: solo referencia de costo unitario almacenado.')
        digest = sha256(dumps({'version': SOURCE_VERSION, 'data': data}).encode('utf-8')).hexdigest()
        return ConstructionEstimateSnapshot(project_id, partida_id, digest, now(), SOURCE_VERSION,
                                            part['descripcion'], part['metrado'], unit, part['precio_unitario'], code, data, warnings)
