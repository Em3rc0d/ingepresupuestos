# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit portable backup: full SQLite snapshot plus all historical managed documents."""
from hashlib import sha256
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED

from ..domain.errors import StorageError, ValidationError
from .datasheets import MAX_FILE_BYTES, ManagedDatasheets, public_reference
from .exporters import atomic_destination
from .repositories import dumps
from .sqlite import now

MAX_PACKAGE_BYTES = 512 * 1024 * 1024


def digest_file(path):
    digest = sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def export_package(database, files_root, destination):
    if Path(destination).suffix.lower() != '.zip':
        raise ValidationError('Seleccione un destino con extensión .zip.')
    managed = ManagedDatasheets(files_root)
    if Path(database).stat().st_size > MAX_PACKAGE_BYTES:
        raise ValidationError('La SQLite supera 512 MiB; se requiere una estrategia de respaldo mayor.')
    try:
        with TemporaryDirectory(prefix='ventas-package-') as temporary:
            snapshot = Path(temporary) / 'presupuestos.db'
            source = target = None
            try:
                source = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
                source.execute('PRAGMA query_only=ON')
                target = sqlite3.connect(snapshot)
                source.backup(target)
            finally:
                if target is not None:
                    target.close()
                if source is not None:
                    source.close()
            connection = sqlite3.connect(snapshot.resolve().as_uri() + '?mode=ro', uri=True)
            try:
                connection.row_factory = sqlite3.Row
                rows = [dict(row) for row in connection.execute('SELECT * FROM ventas_fichas ORDER BY id')]
            finally:
                connection.close()
            distinct = {}
            if len(rows) > 10000:
                raise ValidationError('El paquete supera 10000 referencias históricas; se requiere un respaldo especializado.')
            for row in rows:
                reference = public_reference(row)
                if not managed.status(reference).startswith('DISPONIBLE'):
                    raise StorageError('Respaldo bloqueado: alguna ficha histórica está ausente o cambió. La base SQLite sola no respalda documentos externos.')
                path = managed.path(reference['sha256'], reference['mime'])
                name = path.name
                if row['ruta_interna'] != name:
                    raise StorageError('Referencia de ruta administrada inconsistente.')
                distinct[name] = {'path': path, 'sha256': reference['sha256'], 'bytes': reference['size'], 'mime': reference['mime']}
            if snapshot.stat().st_size + sum(file['bytes'] for file in distinct.values()) > MAX_PACKAGE_BYTES:
                raise ValidationError('El paquete supera 512 MiB. Se requiere una estrategia de respaldo mayor; no se genera uno incompleto.')
            manifest = {'format': 'ingepresupuestos-ventas-package/1', 'created_at': now(), 'complete': True,
                        'scope': 'SQLite completa (Construcción, Ventas y usuarios) y todas las fichas históricas',
                        'database': {'path': 'database/presupuestos.db', 'sha256': digest_file(snapshot), 'bytes': snapshot.stat().st_size},
                        'files': [{'path': 'fichas/' + name, 'sha256': f['sha256'], 'bytes': f['bytes'], 'mime': f['mime']} for name, f in distinct.items()]}
            with atomic_destination(destination) as output:
                with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
                    archive.write(snapshot, 'database/presupuestos.db')
                    for name, file in distinct.items():
                        with file['path'].open('rb') as stream:
                            content = stream.read(MAX_FILE_BYTES + 1)
                        if len(content) != file['bytes'] or sha256(content).hexdigest() != file['sha256']:
                            raise StorageError('Ficha modificada durante respaldo. Se conserva el archivo destino anterior.')
                        archive.writestr('fichas/' + name, content)
                    archive.writestr('manifest.json', dumps(manifest))
            return {'files': len(distinct), 'database_sha256': manifest['database']['sha256'], 'complete': True}
    except sqlite3.Error as exc:
        raise StorageError('No se pudo obtener una copia SQLite consistente para el paquete.') from exc
