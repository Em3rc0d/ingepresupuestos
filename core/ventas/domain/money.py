# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

from .errors import ValidationError

SCALES = {'PEN': 2, 'USD': 2, 'EUR': 2, 'JPY': 0}
MAX_VALUE = Decimal('1000000000000')
ZERO = Decimal('0')


def decimal(value, label='Valor', minimum=ZERO, maximum=MAX_VALUE) -> Decimal:
    if isinstance(value, (float, bool)) or not isinstance(value, (str, int, Decimal)):
        raise ValidationError(f'{label}: utilice un decimal explícito, sin float.')
    text = str(value).strip()
    if not text or len(text) > 80:
        raise ValidationError(f'{label}: número vacío o demasiado largo.')
    try:
        result = Decimal(text)
        if not result.is_finite() or result.adjusted() > 24 or result.as_tuple().exponent < -18:
            raise InvalidOperation
        if result < minimum or result > maximum:
            raise ValidationError(f'{label}: fuera del rango {minimum} a {maximum}.')
        return result
    except (InvalidOperation, ValueError):
        raise ValidationError(f'{label}: decimal inválido.') from None


def currency(code: str) -> str:
    if code not in SCALES:
        raise ValidationError('Moneda sin precisión configurada: ' + str(code))
    return code


def rounded(value: Decimal, code='PEN') -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 48
        return value.quantize(Decimal(10) ** -SCALES[currency(code)], rounding=ROUND_HALF_UP)


def precise(value, label='Valor') -> Decimal:
    number = decimal(value, label)
    quantized = number.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
    if number != quantized:
        raise ValidationError(f'{label}: máximo seis decimales.')
    return quantized


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self):
        object.__setattr__(self, 'currency', currency(self.currency))
        object.__setattr__(self, 'amount', rounded(decimal(self.amount, 'Importe'), self.currency))

    def __add__(self, other):
        if not isinstance(other, Money) or other.currency != self.currency:
            raise ValidationError('No se pueden sumar monedas diferentes.')
        return Money(self.amount + other.amount, self.currency)


@dataclass(frozen=True)
class SalePrice:
    amount: Decimal
    currency: str
    unit: str

    def __post_init__(self):
        from .quantity import UnitRegistry
        currency(self.currency)
        UnitRegistry.get(self.unit)
        object.__setattr__(self, 'amount', precise(self.amount, 'Precio de venta'))
