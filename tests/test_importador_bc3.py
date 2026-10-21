# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari
# This file is part of IngePresupuestos — https://ingepresupuestos.com
# Software libre bajo la GNU GPL v3 o posterior. Ver el archivo LICENSE.
"""Importador BC3 (FIEBDC-3): presupuesto → proyecto y base → biblioteca.

Corre con:  QT_QPA_PLATFORM=offscreen venv/bin/python3 tests/test_importador_bc3.py

Usa una COPIA temporal de presupuestos_seed.db (nunca la BD activa) y un BC3
PEQUEÑO escrito aquí mismo, en cp1252 y con registros partidos en varias
líneas, que cubre: capítulos anidados bajo una raíz ##, una partida con
MO/MAT/EQ, un auxiliar anidado (se aplana), un porcentaje sobre todo lo
anterior (se congela) y otro que es exactamente el subtotal de MO (se mapea a
%mo), mediciones con dimensiones, expresión y subtotal, texto ~T con tildes
y ñ, y un capítulo con rendimiento 0 (fuera del total, no se importa).

Las cuentas se verifican con las funciones de la app (`_pu_desde_items`,
`get_acu_items`, `calcular_totales`), NUNCA reimplementando la regla aquí.

Si existe la muestra real CENZANO.bc3 (Presto 8.8, vivienda unifamiliar) en
la ruta de `CENZANO`, se reconcilia también contra ella; si no, se salta.
"""
import os
import shutil
import sys
import tempfile
import zipfile

# Antes de importar nada de la app: que `core.config` no apunte a la BD real.
_XDG = tempfile.mkdtemp(prefix='bc3_xdg_')
os.environ['XDG_DATA_HOME'] = _XDG
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import core.config as _cfg
import core.database as d
from core import bc3_importer as b

SEED = os.path.join(os.path.dirname(__file__), '..', 'presupuestos_seed.db')
CENZANO = ('/tmp/claude-1000/-home-sumaritux-Proyectos-ingepresupuestos/'
           '39847725-e841-4801-9940-a7e93f3b75a8/scratchpad/muestras/bc3/CENZANO.bc3')

# Precios esperados (cuentas a mano, redondeo a 2 por línea como Presto):
#   AUX1 = 2×15 + 0.3×100                                   = 60.00
#   P01  = 0.5×20 + 40×0.15 + 0.03×60 + 0.1×3 = 18.10 ; 2 % → 0.36 → 18.46
#   P02  = 2×16 + 10×0.15 = 33.50 ; 5 % de la MO (32) = 1.60 → 35.10
#   C11  = 12.5×18.46 + 3×35.10 = 230.75 + 105.30          = 336.05
BC3 = (
    "~V|Prueba S.L.|FIEBDC-3/2020\\01102026|PruebaSoft 1.0||ANSI||2|\r\n"
    "~K|\\2\\2\\3\\2\\2\\2\\2\\EUR\\|0\\13\\6\\0\\21|\r\n"
    "~C|OBRA##||Vivienda en Begoña|336.05|011026|0|\r\n"
    "~D|OBRA##|C1\\1\\1\\INF\\1\\0\\|\r\n"
    "~C|C1#||Capítulo uno: edificación|336.05|011026|0|\r\n"
    "~D|C1#|C11\\1\\1\\|\r\n"
    "~C|C11#||Albañilería|336.05|011026|0|\r\n"
    "~D|C11#|P01\\1\\12.5\\P02\\1\\3\\|\r\n"
    "~C|INF#||Estudio informativo|35.10|011026|0|\r\n"
    "~D|INF#|P02\\1\\1\\|\r\n"
    "~C|P01|m2|Fábrica de ladrillo|18.46|011026|0|\r\n"
    # Registro partido en varias líneas (Presto lo hace con los ~D largos)
    "~D|P01|MO1\\1\\0.5\\\r\n"
    "      MAT1\\1\\40\\\r\n"
    "      AUX1\\1\\0.03\\\r\n"
    "      EQ1\\1\\0.1\\\r\n"
    "      %MA\\1\\0.02\\|\r\n"
    "~T|P01|Fábrica de ladrillo cerámico recibida con mortero,\r\n"
    "incluso replanteo y nivelación. Año de diseño: «ñandú».|\r\n"
    "~C|MO1|h|Oficial 1ª albañil|20|011026|1|\r\n"
    "~C|MAT1|ud|Ladrillo cerámico|0.15|011026|3|\r\n"
    "~C|EQ1|h|Hormigonera eléctrica|3|011026|2|\r\n"
    "~C|AUX1|m3|Mortero de cemento M-5|60|011026|3|\r\n"
    "~D|AUX1|MO2\\1\\2\\MAT2\\1\\0.3\\|\r\n"
    "~C|MO2|h|Peón ordinario|15|011026|1|\r\n"
    "~C|MAT2|t|Cemento CEM II|100|011026|3|\r\n"
    "~C|%MA|%|Medios auxiliares|2|011026|0|\r\n"
    "~C|P02|ud|Recibido de cercos|35.10|011026|0|\r\n"
    "~D|P02|O1\\1\\2\\MAT1\\1\\10\\O%H\\1\\0.05\\|\r\n"
    "~C|O1|h|Peón especialista|16|011026|1|\r\n"
    "~C|O%H|%|Herramientas (% s/ mano de obra)|5|011026|0|\r\n"
    "~M|C11\\P01|1\\1\\1\\|12.5|\\Muro norte\\2\\2.5\\1.5\\\\"
    "3\\(a+b)*c\\1\\1.5\\2\\\\1\\Subtotal muros\\\\\\\\\\|\r\n"
    "~M|C11\\P02|1\\1\\2\\|3|\\Puertas\\3\\\\\\\\|\r\n"
    "\x1a"
)

_tmpdb = None


def _db_limpia():
    """BD nueva para cada test: copia del seed, `get_db()` apunta a ella."""
    global _tmpdb
    if _tmpdb and os.path.exists(_tmpdb):
        os.unlink(_tmpdb)
    fd, _tmpdb = tempfile.mkstemp(suffix='_bc3.db')
    os.close(fd)
    shutil.copy(SEED, _tmpdb)
    d.DB_PATH = _tmpdb
    _cfg.DB_PATH = _tmpdb
    d.init_db()


def _archivo(contenido: str = BC3, nombre: str = 'prueba.bc3') -> str:
    carpeta = tempfile.mkdtemp(prefix='bc3_')
    ruta = os.path.join(carpeta, nombre)
    with open(ruta, 'wb') as f:
        f.write(contenido.encode('cp1252'))
    return ruta


def _items_db(conn, partida_id):
    items, _ = d.get_acu_items(conn, partida_id)
    return items


# ── Lectura ──────────────────────────────────────────────────────────────────

def test_lee_cp1252_multilinea_y_raiz():
    bc3 = b.leer_bc3(_archivo())
    assert bc3['codificacion'] == 'cp1252'
    assert bc3['raiz'] == 'OBRA'
    assert bc3['divisa'] == 'EUR'
    assert bc3['k']['gg'] == 13 and bc3['k']['bi'] == 6 and bc3['k']['iva'] == 21
    assert {'OBRA', 'C1', 'C11', 'INF'} <= bc3['capitulos']
    assert bc3['conceptos']['OBRA']['resumen'] == 'Vivienda en Begoña'
    # El ~D partido en cinco líneas se lee entero
    assert [h for h, *_ in bc3['descomp']['P01']] == ['MO1', 'MAT1', 'AUX1', 'EQ1', '%MA']
    # El ~T conserva tildes, ñ y el salto de línea
    assert 'nivelación' in bc3['textos']['P01'] and '«ñandú»' in bc3['textos']['P01']
    assert '\n' in bc3['textos']['P01']


def test_detecta_presupuesto_y_base():
    assert b.detectar_bc3(_archivo())['tipo'] == 'presupuesto'
    sin_m = '\r\n'.join(l for l in BC3.split('\r\n') if not l.startswith('~M'))
    det = b.detectar_bc3(_archivo(sin_m))
    assert det['tipo'] == 'base'
    assert det['n_descompuestos'] == 3            # P01, P02 y el auxiliar


def test_lee_bc3_dentro_de_zip():
    carpeta = tempfile.mkdtemp(prefix='bc3zip_')
    ruta = os.path.join(carpeta, 'base.zip')
    with zipfile.ZipFile(ruta, 'w') as z:
        z.writestr('LEEME.txt', 'no soy un bc3')
        z.writestr('BASE2026.bc3', BC3.encode('cp1252'))
    bc3 = b.leer_bc3(ruta)
    assert bc3['nombre_archivo'] == 'BASE2026.bc3'
    assert bc3['raiz'] == 'OBRA'


def test_expresion_de_medicion_no_usa_eval():
    assert b.evaluar_expresion('(b+c)/2*d', {'a': 1, 'b': 17, 'c': 9, 'd': 0.5}) == 6.5
    assert b.evaluar_expresion('2*(3+5+2) * 0.5 - 2.98', {}) == 7.02
    assert abs(b.evaluar_expresion('p*a^2/4', {'a': 2}) - 3.14159265) < 1e-6
    assert b.evaluar_expresion('ABS(-3)+SQRT(16)', {}) == 7
    for maligno in ("__import__('os')", 'a.__class__', 'open(1)'):
        try:
            b.evaluar_expresion(maligno, {'a': 1})
        except ValueError:
            continue
        raise AssertionError(f"se evaluó {maligno!r}")


def test_unidad_porcentaje_de_un_insumo_normal_no_es_porcentaje():
    """BCCA 2023 trae «% Perfilería complementaria» medido en «%» con precio
    propio: guardado con unidad «%» la app lo calculaba como % de la MO."""
    u = b._unidad_insumo('%')
    assert not u.startswith('%')
    assert b._unidad_insumo('m2') == 'm2'


# ── Presupuesto → proyecto ───────────────────────────────────────────────────

def test_presupuesto_a_proyecto_reconcilia():
    _db_limpia()
    pid, resumen, info = b.guardar_presupuesto_bc3(_archivo())
    conn = d.get_db()
    try:
        filas = {r['item']: r for r in conn.execute(
            "SELECT * FROM partidas WHERE proyecto_id=? ORDER BY item", (pid,))}
        # Capítulos anidados → títulos; el capítulo con rendimiento 0 no entra
        assert filas['01']['es_titulo'] == 1 and filas['01']['nivel'] == 1
        assert filas['01.01']['es_titulo'] == 1 and filas['01.01']['nivel'] == 2
        assert set(filas) == {'01', '01.01', '01.01.01', '01.01.02'}
        assert any('rendimiento 0' in a for a in info['bc3_avisos'])
        p01, p02 = filas['01.01.01'], filas['01.01.02']
        assert p01['descripcion'] == 'Fábrica de ladrillo'
        assert p01['metrado'] == 12.5 and p02['metrado'] == 3

        # P.U.: el que calcula la app desde el ACU guardado == ~C del archivo
        for p, esperado in ((p01, 18.46), (p02, 35.10)):
            items = _items_db(conn, p['id'])
            assert d._pu_desde_items(items) == esperado, (p['item'], items)
            assert abs(p['precio_unitario'] - esperado) < 0.005

        it1 = {i['descripcion']: i for i in _items_db(conn, p01['id'])}
        # MO directa: cuadrilla 0, cantidad del ~D
        assert it1['Oficial 1ª albañil']['tipo'] == 'MO'
        assert it1['Oficial 1ª albañil']['cantidad'] == 0.5
        assert not it1['Oficial 1ª albañil']['cuadrilla']
        assert it1['Hormigonera eléctrica']['tipo'] == 'EQ'
        # Auxiliar aplanado: una línea con el precio de su descomposición
        aux = it1['Mortero de cemento M-5']
        assert aux['tipo'] == 'MAT' and aux['precio'] == 60 and aux['cantidad'] == 0.03
        assert 'Peón ordinario' not in it1                 # no se duplica
        # Porcentaje sobre todo lo anterior: congelado en dinero
        ma = it1['Medios auxiliares']
        assert ma['unidad'] == '€' and ma['precio'] == 1 and ma['parcial'] == 0.36

        it2 = {i['descripcion']: i for i in _items_db(conn, p02['id'])}
        # Porcentaje cuya base es toda la MO: unidad %mo, recalculable
        h = it2['Herramientas (% s/ mano de obra)']
        assert h['unidad'] == '%mo' and h['cantidad'] == 5 and h['parcial'] == 1.6

        # Mediciones: dimensiones, expresión (resultado en n_elementos) y subtotal
        met = conn.execute(
            "SELECT * FROM metrados_detalle WHERE partida_id=? ORDER BY orden",
            (p01['id'],)).fetchall()
        assert len(met) == 3
        assert (met[0]['n_elementos'], met[0]['largo'], met[0]['ancho']) == (2, 2.5, 1.5)
        assert met[0]['parcial'] == 7.5
        assert met[1]['n_elementos'] == 5 and met[1]['parcial'] == 5
        assert '(a+b)*c' in met[1]['descripcion']
        assert met[2]['parcial'] is None and 'Subtotal' in met[2]['descripcion']

        # ~T → especificaciones, con el código BC3 delante
        assert p01['especificaciones'].startswith('Código BC3: P01')
        assert '«ñandú»' in p01['especificaciones']

        proy = conn.execute("SELECT * FROM proyectos WHERE id=?", (pid,)).fetchone()
        assert proy['nombre'] == 'Vivienda en Begoña'
        assert proy['moneda'] == 'Euros'
        assert (proy['gf_pct'], proy['utilidad_pct'], proy['igv_pct']) == (13, 6, 21)
        # Insumo nuevo sin índice INEI (no es un insumo peruano)
        r = conn.execute("SELECT codigo, indice_inei FROM recursos "
                         "WHERE descripcion='Hormigonera eléctrica'").fetchone()
        assert r['codigo'].startswith('03') and len(r['codigo']) == 7
        assert r['indice_inei'] == ''
    finally:
        conn.close()

    # Total de la app == precio de la raíz ##: el pie entra inactivo
    _, tot = d.calcular_totales(pid)
    assert tot['cd'] == 336.05 and tot['total'] == 336.05, tot


def test_presupuesto_sin_raiz_ni_mediciones():
    """Sin raíz ## los capítulos superiores son los que nadie contiene; sin
    ~M el metrado sale del rendimiento del ~D del capítulo."""
    sin = '\r\n'.join(l for l in BC3.split('\r\n')
                      if not l.startswith(('~M', '~C|OBRA##', '~D|OBRA##')))
    info, partidas, acus, recursos, metrados = b.import_bc3_presupuesto(_archivo(sin))
    items = {p['item']: p for p in partidas}
    assert items['01']['descripcion'].startswith('Capítulo uno')
    assert items['02']['descripcion'] == 'Estudio informativo'   # sin raíz no hay rend 0
    assert items['01.01.01']['metrado'] == 12.5
    assert metrados is None


# ── Base de precios → biblioteca ─────────────────────────────────────────────

def test_base_a_biblioteca_y_reimportacion():
    _db_limpia()
    ruta = _archivo(nombre='BASE2026.bc3')
    r = b.import_biblioteca_bc3(ruta)
    assert r['ok'] and r['n_acs_origen'] == 3 and r['n_creados'] == 3
    assert r['n_cuadran'] == 3 and not r['descuadres']
    conn = d.get_db()
    try:
        cus = {c['descripcion']: c for c in conn.execute(
            "SELECT * FROM biblioteca_cu WHERE grupo LIKE 'OBRA%'")}
        assert set(cus) == {'Fábrica de ladrillo', 'Recibido de cercos',
                            'Mortero de cemento M-5'}
        assert cus['Fábrica de ladrillo']['grupo'] == 'OBRA · Albañilería'
        assert cus['Mortero de cemento M-5']['grupo'] == 'OBRA'   # sin capítulo
        assert 'nivelación' in cus['Fábrica de ladrillo']['especificaciones']
        for desc, esperado in (('Fábrica de ladrillo', 18.46),
                               ('Recibido de cercos', 35.10),
                               ('Mortero de cemento M-5', 60.0)):
            cu = cus[desc]
            items = conn.execute(
                """SELECT i.cantidad, COALESCE(i.precio, r.precio, 0) AS precio,
                          r.unidad, r.tipo
                   FROM biblioteca_acu_items i JOIN recursos r ON r.id=i.recurso_id
                   WHERE i.cu_id=?""", (cu['id'],)).fetchall()
            assert d._pu_desde_items(items) == esperado, desc
            assert cu['costo_unitario'] == esperado
        n_rec = conn.execute("SELECT COUNT(*) FROM recursos").fetchone()[0]
    finally:
        conn.close()

    # Reimportar la misma base actualiza, no duplica (ni CU ni insumos)
    r2 = b.import_biblioteca_bc3(ruta)
    assert r2['n_creados'] == 0 and r2['n_actualizados'] == 3
    assert r2['n_recursos_creados'] == 0
    conn = d.get_db()
    try:
        assert conn.execute("SELECT COUNT(*) FROM recursos").fetchone()[0] == n_rec
        assert conn.execute("SELECT COUNT(*) FROM biblioteca_cu "
                            "WHERE grupo LIKE 'OBRA%'").fetchone()[0] == 3
    finally:
        conn.close()
    r3 = b.import_biblioteca_bc3(ruta, modo='solo_nuevos')
    assert r3['n_ignorados'] == 3 and r3['n_creados'] == 0


# ── Muestra real ─────────────────────────────────────────────────────────────

def test_cenzano_reconcilia():
    """CENZANO.bc3 (Presto 8.8): 160 partidas, raíz 132 806,15 €."""
    if not os.path.isfile(CENZANO):
        print("      (saltado: no está la muestra CENZANO.bc3)")
        return
    _db_limpia()
    bc3 = b.leer_bc3(CENZANO)
    calc = b._Calculo(bc3)
    pid, _resumen, info = b.guardar_presupuesto_bc3(CENZANO)
    conn = d.get_db()
    malos = []
    n = 0
    try:
        for p in conn.execute("SELECT id, item, especificaciones FROM partidas "
                              "WHERE proyecto_id=? AND es_titulo=0", (pid,)):
            n += 1
            cod = p['especificaciones'].splitlines()[0].replace('Código BC3: ', '')
            pu_app = d._pu_desde_items(_items_db(conn, p['id']))
            if abs(pu_app - calc.precio_archivo(cod)) > 0.0105:
                malos.append((p['item'], cod, pu_app, calc.precio_archivo(cod)))
    finally:
        conn.close()
    assert n == 160, n
    assert not malos, malos[:10]
    _, tot = d.calcular_totales(pid)
    assert abs(tot['total'] - info['bc3_precio_raiz']) < 0.005, (tot, info['bc3_precio_raiz'])
    assert info['bc3_metrados_desglosados'] >= 150


if __name__ == "__main__":
    fallos = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"  OK  {name}")
            except AssertionError as e:
                fallos += 1
                print(f"  FAIL {name}: {e}")
    if _tmpdb and os.path.exists(_tmpdb):
        os.unlink(_tmpdb)
    shutil.rmtree(_XDG, ignore_errors=True)
    sys.exit(1 if fallos else 0)
