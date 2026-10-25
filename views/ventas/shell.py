# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import date
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMessageBox, QTabWidget, QVBoxLayout, QWidget)

from core.ventas.application.services import SalesService, valid_date
from core.ventas.domain.errors import ValidationError
from core.ventas.domain.quote_states import TRANSITIONS
from utils.i18n import tr
from utils.theme import C
from .catalog import RecordsView
from .common import action, button, fill_table, table
from .editor import PreviewDialog, QuoteEditor
from .inventory import InventoryView


class QuotesView(QWidget):
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service, self.records, self.visible = service, [], []
        self.selected_document = None
        layout = QVBoxLayout(self)
        filters = QHBoxLayout()
        layout.addLayout(filters)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr('Número, título o cliente'))
        self.search.setAccessibleName(tr('Buscar cotizaciones'))
        filters.addWidget(self.search, 1)
        self.status = QComboBox()
        self.status.addItem(tr('Todos los estados'), None)
        for status in TRANSITIONS:
            self.status.addItem(tr(status), status)
        self.status.setAccessibleName(tr('Filtrar por estado'))
        filters.addWidget(self.status)
        self.client = QComboBox()
        self.client.setAccessibleName(tr('Filtrar por cliente'))
        filters.addWidget(self.client)
        self.from_date = QLineEdit()
        self.from_date.setPlaceholderText(tr('Desde AAAA-MM-DD'))
        self.from_date.setAccessibleName(tr('Fecha desde'))
        self.to_date = QLineEdit()
        self.to_date.setPlaceholderText(tr('Hasta AAAA-MM-DD'))
        self.to_date.setAccessibleName(tr('Fecha hasta'))
        filters.addWidget(self.from_date)
        filters.addWidget(self.to_date)
        button('Filtrar fechas', self.render, filters)
        controls = QHBoxLayout()
        layout.addLayout(controls)
        new = button('Nueva cotización', self.create, controls, True)
        button('Abrir / editar borrador', self.open, controls)
        duplicate = button('Duplicar documento', self.duplicate, controls)
        self.revision_button = revision = button('Nueva revisión', self.revise, controls)
        state = button('Cambiar estado', self.change_state, controls)
        for widget in (new, duplicate, revision, state):
            widget.setEnabled(not service.readonly)
        button('Actualizar', self.refresh, controls)
        self.tbl = table(['Número', 'Cliente', 'Referencia', 'Fecha', 'Vigencia', 'Estado', 'V.', 'Moneda', 'Total'])
        layout.addWidget(self.tbl, 2)
        self.tbl.doubleClicked.connect(lambda *_: self.open())
        self.tbl.itemSelectionChanged.connect(self.selection_changed)
        version_controls = QHBoxLayout()
        layout.addLayout(version_controls)
        version_controls.addWidget(QLabel(tr('Revisiones guardadas:')))
        self.versions = QComboBox()
        self.versions.setAccessibleName(tr('Revisión de cotización'))
        version_controls.addWidget(self.versions, 1)
        button('Vista previa / PDF / Excel de esta revisión', self.preview_revision, version_controls)
        button('Comparar con última versión', self.compare, version_controls)
        self.history = table(['Evento', 'Fecha', 'Actor', 'Detalle'])
        layout.addWidget(self.history, 1)
        self.search.textChanged.connect(self.render)
        self.status.currentIndexChanged.connect(self.render)
        self.client.currentIndexChanged.connect(self.render)
        self.refresh()

    @action
    def refresh(self):
        selected_client = self.client.currentData()
        self.client.blockSignals(True)
        self.client.clear()
        self.client.addItem(tr('Todos los clientes'), None)
        for client in self.service.clients(True):
            self.client.addItem(client['name'], client['id'])
        self.client.setCurrentIndex(max(0, self.client.findData(selected_client)))
        self.client.blockSignals(False)
        self.records = self.service.quotes()
        self.render()

    @action
    def render(self, *args):
        start, until = self.from_date.text().strip(), self.to_date.text().strip()
        if start:
            valid_date(start, 'Desde')
        if until:
            valid_date(until, 'Hasta')
        query, state, client_id = self.search.text().casefold(), self.status.currentData(), self.client.currentData()
        client_names = {c['id']: c['name'] for c in self.service.clients(True)}
        self.visible = []
        rows = []
        for record in self.records:
            customer = json.loads(record['cabecera_json']).get('customer', {}).get('name', tr('Receptor ocasional'))
            if state and record['estado'] != state or client_id and record['cliente_id'] != client_id:
                continue
            if start and record['fecha'] < start or until and record['fecha'] > until:
                continue
            if query not in (record['numero'] + ' ' + record['titulo'] + ' ' + customer).casefold():
                continue
            self.visible.append(record)
            rows.append([record['numero'], customer, record['titulo'], record['fecha'], record['vencimiento'], record['estado'], record['version'], record['moneda'], json.loads(record['totales_json'])['total']])
        self.selected_document = None
        self.revision_button.setEnabled(False)
        self.versions.clear()
        fill_table(self.history, [])
        fill_table(self.tbl, rows)

    def selected(self):
        index = self.tbl.currentRow()
        if not 0 <= index < len(self.visible):
            raise ValidationError('Seleccione una cotización.')
        return self.visible[index]

    @action
    def selection_changed(self):
        index = self.tbl.currentRow()
        if not 0 <= index < len(self.visible):
            return
        record = self.visible[index]
        self.selected_document = self.service.open_document(record['id'])
        allowed = self.selected_document['state'] == 'EMITIDA' and self.selected_document['revision_state'] == 'EMITIDA' and not self.service.readonly
        self.revision_button.setEnabled(allowed)
        self.revision_button.setToolTip(tr('Solo se permite revisar una cotización en estado EMITIDA; los estados terminales no se reabren.'))
        self.versions.clear()
        for version in self.service.versions(record['id']):
            self.versions.addItem(f"V{version['version']} · {version['estado']} · {version['fecha_emision'] or 'Borrador'}", version['id'])
        fill_table(self.history, [[e['tipo'], e['fecha'], e['actor'], e['detalle_json']] for e in self.service.events(record['id'])])

    @action
    def create(self):
        QuoteEditor(self.service, parent=self).exec()
        self.refresh()

    @action
    def open(self):
        doc = self.service.open_document(self.selected()['id'])
        if doc['state'] == 'BORRADOR' and doc['revision_state'] == 'BORRADOR' and not self.service.readonly:
            QuoteEditor(self.service, doc, self).exec()
        else:
            PreviewDialog(self.service, doc, False, self).exec()
        self.refresh()

    @action
    def duplicate(self):
        doc = self.service.duplicate(self.selected()['id'], self.versions.currentData())
        QuoteEditor(self.service, doc, self).exec()
        self.refresh()

    @action
    def revise(self):
        current = self.service.open_document(self.selected()['id'])
        if current['revision_state'] != 'EMITIDA' or current['state'] != 'EMITIDA':
            raise ValidationError('Solo puede crear una revisión de una cotización en estado EMITIDA. Los estados terminales no se reabren.')
        answer = QMessageBox.question(self, tr('Nueva revisión'), tr('Se creará un borrador nuevo. La revisión emitida se conservará íntegra.'))
        if answer != QMessageBox.Yes:
            return
        doc = self.service.new_revision(current['id'], current['token'])
        QuoteEditor(self.service, doc, self).exec()
        self.refresh()

    @action
    def change_state(self):
        current = self.service.open_document(self.selected()['id'])
        targets = sorted(TRANSITIONS[current['state']] - {'EMITIDA'})
        if not targets:
            raise ValidationError('Estado terminal: no admite transiciones ni revisiones. Puede duplicar como otra cotización independiente.')
        target, ok = QInputDialog.getItem(self, tr('Cambiar estado'), tr('Estado nuevo'), targets, 0, False)
        if not ok:
            return
        reason, ok = QInputDialog.getText(self, tr('Constancia'), tr('Motivo / persona que aceptó o rechazó / referencia'))
        if ok:
            self.service.change_state(current['id'], current['token'], target, reason)
            self.refresh()

    @action
    def preview_revision(self):
        record = self.selected()
        revision_id = self.versions.currentData()
        if revision_id:
            PreviewDialog(self.service, self.service.open_document(record['id'], revision_id), False, self).exec()

    @action
    def compare(self):
        record = self.selected()
        previous = self.service.open_document(record['id'], self.versions.currentData())
        current = self.service.open_document(record['id'])
        QMessageBox.information(self, tr('Diferencias de revisiones'), '\n'.join(self.service.diff(previous, current)))


class SalesView(QWidget):
    def __init__(self, user, parent=None):
        super().__init__(parent)
        from core.config import DB_PATH
        actor = f'{user.id}:{user.username or user.nombre}' if user is not None else 'Usuario local'
        self.service = SalesService(DB_PATH, actor, readonly=user is None or user.es_invitado,
                                    user_id=getattr(user, 'id', None), is_admin=getattr(user, 'es_admin', False))
        self.setObjectName('salesWorkspace')
        self.setStyleSheet(f'QWidget#salesWorkspace {{ background:{C.bg}; color:{C.text}; }}')
        layout = QVBoxLayout(self)
        heading = QLabel(tr('Cotizaciones de Ventas'))
        heading.setStyleSheet(f'font-size:22px;font-weight:700;color:{C.text};')
        layout.addWidget(heading)
        hint = QLabel(tr('Propuestas comerciales locales · Inventario separado de Construcción · Sin facturación electrónica'))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.dashboard = QWidget()
        dashboard_layout = QVBoxLayout(self.dashboard)
        self.overview = QLabel()
        self.overview.setWordWrap(True)
        dashboard_layout.addWidget(self.overview)
        actions = QHBoxLayout()
        dashboard_layout.addLayout(actions)
        new = button('Nueva cotización', self.new_quote, actions, True)
        new.setEnabled(not self.service.readonly)
        button('Clientes', lambda: self.tabs.setCurrentIndex(3), actions)
        button('Productos y servicios', lambda: self.tabs.setCurrentIndex(2), actions)
        button('Inventario', lambda: self.tabs.setCurrentIndex(4), actions)
        issuer = button('Configurar emisor', self.configure, actions)
        issuer.setEnabled(not self.service.readonly)
        self.recent = table(['Número', 'Referencia', 'Estado', 'Vigencia', 'Moneda', 'Total'])
        dashboard_layout.addWidget(self.recent, 1)
        dashboard_layout.addWidget(QLabel(tr('Conector de partidas/ACU: no disponible en v1. Importación CSV: pendiente.')))
        self.quotes = QuotesView(self.service, self)
        self.catalog = RecordsView(self.service, parent=self)
        self.clients = RecordsView(self.service, clients=True, parent=self)
        self.inventory = InventoryView(self.service, self)
        self.tabs.addTab(self.dashboard, tr('Inicio Ventas'))
        self.tabs.addTab(self.quotes, tr('Cotizaciones'))
        self.tabs.addTab(self.catalog, tr('Productos y servicios'))
        self.tabs.addTab(self.clients, tr('Clientes'))
        self.tabs.addTab(self.inventory, tr('Inventario'))
        self.tabs.currentChanged.connect(self.refresh_tab)
        self.refresh_dashboard()

    @action
    def refresh_dashboard(self):
        documents = self.service.quotes()
        issued = [d for d in documents if d['estado'] == 'EMITIDA']
        expired = sum(d['vencimiento'] < date.today().isoformat() for d in issued)
        self.overview.setText(tr('Cotizaciones: ') + str(len(documents)) + tr(' · Emitidas: ') + str(len(issued)) + tr(' · Con vigencia vencida (sin cambio automático de estado): ') + str(expired))
        fill_table(self.recent, [[d['numero'], d['titulo'], d['estado'], d['vencimiento'], d['moneda'], json.loads(d['totales_json'])['total']] for d in documents[:20]])

    def refresh_tab(self, index):
        if index == 0:
            self.refresh_dashboard()
        elif index == 1:
            self.quotes.refresh()
        elif index == 2:
            self.catalog.refresh()
        elif index == 3:
            self.clients.refresh()
        elif index == 4:
            self.inventory.refresh()

    @action
    def new_quote(self):
        QuoteEditor(self.service, parent=self).exec()
        self.refresh_dashboard()

    @action
    def configure(self):
        issuer, ok = QInputDialog.getMultiLineText(self, tr('Emisor comercial'), tr('Nombre / identificación / dirección y contacto del emisor'), self.service.config().get('issuer', ''))
        if ok:
            self.service.configure(issuer)
