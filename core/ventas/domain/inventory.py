# SPDX-License-Identifier: GPL-3.0-or-later
from .errors import ValidationError
from .money import ZERO, decimal


def movement_delta(kind, quantity):
    value = decimal(quantity, 'Movimiento', minimum=-decimal('1000000000000'))
    if kind == 'AJUSTE':
        return value
    if kind not in ('ENTRADA', 'SALIDA') or value <= 0:
        raise ValidationError('Entrada/salida requiere cantidad positiva.')
    return value if kind == 'ENTRADA' else -value


def next_balance(balance, delta, verified):
    if delta < 0 and not verified:
        raise ValidationError('Registre una entrada/ajuste de referencia antes de una salida.')
    result = balance + delta
    if result < ZERO:
        raise ValidationError('El movimiento produciría stock negativo.')
    return result
