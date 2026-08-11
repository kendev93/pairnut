from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pairnut.database import repositories
from pairnut.database.connection import (
    db_connection,
    get_db_path,
    get_images_dir,
    get_meshes_dir,
    get_models_dir,
)
from pairnut.database.schema import init_database


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

    def test_init_database_sets_schema_version(self) -> None:
        with db_connection() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]

        self.assertEqual(version, 1)

    def test_development_data_dir_uses_project_data_directory(self) -> None:
        os.environ.pop("PAIRNUT_DATA_DIR", None)

        with patch.object(sys, "frozen", False, create=True):
            self.assertEqual(
                get_db_path(),
                Path(__file__).resolve().parents[1] / "data" / "pairnut.db",
            )

        os.environ["PAIRNUT_DATA_DIR"] = self.tempdir.name

    def test_packaged_data_dir_uses_macos_application_support(self) -> None:
        os.environ.pop("PAIRNUT_DATA_DIR", None)
        home_dir = self.tempdir.name

        with (
            patch("pathlib.Path.home", return_value=Path(home_dir)),
            patch.object(sys, "platform", "darwin"),
            patch.object(sys, "frozen", True, create=True),
        ):
            self.assertEqual(
                get_db_path(),
                Path(home_dir)
                / "Library"
                / "Application Support"
                / "PairNut"
                / "pairnut.db",
            )

        os.environ["PAIRNUT_DATA_DIR"] = self.tempdir.name

    def test_packaged_data_dir_uses_windows_program_data(self) -> None:
        os.environ.pop("PAIRNUT_DATA_DIR", None)
        program_data = Path(self.tempdir.name) / "ProgramData"

        with (
            patch.dict(os.environ, {"PROGRAMDATA": str(program_data)}, clear=False),
            patch.object(sys, "platform", "win32"),
            patch.object(sys, "frozen", True, create=True),
        ):
            self.assertEqual(get_db_path(), program_data / "PairNut" / "pairnut.db")

        os.environ["PAIRNUT_DATA_DIR"] = self.tempdir.name

    def test_images_dir_lives_under_data_dir(self) -> None:
        self.assertEqual(get_images_dir(), Path(self.tempdir.name) / "images")
        self.assertTrue(get_images_dir().exists())

    def test_models_dir_lives_under_data_dir(self) -> None:
        self.assertEqual(get_models_dir(), Path(self.tempdir.name) / "models")
        self.assertTrue(get_models_dir().exists())

    def test_meshes_dir_lives_under_data_dir(self) -> None:
        self.assertEqual(get_meshes_dir(), Path(self.tempdir.name) / "meshes")
        self.assertTrue(get_meshes_dir().exists())

    def test_variety_unique_constraints(self) -> None:
        repositories.create_variety("狮子头", "SZT", 1.0)
        with self.assertRaises(sqlite3.IntegrityError):
            repositories.create_variety("狮子头", "SZT2", 1.0)
        with self.assertRaises(sqlite3.IntegrityError):
            repositories.create_variety("官帽", "SZT", 1.0)

    def test_variety_input_is_validated(self) -> None:
        with self.assertRaises(ValueError):
            repositories.create_variety("", "SZT", 1.0)
        with self.assertRaises(ValueError):
            repositories.create_variety("狮子头", "", 1.0)
        with self.assertRaises(ValueError):
            repositories.create_variety("狮子头", "SZ T", 1.0)
        with self.assertRaises(ValueError):
            repositories.create_variety("狮子头", "SZT", 0.0)

    def test_walnut_input_is_validated(self) -> None:
        variety_id = repositories.create_variety("狮子头", "SZT", 1.0)
        data = {
            "variety_id": variety_id,
            "serial_mode": "manual",
            "serial_no": "SZT-0001",
            "edge_mm": 40.0,
            "belly_mm": 42.0,
            "height_mm": 38.0,
            "weight_g": 52.0,
            "defect_level": "none",
            "notes": None,
        }

        for field in ("edge_mm", "belly_mm", "height_mm", "weight_g"):
            invalid = {**data, field: 0.0}
            with self.subTest(field=field), self.assertRaises(ValueError):
                repositories.create_walnut(invalid)

        with self.assertRaises(ValueError):
            repositories.create_walnut({**data, "serial_no": "   "})
        with self.assertRaises(ValueError):
            repositories.create_walnut({**data, "serial_mode": "invalid"})
        with self.assertRaises(ValueError):
            repositories.create_walnut({**data, "defect_level": "invalid"})
