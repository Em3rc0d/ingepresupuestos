# SPDX-License-Identifier: GPL-3.0-or-later
"""Content-addressed, bounded documents. No files are copied during inspection."""
from hashlib import sha256
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from ..domain.errors import StorageError, ValidationError

MAX_FILE_BYTES = 20 * 1024 * 1024
MIMES = {'.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}
EXTENSIONS = {'application/pdf': '.pdf', 'image/png': '.png', 'image/jpeg': '.jpg'}


def inspect_file(path):
    candidate = Path(path)
    extension = candidate.suffix.lower()
    if extension not in MIMES:
        raise ValidationError('Solo se admiten PDF, PNG o JPEG. No se ejecutan adjuntos.')
    try:
        with candidate.open('rb') as stream:
            content = stream.read(MAX_FILE_BYTES + 1)
    except OSError as exc:
        raise StorageError('La ficha seleccionada ya no se puede leer.') from exc
    if not content or len(content) > MAX_FILE_BYTES:
        raise ValidationError('Ficha vacía o superior a 20 MiB.')
    mime = MIMES[extension]
    signatures = {'application/pdf': content.startswith(b'%PDF-'), 'image/png': content.startswith(b'\x89PNG\r\n\x1a\n'), 'image/jpeg': content.startswith(b'\xff\xd8\xff')}
    if not signatures[mime]:
        raise ValidationError('La firma del archivo no coincide con su extensión PDF/PNG/JPEG.')
    name = re.sub(r'[\x00-\x1f\x7f/\\]', '', candidate.name)[:180]
    return {'source_path': str(candidate), 'filename': name, 'mime': mime, 'size': len(content), 'sha256': sha256(content).hexdigest()}


def validate_reference(reference):
    if not re.fullmatch(r'[0-9a-f]{64}', reference.get('sha256', '')):
        raise ValidationError('SHA256 de ficha inválido.')
    name = reference.get('filename', '')
    if not name or Path(name).name != name or '/' in name or '\\' in name or len(name) > 180:
        raise ValidationError('Nombre de ficha no seguro.')
    if reference.get('mime') not in EXTENSIONS or not isinstance(reference.get('size'), int) or not 1 <= reference['size'] <= MAX_FILE_BYTES:
        raise ValidationError('Metadatos de ficha no compatibles.')
    if reference.get('source_kind') not in ('DOCUMENTO_APORTADO', 'SUPUESTO_NO_VALIDADO'):
        raise ValidationError('Clasifique la fuente de la ficha de manera explícita.')


class ManagedDatasheets:
    def __init__(self, root):
        self.root = Path(root)

    def path(self, digest, mime):
        if not re.fullmatch(r'[0-9a-f]{64}', digest) or mime not in EXTENSIONS:
            raise ValidationError('Identificación interna de ficha no válida.')
        target = self.root / (digest + EXTENSIONS[mime])
        if self.root.is_symlink() or target.is_symlink():
            raise StorageError('Almacén de fichas con enlace simbólico no admitido.')
        if target.resolve().parent != self.root.resolve():
            raise StorageError('Ruta de ficha fuera del almacén administrado.')
        return target

    def status(self, reference):
        validate_reference(reference)
        path = self.path(reference['sha256'], reference['mime'])
        try:
            if not path.is_file() or path.stat().st_size != reference['size']:
                return 'ARCHIVO NO DISPONIBLE'
            with path.open('rb') as stream:
                actual = sha256(stream.read(MAX_FILE_BYTES + 1)).hexdigest()
            return 'DISPONIBLE (hash coincide; contenido no validado técnicamente)' if actual == reference['sha256'] else 'ARCHIVO NO DISPONIBLE (hash diferente)'
        except OSError:
            return 'ARCHIVO NO DISPONIBLE'

    def store(self, inspection):
        current = inspect_file(inspection['source_path'])
        if any(current[key] != inspection[key] for key in ('sha256', 'size', 'mime', 'filename')):
            raise ValidationError('La ficha cambió desde la vista previa. Vuelva a seleccionarla.')
        destination = self.path(current['sha256'], current['mime'])
        self.root.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            reference = {**current, 'source_kind': 'DOCUMENTO_APORTADO'}
            if not self.status(reference).startswith('DISPONIBLE'):
                raise StorageError('Ya existe un archivo administrado inconsistente; revise su respaldo.')
            return destination.name
        temporary = None
        try:
            with open(current['source_path'], 'rb') as source:
                content = source.read(MAX_FILE_BYTES + 1)
            if len(content) != current['size'] or sha256(content).hexdigest() != current['sha256']:
                raise ValidationError('La ficha cambió durante la confirmación; no fue asociada.')
            with NamedTemporaryFile(prefix='.ficha-', dir=self.root, delete=False) as target:
                temporary = Path(target.name)
                target.write(content)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, destination)
            return destination.name
        except OSError as exc:
            raise StorageError('No se pudo guardar la ficha administrada. Revise permisos y espacio.') from exc
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass


def public_reference(row):
    return {'id': row['id'], 'item_id': row['item_id'], 'filename': row['nombre'], 'mime': row['mime'],
            'size': row['tamano'], 'sha256': row['sha256'], 'document_date': row['fecha_documento'],
            'source_kind': row['fuente_tipo'], 'reference': row['referencia'], 'actor': row['actor'], 'registered_at': row['registrada_en']}
