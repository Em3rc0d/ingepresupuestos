# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari
# This file is part of IngePresupuestos — https://ingepresupuestos.com
# Software libre bajo la GNU GPL v3 o posterior. Ver el archivo LICENSE.
"""«Guardar en Biblioteca» — elegir qué CU actualizar o en qué grupo copiar.

Hasta la 3.0.16 el botón buscaba UNA partida con la misma descripción
(`fetchone` sin orden: cualquiera de los duplicados) y la copia nueva iba
siempre a «MIS PARTIDAS». Pedido de David Ramos (ronda 7, 21-10-2026):
mostrar los grupos donde ya existe, poder elegir cuál actualizar, y para la
copia nueva un campo de grupo que autocompleta con los existentes.

El diálogo solo decide; `ProyectoView._guardar_en_biblioteca` escribe.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCompleter, QDialog, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton, QRadioButton,
    QVBoxLayout,
)

from core.database import get_db
from utils.formatting import fmt, norm_busqueda
from utils.theme import BTN_PRIMARY_SS, btn_secondary

# Grupos del catálogo base (seed): no se deben sobrescribir a la ligera.
GRUPOS_SEED = {'INGEPRESUPUESTOS', 'LLAMKASUN', 'CAPECO'}
GRUPO_DEFECTO = 'MIS PARTIDAS'


def coincidencias(conn, descripcion: str) -> list[dict]:
    """CU de la biblioteca con la misma descripción, sin mirar tildes ni
    mayúsculas, los del usuario antes que los del catálogo base."""
    conn.create_function("_norm", 1, norm_busqueda)
    rows = conn.execute(
        "SELECT id, grupo, unidad, costo_unitario FROM biblioteca_cu "
        "WHERE _norm(TRIM(descripcion)) = ? ORDER BY grupo, id",
        (norm_busqueda((descripcion or '').strip()),)).fetchall()
    out = [dict(r) for r in rows]
    out.sort(key=lambda r: es_grupo_seed(r['grupo']))
    return out


def grupos_existentes(conn) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT grupo FROM biblioteca_cu "
        "WHERE grupo IS NOT NULL AND TRIM(grupo) != '' ORDER BY grupo")]


def es_grupo_seed(grupo) -> bool:
    return (grupo or '').strip().upper() in GRUPOS_SEED


def grupo_canonico(texto: str, existentes: list[str]) -> str:
    """El grupo tecleado; si ya existe con otras mayúsculas, el existente
    (así «mis partidas» no abre un grupo aparte). Vacío → «MIS PARTIDAS»."""
    t = ' '.join((texto or '').split())
    if not t:
        return GRUPO_DEFECTO
    for g in existentes:
        if norm_busqueda(g.strip()) == norm_busqueda(t):
            return g
    return t


class GuardarBibliotecaDialog(QDialog):
    """Tras `exec()` aceptado: `modo` es 'actualizar' (con `cu_id`) o
    'nuevo' (con `grupo`)."""

    def __init__(self, descripcion: str, grupo_partida: str = '',
                 moneda: str = 'S/', parent=None):
        super().__init__(parent)
        self.setWindowTitle("Guardar en Biblioteca")
        self.setWindowModality(Qt.WindowModal)
        self.setMinimumWidth(520)
        self.modo: str | None = None
        self.cu_id: int | None = None
        self.grupo: str | None = None

        conn = get_db()
        try:
            self._coinc = coincidencias(conn, descripcion)
            self._grupos = grupos_existentes(conn)
        finally:
            conn.close()

        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 14)
        v.setSpacing(8)
        lbl = QLabel(f"<b>{descripcion}</b>")
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.RichText)
        v.addWidget(lbl)

        self._grp = QButtonGroup(self)
        self.rb_actualizar = QRadioButton()
        self.rb_nuevo = QRadioButton()
        self.lst = QListWidget()
        if self._coinc:
            n = len(self._coinc)
            self.rb_actualizar.setText(
                "Actualizar la que ya existe" if n == 1 else
                f"Actualizar una de las {n} que ya existen — elige el grupo:")
            v.addWidget(self.rb_actualizar)
            self.lst.setSelectionMode(QAbstractItemView.SingleSelection)
            for r in self._coinc:
                grupo = (r['grupo'] or '').strip() or '(sin grupo)'
                extra = "  ·  catálogo base" if es_grupo_seed(r['grupo']) else ''
                it = QListWidgetItem(
                    f"{grupo}   ·   {r['unidad'] or '—'}   ·   "
                    f"{fmt(r['costo_unitario'] or 0, moneda)}{extra}")
                it.setData(Qt.UserRole, r['id'])
                self.lst.addItem(it)
            self.lst.setFixedHeight(min(150, 26 * n + 8))
            self.lst.itemClicked.connect(lambda _i: self.rb_actualizar.setChecked(True))
            v.addWidget(self.lst)
            self._grp.addButton(self.rb_actualizar)
            self.rb_nuevo.setText("Guardar como copia nueva en el grupo:")
        else:
            self.rb_nuevo.setText("Guardar en el grupo:")
            self.rb_nuevo.hide()     # una sola opción: no hace falta elegir
            v.addWidget(QLabel("Grupo:"))
        self._grp.addButton(self.rb_nuevo)
        v.addWidget(self.rb_nuevo)

        self.inp_grupo = QLineEdit()
        self.inp_grupo.setPlaceholderText(GRUPO_DEFECTO)
        comp = QCompleter(self._grupos, self.inp_grupo)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setFilterMode(Qt.MatchContains)
        self.inp_grupo.setCompleter(comp)
        self.inp_grupo.textEdited.connect(lambda _t: self.rb_nuevo.setChecked(True))
        v.addWidget(self.inp_grupo)

        # Por defecto: actualizar la primera del usuario si la hay; si solo
        # existe en el catálogo base, copia nueva (no tocarlo a la ligera).
        propias = [i for i, r in enumerate(self._coinc) if not es_grupo_seed(r['grupo'])]
        if propias:
            self.lst.setCurrentRow(propias[0])
            self.rb_actualizar.setChecked(True)
        else:
            if self._coinc:
                self.lst.setCurrentRow(0)
            self.rb_nuevo.setChecked(True)
            g = (grupo_partida or '').strip()
            self.inp_grupo.setText(GRUPO_DEFECTO if (self._coinc or not g) else g)

        fila = QHBoxLayout()
        fila.addStretch(1)
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setStyleSheet(btn_secondary())
        btn_cancelar.clicked.connect(self.reject)
        self.btn_guardar = QPushButton("Guardar")
        self.btn_guardar.setStyleSheet(BTN_PRIMARY_SS)
        self.btn_guardar.setDefault(True)
        self.btn_guardar.clicked.connect(self._aceptar)
        fila.addWidget(btn_cancelar)
        fila.addWidget(self.btn_guardar)
        v.addSpacing(6)
        v.addLayout(fila)

    def _aceptar(self):
        if self.rb_actualizar.isChecked() and self.lst.currentItem() is not None:
            self.modo = 'actualizar'
            self.cu_id = int(self.lst.currentItem().data(Qt.UserRole))
        else:
            self.modo = 'nuevo'
            self.grupo = grupo_canonico(self.inp_grupo.text(), self._grupos)
        self.accept()
