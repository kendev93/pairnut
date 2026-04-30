"""Optional feature extractor model registry."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from ..database import get_models_dir
from .image_features import OPENCV_FEATURE_VERSION


CONFIG_FILENAME = "model_config.json"


@dataclass(frozen=True)
class FeatureModel:
    model_id: str
    name: str
    input_type: str
    feature_version: str
    description: str
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
)


MODEL_CATALOG: tuple[FeatureModel, ...] = (
    BUILTIN_OPENCV_MODEL,
)


def model_config_path() -> Path:
    return get_models_dir() / CONFIG_FILENAME


def _read_config() -> dict[str, Any]:
    path = model_config_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_config(config: dict[str, Any]) -> None:
    path = model_config_path()
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_feature_models() -> list[FeatureModel]:
    return list(MODEL_CATALOG)


def get_active_model_id() -> str:
    return str(_read_config().get("active_image_model_id") or BUILTIN_OPENCV_MODEL.model_id)


def set_active_model(model_id: str) -> None:
    if not any(model.model_id == model_id for model in MODEL_CATALOG):
        raise ValueError(f"Unknown model: {model_id}")
    config = _read_config()
    config["active_image_model_id"] = model_id
    _write_config(config)


def get_active_model() -> FeatureModel:
    active_model_id = get_active_model_id()
    for model in MODEL_CATALOG:
        if model.model_id == active_model_id:
            return model
    return BUILTIN_OPENCV_MODEL


def is_model_downloaded(model: FeatureModel) -> bool:
    if model.is_builtin:
        return True
    return (get_models_dir() / model.filename).exists()
