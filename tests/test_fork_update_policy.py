# SPDX-License-Identifier: GPL-3.0-or-later
"""El fork no debe consultar feeds ni publicar actualizaciones del autor original."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from core import update_manager as updates


class PoliticaActualizacionesFork(unittest.TestCase):
    def test_sin_url_no_hace_polling(self):
        with patch.object(updates, "VERSION_URL", ""):
            self.assertFalse(updates.actualizaciones_habilitadas())
            self.assertFalse(updates.debe_chequear_silencioso())
            with patch.object(updates, "fetch_version_info") as fetch:
                result = updates.chequear_actualizacion()
                fetch.assert_not_called()
                self.assertIsNone(result.info)
                self.assertFalse(result.es_nueva)
                self.assertFalse(result.error)

    def test_no_se_muestra_feed_cacheado_del_autor(self):
        with patch.object(updates, "VERSION_URL", ""):
            with patch.object(updates, "_cargar_state") as loader:
                self.assertIsNone(updates.cached_version_info())
                loader.assert_not_called()

    def test_url_insegura_no_activa_red(self):
        for url in ("http://example.com/feed.json", "ftp://example.com/feed.json",
                    "//example.com/feed.json", "https://user:secret@example.com/feed.json",
                    "https://", "file:///tmp/version.json"):
            with self.subTest(url=url), patch.object(updates, "VERSION_URL", url):
                self.assertFalse(updates.actualizaciones_habilitadas())
                self.assertFalse(updates.debe_chequear_silencioso())
                with patch.object(updates, "fetch_version_info") as fetch:
                    updates.chequear_actualizacion()
                    fetch.assert_not_called()

    def test_canal_https_propio_debe_ser_configurado_expresamente(self):
        with patch.object(updates, "VERSION_URL", "https://mi-dominio.ejemplo/version.json"):
            self.assertTrue(updates.actualizaciones_habilitadas())

    def test_canal_https_propio_puede_recibir_resultado_mock(self):
        inf = updates.VersionInfo("9.9.0", "2026-10-24", "Demo", "https://mi-dominio.ejemplo/download")
        with patch.object(updates, "VERSION_URL", "https://mi-dominio.ejemplo/version.json"):
            with patch.object(updates, "fetch_version_info", return_value=inf), patch.object(
                updates, "marcar_check"
            ) as save:
                r = updates.chequear_actualizacion()
                self.assertTrue(r.es_nueva)
                self.assertEqual(r.info.version, "9.9.0")
                save.assert_called_once_with(inf)


if __name__ == "__main__":
    unittest.main()
