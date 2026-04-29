"""Batch import helpers for walnut photos."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import shutil

from ..database import get_images_dir, repositories


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
        target.parent.mkdir(parents=True, exist_ok=True)
        existing_images = repositories.list_walnut_images(walnut_id)
        existing_image = next((image for image in existing_images if int(image["face_no"]) == parsed.face_no), None)
        shutil.copy2(source, target)
        repositories.upsert_walnut_image(
            walnut_id,
            parsed.face_no,
            source.name,
            relative_path.as_posix(),
        )
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
