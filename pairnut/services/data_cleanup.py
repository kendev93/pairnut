"""User-data deletion workflows for database records and stored assets."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from ..database import get_data_dir, get_images_dir, get_meshes_dir, repositories

STAGING_PREFIX = ".pairnut-delete-"
STAGING_MANIFEST = ".manifest.json"


def _collect_asset_paths(walnut_id: int) -> tuple[list[str], list[str]]:
    image_paths = [image["stored_path"] for image in repositories.list_walnut_images(walnut_id)]
    mesh = repositories.get_walnut_mesh(walnut_id)
    mesh_paths = [mesh["stored_path"]] if mesh else []
    return image_paths, mesh_paths


def _resolve_asset_path(root: Path, stored_path: str) -> Path:
    resolved_root = root.resolve()
    candidate = (root / stored_path).resolve()
    if candidate == resolved_root or not candidate.is_relative_to(resolved_root):
        raise ValueError("资产路径超出应用数据目录。")
    return candidate


def _stage_assets(image_paths: list[str], mesh_paths: list[str]) -> tuple[Path, list[tuple[Path, Path]]]:
    """Move assets to a recoverable staging directory before DB deletion."""
    staging_root = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=get_data_dir()))
    staged: list[tuple[Path, Path]] = []
    manifest_records: list[dict[str, str]] = []
    try:
        for root, stored_paths in ((get_images_dir(), image_paths), (get_meshes_dir(), mesh_paths)):
            for index, stored_path in enumerate(stored_paths):
                candidate = _resolve_asset_path(root, stored_path)
                if not candidate.exists():
                    continue
                if not candidate.is_file():
                    raise OSError(f"资产不是普通文件: {candidate}")
                staged_path = staging_root / f"{root.name}-{index}-{candidate.name}"
                manifest_records.append(
                    {
                        "root": root.name,
                        "stored_path": stored_path,
                        "staged_name": staged_path.name,
                    }
                )
                _write_staging_manifest(staging_root, manifest_records)
                shutil.move(str(candidate), str(staged_path))
                staged.append((candidate, staged_path))
    except Exception:
        try:
            _restore_staged_assets(staged)
        finally:
            shutil.rmtree(staging_root, ignore_errors=True)
        raise
    return staging_root, staged


def _restore_staged_assets(staged: list[tuple[Path, Path]]) -> None:
    for original_path, staged_path in reversed(staged):
        if not staged_path.exists():
            continue
        original_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staged_path), str(original_path))


def _discard_staged_assets(staging_root: Path) -> None:
    shutil.rmtree(staging_root, ignore_errors=True)


def _write_staging_manifest(staging_root: Path, records: list[dict[str, str]]) -> None:
    manifest_path = staging_root / STAGING_MANIFEST
    temporary_path = manifest_path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(manifest_path)


def recover_stale_staging() -> int:
    """Restore assets left in a staging directory after an interrupted delete."""
    recovered = 0
    images_root = get_images_dir()
    meshes_root = get_meshes_dir()
    for staging_root in get_data_dir().glob(f"{STAGING_PREFIX}*"):
        if not staging_root.is_dir():
            continue
        manifest_path = staging_root / STAGING_MANIFEST
        if not manifest_path.exists():
            continue
        try:
            records = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(records, list):
                continue
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue

        unresolved = False
        for record in records:
            if not isinstance(record, dict):
                unresolved = True
                continue
            root_name = record.get("root")
            stored_path = record.get("stored_path")
            staged_name = record.get("staged_name")
            if not isinstance(root_name, str) or not root_name:
                unresolved = True
                continue
            if not isinstance(stored_path, str) or not stored_path:
                unresolved = True
                continue
            if not isinstance(staged_name, str) or not staged_name:
                unresolved = True
                continue
            root = images_root if root_name == images_root.name else meshes_root if root_name == meshes_root.name else None
            if root is None or Path(staged_name).name != staged_name:
                unresolved = True
                continue
            try:
                original_path = _resolve_asset_path(root, stored_path)
            except ValueError:
                unresolved = True
                continue
            staged_path = staging_root / staged_name
            if not staged_path.exists():
                continue
            if original_path.exists():
                unresolved = True
                continue
            try:
                original_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(staged_path), str(original_path))
            except OSError:
                unresolved = True

        if unresolved:
            continue
        _discard_staged_assets(staging_root)
        recovered += 1
    return recovered


def _remove_empty_asset_parents(root: Path, stored_paths: list[str]) -> None:
    resolved_root = root.resolve()
    for stored_path in stored_paths:
        parent = _resolve_asset_path(root, stored_path).parent
        while parent != resolved_root and parent.is_relative_to(resolved_root):
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent


def delete_walnut_data(walnut_id: int) -> bool:
    """Delete one walnut and its locally stored image/mesh files."""
    walnut = repositories.get_walnut(walnut_id)
    if walnut is None:
        return False
    if repositories.get_active_lock_for_walnut(walnut_id):
        raise ValueError("已锁定的核桃不能删除，请先解除锁定。")

    image_paths, mesh_paths = _collect_asset_paths(walnut_id)
    staging_root, staged = _stage_assets(image_paths, mesh_paths)
    try:
        repositories.delete_walnut(walnut_id)
    except Exception:
        _restore_staged_assets(staged)
        _discard_staged_assets(staging_root)
        raise
    _discard_staged_assets(staging_root)
    _remove_empty_asset_parents(get_images_dir(), image_paths)
    _remove_empty_asset_parents(get_meshes_dir(), mesh_paths)
    return True


def delete_variety_data(variety_id: int) -> bool:
    """Delete a variety, its walnuts, and all locally stored assets."""
    if repositories.get_variety(variety_id) is None:
        return False
    if repositories.list_locked_pairs(variety_id=variety_id, active_only=True):
        raise ValueError("该品种存在已锁定配对，请先解除锁定。")

    image_paths: list[str] = []
    mesh_paths: list[str] = []
    for walnut in repositories.list_walnuts(variety_id=variety_id, include_locked=True):
        walnut_images, walnut_meshes = _collect_asset_paths(int(walnut["id"]))
        image_paths.extend(walnut_images)
        mesh_paths.extend(walnut_meshes)

    staging_root, staged = _stage_assets(image_paths, mesh_paths)
    try:
        repositories.delete_variety(variety_id)
    except Exception:
        _restore_staged_assets(staged)
        _discard_staged_assets(staging_root)
        raise
    _discard_staged_assets(staging_root)
    _remove_empty_asset_parents(get_images_dir(), image_paths)
    _remove_empty_asset_parents(get_meshes_dir(), mesh_paths)
    return True
