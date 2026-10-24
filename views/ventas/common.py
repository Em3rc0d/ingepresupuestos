# SPDX-License-Identifier: GPL-3.0-or-later
from functools import wraps

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from core.ventas.domain.errors import SalesError, ValidationError
from core.ventas.domain.money import decimal
from utils.i18n import tr
from utils.theme import C, BTN_PRIMARY_SS


def action(function):
    @wraps(function)
    def wrapped(self, *args, **kwargs):
        try:
            return function(self, *args, **kwargs)
        except (SalesError, ValueError, KeyError, TypeError, OSError) as exc:
            QMessageBox.warning(self, tr('Cotizaciones de Ventas'), str(exc))
            return None
    return wrapped


def button(text, callback, parent_layout=None, primary=False):
    widget = QPushButton(tr(text))
    widget.setAccessibleName(tr(text))
    widget.setMinimumHeight(30)
    if primary:
        widget.setStyleSheet(BTN_PRIMARY_SS)
    widget.clicked.connect(lambda checked=False: callback())
    if parent_layout is not None:
        parent_layout.addWidget(widget)
    return widget


def field(form, label, value='', placeholder=''):
    edit = QLineEdit(str(value or ''))
    edit.setPlaceholderText(tr(placeholder))
    edit.setAccessibleName(tr(label))
    form.addRow(tr(label), edit)
    return edit


def combo(form, label, values, selected=None):
    widget = QComboBox()
    widget.setAccessibleName(tr(label))
    for value in values:
        if isinstance(value, tuple):
            widget.addItem(tr(value[0]), value[1])
        else:
            widget.addItem(tr(value), value)
    if selected is not None:
        index = widget.findData(selected)
        widget.setCurrentIndex(max(0, index))
    form.addRow(tr(label), widget)
    return widget


def table(headers):
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels([tr(h) for h in headers])
    widget.setSelectionBehavior(QAbstractItemView.SelectRows)
    widget.setSelectionMode(QAbstractItemView.SingleSelection)
    widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
    widget.setAlternatingRowColors(True)
    widget.horizontalHeader().setStretchLastSection(True)
    widget.setAccessibleName(tr('Tabla de datos de Ventas'))
    return widget


def fill_table(widget, rows):
    widget.setRowCount(len(rows))
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            cell = QTableWidgetItem(str(value if value is not None else '—'))
            cell.setToolTip(cell.text())
            widget.setItem(i, j, cell)
    widget.resizeColumnsToContents()
    # Descriptions wrap/scroll rather than forcing a window wider than the screen.
    for j in range(widget.columnCount()):
        widget.setColumnWidth(j, min(360, max(80, widget.columnWidth(j))))


class DirtyDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr(title))
        self.setModal(True)
        self.resize(780, 660)
        self.dirty = False
        self._watching = False
        self.outer = QVBoxLayout(self)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.form = QFormLayout()
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.body_layout.addLayout(self.form)
        self.scroll.setWidget(self.body)
        self.outer.addWidget(self.scroll, 1)

    def watch(self):
        for edit in self.findChildren(QLineEdit):
            edit.textChanged.connect(self.mark_dirty)
        for widget in self.findChildren(QComboBox):
            widget.currentIndexChanged.connect(self.mark_dirty)
        from PySide6.QtWidgets import QCheckBox, QPlainTextEdit
        for widget in self.findChildren(QCheckBox):
            widget.toggled.connect(self.mark_dirty)
        for widget in self.findChildren(QPlainTextEdit):
            widget.textChanged.connect(self.mark_dirty)
        self._watching = True
        self.dirty = False

    def mark_dirty(self, *args):
        if self._watching:
            self.dirty = True

    def confirm_discard(self):
        if not self.dirty:
            return True
        answer = QMessageBox.question(self, tr('Cambios sin guardar'),
            tr('Hay cambios sin guardar. ¿Desea descartarlos?'),
            QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Cancel)
        if answer == QMessageBox.Discard:
            self.dirty = False
            return True
        return False

    def reject(self):
        if self.confirm_discard():
            super().reject()

    def accept(self):
        self.dirty = False
        super().accept()

    def save_buttons(self, handler, text='Guardar'):
        box = QDialogButtonBox(QDialogButtonBox.Cancel)
        box.rejected.connect(self.reject)
        save = box.addButton(tr(text), QDialogButtonBox.AcceptRole)
        save.setStyleSheet(BTN_PRIMARY_SS)
        save.clicked.connect(lambda checked=False: handler())
        self.outer.addWidget(box)
        return save


class TaxFields(QWidget):
    def __init__(self, rule=None, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        rule = rule or {}
        self.mode = combo(form, 'Impuesto en precio', [('Sin configurar', None), ('Se añade al precio', 'EXCLUSIVE'), ('Incluido en precio', 'INCLUSIVE')], rule.get('mode'))
        self.name = field(form, 'Nombre de impuesto / regla', rule.get('name', ''))
        self.rate = field(form, 'Tasa explícita (%)', rule.get('rate', ''), '0 para tasa cero explícita')
        self.mode.currentIndexChanged.connect(self._enabled)
        self._enabled()

    def _enabled(self, *args):
        defined = self.mode.currentData() is not None
        self.name.setEnabled(defined)
        self.rate.setEnabled(defined)

    def value(self):
        mode = self.mode.currentData()
        if mode is None:
            return None
        name = self.name.text().strip()
        if not name:
            raise ValidationError('Nombre de impuesto/regla requerido, incluso para tasa cero.')
        return {'mode': mode, 'name': name, 'rate': str(decimal(self.rate.text(), 'Tasa de impuesto', maximum=decimal('100')))}
