# SPDX-License-Identifier: GPL-3.0-or-later
from copy import deepcopy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QTableWidgetItem

from core.ventas.domain.errors import ValidationError
from core.ventas.domain.formulas import calculate
from .common import DirtyDialog, action, button, combo, field, table
from utils.i18n import tr


class QuantityDialog(DirtyDialog):
    def __init__(self, unit, formula=None, defaults=None, parent=None):
        super().__init__('Calcular cantidad vendible', parent)
        self.unit = unit
        formula = formula or {}
        params = deepcopy(defaults or {})
        params.update(formula.get('params', {}))
        self.method = combo(self.form, 'Método', ['MANUAL', 'LONGITUD', 'AREA', 'VOLUMEN', 'COBERTURA'], formula.get('method', 'MANUAL'))
        self.manual = field(self.form, 'Cantidad manual (' + unit + ')', params.get('quantity', ''))
        self.length_unit = combo(self.form, 'Unidad de todas las medidas', ['m', 'cm', 'mm'], 'm')
        self.rows = table(['Largo', 'Ancho', 'Alto', 'Piezas / repeticiones'])
        from PySide6.QtWidgets import QAbstractItemView
        self.rows.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.rows.setMinimumHeight(160)
        self.body_layout.addWidget(QLabel(tr('Filas para sumar medidas (ancho/alto se usan según método)')))
        self.body_layout.addWidget(self.rows)
        controls = QHBoxLayout()
        self.body_layout.addLayout(controls)
        button('Añadir fila', self.add_row, controls)
        button('Eliminar fila', self.remove_row, controls)
        saved_rows = params.get('rows') or [{'length': '', 'width': '', 'height': '', 'pieces': '1', 'length_unit': 'm'}]
        if saved_rows:
            self.length_unit.setCurrentIndex(max(0, self.length_unit.findData(saved_rows[0]['length_unit'])))
        for row in saved_rows:
            self._insert_row(row)
        self.area = field(self.form, 'Superficie para cobertura (m²)', params.get('area', ''))
        self.coats = field(self.form, 'Manos', params.get('coats', ''))
        self.coverage = field(self.form, 'Cobertura (m²/L/mano)', params.get('coverage', ''))
        self.extra = field(self.form, 'Consumo adicional (%)', params.get('extra_percent', ''), '0 explícito si no corresponde')
        self.size = field(self.form, 'Contenido de cada ' + unit + ' (opcional)', params.get('presentation_size', ''))
        self.size_unit = combo(self.form, 'Unidad del contenido', ['L', 'mL', 'm3'], params.get('presentation_unit', 'L'))
        self.closed = QCheckBox(tr('Presentación cerrada: redondear unidades vendibles hacia arriba'))
        self.closed.setChecked(params.get('closed_presentation', False))
        self.form.addRow(self.closed)
        self.source = field(self.form, 'Ficha / referencia / supuesto', params.get('source', ''))
        self.summary = QLabel(tr('Calcule para ver consumo requerido y cantidad vendible.'))
        self.summary.setWordWrap(True)
        self.body_layout.addWidget(self.summary)
        button('Calcular y mostrar resultado', self.recalculate, self.body_layout)
        self.result_formula = None
        self.save_buttons(self.apply, 'Aplicar cantidad')
        self.rows.cellChanged.connect(self.mark_dirty)
        self.watch()

    def _insert_row(self, values):
        i = self.rows.rowCount()
        self.rows.insertRow(i)
        for j, key in enumerate(('length', 'width', 'height', 'pieces')):
            self.rows.setItem(i, j, QTableWidgetItem(str(values.get(key, ''))))

    def add_row(self):
        self._insert_row({'pieces': '1'})
        self.mark_dirty()

    def remove_row(self):
        if self.rows.currentRow() >= 0:
            self.rows.removeRow(self.rows.currentRow())
            self.mark_dirty()

    def parameters(self):
        method = self.method.currentData()
        if method == 'MANUAL':
            params = {'quantity': self.manual.text()}
        elif method in ('LONGITUD', 'AREA', 'VOLUMEN'):
            rows = []
            for i in range(self.rows.rowCount()):
                values = [self.rows.item(i, j).text() if self.rows.item(i, j) else '' for j in range(4)]
                rows.append(dict(zip(('length', 'width', 'height', 'pieces'), values), length_unit=self.length_unit.currentData()))
            params = {'rows': rows}
        else:
            params = {'area': self.area.text(), 'area_unit': 'm2', 'coats': self.coats.text(),
                      'coverage': self.coverage.text(), 'extra_percent': self.extra.text(),
                      'presentation_size': self.size.text().strip() or None, 'presentation_unit': self.size_unit.currentData(),
                      'closed_presentation': self.closed.isChecked()}
        params['source'] = self.source.text().strip() or 'Supuesto no validado'
        return method, params

    def value(self):
        method, params = self.parameters()
        return calculate(method, params, self.unit)

    @action
    def recalculate(self):
        result = self.value()
        self.summary.setText(tr('Requerido: ') + result['required'] + ' ' + result['required_unit'] +
                             tr(' · Vendible: ') + result['quantity'] + ' ' + result['unit'] +
                             tr(' · Equivalente físico: ') + result['sold_physical'] + ' ' + result['sold_unit'] + '\n' + result['source'])

    @action
    def apply(self):
        self.result_formula = self.value()
        self.accept()
