# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

from .errors import ValidationError
from .money import currency, decimal, precise
from .quantity import UnitRegistry


class ItemType(str, Enum):
    PRODUCTO = 'PRODUCTO'
    SERVICIO = 'SERVICIO'
    MATERIAL_MEDIBLE = 'MATERIAL_MEDIBLE'
    PAQUETE = 'PAQUETE'
    ITEM_LIBRE = 'ITEM_LIBRE'


@dataclass(frozen=True)
class Client:
    name: str
    document: str = ''
    email: str = ''
    phone: str = ''
    contact: str = ''
    address: str = ''
    notes: str = ''
    active: bool = True
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self):
        if not self.name.strip() or len(self.name) > 250:
            raise ValidationError('Cliente: nombre requerido (máximo 250 caracteres).')


@dataclass(frozen=True)
class Item:
    sku: str
    name: str
    kind: str
    unit: str
    physical_unit: str
    price: str
    currency: str
    cost: str | None = None
    description: str = ''
    tracks_stock: bool = False
    active: bool = True
    parent_id: str | None = None
    attributes: dict = field(default_factory=dict)
    formula: dict = field(default_factory=dict)
    components: list = field(default_factory=list)
    tax: dict | None = None
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self):
        if not self.sku.strip() or not self.name.strip():
            raise ValidationError('SKU y nombre son obligatorios.')
        if self.kind not in {x.value for x in ItemType if x != ItemType.ITEM_LIBRE}:
            raise ValidationError('Tipo de catálogo no soportado.')
        UnitRegistry.get(self.unit)
        UnitRegistry.get(self.physical_unit)
        currency(self.currency)
        precise(self.price, 'Precio')
        if self.cost is not None:
            precise(self.cost, 'Costo')
        if self.kind in ('SERVICIO', 'PAQUETE') and self.tracks_stock:
            raise ValidationError('Servicios/paquetes no llevan ledger propio.')
        if self.kind != 'PAQUETE' and self.components:
            raise ValidationError('Solo los paquetes admiten componentes.')
        if len(self.sku) > 100 or len(self.name) > 250:
            raise ValidationError('SKU/nombre demasiado largo.')


@dataclass(frozen=True)
class QuoteLine:
    description: str
    quantity: str
    unit: str
    price: str
    kind: str = 'ITEM_LIBRE'
    item_id: str | None = None
    sku: str = ''
    cost: str | None = None
    discount: dict = field(default_factory=lambda: {'kind': 'PERCENT', 'value': '0'})
    tax: dict | None = None
    formula: dict = field(default_factory=dict)
    components: list = field(default_factory=list)
    override_reason: str = ''
    id: str = field(default_factory=lambda: str(uuid4()))
    provenance: dict = field(default_factory=dict)
    datasheets: list = field(default_factory=list)

    def __post_init__(self):
        if not self.description.strip() or len(self.description) > 5000:
            raise ValidationError('Descripción de línea requerida (máximo 5000 caracteres).')
        if self.kind not in {x.value for x in ItemType}:
            raise ValidationError('Tipo de línea no soportado.')
        UnitRegistry.get(self.unit)
        precise(self.quantity, 'Cantidad')
        precise(self.price, 'Precio')
        if self.cost is not None:
            precise(self.cost, 'Costo')


@dataclass(frozen=True)
class Package:
    components: list

    def __post_init__(self):
        if not self.components:
            raise ValidationError('Un paquete necesita componentes.')
        for component in self.components:
            if component.get('kind') == 'PAQUETE':
                raise ValidationError('No se admiten paquetes anidados.')
            if decimal(component['quantity']) <= 0:
                raise ValidationError('Cantidad de componente debe ser positiva.')
