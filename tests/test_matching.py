from __future__ import annotations

import os
import tempfile
import unittest

from pairnut.database import repositories
from pairnut.database.schema import init_database
from pairnut.services.matching import get_candidates_for_variety, get_candidates_for_walnut
from pairnut.services.mesh_features import MESH_FEATURE_VERSION


class MatchingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["PAIRNUT_DATA_DIR"] = self.tempdir.name
        init_database()
        self.variety_id = repositories.create_variety("狮子头", "SZT", 1.0)
        self.w1 = repositories.create_walnut(
            {
                "variety_id": self.variety_id,
                "serial_mode": "manual",
                "serial_no": "SZT-0001",
                "edge_mm": 40.0,
                "belly_mm": 42.0,
                "height_mm": 38.0,
                "weight_g": 52.0,
                "defect_level": "none",
                "notes": None,
            }
        )
        self.w2 = repositories.create_walnut(
            {
                "variety_id": self.variety_id,
                "serial_mode": "manual",
                "serial_no": "SZT-0002",
                "edge_mm": 40.2,
                "belly_mm": 42.1,
                "height_mm": 38.2,
                "weight_g": 52.2,
                "defect_level": "none",
                "notes": None,
            }
        )
        self.w3 = repositories.create_walnut(
            {
                "variety_id": self.variety_id,
                "serial_mode": "manual",
                "serial_no": "SZT-0003",
                "edge_mm": 40.3,
                "belly_mm": 42.4,
                "height_mm": 38.2,
                "weight_g": 53.5,
                "defect_level": "light",
                "notes": None,
            }
        )
        self.w4 = repositories.create_walnut(
            {
                "variety_id": self.variety_id,
                "serial_mode": "manual",
                "serial_no": "SZT-0004",
                "edge_mm": 40.4,
                "belly_mm": 42.2,
                "height_mm": 38.4,
                "weight_g": 52.4,
                "defect_level": "none",
                "notes": None,
            }
        )

    def tearDown(self) -> None:
        os.environ.pop("PAIRNUT_DATA_DIR", None)
        self.tempdir.cleanup()

    def test_candidates_are_limited_to_top_three(self) -> None:
        result = get_candidates_for_walnut(self.w1)
        self.assertLessEqual(len(result), 3)
        self.assertEqual(result[0].walnut_id, self.w2)

    def test_candidates_can_repeat_across_rows(self) -> None:
        result = get_candidates_for_variety(self.variety_id)
        candidate_ids_for_w1 = [item.walnut_id for item in result[self.w1]]
        candidate_ids_for_w4 = [item.walnut_id for item in result[self.w4]]
        self.assertIn(self.w2, candidate_ids_for_w1)
        self.assertIn(self.w2, candidate_ids_for_w4)

    def test_locked_walnuts_are_removed_from_future_candidates(self) -> None:
        repositories.lock_pair(self.variety_id, self.w1, self.w2)
        result = get_candidates_for_variety(self.variety_id)
        self.assertEqual(result[self.w1], [])
        for candidate in result[self.w3]:
            self.assertNotEqual(candidate.walnut_id, self.w2)

    def test_unlock_after_second_lock_same_pair(self) -> None:
        """Regression: old unique index on (pair, is_active) blocked a second unlock."""
        first = repositories.lock_pair(self.variety_id, self.w1, self.w2)
        repositories.unlock_pair(first)
        second = repositories.lock_pair(self.variety_id, self.w1, self.w2)
        repositories.unlock_pair(second)

    def test_blacklisted_pair_never_reappears(self) -> None:
        repositories.create_blacklist_pair(self.variety_id, self.w1, self.w2)
        result = get_candidates_for_walnut(self.w1)
        candidate_ids = [item.walnut_id for item in result]
        self.assertNotIn(self.w2, candidate_ids)

    def test_candidates_include_mesh_similarity_when_available(self) -> None:
        mesh_id_1 = repositories.upsert_walnut_mesh(self.w1, "w1.obj", "w1/source.obj")
        mesh_id_2 = repositories.upsert_walnut_mesh(self.w2, "w2.obj", "w2/source.obj")
        for mesh_id in (mesh_id_1, mesh_id_2):
            repositories.upsert_walnut_mesh_feature(
                mesh_id=mesh_id,
                feature_version=MESH_FEATURE_VERSION,
                dimensions_vector="[1,1,1]",
                shape_vector="[1,1,1,0.5,0.8,0.1,1,1]",
            )

        result = get_candidates_for_walnut(self.w1)
        candidate = next(item for item in result if item.walnut_id == self.w2)

        self.assertIsNotNone(candidate.mesh_similarity)
        assert candidate.mesh_similarity is not None
        self.assertGreater(candidate.mesh_similarity, 99.0)
        self.assertGreater(candidate.total_score, candidate.dimension_score)
