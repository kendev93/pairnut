from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from pairnut.database import repositories
from pairnut.database.schema import init_database
from pairnut.services.image_features import OPENCV_FEATURE_VERSION
from pairnut.services.matching import (
    _combine_optional_evidence,
    get_candidates_for_variety,
    get_candidates_for_walnut,
    get_matching_view_data,
    get_non_overlapping_pairs,
    lock_candidate_pair,
)
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

    def test_negative_limit_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            get_candidates_for_walnut(self.w1, limit=-1)

    def test_zero_limit_returns_no_candidates(self) -> None:
        self.assertEqual(get_candidates_for_walnut(self.w1, limit=0), [])

    def test_candidate_screening_allows_a_small_single_dimension_overrun(self) -> None:
        walnut_id = repositories.create_walnut(
            {
                "variety_id": self.variety_id,
                "serial_mode": "manual",
                "serial_no": "SZT-0005",
                "edge_mm": 41.1,
                "belly_mm": 42.0,
                "height_mm": 38.0,
                "weight_g": 52.0,
                "defect_level": "none",
                "notes": None,
            }
        )

        result = get_candidates_for_walnut(self.w1, limit=10)

        self.assertIn(walnut_id, [item.walnut_id for item in result])
        candidate = next(item for item in result if item.walnut_id == walnut_id)
        self.assertFalse(candidate.is_strict_match)

    def test_minimum_score_filters_weak_recommendations(self) -> None:
        self.assertEqual(get_candidates_for_walnut(self.w1, minimum_score=101.0), [])

    def test_matching_view_data_reuses_one_walnut_snapshot(self) -> None:
        with patch.object(repositories, "list_walnuts", wraps=repositories.list_walnuts) as list_walnuts:
            walnuts, candidates = get_matching_view_data(self.variety_id)

        self.assertEqual(len(walnuts), 4)
        self.assertIn(self.w1, candidates)
        self.assertEqual(list_walnuts.call_count, 1)

    def test_partial_optional_evidence_has_lower_influence_than_full_coverage(self) -> None:
        full_coverage = _combine_optional_evidence(80.0, [100.0], [1.0])
        partial_coverage = _combine_optional_evidence(80.0, [100.0], [1.0 / 6.0])

        self.assertGreater(full_coverage, partial_coverage)
        self.assertGreater(partial_coverage, 80.0)

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

    def test_blacklisted_pair_cannot_be_locked_and_can_be_removed(self) -> None:
        blacklist_id = repositories.create_blacklist_pair(self.variety_id, self.w1, self.w2, reason="人工排除")

        with self.assertRaises(ValueError):
            repositories.lock_pair(self.variety_id, self.w1, self.w2)

        self.assertTrue(repositories.delete_blacklist_pair(blacklist_id))
        repositories.lock_pair(self.variety_id, self.w1, self.w2)

    def test_locked_walnut_cannot_be_edited(self) -> None:
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

    def test_lock_candidate_pair_rejects_screening_only_candidate(self) -> None:
        walnut_id = repositories.create_walnut(
            {
                "variety_id": self.variety_id,
                "serial_mode": "manual",
                "serial_no": "SZT-0005",
                "edge_mm": 41.1,
                "belly_mm": 42.0,
                "height_mm": 38.0,
                "weight_g": 52.0,
                "defect_level": "none",
                "notes": None,
            }
        )

        with self.assertRaises(ValueError):
            lock_candidate_pair(self.variety_id, self.w1, walnut_id)

        with self.assertRaises(ValueError):
            repositories.lock_pair(self.variety_id, self.w1, walnut_id)

    def test_lock_pair_rejects_walnuts_from_different_varieties(self) -> None:
        other_variety_id = repositories.create_variety("官帽", "GM", 1.0)
        other_walnut_id = repositories.create_walnut(
            {
                "variety_id": other_variety_id,
                "serial_mode": "manual",
                "serial_no": "GM-0001",
                "edge_mm": 40.0,
                "belly_mm": 42.0,
                "height_mm": 38.0,
                "weight_g": 52.0,
                "defect_level": "none",
                "notes": None,
            }
        )

        with self.assertRaises(ValueError):
            repositories.lock_pair(self.variety_id, self.w1, other_walnut_id)

        self.assertIsNone(repositories.get_active_lock_for_walnut(self.w1))

    def test_blacklist_pair_rejects_walnuts_from_different_varieties(self) -> None:
        other_variety_id = repositories.create_variety("官帽", "GM", 1.0)
        other_walnut_id = repositories.create_walnut(
            {
                "variety_id": other_variety_id,
                "serial_mode": "manual",
                "serial_no": "GM-0001",
                "edge_mm": 40.0,
                "belly_mm": 42.0,
                "height_mm": 38.0,
                "weight_g": 52.0,
                "defect_level": "none",
                "notes": None,
            }
        )

        with self.assertRaises(ValueError):
            repositories.create_blacklist_pair(self.variety_id, self.w1, other_walnut_id)

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

    def test_candidates_include_image_similarity_from_bulk_features(self) -> None:
        for walnut_id in (self.w1, self.w2):
            image_id = repositories.upsert_walnut_image(
                walnut_id,
                1,
                f"{walnut_id}-1.jpg",
                f"{walnut_id}/1.jpg",
            )
            repositories.upsert_walnut_image_feature(
                image_id=image_id,
                feature_version=OPENCV_FEATURE_VERSION,
                color_histogram="[1,0]",
                texture_vector="[1,0]",
                shape_vector="[1,0]",
            )

        result = get_candidates_for_walnut(self.w1)
        candidate = next(item for item in result if item.walnut_id == self.w2)

        self.assertIsNotNone(candidate.image_similarity)
        self.assertEqual(candidate.image_matched_faces, 1)

    def test_candidates_for_variety_reuse_the_walnut_snapshot(self) -> None:
        with patch.object(repositories, "list_walnuts", wraps=repositories.list_walnuts) as list_walnuts:
            get_candidates_for_variety(self.variety_id)

        self.assertEqual(list_walnuts.call_count, 1)

    def test_non_overlapping_pairs_use_each_walnut_at_most_once(self) -> None:
        result = get_non_overlapping_pairs(self.variety_id)

        used_ids = [walnut_id for pair in result for walnut_id in (pair.walnut_id_1, pair.walnut_id_2)]

        self.assertEqual(len(used_ids), len(set(used_ids)))
        self.assertEqual(len(result), 2)
