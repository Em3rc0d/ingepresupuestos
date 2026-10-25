# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded UTF-8 CSV input. No database or Qt; importing never reads files."""
import csv
from hashlib import sha256
from io import StringIO
from pathlib import Path

from ..domain.errors import ValidationError

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000
REQUIRED = ('sku', 'nombre', 'tipo', 'unidad', 'unidad_fisica', 'precio', 'moneda')
OPTIONAL = ('costo', 'controla_stock', 'descripcion', 'activo', 'impuesto_nombre', 'impuesto_tasa',
            'impuesto_modo', 'sku_padre', 'color', 'presentacion')
COLUMNS = REQUIRED + OPTIONAL


def read_csv(path, delimiter=None, max_rows=MAX_ROWS, max_bytes=MAX_BYTES):
    if not 1 <= max_rows <= MAX_ROWS or not 1 <= max_bytes <= MAX_BYTES:
        raise ValidationError('Límites CSV fuera de los máximos permitidos (5000 filas, 5 MiB).')
    try:
        with open(path, 'rb') as stream:
            content = stream.read(max_bytes + 1)
    except OSError as exc:
        raise ValidationError('No se pudo leer el archivo CSV seleccionado.') from exc
    if len(content) > max_bytes:
        raise ValidationError('CSV demasiado grande; máximo 5 MiB. Divida el archivo.')
    try:
        text = content.decode('utf-8-sig')
    except UnicodeError:
        raise ValidationError('CSV debe estar codificado en UTF-8 o UTF-8 con BOM.') from None
    if '\x00' in text:
        raise ValidationError('CSV contiene caracteres nulos.')
    if delimiter not in (None, ',', ';'):
        raise ValidationError('Separador CSV debe ser coma o punto y coma.')
    if delimiter is None:
        candidates = []
        for candidate in (',', ';'):
            try:
                header = next(csv.reader(StringIO(text, newline=''), delimiter=candidate, strict=True), [])
                if set(REQUIRED) <= {h.strip().lower() for h in header}:
                    candidates.append(candidate)
            except csv.Error:
                pass
        if len(candidates) != 1:
            raise ValidationError('No se pudo determinar un separador inequívoco. Elija coma/punto y coma y revise encabezados.')
        delimiter = candidates[0]
    reader = csv.reader(StringIO(text, newline=''), delimiter=delimiter, strict=True)
    result, errors = [], []
    try:
        header = [h.strip().lower() for h in next(reader, [])]
        if len(header) != len(set(header)):
            raise ValidationError('Encabezados CSV duplicados.')
        missing = sorted(set(REQUIRED) - set(header))
        unknown = sorted(set(header) - set(COLUMNS))
        if missing or unknown:
            raise ValidationError('Encabezados inválidos. Faltan: ' + ', '.join(missing) + '. No admitidos: ' + ', '.join(unknown))
        for values in reader:
            if not values or all(not v.strip() for v in values):
                continue
            if len(result) + len(errors) >= max_rows:
                raise ValidationError('CSV supera el límite de 5000 registros. Divida el archivo.')
            row_number = reader.line_num
            if len(values) != len(header):
                errors.append({'row': row_number, 'field': 'columnas', 'cause': 'Número de columnas diferente del encabezado.'})
                continue
            if any(len(v) > 8192 for v in values):
                errors.append({'row': row_number, 'field': 'texto', 'cause': 'Máximo 8192 caracteres por celda.'})
                continue
            result.append({'row': row_number, 'values': dict(zip(header, (v.strip() for v in values)))})
    except csv.Error:
        errors.append({'row': reader.line_num, 'field': 'formato', 'cause': 'Comillas/campo CSV inválido o demasiado extenso.'})
    if not result and not errors:
        raise ValidationError('CSV sin registros de catálogo.')
    return {'filename': Path(path).name, 'sha256': sha256(content).hexdigest(), 'delimiter': delimiter,
            'records': result, 'errors': errors}


def write_template(path, delimiter=','):
    if delimiter not in (',', ';'):
        raise ValidationError('Separador de plantilla no soportado.')
    # Synthetic figures; no market rates or inventory quantities.
    rows = [
        ['DEMO-MAT-001', 'Material sintético', 'MATERIAL_MEDIBLE', 'envase', 'L', '20.00', 'PEN', '', '1', 'Ejemplo sin stock inicial', '1', 'Cero de ejemplo', '0', 'EXCLUSIVE', '', 'azul', '4 L'],
        ['DEMO-SRV-001', 'Servicio sintético', 'SERVICIO', 'h', 'h', '10.00', 'PEN', '', '0', 'Tarifa de ejemplo', '1', 'Cero de ejemplo', '0', 'EXCLUSIVE', '', '', ''],
    ]
    from .exporters import atomic_destination
    with atomic_destination(path) as temp:
        with open(temp, 'w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream, delimiter=delimiter)
            writer.writerow(COLUMNS)
            writer.writerows(rows)
