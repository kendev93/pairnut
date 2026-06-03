"""Candidate matching service."""

from __future__ import annotations

from ..database import repositories
from ..domain.models import CandidateMatch
from .image_features import walnut_image_similarity
from .mesh_features import walnut_mesh_similarity
from .scoring import build_score, within_tolerance


def _combine_optional_evidence(base_score: float, evidence_scores: list[float]) -> float:
    if not evidence_scores:
        return base_score
    evidence_score = sum(evidence_scores) / len(evidence_scores)
    return (base_score * 0.75) + (evidence_score * 0.25)


def get_candidates_for_walnut(walnut_id: int, limit: int = 3) -> list[CandidateMatch]:
    walnut = repositories.get_walnut(walnut_id)
    if walnut is None:
        return []
    if walnut["is_locked"]:
        return []

    variety = repositories.get_variety(walnut["variety_id"])
    tolerance_mm = float(variety["tolerance_mm"]) if variety else 1.0
    candidates: list[CandidateMatch] = []

    for other in repositories.list_walnuts(variety_id=walnut["variety_id"], include_locked=False):
        if other["id"] == walnut_id:
            continue
        if repositories.is_pair_blacklisted(walnut_id, other["id"]):
            continue
        if not within_tolerance(walnut, other, tolerance_mm):
            continue
        score = build_score(walnut, other, tolerance_mm)
        image_similarity = walnut_image_similarity(walnut_id, int(other["id"]))
        mesh_similarity = walnut_mesh_similarity(walnut_id, int(other["id"]))
        optional_scores = []
        if image_similarity:
            optional_scores.append(image_similarity.score)
        if mesh_similarity:
            optional_scores.append(mesh_similarity.score)
        total_score = _combine_optional_evidence(score["total_score"], optional_scores)
        candidates.append(
            CandidateMatch(
                walnut_id=other["id"],
                serial_no=other["serial_no"],
                total_score=total_score,
                dimension_score=score["dimension_score"],
                weight_bonus=score["weight_bonus"],
                defect_penalty=score["defect_penalty"],
                edge_diff=score["edge_diff"],
                belly_diff=score["belly_diff"],
                height_diff=score["height_diff"],
                weight_diff=score["weight_diff"],
                defect_level=other["defect_level"],
                image_similarity=image_similarity.score if image_similarity else None,
                image_matched_faces=image_similarity.matched_faces if image_similarity else 0,
                image_base_faces=image_similarity.base_faces if image_similarity else 0,
                image_candidate_faces=image_similarity.candidate_faces if image_similarity else 0,
                mesh_similarity=mesh_similarity.score if mesh_similarity else None,
            )
        )

    candidates.sort(
        key=lambda item: (
            -item.total_score,
            item.weight_diff,
            item.serial_no,
        )
    )
    return candidates[:limit]


def get_candidates_for_variety(variety_id: int, limit: int = 3) -> dict[int, list[CandidateMatch]]:
    result: dict[int, list[CandidateMatch]] = {}
    for walnut in repositories.list_walnuts(variety_id=variety_id, include_locked=True):
        result[walnut["id"]] = get_candidates_for_walnut(walnut["id"], limit=limit)
    return result
