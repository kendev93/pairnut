"""Shared domain models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SerialMode(StrEnum):
    MANUAL = "manual"
    AUTO = "auto"


class DefectLevel(StrEnum):
    NONE = "none"
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


@dataclass(slots=True)
class CandidateMatch:
    walnut_id: int
    serial_no: str
    total_score: float
    dimension_score: float
    weight_bonus: float
    defect_penalty: float
    edge_diff: float
    belly_diff: float
    height_diff: float
    weight_diff: float
    defect_level: str
