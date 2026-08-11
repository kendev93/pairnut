"""Candidate matching and non-overlapping pairing services."""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cache

import networkx as nx  # type: ignore[import-untyped]

from ..database import repositories
from ..domain.models import CandidateMatch, PairMatch
from .image_features import (
    OPENCV_FEATURE_VERSION,
    WalnutImageSimilarity,
    image_similarity_from_features,
)
from .mesh_features import (
    MESH_FEATURE_VERSION,
    WalnutMeshSimilarity,
    mesh_similarity_from_features,
)
from .scoring import MIN_RECOMMENDATION_SCORE, build_score, within_tolerance

DEFAULT_CANDIDATE_LIMIT = 3
# The wider window is used only to avoid dropping near matches too early;
# the original tolerance is still used by the dimension score.
DEFAULT_SCREENING_TOLERANCE_MULTIPLIER = 1.25
OPTIONAL_EVIDENCE_WEIGHT = 0.25
MAX_IMAGE_FACE_COUNT = 6


@dataclass(frozen=True, slots=True)
class _MatchingSnapshot:
    walnuts: list[dict]
    blacklisted_pairs: frozenset[tuple[int, int]]
    image_features: dict[int, list[dict]]
    mesh_features: dict[int, list[dict]]


@dataclass(frozen=True, slots=True)
class _PairEvidence:
    image_similarity: WalnutImageSimilarity | None
    mesh_similarity: WalnutMeshSimilarity | None


def _validate_limit(limit: int | None) -> int | None:
    if limit is None:
        return None
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise ValueError("limit must be a non-negative integer or None.")
    return limit


def _validate_screening_multiplier(multiplier: float) -> float:
    try:
        value = float(multiplier)
    except (TypeError, ValueError) as exc:
        raise ValueError("screening multiplier must be a positive finite number.") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError("screening multiplier must be a positive finite number.")
    return value


def _validate_minimum_score(minimum_score: float | None) -> float | None:
    if minimum_score is None:
        return None
    try:
        value = float(minimum_score)
    except (TypeError, ValueError) as exc:
        raise ValueError("minimum_score must be finite or None.") from exc
    if not math.isfinite(value):
        raise ValueError("minimum_score must be finite or None.")
    return value


def _combine_optional_evidence(
    base_score: float,
    evidence_scores: list[float],
    evidence_confidences: list[float] | None = None,
) -> float:
    """Add optional evidence without allowing sparse evidence to dominate.

    Missing evidence remains neutral. When evidence exists but has incomplete
    coverage, its influence is scaled by the supplied confidence.
    """
    if not evidence_scores:
        return base_score
    confidences = (
        evidence_confidences
        if evidence_confidences is not None
        else [1.0] * len(evidence_scores)
    )
    if len(confidences) != len(evidence_scores):
        raise ValueError("Evidence scores and confidences must have the same length.")
    normalized_confidences = [max(0.0, min(1.0, float(value))) for value in confidences]
    confidence_sum = sum(normalized_confidences)
    if confidence_sum <= 0:
        return base_score
    evidence_score = sum(
        score * confidence
        for score, confidence in zip(evidence_scores, normalized_confidences)
    )
    evidence_score /= confidence_sum
    coverage = min(1.0, confidence_sum / len(normalized_confidences))
    evidence_weight = OPTIONAL_EVIDENCE_WEIGHT * coverage
    return (base_score * (1.0 - evidence_weight)) + (evidence_score * evidence_weight)


def _pair_key(walnut_id_1: int, walnut_id_2: int) -> tuple[int, int]:
    return (
        (walnut_id_1, walnut_id_2)
        if walnut_id_1 < walnut_id_2
        else (walnut_id_2, walnut_id_1)
    )


def _load_matching_snapshot(variety_id: int) -> _MatchingSnapshot:
    walnuts = repositories.list_walnuts(variety_id=variety_id, include_locked=True)
    blacklist = frozenset(
        _pair_key(int(row["walnut_id_1"]), int(row["walnut_id_2"]))
        for row in repositories.list_blacklist_pairs(variety_id=variety_id)
    )
    return _MatchingSnapshot(
        walnuts=walnuts,
        blacklisted_pairs=blacklist,
        image_features=repositories.list_walnut_image_features_for_variety(
            variety_id,
            OPENCV_FEATURE_VERSION,
        ),
        mesh_features=repositories.list_walnut_mesh_features_for_variety(
            variety_id,
            MESH_FEATURE_VERSION,
        ),
    )


def _reverse_image_similarity(similarity: WalnutImageSimilarity) -> WalnutImageSimilarity:
    return WalnutImageSimilarity(
        score=similarity.score,
        matched_faces=similarity.matched_faces,
        base_faces=similarity.candidate_faces,
        candidate_faces=similarity.base_faces,
    )


def _get_pair_evidence(
    base_walnut_id: int,
    candidate_walnut_id: int,
    snapshot: _MatchingSnapshot,
    cache: dict[tuple[int, int], _PairEvidence],
) -> _PairEvidence:
    key = _pair_key(base_walnut_id, candidate_walnut_id)
    if key not in cache:
        cache[key] = _PairEvidence(
            image_similarity=image_similarity_from_features(
                snapshot.image_features.get(key[0], []),
                snapshot.image_features.get(key[1], []),
            ),
            mesh_similarity=mesh_similarity_from_features(
                snapshot.mesh_features.get(key[0], []),
                snapshot.mesh_features.get(key[1], []),
            ),
        )
    evidence = cache[key]
    if base_walnut_id == key[0]:
        return evidence
    return _PairEvidence(
        image_similarity=(
            _reverse_image_similarity(evidence.image_similarity)
            if evidence.image_similarity is not None
            else None
        ),
        mesh_similarity=evidence.mesh_similarity,
    )


def _candidate_from_pair(
    base: dict,
    candidate: dict,
    tolerance_mm: float,
    evidence: _PairEvidence,
) -> CandidateMatch:
    score = build_score(base, candidate, tolerance_mm)
    evidence_scores: list[float] = []
    evidence_confidences: list[float] = []
    if evidence.image_similarity is not None:
        evidence_scores.append(evidence.image_similarity.score)
        evidence_confidences.append(
            min(1.0, evidence.image_similarity.matched_faces / MAX_IMAGE_FACE_COUNT)
        )
    if evidence.mesh_similarity is not None:
        evidence_scores.append(evidence.mesh_similarity.score)
        evidence_confidences.append(1.0)
    total_score = _combine_optional_evidence(
        score["total_score"],
        evidence_scores,
        evidence_confidences,
    )
    image_similarity = evidence.image_similarity
    mesh_similarity = evidence.mesh_similarity
    return CandidateMatch(
        walnut_id=int(candidate["id"]),
        serial_no=candidate["serial_no"],
        total_score=total_score,
        dimension_score=score["dimension_score"],
        weight_bonus=score["weight_bonus"],
        defect_penalty=score["defect_penalty"],
        edge_diff=score["edge_diff"],
        belly_diff=score["belly_diff"],
        height_diff=score["height_diff"],
        weight_diff=score["weight_diff"],
        defect_level=candidate["defect_level"],
        image_similarity=image_similarity.score if image_similarity else None,
        image_matched_faces=image_similarity.matched_faces if image_similarity else 0,
        image_base_faces=image_similarity.base_faces if image_similarity else 0,
        image_candidate_faces=image_similarity.candidate_faces if image_similarity else 0,
        mesh_similarity=mesh_similarity.score if mesh_similarity else None,
        is_strict_match=within_tolerance(base, candidate, tolerance_mm),
    )


def _get_candidates_from_snapshot(
    walnut: dict,
    snapshot: _MatchingSnapshot,
    limit: int | None,
    minimum_score: float | None,
    screening_multiplier: float,
    evidence_cache: dict[tuple[int, int], _PairEvidence],
) -> list[CandidateMatch]:
    if walnut["is_locked"]:
        return []
    tolerance_mm = float(walnut["tolerance_mm"])
    candidates: list[CandidateMatch] = []
    for other in snapshot.walnuts:
        if other["id"] == walnut["id"] or other["is_locked"]:
            continue
        if not within_tolerance(
            walnut,
            other,
            tolerance_mm,
            multiplier=screening_multiplier,
        ):
            continue
        if _pair_key(int(walnut["id"]), int(other["id"])) in snapshot.blacklisted_pairs:
            continue
        evidence = _get_pair_evidence(
            int(walnut["id"]),
            int(other["id"]),
            snapshot,
            evidence_cache,
        )
        candidate = _candidate_from_pair(walnut, other, tolerance_mm, evidence)
        if minimum_score is not None and candidate.total_score < minimum_score:
            continue
        candidates.append(candidate)

    candidates.sort(key=lambda item: (-item.total_score, item.weight_diff, item.serial_no))
    return candidates if limit is None else candidates[:limit]


def get_candidates_for_walnut(
    walnut_id: int,
    limit: int | None = DEFAULT_CANDIDATE_LIMIT,
    screening_multiplier: float = DEFAULT_SCREENING_TOLERANCE_MULTIPLIER,
    minimum_score: float | None = None,
) -> list[CandidateMatch]:
    normalized_limit = _validate_limit(limit)
    normalized_multiplier = _validate_screening_multiplier(screening_multiplier)
    normalized_minimum_score = _validate_minimum_score(minimum_score)
    walnut = repositories.get_walnut(walnut_id)
    if walnut is None or walnut["is_locked"]:
        return []
    if normalized_limit == 0:
        return []
    snapshot = _load_matching_snapshot(int(walnut["variety_id"]))
    snapshot_walnut = next(
        (item for item in snapshot.walnuts if item["id"] == walnut_id),
        None,
    )
    if snapshot_walnut is None:
        return []
    return _get_candidates_from_snapshot(
        snapshot_walnut,
        snapshot,
        normalized_limit,
        normalized_minimum_score,
        normalized_multiplier,
        {},
    )


def get_candidates_for_variety(
    variety_id: int,
    limit: int | None = DEFAULT_CANDIDATE_LIMIT,
    screening_multiplier: float = DEFAULT_SCREENING_TOLERANCE_MULTIPLIER,
    minimum_score: float | None = None,
) -> dict[int, list[CandidateMatch]]:
    normalized_limit = _validate_limit(limit)
    normalized_multiplier = _validate_screening_multiplier(screening_multiplier)
    normalized_minimum_score = _validate_minimum_score(minimum_score)
    snapshot = _load_matching_snapshot(variety_id)
    evidence_cache: dict[tuple[int, int], _PairEvidence] = {}
    return {
        int(walnut["id"]): _get_candidates_from_snapshot(
            walnut,
            snapshot,
            normalized_limit,
            normalized_minimum_score,
            normalized_multiplier,
            evidence_cache,
        )
        for walnut in snapshot.walnuts
    }


def get_matching_view_data(
    variety_id: int,
    limit: int | None = DEFAULT_CANDIDATE_LIMIT,
    minimum_score: float | None = MIN_RECOMMENDATION_SCORE,
    screening_multiplier: float = DEFAULT_SCREENING_TOLERANCE_MULTIPLIER,
) -> tuple[list[dict], dict[int, list[CandidateMatch]]]:
    """Load the walnut rows and candidate board from one matching snapshot."""
    normalized_limit = _validate_limit(limit)
    normalized_minimum_score = _validate_minimum_score(minimum_score)
    normalized_multiplier = _validate_screening_multiplier(screening_multiplier)
    snapshot = _load_matching_snapshot(variety_id)
    evidence_cache: dict[tuple[int, int], _PairEvidence] = {}
    candidates = {
        int(walnut["id"]): _get_candidates_from_snapshot(
            walnut,
            snapshot,
            normalized_limit,
            normalized_minimum_score,
            normalized_multiplier,
            evidence_cache,
        )
        for walnut in snapshot.walnuts
    }
    return snapshot.walnuts, candidates


def lock_candidate_pair(
    variety_id: int,
    walnut_id_1: int,
    walnut_id_2: int,
    minimum_score: float = MIN_RECOMMENDATION_SCORE,
) -> int:
    """Lock only a currently recommended, strict-tolerance candidate pair."""
    candidates = get_candidates_for_walnut(
        walnut_id_1,
        limit=None,
        minimum_score=minimum_score,
    )
    candidate = next((item for item in candidates if item.walnut_id == walnut_id_2), None)
    if candidate is None:
        raise ValueError("该配对未达到当前推荐门槛。")
    if not candidate.is_strict_match:
        raise ValueError("该配对超出品种统一偏差，不能直接锁定。")
    return repositories.lock_pair(variety_id, walnut_id_1, walnut_id_2)


def _select_non_overlapping_pairs(possible_pairs: list[PairMatch]) -> list[PairMatch]:
    """Select a deterministic maximum-score matching for small candidate graphs.

    Exact bitmask dynamic programming is practical for the usual small pairing
    batch. Larger batches use the deterministic greedy fallback to avoid an
    exponential memory/time spike.
    """
    if not possible_pairs:
        return []

    ordered_pairs = sorted(
        possible_pairs,
        key=lambda pair: (
            -pair.candidate.total_score,
            pair.candidate.weight_diff,
            pair.walnut_id_1,
            pair.walnut_id_2,
        ),
    )
    unique_pairs: dict[tuple[int, int], PairMatch] = {}
    for pair in ordered_pairs:
        key = _pair_key(pair.walnut_id_1, pair.walnut_id_2)
        unique_pairs.setdefault(key, pair)

    walnut_ids = sorted({walnut_id for pair in unique_pairs for walnut_id in pair})
    if len(walnut_ids) > 20:
        graph = nx.Graph()
        graph.add_nodes_from(walnut_ids)
        for index, key in enumerate(sorted(unique_pairs)):
            pair = unique_pairs[key]
            # The tiny deterministic tie-breaker never changes a meaningful score.
            tie_breaker = (len(unique_pairs) - index) * 1e-10
            graph.add_edge(key[0], key[1], weight=pair.candidate.total_score + tie_breaker)
        large_selected_keys = sorted(
            _pair_key(int(left), int(right))
            for left, right in nx.max_weight_matching(graph, maxcardinality=False, weight="weight")
        )
        return [unique_pairs[key] for key in large_selected_keys]

    def better(
        left: tuple[float, tuple[tuple[int, int], ...]],
        right: tuple[float, tuple[tuple[int, int], ...]],
    ) -> bool:
        if left[0] > right[0] + 1e-9:
            return True
        if abs(left[0] - right[0]) <= 1e-9:
            return left[1] < right[1]
        return False

    @cache
    def solve(mask: int) -> tuple[float, tuple[tuple[int, int], ...]]:
        if mask == 0:
            return 0.0, ()
        lowest_bit = mask & -mask
        left_index = lowest_bit.bit_length() - 1
        left_id = walnut_ids[left_index]
        best = solve(mask ^ lowest_bit)
        remaining_mask = mask ^ lowest_bit
        while remaining_mask:
            right_bit = remaining_mask & -remaining_mask
            right_index = right_bit.bit_length() - 1
            right_id = walnut_ids[right_index]
            pair = unique_pairs.get((left_id, right_id))
            if pair is not None:
                rest_score, rest_pairs = solve(mask ^ lowest_bit ^ right_bit)
                pair_key = (left_id, right_id)
                candidate = (
                    rest_score + pair.candidate.total_score,
                    tuple(sorted((*rest_pairs, pair_key))),
                )
                if better(candidate, best):
                    best = candidate
            remaining_mask ^= right_bit
        return best

    _, exact_selected_keys = solve((1 << len(walnut_ids)) - 1)
    return [unique_pairs[key] for key in exact_selected_keys]


def get_non_overlapping_pairs(
    variety_id: int,
    minimum_score: float = MIN_RECOMMENDATION_SCORE,
    screening_multiplier: float = DEFAULT_SCREENING_TOLERANCE_MULTIPLIER,
) -> list[PairMatch]:
    """Return deterministic, highest-score-first pairs without reused walnuts.

    The existing candidate board intentionally shows repeated candidates. This
    separate helper is for workflows that need a one-to-one recommendation.
    """
    normalized_minimum_score = _validate_minimum_score(minimum_score)
    assert normalized_minimum_score is not None
    candidates_by_walnut = get_candidates_for_variety(
        variety_id,
        limit=None,
        screening_multiplier=screening_multiplier,
        minimum_score=normalized_minimum_score,
    )
    possible_pairs: list[PairMatch] = []
    for base_id, candidates in candidates_by_walnut.items():
        for candidate in candidates:
            left, right = _pair_key(base_id, candidate.walnut_id)
            if base_id != left or candidate.total_score < normalized_minimum_score:
                continue
            possible_pairs.append(PairMatch(left, right, candidate))

    return _select_non_overlapping_pairs(possible_pairs)
