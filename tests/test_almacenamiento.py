"""Pruebas básicas del disco temporal y la exportación por filas (sin GPU)."""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
import storage_config
from disk_output import DiskImage


class StorageTests(unittest.TestCase):
    def test_carpeta_externa_y_sesion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            external = root / "externo"
            external.mkdir()
            with patch.object(storage_config, "APP_DIR", root / "config"), \
                 patch.object(storage_config, "CONFIG_FILE", root / "config" / "config.json"):
                folder = storage_config.save_folder(external)
                self.assertEqual(folder, external / "Zompix_Temporales")
                session, warning = storage_config.create_session()
                self.assertEqual(session.parent.resolve(), folder.resolve())
                self.assertFalse(warning)
                status = storage_config.status(session)
                self.assertGreater(status["free_gb"], 0)
                shutil.rmtree(session)

    def test_unidad_desconectada_usa_local_con_aviso(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            external = root / "externo"
            external.mkdir()
            with patch.object(storage_config, "APP_DIR", root / "config"), \
                 patch.object(storage_config, "CONFIG_FILE", root / "config" / "config.json"):
                storage_config.save_folder(external)
                shutil.rmtree(external)
                session, warning = storage_config.create_session()
                try:
                    self.assertTrue(warning)
                    self.assertTrue(session.exists())
                finally:
                    shutil.rmtree(session)

    def test_png_sin_cargar_resultado_completo(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "salida.tmp"
            png = Path(tmp) / "salida.png"
            img = DiskImage(raw, 40, 30, 3)
            try:
                img.paste(Image.new("RGB", (20, 30), (255, 0, 0)), 0, 0)
                img.paste(Image.new("RGB", (20, 30), (0, 0, 255)), 20, 0)
                img.save(png)
            finally:
                img.close()
            self.assertFalse(raw.exists())
            with Image.open(png) as result:
                self.assertEqual(result.size, (40, 30))
                self.assertEqual(result.getpixel((5, 5)), (255, 0, 0))
                self.assertEqual(result.getpixel((35, 15)), (0, 0, 255))


if __name__ == "__main__":
    unittest.main()
