# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari
# This file is part of IngePresupuestos — https://ingepresupuestos.com
# Software libre bajo la GNU GPL v3 o posterior. Ver el archivo LICENSE.
"""Ronda 7 de David Ramos (SUG..docx y ACU.docx, sep 2026) — cuatro errores
y cuatro mejoras.

1. Biblioteca con «Todos los grupos»: un LIMIT 1000 alfabético escondía los
   CU del usuario que caían después, aunque su grupo saliera en la lista.
2. Biblioteca: la búsqueda no encontraba nada con tilde (LOWER de SQLite
   solo baja ASCII).
3. Copiar insumos en el ACU abría un QLabel sin padre: una ventana suelta.
4. Donut del Resumen: el Total se medía con la fuente normal y se pintaba en
   negrita, así que la columna quedaba corta y se comía la «S/».

Mejoras (decididas por Marco el 21-10-2026): columna INEI en ACU e Insumos;
Ctrl+C en el árbol deja también el texto para Excel, y «Seleccionar todo»;
«Guardar en Biblioteca» muestra los grupos donde ya existe y deja elegir;
la Biblioteca pierde la columna y el KPI «Usos», que nada contaba.

Corre con:  QT_QPA_PLATFORM=offscreen venv/bin/python3 tests/test_ronda7_david.py

Usa una copia temporal del seed, nunca la BD activa.
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtGui import QFont, QFontMetrics                       # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow     # noqa: E402

_app = QApplication.instance() or QApplication([])

import core.database as d                                           # noqa: E402

SEED = os.path.join(os.path.dirname(__file__), '..', 'presupuestos_seed.db')
_fd, _tmpdb = tempfile.mkstemp(suffix='_ronda7_test.db')
os.close(_fd)
shutil.copy(SEED, _tmpdb)
d.DB_PATH = _tmpdb
d.init_db()

PID = 397
_VIVAS = []


def _nuevo_cu(descripcion: str, grupo: str) -> int:
    conn = d.get_db()
    cur = conn.execute(
        "INSERT INTO biblioteca_cu (descripcion, unidad, rendimiento, "
        "costo_unitario, grupo) VALUES (?, 'm2', 10, 25.5, ?)",
        (descripcion, grupo))
    conn.commit()
    cu_id = cur.lastrowid
    conn.close()
    return cu_id


def _biblioteca():
    from views.biblioteca_view import BibliotecaView
    v = BibliotecaView()
    _VIVAS.append(v)
    return v


def _ids(v) -> set:
    return {v._rid_at(r) for r in range(v.tbl.rowCount())}


# ── 1 y 2. Biblioteca ────────────────────────────────────────────────────────

def test_todos_los_grupos_muestra_los_cu_que_caen_despues_de_mil():
    conn = d.get_db()
    total = conn.execute("SELECT COUNT(*) FROM biblioteca_cu").fetchone()[0]
    conn.close()
    assert total > 1000, 'el seed debería pasar de mil CU para que la prueba valga'
    cu_id = _nuevo_cu('ZZZ PARTIDA PROPIA DEL USUARIO', 'ZZ MIS PARTIDAS')
    v = _biblioteca()
    v.cargar()
    assert v.tbl.rowCount() == total + 1
    assert cu_id in _ids(v)


def test_la_busqueda_ignora_tildes_y_mayusculas():
    cu_id = _nuevo_cu('PREPARACIÓN DE TERRENO RONDA SIETE', 'MIS PARTIDAS')
    v = _biblioteca()
    for texto in ('preparación de terreno ronda', 'PREPARACION DE TERRENO RONDA',
                  'preparacion de terreno ronda'):
        v.inp_q.setText(texto)
        v.cargar()
        assert cu_id in _ids(v), texto


# ── 3. Copiar insumos en el ACU ──────────────────────────────────────────────

def test_copiar_insumos_avisa_en_la_barra_de_estado_sin_ventana_suelta():
    from views.proyecto_view import ProyectoView
    from models.usuario import Usuario
    win = QMainWindow()
    v = ProyectoView(PID, Usuario(id=1, nombre="t", rol="admin"))
    win.setCentralWidget(v)
    _VIVAS.extend([win, v])
    v._completar_panel_tabs()
    v._cargar_datos_inicial()
    _app.processEvents()
    win.show()
    conn = d.get_db()
    part = conn.execute(
        "SELECT p.id FROM partidas p JOIN acu_items ai ON ai.partida_id=p.id "
        "WHERE p.proyecto_id=? AND p.es_titulo=0 ORDER BY p.item LIMIT 1",
        (PID,)).fetchone()[0]
    conn.close()
    v.cargar_acu(part)
    fila = next(r for r, i in enumerate(v._acu_row_ids) if i != -1)
    v.tbl_acu.selectRow(fila)
    antes = {id(w) for w in QApplication.topLevelWidgets()}
    v._copiar_acu_seleccionados()
    _app.processEvents()
    assert v._acu_clipboard
    nuevas = [w for w in QApplication.topLevelWidgets()
              if id(w) not in antes and isinstance(w, QLabel) and w.isVisible()]
    assert not nuevas, 'el aviso salió como ventana suelta'
    assert 'copiado' in win.statusBar().currentMessage()
    win.close()


# ── 4. Donut ─────────────────────────────────────────────────────────────────

def test_la_columna_de_montos_alcanza_para_el_total_en_negrita():
    from views.proyecto_view import _DonutChart
    datos = [("Mano de Obra", 412345.67, "#F39C12"),
             ("Materiales", 1012345.67, "#27AE60"),
             ("Equipos", 136025.95, "#607D8B")]
    ch = _DonutChart(datos, moneda="S/")
    f = QFont(); f.setPointSize(8)
    f_tot = QFont(f); f_tot.setBold(True)
    w_amt, _w_pct = ch._columnas_leyenda(QFontMetrics(f))
    assert w_amt >= QFontMetrics(f_tot).horizontalAdvance(ch._texto_total())


# ── Mejoras ──────────────────────────────────────────────────────────────────

def _vista():
    from views.proyecto_view import ProyectoView
    from models.usuario import Usuario
    win = QMainWindow()
    v = ProyectoView(PID, Usuario(id=1, nombre="t", rol="admin"))
    win.setCentralWidget(v)
    _VIVAS.extend([win, v])
    v._completar_panel_tabs()
    v._cargar_datos_inicial()
    _app.processEvents()
    return v


def _partida_con_acu() -> int:
    conn = d.get_db()
    part = conn.execute(
        "SELECT p.id FROM partidas p JOIN acu_items ai ON ai.partida_id=p.id "
        "JOIN recursos r ON r.id=ai.recurso_id "
        "WHERE p.proyecto_id=? AND p.es_titulo=0 AND COALESCE(r.indice_inei,'')!='' "
        "ORDER BY p.item LIMIT 1", (PID,)).fetchone()[0]
    conn.close()
    return part


def test_acu_e_insumos_muestran_el_indice_inei_al_final():
    from views.proyecto_view import _COL_INEI_ACU, _COL_INEI_INS
    v = _vista()
    part = _partida_con_acu()
    conn = d.get_db()
    inei = {r['id']: (r['indice_inei'] or '').replace('00', '') for r in conn.execute(
        "SELECT ai.id, r.indice_inei FROM acu_items ai JOIN recursos r "
        "ON r.id=ai.recurso_id WHERE ai.partida_id=?", (part,))}
    conn.close()
    v.cargar_acu(part)
    assert v.tbl_acu.columnCount() == _COL_INEI_ACU + 1
    assert v.tbl_acu.horizontalHeaderItem(_COL_INEI_ACU).text() == 'INEI'
    for r, acu_id in enumerate(v._acu_row_ids):
        if acu_id != -1:
            assert v.tbl_acu.item(r, _COL_INEI_ACU).text() == inei[acu_id]
    v.cargar_insumos(part)
    assert v.tbl_ins.horizontalHeaderItem(_COL_INEI_INS).text() == 'INEI'
    textos = {v.tbl_ins.item(r, _COL_INEI_INS).text() for r in range(v.tbl_ins.rowCount())}
    assert textos == set(inei.values())


def test_ctrl_c_en_el_arbol_deja_el_texto_para_excel():
    v = _vista()
    titulo = v.tree.topLevelItem(0)
    v.tree.clearSelection()
    titulo.setSelected(True)
    v._copiar_partidas_seleccionadas()
    lineas = QApplication.clipboard().text().splitlines()

    def _contar(it):
        return 1 + sum(_contar(it.child(i)) for i in range(it.childCount()))
    assert len(lineas) == 1 + _contar(titulo)        # cabecera + el título entero
    assert lineas[0].split('\t')[:2] == ['Ítem', 'Descripción']
    assert lineas[1].split('\t')[:2] == [titulo.text(0), titulo.text(1)]
    assert all(l.count('\t') == lineas[0].count('\t') for l in lineas)


def test_guardar_en_biblioteca_deja_elegir_el_grupo(monkeypatch):
    import views.proyecto_view as PV
    import views.guardar_biblioteca_dialog as GB
    monkeypatch.setattr(PV.QMessageBox, 'information', lambda *a, **k: None)
    v = _vista()
    part = _partida_con_acu()
    conn = d.get_db()
    desc = conn.execute("SELECT descripcion FROM partidas WHERE id=?", (part,)).fetchone()[0]
    conn.close()
    otro = _nuevo_cu(desc.lower(), 'OBRAS DE MARCO')       # misma, otras mayúsculas
    v.cargar_acu(part)

    # El diálogo ve el CU existente y propone actualizarlo.
    dlg = GB.GuardarBibliotecaDialog(desc, '', 'S/')
    assert otro in [dlg.lst.item(i).data(PV.Qt.UserRole) for i in range(dlg.lst.count())]
    assert dlg.rb_actualizar.isChecked()

    def _exec_nuevo(self):
        self.rb_nuevo.setChecked(True)
        self.inp_grupo.setText('obras de marco')           # el existente, en minúsculas
        self._aceptar()
        return PV.QDialog.Accepted
    monkeypatch.setattr(GB.GuardarBibliotecaDialog, 'exec', _exec_nuevo)
    v._guardar_en_biblioteca()
    conn = d.get_db()
    grupos = [r[0] for r in conn.execute(
        "SELECT grupo FROM biblioteca_cu WHERE descripcion=? ORDER BY id DESC", (desc,))]
    n_acu = conn.execute(
        "SELECT COUNT(*) FROM biblioteca_acu_items WHERE cu_id=(SELECT MAX(id) FROM biblioteca_cu)"
    ).fetchone()[0]
    conn.close()
    assert grupos[0] == 'OBRAS DE MARCO' and n_acu > 0

    def _exec_actualizar(self):
        for i in range(self.lst.count()):
            if self.lst.item(i).data(PV.Qt.UserRole) == otro:
                self.lst.setCurrentRow(i)
        self.rb_actualizar.setChecked(True)
        self._aceptar()
        return PV.QDialog.Accepted
    monkeypatch.setattr(GB.GuardarBibliotecaDialog, 'exec', _exec_actualizar)
    v._guardar_en_biblioteca()
    conn = d.get_db()
    costo, n = conn.execute(
        "SELECT cu.costo_unitario, (SELECT COUNT(*) FROM biblioteca_acu_items i WHERE i.cu_id=cu.id) "
        "FROM biblioteca_cu cu WHERE id=?", (otro,)).fetchone()
    pu = conn.execute("SELECT precio_unitario FROM partidas WHERE id=?", (part,)).fetchone()[0]
    conn.close()
    assert costo == pu and n > 0


def test_el_centinela_00_cuenta_como_sin_indice():
    from views.proyecto_view import _celda_inei
    assert _celda_inei({'indice_inei': '00'}).text() == ''
    assert _celda_inei({'indice_inei': None}).text() == ''
    assert _celda_inei({'indice_inei': '47'}).text() == '47'


def test_grupo_canonico():
    from views.guardar_biblioteca_dialog import grupo_canonico
    assert grupo_canonico('  ', ['A']) == 'MIS PARTIDAS'
    assert grupo_canonico('mis  partidas', ['MIS PARTIDAS']) == 'MIS PARTIDAS'
    assert grupo_canonico('Nuevo', ['MIS PARTIDAS']) == 'Nuevo'


def test_la_biblioteca_ya_no_muestra_usos():
    v = _biblioteca()
    v.cargar()
    cab = [v.tbl.horizontalHeaderItem(c).text() for c in range(v.tbl.columnCount())]
    assert 'Usos' not in cab and not hasattr(v, 'kpi_usados')


if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__, '-q']))
