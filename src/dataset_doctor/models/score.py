"""Health score model with a fully itemized, explainable breakdown."""

from __future__ import annotations

from pydantic import BaseModel, Field

from dataset_doctor.models.findings import FindingCategory


def score_grade(score: int) -> str:
    """Map a numeric score to a deterministic grade label."""
    if score >= 85:
        return "GOOD"
    if score >= 70:
        return "FAIR"
    if score >= 50:
        return "POOR"
    return "CRITICAL"


class ScoreCategoryBreakdown(BaseModel):
    """Deduction accounting for one scoring category."""

    category: FindingCategory
    label: str
    #: Raw points accumulated from findings before capping.
    points: int = Field(ge=0)
    #: Maximum deduction this category may contribute.
    cap: int = Field(ge=0)
    #: ``min(points, cap)`` - the amount actually deducted.
    deduction: int = Field(ge=0)
    finding_count: int = Field(ge=0)


class HealthScore(BaseModel):
    """Deterministic score in ``[0, 100]`` plus its itemized deductions."""

    score: int = Field(ge=0, le=100)
    grade: str
    total_deduction: int = Field(ge=0)
    #: Only categories with a non-zero deduction, sorted by deduction desc.
    deductions: list[ScoreCategoryBreakdown] = Field(default_factory=list)

    @property
    def is_perfect(self) -> bool:
        return self.total_deduction == 0
