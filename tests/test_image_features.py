from __future__ import annotations

import os
import tempfile
import unittest

from pairnut.database import repositories
from pairnut.database.schema import init_database
from pairnut.services.image_features import (
    OPENCV_FEATURE_VERSION,
    cosine_similarity,
    serialize_vector,
    walnut_image_similarity,
)


class ImageFeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["PAIRNUT_DATA_DIR"] = self.tempdir.name
        init_database()
        self.variety_id = repositories.create_variety("南疆石", "NJS", 1.0)
        self.w1 = self._create_walnut("NJS-01")
        self.w2 = self._create_walnut("NJS-02")

    def tearDown(self) -> None:
        os.environ.pop("PAIRNUT_DATA_DIR", None)
        self.tempdir.cleanup()

    def _create_walnut(self, serial_no: str) -> int:
        return repositories.create_walnut(
            {
                "variety_id": self.variety_id,
                "serial_mode": "manual",
                "serial_no": serial_no,
                "edge_mm": 40,
                "belly_mm": 40,
                "height_mm": 40,
                "weight_g": 30,
                "defect_level": "none",
                "notes": None,
            }
        )

    def _store_feature(self, walnut_id: int, face_no: int, vector: list[float]) -> None:
        image_id = repositories.upsert_walnut_image(walnut_id, face_no, f"{walnut_id}-{face_no}.jpg", f"{walnut_id}/{face_no}.jpg")
        repositories.upsert_walnut_image_feature(
            image_id=image_id,
            feature_version=OPENCV_FEATURE_VERSION,
            color_histogram=serialize_vector(vector),
            texture_vector=serialize_vector(vector),
            shape_vector=serialize_vector(vector),
        )

    def test_cosine_similarity_scores_identical_vectors_as_one(self) -> None:
        self.assertEqual(cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0)
        self.assertEqual(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)

    def test_walnut_image_similarity_uses_matching_faces(self) -> None:
        self._store_feature(self.w1, 1, [1.0, 0.0, 0.0])
        self._store_feature(self.w1, 2, [0.0, 1.0, 0.0])
        self._store_feature(self.w2, 1, [1.0, 0.0, 0.0])
        self._store_feature(self.w2, 3, [0.0, 0.0, 1.0])

        result = walnut_image_similarity(self.w1, self.w2)

        self.assertIsNotNone(result)
        self.assertEqual(result.matched_faces, 1)
        self.assertEqual(result.base_faces, 2)
        self.assertEqual(result.candidate_faces, 2)
        self.assertGreater(result.score, 99.0)
