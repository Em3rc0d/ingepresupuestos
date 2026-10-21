# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari
# This file is part of IngePresupuestos — https://ingepresupuestos.com
# Software libre bajo la GNU GPL v3 o posterior. Ver el archivo LICENSE.
"""Ronda 7 de David Ramos (ACU.docx, 29-09-2026) — los cuatro errores.

1. Biblioteca con «Todos los grupos»: un LIMIT 1000 alfabético escondía los
   CU del usuario que caían después, aunque su grupo saliera en la lista.
2. Biblioteca: la búsqueda no encontraba nada con tilde (LOWER de SQLite
   solo baja ASCII).
3. Copiar insumos en el ACU abría un QLabel sin padre: una ventana suelta.
4. Donut del Resumen: el Total se medía con la fuente normal y se pintaba en
   negrita, así que la columna quedaba corta y se comía la «S/».

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


if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__, '-q']))
