# SPDX-License-Identifier: GPL-3.0-or-later
from enum import Enum
from .errors import ValidationError


class QuotationState(str, Enum):
    BORRADOR = 'BORRADOR'
    EMITIDA = 'EMITIDA'
    ACEPTADA = 'ACEPTADA'
    RECHAZADA = 'RECHAZADA'
    VENCIDA = 'VENCIDA'
    ANULADA = 'ANULADA'


TRANSITIONS = {
    'BORRADOR': {'EMITIDA', 'ANULADA'},
    'EMITIDA': {'ACEPTADA', 'RECHAZADA', 'VENCIDA', 'ANULADA'},
    'ACEPTADA': set(), 'RECHAZADA': set(), 'VENCIDA': set(), 'ANULADA': set(),
}


def transition(current, target):
    if target not in TRANSITIONS.get(current, set()):
        raise ValidationError(f'Transición no permitida: {current} → {target}.')
    return target
