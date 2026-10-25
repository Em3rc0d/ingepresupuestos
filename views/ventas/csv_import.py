# SPDX-License-Identifier: GPL-3.0-or-later
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QMessageBox

from core.ventas.domain.errors import ValidationError
from utils.i18n import tr
from .background import AsyncDialog
from .common import action, button, combo, field, fill_table, table


class CatalogImportDialog(AsyncDialog):
    def __init__(self, service, parent=None):
        super().__init__('Importar catálogo CSV', parent)
        self.resize(980, 700)
        self.service, self.preview = service, None
        self.path = field(self.form, 'Archivo CSV elegido')
        self.path.setReadOnly(True)
        self.mode = combo(self.form, 'Estrategia', [('Crear solo (existentes omitidos)', 'CREAR_SOLO'), ('Crear y actualizar existentes', 'ACTUALIZAR_EXISTENTES')])
        self.delimiter = combo(self.form, 'Separador', [('Detectar por encabezados', None), ('Coma', ','), ('Punto y coma', ';')])
        controls = QHBoxLayout()
        self.body_layout.addLayout(controls)
        button('Seleccionar CSV', self.choose, controls)
        button('Guardar plantilla sintética', self.template, controls)
        button('Validar y previsualizar', self.read, controls)
        hint = QLabel(tr('UTF-8/BOM · Hasta 5 MiB y 5000 registros · Punto decimal · Sin stock inicial. La vista previa no escribe datos. Corregir todos los errores antes de confirmar.'))
        hint.setWordWrap(True)
        self.body_layout.addWidget(hint)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.body_layout.addWidget(self.summary)
        self.records = table(['Fila', 'SKU', 'Operación', 'Artículo / precio propuesto'])
        self.errors = table(['Fila', 'Campo', 'Causa'])
        self.body_layout.addWidget(self.records, 2)
        self.body_layout.addWidget(self.errors, 1)
        footer = QHBoxLayout()
        self.outer.addLayout(footer)
        self.confirm_button = button('Confirmar lote completo', self.confirm, footer, True)
        self.confirm_button.setEnabled(False)
        button('Cerrar', self.reject, footer)
        self.mode.currentIndexChanged.connect(self.invalidate)
        self.delimiter.currentIndexChanged.connect(self.invalidate)

    def invalidate(self, *args):
        self.preview = None
        self.confirm_button.setEnabled(False)
        self.summary.setText(tr('Seleccione archivo y genere una nueva vista previa.'))

    def choose(self):
        path, _ = QFileDialog.getOpenFileName(self, tr('Seleccionar CSV'), '', 'CSV (*.csv)')
        if path:
            self.path.setText(path)
            self.invalidate()
            self.read()

    @action
    def read(self):
        if not self.path.text():
            raise ValidationError('Seleccione un CSV antes de previsualizar.')
        path, mode, delimiter = self.path.text(), self.mode.currentData(), self.delimiter.currentData()
        self.confirm_button.setEnabled(False)
        self.summary.setText(tr('Leyendo y validando; no se escribe en el catálogo…'))
        self.start(lambda: self.service.preview_catalog_csv(path, mode, delimiter), self.show_preview)

    def show_preview(self, result):
        self.preview = result
        fill_table(self.records, [[r['row'], r['sku'], r['operation'], (r['item']['name'] + ' · ' + r['item']['price'] + ' ' + r['item']['currency']) if r['item'] else tr('Conserva datos existentes')] for r in result['rows']])
        fill_table(self.errors, [[e['row'], e['field'], e['cause']] for e in result['errors']])
        self.summary.setText(f"Nuevos: {result['created']} · Actualizados: {result['updated']} · Omitidos: {result['skipped']} · Errores: {len(result['errors'])}\nSHA256 CSV: {result['sha256']}")
        self.confirm_button.setEnabled(not result['errors'] and result['created'] + result['updated'] > 0)

    @action
    def confirm(self):
        if self.busy or self.preview is None or self.preview['errors']:
            return
        answer = QMessageBox.question(self, tr('Confirmar importación'), tr('¿Guardar el lote previsualizado en una única transacción? Esta operación no registra stock.'))
        if answer != QMessageBox.Yes:
            return
        preview = self.preview
        self.confirm_button.setEnabled(False)
        self.start(lambda: self.service.apply_catalog_import(preview), self.saved)

    def saved(self, result):
        QMessageBox.information(self, tr('Importación registrada'), f"Nuevos: {result['created']} · Actualizados: {result['updated']} · Omitidos: {result['skipped']}")
        self.accept()

    @action
    def template(self):
        path, _ = QFileDialog.getSaveFileName(self, tr('Guardar plantilla de catálogo'), 'catalogo-ejemplo.csv', 'CSV (*.csv)')
        if path:
            self.service.catalog_template(path, self.delimiter.currentData() or ',')
            QMessageBox.information(self, tr('Plantilla'), tr('Plantilla sintética guardada. No contiene existencias ni precios de mercado.'))
