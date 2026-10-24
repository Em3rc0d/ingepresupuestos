# SPDX-License-Identifier: GPL-3.0-or-later
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from ..domain.errors import ConflictError, StorageError
from .migrations import migrate
from .repositories import Repository


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


class SalesStore:
    """Explicit path; no global DB override, seed, Qt or import-time IO."""
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def transaction(self, write=False):
        connection = None
        try:
            connection = sqlite3.connect(self.path.resolve().as_uri() + '?mode=rw', uri=True, timeout=5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield Repository(connection)
            connection.commit()
        except sqlite3.IntegrityError as exc:
            if connection is not None:
                connection.rollback()
            raise ConflictError('Conflicto de datos: SKU/número duplicado, referencia inválida o revisión protegida.') from exc
        except sqlite3.Error as exc:
            if connection is not None:
                connection.rollback()
            message = 'Base ocupada; cierre otras operaciones y vuelva a intentar.' if 'locked' in str(exc).lower() else 'No se pudo acceder a Ventas. Revise permisos, espacio y respaldo antes de reparar.'
            raise StorageError(message) from exc
        except BaseException:
            if connection is not None:
                connection.rollback()
            raise
        finally:
            if connection is not None:
                connection.close()

    def initialize(self):
        with self.transaction(write=True) as repo:
            migrate(repo.connection, now())
