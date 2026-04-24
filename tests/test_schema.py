from __future__ import annotations

import os
import tempfile
import unittest

from pairnut.database.connection import get_db_path
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

    def test_variety_unique_constraints(self) -> None:
        repositories.create_variety("狮子头", "SZT", 1.0)
        with self.assertRaises(Exception):
            repositories.create_variety("狮子头", "SZT2", 1.0)
        with self.assertRaises(Exception):
            repositories.create_variety("官帽", "SZT", 1.0)
