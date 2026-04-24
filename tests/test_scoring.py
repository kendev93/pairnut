from __future__ import annotations

import unittest

from pairnut.services.scoring import build_score, within_tolerance


BASE_WALNUT = {
    "edge_mm": 40.0,
    "belly_mm": 42.0,
    "height_mm": 38.0,
    "weight_g": 52.0,
    "defect_level": "none",
}


class ScoringTests(unittest.TestCase):
    def test_within_tolerance_requires_all_three_dimensions(self) -> None:
        candidate = {
            **BASE_WALNUT,
            "edge_mm": 40.8,
            "belly_mm": 42.4,
            "height_mm": 39.2,
        }
        self.assertFalse(within_tolerance(BASE_WALNUT, candidate, 1.0))

    def test_closer_weight_scores_higher(self) -> None:
        close_weight = {**BASE_WALNUT, "weight_g": 52.2}
        far_weight = {**BASE_WALNUT, "weight_g": 55.0}
        close_score = build_score(BASE_WALNUT, close_weight, 1.0)
        far_score = build_score(BASE_WALNUT, far_weight, 1.0)
        self.assertGreater(close_score["total_score"], far_score["total_score"])

    def test_defect_penalty_reduces_score(self) -> None:
        clean = {**BASE_WALNUT, "weight_g": 52.1}
        medium_defect = {**BASE_WALNUT, "weight_g": 52.1, "defect_level": "medium"}
        clean_score = build_score(BASE_WALNUT, clean, 1.0)
        defect_score = build_score(BASE_WALNUT, medium_defect, 1.0)
        self.assertGreater(clean_score["total_score"], defect_score["total_score"])
