from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from pairnut.database import repositories
from pairnut.database.connection import db_connection, get_db_path
from pairnut.database.schema import CURRENT_SCHEMA_VERSION, init_database
from pairnut.services.image_features import OPENCV_FEATURE_VERSION


class WriteTransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["PAIRNUT_DATA_DIR"] = self.tempdir.name
        init_database()
        self.variety_id = repositories.create_variety("狮子头", "SZT", 1.0)
        self.w1 = self._create_walnut("SZT-0001")
        self.w2 = self._create_walnut("SZT-0002")

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
                "belly_mm": 42.0,
                "height_mm": 38.0,
                "weight_g": 52.0,
                "defect_level": "none",
                "notes": None,
            }
        )

    def _fast_connect(self):
        real_connect = sqlite3.connect

        def connect(path, **kwargs):
            return real_connect(path, timeout=0.2)

        return patch("pairnut.database.connection.sqlite3.connect", connect)

    def test_pair_write_fails_instead_of_waiting_on_another_writer(self) -> None:
        other = sqlite3.connect(get_db_path())
        other.execute("BEGIN IMMEDIATE")
        try:
            with self._fast_connect(), self.assertRaises(sqlite3.OperationalError):
                repositories.lock_pair(self.variety_id, self.w1, self.w2)
        finally:
            other.rollback()
            other.close()

        self.assertIsNone(repositories.get_active_lock_for_walnut(self.w1))

    def test_media_writes_are_rejected_for_locked_walnuts(self) -> None:
        repositories.lock_pair(self.variety_id, self.w1, self.w2)

        with self.assertRaises(ValueError):
            repositories.upsert_walnut_image_with_feature(
                walnut_id=self.w1,
                face_no=1,
                original_filename="w1-1.jpg",
                stored_path="w1/1.jpg",
                feature_version=OPENCV_FEATURE_VERSION,
                color_histogram="[1,0]",
                texture_vector="[1,0]",
                shape_vector="[1,0]",
            )
        with self.assertRaises(ValueError):
            repositories.upsert_walnut_mesh(self.w1, "w1.obj", "w1/source.obj")

    def test_edit_and_delete_stay_rejected_for_locked_walnuts(self) -> None:
        repositories.lock_pair(self.variety_id, self.w1, self.w2)

        with self.assertRaises(ValueError):
            repositories.update_walnut(
                self.w1,
                {
                    "serial_mode": "manual",
                    "serial_no": "SZT-UPDATED",
                    "edge_mm": 40.0,
                    "belly_mm": 42.0,
                    "height_mm": 38.0,
                    "weight_g": 52.0,
                    "defect_level": "none",
                    "notes": None,
                },
            )
        with self.assertRaises(ValueError):
            repositories.delete_walnut(self.w1)

        self.assertIsNotNone(repositories.get_walnut(self.w1))

    def test_lock_flag_drift_is_repaired_when_upgrading(self) -> None:
        repositories.lock_pair(self.variety_id, self.w1, self.w2)
        with db_connection() as conn:
            conn.execute("PRAGMA user_version = 1")
            conn.execute("UPDATE walnuts SET is_locked = 0")

        init_database()

        with db_connection() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            flags = {
                row["id"]: row["is_locked"]
                for row in conn.execute("SELECT id, is_locked FROM walnuts")
            }

        self.assertEqual(version, CURRENT_SCHEMA_VERSION)
        self.assertEqual(flags[self.w1], 1)
        self.assertEqual(flags[self.w2], 1)
