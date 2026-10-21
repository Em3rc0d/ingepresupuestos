#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari
# This file is part of IngePresupuestos — https://ingepresupuestos.com
# Software libre bajo la GNU GPL v3 o posterior. Ver el archivo LICENSE.
"""Lista las cadenas de `tr()` que faltan (o sobran) en cada JSON de idioma.

Lee por AST todo el código de la interfaz (views/ widgets/ utils/ core/
main.py), junta los literales pasados a `tr()` y a `N_()` —o a su alias, si
el archivo hace `from utils.i18n import tr as _x`— y los compara con
`resources/i18n/<código>.json`.

    python3 scripts/i18n_faltantes.py               # resumen de todos los idiomas
    python3 scripts/i18n_faltantes.py pt_BR         # lista lo que falta en pt_BR
    python3 scripts/i18n_faltantes.py pt_BR --plantilla faltan.json
                                                     # {texto: ""} para traducir
    python3 scripts/i18n_faltantes.py --por-archivo  # llamadas a tr() por archivo

Avisa también de las llamadas a `tr()` con un argumento que no es un literal
(variable, f-string): esas no se pueden traducir — la clave tiene que ser el
texto fijo, con marcadores `{n}` y `.format(n=…)` después.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CARPETAS = ("views", "widgets", "utils", "core")
ARCHIVOS_SUELTOS = ("main.py",)
DIR_I18N = RAIZ / "resources" / "i18n"


def archivos_fuente() -> list[Path]:
    out: list[Path] = []
    for c in CARPETAS:
        out.extend(sorted((RAIZ / c).rglob("*.py")))
    for a in ARCHIVOS_SUELTOS:
        p = RAIZ / a
        if p.exists():
            out.append(p)
    return out


def _alias_tr(arbol: ast.AST) -> set[str]:
    """Nombres con los que el archivo llama a utils.i18n.tr (y al marcador N_)."""
    nombres: set[str] = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.ImportFrom) and n.module == "utils.i18n":
            for a in n.names:
                if a.name in ("tr", "N_"):
                    nombres.add(a.asname or a.name)
    return nombres


def cadenas_de(path: Path) -> tuple[list[tuple[str, int]], list[int]]:
    """(literales [(texto, línea)], líneas con argumento no literal)."""
    src = path.read_text(encoding="utf-8")
    arbol = ast.parse(src, filename=str(path))
    alias = _alias_tr(arbol)
    if not alias:
        return [], []
    literales: list[tuple[str, int]] = []
    dinamicas: list[int] = []
    for n in ast.walk(arbol):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id in alias and n.args):
            a = n.args[0]
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                literales.append((a.value, n.lineno))
            else:
                dinamicas.append(n.lineno)
    return literales, dinamicas


def recolectar() -> tuple[dict[str, list[str]], dict[str, list[int]], dict[str, int]]:
    """{texto: [archivo:línea…]}, {archivo: [líneas dinámicas]}, {archivo: n_llamadas}."""
    usos: dict[str, list[str]] = {}
    dinamicas: dict[str, list[int]] = {}
    por_archivo: dict[str, int] = {}
    for p in archivos_fuente():
        rel = str(p.relative_to(RAIZ))
        lits, dins = cadenas_de(p)
        if lits:
            por_archivo[rel] = len(lits)
        for texto, linea in lits:
            usos.setdefault(texto, []).append(f"{rel}:{linea}")
        if dins:
            dinamicas[rel] = dins
    return usos, dinamicas, por_archivo


def idiomas() -> list[str]:
    return sorted(p.stem for p in DIR_I18N.glob("*.json"))


def catalogo(codigo: str) -> dict[str, str]:
    with open(DIR_I18N / f"{codigo}.json", encoding="utf-8") as fh:
        return json.load(fh)


def faltantes(codigo: str, usos: dict[str, list[str]] | None = None) -> list[str]:
    if usos is None:
        usos = recolectar()[0]
    cat = catalogo(codigo)
    return sorted(t for t in usos if not cat.get(t))


def sobrantes(codigo: str, usos: dict[str, list[str]] | None = None) -> list[str]:
    if usos is None:
        usos = recolectar()[0]
    return sorted(t for t in catalogo(codigo) if t not in usos)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("idioma", nargs="?", help="código (en, pt_BR…); sin él, resumen")
    ap.add_argument("--plantilla", metavar="ARCHIVO",
                    help="escribe las faltantes como JSON {texto: ''}")
    ap.add_argument("--sobrantes", action="store_true",
                    help="lista también las claves del JSON que nadie usa")
    ap.add_argument("--por-archivo", action="store_true",
                    help="cuántos literales pasan por tr() en cada archivo")
    args = ap.parse_args()

    usos, dinamicas, por_archivo = recolectar()
    print(f"{len(usos)} cadenas distintas en {sum(por_archivo.values())} "
          f"llamadas a tr() ({len(por_archivo)} archivos)")

    if args.por_archivo:
        for rel, n in sorted(por_archivo.items(), key=lambda kv: -kv[1]):
            print(f"  {n:5d}  {rel}")

    if dinamicas:
        print("\nLlamadas a tr() con argumento NO literal (no se pueden traducir):")
        for rel, lineas in dinamicas.items():
            print(f"  {rel}: líneas {', '.join(map(str, lineas))}")

    codigos = [args.idioma] if args.idioma else idiomas()
    for cod in codigos:
        falt = faltantes(cod, usos)
        sobr = sobrantes(cod, usos)
        print(f"\n[{cod}] faltan {len(falt)} · sobran {len(sobr)}")
        if args.idioma:
            for t in falt:
                print(f"  FALTA  {t!r}  ({usos[t][0]})")
        if args.sobrantes or args.idioma:
            for t in sobr:
                print(f"  SOBRA  {t!r}")
        if args.plantilla:
            with open(args.plantilla, "w", encoding="utf-8") as fh:
                json.dump({t: "" for t in falt}, fh, ensure_ascii=False, indent=1)
            print(f"  plantilla → {args.plantilla}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
