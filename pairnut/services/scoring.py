"""Scoring functions for walnut candidates."""

from __future__ import annotations

import math

from ..domain.models import DefectLevel


DEFECT_PENALTIES = {
    DefectLevel.NONE.value: 0.0,
    DefectLevel.LIGHT.value: 5.0,
    DefectLevel.MEDIUM.value: 12.0,
    DefectLevel.HEAVY.value: 20.0,
}

MIN_RECOMMENDATION_SCORE = 70.0
HIGH_RECOMMENDATION_SCORE = 85.0


def recommendation_label(score: float) -> str:
    """Return a user-facing explanation for a recommendation score."""
    normalized_score = float(score)
    if normalized_score >= HIGH_RECOMMENDATION_SCORE:
        return "优先推荐"
    if normalized_score >= MIN_RECOMMENDATION_SCORE:
        return "可人工确认"
    return "不建议"


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def dimension_component(diff: float, tolerance_mm: float) -> float:
    if tolerance_mm <= 0:
        return 100.0 if diff == 0 else 0.0
    return clamp(100.0 * (1.0 - (diff / tolerance_mm)))


def weight_bonus(weight_diff: float) -> float:
    # 10g 内线性衰减到 0，越接近越高。
    return clamp(100.0 - (weight_diff * 10.0))


def defect_penalty(defect_level_1: str, defect_level_2: str) -> float:
    penalty_1 = DEFECT_PENALTIES.get(defect_level_1, 0.0)
    penalty_2 = DEFECT_PENALTIES.get(defect_level_2, 0.0)
    return (penalty_1 + penalty_2) / 2.0


def within_tolerance(base: dict, candidate: dict, tolerance_mm: float, multiplier: float = 1.0) -> bool:
    if not math.isfinite(float(tolerance_mm)) or not math.isfinite(float(multiplier)) or multiplier <= 0:
        raise ValueError("tolerance and multiplier must be finite; multiplier must be positive.")
    screening_tolerance = tolerance_mm * multiplier
    return (
        abs(base["edge_mm"] - candidate["edge_mm"]) <= screening_tolerance
        and abs(base["belly_mm"] - candidate["belly_mm"]) <= screening_tolerance
        and abs(base["height_mm"] - candidate["height_mm"]) <= screening_tolerance
    )


def build_score(base: dict, candidate: dict, tolerance_mm: float) -> dict[str, float]:
    edge_diff = abs(base["edge_mm"] - candidate["edge_mm"])
    belly_diff = abs(base["belly_mm"] - candidate["belly_mm"])
    height_diff = abs(base["height_mm"] - candidate["height_mm"])
    current_weight_diff = abs(base["weight_g"] - candidate["weight_g"])

    dimension_score = (
        dimension_component(edge_diff, tolerance_mm)
        + dimension_component(belly_diff, tolerance_mm)
        + dimension_component(height_diff, tolerance_mm)
    ) / 3.0
    current_weight_bonus = weight_bonus(current_weight_diff)
    current_defect_penalty = defect_penalty(base["defect_level"], candidate["defect_level"])
    total_score = clamp((dimension_score * 0.8) + (current_weight_bonus * 0.2) - current_defect_penalty)

    return {
        "total_score": total_score,
        "dimension_score": dimension_score,
        "weight_bonus": current_weight_bonus,
        "defect_penalty": current_defect_penalty,
        "edge_diff": edge_diff,
        "belly_diff": belly_diff,
        "height_diff": height_diff,
        "weight_diff": current_weight_diff,
    }
