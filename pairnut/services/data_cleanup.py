"""User-data deletion workflows for database records and stored assets."""

from __future__ import annotations

from pathlib import Path

from ..database import get_images_dir, get_meshes_dir, repositories


def _collect_asset_paths(walnut_id: int) -> tuple[list[str], list[str]]:
    image_paths = [image["stored_path"] for image in repositories.list_walnut_images(walnut_id)]
    mesh = repositories.get_walnut_mesh(walnut_id)
    mesh_paths = [mesh["stored_path"]] if mesh else []
    return image_paths, mesh_paths


def _remove_asset_files(root: Path, stored_paths: list[str]) -> None:
    resolved_root = root.resolve()
    for stored_path in stored_paths:
        candidate = (root / stored_path).resolve()
        if candidate == resolved_root or not candidate.is_relative_to(resolved_root):
            continue
        try:
            candidate.unlink()
        except FileNotFoundError:
            continue
        except OSError:
            continue

        parent = candidate.parent
        while parent != resolved_root and parent.is_relative_to(resolved_root):
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent


def _remove_assets(image_paths: list[str], mesh_paths: list[str]) -> None:
    _remove_asset_files(get_images_dir(), image_paths)
    _remove_asset_files(get_meshes_dir(), mesh_paths)


def delete_walnut_data(walnut_id: int) -> bool:
    """Delete one walnut and its locally stored image/mesh files."""
    walnut = repositories.get_walnut(walnut_id)
    if walnut is None:
        return False
    if repositories.get_active_lock_for_walnut(walnut_id):
        raise ValueError("已锁定的核桃不能删除，请先解除锁定。")

    image_paths, mesh_paths = _collect_asset_paths(walnut_id)
    repositories.delete_walnut(walnut_id)
    _remove_assets(image_paths, mesh_paths)
    return True


def delete_variety_data(variety_id: int) -> bool:
    """Delete a variety, its walnuts, and all locally stored assets."""
    if repositories.get_variety(variety_id) is None:
        return False

    image_paths: list[str] = []
    mesh_paths: list[str] = []
    for walnut in repositories.list_walnuts(variety_id=variety_id, include_locked=True):
        walnut_images, walnut_meshes = _collect_asset_paths(int(walnut["id"]))
        image_paths.extend(walnut_images)
        mesh_paths.extend(walnut_meshes)

    repositories.delete_variety(variety_id)
    _remove_assets(image_paths, mesh_paths)
    return True
