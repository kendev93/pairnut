from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

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

    class _FakeResponse:
        def __init__(self, data: bytes):
            self.data = data
            self.offset = 0
            self.headers = {}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self, size: int) -> bytes:
            chunk = self.data[self.offset : self.offset + size]
            self.offset += len(chunk)
            return chunk

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

    def test_malformed_model_config_falls_back_to_builtin_model(self) -> None:
        path = model_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json", encoding="utf-8")

        self.assertEqual(get_active_model_id(), BUILTIN_OPENCV_MODEL.model_id)

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

    def test_download_rejects_non_https_url(self) -> None:
        model = replace(
            OPTIONAL_MOBILENET_MODEL,
            download_url="http://example.com/model.onnx",
            sha256="a" * 64,
        )
        with patch("pairnut.services.model_registry.MODEL_CATALOG", (BUILTIN_OPENCV_MODEL, model)), self.assertRaises(ValueError):
            download_model(model.model_id)

    def test_download_requires_checksum_and_cleans_temporary_file(self) -> None:
        model = replace(
            OPTIONAL_MOBILENET_MODEL,
            download_url="https://example.com/model.onnx",
            sha256=None,
        )

        with patch("pairnut.services.model_registry.MODEL_CATALOG", (BUILTIN_OPENCV_MODEL, model)), self.assertRaises(ValueError):
            download_model(model.model_id)

        path = model_path(model)
        assert path is not None
        self.assertFalse(path.exists())
        self.assertFalse(path.with_suffix(path.suffix + ".download").exists())

    def test_download_streams_and_replaces_atomically_after_checksum(self) -> None:
        data = b"model bytes"
        model = replace(
            OPTIONAL_MOBILENET_MODEL,
            download_url="https://example.com/model.onnx",
            sha256=hashlib.sha256(data).hexdigest(),
        )
        response = self._FakeResponse(data)

        with patch("pairnut.services.model_registry.MODEL_CATALOG", (BUILTIN_OPENCV_MODEL, model)):
            path = download_model(model.model_id, urlopen_func=lambda url, timeout: response)

        self.assertEqual(path.read_bytes(), data)
        path.unlink()

    def test_download_rejects_oversized_response_and_removes_temp_file(self) -> None:
        data = b"too large"
        model = replace(
            OPTIONAL_MOBILENET_MODEL,
            download_url="https://example.com/model.onnx",
            sha256=hashlib.sha256(data).hexdigest(),
        )
        response = self._FakeResponse(data)

        with (
            patch("pairnut.services.model_registry.MODEL_CATALOG", (BUILTIN_OPENCV_MODEL, model)),
            patch("pairnut.services.model_registry.MAX_MODEL_FILE_SIZE", 1),
            self.assertRaisesRegex(ValueError, "too large"),
        ):
            download_model(model.model_id, urlopen_func=lambda url, timeout: response)

        path = model_path(model)
        assert path is not None
        self.assertFalse(path.exists())
        self.assertFalse(path.with_suffix(path.suffix + ".download").exists())

    def test_delete_optional_model_removes_file_and_resets_active_model(self) -> None:
        path = model_path(OPTIONAL_MOBILENET_MODEL)
        self.assertIsNotNone(path)
        assert path is not None
        path.write_bytes(b"model")
        set_active_model(OPTIONAL_MOBILENET_MODEL.model_id)

        delete_model(OPTIONAL_MOBILENET_MODEL.model_id)

        self.assertFalse(path.exists())
        self.assertEqual(get_active_model_id(), BUILTIN_OPENCV_MODEL.model_id)
