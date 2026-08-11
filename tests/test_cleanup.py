from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from pairnut.database import repositories
from pairnut.database.connection import get_data_dir, get_images_dir, get_meshes_dir
from pairnut.database.schema import init_database
from pairnut.services.data_cleanup import (
    _stage_assets,
    delete_variety_data,
    delete_walnut_data,
    recover_stale_staging,
)


class DataCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["PAIRNUT_DATA_DIR"] = self.tempdir.name
        init_database()
        self.variety_id = repositories.create_variety("南疆石", "NJS", 1.0)
        self.walnut_id = self._create_walnut("NJS-01")

    def tearDown(self) -> None:
        os.environ.pop("PAIRNUT_DATA_DIR", None)
        self.tempdir.cleanup()

    def _create_walnut(self, serial_no: str) -> int:
        return repositories.create_walnut(
            {
                "variety_id": self.variety_id,
                "serial_mode": "manual",
                "serial_no": serial_no,
                "edge_mm": 40.0,
                "belly_mm": 40.0,
                "height_mm": 40.0,
                "weight_g": 30.0,
                "defect_level": "none",
                "notes": None,
            }
        )

    def test_delete_walnut_removes_database_records_and_asset_files(self) -> None:
        image_path = get_images_dir() / f"{self.walnut_id}-NJS-01" / "1.jpg"
        mesh_path = get_meshes_dir() / f"{self.walnut_id}-NJS-01" / "source.obj"
        image_path.parent.mkdir(parents=True)
        mesh_path.parent.mkdir(parents=True)
        image_path.write_bytes(b"image")
        mesh_path.write_text("mesh", encoding="utf-8")
        repositories.upsert_walnut_image(self.walnut_id, 1, "NJS-01-1.jpg", f"{self.walnut_id}-NJS-01/1.jpg")
        repositories.upsert_walnut_mesh(self.walnut_id, "source.obj", f"{self.walnut_id}-NJS-01/source.obj")

        self.assertTrue(delete_walnut_data(self.walnut_id))

        self.assertIsNone(repositories.get_walnut(self.walnut_id))
        self.assertFalse(image_path.exists())
        self.assertFalse(mesh_path.exists())

    def test_delete_variety_removes_all_asset_files(self) -> None:
        second_id = self._create_walnut("NJS-02")
        image_path = get_images_dir() / f"{second_id}-NJS-02" / "1.jpg"
        mesh_path = get_meshes_dir() / f"{second_id}-NJS-02" / "source.obj"
        image_path.parent.mkdir(parents=True)
        mesh_path.parent.mkdir(parents=True)
        image_path.write_bytes(b"image")
        mesh_path.write_text("mesh", encoding="utf-8")
        repositories.upsert_walnut_image(second_id, 1, "NJS-02-1.jpg", f"{second_id}-NJS-02/1.jpg")
        repositories.upsert_walnut_mesh(second_id, "source.obj", f"{second_id}-NJS-02/source.obj")

        self.assertTrue(delete_variety_data(self.variety_id))

        self.assertEqual(repositories.list_walnuts(), [])
        self.assertFalse(image_path.exists())
        self.assertFalse(mesh_path.exists())

    def test_delete_locked_walnut_is_rejected_without_orphaning_partner_lock(self) -> None:
        partner_id = self._create_walnut("NJS-02")
        pair_id = repositories.lock_pair(self.variety_id, self.walnut_id, partner_id)

        with self.assertRaises(ValueError):
            delete_walnut_data(self.walnut_id)

        self.assertIsNotNone(repositories.get_walnut(self.walnut_id))
        self.assertEqual(repositories.get_active_lock_for_walnut(partner_id)["id"], pair_id)
        self.assertEqual(repositories.get_walnut(partner_id)["is_locked"], 1)

    def test_delete_variety_with_locked_pair_is_rejected(self) -> None:
        partner_id = self._create_walnut("NJS-02")
        repositories.lock_pair(self.variety_id, self.walnut_id, partner_id)

        with self.assertRaises(ValueError):
            delete_variety_data(self.variety_id)

        self.assertIsNotNone(repositories.get_walnut(self.walnut_id))
        self.assertIsNotNone(repositories.get_walnut(partner_id))
        self.assertEqual(len(repositories.list_locked_pairs(self.variety_id)), 1)

    def test_asset_move_failure_keeps_walnut_and_asset(self) -> None:
        image_path = get_images_dir() / f"{self.walnut_id}-NJS-01" / "1.jpg"
        image_path.parent.mkdir(parents=True)
        image_path.write_bytes(b"image")
        repositories.upsert_walnut_image(self.walnut_id, 1, "NJS-01-1.jpg", f"{self.walnut_id}-NJS-01/1.jpg")

        with patch("pairnut.services.data_cleanup.shutil.move", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                delete_walnut_data(self.walnut_id)

        self.assertIsNotNone(repositories.get_walnut(self.walnut_id))
        self.assertTrue(image_path.exists())

    def test_database_delete_failure_restores_staged_assets(self) -> None:
        image_path = get_images_dir() / f"{self.walnut_id}-NJS-01" / "1.jpg"
        image_path.parent.mkdir(parents=True)
        image_path.write_bytes(b"image")
        repositories.upsert_walnut_image(self.walnut_id, 1, "NJS-01-1.jpg", f"{self.walnut_id}-NJS-01/1.jpg")

        with patch.object(repositories, "delete_walnut", side_effect=RuntimeError("database unavailable")):
            with self.assertRaises(RuntimeError):
                delete_walnut_data(self.walnut_id)

        self.assertIsNotNone(repositories.get_walnut(self.walnut_id))
        self.assertTrue(image_path.exists())
        self.assertEqual(list(get_data_dir().glob(".pairnut-delete-*")), [])

    def test_stale_staging_manifest_restores_assets_after_restart(self) -> None:
        image_path = get_images_dir() / f"{self.walnut_id}-NJS-01" / "1.jpg"
        image_path.parent.mkdir(parents=True)
        image_path.write_bytes(b"image")
        repositories.upsert_walnut_image(self.walnut_id, 1, "NJS-01-1.jpg", f"{self.walnut_id}-NJS-01/1.jpg")

        staging_root, _ = _stage_assets([f"{self.walnut_id}-NJS-01/1.jpg"], [])
        self.assertFalse(image_path.exists())

        self.assertEqual(recover_stale_staging(), 1)
        self.assertTrue(image_path.exists())
        self.assertFalse(staging_root.exists())


if __name__ == "__main__":
    unittest.main()
