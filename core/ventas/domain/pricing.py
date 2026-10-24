# SPDX-License-Identifier: GPL-3.0-or-later
from decimal import Decimal, ROUND_FLOOR, localcontext

from .errors import ValidationError
from .models import QuoteLine
from .money import ZERO, SCALES, currency, decimal, rounded

PRICING_VERSION = 'ventas-pricing/1'


def discount_amount(base, rule, code):
    kind = rule.get('kind', 'PERCENT')
    value = decimal(rule.get('value', '0'), 'Descuento')
    if kind == 'PERCENT':
        if value > 100:
            raise ValidationError('Descuento porcentual debe estar entre 0 y 100.')
        result = rounded(base * value / 100, code)
    elif kind == 'AMOUNT':
        result = rounded(value, code)
    else:
        raise ValidationError('Descuento debe ser PERCENT o AMOUNT.')
    if result > base:
        raise ValidationError('Descuento supera el importe de la línea/documento.')
    return result


def allocate(amount, bases, code):
    """Largest remainder, ties by position; exactly sum to amount, never overdraw."""
    total = sum(bases, ZERO)
    if not amount or not total:
        return [ZERO for _ in bases]
    factor = Decimal(10) ** SCALES[code]
    units = int(amount * factor)
    exact = [amount * b / total * factor for b in bases]
    floors = [int(v.to_integral_value(rounding=ROUND_FLOOR)) for v in exact]
    remainder = units - sum(floors)
    order = sorted(range(len(bases)), key=lambda i: (-(exact[i] - floors[i]), i))
    for i in order[:remainder]:
        floors[i] += 1
    return [Decimal(v) / factor for v in floors]


def calculate(lines: list[QuoteLine], code: str, global_discount: dict) -> dict:
    currency(code)
    if len(lines) > 200:
        raise ValidationError('Máximo 200 líneas por cotización en v1.')
    with localcontext() as ctx:
        ctx.prec = 48
        gross = [rounded(decimal(l.quantity) * decimal(l.price), code) for l in lines]
        discounts = [discount_amount(b, l.discount, code) for b, l in zip(gross, lines)]
        bases = [b - d for b, d in zip(gross, discounts)]
        global_amount = discount_amount(sum(bases, ZERO), global_discount, code)
        shares = allocate(global_amount, bases, code)
        results, groups = [], {}
        for index, (line, base, share) in enumerate(zip(lines, bases, shares)):
            adjusted = base - share
            rule = line.tax
            known = rule is not None
            if known:
                if not str(rule.get('name', '')).strip() or rule.get('mode') not in ('EXCLUSIVE', 'INCLUSIVE'):
                    raise ValidationError('Impuesto: nombre y modalidad explícitos requeridos.')
                rate = decimal(rule['rate'], 'Tasa de impuesto %', maximum=Decimal('100'))
                if rule['mode'] == 'INCLUSIVE':
                    net = rounded(adjusted / (1 + rate / 100), code)
                    tax = adjusted - net
                else:
                    net = adjusted
                    tax = rounded(net * rate / 100, code)
                key = (rule['name'], str(rate), rule['mode'])
                group = groups.setdefault(key, {'name': key[0], 'rate': key[1], 'mode': key[2], 'base': ZERO, 'tax': ZERO})
                group['base'] += net
                group['tax'] += tax
            else:
                net, tax = adjusted, ZERO
            results.append({
                'position': index, 'gross': str(gross[index]), 'line_discount': str(discounts[index]),
                'global_discount': str(share), 'net': str(net), 'tax': str(tax),
                'total': str(net + tax), 'tax_known': known,
            })
        net_total = sum((Decimal(r['net']) for r in results), ZERO)
        tax_total = sum((Decimal(r['tax']) for r in results), ZERO)
        return {
            'policy_version': PRICING_VERSION, 'currency': code, 'gross': str(sum(gross, ZERO)),
            'line_discount': str(sum(discounts, ZERO)), 'global_discount': str(global_amount),
            'net': str(net_total), 'tax': str(tax_total), 'total': str(net_total + tax_total),
            'tax_configured': bool(lines) and all(l.tax is not None for l in lines),
            'tax_groups': [{**g, 'base': str(g['base']), 'tax': str(g['tax'])} for g in groups.values()],
            'lines': results,
        }
