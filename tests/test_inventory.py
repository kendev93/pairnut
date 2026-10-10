from __future__ import annotations

import os
import tempfile
import unittest

from pairnut.database import repositories
from pairnut.database.schema import init_database
from pairnut.services.inventory import (
    find_variety_id,
    load_dashboard_counts,
    load_walnut_rows,
)


class InventoryTests(unittest.TestCase):
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

    def test_walnut_rows_include_assets_and_labels(self) -> None:
        repositories.upsert_walnut_image(self.w1, 1, "w1-1.jpg", "w1/1.jpg")
        repositories.upsert_walnut_mesh(self.w1, "w1.obj", "w1/source.obj")

        rows = load_walnut_rows(self.variety_id)

        first = next(row for row in rows if row.id == self.w1)
        second = next(row for row in rows if row.id == self.w2)
        self.assertEqual(first.image_count_label, "1 / 6")
        self.assertEqual(first.mesh_label, "已导入")
        self.assertEqual(first.lock_label, "未锁定")
        self.assertEqual(second.image_count_label, "0 / 6")
        self.assertEqual(second.mesh_label, "未导入")
        self.assertIsNone(second.mesh)

    def test_walnut_rows_report_locked_state_from_active_locks(self) -> None:
        repositories.lock_pair(self.variety_id, self.w1, self.w2)

        rows = load_walnut_rows(self.variety_id)

        self.assertTrue(all(row.lock_label == "已锁定" for row in rows))

    def test_walnut_rows_are_empty_without_a_variety(self) -> None:
        self.assertEqual(load_walnut_rows(None), [])

    def test_variety_is_resolved_by_name_and_prefix(self) -> None:
        self.assertEqual(find_variety_id("狮子头", "SZT"), self.variety_id)
        self.assertIsNone(find_variety_id("狮子头", "GM"))
        self.assertIsNone(find_variety_id("官帽", "SZT"))

    def test_dashboard_counts_reflect_walnuts_and_locks(self) -> None:
        repositories.lock_pair(self.variety_id, self.w1, self.w2)

        counts = load_dashboard_counts()

        self.assertEqual(counts.varieties, 1)
        self.assertEqual(counts.walnuts, 2)
        self.assertEqual(counts.locked_pairs, 1)
