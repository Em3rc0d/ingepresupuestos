# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Contribuidores del fork Em3rc0d/ingepresupuestos
"""Prototipo aislado: cantidades por unidad de partida para ACU.

NO calcula precios, NO dimensiona estructuras, NO escribe en SQLite,
NO sustituye el motor de ACU existente. Las fórmulas son ejemplos
sintéticos hasta que un profesional valide sus supuestos.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping


class ErrorParametros(ValueError):
    """Parámetros, unidades o plantilla incompatibles."""


@dataclass(frozen=True)
class CantidadRecurso:
    rol_recurso: str
    unidad_recurso: str
    unidad_partida: str
    cantidad_por_unidad: Decimal
    explicacion: str


@dataclass(frozen=True)
class ResultadoACUParametrico:
    plantilla: str
    unidad_partida: str
    cantidades: tuple[CantidadRecurso, ...]
    advertencias: tuple[str, ...]


def _decimal(valor: object, nombre: str) -> Decimal:
    if isinstance(valor, bool):
        raise ErrorParametros(f"{nombre}: se esperaba un número, no booleano")
    try:
        numero = Decimal(str(valor))
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise ErrorParametros(f"{nombre}: número inválido") from exc
    if not numero.is_finite():
        raise ErrorParametros(f"{nombre}: no puede ser NaN ni infinito")
    return numero


def _positivo(valor: object, nombre: str) -> Decimal:
    n = _decimal(valor, nombre)
    if n <= 0:
        raise ErrorParametros(f"{nombre}: debe ser mayor que cero")
    return n


def _campos_exactos(parametros: Mapping[str, object],
                    esperados: frozenset[str]) -> None:
    if not isinstance(parametros, Mapping):
        raise ErrorParametros("Los parámetros deben ser un mapa")
    recibidos = set(parametros)
    faltantes = sorted(esperados - recibidos)
    sobrantes = sorted(recibidos - esperados)
    if faltantes or sobrantes:
        raise ErrorParametros(f"Campos faltantes={faltantes}; no admitidos={sobrantes}")


def evaluar_acu_parametrico(
    plantilla: str,
    parametros: Mapping[str, object],
    unidad_partida: str,
) -> ResultadoACUParametrico:
    """Devuelve cantidades físicas POR UNA unidad de partida, nunca precios.

    Entrada decimal sin redondear. El futuro adaptador deberá delegar
    el redondeo y el precio unitario a core.database, no implementarlos aquí.
    No interpretar estos resultados como diseño estructural o ficha técnica.
    """
    if plantilla == "zapata_concreto_rectangular_v1":
        _campos_exactos(parametros, frozenset({"largo_m", "ancho_m", "alto_m"}))
        if unidad_partida != "und":
            raise ErrorParametros("La zapata piloto necesita partida 'und'")
        largo = _positivo(parametros["largo_m"], "largo_m")
        ancho = _positivo(parametros["ancho_m"], "ancho_m")
        alto = _positivo(parametros["alto_m"], "alto_m")
        volumen = largo * ancho * alto
        return ResultadoACUParametrico(
            plantilla, "und",
            (CantidadRecurso("concreto", "m3", "und", volumen,
                             "largo_m × ancho_m × alto_m [m3/und]"),),
            ("Volumen geométrico bruto; no es diseño estructural ni dosificación "
             "de mezcla. No incluye acero, pérdidas ni otros insumos.",),
        )

    if plantilla == "pintura_superficie_v1":
        _campos_exactos(parametros, frozenset({
            "manos", "cobertura_m2_l_mano", "consumo_adicional_fraccion",
        }))
        if unidad_partida != "m2":
            raise ErrorParametros("La pintura piloto necesita partida 'm2'")
        manos = _positivo(parametros["manos"], "manos")
        if manos != manos.to_integral_value():
            raise ErrorParametros("manos: debe ser un entero positivo")
        cobertura = _positivo(parametros["cobertura_m2_l_mano"],
                              "cobertura_m2_l_mano")
        adicional = _decimal(parametros["consumo_adicional_fraccion"],
                            "consumo_adicional_fraccion")
        if adicional < 0 or adicional > 1:
            raise ErrorParametros("consumo_adicional_fraccion: rango permitido 0..1")
        cantidad = (manos / cobertura) * (Decimal(1) + adicional)
        return ResultadoACUParametrico(
            plantilla, "m2",
            (CantidadRecurso("pintura", "L", "m2", cantidad,
                             "(manos / cobertura_m2_l_mano) × "
                             "(1 + consumo_adicional_fraccion) [L/m2]"),),
            ("La cobertura es por mano, no por sistema completo. El extra es "
             "consumo adicional sobre el teórico, NO fracción comprada perdida. "
             "Exige ficha técnica y revisión del sustrato.",),
        )
    raise ErrorParametros(f"Plantilla no registrada: {plantilla!r}")
