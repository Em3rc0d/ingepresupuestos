# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Contribuidores del fork Em3rc0d/ingepresupuestos
"""Pruebas del spike de cantidades; no requiere PySide6 ni BD."""
from __future__ import annotations

import os
import sys
import unittest
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.acu_parametrico import ErrorParametros, evaluar_acu_parametrico


def pintura(**cambios):
    d = {"manos": "2", "cobertura_m2_l_mano": "8",
         "consumo_adicional_fraccion": "0.10"}
    d.update(cambios)
    return evaluar_acu_parametrico("pintura_superficie_v1", d, "m2")


def zapata(**cambios):
    d = {"largo_m": "2", "ancho_m": "2", "alto_m": "0.5"}
    d.update(cambios)
    return evaluar_acu_parametrico("zapata_concreto_rectangular_v1", d, "und")


class ACUParametricoSpikeTests(unittest.TestCase):
    def test_zapata_es_volumen_por_und(self):
        x = zapata()
        self.assertEqual(x.cantidades[0].cantidad_por_unidad, Decimal("2.0"))
        self.assertEqual((x.cantidades[0].unidad_recurso,
                          x.unidad_partida), ("m3", "und"))

    def test_metrado_no_se_confunde_con_cantidad_unitaria(self):
        self.assertEqual(zapata().cantidades[0].cantidad_por_unidad * 3,
                         Decimal("6.0"))

    def test_pintura_cantidad_por_m2(self):
        x = pintura()
        self.assertEqual(x.cantidades[0].cantidad_por_unidad, Decimal("0.275"))
        self.assertEqual((x.cantidades[0].unidad_recurso,
                          x.unidad_partida), ("L", "m2"))

    def test_pintura_sin_adicional(self):
        self.assertEqual(
            pintura(consumo_adicional_fraccion=0).cantidades[0].cantidad_por_unidad,
            Decimal("0.25"))

    def test_pintura_una_mano(self):
        x = pintura(manos=1, cobertura_m2_l_mano=10,
                    consumo_adicional_fraccion="0.05")
        self.assertEqual(x.cantidades[0].cantidad_por_unidad, Decimal("0.105"))

    def test_pintura_preserva_precision_no_redondea_dentro(self):
        x = pintura(cobertura_m2_l_mano=3, consumo_adicional_fraccion=0)
        self.assertGreater(len(str(x.cantidades[0].cantidad_por_unidad)), 10)

    def test_plantilla_no_registrada(self):
        with self.assertRaises(ErrorParametros):
            evaluar_acu_parametrico("codigo_python", {}, "m2")

    def test_unidad_incompatible(self):
        with self.assertRaises(ErrorParametros):
            evaluar_acu_parametrico("pintura_superficie_v1",
                                   {"manos": 2, "cobertura_m2_l_mano": 8,
                                    "consumo_adicional_fraccion": 0}, "und")

    def test_parametros_faltantes(self):
        with self.assertRaises(ErrorParametros):
            zapata(alto_m=None)

    def test_parametros_extras_rechazados(self):
        with self.assertRaises(ErrorParametros):
            zapata(cantidad_total=3)

    def test_cero_negativo_y_no_finito(self):
        for obj in [
            {"alto_m": 0}, {"largo_m": -1}, {"ancho_m": "NaN"},
            {"alto_m": "Infinity"}, {"largo_m": True},
        ]:
            with self.subTest(obj=obj), self.assertRaises(ErrorParametros):
                zapata(**obj)

    def test_manos_fraccionarias_rechazadas(self):
        with self.assertRaises(ErrorParametros):
            pintura(manos="1.5")

    def test_cobertura_no_positiva(self):
        with self.assertRaises(ErrorParametros):
            pintura(cobertura_m2_l_mano=0)

    def test_adicional_fuera_de_rango(self):
        for valor in ("-0.1", "1.1", "NaN"):
            with self.subTest(valor=valor), self.assertRaises(ErrorParametros):
                pintura(consumo_adicional_fraccion=valor)

    def test_booleano_no_es_una_dimension(self):
        with self.assertRaises(ErrorParametros):
            pintura(manos=True)

    def test_evaluacion_determinista(self):
        self.assertEqual(pintura(), pintura())
        self.assertEqual(zapata(), zapata())

    def test_resultado_no_contiene_precio_o_escritura(self):
        result = pintura()
        self.assertFalse(hasattr(result, "precio"))
        self.assertFalse(hasattr(result, "recurso_id"))
        self.assertFalse(hasattr(result, "conn"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
