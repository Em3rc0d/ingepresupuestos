# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, localcontext

from .errors import ValidationError
from .money import precise

# Presentaciones no se convierten a piezas sin una ficha explícita.
UNITS = {
    'm': ('length', '1'), 'cm': ('length', '.01'), 'mm': ('length', '.001'),
    'm2': ('area', '1'), 'cm2': ('area', '.0001'), 'mm2': ('area', '.000001'),
    'm3': ('volume', '1'), 'L': ('volume', '.001'), 'mL': ('volume', '.000001'),
    'kg': ('mass', '1'), 'g': ('mass', '.001'),
    'h': ('time', '1'), 'jornada': ('jornada', '1'), 'evento': ('evento', '1'),
    'tarifa': ('tarifa', '1'), 'und': ('count', '1'), 'pieza': ('count', '1'),
    'envase': ('envase', '1'), 'caja': ('caja', '1'), 'paquete': ('paquete', '1'),
}


class UnitRegistry:
    @staticmethod
    def get(unit):
        if unit not in UNITS:
            raise ValidationError('Unidad no soportada: ' + str(unit))
        dimension, factor = UNITS[unit]
        return dimension, Decimal(factor)

    @staticmethod
    def convert(value, source, target):
        sd, sf = UnitRegistry.get(source)
        td, tf = UnitRegistry.get(target)
        if sd != td:
            raise ValidationError(f'Conversión incompatible: {source} → {target}.')
        with localcontext() as ctx:
            ctx.prec = 48
            result = precise(value, 'Cantidad') * sf / tf
            return precise(result.quantize(Decimal('.000001'), rounding=ROUND_HALF_UP), 'Cantidad convertida')


@dataclass(frozen=True)
class Quantity:
    amount: Decimal
    unit: str

    def __post_init__(self):
        UnitRegistry.get(self.unit)
        object.__setattr__(self, 'amount', precise(self.amount, 'Cantidad'))

    def to(self, unit):
        return Quantity(UnitRegistry.convert(self.amount, self.unit, unit), unit)
