# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari
# This file is part of IngePresupuestos — https://ingepresupuestos.com
# Software libre bajo la GNU GPL v3 o posterior. Ver el archivo LICENSE.
"""Importador de ficheros BC3 (formato FIEBDC-3, el estándar español).

Es el formato de intercambio de Presto, Arquímedes, Menfis, PREMETI y de
todas las bases de precios autonómicas (Andalucía, Castilla y León, CENTRO…).
Un mismo fichero puede ser dos cosas, y la app hace con cada una algo distinto:

  1. BASE DE PRECIOS → Biblioteca de CU + catálogo de insumos.
     Miles de conceptos: los básicos (mano de obra, maquinaria, materiales)
     van a `recursos`; los descompuestos a `biblioteca_cu` +
     `biblioteca_acu_items`. Sin mediciones.  → ``import_biblioteca_bc3``

  2. PRESUPUESTO → Proyecto.
     Capítulos (#) → títulos, partidas con metrado (de ~M o del rendimiento
     del ~D del capítulo) y ACU desde su ~D. Se guarda por el mismo camino
     que los demás importadores (`importer.guardar_importacion`).
     → ``import_bc3_presupuesto`` / ``guardar_presupuesto_bc3``

Cuál de las dos es lo decide ``detectar_bc3`` (con mediciones ~M =
presupuesto) y el usuario confirma en la pantalla de importar. El campo
TIPO INFORMACIÓN del ~V NO sirve: las dos bases de Andalucía de 2023/2025
dicen «2 = Presupuesto» y son bases de precios.

Decisiones (ver también CLAUDE.md, «Importador BC3»):

- **Varios precios por concepto:** se toma el PRIMERO. Es el que
  corresponde al primer ROTULO del ~V y el único que traen casi todos.
- **Tipo del concepto (~C, campo 6):** 1 → MO · 2 → EQ · 3 → MAT. Un
  concepto SIN descomposición con tipo 0 u otro código (las bases usan la
  clasificación del BOE, Anexo 4) va a MAT, que es el defecto de la app para
  lo desconocido. Uno CON descomposición que aparece dentro de otro ACU
  (auxiliar: mortero, hormigón… o una partida dentro de otra) se APLANA a
  una línea con su precio: con tipo 1/2/3 conserva ese tipo (Presto marca
  los morteros como material, 3) y con tipo 0 va a SC.
- **Porcentajes (`%`/`&` en el código):** se aplican a la suma de las
  líneas ANTERIORES que cubre la máscara (prefijo del código, o la lista
  CODIGO_PORCENTAJE del campo 3 del ~D). Si esa base es exactamente el
  subtotal de UN tipo del ACU entero (todas las MO, todos los MAT o todos
  los EQ y nada más), se mapea a la unidad porcentaje de la app
  (`%mo`/`%mt`/`%eq`, ver `database.base_overhead`) y sigue siendo
  recalculable. Si no —el caso normal: `%CI` o `%MA` sobre todo lo
  anterior, incluso otros porcentajes— la app no tiene unidad que lo
  exprese y se CONGELA: una línea con unidad = divisa («€»), precio 1 y
  cantidad = importe. Reproduce el precio del fichero al céntimo, pero no
  se recalcula si luego cambian los insumos.
- **Auxiliares anidados:** la app no tiene sub-análisis (CLAUDE.md,
  «Trabajo futuro»), así que se aplanan como en PowerCost y Delphin.
- **Mano de obra:** cantidad DIRECTA (cuadrilla 0) y rendimiento de la
  partida vacío (0 = «no aplica»): el BC3 no tiene cuadrillas ni
  producción diaria, y con cuadrilla 0 la app no re-deriva la cantidad
  aunque luego se escriba un rendimiento.
- **~K:** DIVISA → moneda del proyecto; GG/BI/IVA → porcentajes del pie,
  con los rubros INACTIVOS (el precio de la raíz es el de ejecución
  material y así el total de la app es ese mismo número). El CI del ~K NO
  se suma a los precios: la BCCA 2023 declara CI 13 y sus 6 525 precios
  cuadran sin aplicarlo (la spec advierte de no aplicarlo dos veces).
- **Códigos:** el código BC3 (hasta 20 caracteres) no cabe en el código de
  7 dígitos de la app. Los insumos reciben un código nuevo con el prefijo
  de su tipo (01 MO · 02 MAT · 03 EQ · 04 SC) y el código BC3 viaja en la
  primera línea de las especificaciones de cada CU / partida.
"""
from __future__ import annotations

import math
import os
import re
import zipfile
from pathlib import Path

from utils.formatting import num_importado


# ── Constantes ───────────────────────────────────────────────────────────────

_TIPO_BC3 = {1: 'MO', 2: 'EQ', 3: 'MAT'}
_PREFIJO_TIPO = {'MO': '01', 'MAT': '02', 'EQ': '03', 'SC': '04'}

# ~K DIVISA (abreviatura del BCE) → nombre de moneda de la app (config.MONEDAS)
_DIVISAS = {
    'EUR': 'Euros', 'USD': 'Dólares', 'PEN': 'Soles', 'CLP': 'Pesos Chilenos',
    'COP': 'Pesos Colombianos', 'BOB': 'Bolivianos', 'BRL': 'Reales',
    'ARS': 'Pesos Argentinos', 'PYG': 'Guaraníes', 'UYU': 'Pesos Uruguayos',
    'MXN': 'Pesos Mexicanos',
}
_SIMBOLO_DIVISA = {'EUR': '€', 'USD': 'US$', 'PEN': 'S/'}

# Decimales de la línea de medición (DSP del ~K; el defecto de la spec).
_DSP = 2

# Tope del nivel de título: el que la app sabe pintar (theme.NIVEL_MAX).
_NIVEL_MAX = 9

# Tope de lo que se lee de un .zip: una base autonómica pesa ~15 MB.
_MAX_BYTES_ZIP = 300 * 1024 * 1024


class Bc3Error(Exception):
    """El archivo no es un BC3 legible."""


def _num(v, default: float = 0.0) -> float:
    """Ver `utils.formatting.num_importado`. El BC3 usa punto decimal y sin
    miles, pero hay exportadores que escriben coma."""
    return num_importado(v, default)


def _rn(v: float, n: int = 2) -> float:
    from core.database import _rn as _rn_db
    return _rn_db(v, n)


def _cod(c: str) -> str:
    """Código normalizado: sin los '#'/'##' finales. La spec dice que la
    marca es obligatoria en el ~C y opcional en el resto de registros, y
    que «01#» y «01» son el mismo concepto (CENZANO lo hace: el ~D de la raíz
    nombra «01», el ~C es «01#»)."""
    return (c or '').strip().rstrip('#')


def es_porcentaje(codigo: str) -> bool:
    return '%' in codigo or '&' in codigo


def _mascara(codigo: str) -> str:
    """Prefijo de un código porcentaje: «OP%N0001» → «OP», «%CI» → ''."""
    return re.split(r'[%&]', codigo, maxsplit=1)[0]


# ── Lectura ──────────────────────────────────────────────────────────────────

def _leer_bytes(ruta: str) -> tuple[bytes, str]:
    """Bytes del BC3 y su nombre. Acepta un .zip con un .bc3 dentro (así se
    distribuyen varias bases: BCCA2023_V02.zip): se lee en memoria el .bc3
    más grande, sin extraer nada al disco."""
    p = Path(ruta)
    if not p.is_file():
        raise FileNotFoundError(f"No existe: {ruta}")
    if zipfile.is_zipfile(p):
        with zipfile.ZipFile(p) as z:
            cands = [i for i in z.infolist()
                     if i.filename.lower().endswith('.bc3') and not i.is_dir()]
            if not cands:
                raise Bc3Error("El .zip no contiene ningún archivo .bc3.")
            info = max(cands, key=lambda i: i.file_size)
            if info.file_size > _MAX_BYTES_ZIP:
                raise Bc3Error("El .bc3 del .zip es demasiado grande.")
            return z.read(info), Path(info.filename).name
    return p.read_bytes(), p.name


def _decodificar(raw: bytes) -> tuple[str, str]:
    """Texto + codificación usada. Manda el JUEGO_CARACTERES del ~V (ANSI =
    cp1252; 850; 437). La spec dice que vacío es 850, pero en la práctica
    los programas de Windows escriben ANSI sin declararlo: si el campo está
    vacío se elige entre cp1252 y cp850 por cuál produce más letras
    españolas. Un archivo que es UTF-8 válido con caracteres no ASCII se lee
    como UTF-8 aunque diga ANSI (un cp1252 con tildes casi nunca lo es)."""
    juego = ''
    m = re.search(rb'~V\|([^~]*)', raw[:4096])
    if m:
        campos = m.group(1).split(b'|')
        if len(campos) > 4:
            juego = campos[4].strip().decode('ascii', 'ignore').upper()
    try:
        txt = raw.decode('utf-8')
        if any(ord(ch) > 127 for ch in txt[:200000]):
            return txt, 'utf-8'
    except UnicodeDecodeError:
        pass
    if juego in ('850', '437'):
        enc = 'cp' + juego
    elif juego == 'ANSI':
        enc = 'cp1252'
    else:
        muestra = raw[:500000]
        esp = 'áéíóúñÑÁÉÍÓÚüº'
        puntos = {e: sum(muestra.decode(e, 'replace').count(c) for c in esp)
                  for e in ('cp1252', 'cp850')}
        enc = max(puntos, key=puntos.get)
    return raw.decode(enc, 'replace'), enc


# Un registro empieza en «~» seguido de la letra de cabecera y «|».
_RE_REGISTRO = re.compile(r'~(?=[A-Z]\s*\|)')


def _campos(cuerpo: str) -> list[str]:
    """Campos de un registro. La spec ignora blancos y fines de línea DELANTE
    de los separadores, que es lo que deja un registro partido en varias
    líneas (~D largos de Presto, ~M con muchas líneas de medición)."""
    return [c.rstrip(' \t\r\n') for c in cuerpo.split('|')]


def _sub(campo: str) -> list[str]:
    return [s.strip(' \t\r\n') for s in campo.split('\\')]


def leer_bc3(ruta: str) -> dict:
    """Lee el archivo y devuelve su modelo en memoria:

    ``{'nombre_archivo', 'codificacion', 'version', 'programa', 'divisa',
       'k': {'ci','gg','bi','baja','iva'}, 'conceptos': {cod: {...}},
       'descomp': {cod: [(hijo, factor, rend, [cods_pct])...]},
       'textos': {cod: str}, 'mediciones': [ {...} ], 'raiz': cod|None,
       'capitulos': set}``

    Los registros se aplican en orden (la spec garantiza lectura secuencial:
    un ~C posterior del mismo código reemplaza al anterior, ~Y añade líneas
    a la descomposición y ~N añade mediciones).
    """
    raw, nombre = _leer_bytes(ruta)
    txt, enc = _decodificar(raw)
    txt = txt.replace('\x1a', '')       # fin de archivo MS-DOS
    if '~C|' not in txt and not re.search(r'~C\s*\|', txt):
        raise Bc3Error("El archivo no parece un BC3: no tiene conceptos (~C).")

    bc3 = {
        'nombre_archivo': nombre, 'codificacion': enc, 'version': '',
        'programa': '', 'divisa': '', 'tipo_info': '',
        'k': {'ci': 0.0, 'gg': 0.0, 'bi': 0.0, 'baja': 0.0, 'iva': 0.0},
        'conceptos': {}, 'descomp': {}, 'textos': {}, 'mediciones': [],
        'raiz': None, 'capitulos': set(), 'alias': {},
    }
    conceptos = bc3['conceptos']
    descomp = bc3['descomp']
    alias = bc3['alias']

    for reg in _RE_REGISTRO.split(txt)[1:]:
        letra = reg[:1]
        cuerpo = reg[reg.index('|') + 1:] if '|' in reg else ''
        if letra == 'T':
            # Texto libre: solo dos campos y el texto conserva sus saltos.
            cod, _, resto = cuerpo.partition('|')
            texto = resto.rsplit('|', 1)[0] if '|' in resto else resto
            texto = texto.replace('\r\n', '\n').replace('\r', '\n').strip()
            if texto:
                bc3['textos'][_cod(cod)] = texto
            continue
        f = _campos(cuerpo)
        if letra == 'V':
            v = _sub(f[1]) if len(f) > 1 else ['']
            bc3['version'] = v[0]
            bc3['programa'] = f[2].strip() if len(f) > 2 else ''
            bc3['tipo_info'] = f[6].strip() if len(f) > 6 else ''
        elif letra == 'K':
            # Campo 1 (compatibilidad) y campo 3 (el completo): la DIVISA es
            # el último subcampo no vacío de cualquiera de los dos.
            for idx in (2, 0):
                if len(f) > idx:
                    subs = [s for s in _sub(f[idx]) if s]
                    if subs and re.fullmatch(r'[A-Za-z]{3}', subs[-1]):
                        bc3['divisa'] = subs[-1].upper()
                        break
            if len(f) > 1:
                pct = _sub(f[1]) + [''] * 5
                for i, k in enumerate(('ci', 'gg', 'bi', 'baja', 'iva')):
                    bc3['k'][k] = _num(pct[i])
        elif letra == 'C':
            codigos = [c for c in _sub(f[0]) if c] if f else []
            if not codigos:
                continue
            cod_crudo = codigos[0]
            cod = _cod(cod_crudo)
            precios = _sub(f[3]) if len(f) > 3 else []
            fechas = _sub(f[4]) if len(f) > 4 else []
            tipo_txt = f[5].strip() if len(f) > 5 else ''
            try:
                tipo = int(tipo_txt) if tipo_txt else 0
            except ValueError:
                tipo = 0
            conceptos[cod] = {
                'codigo': cod,
                'unidad': f[1].strip() if len(f) > 1 else '',
                'resumen': (f[2].strip() if len(f) > 2 else '') or cod,
                'precio': _num(precios[0]) if precios and precios[0] else 0.0,
                'fecha': fechas[0] if fechas else '',
                'tipo': tipo,
            }
            if cod_crudo.endswith('##'):
                bc3['raiz'] = cod
                bc3['capitulos'].add(cod)
            elif cod_crudo.endswith('#'):
                bc3['capitulos'].add(cod)
            for sin in codigos[1:]:
                alias[_cod(sin)] = cod
        elif letra in ('D', 'Y'):
            if not f:
                continue
            padre = _cod(f[0])
            # El campo 3 (2012+) lleva además los CODIGO_PORCENTAJE de cada
            # línea; la spec pide leerlo «y en su defecto el campo 2».
            if len(f) > 2 and f[2].strip():
                subs, paso = _sub(f[2]), 4
            elif len(f) > 1:
                subs, paso = _sub(f[1]), 3
            else:
                continue
            lineas = []
            for i in range(0, len(subs) - 1, paso):
                hijo = _cod(subs[i])
                if not hijo:
                    continue
                fac = _num(subs[i + 1], 1.0) if i + 1 < len(subs) and subs[i + 1] else 1.0
                ren = _num(subs[i + 2], 1.0) if i + 2 < len(subs) and subs[i + 2] else 1.0
                pcts = []
                if paso == 4 and i + 3 < len(subs) and subs[i + 3]:
                    pcts = [_cod(x) for x in subs[i + 3].split(';') if x.strip()]
                lineas.append((hijo, fac, ren, pcts))
            if letra == 'D':
                descomp[padre] = lineas
            else:
                descomp.setdefault(padre, []).extend(lineas)
        elif letra in ('M', 'N'):
            if not f:
                continue
            ruta_m = _sub(f[0])
            if len(ruta_m) >= 2:
                padre, hijo = _cod(ruta_m[0]), _cod(ruta_m[1])
            else:
                padre, hijo = '', _cod(ruta_m[0])
            pos = []
            if len(f) > 1:
                for s in _sub(f[1]):
                    if s:
                        try:
                            pos.append(int(float(s)))
                        except ValueError:
                            pass
            lineas = []
            if len(f) > 3:
                subs = _sub(f[3])
                for i in range(0, len(subs) - 5, 6):
                    lineas.append(subs[i:i + 6])
            med = {'padre': padre, 'hijo': hijo, 'pos': tuple(pos),
                   'total': _num(f[2]) if len(f) > 2 and f[2].strip() else None,
                   'lineas': lineas,
                   'etiqueta': f[4].strip() if len(f) > 4 else ''}
            if letra == 'N':
                previa = next((m for m in bc3['mediciones']
                               if m['padre'] == padre and m['hijo'] == hijo
                               and m['pos'] == med['pos']), None)
                if previa:
                    previa['lineas'].extend(lineas)
                    continue
            bc3['mediciones'].append(med)
        # ~L ~Q ~J (pliegos), ~G (gráficos), ~E (entidades), ~O (relación
        # comercial), ~X (información técnica), ~R (residuos), ~A, ~B, ~F,
        # ~P, ~W, ~I: no tienen dónde ir en la app y se ignoran.

    # Sinónimos: una referencia a un código secundario apunta al principal.
    if alias:
        for padre, lineas in descomp.items():
            descomp[padre] = [(alias.get(h, h), fa, re_, p)
                              for h, fa, re_, p in lineas]
    return bc3


# ── Detección ────────────────────────────────────────────────────────────────

def detectar_bc3(ruta: str) -> dict:
    """¿Presupuesto o base de precios? Regla: si trae registros ~M es un
    presupuesto (la spec los exige en el intercambio de presupuestos «exista
    o no desglose de mediciones»); si no, es una base. El ~V TIPO
    INFORMACIÓN no sirve: Presto lo exporta como «2 = Presupuesto» también
    en las bases de precios de la Junta de Andalucía."""
    bc3 = leer_bc3(ruta)
    return _resumen_deteccion(bc3)


def _resumen_deteccion(bc3: dict) -> dict:
    caps = bc3['capitulos']
    n_desc = sum(1 for c in bc3['descomp'] if c not in caps)
    n_med = len(bc3['mediciones'])
    raiz = bc3['raiz']
    nombre = (bc3['conceptos'].get(raiz, {}).get('resumen') if raiz else '') \
        or Path(bc3['nombre_archivo']).stem
    if nombre.isdigit() and raiz:
        nombre = raiz       # la PemA 2025 resume su raíz «pemA_2025» como «2025»
    return {
        'tipo': 'presupuesto' if n_med else 'base',
        'n_conceptos': len(bc3['conceptos']),
        'n_descompuestos': n_desc,
        'n_capitulos': len(caps),
        'n_mediciones': n_med,
        'raiz': raiz,
        'nombre': nombre,
        'divisa': bc3['divisa'],
        'programa': bc3['programa'],
        'codificacion': bc3['codificacion'],
    }


# ── Cálculo de precios y líneas de ACU ───────────────────────────────────────

class _Calculo:
    """Precios de los descompuestos y sus líneas de ACU en el modelo de la app.

    Memoriza el precio de cada descompuesto (las bases traen miles y los
    auxiliares se repiten en cientos de partidas) y corta ciclos A→B→A
    tratando la segunda visita como concepto simple (precio del ~C)."""

    def __init__(self, bc3: dict):
        self.bc3 = bc3
        self.c = bc3['conceptos']
        self.d = bc3['descomp']
        self.caps = bc3['capitulos']
        self._precio: dict[str, float] = {}
        self._pila: set[str] = set()
        div = bc3['divisa'] or 'EUR'
        self.unidad_dinero = _SIMBOLO_DIVISA.get(div, div)

    def es_descompuesto(self, cod: str) -> bool:
        return cod not in self.caps and bool(self.d.get(cod))

    def precio_archivo(self, cod: str) -> float:
        return float(self.c.get(cod, {}).get('precio') or 0)

    def precio_uso(self, cod: str) -> float:
        """Precio con el que un concepto entra en la línea de OTRO ACU. Para
        un descompuesto, el que da su descomposición (la spec: «tendrá
        preponderancia el resultado obtenido por la descomposición»)."""
        if self.es_descompuesto(cod):
            return self.precio_calculado(cod)
        return self.precio_archivo(cod)

    def importes(self, cod: str) -> list[tuple[str, float, float, bool]]:
        """Por cada línea del ~D: ``(hijo, cantidad, importe, es_pct)``.
        El importe de una línea normal es cantidad × precio redondeado a 2
        (DI del ~K); el de un porcentaje, su fracción × la suma de las líneas
        anteriores que cubre."""
        lineas = self.d.get(cod) or []
        explicitos = any(p for *_, p in lineas)
        out: list[tuple[str, float, float, bool]] = []
        for hijo, fac, ren, _p in lineas:
            cant = fac * ren
            if es_porcentaje(hijo):
                base = sum(out[i][2] for i in self._cubiertas(
                    hijo, lineas, out, explicitos))
                out.append((hijo, cant, _rn(base * cant, 2), True))
            else:
                out.append((hijo, cant, _rn(cant * self.precio_uso(hijo), 2), False))
        return out

    def _cubiertas(self, pct: str, lineas, previas, explicitos):
        """Índices de las líneas anteriores a las que se aplica el porcentaje
        `pct`: las que lo nombran en su CODIGO_PORCENTAJE si el ~D usa esa
        lista, si no las que empiezan por su máscara («incluso porcentajes»,
        dice la spec)."""
        if explicitos:
            return [i for i in range(len(previas)) if pct in lineas[i][3]]
        mask = _mascara(pct)
        return [i for i, x in enumerate(previas) if x[0].startswith(mask)]

    def precio_calculado(self, cod: str) -> float:
        if cod in self._precio:
            return self._precio[cod]
        if cod in self._pila:                       # ciclo: cortar
            return self.precio_archivo(cod)
        self._pila.add(cod)
        try:
            p = _rn(sum(imp for *_x, imp, _e in self.importes(cod)), 2)
        finally:
            self._pila.discard(cod)
        self._precio[cod] = p
        return p

    def tipo_de(self, cod: str) -> str:
        """Tipo de la app de un concepto que entra como línea de ACU."""
        t = _TIPO_BC3.get(int(self.c.get(cod, {}).get('tipo') or 0))
        if t:
            return t
        return 'SC' if self.es_descompuesto(cod) else 'MAT'

    def items_acu(self, cod: str) -> list[dict]:
        """Líneas del ACU de un descompuesto en el formato de los importadores
        (`codigo` BC3, `descripcion`, `tipo`, `unidad`, `precio`,
        `cantidad`, `cuadrilla`). El `codigo` es el BC3: quien guarda le
        asigna el de la app."""
        lineas = self.d.get(cod) or []
        imps = self.importes(cod)
        tipos = [None if e else self.tipo_de(h) for h, _c, _i, e in imps]
        explicitos = any(p for *_, p in lineas)
        items = []
        for k, (hijo, cant, imp, es_pct) in enumerate(imps):
            con = self.c.get(hijo, {})
            desc = con.get('resumen') or hijo
            if not es_pct:
                items.append({
                    'codigo_bc3': hijo, 'descripcion': desc,
                    'tipo': tipos[k], 'unidad': _unidad_insumo(con.get('unidad')),
                    'precio': _rn(self.precio_uso(hijo), 4) if self.es_descompuesto(hijo)
                              else self.precio_archivo(hijo),
                    'cantidad': cant, 'cuadrilla': 0.0,
                })
                continue
            # Porcentaje: ¿su base es exactamente un subtotal de tipo?
            idx_cub = set(self._cubiertas(hijo, lineas, imps[:k], explicitos))
            tipos_cub = {tipos[i] for i in idx_cub}
            unidad_app = None
            if (len(tipos_cub) == 1 and None not in tipos_cub
                    and tipos_cub <= {'MO', 'MAT', 'EQ'}):
                t = next(iter(tipos_cub))
                todos_t = {i for i in range(len(imps)) if tipos[i] == t}
                if todos_t == idx_cub:
                    unidad_app = {'MO': '%mo', 'MAT': '%mt', 'EQ': '%eq'}[t]
            if unidad_app:
                items.append({
                    'codigo_bc3': hijo, 'descripcion': desc, 'tipo': 'EQ',
                    'unidad': unidad_app, 'precio': 0.0,
                    'cantidad': cant * 100, 'cuadrilla': 0.0,
                })
            else:
                t = _TIPO_BC3.get(int(con.get('tipo') or 0)) or 'SC'
                items.append({
                    'codigo_bc3': hijo, 'descripcion': desc, 'tipo': t,
                    'unidad': self.unidad_dinero, 'precio': 1.0,
                    'cantidad': imp, 'cuadrilla': 0.0, 'congelado': True,
                })
        # Un porcentaje mapeado suma su parcial al subtotal de SU tipo en
        # `get_acu_items` (EQ, como las herramientas %MO de S10), pero no en
        # `_pu_desde_items`. Si en el mismo ACU hay un `%eq`, ese EQ extra
        # le cambiaría la base según quién calcule: en ese caso los
        # mapeados van a SC, que no es base de ninguna unidad porcentaje.
        if any(it['unidad'] == '%eq' for it in items):
            for it in items:
                if it['unidad'] in ('%mo', '%mt', '%eq'):
                    it['tipo'] = 'SC'
        return items


def _unidad_insumo(unidad: str | None) -> str:
    """Unidad de un insumo NORMAL tal como se guarda. Una que empiece por
    «%» la app la toma por porcentaje del ACU (`_pu_desde_items`), y las
    bases traen insumos corrientes medidos en «%» con precio propio (BCCA
    2023: «% Perfilería complementaria», 29.45 € el «%», 0.03 por m2): sin
    esto ese insumo se calculaba como 0.03 % de la mano de obra."""
    u = (unidad or '').strip() or 'ud'
    return f"ud ({u})" if u.startswith('%') else u


def _texto_specs(bc3: dict, cod: str) -> str:
    """Especificaciones de un CU/partida: el código BC3 (para poder buscarlo
    en la base de origen) y el texto largo ~T."""
    txt = bc3['textos'].get(cod, '')
    cab = f"Código BC3: {cod}"
    return f"{cab}\n\n{txt}" if txt else cab


def _fecha_iso(f: str) -> str:
    """DDMMAAAA / DDMMAA del BC3 → ISO. Criterio 80/20 de la spec para dos
    cifras de año. Lo que no se entienda, vacío."""
    f = (f or '').strip()
    if not f.isdigit():
        return ''
    if len(f) % 2:
        f = '0' + f
    try:
        if len(f) == 8:
            d, m, a = int(f[:2]), int(f[2:4]), int(f[4:])
        elif len(f) == 6:
            d, m, a = int(f[:2]), int(f[2:4]), int(f[4:])
            a += 1900 if a >= 80 else 2000
        else:
            return ''
        if not (1 <= m <= 12):
            return ''
        return f"{a:04d}-{m:02d}-{max(d, 1):02d}"
    except ValueError:
        return ''


# ── Mediciones ───────────────────────────────────────────────────────────────

_FUNCIONES = {
    'ABS': abs, 'INT': lambda x: float(int(x)), 'SQRT': math.sqrt,
    'ROUND': lambda x, d=0: _rn(x, int(d)),
    'SIN': lambda x: math.sin(math.radians(x)),
    'COS': lambda x: math.cos(math.radians(x)),
    'TAN': lambda x: math.tan(math.radians(x)),
    'ASIN': lambda x: math.degrees(math.asin(x)),
    'ACOS': lambda x: math.degrees(math.acos(x)),
    'ATAN': lambda x: math.degrees(math.atan(x)),
    'ATAN2': lambda x, y: math.degrees(math.atan2(x, y)),
}
_RE_TOKEN = re.compile(r'\s*(?:(\d+(?:[.,]\d*)?|[.,]\d+)|([A-Za-z_]\w*)|(.))')


def evaluar_expresion(expr: str, variables: dict) -> float:
    """Evalúa una expresión de línea de medición (~M tipo 3): números,
    + - * / ^, paréntesis, las variables a b c d (unidades, longitud,
    latitud, altura), la constante p (pi) y las funciones del Anexo 2.
    Analizador propio de descenso recursivo: el texto viene del archivo y
    NO se pasa nunca a `eval`. Lanza ValueError si no la entiende."""
    toks = []
    for num, nom, op in _RE_TOKEN.findall(expr):
        if num:
            toks.append(('n', float(num.replace(',', '.'))))
        elif nom:
            toks.append(('id', nom))
        elif op.strip():
            toks.append(('op', op))
    pos = 0

    def ver():
        return toks[pos] if pos < len(toks) else ('fin', None)

    def tomar():
        nonlocal pos
        t = ver()
        pos += 1
        return t

    def suma():
        v = producto()
        while ver() in (('op', '+'), ('op', '-')):
            op = tomar()[1]
            v = v + producto() if op == '+' else v - producto()
        return v

    def producto():
        v = potencia()
        while ver() in (('op', '*'), ('op', '/')):
            op = tomar()[1]
            w = potencia()
            v = v * w if op == '*' else v / w
        return v

    def potencia():
        v = unario()
        if ver() == ('op', '^'):
            tomar()
            v = v ** potencia()
        return v

    def unario():
        if ver() == ('op', '-'):
            tomar()
            return -unario()
        if ver() == ('op', '+'):
            tomar()
            return unario()
        return atomo()

    def atomo():
        t = tomar()
        if t[0] == 'n':
            return t[1]
        if t == ('op', '('):
            v = suma()
            if tomar() != ('op', ')'):
                raise ValueError("falta ')'")
            return v
        if t[0] == 'id':
            nom = t[1]
            if nom.upper() in _FUNCIONES and ver() == ('op', '('):
                tomar()
                args = [suma()]
                while ver() in (('op', ','), ('op', ';')):
                    tomar()
                    args.append(suma())
                if tomar() != ('op', ')'):
                    raise ValueError("falta ')'")
                return float(_FUNCIONES[nom.upper()](*args))
            if nom.lower() == 'p':
                return math.pi
            if nom.lower() in variables:
                return float(variables[nom.lower()] or 0)
        raise ValueError(f"no se entiende {t[1]!r}")

    v = suma()
    if pos != len(toks):
        raise ValueError("sobra texto")
    return v


def filas_medicion(lineas: list[list[str]]) -> list[dict]:
    """Líneas de un ~M → filas de `metrados_detalle`.

    - Línea normal: comentario + N (unidades) / L / A / H; parcial = producto
      de las magnitudes presentes. Van a n_elementos / largo / ancho / alto.
    - Tipo 3 (expresión): la expresión es el comentario y vale «hasta la
      siguiente línea en la que se defina otra». Su resultado se guarda en
      n_elementos (así, si el usuario retoca la fila, la app vuelve a
      multiplicar y obtiene lo mismo) y la descripción conserva la expresión
      y sus valores.
    - Tipos 1/2 (subtotales): fila solo con texto y parcial vacío; no suman.

    Cada parcial se redondea a 2 decimales ANTES de sumar (DSP del ~K, por
    defecto 2): es lo que hace Presto y sin eso 8 de las 159 mediciones de
    CENZANO no daban su total (0.715 + 0.52 = 1.235 frente a 1.24).
    """
    filas = []
    expr = None
    for ln in lineas:
        ln = (ln + [''] * 6)[:6]
        tipo, com, *dims_txt = ln
        tipo = tipo.strip()
        dims = [_num(x) if x.strip() else None for x in dims_txt]
        if tipo in ('1', '2'):
            filas.append({'descripcion': com or 'Subtotal', 'parcial': None})
            continue
        if tipo == '3':
            expr = com
        if expr is not None and tipo == '3':
            vars_ = dict(zip('abcd', [x or 0 for x in dims]))
            try:
                val = evaluar_expresion(expr, vars_)
            except (ValueError, ZeroDivisionError, OverflowError):
                val = 0.0
            vals = ' '.join(f"{k}={_fmt(v)}" for k, v in zip('abcd', dims)
                            if v is not None)
            filas.append({'descripcion': f"{expr}  ({vals})" if vals else expr,
                          'n_elementos': _rn(val, 4), 'parcial': _rn(val, _DSP)})
            continue
        presentes = [x for x in dims if x is not None]
        if not presentes:
            filas.append({'descripcion': com, 'parcial': None})
            continue
        parcial = 1.0
        for x in presentes:
            parcial *= x
        filas.append({'descripcion': com, 'n_elementos': dims[0],
                      'largo': dims[1], 'ancho': dims[2], 'alto': dims[3],
                      'parcial': _rn(parcial, _DSP)})
    return filas


def _fmt(v: float) -> str:
    return f"{v:g}"


# ── Presupuesto → proyecto ───────────────────────────────────────────────────

def import_bc3_presupuesto(ruta: str, bc3: dict | None = None):
    """Devuelve ``(info, partidas, acus, recursos, metrados)`` como los demás
    importadores, listo para `importer.guardar_importacion`.

    Recorre el árbol desde la raíz (##) —o desde los capítulos que nadie
    contiene si no hay raíz—: capítulo → título, cualquier otro concepto →
    partida. El metrado es el rendimiento × factor de la línea del ~D del
    capítulo (la spec: el MEDICION_TOTAL del ~M «debe coincidir» con él);
    las líneas del ~M van a la hoja de metrados solo si su suma da ese
    mismo metrado, porque `guardar_importacion` reescribe el metrado con la
    suma de la planilla y un desglose que no cuadra movería el total.

    Un capítulo con rendimiento 0 en el ~D de su padre NO se importa:
    Presto lo usa para dejar fuera del total un capítulo informativo
    (CENZANO trae así su «ESTUDIO COSTES INDIRECTOS»: sumarlo inflaría el
    presupuesto un 10 %). Se avisa en ``info['bc3_avisos']``.
    """
    bc3 = bc3 or leer_bc3(ruta)
    calc = _Calculo(bc3)
    c, d, caps = bc3['conceptos'], bc3['descomp'], bc3['capitulos']
    raiz = bc3['raiz']
    avisos: list[str] = []

    if raiz:
        tops = [(h, fa, re_) for h, fa, re_, _p in d.get(raiz, [])]
    else:
        hijos = {h for ls in d.values() for h, *_ in ls}
        tops = [(k, 1.0, 1.0) for k in c if k in caps and k not in hijos]

    # Mediciones por (padre, hijo) y por ruta de posiciones
    med_pos: dict = {}
    med_ph: dict = {}
    for m in bc3['mediciones']:
        med_pos[(m['padre'], m['hijo'], m['pos'])] = m
        med_ph.setdefault((m['padre'], m['hijo']), []).append(m)

    def medicion(padre, hijo, ruta_pos):
        m = med_pos.get((padre, hijo, ruta_pos))
        if m:
            return m
        lst = med_ph.get((padre, hijo)) or []
        if len(lst) == 1:
            return lst[0]
        for x in lst:
            if x['pos'] and x['pos'][-1] == ruta_pos[-1]:
                return x
        return None

    partidas, acus, metrados = [], {}, {}
    recursos_uniq: dict[str, dict] = {}
    specs: dict[str, str] = {}
    n_med_ok = n_med_desc = 0

    def emitir(cod, padre, fac, ren, prefijo, indice, nivel, ruta_pos, pila):
        nonlocal n_med_ok, n_med_desc
        con = c.get(cod, {'resumen': cod, 'unidad': '', 'precio': 0, 'tipo': 0})
        item = (prefijo + '.' if prefijo else '') + f"{indice:02d}"
        if cod in caps:
            partidas.append({
                'item': item, 'descripcion': con['resumen'], 'unidad': '',
                'metrado': 0, 'precio_unitario': 0,
                'nivel': min(nivel, _NIVEL_MAX), 'es_titulo': 1,
            })
            if cod in pila:
                return
            k = 0
            for j, (h, fa, re_, _p) in enumerate(d.get(cod, []), 1):
                if h in caps and re_ == 0:
                    avisos.append(f"Capítulo «{c.get(h, {}).get('resumen', h)}» "
                                  "con rendimiento 0: fuera del total, no se importa.")
                    continue
                k += 1
                emitir(h, cod, fa, re_, item, k, nivel + 1, ruta_pos + (j,),
                       pila | {cod})
            return

        metrado = fac * ren
        if calc.es_descompuesto(cod):
            items = calc.items_acu(cod)
            pu = calc.precio_calculado(cod)
        else:
            # Partida sin descomposición (precio alzado, un material puesto
            # tal cual): un ACU de una línea con el propio concepto, para que
            # el PU de la app salga del ACU como en todas las demás.
            items = [{'codigo_bc3': cod, 'descripcion': con['resumen'],
                      'tipo': _TIPO_BC3.get(int(con.get('tipo') or 0), 'SC'),
                      'unidad': _unidad_insumo(con.get('unidad')),
                      'precio': calc.precio_archivo(cod),
                      'cantidad': 1.0, 'cuadrilla': 0.0}]
            pu = calc.precio_archivo(cod)
        partidas.append({
            'item': item, 'descripcion': con['resumen'],
            'unidad': con.get('unidad') or '', 'metrado': metrado,
            'precio_unitario': pu, 'nivel': min(nivel, _NIVEL_MAX),
            'es_titulo': 0, 'codigo_bc3': cod,
        })
        acus[item] = {'rendimiento': 0.0, 'items': items}
        specs[item] = _texto_specs(bc3, cod)
        for it in items:
            recursos_uniq.setdefault(_clave_recurso(it), it)
        m = medicion(padre, cod, ruta_pos)
        if m and m['lineas']:
            filas = filas_medicion(m['lineas'])
            suma = sum(f.get('parcial') or 0 for f in filas)
            if filas and abs(_rn(suma, 2) - _rn(metrado, 2)) <= 0.005:
                metrados[item] = filas
                n_med_ok += 1
            else:
                n_med_desc += 1

    k = 0
    for j, (h, fa, re_) in enumerate(tops, 1):
        if raiz and h in caps and re_ == 0:
            avisos.append(f"Capítulo «{c.get(h, {}).get('resumen', h)}» con "
                          "rendimiento 0: fuera del total, no se importa.")
            continue
        k += 1
        emitir(h, raiz or '', fa, re_, '', k, 1, (j,), frozenset())

    if n_med_desc:
        avisos.append(f"{n_med_desc} mediciones cuyo desglose no suma el "
                      "metrado del capítulo: se importó el metrado sin desglose.")

    # Igual que PowerCost: si el PU del ACU según la app difiere en céntimos
    # (redondeos) y el impacto en el total es despreciable, se adopta el de
    # la app para que el presupuesto quede autoconsistente.
    from core.database import _pu_desde_items
    for p in partidas:
        if p['es_titulo']:
            continue
        cu_app = _pu_desde_items(acus[p['item']]['items'])
        dif = abs(cu_app - p['precio_unitario'])
        if dif <= 0.0205 and dif * abs(p['metrado']) <= 1.0:
            p['precio_unitario'] = cu_app

    raiz_c = c.get(raiz, {}) if raiz else {}
    k_ = bc3['k']
    info = {
        'nombre': raiz_c.get('resumen') or Path(bc3['nombre_archivo']).stem,
        'cliente': '', 'ubicacion': '',
        'sub_presupuesto': '',
        'costo_al': _fecha_iso(raiz_c.get('fecha', '')),
        # Siempre explícitos (aunque sean 0): sin ellos la app aplicaría sus
        # 10/5/18 por defecto. El pie se crea INACTIVO: el precio de la raíz
        # del BC3 es el de ejecución material, y así el total de la app es
        # el mismo número; GG/BI/IVA del ~K quedan cargados para activarlos.
        'gf_pct': k_['gg'], 'utilidad_pct': k_['bi'], 'igv_pct': k_['iva'],
        'pie_activo_default': False,
        'moneda': _DIVISAS.get(bc3['divisa'] or ''),
        'bc3_especificaciones': specs,
        'bc3_avisos': avisos,
        'bc3_precio_raiz': float(raiz_c.get('precio') or 0) if raiz else None,
        'bc3_metrados_desglosados': n_med_ok,
    }
    recursos = list(recursos_uniq.values())
    _asignar_codigos(recursos, [it for a in acus.values() for it in a['items']])
    return info, partidas, acus, recursos, (metrados or None)


def _clave_recurso(it: dict) -> tuple:
    return (it['tipo'], (it['descripcion'] or '').strip().upper(),
            (it['unidad'] or '').strip())


def _asignar_codigos(recursos: list[dict], items: list[dict]) -> None:
    """Código de 7 dígitos de la app para cada insumo: prefijo de su tipo +
    correlativo libre en la BD. Si el insumo ya existe en el catálogo (mismo
    tipo, descripción y unidad) se le da SU código, que es lo que
    `_resolve_recurso` reutilizará. Mismo `(tipo, desc, unidad)` ⇒ mismo
    código en recursos e ítems de ACU."""
    from core.database import get_db
    conn = get_db()
    try:
        existentes = {}
        for r in conn.execute("SELECT codigo, tipo, descripcion, unidad FROM recursos"):
            k = (r['tipo'], (r['descripcion'] or '').strip().upper(),
                 (r['unidad'] or '').strip())
            existentes.setdefault(k, r['codigo'])
        sig = {}
        for pre in _PREFIJO_TIPO.values():
            mx = conn.execute(
                "SELECT MAX(CAST(SUBSTR(codigo,3) AS INTEGER)) FROM recursos "
                "WHERE SUBSTR(codigo,1,2)=? AND LENGTH(codigo)=7", (pre,)
            ).fetchone()[0]
            sig[pre] = (mx or 0) + 1
    finally:
        conn.close()
    asignado: dict[tuple, str] = {}
    for it in list(recursos) + list(items):
        k = _clave_recurso(it)
        if k not in asignado:
            if k in existentes:
                asignado[k] = existentes[k]
            else:
                pre = _PREFIJO_TIPO.get(it['tipo'], '02')
                asignado[k] = f"{pre}{sig[pre]:05d}"
                sig[pre] += 1
        it['codigo'] = asignado[k]


def guardar_presupuesto_bc3(ruta: str) -> tuple[int, str, dict]:
    """Importa un presupuesto BC3 como proyecto. Devuelve
    ``(pid, resumen, info)``.

    Guarda por `guardar_importacion` (numeración, sub-presupuestos,
    normalización de precios y enriquecimiento de la biblioteca, igual que
    cualquier importador) y después completa lo que ese camino no lleva:
    las especificaciones (~T) de cada partida, la moneda (~K DIVISA) y el
    índice INEI vacío en los insumos nuevos (un insumo español no tiene
    índice unificado; `_resolve_recurso` le pondría los dos primeros
    dígitos del código, que aquí son el tipo)."""
    from core import importer
    from core.database import get_db
    info, partidas, acus, recursos, metrados = import_bc3_presupuesto(ruta)
    if not [p for p in partidas if not p['es_titulo']]:
        raise Bc3Error("El BC3 no contiene partidas.")
    conn = get_db()
    max_rec = conn.execute("SELECT COALESCE(MAX(id),0) FROM recursos").fetchone()[0]
    conn.close()
    pid = importer.guardar_importacion(info, partidas, acus, recursos, metrados)
    conn = get_db()
    try:
        conn.executemany(
            "UPDATE partidas SET especificaciones=? WHERE proyecto_id=? AND item=?",
            [(txt, pid, item) for item, txt in info['bc3_especificaciones'].items()])
        if info.get('moneda'):
            conn.execute("UPDATE proyectos SET moneda=? WHERE id=?",
                         (info['moneda'], pid))
        codigos = {r['codigo'] for r in recursos}
        conn.executemany(
            "UPDATE recursos SET indice_inei='' WHERE id>? AND codigo=?",
            [(max_rec, cod) for cod in codigos])
        conn.commit()
    finally:
        conn.close()
    n_part = sum(1 for p in partidas if not p['es_titulo'])
    partes = [f"{n_part} partidas", f"{len(acus)} ACUs",
              f"{len(recursos)} insumos"]
    if metrados:
        partes.append(f"{len(metrados)} partidas con mediciones")
    resumen = "  ·  ".join(partes)
    if info['bc3_avisos']:
        resumen += "\n\n" + "\n".join(info['bc3_avisos'][:8])
    return pid, resumen, info


# ── Base de precios → biblioteca ─────────────────────────────────────────────

def _grupos_cu(bc3: dict) -> dict[str, str]:
    """Capítulo con el que se agrupa cada descompuesto en la biblioteca.

    Se toma el capítulo de PRIMER nivel útil que lo contiene: el hijo de la
    raíz (o el capítulo superior si no hay raíz). Si ese nivel es un mero
    contenedor de capítulos («Precios Unitarios» / «Precios Auxiliares» de la
    BCCA de Andalucía, «Precios descompuestos» de Presto), se baja uno más.
    Un descompuesto que no cuelga de ningún capítulo queda sin capítulo."""
    c, d, caps = bc3['conceptos'], bc3['descomp'], bc3['capitulos']
    raiz = bc3['raiz']
    if raiz:
        tops = [h for h, *_ in d.get(raiz, []) if h in caps]
    else:
        hijos = {h for ls in d.values() for h, *_ in ls}
        tops = [k for k in c if k in caps and k not in hijos]

    def solo_capitulos(cap):
        hs = [h for h, *_ in d.get(cap, [])]
        return bool(hs) and all(h in caps for h in hs)

    nivel1 = []
    for t in tops:
        if solo_capitulos(t) and len(tops) <= 4:
            nivel1.extend(h for h, *_ in d.get(t, []))
        else:
            nivel1.append(t)

    grupo: dict[str, str] = {}
    for top in nivel1:
        nombre = c.get(top, {}).get('resumen') or top
        pila, vistos = [top], set()
        while pila:
            x = pila.pop()
            if x in vistos:
                continue
            vistos.add(x)
            for h, *_ in d.get(x, []):
                if h in caps:
                    pila.append(h)
                else:
                    grupo.setdefault(h, nombre)
    return grupo


def import_biblioteca_bc3(ruta: str, modo: str = 'merge',
                          nombre_base: str | None = None,
                          progreso=None) -> dict:
    """Importa una base de precios BC3 a la Biblioteca de CU.

    Cada concepto DESCOMPUESTO (con ~D y que no es capítulo) es un CU; sus
    líneas, ítems de ACU con los insumos del catálogo (creados si faltan,
    reutilizados por tipo + descripción + unidad como en
    `importer._resolve_recurso`). Los auxiliares entran como CU propio Y
    aplanados dentro de los CU que los usan.

    Grupo del CU = «<base> · <capítulo>» (ver `_grupos_cu`); la base es el
    código de la raíz o el nombre del archivo. ``modo`` como Delphin:
    'merge' reemplaza un CU con la misma (descripción, unidad, grupo) que ya
    estuviera en la biblioteca; 'solo_nuevos' lo deja; 'duplicar' no
    deduplica. Dentro de una MISMA base dos conceptos con igual resumen y
    unidad entran los dos (son variantes con otro código; pisar uno con
    otro perdería precios).

    Rendimiento: lectura del catálogo en memoria y escritura con
    `executemany` en una sola transacción — una base de 27 000 conceptos
    no puede hacer un SELECT por insumo.
    """
    def _avisar(msg):
        if progreso:
            progreso(msg)

    _avisar("Leyendo el archivo BC3…")
    bc3 = leer_bc3(ruta)
    calc = _Calculo(bc3)
    c, caps = bc3['conceptos'], bc3['capitulos']
    raiz = bc3['raiz']
    # Nombre corto de la base: el CÓDIGO de la raíz («BCCA_2023_v02»), que
    # identifica base y versión; su resumen («BANCO DE COSTE DE LA
    # CONSTRUCCIÓN DE ANDALUCÍA») no cabe delante de cada capítulo en el
    # desplegable de grupos. Sin raíz, el nombre del archivo.
    base = (nombre_base or raiz or Path(bc3['nombre_archivo']).stem).strip()
    grupos = _grupos_cu(bc3)
    cus = [k for k in bc3['descomp'] if calc.es_descompuesto(k) and k in c]

    _avisar(f"Calculando {len(cus)} precios descompuestos…")
    lineas_cu = {k: calc.items_acu(k) for k in cus}

    from core.database import get_db, _pu_desde_items
    conn = get_db()
    n_creados = n_actualizados = n_ignorados = n_items = n_rec = 0
    n_cuadran = 0
    descuadres: list[tuple] = []
    try:
        # Catálogo actual en memoria
        rec_por_clave: dict[tuple, int] = {}
        for r in conn.execute("SELECT id, tipo, descripcion, unidad FROM recursos ORDER BY id"):
            k = (r['tipo'], (r['descripcion'] or '').strip().upper(),
                 (r['unidad'] or '').strip())
            rec_por_clave.setdefault(k, r['id'])
        sig = {}
        for pre in _PREFIJO_TIPO.values():
            mx = conn.execute(
                "SELECT MAX(CAST(SUBSTR(codigo,3) AS INTEGER)) FROM recursos "
                "WHERE SUBSTR(codigo,1,2)=? AND LENGTH(codigo)=7", (pre,)
            ).fetchone()[0]
            sig[pre] = (mx or 0) + 1
        # Por clave, la COLA de CU que ya existen: una base con dos conceptos
        # de igual resumen y unidad crea dos CU, y al reimportarla cada uno
        # debe pisar al suyo (con un solo id por clave el segundo se
        # duplicaba en cada reimportación).
        cu_existentes: dict[tuple, list[int]] = {}
        if modo in ('merge', 'solo_nuevos'):
            for r in conn.execute("SELECT id, descripcion, unidad, grupo "
                                  "FROM biblioteca_cu ORDER BY id"):
                cu_existentes.setdefault(
                    (r['descripcion'], r['unidad'], r['grupo']), []).append(r['id'])

        def recurso_id(it) -> int:
            nonlocal n_rec
            k = _clave_recurso(it)
            rid = rec_por_clave.get(k)
            if rid:
                return rid
            pre = _PREFIJO_TIPO.get(it['tipo'], '02')
            cod = f"{pre}{sig[pre]:05d}"
            sig[pre] += 1
            # Precio de catálogo: el del archivo (en un congelado, 1).
            cur = conn.execute(
                "INSERT INTO recursos (codigo, descripcion, tipo, unidad, precio, "
                "indice_inei) VALUES (?,?,?,?,?,'')",
                (cod, it['descripcion'], it['tipo'], it['unidad'], it['precio']))
            rec_por_clave[k] = cur.lastrowid
            n_rec += 1
            return cur.lastrowid

        _avisar("Guardando en la biblioteca…")
        filas_items = []
        for cod in cus:
            con = c[cod]
            desc = con['resumen'].strip()
            und = (con.get('unidad') or '').strip()
            cap = grupos.get(cod)
            grupo = f"{base} · {cap}" if cap else base
            items = lineas_cu[cod]
            # Costo del CU = el que da su ACU en la app, no el del ~C: así la
            # lista de la biblioteca y el proyecto que lo use muestran el
            # mismo número. Es además lo que manda la spec («tendrá
            # preponderancia el resultado obtenido por la descomposición»).
            # Lo que no coincide con el ~C se cuenta en `descuadres`.
            costo = _pu_desde_items(items)
            precio_arch = calc.precio_archivo(cod)
            specs = _texto_specs(bc3, cod)
            cola = cu_existentes.get((desc, und, grupo))
            existente = cola.pop(0) if cola else None
            if existente and modo == 'solo_nuevos':
                n_ignorados += 1
                continue
            if existente and modo == 'merge':
                cu_id = existente
                conn.execute(
                    "UPDATE biblioteca_cu SET rendimiento=0, costo_unitario=?, "
                    "especificaciones=? WHERE id=?", (costo, specs, cu_id))
                conn.execute("DELETE FROM biblioteca_acu_items WHERE cu_id=?", (cu_id,))
                n_actualizados += 1
            else:
                cur = conn.execute(
                    "INSERT INTO biblioteca_cu (descripcion, unidad, rendimiento, "
                    "costo_unitario, grupo, especificaciones, usos) "
                    "VALUES (?,?,0,?,?,?,0)", (desc, und, costo, grupo, specs))
                cu_id = cur.lastrowid
                n_creados += 1
            for it in items:
                filas_items.append((cu_id, recurso_id(it), 0.0,
                                    it['cantidad'], it['precio']))
            n_items += len(items)
            if abs(costo - precio_arch) <= 0.0105:
                n_cuadran += 1
            else:
                descuadres.append((cod, precio_arch, costo))
        conn.executemany(
            "INSERT INTO biblioteca_acu_items (cu_id, recurso_id, cuadrilla, "
            "cantidad, precio) VALUES (?,?,?,?,?)", filas_items)
        conn.commit()
    finally:
        conn.close()

    simples = sum(1 for k in c if k not in caps and not calc.es_descompuesto(k)
                  and not es_porcentaje(k))
    return {
        'ok': True,
        'msg': f"Base de precios «{base}» importada.",
        'base': base,
        'n_conceptos': len(c),
        'n_simples': simples,
        'n_acs_origen': len(cus),
        'n_creados': n_creados,
        'n_actualizados': n_actualizados,
        'n_ignorados': n_ignorados,
        'n_items': n_items,
        'n_recursos_creados': n_rec,
        'n_cuadran': n_cuadran,
        'descuadres': descuadres,
    }


def resumen_biblioteca(r: dict) -> str:
    """Texto para el usuario del resultado de `import_biblioteca_bc3` (lo
    usan la pantalla de importar y la Biblioteca CU)."""
    lineas = [
        r['msg'], '',
        f"  Precios descompuestos:  {r['n_acs_origen']}",
        f"  CU nuevos:              {r['n_creados']}",
        f"  CU actualizados:        {r['n_actualizados']}",
        f"  CU ignorados:           {r['n_ignorados']}",
        f"  Ítems de ACU:           {r['n_items']}",
        f"  Insumos nuevos:         {r['n_recursos_creados']}",
    ]
    n_desc = len(r['descuadres'])
    if n_desc:
        lineas += ['', f"{n_desc} de {r['n_acs_origen']} precios del archivo no "
                   "coinciden con su propia descomposición: se usó la "
                   "descomposición, como indica el formato FIEBDC."]
    return '\n'.join(lineas)
