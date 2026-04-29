from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pairnut.database.connection import get_data_dir, get_db_path, get_images_dir
from pairnut.database.schema import init_database
from pairnut.database import repositories


class SchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["PAIRNUT_DATA_DIR"] = self.tempdir.name
        init_database()

    def tearDown(self) -> None:
        os.environ.pop("PAIRNUT_DATA_DIR", None)
        self.tempdir.cleanup()

    def test_init_database_creates_sqlite_file(self) -> None:
        self.assertTrue(get_db_path().exists())

    def test_default_data_dir_uses_user_documents(self) -> None:
        os.environ.pop("PAIRNUT_DATA_DIR", None)
        home_dir = self.tempdir.name
        original_home = os.environ.get("HOME")
        os.environ["HOME"] = home_dir
        shutil.rmtree(os.path.join(home_dir, "PairNut"), ignore_errors=True)

        try:
            self.assertEqual(get_db_path(), Path(home_dir) / "Documents" / "PairNut" / "pairnut.db")
        finally:
            if original_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = original_home
            os.environ["PAIRNUT_DATA_DIR"] = self.tempdir.name

    def test_legacy_project_database_is_copied_to_user_data_dir_once(self) -> None:
        os.environ.pop("PAIRNUT_DATA_DIR", None)
        legacy_root = Path(self.tempdir.name) / "legacy"
        target_root = Path(self.tempdir.name) / "target"
        legacy_root.mkdir()
        (legacy_root / "pairnut.db").write_text("legacy db", encoding="utf-8")

        with (
            patch("pairnut.database.connection._default_user_data_dir", return_value=target_root),
            patch("pairnut.database.connection._legacy_project_data_dir", return_value=legacy_root),
        ):
            self.assertEqual(get_data_dir(), target_root)
            self.assertEqual((target_root / "pairnut.db").read_text(encoding="utf-8"), "legacy db")

            (legacy_root / "pairnut.db").write_text("changed legacy db", encoding="utf-8")
            self.assertEqual(get_data_dir(), target_root)
            self.assertEqual((target_root / "pairnut.db").read_text(encoding="utf-8"), "legacy db")

        os.environ["PAIRNUT_DATA_DIR"] = self.tempdir.name

    def test_images_dir_lives_under_data_dir(self) -> None:
        self.assertEqual(get_images_dir(), Path(self.tempdir.name) / "images")
        self.assertTrue(get_images_dir().exists())

    def test_variety_unique_constraints(self) -> None:
        repositories.create_variety("狮子头", "SZT", 1.0)
        with self.assertRaises(Exception):
            repositories.create_variety("狮子头", "SZT2", 1.0)
        with self.assertRaises(Exception):
            repositories.create_variety("官帽", "SZT", 1.0)
