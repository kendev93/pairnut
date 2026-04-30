from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pairnut.database import repositories
from pairnut.database.connection import get_images_dir
from pairnut.database.schema import init_database
from pairnut.domain.models import DefectLevel, SerialMode
from pairnut.services.images import delete_walnut_image, import_walnut_images, parse_image_filename


class ImageImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["PAIRNUT_DATA_DIR"] = self.tempdir.name
        init_database()
        self.variety_id = repositories.create_variety("南疆石", "NJS", 1.0)
        self.walnut_id = repositories.create_walnut(
            {
                "variety_id": self.variety_id,
                "serial_mode": SerialMode.MANUAL.value,
                "serial_no": "NJS-01",
                "edge_mm": 40,
                "belly_mm": 40,
                "height_mm": 40,
                "weight_g": 30,
                "defect_level": DefectLevel.NONE.value,
                "notes": None,
            }
        )

    def tearDown(self) -> None:
        os.environ.pop("PAIRNUT_DATA_DIR", None)
        self.tempdir.cleanup()

    def test_parse_image_filename_uses_last_separator_as_face_number(self) -> None:
        parsed = parse_image_filename("NJS-01-6.JPG")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.serial_no, "NJS-01")
        self.assertEqual(parsed.face_no, 6)

    def test_import_walnut_images_copies_files_and_records_face(self) -> None:
        source = Path(self.tempdir.name) / "NJS-01-1.JPG"
        source.write_text("image", encoding="utf-8")

        with patch("pairnut.services.images.store_opencv_features") as store_features:
            result = import_walnut_images([source], self.variety_id)

        self.assertEqual(result.imported_count, 1)
        self.assertEqual(result.replaced_count, 0)
        self.assertEqual(result.skipped, [])
        self.assertEqual(result.feature_failed, [])

        images = repositories.list_walnut_images(self.walnut_id)
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["face_no"], 1)
        self.assertEqual(images[0]["original_filename"], "NJS-01-1.JPG")
        self.assertEqual(images[0]["stored_path"], f"{self.walnut_id}-NJS-01/1.jpg")
        self.assertEqual((get_images_dir() / f"{self.walnut_id}-NJS-01" / "1.jpg").read_text(encoding="utf-8"), "image")
        store_features.assert_called_once()

    def test_import_walnut_images_replaces_existing_face(self) -> None:
        first = Path(self.tempdir.name) / "NJS-01-2.JPG"
        second = Path(self.tempdir.name) / "NJS-01-2.PNG"
        first.write_text("first", encoding="utf-8")
        second.write_text("second", encoding="utf-8")

        import_walnut_images([first], self.variety_id)
        result = import_walnut_images([second], self.variety_id)

        self.assertEqual(result.imported_count, 0)
        self.assertEqual(result.replaced_count, 1)
        images = repositories.list_walnut_images(self.walnut_id)
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["stored_path"], f"{self.walnut_id}-NJS-01/2.png")

    def test_import_walnut_images_skips_unknown_serial_and_bad_name(self) -> None:
        unknown = Path(self.tempdir.name) / "NJS-99-1.JPG"
        bad = Path(self.tempdir.name) / "NJS-01-front.JPG"
        unknown.write_text("image", encoding="utf-8")
        bad.write_text("image", encoding="utf-8")

        result = import_walnut_images([unknown, bad], self.variety_id)

        self.assertEqual(result.imported_count, 0)
        self.assertEqual(result.replaced_count, 0)
        self.assertEqual(len(result.skipped), 2)
        self.assertEqual(repositories.list_walnut_images(self.walnut_id), [])

    def test_delete_walnut_image_removes_file_and_database_record(self) -> None:
        source = Path(self.tempdir.name) / "NJS-01-3.JPG"
        source.write_text("image", encoding="utf-8")
        import_walnut_images([source], self.variety_id)

        self.assertTrue(delete_walnut_image(self.walnut_id, 3))

        self.assertEqual(repositories.list_walnut_images(self.walnut_id), [])
        self.assertFalse((get_images_dir() / f"{self.walnut_id}-NJS-01" / "3.jpg").exists())

    def test_delete_walnut_image_cleans_record_when_file_is_missing(self) -> None:
        source = Path(self.tempdir.name) / "NJS-01-4.JPG"
        source.write_text("image", encoding="utf-8")
        import_walnut_images([source], self.variety_id)
        stored_file = get_images_dir() / f"{self.walnut_id}-NJS-01" / "4.jpg"
        stored_file.unlink()

        self.assertTrue(delete_walnut_image(self.walnut_id, 4))

        self.assertEqual(repositories.list_walnut_images(self.walnut_id), [])
