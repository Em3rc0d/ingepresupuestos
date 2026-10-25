# SPDX-License-Identifier: GPL-3.0-or-later
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QMessageBox

from core.ventas.domain.errors import ValidationError
from utils.i18n import tr
from .background import AsyncDialog
from .common import action, button, combo, field, fill_table, table


class DatasheetsDialog(AsyncDialog):
    def __init__(self, service, item, parent=None):
        super().__init__('Fichas técnicas del artículo', parent)
        self.resize(1020, 740)
        self.service, self.item = service, item
        self.inspection, self.references = None, []
        self.form.addRow(QLabel(item['sku'] + ' · ' + item['name']))
        self.source_kind = combo(self.form, 'Clasificación de fuente', [('Documento aportado (sin validación técnica)', 'DOCUMENTO_APORTADO'), ('Supuesto no validado', 'SUPUESTO_NO_VALIDADO')])
        self.document_date = field(self.form, 'Fecha del documento (AAAA-MM-DD, opcional)')
        self.reference = field(self.form, 'Referencia de fuente / explicación del supuesto')
        controls = QHBoxLayout()
        self.body_layout.addLayout(controls)
        choose = button('Seleccionar PDF / imagen', self.choose, controls)
        self.associate_button = button('Confirmar asociación', self.associate, controls, True)
        self.associate_button.setEnabled(False)
        self.preview = QLabel(tr('No se copian archivos al seleccionar. Confirme para guardar una copia administrada. PDF/PNG/JPEG; hasta 20 MiB.'))
        self.preview.setWordWrap(True)
        self.body_layout.addWidget(self.preview)
        self.tbl = table(['Documento', 'Fecha', 'Fuente', 'SHA256', 'Tamaño', 'Disponibilidad'])
        self.body_layout.addWidget(self.tbl, 1)
        footer = QHBoxLayout()
        self.outer.addLayout(footer)
        button('Actualizar disponibilidad', self.refresh, footer)
        button('Guardar copia de ficha seleccionada', self.export_selected, footer)
        retire = button('Retirar asociación del artículo', self.retire, footer)
        button('Cerrar', self.reject, footer)
        choose.setEnabled(not service.readonly)
        retire.setEnabled(not service.readonly)
        note = QLabel(tr('Retirar no borra archivos ni referencias de cotizaciones anteriores. El backup SQLite habitual NO incluye fichas. Use el paquete de respaldo del Inicio Ventas. No se extraen coberturas ni se abren/ejecutan adjuntos.'))
        note.setWordWrap(True)
        self.body_layout.addWidget(note)
        self.watch()
        self.refresh()

    def refresh(self):
        if self.busy:
            return
        item_id = self.item['id']
        def read():
            references = self.service.datasheets(item_id)
            return [(r, self.service.datasheet_status(r)) for r in references]
        self.start(read, self.show_references)

    def show_references(self, values):
        self.references = [reference for reference, status in values]
        fill_table(self.tbl, [[r['filename'], r['document_date'] or tr('Desconocida'), r['source_kind'], r['sha256'], str(r['size']), status] for r, status in values])

    def choose(self):
        path, _ = QFileDialog.getOpenFileName(self, tr('Seleccionar ficha técnica'), '', 'PDF / imagen (*.pdf *.png *.jpg *.jpeg)')
        if path:
            self.inspection = None
            self.associate_button.setEnabled(False)
            self.start(lambda: self.service.inspect_datasheet(path), self.show_inspection)

    def show_inspection(self, inspection):
        self.inspection = inspection
        self.preview.setText(f"{inspection['filename']} · {inspection['mime']} · {inspection['size']} bytes\nSHA256: {inspection['sha256']}\n" + tr('Archivo aún sin copiar; confirme la asociación.'))
        self.associate_button.setEnabled(not self.service.readonly)
        self.mark_dirty()

    @action
    def associate(self):
        if self.busy or self.inspection is None:
            return
        if not self.reference.text().strip():
            raise ValidationError('Describa la fuente o el supuesto de la ficha.')
        answer = QMessageBox.question(self, tr('Asociar ficha'), tr('¿Copiar el archivo al almacén administrado y asociarlo al artículo? No se modifica ninguna cotización guardada.'))
        if answer != QMessageBox.Yes:
            return
        item_id, inspection = self.item['id'], self.inspection
        doc_date, kind, reference = self.document_date.text().strip(), self.source_kind.currentData(), self.reference.text().strip()
        self.associate_button.setEnabled(False)
        self.start(lambda: self.service.attach_datasheet(item_id, inspection, doc_date, kind, reference), self.associated)

    def associated(self, reference):
        self.inspection = None
        self.dirty = False
        self.preview.setText(tr('Ficha asociada al artículo. Para un borrador ya abierto, actualice expresamente sus referencias desde el editor de línea.'))
        self.refresh()

    def selected(self):
        index = self.tbl.currentRow()
        if not 0 <= index < len(self.references):
            raise ValidationError('Seleccione una ficha asociada.')
        return self.references[index]

    @action
    def retire(self):
        reference = self.selected()
        answer = QMessageBox.question(self, tr('Retirar ficha'), tr('¿Retirar la asociación activa? Se conservan archivo, metadatos y referencias históricas.'))
        if answer == QMessageBox.Yes:
            item_id, identifier = self.item['id'], reference['id']
            self.start(lambda: self.service.retire_datasheet(item_id, identifier), lambda result: self.refresh())

    @action
    def export_selected(self):
        reference = self.selected()
        path, _ = QFileDialog.getSaveFileName(self, tr('Guardar copia documental'), reference['filename'], 'PDF / imagen (*.pdf *.png *.jpg *.jpeg)')
        if path:
            self.start(lambda: self.service.export_datasheet(reference, path), lambda result: QMessageBox.information(self, tr('Ficha'), tr('Copia guardada; no se ha abierto ni ejecutado.')))


class PackageDialog(AsyncDialog):
    def __init__(self, service, parent=None):
        super().__init__('Respaldo completo con fichas', parent)
        self.service = service
        message = QLabel(tr('El paquete ZIP contiene la SQLite COMPLETA: Construcción, Ventas y usuarios, además de todas las fichas históricas. No tiene cifrado. Guárdelo en una ubicación privada. El backup SQLite habitual no incluye documentos externos. La restauración requiere cerrar la app y seguir la guía; no se sobrescriben datos desde este diálogo.'))
        message.setWordWrap(True)
        self.body_layout.addWidget(message)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.body_layout.addWidget(self.status)
        controls = QHBoxLayout()
        self.outer.addLayout(controls)
        self.export_button = button('Elegir destino y confirmar respaldo', self.export, controls, True)
        self.export_button.setEnabled(service.is_admin and not service.readonly)
        button('Cerrar', self.reject, controls)

    @action
    def export(self):
        path, _ = QFileDialog.getSaveFileName(self, tr('Paquete privado completo'), 'ingepresupuestos-datos.zip', 'ZIP (*.zip)')
        if not path:
            return
        answer = QMessageBox.question(self, tr('Confirmar respaldo privado'), tr('¿Exportar base completa y fichas históricas al ZIP seleccionado? Incluye datos de ambas unidades y usuarios.'))
        if answer != QMessageBox.Yes:
            return
        self.status.setText(tr('Creando snapshot SQLite y copiando fichas; no cierre hasta terminar…'))
        self.export_button.setEnabled(False)
        self.start(lambda: self.service.export_sales_package(path), self.done_export)

    def done_export(self, result):
        self.status.setText(f"Paquete creado · {result['files']} archivos documentales\nSHA256 SQLite: {result['database_sha256']}\n" + tr('La generación no demuestra que la restauración haya sido probada.'))
        self.export_button.setEnabled(True)
