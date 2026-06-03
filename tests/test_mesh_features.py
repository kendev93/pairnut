from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from pairnut.database import repositories
from pairnut.database.connection import get_meshes_dir
from pairnut.database.schema import init_database
from pairnut.domain.models import DefectLevel, SerialMode
from pairnut.services.mesh_features import (
    MESH_FEATURE_VERSION,
    extract_mesh_features,
    import_walnut_mesh,
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

    def test_walnut_mesh_similarity_scores_identical_meshes_highly(self) -> None:
        import_walnut_mesh(self.w1, self._write_obj("NJS-01.obj"))
        import_walnut_mesh(self.w2, self._write_obj("NJS-02.obj"))

        result = walnut_mesh_similarity(self.w1, self.w2)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertGreater(result.score, 99.0)

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
