"""Optional feature extractor model registry."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from ..database import get_models_dir
from .image_features import OPENCV_FEATURE_VERSION

CONFIG_FILENAME = "model_config.json"
MAX_MODEL_FILE_SIZE = 256 * 1024 * 1024
DOWNLOAD_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class FeatureModel:
    model_id: str
    name: str
    input_type: str
    feature_version: str
    description: str
    size_label: str
    resource_label: str
    effect_label: str
    filename: str | None = None
    download_url: str | None = None
    sha256: str | None = None

    @property
    def is_builtin(self) -> bool:
        return self.filename is None


BUILTIN_OPENCV_MODEL = FeatureModel(
    model_id="opencv-basic",
    name="OpenCV 基础特征",
    input_type="image",
    feature_version=OPENCV_FEATURE_VERSION,
    description="默认图片匹配方案，提取颜色、纹理和形状特征，不需要下载模型。",
    size_label="无需下载",
    resource_label="低",
    effect_label="基础匹配",
)

OPTIONAL_MOBILENET_MODEL = FeatureModel(
    model_id="mobilenetv3-small-image-v1",
    name="轻量 AI 图片模型（待发布）",
    input_type="image",
    feature_version="mobilenetv3-small-v1",
    description="可选 AI 图片特征模型。模型发布后可下载到 models/ 目录并启用。",
    size_label="约 15-30 MB",
    resource_label="中",
    effect_label="预计提升纹理和局部相似度判断",
    filename="mobilenetv3-small-image-v1.onnx",
)


MODEL_CATALOG: tuple[FeatureModel, ...] = (
    BUILTIN_OPENCV_MODEL,
    OPTIONAL_MOBILENET_MODEL,
)


def model_config_path() -> Path:
    return get_models_dir() / CONFIG_FILENAME


def _read_config() -> dict[str, Any]:
    path = model_config_path()
    if not path.exists():
        return {}
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return config if isinstance(config, dict) else {}


def _write_config(config: dict[str, Any]) -> None:
    path = model_config_path()
    path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def list_feature_models() -> list[FeatureModel]:
    return list(MODEL_CATALOG)


def set_active_model(model_id: str) -> None:
    model = _get_model(model_id)
    if not is_model_downloaded(model):
        raise ValueError(f"Model is not downloaded: {model_id}")
    config = _read_config()
    config["active_image_model_id"] = model_id
    _write_config(config)


def _get_model(model_id: str) -> FeatureModel:
    for model in MODEL_CATALOG:
        if model.model_id == model_id:
            return model
    raise ValueError(f"Unknown model: {model_id}")


def model_path(model: FeatureModel) -> Path | None:
    if model.filename is None:
        return None
    return get_models_dir() / model.filename


def can_download_model(model: FeatureModel) -> bool:
    return bool(model.download_url)


def download_model(model_id: str, urlopen_func=urlopen) -> Path:
    model = _get_model(model_id)
    if model.is_builtin:
        raise ValueError("Built-in model does not need downloading.")
    if not model.download_url:
        raise ValueError("Model download URL is not configured yet.")
    parsed_url = urlparse(model.download_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise ValueError("Model download URL must use HTTPS.")
    if (
        not model.sha256
        or len(model.sha256) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in model.sha256)
    ):
        raise ValueError("Model download requires a valid SHA-256 checksum.")

    path = model_path(model)
    if path is None:
        raise ValueError("Model file path is not configured.")

    temp_path = path.with_suffix(path.suffix + ".download")
    try:
        with urlopen_func(model.download_url, timeout=60) as response:
            headers = getattr(response, "headers", None)
            content_length = (
                headers.get("Content-Length") if headers is not None else None
            )
            if content_length is not None:
                try:
                    declared_size = int(content_length)
                except (TypeError, ValueError):
                    declared_size = None
                if declared_size is not None and declared_size > MAX_MODEL_FILE_SIZE:
                    raise ValueError("Model file is too large.")

            digest = hashlib.sha256()
            total_size = 0
            with temp_path.open("wb") as target:
                while True:
                    chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > MAX_MODEL_FILE_SIZE:
                        raise ValueError("Model file is too large.")
                    digest.update(chunk)
                    target.write(chunk)

        if digest.hexdigest().lower() != model.sha256.lower():
            raise ValueError("Downloaded model checksum does not match.")

        temp_path.replace(path)
        return path
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def delete_model(model_id: str) -> None:
    model = _get_model(model_id)
    if model.is_builtin:
        raise ValueError("Built-in model cannot be deleted.")
    path = model_path(model)
    if path is not None and path.exists():
        path.unlink()
    if get_active_model_id() == model.model_id:
        set_active_model(BUILTIN_OPENCV_MODEL.model_id)


def _is_known_model(model_id: str) -> bool:
    return any(model.model_id == model_id for model in MODEL_CATALOG)


def _reset_unknown_active_model() -> None:
    config = _read_config()
    if "active_image_model_id" in config:
        config["active_image_model_id"] = BUILTIN_OPENCV_MODEL.model_id
        _write_config(config)


def _resolve_active_model_id(active_model_id: str) -> str:
    if not _is_known_model(active_model_id):
        _reset_unknown_active_model()
        return BUILTIN_OPENCV_MODEL.model_id
    model = _get_model(active_model_id)
    if not is_model_downloaded(model):
        _reset_unknown_active_model()
        return BUILTIN_OPENCV_MODEL.model_id
    return active_model_id


def get_active_model_id() -> str:
    active_model_id = str(
        _read_config().get("active_image_model_id") or BUILTIN_OPENCV_MODEL.model_id
    )
    return _resolve_active_model_id(active_model_id)


def get_active_model() -> FeatureModel:
    return _get_model(get_active_model_id())


def is_model_downloaded(model: FeatureModel) -> bool:
    if model.is_builtin:
        return True
    path = model_path(model)
    return bool(path and path.exists())
