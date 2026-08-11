from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pairnut.database import repositories
from pairnut.database.connection import get_meshes_dir
from pairnut.database.schema import init_database
from pairnut.domain.models import DefectLevel, SerialMode
from pairnut.services.mesh_features import (
    MESH_FEATURE_VERSION,
    delete_walnut_mesh,
    extract_mesh_features,
    feature_similarity,
    import_walnut_mesh,
    mesh_similarity_from_features,
    walnut_mesh_similarity,
)


TETRA_OBJ = """\
v 0 0 0
v 1 0 0
v 0 1 0
v 0 0 1
f 1 2 3
f 1 2 4
f 1 3 4
f 2 3 4
"""


class MeshFeatureTests(unittest.TestCase):
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
                "serial_mode": SerialMode.MANUAL.value,
                "serial_no": serial_no,
                "edge_mm": 40,
                "belly_mm": 40,
                "height_mm": 40,
                "weight_g": 30,
                "defect_level": DefectLevel.NONE.value,
                "notes": None,
            }
        )

    def _write_obj(self, name: str, content: str = TETRA_OBJ) -> Path:
        path = Path(self.tempdir.name) / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_extract_mesh_features_from_obj(self) -> None:
        source = self._write_obj("tetra.obj")

        feature = extract_mesh_features(source)

        self.assertEqual(feature.dimensions_vector, [1.0, 1.0, 1.0])
        self.assertGreater(feature.shape_vector[1], 0.0)
        self.assertGreater(feature.shape_vector[2], 0.0)

    def test_import_walnut_mesh_copies_file_and_stores_features(self) -> None:
        source = self._write_obj("NJS-01.obj")

        import_walnut_mesh(self.w1, source)

        mesh = repositories.get_walnut_mesh(self.w1)
        self.assertIsNotNone(mesh)
        assert mesh is not None
        self.assertEqual(mesh["original_filename"], "NJS-01.obj")
        self.assertEqual(mesh["stored_path"], f"{self.w1}-NJS-01/source.obj")
        self.assertTrue((get_meshes_dir() / f"{self.w1}-NJS-01" / "source.obj").exists())

        features = repositories.list_walnut_mesh_features(self.w1, MESH_FEATURE_VERSION)
        self.assertEqual(len(features), 1)
        meshes_by_walnut = repositories.list_walnut_meshes_for_variety(self.variety_id)
        self.assertEqual(meshes_by_walnut[self.w1]["original_filename"], "NJS-01.obj")

    def test_walnut_mesh_similarity_scores_identical_meshes_highly(self) -> None:
        import_walnut_mesh(self.w1, self._write_obj("NJS-01.obj"))
        import_walnut_mesh(self.w2, self._write_obj("NJS-02.obj"))

        result = walnut_mesh_similarity(self.w1, self.w2)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertGreater(result.score, 99.0)

    def test_feature_similarity_is_invariant_to_uniform_model_scaling(self) -> None:
        left = {
            "dimensions_vector": "[1,2,3]",
            "shape_vector": "[6,2,3,0.5,0.8,0.1,0.66,0.33]",
        }
        right = {
            "dimensions_vector": "[2,4,6]",
            "shape_vector": "[48,16,12,0.5,0.8,0.1,0.66,0.33]",
        }

        self.assertGreater(feature_similarity(left, right), 99.0)

    def test_feature_similarity_rejects_malformed_vector_lengths(self) -> None:
        left = {
            "dimensions_vector": "[1,2]",
            "shape_vector": "[6,2,3,0.5,0.8,0.1,0.66,0.33]",
        }
        right = {
            "dimensions_vector": "[1,2,3]",
            "shape_vector": "[6,2,3,0.5,0.8,0.1,0.66,0.33]",
        }

        self.assertEqual(feature_similarity(left, right), 0.0)

    def test_malformed_mesh_feature_is_ignored_without_crashing(self) -> None:
        result = mesh_similarity_from_features(
            [{"dimensions_vector": "not-json", "shape_vector": "[1,2,3,4,5,6,7,8]"}],
            [{"dimensions_vector": "[1,2,3]", "shape_vector": "[1,2,3,4,5,6,7,8]"}],
        )

        self.assertIsNone(result)

    def test_unsupported_mesh_suffix_is_rejected(self) -> None:
        source = self._write_obj("NJS-01.glb")

        with self.assertRaises(ValueError):
            import_walnut_mesh(self.w1, source)

    def test_invalid_mesh_does_not_create_record_or_copy_file(self) -> None:
        source = self._write_obj("broken.obj", "v 0 0 0\n")

        with self.assertRaises(ValueError):
            import_walnut_mesh(self.w1, source)

        self.assertIsNone(repositories.get_walnut_mesh(self.w1))
        self.assertFalse((get_meshes_dir() / f"{self.w1}-NJS-01" / "source.obj").exists())

    def test_database_failure_does_not_leave_copied_mesh(self) -> None:
        source = self._write_obj("NJS-01.obj")

        with patch.object(repositories, "upsert_walnut_mesh", side_effect=RuntimeError("database unavailable")):
            with self.assertRaises(RuntimeError):
                import_walnut_mesh(self.w1, source)

        self.assertIsNone(repositories.get_walnut_mesh(self.w1))
        self.assertFalse((get_meshes_dir() / f"{self.w1}-NJS-01" / "source.obj").exists())

    def test_failed_mesh_replacement_restores_previous_record_and_file(self) -> None:
        source = self._write_obj("NJS-01.obj")
        import_walnut_mesh(self.w1, source)
        stored_path = get_meshes_dir() / f"{self.w1}-NJS-01" / "source.obj"
        original_content = stored_path.read_text(encoding="utf-8")
        source.write_text(TETRA_OBJ + "# replacement", encoding="utf-8")

        with patch("pairnut.services.mesh_features.store_mesh_feature", side_effect=RuntimeError("feature store failed")):
            with self.assertRaises(RuntimeError):
                import_walnut_mesh(self.w1, source)

        mesh = repositories.get_walnut_mesh(self.w1)
        self.assertIsNotNone(mesh)
        assert mesh is not None
        self.assertEqual(mesh["original_filename"], "NJS-01.obj")
        self.assertEqual(stored_path.read_text(encoding="utf-8"), original_content)

    def test_locked_walnut_cannot_import_mesh(self) -> None:
        partner_id = self._create_walnut("NJS-03")
        repositories.lock_pair(self.variety_id, self.w1, partner_id)
        source = self._write_obj("NJS-01.obj")

        with self.assertRaises(ValueError):
            import_walnut_mesh(self.w1, source)

        self.assertIsNone(repositories.get_walnut_mesh(self.w1))

    def test_locked_walnut_cannot_delete_mesh(self) -> None:
        import_walnut_mesh(self.w1, self._write_obj("NJS-01.obj"))
        partner_id = self._create_walnut("NJS-03")
        repositories.lock_pair(self.variety_id, self.w1, partner_id)

        with self.assertRaises(ValueError):
            delete_walnut_mesh(self.w1)

    def test_database_failure_restores_deleted_mesh_file(self) -> None:
        import_walnut_mesh(self.w1, self._write_obj("NJS-01.obj"))
        stored_file = get_meshes_dir() / f"{self.w1}-NJS-01" / "source.obj"

        with patch.object(repositories, "delete_walnut_mesh", side_effect=RuntimeError("database unavailable")):
            with self.assertRaises(RuntimeError):
                delete_walnut_mesh(self.w1)

        self.assertTrue(stored_file.exists())
        self.assertIsNotNone(repositories.get_walnut_mesh(self.w1))

    def test_mesh_delete_rejects_path_outside_data_directory(self) -> None:
        outside = Path(self.tempdir.name).parent / f"{self.tempdir.name.rsplit('/', 1)[-1]}-outside.obj"
        outside.write_text("keep", encoding="utf-8")
        try:
            repositories.upsert_walnut_mesh(self.w1, "bad.obj", "../../" + outside.name)

            with self.assertRaises(ValueError):
                delete_walnut_mesh(self.w1)

            self.assertTrue(outside.exists())
        finally:
            outside.unlink(missing_ok=True)
