"""Batch import helpers for walnut photos."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import shutil

from ..database import get_images_dir, repositories
from .image_features import OPENCV_FEATURE_VERSION, extract_opencv_features, serialize_vector


SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic"}
FILENAME_PATTERN = re.compile(r"^(.+)[-_ ]([1-6])$")


@dataclass(frozen=True)
class ParsedImageName:
    serial_no: str
    face_no: int


@dataclass
class BatchImageImportResult:
    imported_count: int = 0
    replaced_count: int = 0
    skipped: list[str] = field(default_factory=list)


def parse_image_filename(path: str | Path) -> ParsedImageName | None:
    source = Path(path)
    if source.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
        return None
    match = FILENAME_PATTERN.match(source.stem.strip())
    if not match:
        return None
    return ParsedImageName(serial_no=match.group(1).strip(), face_no=int(match.group(2)))


def _safe_path_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned.strip("._") or "walnut"


def import_walnut_images(file_paths: list[str | Path], variety_id: int) -> BatchImageImportResult:
    result = BatchImageImportResult()
    images_root = get_images_dir()

    for file_path in file_paths:
        source = Path(file_path)
        parsed = parse_image_filename(source)
        if parsed is None:
            result.skipped.append(f"{source.name}: 文件名需为 核桃编号-1 到 核桃编号-6")
            continue
        if not source.exists() or not source.is_file():
            result.skipped.append(f"{source.name}: 文件不存在")
            continue

        walnut = repositories.get_walnut_by_serial_and_variety(parsed.serial_no, variety_id)
        if walnut is None:
            result.skipped.append(f"{source.name}: 当前品种下没有编号 {parsed.serial_no}")
            continue

        walnut_id = int(walnut["id"])
        relative_path = Path(f"{walnut_id}-{_safe_path_part(parsed.serial_no)}") / f"{parsed.face_no}{source.suffix.lower()}"
        target = images_root / relative_path
        existing_images = repositories.list_walnut_images(walnut_id)
        existing_image = next((image for image in existing_images if int(image["face_no"]) == parsed.face_no), None)

        try:
            features = extract_opencv_features(source)
        except Exception as exc:
            result.skipped.append(f"{source.name}: 图片特征提取失败：{exc}")
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        backup_path: Path | None = None
        try:
            if target.exists():
                backup_path = target.with_name(f".{target.name}.pairnut-backup")
                shutil.copy2(target, backup_path)
            shutil.copy2(source, target)
            repositories.upsert_walnut_image_with_feature(
                walnut_id=walnut_id,
                face_no=parsed.face_no,
                original_filename=source.name,
                stored_path=relative_path.as_posix(),
                feature_version=OPENCV_FEATURE_VERSION,
                color_histogram=serialize_vector(features.color_histogram),
                texture_vector=serialize_vector(features.texture_vector),
                shape_vector=serialize_vector(features.shape_vector),
            )
        except Exception as exc:
            if backup_path and backup_path.exists():
                shutil.copy2(backup_path, target)
            elif target.exists() and existing_image is None:
                target.unlink()
            result.skipped.append(f"{source.name}: 导入失败：{exc}")
            if backup_path and backup_path.exists():
                backup_path.unlink()
            continue
        finally:
            if backup_path and backup_path.exists():
                backup_path.unlink()

        if existing_image:
            old_path = images_root / existing_image["stored_path"]
            if old_path != target and old_path.exists():
                old_path.unlink()
            result.replaced_count += 1
        else:
            result.imported_count += 1

    return result


def delete_walnut_image(walnut_id: int, face_no: int) -> bool:
    image = repositories.get_walnut_image(walnut_id, face_no)
    if image is None:
        return False

    image_path = get_images_dir() / image["stored_path"]
    if image_path.exists():
        image_path.unlink()
    repositories.delete_walnut_image(walnut_id, face_no)
    return True
