"""Read models that combine multiple persistence calls for the UI."""

from __future__ import annotations

from dataclasses import dataclass

from ..database import repositories


@dataclass(frozen=True, slots=True)
class WalnutRow:
    """One walnut row together with its optional image and mesh evidence."""

    id: int
    walnut: dict
    images: list[dict]
    mesh: dict | None

    @property
    def image_count_label(self) -> str:
        return f"{len(self.images)} / 6"

    @property
    def mesh_label(self) -> str:
        return "已导入" if self.mesh else "未导入"

    @property
    def lock_label(self) -> str:
        return "已锁定" if self.walnut["is_locked"] else "未锁定"


@dataclass(frozen=True, slots=True)
class DashboardCounts:
    varieties: int
    walnuts: int
    locked_pairs: int


def load_walnut_rows(variety_id: int | None) -> list[WalnutRow]:
    """Load every walnut of a variety together with its images and mesh."""
    if not variety_id:
        return []
    walnuts = repositories.list_walnuts(variety_id=variety_id, include_locked=True)
    images_by_walnut = repositories.list_walnut_images_for_variety(variety_id)
    meshes_by_walnut = repositories.list_walnut_meshes_for_variety(variety_id)
    return [
        WalnutRow(
            id=int(walnut["id"]),
            walnut=walnut,
            images=images_by_walnut.get(int(walnut["id"]), []),
            mesh=meshes_by_walnut.get(int(walnut["id"])),
        )
        for walnut in walnuts
    ]


def find_variety_id(name: str, code_prefix: str) -> int | None:
    """Resolve a variety id from the two columns shown in the variety table."""
    for variety in repositories.list_varieties():
        if variety["name"] == name and variety["code_prefix"] == code_prefix:
            return int(variety["id"])
    return None


def load_dashboard_counts() -> DashboardCounts:
    return DashboardCounts(
        varieties=len(repositories.list_varieties()),
        walnuts=len(repositories.list_walnuts(include_locked=True)),
        locked_pairs=len(repositories.list_locked_pairs(active_only=True)),
    )
