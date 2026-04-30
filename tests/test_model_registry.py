from __future__ import annotations

import os
import tempfile
import unittest

from pairnut.database.connection import get_models_dir
from pairnut.services.model_registry import (
    BUILTIN_OPENCV_MODEL,
    get_active_model,
    get_active_model_id,
    is_model_downloaded,
    list_feature_models,
    model_config_path,
    set_active_model,
)


class ModelRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["PAIRNUT_DATA_DIR"] = self.tempdir.name

    def tearDown(self) -> None:
        os.environ.pop("PAIRNUT_DATA_DIR", None)
        self.tempdir.cleanup()

    def test_builtin_opencv_model_is_default_and_downloaded(self) -> None:
        self.assertEqual(get_active_model_id(), BUILTIN_OPENCV_MODEL.model_id)
        self.assertEqual(get_active_model(), BUILTIN_OPENCV_MODEL)
        self.assertTrue(is_model_downloaded(BUILTIN_OPENCV_MODEL))

    def test_model_catalog_contains_builtin_opencv_model(self) -> None:
        self.assertEqual(list_feature_models(), [BUILTIN_OPENCV_MODEL])

    def test_set_active_model_writes_config_under_models_dir(self) -> None:
        set_active_model(BUILTIN_OPENCV_MODEL.model_id)

        self.assertEqual(get_active_model_id(), BUILTIN_OPENCV_MODEL.model_id)
        self.assertEqual(model_config_path().parent, get_models_dir())
        self.assertTrue(model_config_path().exists())

    def test_unknown_model_cannot_be_activated(self) -> None:
        with self.assertRaises(ValueError):
            set_active_model("missing-model")
