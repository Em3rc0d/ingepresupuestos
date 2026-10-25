# SPDX-License-Identifier: GPL-3.0-or-later
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit

from core.ventas.domain.errors import ValidationError
from utils.i18n import tr
from .background import AsyncDialog
from .common import action, button, field, fill_table, table


class ConstructionDialog(AsyncDialog):
    def __init__(self, service, code, parent=None):
        super().__init__('Añadir desde Construcción (solo lectura)', parent)
        self.resize(1000, 720)
        self.service, self.code = service, code
        self.snapshot, self.result_line, self.parts = None, None, []
        self.projects = QComboBox()
        self.projects.setAccessibleName(tr('Proyecto de Construcción'))
        self.form.addRow(tr('Proyecto'), self.projects)
        self.search = field(self.form, 'Buscar partida por código / descripción')
        controls = QHBoxLayout()
        self.body_layout.addLayout(controls)
        button('Buscar partidas', self.load_parts, controls)
        button('Previsualizar partida seleccionada', self.preview, controls)
        self.tbl = table(['Código', 'Partida', 'Unidad origen', 'Metrado referencia', 'Costo técnico GUARDADO'])
        self.body_layout.addWidget(self.tbl, 1)
        self.details = QLabel(tr('La lectura no modifica la obra ni su almacén. El costo técnico no se convierte en precio de venta.'))
        self.details.setWordWrap(True)
        self.body_layout.addWidget(self.details)
        self.quantity = field(self.form, 'Cantidad de venta explícita')
        self.price = field(self.form, 'Precio unitario de venta (' + code + ')', '', 'Obligatorio, no se copia del costo ACU')
        footer = QHBoxLayout()
        self.outer.addLayout(footer)
        self.confirm = button('Añadir copia a la cotización', self.apply, footer, True)
        self.confirm.setEnabled(False)
        button('Cerrar', self.reject, footer)
        self.projects.currentIndexChanged.connect(self.project_changed)
        self.tbl.itemSelectionChanged.connect(self.selection_changed)
        self.watch()
        self.start(service.construction_projects, self.show_projects)

    def show_projects(self, projects):
        self.projects.blockSignals(True)
        self.projects.clear()
        for project in projects:
            self.projects.addItem(project['nombre'] + ' · ' + project['moneda'], project['id'])
        self.projects.blockSignals(False)
        if not projects:
            self.details.setText(tr('No hay proyectos accesibles para esta sesión. Puede seguir cotizando líneas libres y del catálogo.'))
        else:
            self.load_parts()
        self.dirty = False

    def project_changed(self, *args):
        self.snapshot = None
        self.confirm.setEnabled(False)
        self.load_parts()

    @action
    def load_parts(self):
        project_id, search = self.projects.currentData(), self.search.text().strip()
        if project_id is None or self.busy:
            return
        self.snapshot = None
        self.confirm.setEnabled(False)
        self.start(lambda: self.service.construction_parts(project_id, search), self.show_parts)

    def show_parts(self, parts):
        self.parts = parts
        self.tbl.blockSignals(True)
        fill_table(self.tbl, [[p['item'], p['descripcion'], p['unidad'], p['quantity'], p['cost']] for p in parts])
        self.tbl.blockSignals(False)
        self.details.setText(tr('Seleccione una partida y previsualice. Límite de 5000 resultados; refine la búsqueda si hace falta.'))

    def selection_changed(self):
        self.snapshot = None
        self.confirm.setEnabled(False)

    @action
    def preview(self):
        index = self.tbl.currentRow()
        if not 0 <= index < len(self.parts):
            raise ValidationError('Seleccione una partida cotizable.')
        project_id, part_id = self.projects.currentData(), self.parts[index]['id']
        self.confirm.setEnabled(False)
        self.start(lambda: self.service.preview_construction(project_id, part_id), self.show_snapshot)

    def show_snapshot(self, snapshot):
        self.snapshot = snapshot
        self.details.setText(
            snapshot['description'] + '\n' +
            f"Proyecto {snapshot['source_project_id']} / partida {snapshot['source_partida_id']} · {snapshot['unit']}\n"
            f"Costo unitario técnico GUARDADO (interno): {snapshot['cost_basis'] or 'desconocido'} {snapshot['cost_currency']}\n"
            f"SHA256 origen: {snapshot['source_hash']}\n" + '\n'.join(snapshot['warnings']))
        self.quantity.setText(snapshot['quantity'] if snapshot['quantity'] not in ('0', '0.0', None) else '')
        self.price.clear()
        compatible = snapshot['cost_currency'] == self.code
        self.confirm.setEnabled(compatible)
        if not compatible:
            self.details.setText(self.details.text() + '\n' + tr('Moneda incompatible con la cotización. Cambie de documento; no hay conversión automática.'))

    @action
    def apply(self):
        if self.busy or self.snapshot is None:
            return
        self.result_line = self.service.line_from_construction(self.snapshot, self.code, self.price.text().strip(), self.quantity.text().strip())
        self.accept()
