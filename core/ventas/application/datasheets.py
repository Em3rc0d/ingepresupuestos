# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import date
from uuid import uuid4

from ..domain.errors import ValidationError
from ..infrastructure.datasheets import ManagedDatasheets, inspect_file, public_reference, validate_reference
from ..infrastructure.data_package import export_package
from ..infrastructure.sqlite import now


class DatasheetsMixin:
    def datasheet_store(self):
        return ManagedDatasheets(self.store.path.parent / 'ventas' / 'fichas')

    def inspect_datasheet(self, path):
        self.writable()
        return inspect_file(path)

    def datasheets(self, item_id, include_retired=False):
        with self.store.transaction() as repo:
            repo.item(item_id)
            return [public_reference(row) for row in repo.datasheets(item_id, include_retired)]

    def datasheet_status(self, reference):
        return self.datasheet_store().status(reference)

    def attach_datasheet(self, item_id, inspection, document_date, source_kind, reference):
        self.writable()
        if document_date:
            try:
                date.fromisoformat(document_date)
            except ValueError:
                raise ValidationError('Fecha de documento inválida; déjela vacía si es desconocida.') from None
        if source_kind not in ('DOCUMENTO_APORTADO', 'SUPUESTO_NO_VALIDADO'):
            raise ValidationError('Seleccione tipo de fuente explícito.')
        if not reference.strip() or len(reference) > 1000:
            raise ValidationError('Describa la fuente o el supuesto (máximo 1000 caracteres).')
        record = {'id': str(uuid4()), 'item_id': item_id, 'filename': inspection['filename'], 'mime': inspection['mime'],
                  'size': inspection['size'], 'sha256': inspection['sha256'], 'document_date': document_date,
                  'source_kind': source_kind, 'reference': reference.strip(), 'actor': self.actor, 'registered_at': now()}
        validate_reference(record)
        # Copy only after explicit UI confirmation. Rollback can leave an unreferenced
        # content-addressed blob; never delete it automatically (another item may use it).
        with self.store.transaction(True) as repo:
            repo.item(item_id)
            if len(repo.datasheets(item_id)) >= 10:
                raise ValidationError('Máximo 10 fichas activas por artículo; retire asociaciones anteriores si corresponde.')
            internal_path = self.datasheet_store().store(inspection)
            repo.add_datasheet(record, internal_path)
        return record

    def retire_datasheet(self, item_id, datasheet_id):
        self.writable()
        with self.store.transaction(True) as repo:
            active = repo.datasheets(item_id)
            if not any(row['id'] == datasheet_id for row in active):
                raise ValidationError('La ficha ya no está asociada activamente al artículo.')
            repo.retire_datasheet(datasheet_id, self.actor, now())

    def export_sales_package(self, destination):
        self.writable()
        if not self.is_admin:
            raise ValidationError('El respaldo completo requiere administrador: incluye SQLite de ambas unidades y usuarios.')
        return export_package(self.store.path, self.datasheet_store().root, destination)

    def export_datasheet(self, reference, destination):
        store = self.datasheet_store()
        if not store.status(reference).startswith('DISPONIBLE'):
            raise ValidationError('ARCHIVO NO DISPONIBLE; la cotización conserva su referencia histórica.')
        from ..infrastructure.exporters import atomic_destination
        from hashlib import sha256
        from ..infrastructure.datasheets import MAX_FILE_BYTES
        from pathlib import Path
        from ..infrastructure.datasheets import MIMES
        if MIMES.get(Path(destination).suffix.lower()) != reference['mime']:
            raise ValidationError('La extensión de destino debe coincidir con el PDF/PNG/JPEG original.')
        source = store.path(reference['sha256'], reference['mime'])
        with source.open('rb') as stream:
            content = stream.read(MAX_FILE_BYTES + 1)
        if len(content) != reference['size'] or sha256(content).hexdigest() != reference['sha256']:
            raise ValidationError('La ficha cambió antes de exportarla.')
        with atomic_destination(destination) as target:
            target.write_bytes(content)
