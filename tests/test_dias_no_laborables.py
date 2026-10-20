# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari
# This file is part of IngePresupuestos — https://ingepresupuestos.com
# Software libre bajo la GNU GPL v3 o posterior. Ver el archivo LICENSE.
"""Issue #24 — sin fecha de inicio guardada no se descontaban domingos ni
feriados, y cambiar el inicio no recalculaba.

Corre con:  QT_QPA_PLATFORM=offscreen venv/bin/python3 tests/test_dias_no_laborables.py

El Gantt mostraba hoy como día 1, pero el CPM no tenía fecha y no saltaba
ningún día: «Días lab.» salía igual a «Días cal.». Ahora la fecha del día 1
y los días no laborables tienen un solo dueño (`core.cronograma`), que usan
la pantalla y los reportes PDF.
Usa una COPIA temporal del seed.
"""
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QDate                                    # noqa: E402
from PySide6.QtWidgets import QApplication                          # noqa: E402

import core.config as cfg                                           # noqa: E402
import core.database as d                                           # noqa: E402

_app = QApplication.instance() or QApplication([])

SEED = os.path.join(os.path.dirname(__file__), '..', 'presupuestos_seed.db')
_fd, _tmpdb = tempfile.mkstemp(suffix='_no_laborables_test.db')
os.close(_fd)
shutil.copy(SEED, _tmpdb)
d.DB_PATH = _tmpdb
cfg.DB_PATH = _tmpdb
d.init_db()

import core.cronograma as cr                                        # noqa: E402

PID = 397  # PLAZA PRINCIPAL DE YANQUE: the only budget in the public seed
_VIVAS = []


def _sin_fecha():
    """Yanque sin fecha de inicio ni costo_al, como el proyecto del reporte."""
    conn = d.get_db()
    conn.execute("UPDATE proyectos SET fecha_inicio=NULL, costo_al=NULL, "
                 "salta_no_laborables=1 WHERE id=?", (PID,))
    conn.commit()
    conn.close()


def _cronograma():
    from views.cronograma_view import CronogramaView
    conn = d.get_db()
    proy = dict(conn.execute("SELECT * FROM proyectos WHERE id=?", (PID,)).fetchone())
    conn.close()
    cv = CronogramaView(PID, proy, lambda: None)
    cv.show()
    cv.cargar()
    _VIVAS.append(cv)
    return cv


def test_sin_fecha_el_dia_1_es_hoy_y_los_domingos_se_saltan():
    proy = {'fecha_inicio': None, 'costo_al': '', 'salta_no_laborables': 1}
    hoy = datetime.combine(datetime.today().date(), datetime.min.time())
    assert cr.fecha_dia1(proy) == hoy
    nw = cr.dias_no_laborables(proy, 14)
    domingos = {k for k in range(1, 15) if (hoy + timedelta(days=k - 1)).weekday() == 6}
    assert nw == domingos and len(domingos) == 2, (nw, domingos)


def test_la_fecha_guardada_manda_y_los_feriados_cuentan():
    # 26/10/2026 es lunes: el 1/11 (domingo) es el día 7; el 8/11 el 14.
    proy = {'fecha_inicio': '2026-10-26', 'feriados': '2026-10-28',
            'salta_no_laborables': 1}
    assert cr.dias_no_laborables(proy, 14) == {3, 7, 14}
    # costo_al (legacy) cuando no hay fecha_inicio.
    assert cr.fecha_dia1({'costo_al': '2026-10-26'}) == datetime(2026, 10, 26)
    # Apagado: nada se salta.
    proy['salta_no_laborables'] = 0
    assert cr.dias_no_laborables(proy, 14) == set()


def test_los_reportes_usan_la_misma_regla_que_la_pantalla():
    import core.pdf_reports as pr
    for proy in ({'fecha_inicio': '2026-10-26', 'feriados': '2026-11-01'},
                 {'fecha_inicio': '', 'costo_al': ''}):
        assert pr._non_working_set_for(proy, 60) == cr.dias_no_laborables(proy, 60)


def test_el_cronograma_sin_fecha_descuenta_dias_no_laborables():
    _sin_fecha()
    cv = _cronograma()
    nw = cv._non_working_set(60)
    assert nw, "sin fecha guardada el CPM debe saltar los domingos de hoy en adelante"
    # Alguna partida de una semana o más cruza un domingo: días lab. < días cal.
    largas = [t for t in cv._tasks.values() if t['EF'] - t['ES'] + 1 >= 7]
    assert largas, "el seed debería tener partidas de una semana o más"
    assert any(cr.contar_laborables(t['ES'], t['EF'], nw) < t['EF'] - t['ES'] + 1
               for t in largas)
    cv.close()


def test_cambiar_el_inicio_recalcula_el_cpm():
    _sin_fecha()
    cv = _cronograma()
    g = cv._gantt_w
    g._on_fecha_inicio(QDate(2026, 11, 1))           # el día 1 cae en domingo
    assert cv._proy['fecha_inicio'] == '2026-11-01'
    plazo = cv._proy.get('plazo') or 0
    esperado = cr.cpm(cv._cron_map, cv._partidas, plazo,
                      cr.dias_no_laborables(cv._proy, plazo + 365))
    assert cv._tasks == esperado
    cv.close()


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
