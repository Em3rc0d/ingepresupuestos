# SPDX-License-Identifier: GPL-3.0-or-later
from copy import deepcopy
from dataclasses import asdict
from decimal import Decimal
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QTextBrowser, QVBoxLayout)

from core.ventas.domain.errors import SalesError, ValidationError
from core.ventas.domain.models import QuoteLine
from core.ventas.domain.money import SCALES, precise
from core.ventas.infrastructure.exporters import export_pdf, export_xlsx, html_preview
from core.ventas.infrastructure.repositories import fingerprint
from utils.i18n import tr
from .common import DirtyDialog, TaxFields, action, button, combo, field, fill_table, table
from .catalog import ClientDialog, ItemDialog
from .quantity import QuantityDialog


class LineDialog(DirtyDialog):
    def __init__(self, service, code, line=None, parent=None):
        super().__init__('Línea de cotización', parent)
        self.service, self.code = service, code
        self.line = deepcopy(line or {})
        self.catalog_unit = self.line.get('unit') if self.line.get('item_id') else None
        self.defaults = {}
        self.catalog = QComboBox()
        self.catalog.setAccessibleName(tr('Seleccionar SKU de catálogo'))
        self.form.addRow(tr('Catálogo'), self.catalog)
        top = QHBoxLayout()
        self.body_layout.addLayout(top)
        button('Cargar artículo seleccionado', self.load_item, top)
        button('Crear artículo en catálogo', self.create_item, top)
        self.description = field(self.form, 'Descripción', self.line.get('description', ''))
        self.kind = combo(self.form, 'Tipo', ['ITEM_LIBRE', 'PRODUCTO', 'SERVICIO', 'MATERIAL_MEDIBLE', 'PAQUETE'], self.line.get('kind', 'ITEM_LIBRE'))
        from core.ventas.domain.quantity import UNITS
        self.unit = combo(self.form, 'Unidad de venta', list(UNITS), self.line.get('unit', 'und'))
        self.quantity = field(self.form, 'Cantidad vendible', self.line.get('quantity', '1'))
        button('Calcular por medidas / cobertura', self.measure, self.body_layout)
        self.formula_label = QLabel()
        self.formula_label.setWordWrap(True)
        self.body_layout.addWidget(self.formula_label)
        self.evidence_label = QLabel()
        self.evidence_label.setWordWrap(True)
        self.body_layout.addWidget(self.evidence_label)
        self.origin_label = QLabel()
        self.origin_label.setWordWrap(True)
        self.body_layout.addWidget(self.origin_label)
        self.datasheets_button = button('Gestionar fichas del artículo', self.manage_datasheets, self.body_layout)
        self.capture_button = button('Capturar fichas actuales para esta línea', self.capture_datasheets, self.body_layout)
        self.price = field(self.form, 'Precio unitario de venta (' + code + ')', self.line.get('price', ''))
        self.cost = field(self.form, 'Costo interno unitario (opcional)', self.line.get('cost', ''))
        self.reason = field(self.form, 'Motivo de precio manual (opcional)', self.line.get('override_reason', ''))
        discount = self.line.get('discount', {'kind': 'PERCENT', 'value': '0'})
        self.discount_kind = combo(self.form, 'Descuento por línea', [('Porcentaje', 'PERCENT'), ('Importe en moneda del documento', 'AMOUNT')], discount['kind'])
        self.discount = field(self.form, 'Valor de descuento', discount['value'])
        self.tax = TaxFields(self.line.get('tax'))
        self.form.addRow(self.tax)
        self.margin = QLabel(tr('Margen desconocido si falta costo.'))
        self.body_layout.addWidget(self.margin)
        self.price.textChanged.connect(self.update_margin)
        self.cost.textChanged.connect(self.update_margin)
        self.result_line = None
        self.save_buttons(self.apply, 'Aplicar línea')
        self.reload_catalog()
        self.show_formula()
        self.watch()
        self.unit.currentIndexChanged.connect(self.clear_formula)
        self.quantity.textEdited.connect(self.clear_formula)
        fixed = bool(self.line.get('item_id') or self.line.get('provenance'))
        self.kind.setEnabled(not fixed)
        self.unit.setEnabled(not fixed)
        self.update_margin()
        self.show_datasheets()

    def reload_catalog(self):
        self.catalog.clear()
        self.catalog.addItem(tr('Seleccione producto / servicio'), None)
        for item in self.service.items(code=self.code):
            self.catalog.addItem(item['sku'] + ' · ' + item['name'] + (' · sin tarifa' if item['price'] is None else ''), item['id'])

    @action
    def load_item(self):
        item_id = self.catalog.currentData()
        if not item_id:
            return
        self.line = self.service.line_from_item(item_id, self.code)
        self.catalog_unit = self.line['unit']
        item = next(i for i in self.service.items(code=self.code) if i['id'] == item_id)
        self.defaults = item['formula']
        self.description.setText(self.line['description'])
        self.kind.setCurrentIndex(self.kind.findData(self.line['kind']))
        self.unit.setCurrentIndex(self.unit.findData(self.line['unit']))
        self.quantity.setText(self.line['quantity'])
        self.price.setText(self.line['price'])
        self.cost.setText(self.line['cost'] or '')
        rule = self.line['tax'] or {}
        self.tax.mode.setCurrentIndex(max(0, self.tax.mode.findData(rule.get('mode'))))
        self.tax.name.setText(rule.get('name', ''))
        self.tax.rate.setText(rule.get('rate', ''))
        self.kind.setEnabled(False)
        self.unit.setEnabled(False)
        self.show_formula()
        self.show_datasheets()

    def show_datasheets(self):
        self.datasheets_button.setEnabled(bool(self.line.get('item_id')))
        self.capture_button.setEnabled(bool(self.line.get('item_id')))
        origin = (self.line.get('provenance') or {}).get('snapshot')
        self.origin_label.setText(
            f"Referencia interna de Construcción · Proyecto {origin['source_project_id']} / partida {origin['source_partida_id']}\n"
            f"Capturada {origin['captured_at']} · SHA256 {origin['source_hash']}\nCosto técnico guardado; precio de venta independiente."
            if origin else '')
        self.evidence_label.setText(tr('Referencias documentales congeladas en esta línea: ') +
            ('\n'.join(r['filename'] + ' · SHA256 ' + r['sha256'] for r in self.line.get('datasheets', [])) or tr('Ninguna.')))

    @action
    def manage_datasheets(self):
        if not self.line.get('item_id'):
            raise ValidationError('Las fichas se administran en artículos guardados. Esta línea conserva sus referencias históricas si las tiene.')
        from .datasheets import DatasheetsDialog
        DatasheetsDialog(self.service, self.service.item(self.line['item_id']), self).exec()

    @action
    def capture_datasheets(self):
        if not self.line.get('item_id'):
            raise ValidationError('Seleccione un artículo de catálogo antes de capturar sus fichas.')
        self.line['datasheets'] = self.service.datasheets(self.line['item_id'])
        self.show_datasheets()
        self.mark_dirty()

    @action
    def create_item(self):
        dialog = ItemDialog(self.service, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.reload_catalog()
            self.catalog.setCurrentIndex(self.catalog.findData(dialog.result_data['id']))
            self.load_item()

    @action
    def measure(self):
        dialog = QuantityDialog(self.unit.currentData(), self.line.get('formula'), self.defaults, self)
        if dialog.exec() == QDialog.Accepted:
            self.line['formula'] = dialog.result_formula
            self.quantity.setText(dialog.result_formula['quantity'])
            self.show_formula()
            self.mark_dirty()

    def clear_formula(self, *args):
        self.line['formula'] = {}
        self.show_formula()

    def show_formula(self):
        formula = self.line.get('formula')
        self.formula_label.setText(
            f"Requerido {formula['required']} {formula['required_unit']} · Vendible {formula['quantity']} {formula['unit']}"
            f" · Equivalente {formula.get('sold_physical', formula['required'])} {formula.get('sold_unit', formula['required_unit'])}\n{formula['source']}"
            if formula else tr('Cantidad manual; no hay fórmula vinculada.'))

    def update_margin(self):
        try:
            price = precise(self.price.text())
            cost = precise(self.cost.text())
            if price <= 0:
                self.margin.setText(tr('Margen no calculable con precio cero.'))
                return
            self.margin.setText(tr('Margen unitario de referencia antes de descuentos/impuestos: ') + f'{(price - cost) / price * 100:.2f}%')
        except ValidationError:
            self.margin.setText(tr('Margen desconocido; costo/precio incompleto.'))

    @action
    def apply(self):
        unit = self.unit.currentData()
        # Catalog units cannot be silently reinterpreted as another presentation.
        if self.line.get('item_id'):
            if unit != self.catalog_unit:
                raise ValidationError('Unidad de SKU fija. Use su unidad de venta o una línea libre.')
        data = dict(self.line)
        data.update(description=self.description.text().strip(), quantity=str(precise(self.quantity.text(), 'Cantidad')),
                    unit=unit, kind=self.kind.currentData(), price=str(precise(self.price.text(), 'Precio')),
                    cost=str(precise(self.cost.text(), 'Costo')) if self.cost.text().strip() else None,
                    override_reason=self.reason.text().strip(), tax=self.tax.value(),
                    discount={'kind': self.discount_kind.currentData(), 'value': self.discount.text().strip()})
        if data.get('item_id'):
            data['kind'] = self.line['kind']
        if not data.get('item_id'):
            data['kind'] = 'SERVICIO' if data.get('provenance') else 'ITEM_LIBRE'
            data['components'] = []
        line = QuoteLine(**data)
        from core.ventas.domain.pricing import calculate
        calculate([line], self.code, {'kind': 'PERCENT', 'value': '0'})
        self.result_line = asdict(line)
        self.accept()


class PreviewDialog(QDialog):
    def __init__(self, service, document, can_issue=False, parent=None):
        super().__init__(parent)
        self.service, self.document = service, deepcopy(document)
        self.setWindowTitle(tr('Vista previa de revisión guardada'))
        self.resize(1080, 760)
        layout = QVBoxLayout(self)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setHtml(html_preview(document))
        self.browser.setAccessibleName(tr('Vista previa de cotización'))
        layout.addWidget(self.browser)
        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        button('Exportar PDF', self.pdf, buttons)
        button('Exportar Excel', self.xlsx, buttons)
        if can_issue:
            self.issue_button = button('Confirmar emisión de esta revisión', self.issue, buttons, True)
            self.issue_button.setEnabled(document['totals']['tax_configured'] and bool(document['lines']) and not service.readonly)
        button('Cerrar', self.reject, buttons)
        self.issued_document = None

    @action
    def pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, tr('Exportar PDF'), f"{self.document['number']}-V{self.document['version']}.pdf", 'PDF (*.pdf)')
        if path:
            if not path.lower().endswith('.pdf'):
                path += '.pdf'
            from core.config import BASE_DIR
            export_pdf(self.document, path, BASE_DIR / 'resources' / 'fonts')
            QMessageBox.information(self, tr('Exportación'), tr('Documento guardado.'))

    @action
    def xlsx(self):
        path, _ = QFileDialog.getSaveFileName(self, tr('Exportar Excel'), f"{self.document['number']}-V{self.document['version']}.xlsx", 'Excel (*.xlsx)')
        if path:
            if not path.lower().endswith('.xlsx'):
                path += '.xlsx'
            export_xlsx(self.document, path)
            QMessageBox.information(self, tr('Exportación'), tr('Documento guardado.'))

    @action
    def issue(self):
        self.issued_document = self.service.save_draft(self.document, issue=True)
        self.accept()


class QuoteEditor(DirtyDialog):
    def __init__(self, service, document=None, parent=None):
        super().__init__('Editor de cotización comercial', parent)
        self.resize(1100, 800)
        self.service = service
        self.document = deepcopy(document or service.new_document())
        self.saved_document = deepcopy(self.document) if self.document['id'] else None
        self.baseline = None
        if self.document['id'] and self.document['version'] > 1:
            versions = service.versions(self.document['id'])
            previous = next((r for r in versions if r['version'] == self.document['version'] - 1), None)
            if previous:
                self.baseline = service.open_document(self.document['id'], previous['id'])
        header = self.document['header']
        self.label = QLabel(f"{self.document['number']} · V{self.document['version']}")
        self.form.addRow(self.label)
        self.title_edit = field(self.form, 'Título / referencia', header['title'])
        self.client = QComboBox()
        self.client.setAccessibleName(tr('Cliente de catálogo o receptor ocasional'))
        self.form.addRow(tr('Cliente'), self.client)
        button('Crear cliente', self.create_client, self.body_layout)
        self.customer_name = field(self.form, 'Nombre del receptor ocasional', header.get('customer', {}).get('name', ''))
        self.customer_document = field(self.form, 'Documento del receptor ocasional', header.get('customer', {}).get('document', ''))
        self.customer_address = field(self.form, 'Dirección del receptor ocasional', header.get('customer', {}).get('address', ''))
        self.code = combo(self.form, 'Moneda de cotización', list(SCALES), header['currency'])
        self.date = field(self.form, 'Fecha (AAAA-MM-DD)', header['date'])
        self.until = field(self.form, 'Vigencia (AAAA-MM-DD)', header['valid_until'])
        self.issuer = field(self.form, 'Emisor textual', header.get('issuer', ''))
        self.conditions = field(self.form, 'Condiciones comerciales', header.get('conditions', ''))
        self.notes = field(self.form, 'Observaciones para el cliente', header.get('notes', ''))
        rule = header['global_discount']
        self.discount_kind = combo(self.form, 'Descuento global', [('Porcentaje', 'PERCENT'), ('Importe', 'AMOUNT')], rule['kind'])
        self.discount = field(self.form, 'Valor de descuento global', rule['value'])
        self.tbl = table(['Descripción', 'Cantidad', 'Unidad', 'P. venta', 'Dto. línea', 'Dto. global', 'Neto', 'Impuesto', 'Total'])
        self.tbl.setMinimumHeight(190)
        self.body_layout.addWidget(self.tbl)
        controls = QHBoxLayout()
        self.body_layout.addLayout(controls)
        button('Añadir línea', self.add_line, controls, True)
        button('Añadir desde Construcción', self.add_construction, controls)
        button('Editar', self.edit_line, controls)
        button('Duplicar', self.duplicate_line, controls)
        button('Eliminar', self.remove_line, controls)
        button('Subir', lambda: self.move_line(-1), controls)
        button('Bajar', lambda: self.move_line(1), controls)
        self.tbl.doubleClicked.connect(lambda *_: self.edit_line())
        self.totals = QLabel()
        self.totals.setWordWrap(True)
        self.outer.addWidget(self.totals)
        self.stock = QLabel()
        self.stock.setWordWrap(True)
        self.body_layout.addWidget(self.stock)
        actions = QHBoxLayout()
        self.outer.addLayout(actions)
        self.save_button = button('Guardar borrador', self.save, actions, True)
        self.preview_button = button('Guardar y vista previa', self.preview, actions)
        button('Ver diferencias', self.show_diff, actions)
        button('Cerrar', self.reject, actions)
        self.reload_clients(header.get('client_id'))
        self.code.currentIndexChanged.connect(self.currency_changed)
        self.discount.textChanged.connect(self.refresh_totals)
        self.discount_kind.currentIndexChanged.connect(self.refresh_totals)
        self.client.currentIndexChanged.connect(self.client_changed)
        self.client_changed()
        self.watch()
        self.refresh_totals()

    def reload_clients(self, selected=None):
        self.client.blockSignals(True)
        self.client.clear()
        self.client.addItem(tr('Receptor ocasional (sin ficha)'), None)
        for client in self.service.clients():
            self.client.addItem(client['name'], client['id'])
        if selected:
            self.client.setCurrentIndex(max(0, self.client.findData(selected)))
        self.client.blockSignals(False)

    def client_changed(self, *args):
        occasional = self.client.currentData() is None
        for edit in (self.customer_name, self.customer_document, self.customer_address):
            edit.setEnabled(occasional)

    @action
    def create_client(self):
        dialog = ClientDialog(self.service, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.reload_clients(dialog.result_data['id'])
            self.client_changed()
            self.mark_dirty()

    def currency_changed(self, *args):
        if self.document['lines']:
            QMessageBox.warning(self, tr('Moneda'), tr('Retire las líneas antes de cambiar moneda. No se realiza conversión automática.'))
            self.code.blockSignals(True)
            self.code.setCurrentIndex(self.code.findData(self.document['header']['currency']))
            self.code.blockSignals(False)
        else:
            self.document['header']['currency'] = self.code.currentData()
            self.refresh_totals()

    def collect(self):
        doc = deepcopy(self.document)
        h = doc['header']
        h.update(title=self.title_edit.text().strip(), client_id=self.client.currentData(), currency=self.code.currentData(),
                 date=self.date.text().strip(), valid_until=self.until.text().strip(), issuer=self.issuer.text().strip(),
                 conditions=self.conditions.text(), notes=self.notes.text(),
                 global_discount={'kind': self.discount_kind.currentData(), 'value': self.discount.text().strip()})
        if h['client_id'] is None:
            h['customer'] = {'name': self.customer_name.text().strip(), 'document': self.customer_document.text().strip(), 'address': self.customer_address.text().strip()}
        return doc

    def selected(self):
        index = self.tbl.currentRow()
        return index if 0 <= index < len(self.document['lines']) else None

    @action
    def add_line(self):
        dialog = LineDialog(self.service, self.code.currentData(), parent=self)
        if dialog.exec() == QDialog.Accepted:
            if len(self.document['lines']) >= 200:
                raise ValidationError('Máximo 200 líneas.')
            self.document['lines'].append(dialog.result_line)
            self.mark_dirty()
            self.refresh_totals()

    @action
    def edit_line(self):
        index = self.selected()
        if index is None:
            return
        dialog = LineDialog(self.service, self.code.currentData(), self.document['lines'][index], self)
        if dialog.exec() == QDialog.Accepted:
            self.document['lines'][index] = dialog.result_line
            self.mark_dirty()
            self.refresh_totals()

    @action
    def add_construction(self):
        from .construction import ConstructionDialog
        dialog = ConstructionDialog(self.service, self.code.currentData(), self)
        if dialog.exec() == QDialog.Accepted:
            if len(self.document['lines']) >= 200:
                raise ValidationError('Máximo 200 líneas.')
            self.document['lines'].append(dialog.result_line)
            self.mark_dirty()
            self.refresh_totals()

    def duplicate_line(self):
        index = self.selected()
        if index is not None and len(self.document['lines']) < 200:
            line = deepcopy(self.document['lines'][index])
            line['id'] = str(uuid4())
            self.document['lines'].insert(index + 1, line)
            self.mark_dirty()
            self.refresh_totals()

    def remove_line(self):
        index = self.selected()
        if index is not None:
            self.document['lines'].pop(index)
            self.mark_dirty()
            self.refresh_totals()

    def move_line(self, delta):
        index = self.selected()
        lines = self.document['lines']
        if index is not None and 0 <= index + delta < len(lines):
            lines[index], lines[index + delta] = lines[index + delta], lines[index]
            self.mark_dirty()
            self.refresh_totals()
            self.tbl.selectRow(index + delta)

    def refresh_totals(self, *args):
        try:
            doc = self.collect()
            result = self.service.calculate(doc)
            rows = []
            for line, amount in zip(doc['lines'], result['lines']):
                rows.append([line['description'], line['quantity'], line['unit'], line['price'], amount['line_discount'], amount['global_discount'], amount['net'], amount['tax'] if amount['tax_known'] else tr('SIN DEFINIR'), amount['total']])
            fill_table(self.tbl, rows)
            status = tr('Impuestos configurados') if result['tax_configured'] else tr('Impuestos sin configurar: emisión bloqueada; total provisional')
            self.totals.setText(f"{status}\n{result['currency']} · Neto {result['net']} · Impuesto {result['tax']} · TOTAL {result['total']}")
            self.stock.setText('\n'.join(self.service.stock_warnings(doc['lines'])) + '\n' + tr('Reservado = 0 (sin motor de reservas). Cotizar no mueve stock.'))
            self.save_button.setEnabled(not self.service.readonly)
            self.preview_button.setEnabled(not self.service.readonly)
        except (SalesError, KeyError) as exc:
            self.totals.setText(str(exc))
            self.save_button.setEnabled(False)
            self.preview_button.setEnabled(False)

    @action
    def save(self):
        self.document = self.service.save_draft(self.collect())
        self.saved_document = deepcopy(self.document)
        self.label.setText(f"{self.document['number']} · V{self.document['version']}")
        self.dirty = False
        self.refresh_totals()
        return self.document

    @action
    def preview(self):
        doc = self.save()
        if doc is None:
            return
        preview = PreviewDialog(self.service, doc, True, self)
        preview.exec()
        if preview.issued_document:
            self.document = preview.issued_document
            self.accept()

    @action
    def show_diff(self):
        doc = self.collect()
        doc['totals'] = self.service.calculate(doc)
        baseline = self.baseline or self.saved_document
        if baseline is None:
            QMessageBox.information(self, tr('Diferencias'), tr('Cotización nueva sin versión anterior.'))
        else:
            QMessageBox.information(self, tr('Diferencias con versión anterior / último guardado'), '\n'.join(self.service.diff(baseline, doc)))
