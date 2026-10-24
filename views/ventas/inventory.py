# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import date

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.ventas.domain.errors import ValidationError
from utils.i18n import tr
from .common import DirtyDialog, action, button, combo, field, fill_table, table


class MovementDialog(DirtyDialog):
    def __init__(self, service, item, parent=None):
        super().__init__('Registrar movimiento comercial', parent)
        self.service, self.item = service, item
        self.form.addRow(QLabel(item['sku'] + ' · ' + item['name']))
        self.kind = combo(self.form, 'Tipo', ['ENTRADA', 'SALIDA', 'AJUSTE'])
        self.amount = field(self.form, 'Cantidad (' + item['unit'] + ')', '', 'Ajuste = diferencia firmada, no saldo final')
        self.date = field(self.form, 'Fecha (AAAA-MM-DD)', date.today().isoformat())
        self.reason = field(self.form, 'Motivo / referencia', '')
        self.form.addRow(QLabel(tr('AJUSTE admite 0 para registrar un conteo inicial explícito de cero.\nNo se sobrescribe saldo; se agrega un evento.')))
        self.save_buttons(self.save, 'Registrar movimiento')
        self.watch()

    @action
    def save(self):
        self.service.register_movement(self.item['id'], self.kind.currentData(), self.amount.text().strip(), self.date.text().strip(), self.reason.text().strip())
        self.accept()


class InventoryView(QWidget):
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.entries = []
        layout = QVBoxLayout(self)
        label = QLabel(tr('Almacén comercial local · Reservado = 0 (sin motor de reservas). Las cotizaciones no modifican existencias.'))
        label.setWordWrap(True)
        layout.addWidget(label)
        controls = QHBoxLayout()
        layout.addLayout(controls)
        self.move_button = button('Registrar movimiento', self.move, controls, True)
        self.move_button.setEnabled(not service.readonly)
        button('Actualizar', self.refresh, controls)
        self.tbl = table(['SKU', 'Artículo', 'Unidad', 'Físico', 'Reservado', 'Disponible', 'Referencia de stock', 'Estado'])
        layout.addWidget(self.tbl, 2)
        layout.addWidget(QLabel(tr('Movimientos auditados del SKU seleccionado (ajuste = diferencia, no saldo final)')))
        self.ledger = table(['Tipo', 'Cantidad firmada', 'Unidad', 'Fecha', 'Motivo', 'Actor', 'Registro'])
        layout.addWidget(self.ledger, 1)
        self.tbl.itemSelectionChanged.connect(self.show_ledger)
        self.refresh()

    @action
    def refresh(self):
        self.entries = self.service.inventory()
        fill_table(self.tbl, [[e['item']['sku'], e['item']['name'], e['item']['unit'], e['physical'], e['reserved'], e['available'], e['at'], e['status']] for e in self.entries])
        fill_table(self.ledger, [])

    @action
    def show_ledger(self):
        index = self.tbl.currentRow()
        if 0 <= index < len(self.entries):
            movements = self.service.movements(self.entries[index]['item']['id'])
            fill_table(self.ledger, [[m['tipo'], m['cantidad_decimal'], m['unidad'], m['fecha'], m['motivo'], m['actor'], m['registrado_en']] for m in movements])

    @action
    def move(self):
        index = self.tbl.currentRow()
        if not 0 <= index < len(self.entries):
            raise ValidationError('Seleccione un SKU con seguimiento de stock.')
        dialog = MovementDialog(self.service, self.entries[index]['item'], self)
        if dialog.exec() == QDialog.Accepted:
            self.refresh()
