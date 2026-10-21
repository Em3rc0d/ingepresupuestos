# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari
# This file is part of IngePresupuestos — https://ingepresupuestos.com
# Software libre bajo la GNU GPL v3 o posterior. Ver el archivo LICENSE.
"""Issue #2 — los decimales de cantidad del ACU no se aplicaban al cálculo.

Corre con:  QT_QPA_PLATFORM=offscreen venv/bin/python3 tests/test_decimales_cantidad_por_tipo.py

Reporte (24 sep 2026), rendimiento 12, jornada 8: con la MO a 2 decimales S10
da 0.67 × 24.96 = 16.72 y el programa seguía multiplicando 0.666667 → 16.64,
aunque se configuraran 2 decimales. Ahora hay un ajuste por tipo
(MO · MAT · EQ · SC) y la cantidad se redondea antes de multiplicar.
Usa una COPIA temporal del seed.
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication                          # noqa: E402

import core.config as cfg                                           # noqa: E402
import core.database as d                                           # noqa: E402

_app = QApplication.instance() or QApplication([])

SEED = os.path.join(os.path.dirname(__file__), '..', 'presupuestos_seed.db')
_fd, _tmpdb = tempfile.mkstemp(suffix='_dec_cant_test.db')
os.close(_fd)
shutil.copy(SEED, _tmpdb)
d.DB_PATH = _tmpdb
cfg.DB_PATH = _tmpdb
d.init_db()

# El ACU del reporte: cuadrilla 1/1/2, rendimiento 12, jornada 8.
ACU_DAVID = [
    {'tipo': 'MO', 'unidad': 'hh', 'cantidad': 1 / 12 * 8, 'precio': 24.96},
    {'tipo': 'MO', 'unidad': 'hh', 'cantidad': 1 / 12 * 8, 'precio': 19.63},
    {'tipo': 'MO', 'unidad': 'hh', 'cantidad': 2 / 12 * 8, 'precio': 17.76},
]


def _con(**por_tipo):
    antes = dict(d._DECIMALES_CANT_ACU)
    for t, n in por_tipo.items():
        d.set_decimales_cant_acu(n, t)
    return antes


def test_con_4_decimales_da_lo_de_siempre():
    antes = _con(MO=4)
    try:
        assert d._pu_desde_items(ACU_DAVID) == 53.41
    finally:
        d._DECIMALES_CANT_ACU.update(antes)


def test_con_2_decimales_en_mo_cuadra_con_s10():
    antes = _con(MO=2)
    try:
        assert d._pu_desde_items(ACU_DAVID) == 53.49   # 16.72 + 13.15 + 23.62
    finally:
        d._DECIMALES_CANT_ACU.update(antes)


def test_cada_tipo_tiene_su_ajuste():
    antes = _con(MO=2, MAT=4)
    try:
        items = ACU_DAVID[:1] + [
            {'tipo': 'MAT', 'unidad': 'kg', 'cantidad': 0.123456, 'precio': 100.0}]
        # MO 0.67 × 24.96 = 16.72 · MAT 0.1235 × 100 = 12.35
        assert d._pu_desde_items(items) == 29.07
        assert d.get_decimales_cant_acu('MO') == 2
        assert d.get_decimales_cant_acu('MAT') == 4
        assert d.get_decimales_cant_acu('XYZ') == 4    # desconocido → MAT
    finally:
        d._DECIMALES_CANT_ACU.update(antes)


def test_get_acu_items_calcula_igual_que_el_pu_guardado():
    """La pantalla y los reportes (get_acu_items) y el PU que se guarda
    (_pu_desde_items) deben dar lo mismo con cualquier ajuste."""
    antes = _con(MO=2, EQ=2)
    try:
        conn = d.get_db()
        pids = [r[0] for r in conn.execute(
            "SELECT DISTINCT partida_id FROM acu_items LIMIT 200").fetchall()]
        for pid in pids:
            items, tot = d.get_acu_items(conn, pid)
            d._recalcular_pu(conn, pid)
            pu = conn.execute("SELECT precio_unitario FROM partidas WHERE id=?",
                              (pid,)).fetchone()[0]
            assert abs(sum(tot.values()) - pu) < 0.011, (pid, sum(tot.values()), pu)
            for it in items:
                if not (it['unidad'] or '').startswith('%'):
                    n = d.get_decimales_cant_acu(it['tipo'])
                    assert it['cantidad'] == d._rn(it['cantidad'], n), it
        conn.rollback()
        conn.close()
    finally:
        d._DECIMALES_CANT_ACU.update(antes)


def test_la_configuracion_se_guarda_por_tipo_y_hereda_el_valor_viejo():
    conn = d.get_db()
    claves = {r[0]: r[1] for r in conn.execute(
        "SELECT clave, valor FROM configuracion WHERE clave LIKE 'decimales_cantidad_%'")}
    conn.close()
    for t in ('mo', 'mat', 'eq', 'sc'):
        assert claves.get(f'decimales_cantidad_{t}') == claves['decimales_cantidad_acu'], claves


def test_configuracion_muestra_cuatro_ajustes():
    from views.configuracion_view import ConfiguracionView
    v = ConfiguracionView()
    card = v._card_decimales()   # las secciones se construyen al abrirlas; sin
    assert card is not None      # referencia, Qt borra la tarjeta y sus spins
    assert set(v.spin_dec_cant) == {'MO', 'MAT', 'EQ', 'SC'}
    antes = dict(d._DECIMALES_CANT_ACU)
    try:
        v.spin_dec_cant['MO'].setValue(2)
        v._guardar_decimales()
        assert d.get_decimales_cant_acu('MO') == 2
        assert d.get_config('decimales_cantidad_mo') == '2'
        assert d.get_decimales_cant_acu('MAT') == antes['MAT']
    finally:
        d._DECIMALES_CANT_ACU.update(antes)
        d.set_config('decimales_cantidad_mo', str(antes['MO']))
        v.close()


# ── Los montos del ACU en pantalla siguen a Configuración (David, 2 oct 2026) ─

PID = 397  # PLAZA PRINCIPAL DE YANQUE: the only budget in the public seed
_VIVAS = []


def _vista():
    from views.proyecto_view import ProyectoView
    from models.usuario import Usuario
    v = ProyectoView(PID, Usuario(id=1, nombre="t", rol="admin"))
    v._completar_panel_tabs()
    v._cargar_datos_inicial()
    _app.processEvents()          # the deferred load _completar_panel_tabs queued
    _VIVAS.append(v)
    return v


def _partida_con_acu() -> int:
    conn = d.get_db()
    pid = conn.execute(
        "SELECT p.id FROM partidas p JOIN acu_items ai ON ai.partida_id=p.id "
        "WHERE p.proyecto_id=? AND p.es_titulo=0 ORDER BY p.item LIMIT 1",
        (PID,)).fetchone()[0]
    conn.close()
    return pid


def _decimales(texto: str) -> int:
    """Cifras después del último separador decimal de «S/ 1,234.5678»."""
    return len(texto.rsplit('.', 1)[1]) if '.' in texto else 0


def _parciales_acu(v) -> list:
    return [v.tbl_acu.item(r, 6).text() for r in range(v.tbl_acu.rowCount())
            if v._acu_row_ids[r] != -1]


def test_el_acu_en_pantalla_usa_los_decimales_de_montos():
    antes = d.get_decimales_ppto()
    try:
        d.set_decimales_ppto(4)
        v = _vista()
        v.cargar_acu(_partida_con_acu())
        parciales = _parciales_acu(v)
        assert parciales and all(_decimales(t) == 4 for t in parciales), parciales
        assert _decimales(v.lbl_pu.text()) == 4, v.lbl_pu.text()
        subt = [l.text() for l in v._sub_labels.values()]
        assert all(_decimales(t) == 4 for t in subt), subt
    finally:
        d.set_decimales_ppto(antes)


def test_al_volver_de_configuracion_el_proyecto_abierto_se_repinta():
    antes = d.get_decimales_ppto()
    try:
        d.set_decimales_ppto(2)
        v = _vista()
        v.show()
        v.cargar_acu(_partida_con_acu())
        assert _parciales_acu(v) and all(_decimales(t) == 2 for t in _parciales_acu(v))
        # Ir a Configuración: el proyecto sigue vivo, oculto en el stack.
        v.hide()
        d.set_decimales_ppto(3)
        v.show()
        _app.processEvents()
        parciales = _parciales_acu(v)
        assert parciales and all(_decimales(t) == 3 for t in parciales), parciales
        item = v._id_to_item[v._partida_actual_id]
        assert _decimales(item.text(4)) == 3, item.text(4)          # P.U. del árbol
        v.close()
    finally:
        d.set_decimales_ppto(antes)


# ── La columna Precio del ACU también (David, ronda 7: ACU.docx) ─────────────
# Con 2 decimales en montos el ACU mostraba «28.0300» y la pestaña Insumos
# «28.03». Ahora los dos siguen a Configuración, y los editores abren con el
# valor COMPLETO: arrancar del texto redondeado y guardar al salir dejaba
# 28.0312 en 28.03 en todo el proyecto sin que nadie lo tocara.

def test_texto_de_edicion_guarda_todo_y_no_menos_que_los_decimales():
    from views.proyecto_view import _texto_edicion
    assert _texto_edicion(28.0312, 2) == '28.0312'
    assert _texto_edicion(28.03, 2) == '28.03'
    assert _texto_edicion(5, 2) == '5.00'
    assert _texto_edicion(5, 0) == '5'
    assert _texto_edicion(1.5, 4) == '1.5000'


def _precio_largo():
    """Una línea del ACU con un precio de cuatro decimales; (partida, acu_id)."""
    part = _partida_con_acu()
    conn = d.get_db()
    acu_id, rid = conn.execute(
        "SELECT id, recurso_id FROM acu_items WHERE partida_id=? ORDER BY id LIMIT 1",
        (part,)).fetchone()
    conn.execute("UPDATE acu_items SET precio=28.0312 WHERE recurso_id=? AND partida_id IN "
                 "(SELECT id FROM partidas WHERE proyecto_id=?)", (rid, PID))
    conn.commit()
    conn.close()
    return part, acu_id


def _precio_en_bd(acu_id):
    conn = d.get_db()
    v = conn.execute("SELECT precio FROM acu_items WHERE id=?", (acu_id,)).fetchone()[0]
    conn.close()
    return v


def test_el_precio_del_acu_sigue_los_decimales_y_se_edita_completo():
    from PySide6.QtWidgets import QLineEdit
    antes = d.get_decimales_ppto()
    try:
        d.set_decimales_ppto(2)
        part, acu_id = _precio_largo()
        v = _vista()
        v.cargar_acu(part)
        r = v._acu_row_ids.index(acu_id)
        idx = v.tbl_acu.model().index(r, 5)
        assert v.tbl_acu.item(r, 5).text() == '28.03'
        deleg = v.tbl_acu.itemDelegateForColumn(5)
        ed = QLineEdit()
        deleg.setEditorData(ed, idx)
        assert ed.text() == '28.0312'
        # Pasar por la celda sin cambiar nada no guarda el redondeo.
        deleg.setModelData(ed, v.tbl_acu.model(), idx)
        _app.processEvents()
        assert _precio_en_bd(acu_id) == 28.0312
    finally:
        d.set_decimales_ppto(antes)


def test_el_editor_de_precio_de_insumos_no_guarda_el_redondeo():
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    antes = d.get_decimales_ppto()
    try:
        d.set_decimales_ppto(2)
        part, acu_id = _precio_largo()
        conn = d.get_db()      # solo «En elaboración» deja editar precios
        conn.execute("UPDATE proyectos SET estado='elaboracion' WHERE id=?", (PID,))
        conn.commit()
        conn.close()
        v = _vista()
        v.cargar_insumos()
        fila = next(r for r in range(v.tbl_ins.rowCount())
                    if v.tbl_ins.item(r, 4) is not None
                    and v.tbl_ins.item(r, 4).data(Qt.UserRole) == 28.0312)
        assert v.tbl_ins.item(fila, 4).text().endswith('28.03')
        v._abrir_editor_precio_ins(fila)
        ed = v._ins_ed
        assert ed.text() == '28.0312'
        _app.sendEvent(ed, QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier))
        _app.processEvents()
        assert _precio_en_bd(acu_id) == 28.0312
    finally:
        d.set_decimales_ppto(antes)


if __name__ == "__main__":
    fallos = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"  OK  {name}")
            except Exception as e:                       # noqa: BLE001
                fallos += 1
                import traceback
                print(f"  FAIL {name}: {e}")
                traceback.print_exc()
    print("\nTODO OK" if not fallos else f"\n{fallos} FALLOS")
    try:
        os.remove(_tmpdb)
    except OSError:
        pass
    sys.exit(1 if fallos else 0)
