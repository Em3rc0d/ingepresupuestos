# SPDX-License-Identifier: GPL-3.0-or-later
from copy import deepcopy
from dataclasses import asdict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDialog, QFormLayout, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget)

from core.ventas.domain.errors import ValidationError
from core.ventas.domain.models import Client, Item, ItemType
from core.ventas.domain.money import SCALES, precise
from core.ventas.domain.quantity import UNITS
from utils.i18n import tr
from .common import DirtyDialog, TaxFields, action, button, combo, field, fill_table, table


class ClientDialog(DirtyDialog):
    def __init__(self, service, client=None, parent=None):
        super().__init__('Cliente', parent)
        self.service, self.original = service, client or {}
        self.edits = {key: field(self.form, label, self.original.get(key, '')) for key, label in (
            ('name', 'Nombre / razón social'), ('document', 'Documento (opcional)'),
            ('email', 'Correo'), ('phone', 'Teléfono'), ('contact', 'Contacto'), ('address', 'Dirección'), ('notes', 'Notas'))}
        self.active = QCheckBox(tr('Activo'))
        self.active.setChecked(self.original.get('active', True))
        self.form.addRow(self.active)
        self.result_data = None
        self.save_buttons(self.save)
        self.watch()

    @action
    def save(self):
        data = {key: edit.text().strip() for key, edit in self.edits.items()}
        data['active'] = self.active.isChecked()
        if self.original.get('id'):
            data['id'] = self.original['id']
        self.result_data = self.service.save_client(data)
        self.accept()


class ItemDialog(DirtyDialog):
    def __init__(self, service, item=None, parent=None):
        super().__init__('Artículo / servicio comercial', parent)
        self.service, self.original = service, deepcopy(item or {})
        self.sku = field(self.form, 'SKU único', self.original.get('sku', ''))
        self.sku.setReadOnly(bool(self.original.get('id')))
        self.name = field(self.form, 'Nombre', self.original.get('name', ''))
        self.description = field(self.form, 'Descripción al cliente', self.original.get('description', ''))
        self.kind = combo(self.form, 'Tipo', [x.value for x in ItemType if x != ItemType.ITEM_LIBRE], self.original.get('kind'))
        self.unit = combo(self.form, 'Unidad de venta / stock', list(UNITS), self.original.get('unit', 'und'))
        self.physical = combo(self.form, 'Unidad física de referencia', list(UNITS), self.original.get('physical_unit', 'und'))
        self.code = combo(self.form, 'Moneda de esta tarifa', list(SCALES), self.original.get('currency', 'PEN'))
        self.price = field(self.form, 'Precio de venta', self.original.get('price', ''), 'Precio explícito; no es costo')
        self.cost = field(self.form, 'Costo interno (opcional)', self.original.get('cost', ''), 'Vacío = desconocido')
        self.stock = QCheckBox(tr('Controlar stock comercial por movimientos'))
        self.stock.setChecked(self.original.get('tracks_stock', False))
        self.form.addRow(self.stock)
        self.active = QCheckBox(tr('Activo en nuevas cotizaciones'))
        self.active.setChecked(self.original.get('active', True))
        self.form.addRow(self.active)
        parents = [('Sin variante / artículo principal', None)] + [(i['sku'] + ' · ' + i['name'], i['id']) for i in service.items() if not i['parent_id'] and i['id'] != self.original.get('id')]
        self.parent_item = combo(self.form, 'Variante de', parents, self.original.get('parent_id'))
        attributes = self.original.get('attributes', {})
        self.color = field(self.form, 'Color de variante', attributes.get('color', ''))
        self.size = field(self.form, 'Tamaño / presentación de variante', attributes.get('size', ''))
        self.tax = TaxFields(self.original.get('tax'))
        self.form.addRow(self.tax)
        self.form.addRow(QLabel(tr('Ficha para cobertura (opcional; no se inventan valores)')))
        formula = self.original.get('formula', {})
        self.coverage = field(self.form, 'Cobertura m²/L/mano', formula.get('coverage', ''))
        self.presentation = field(self.form, 'Contenido físico por unidad de venta', formula.get('presentation_size', ''))
        self.presentation_unit = combo(self.form, 'Unidad del contenido', ['L', 'mL', 'm3'], formula.get('presentation_unit', 'L'))
        self.closed = QCheckBox(tr('Presentación cerrada: vender unidades enteras hacia arriba'))
        self.closed.setChecked(formula.get('closed_presentation', False))
        self.form.addRow(self.closed)
        self.source = field(self.form, 'Ficha técnica / fuente / supuesto', formula.get('source', ''))
        self.components = deepcopy(self.original.get('components', []))
        self.components_table = table(['SKU', 'Cantidad por paquete'])
        self.body_layout.addWidget(QLabel(tr('Componentes internos de paquete (un nivel; no se suman al precio de venta)')))
        self.body_layout.addWidget(self.components_table)
        controls = QHBoxLayout()
        self.body_layout.addLayout(controls)
        button('Añadir componente', self.add_component, controls)
        button('Quitar componente', self.remove_component, controls)
        self._show_components()
        self.result_data = None
        self.save_buttons(self.save)
        self.watch()
        self.code.currentIndexChanged.connect(self.change_currency)
        if self.original.get('id'):
            button('Fichas técnicas del artículo guardado', self.manage_datasheets, self.body_layout)
        else:
            self.body_layout.addWidget(QLabel(tr('Guarde primero el artículo para asociar fichas técnicas.')))

    @action
    def manage_datasheets(self):
        from .datasheets import DatasheetsDialog
        DatasheetsDialog(self.service, self.original, self).exec()

    @action
    def change_currency(self, *args):
        code = self.code.currentData()
        previous = next((i for i in self.service.items(True, code) if i['id'] == self.original.get('id')), None)
        self.price.setText(previous['price'] if previous and previous['price'] is not None else '')
        self.cost.setText(previous['cost'] if previous and previous['cost'] is not None else '')
        self.price.setPlaceholderText(tr('Ingrese tarifa explícita; no hay conversión de moneda'))

    def _show_components(self):
        fill_table(self.components_table, [[c.get('sku', c['item_id']), c['quantity']] for c in self.components])

    @action
    def add_component(self):
        items = [i for i in self.service.items() if i['kind'] != 'PAQUETE' and i['id'] != self.original.get('id')]
        if not items:
            raise ValidationError('Cree antes un producto o servicio componente.')
        chosen, ok = QInputDialog.getItem(self, tr('Componente'), tr('Artículo'), [i['sku'] + ' · ' + i['name'] for i in items], 0, False)
        if not ok:
            return
        item = items[[i['sku'] + ' · ' + i['name'] for i in items].index(chosen)]
        value, ok = QInputDialog.getText(self, tr('Cantidad'), tr('Cantidad por paquete (' + item['unit'] + ')'))
        if ok:
            amount = precise(value, 'Cantidad')
            if amount <= 0:
                raise ValidationError('Cantidad positiva requerida.')
            self.components.append({'item_id': item['id'], 'sku': item['sku'], 'kind': item['kind'], 'quantity': str(amount)})
            self._show_components()
            self.mark_dirty()

    def remove_component(self):
        index = self.components_table.currentRow()
        if index >= 0:
            self.components.pop(index)
            self._show_components()
            self.mark_dirty()

    @action
    def save(self):
        formula = {}
        if self.coverage.text().strip():
            formula['coverage'] = str(precise(self.coverage.text(), 'Cobertura'))
            if precise(formula['coverage']) <= 0:
                raise ValidationError('Cobertura debe ser positiva.')
        if self.presentation.text().strip():
            formula.update(presentation_size=str(precise(self.presentation.text(), 'Contenido')),
                           presentation_unit=self.presentation_unit.currentData(), closed_presentation=self.closed.isChecked())
        formula['source'] = self.source.text().strip() or 'Supuesto no validado'
        data = dict(sku=self.sku.text().strip(), name=self.name.text().strip(), description=self.description.text().strip(),
                    kind=self.kind.currentData(), unit=self.unit.currentData(), physical_unit=self.physical.currentData(),
                    currency=self.code.currentData(), price=str(precise(self.price.text(), 'Precio')),
                    cost=str(precise(self.cost.text(), 'Costo')) if self.cost.text().strip() else None,
                    tracks_stock=self.stock.isChecked(), active=self.active.isChecked(), parent_id=self.parent_item.currentData(),
                    attributes={'color': self.color.text().strip(), 'size': self.size.text().strip()},
                    formula=formula, components=self.components, tax=self.tax.value())
        if self.original.get('id'):
            data['id'] = self.original['id']
        self.result_data = self.service.save_item(data)
        self.accept()


class RecordsView(QWidget):
    def __init__(self, service, clients=False, parent=None):
        super().__init__(parent)
        self.service, self.is_clients = service, clients
        layout = QVBoxLayout(self)
        actions = QHBoxLayout()
        layout.addLayout(actions)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr('Buscar por nombre, documento o SKU'))
        self.search.setAccessibleName(tr('Buscar clientes' if clients else 'Buscar catálogo'))
        actions.addWidget(self.search, 1)
        self.show_inactive = QCheckBox(tr('Incluir archivados'))
        actions.addWidget(self.show_inactive)
        self.new_button = button('Nuevo cliente' if clients else 'Nuevo artículo', self.create, actions, True)
        self.edit_button = button('Editar / archivar', self.edit, actions)
        if not clients:
            tools = QHBoxLayout()
            layout.addLayout(tools)
            import_button = button('Importar CSV', self.import_csv, tools)
            import_button.setEnabled(not service.readonly)
            button('Fichas técnicas del artículo seleccionado', self.datasheets, tools)
        button('Actualizar', self.refresh, actions)
        self.new_button.setEnabled(not service.readonly)
        self.edit_button.setEnabled(not service.readonly)
        self.tbl = table(['Nombre', 'Documento', 'Teléfono', 'Activo'] if clients else ['SKU', 'Nombre', 'Tipo', 'Unidad', 'Precio', 'Moneda', 'Stock', 'Activo'])
        layout.addWidget(self.tbl)
        self.search.textChanged.connect(self.render)
        self.show_inactive.toggled.connect(self.refresh)
        self.tbl.doubleClicked.connect(lambda *_: self.edit() if not service.readonly else None)
        self.records, self.visible = [], []
        self.refresh()

    @action
    def refresh(self, *args):
        self.records = self.service.clients(self.show_inactive.isChecked()) if self.is_clients else self.service.items(self.show_inactive.isChecked())
        self.render()

    def render(self, *args):
        query = self.search.text().casefold()
        self.visible = [r for r in self.records if query in ' '.join(str(r.get(k, '')) for k in ('name', 'sku', 'document', 'phone')).casefold()]
        if self.is_clients:
            rows = [[r['name'], r['document'], r['phone'], tr('Sí') if r['active'] else tr('No')] for r in self.visible]
        else:
            rows = [[r['sku'], r['name'], r['kind'], r['unit'], r['price'], r['currency'], tr('Controlado') if r['tracks_stock'] else tr('Sin seguimiento'), tr('Sí') if r['active'] else tr('No')] for r in self.visible]
        fill_table(self.tbl, rows)

    @action
    def create(self):
        dialog = ClientDialog(self.service, parent=self) if self.is_clients else ItemDialog(self.service, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh()

    @action
    def edit(self):
        index = self.tbl.currentRow()
        if index < 0:
            return
        record = self.visible[index]
        dialog = ClientDialog(self.service, record, self) if self.is_clients else ItemDialog(self.service, record, self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh()

    @action
    def import_csv(self):
        from .csv_import import CatalogImportDialog
        if CatalogImportDialog(self.service, self).exec() == QDialog.Accepted:
            self.refresh()

    @action
    def datasheets(self):
        index = self.tbl.currentRow()
        if not 0 <= index < len(self.visible):
            raise ValidationError('Seleccione un artículo para consultar sus fichas.')
        from .datasheets import DatasheetsDialog
        DatasheetsDialog(self.service, self.visible[index], self).exec()
