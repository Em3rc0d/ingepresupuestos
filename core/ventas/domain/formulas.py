# SPDX-License-Identifier: GPL-3.0-or-later
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP, localcontext

from .errors import ValidationError
from .money import decimal, precise
from .quantity import Quantity, UnitRegistry

FORMULA_VERSION = 'ventas-geometry-coverage/1'


def calculate(method: str, params: dict, sale_unit: str) -> dict:
    """Closed formulas; returns required physical and billable quantities + provenance."""
    UnitRegistry.get(sale_unit)
    with localcontext() as ctx:
        ctx.prec = 48
        presentation = None
        if method == 'MANUAL':
            qty = Quantity(precise(params['quantity']), sale_unit)
            required = qty
        elif method in ('LONGITUD', 'AREA', 'VOLUMEN'):
            dimension_unit = {'LONGITUD': 'm', 'AREA': 'm2', 'VOLUMEN': 'm3'}[method]
            rows = params.get('rows')
            if not isinstance(rows, list) or not 1 <= len(rows) <= 200:
                raise ValidationError('Ingrese de 1 a 200 filas de medidas.')
            total = Decimal('0')
            for row in rows:
                length = UnitRegistry.convert(row['length'], row['length_unit'], 'm')
                value = length
                if method in ('AREA', 'VOLUMEN'):
                    value *= UnitRegistry.convert(row['width'], row['length_unit'], 'm')
                if method == 'VOLUMEN':
                    value *= UnitRegistry.convert(row['height'], row['length_unit'], 'm')
                total += value * precise(row.get('pieces', '1'), 'Piezas')
            required = Quantity(total.quantize(Decimal('.000001'), rounding=ROUND_HALF_UP), dimension_unit)
            qty = required.to(sale_unit)
        elif method == 'COBERTURA':
            area = UnitRegistry.convert(params['area'], params['area_unit'], 'm2')
            coats = decimal(params['coats'], 'Manos', minimum=Decimal('.000001'))
            coverage = decimal(params['coverage'], 'Cobertura m2/L/mano', minimum=Decimal('.000001'))
            extra = decimal(params['extra_percent'], 'Consumo adicional %', maximum=Decimal('1000'))
            required_value = area * coats / coverage * (1 + extra / 100)
            required = Quantity(required_value.quantize(Decimal('.000001'), rounding=ROUND_HALF_UP), 'L')
            size = params.get('presentation_size')
            if size not in (None, ''):
                if UnitRegistry.get(sale_unit)[0] not in ('count', 'envase', 'caja', 'paquete'):
                    raise ValidationError('Con contenido por presentación, use pieza/envase/caja/paquete. Para vender volumen, deje el contenido vacío.')
                presentation = UnitRegistry.convert(size, params['presentation_unit'], 'L')
                if presentation <= 0:
                    raise ValidationError('Presentación debe ser mayor que cero.')
                value = required_value / presentation
                if params.get('closed_presentation') is True:
                    value = value.to_integral_value(rounding=ROUND_CEILING)
                qty = Quantity(value.quantize(Decimal('.000001'), rounding=ROUND_HALF_UP), sale_unit)
            else:
                qty = required.to(sale_unit)
        else:
            raise ValidationError('Método de cantidad no soportado.')
        result = {
            'version': FORMULA_VERSION, 'method': method, 'params': params,
            'required': str(required.amount), 'required_unit': required.unit,
            'quantity': str(qty.amount), 'unit': qty.unit,
            'source': str(params.get('source') or 'Supuesto no validado'),
        }
        if method == 'COBERTURA' and presentation is not None:
            sold = qty.amount * presentation
            result.update(sold_physical=str(sold), sold_unit='L', remainder=str(sold - required.amount))
        else:
            result.update(sold_physical=str(required.amount), sold_unit=required.unit, remainder='0')
        return result
