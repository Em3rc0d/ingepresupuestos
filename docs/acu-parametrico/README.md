# ACU paramétricos — prototipo aislado en el fork

**Estado:** SPIKE MK1 · 2026-10-23 · Código de investigación **NO integrado** en UI, persistencia, catálogo de insumos ni motor de precio. Propiedad: [Em3rc0d/ingepresupuestos](https://github.com/Em3rc0d/ingepresupuestos). Referencia de origen/atribución: [ingelibre/ingepresupuestos](https://github.com/ingelibre/ingepresupuestos), GPL-3.0-or-later. **No contactar al upstream** por decisión del propietario del fork.

## Qué se desarrolló

- `core/acu_parametrico.py`: función pura `evaluar_acu_parametrico(plantilla, parametros, unidad_partida)` con `Decimal` y resultados inmutables.
- `tests/test_acu_parametrico.py`: 17 escenarios para fórmulas sintéticas, tipo/unidad/precisión, determinismo y entradas inválidas.
- Plantillas explícitas `zapata_concreto_rectangular_v1` con `m3/und`, y `pintura_superficie_v1` con `L/m2`. No hay fórmulas ejecutadas desde JSON ni llamadas a red o IA.
- No se crea ni cambia un recurso, no se escribe en SQLite, no se calcula ningún precio unitario y no se modifica `core.database`.
- No se generan insumos estructurales o armado de acero; son **cantidades geométricas**, no diseño de obra.

## Verificar localmente

En el directorio raíz del fork (Python 3.11+):

```bash
python -m unittest discover -s tests -p "test_acu_parametrico.py" -v
```

Resultado ejecutado en entorno aislado de ChatGPT: **17 tests, 0 failures, 0 errors, PASS**. Se recrearon localmente los dos archivos Python, y se comprobó que su **Git blob SHA** coincide con los dos archivos GitHub de esta rama:

| Ruta | Git blob SHA validado |
|---|---|
| `core/acu_parametrico.py` | `0e9eae4e3df9ced251c2f4ae673375a5e6f8ade6` |
| `tests/test_acu_parametrico.py` | `5a423a1295c4621c04251d03ea0fbb9ec911899c` |

Esto permite afirmar que los tests aislados se ejecutaron sobre el **mismo contenido de ambos archivos** que está en GitHub. **NO** se descargó/clonó el repositorio completo por fallo DNS, por lo que **NO** se ejecutó la suite original, ni se comprobó empacado Windows/Flatpak/PySide6, ni integración SQLite.

## Ejemplos sintéticos

```python
from core.acu_parametrico import evaluar_acu_parametrico

zapata = evaluar_acu_parametrico(
    "zapata_concreto_rectangular_v1",
    {"largo_m": "2", "ancho_m": "2", "alto_m": "0.5"}, "und")
assert str(zapata.cantidades[0].cantidad_por_unidad) in ("2.0", "2.000")

pintura = evaluar_acu_parametrico(
    "pintura_superficie_v1",
    {"manos": "2", "cobertura_m2_l_mano": "8",
     "consumo_adicional_fraccion": "0.10"}, "m2")
assert pintura.cantidades[0].cantidad_por_unidad == 0.275
```

El cálculo de pintura usa **10% de consumo adicional relativo al teórico**, no 10% del volumen comprado perdido (que llevaría a una fórmula distinta). El valor de cobertura **8 m²/L/mano es inventado para la prueba**, NO corresponde a una ficha técnica real. La cantidad por unidad ACU no debe confundirse con `metrado × cantidad por unidad` (consumo total de obra).

## Línea roja antes de producción

1. Ejecutar la **suite existente** del fork (`tests/test_reglas_negocio.py` y `tests/test_core.py`) en checkout completo y registrar baseline SHA+OS+dependencias.
2. Especificar/validar un contrato interno de selección de `recurso_id`, unidades, precios por proyecto, rendimientos de cuadrilla, permisos y estados de partida.
3. Validar con técnico de obra los ejemplos y fichas reales antes de ponerlos en reportes, órdenes de compra o costos profesionales.
4. Implementar en otra rama un **preview/diff sin escrituras**, luego adaptador transaccional con rollback/confirmación/repetición segura y pruebas, reutilizando `core.database._recalcular_pu`.
5. Integrar diálogo PySide6 y pruebas de regresión/end-to-end solo cuando G1-G4 estén cerrados. No fabricar números de ahorro de tiempo/ROI.
6. Mantener GPL, procedencia, copyright y avisos; revisar activos/terceros al distribuir. Sin firmar CLA externo si no hay PR upstream.

## Dónde está la investigación
[personal_knowledge / IngePresupuestos MK0/MK1](https://github.com/Em3rc0d/personal_knowledge/tree/main/research-corpora/software-reuse-2026-10-23/candidates/ingepresupuestos-parametric-acu)

**No representa release funcional de la aplicación ni un producto comercial aprobado.**
