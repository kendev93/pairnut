"""Pairing board composition and pair mutation services."""

from __future__ import annotations

from dataclasses import dataclass

from ..database import repositories
from ..domain.models import CandidateMatch
from .matching import get_matching_view_data, lock_candidate_pair
from .scoring import MIN_RECOMMENDATION_SCORE


@dataclass(frozen=True, slots=True)
class PairingBoard:
    """Read model for the candidate pairing board of a single variety."""

    walnuts: list[dict]
    candidates_by_walnut: dict[int, list[CandidateMatch]]
    images_by_walnut: dict[int, list[dict]]
    locks_by_walnut: dict[int, dict]
    walnuts_by_id: dict[int, dict]


@dataclass(frozen=True, slots=True)
class BlacklistEntry:
    """One selectable blacklist row for the management dialog."""

    id: int
    label: str


def load_pairing_board(
    variety_id: int,
    minimum_score: float = MIN_RECOMMENDATION_SCORE,
) -> PairingBoard:
    """Load walnuts, candidates, thumbnails and active locks in one pass."""
    walnuts, candidates_by_walnut = get_matching_view_data(
        variety_id,
        minimum_score=minimum_score,
    )
    walnuts_by_id = {int(walnut["id"]): walnut for walnut in walnuts}
    locks_by_walnut: dict[int, dict] = {}
    for lock in repositories.list_locked_pairs(variety_id=variety_id, active_only=True):
        locks_by_walnut[int(lock["walnut_id_1"])] = lock
        locks_by_walnut[int(lock["walnut_id_2"])] = lock
    return PairingBoard(
        walnuts=walnuts,
        candidates_by_walnut=candidates_by_walnut,
        images_by_walnut=repositories.list_walnut_images_for_variety(variety_id),
        locks_by_walnut=locks_by_walnut,
        walnuts_by_id=walnuts_by_id,
    )


def lock_pair(
    variety_id: int,
    walnut_id_1: int,
    walnut_id_2: int,
    minimum_score: float = MIN_RECOMMENDATION_SCORE,
) -> int:
    """Lock a pair that is currently recommended and within strict tolerance."""
    return lock_candidate_pair(variety_id, walnut_id_1, walnut_id_2, minimum_score)


def unlock_pair(pair_id: int) -> None:
    """Release an active lock, keeping it as unlocked history."""
    repositories.unlock_pair(pair_id)


def blacklist_pair(
    variety_id: int,
    walnut_id_1: int,
    walnut_id_2: int,
    reason: str | None = None,
) -> int:
    """Exclude a pair from recommendations."""
    return repositories.create_blacklist_pair(
        variety_id, walnut_id_1, walnut_id_2, reason=reason
    )


def list_blacklist_entries(variety_id: int) -> list[BlacklistEntry]:
    """Return the blacklisted pairs of a variety with their display labels."""
    return [
        BlacklistEntry(id=int(item["id"]), label=_blacklist_label(item))
        for item in repositories.list_blacklist_pairs(variety_id=variety_id)
    ]


def remove_blacklist_entry(blacklist_id: int) -> bool:
    """Delete one blacklist row; False when it no longer exists."""
    return repositories.delete_blacklist_pair(blacklist_id)


def _blacklist_label(item: dict) -> str:
    label = f"{item['serial_no_1']} ↔ {item['serial_no_2']}"
    return f"{label}（{item['reason']}）" if item["reason"] else label
