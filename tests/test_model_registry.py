from __future__ import annotations

import os
import tempfile
import unittest

from pairnut.database.connection import get_models_dir
from pairnut.services.model_registry import (
    BUILTIN_OPENCV_MODEL,
    OPTIONAL_MOBILENET_MODEL,
    can_download_model,
    delete_model,
    download_model,
    get_active_model,
    get_active_model_id,
    is_model_downloaded,
    list_feature_models,
    model_config_path,
    model_path,
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
        self.assertEqual(BUILTIN_OPENCV_MODEL.size_label, "无需下载")
        self.assertEqual(BUILTIN_OPENCV_MODEL.resource_label, "低")

    def test_model_catalog_contains_builtin_opencv_model(self) -> None:
        self.assertIn(BUILTIN_OPENCV_MODEL, list_feature_models())
        self.assertIn(OPTIONAL_MOBILENET_MODEL, list_feature_models())

    def test_set_active_model_writes_config_under_models_dir(self) -> None:
        set_active_model(BUILTIN_OPENCV_MODEL.model_id)

        self.assertEqual(get_active_model_id(), BUILTIN_OPENCV_MODEL.model_id)
        self.assertEqual(model_config_path().parent, get_models_dir())
        self.assertTrue(model_config_path().exists())

    def test_unknown_model_cannot_be_activated(self) -> None:
        with self.assertRaises(ValueError):
            set_active_model("missing-model")

    def test_optional_model_is_not_downloaded_by_default(self) -> None:
        self.assertFalse(is_model_downloaded(OPTIONAL_MOBILENET_MODEL))
        self.assertFalse(can_download_model(OPTIONAL_MOBILENET_MODEL))
        self.assertEqual(model_path(OPTIONAL_MOBILENET_MODEL), get_models_dir() / OPTIONAL_MOBILENET_MODEL.filename)
        self.assertEqual(OPTIONAL_MOBILENET_MODEL.size_label, "约 15-30 MB")
        self.assertEqual(OPTIONAL_MOBILENET_MODEL.resource_label, "中")
        self.assertIn("提升", OPTIONAL_MOBILENET_MODEL.effect_label)

    def test_optional_model_cannot_be_activated_before_download(self) -> None:
        with self.assertRaises(ValueError):
            set_active_model(OPTIONAL_MOBILENET_MODEL.model_id)

        self.assertEqual(get_active_model_id(), BUILTIN_OPENCV_MODEL.model_id)

    def test_download_without_configured_url_fails(self) -> None:
        with self.assertRaises(ValueError):
            download_model(OPTIONAL_MOBILENET_MODEL.model_id)

    def test_delete_optional_model_removes_file_and_resets_active_model(self) -> None:
        path = model_path(OPTIONAL_MOBILENET_MODEL)
        self.assertIsNotNone(path)
        assert path is not None
        path.write_bytes(b"model")
        set_active_model(OPTIONAL_MOBILENET_MODEL.model_id)

        delete_model(OPTIONAL_MOBILENET_MODEL.model_id)

        self.assertFalse(path.exists())
        self.assertEqual(get_active_model_id(), BUILTIN_OPENCV_MODEL.model_id)
