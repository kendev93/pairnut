from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pairnut.database.connection import get_db_path, get_images_dir
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

    def test_development_data_dir_uses_project_data_directory(self) -> None:
        os.environ.pop("PAIRNUT_DATA_DIR", None)

        with patch.object(sys, "frozen", False, create=True):
            self.assertEqual(get_db_path(), Path(__file__).resolve().parents[1] / "data" / "pairnut.db")

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
                Path(home_dir) / "Library" / "Application Support" / "PairNut" / "pairnut.db",
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

    def test_variety_unique_constraints(self) -> None:
        repositories.create_variety("狮子头", "SZT", 1.0)
        with self.assertRaises(Exception):
            repositories.create_variety("狮子头", "SZT2", 1.0)
        with self.assertRaises(Exception):
            repositories.create_variety("官帽", "SZT", 1.0)
