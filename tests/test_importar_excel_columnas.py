# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari
# This file is part of IngePresupuestos — https://ingepresupuestos.com
# Software libre bajo la GNU GPL v3 o posterior. Ver el archivo LICENSE.
"""Importar insumos desde un Excel cualquiera, con asignación de columnas.

Corre con:  QT_QPA_PLATFORM=offscreen venv/bin/python3 -m pytest tests/test_importar_excel_columnas.py -q

Lo pidieron un usuario de Uruguay (Lista Oficial de Precios del MTOP), uno de
España (Menfis) y los de Brasil (SINAPI): el importador viejo exigía la
cabecera propia en la primera fila. Los Excel se crean aquí mismo con
openpyxl; la Lista 606 real se prueba solo si está a mano. Usa una COPIA
temporal del seed y un QSettings temporal.
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest                                                        # noqa: E402
from openpyxl import Workbook                                       # noqa: E402
from PySide6.QtCore import QSettings                                # noqa: E402
from PySide6.QtWidgets import QApplication                          # noqa: E402

_QS_DIR = tempfile.mkdtemp(suffix='_qs')
QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, _QS_DIR)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, _QS_DIR)

import core.config as cfg                                           # noqa: E402
import core.database as d                                           # noqa: E402

_app = QApplication.instance() or QApplication([])

SEED = os.path.join(os.path.dirname(__file__), '..', 'presupuestos_seed.db')
_fd, _tmpdb = tempfile.mkstemp(suffix='_importar_excel_test.db')
os.close(_fd)
shutil.copy(SEED, _tmpdb)
d.DB_PATH = _tmpdb
cfg.DB_PATH = _tmpdb
d.init_db()

from core import importar_excel_insumos as imp                     # noqa: E402

_TMP = tempfile.mkdtemp(suffix='_xlsx')
LISTA_606 = ('/tmp/claude-1000/-home-sumaritux-Proyectos-ingepresupuestos/'
             '39847725-e841-4801-9940-a7e93f3b75a8/scratchpad/muestras/mtop/lista606.xlsx')


def _xlsx(nombre: str, filas: list, hoja: str = 'Hoja1') -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = hoja
    for f in filas:
        ws.append(list(f))
    ruta = os.path.join(_TMP, nombre)
    wb.save(ruta)
    return ruta


def _preparar(ruta: str, **cambios):
    lib = imp.leer_libro(ruta)
    hoja = imp.hoja_inicial(lib)
    op = imp.configuracion_inicial(lib.filas[hoja], hoja, impuesto_pct=22.0)
    for k, v in cambios.items():
        setattr(op, k, v)
    ins, om = imp.preparar_insumos(lib.filas[hoja], op)
    return op, ins, om


def _recurso(codigo: str):
    conn = d.get_db()
    try:
        return conn.execute("SELECT * FROM recursos WHERE codigo=?", (codigo,)).fetchone()
    finally:
        conn.close()


def _alta(codigo: str, precio: float, desc='existente', tipo='MAT', unidad='kg',
          inei='02'):
    conn = d.get_db()
    conn.execute("DELETE FROM recursos WHERE codigo=?", (codigo,))
    conn.execute("INSERT INTO recursos (codigo, descripcion, tipo, unidad, precio,"
                 " indice_inei) VALUES (?,?,?,?,?,?)",
                 (codigo, desc, tipo, unidad, precio, inei))
    conn.commit()
    conn.close()


# ── Cabecera y asignación ───────────────────────────────────────────────────
def test_cabecera_desplazada_y_sinonimos():
    ruta = _xlsx('desplazada.xlsx', [
        ['LISTA DE PRECIOS DE MATERIALES'],
        ['Octubre 2026'],
        [],
        ['Cód.', 'Denominación', 'Und', 'Valor'],
        ['T-001', 'Cemento portland', 'bolsa', '1.234,56'],
        ['T-002', 'Arena gruesa', 'm3', 'S/ 80.50'],
    ])
    op, ins, om = _preparar(ruta)
    assert op.fila_cabecera == 3
    assert op.columnas['codigo'] == 0 and op.columnas['descripcion'] == 1
    assert op.columnas['unidad'] == 2 and op.columnas['precio'] == 3
    assert op.tipo_fijo == 'MAT' and not op.quitar_impuesto
    assert [(i.codigo, i.unidad, i.precio) for i in ins] == [
        ('T-001', 'bolsa', 1234.56), ('T-002', 'm3', 80.5)]
    assert om == []


def test_cabecera_en_portugues_sinapi():
    ruta = _xlsx('sinapi.xlsx', [
        ['SINAPI - PREÇOS DE INSUMOS'],
        ['CODIGO', 'DESCRIÇÃO DO INSUMO', 'UNIDADE DE MEDIDA', 'PREÇO MEDIANO R$'],
        [370, 'AREIA MEDIA', 'M3', '125,00'],
    ])
    op, ins, _ = _preparar(ruta)
    assert op.fila_cabecera == 1
    assert (op.columnas['codigo'], op.columnas['descripcion'],
            op.columnas['unidad'], op.columnas['precio']) == (0, 1, 2, 3)
    assert ins[0].codigo == '370' and ins[0].precio == 125.0


def test_formato_viejo_exacto_sin_tocar_nada():
    ruta = _xlsx('viejo.xlsx', [
        ['Código', 'Tipo', 'Descripción', 'Unidad', 'Precio', 'Índice INEI'],
        ['3999901', 'MAT', 'Clavo de prueba', 'kg', 5.5, '02'],
        ['3999902', 'MO', 'Operario de prueba', 'hh', 23.4, '47'],
        ['3999903', 'EQ', 'Herramientas manuales prueba', '%MO', 0, '37'],
        ['3999904', 'XX', 'Tipo inválido', 'u', 1, '39'],
    ])
    op, ins, om = _preparar(ruta)
    assert op.fila_cabecera == 0 and op.tipo_fijo is None
    assert op.columnas == {'codigo': 0, 'tipo': 1, 'descripcion': 2, 'unidad': 3,
                           'precio': 4, 'inei': 5}
    assert not op.omitir_sin_precio          # en el formato propio un 0 es un dato
    assert [i.tipo for i in ins] == ['MAT', 'MO', 'EQ']
    assert om == [(5, 'tipo_invalido')]
    res = imp.importar_insumos(ins)
    assert res['nuevos'] == 3
    r = _recurso('3999903')
    assert r['unidad'] == '%MO' and r['precio'] == 0 and r['indice_inei'] == '37'


# ── Cantidad + unidad, impuesto, tipo ───────────────────────────────────────
def test_cantidad_en_la_unidad():
    filas = [['Código', 'Descripción', 'Cantidad', 'Precio'],
             ['C1', 'Acero', '100 Kg', 26222.59],
             ['C2', 'Adhesivo', '5  Kg', 251.40],
             ['C3', 'Baldosa', '1 m².', 1564.75],
             ['C4', 'Yeso', 'Kg.', 10]]
    op, ins, _ = _preparar(_xlsx('cant.xlsx', filas))
    assert op.cantidad_en_unidad
    assert [(i.unidad, i.precio) for i in ins] == [
        ('Kg', 262.2259), ('Kg', 50.28), ('m²', 1564.75), ('Kg', 10.0)]
    assert ins[0].original.startswith('100 Kg a 26,222.59')
    # Unidades normales («m2», «kg») no disparan la detección
    assert not imp.detectar_cantidad_en_unidad([['m2'], ['kg'], ['1 u']], 0)
    assert imp.partir_cantidad_unidad('1 l') == (1.0, 'l')


def test_quitar_iva_detectado_por_la_cabecera():
    filas = [['Código', 'Descripción', 'Unidad', 'Precio c/IVA'],
             ['V1', 'Pintura', 'gl', 122]]
    op, ins, _ = _preparar(_xlsx('iva.xlsx', filas))
    assert op.quitar_impuesto and op.impuesto_pct == 22.0
    assert 'impuesto' in op.motivos
    assert ins[0].precio == 100.0
    assert imp.detectar_impuesto('PRECIOS MAS IVA')
    assert not imp.detectar_impuesto('Precio sin IVA')
    assert not imp.detectar_impuesto('Precio s/IVA')
    assert not imp.detectar_impuesto('Precio')
    # Sin la palabra en la cabecera, desmarcado; el usuario lo marca a mano
    filas[0][3] = 'Precio'
    op, ins, _ = _preparar(_xlsx('sin_iva.xlsx', filas))
    assert not op.quitar_impuesto and ins[0].precio == 122
    op, ins, _ = _preparar(_xlsx('sin_iva.xlsx', filas), quitar_impuesto=True,
                           impuesto_pct=18.0)
    assert round(ins[0].precio, 4) == round(122 / 1.18, 4)


def test_tipo_fijo_o_por_columna():
    filas = [['Código', 'Descripción', 'Unidad', 'Precio'], ['F1', 'Peón', 'hh', 10]]
    op, ins, _ = _preparar(_xlsx('fijo.xlsx', filas), tipo_fijo='MO')
    assert ins[0].tipo == 'MO'
    filas = [['Descripción', 'Clase', 'Unidad', 'Precio'],
             ['Peón', 'Mano de obra', 'hh', 10],
             ['Mezcladora', 'Equipos', 'hm', 30],
             ['Pintado', 'Servicio', 'm2', 5]]
    op, ins, _ = _preparar(_xlsx('clase.xlsx', filas))
    assert op.columnas['tipo'] == 1 and op.tipo_fijo is None
    assert [i.tipo for i in ins] == ['MO', 'EQ', 'SC']


# ── Escritura en la BD ──────────────────────────────────────────────────────
def test_omitir_sin_precio_y_no_pisar_con_cero():
    _alta('ZP-1', 50.0, unidad='u')
    filas = [['Código', 'Descripción', 'Unidad', 'Precio'],
             ['ZP-1', 'Descripción nueva', 'u', 0],
             ['ZP-2', 'Sin precio este mes', 'u', 0],
             [None, 'Nota al pie: valores válidos desde junio', None, None]]
    ruta = _xlsx('cero.xlsx', filas)
    op, ins, om = _preparar(ruta)
    assert op.omitir_sin_precio and ins == []
    assert sorted(m for _, m in om) == ['sin_precio', 'sin_precio', 'texto']
    # Desmarcado: se importa, pero el 0 no pisa el 50 existente
    op, ins, om = _preparar(ruta, omitir_sin_precio=False)
    res = imp.importar_insumos(ins)
    assert res == {'nuevos': 1, 'actualizados': 1, 'precio_conservado': 1}
    r = _recurso('ZP-1')
    assert r['precio'] == 50.0 and r['descripcion'] == 'Descripción nueva'
    assert _recurso('ZP-2')['precio'] == 0
    assert 'conservaron su precio' in imp.resumen(res, om)


def test_actualiza_por_codigo_y_conserva_el_indice():
    _alta('UPD-9', 10.0, desc='viejo', unidad='kg', inei='05')
    ruta = _xlsx('upd.xlsx', [['Código', 'Descripción', 'Unidad', 'Precio'],
                              ['UPD-9', 'nuevo', 'kg', 12.5],
                              ['UPD-10', 'otro', 'kg', 3]])
    _, ins, _ = _preparar(ruta)
    res = imp.importar_insumos(ins)
    assert res['nuevos'] == 1 and res['actualizados'] == 1
    r = _recurso('UPD-9')
    assert (r['descripcion'], r['precio'], r['indice_inei']) == ('nuevo', 12.5, '05')
    # Código de otro sistema → índice por defecto del tipo, no «UP»
    assert _recurso('UPD-10')['indice_inei'] == '39'


def test_prefijo_de_codigo():
    ruta = _xlsx('pref.xlsx', [['Código', 'Descripción', 'Unidad', 'Precio'],
                               [4348, 'Acero torsionado', 'kg', 2.0]])
    _, ins, _ = _preparar(ruta, prefijo='MTOP-')
    assert ins[0].codigo == 'MTOP-4348'
    imp.importar_insumos(ins)
    assert _recurso('MTOP-4348')['descripcion'] == 'Acero torsionado'


# ── Diálogo ─────────────────────────────────────────────────────────────────
def test_dialogo_recuerda_la_asignacion_por_firma():
    from views.importar_excel_dialog import ImportarExcelDialog
    qs = QSettings(os.path.join(_TMP, 'qs.ini'), QSettings.IniFormat)
    ruta = _xlsx('dlg.xlsx', [['Titulo'], ['Cod', 'Nombre', 'Und', 'Importe'],
                              ['DLG-1', 'Bomba', 'u', 300]])
    lib = imp.leer_libro(ruta)
    dlg = ImportarExcelDialog(lib, impuesto_pct=22.0, settings=qs)
    assert not dlg._memoria and dlg.spin_cab.value() == 2
    cb = dlg.cmb_col['tipo']
    cb.setCurrentIndex(cb.findData('fijo:EQ'))
    dlg.inp_pref.setText('X-')
    assert dlg.b_ok.isEnabled() and '1' in dlg.b_ok.text()
    dlg._aceptar()
    assert dlg.resultado == {'nuevos': 1, 'actualizados': 0, 'precio_conservado': 0}
    assert _recurso('X-DLG-1')['tipo'] == 'EQ'
    # El mes siguiente: mismo formato → misma asignación, sin tocar nada
    dlg2 = ImportarExcelDialog(lib, impuesto_pct=22.0, settings=qs)
    assert dlg2._memoria
    assert dlg2.op.tipo_fijo == 'EQ' and dlg2.inp_pref.text() == 'X-'
    dlg2._aceptar()
    assert dlg2.resultado['actualizados'] == 1


def test_dialogo_sin_columnas_obligatorias_no_importa():
    from views.importar_excel_dialog import ImportarExcelDialog
    qs = QSettings(os.path.join(_TMP, 'qs2.ini'), QSettings.IniFormat)
    ruta = _xlsx('raro.xlsx', [['Alfa', 'Beta', 'Gamma'], ['x', 'y', 'z']])
    dlg = ImportarExcelDialog(imp.leer_libro(ruta), impuesto_pct=22.0, settings=qs)
    assert not dlg.b_ok.isEnabled()
    assert 'Falta asignar' in dlg.lbl_resumen.text()


# ── La Lista Oficial del MTOP real (n.º 606, junio 2026) ────────────────────
@pytest.mark.skipif(not os.path.exists(LISTA_606), reason="lista 606 no disponible")
def test_lista_mtop_606():
    from views.importar_excel_dialog import ImportarExcelDialog
    qs = QSettings(os.path.join(_TMP, 'qs606.ini'), QSettings.IniFormat)
    lib = imp.leer_libro(LISTA_606)
    dlg = ImportarExcelDialog(lib, impuesto_pct=18.0, settings=qs)
    op = dlg.op
    assert op.hoja == 'JUNIO 2026' and op.fila_cabecera == 2
    assert op.motivos.get('mtop') and op.tipo_fijo == 'MAT'
    assert op.cantidad_en_unidad and op.quitar_impuesto and op.impuesto_pct == 22.0
    assert op.columnas['codigo'] == 2 and op.columnas['descripcion'] == 3
    por_cod = {i.codigo: i for i in dlg._insumos}
    acero = por_cod['4348']
    assert acero.unidad == 'Kg' and abs(acero.precio - 26222.59 / 100 / 1.22) < 0.01
    assert por_cod['4001'].unidad == 'l'
    assert len(dlg._insumos) > 250
    dlg._aceptar()
    assert dlg.resultado['nuevos'] + dlg.resultado['actualizados'] == len(por_cod)
    assert abs(_recurso('4348')['precio'] - 214.94) < 0.01
    # La hoja de nuevos materiales también entra
    dlg2 = ImportarExcelDialog(lib, impuesto_pct=18.0, settings=qs)
    dlg2.cmb_hoja.setCurrentText('NUEVOS MATERIALES')
    assert dlg2.op.fila_cabecera == 3 and dlg2.op.columnas['codigo'] == 1
    assert any(i.codigo == 'SA001' for i in dlg2._insumos)


if __name__ == "__main__":
    fallos = 0
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  OK  {nombre}")
            except Exception as e:
                fallos += 1
                import traceback
                traceback.print_exc()
                print(f"  FAIL {nombre}: {e!r}")
    try:
        os.unlink(_tmpdb)
    except OSError:
        pass
    print("TODO OK" if not fallos else f"FALLOS: {fallos}")
    sys.exit(1 if fallos else 0)
