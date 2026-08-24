"""The health score: severity-weighted points, capped per category.

Formula (deterministic and fully documented in ``docs/health-score.md``):

1. Each finding contributes points based on its severity
   (critical/warning/notice, configurable via ``severity_points``).
2. Points are summed per scoring category.
3. Each category's contribution is capped (``category_caps``) so a single
   pathological category cannot dominate the score.
4. ``score = clamp(100 - sum(deductions), 0, 100)``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dataset_doctor.models.findings import CATEGORY_ORDER, FindingCategory, Severity
from dataset_doctor.models.score import (
    HealthScore,
    ScoreCategoryBreakdown,
    score_grade,
)

if TYPE_CHECKING:
    from dataset_doctor.models.findings import Finding
    from dataset_doctor.models.thresholds import Thresholds

CATEGORY_LABELS: dict[FindingCategory, str] = {
    FindingCategory.MISSINGNESS: "Missing values",
    FindingCategory.DUPLICATES: "Duplicate rows",
    FindingCategory.DISTRIBUTION: "Outliers & distribution",
    FindingCategory.SCHEMA: "Schema & types",
    FindingCategory.CARDINALITY: "Cardinality & constants",
}

#: CategoryCaps field for each scoring category.
_CAP_FIELDS: dict[FindingCategory, str] = {
    FindingCategory.MISSINGNESS: "missingness",
    FindingCategory.DUPLICATES: "duplicates",
    FindingCategory.DISTRIBUTION: "distribution",
    FindingCategory.SCHEMA: "schema_issues",
    FindingCategory.CARDINALITY: "cardinality",
}


def compute_health_score(findings: list[Finding], thresholds: Thresholds) -> HealthScore:
    """Aggregate findings into an explainable 0-100 score."""
    raw_points = dict.fromkeys(FindingCategory, 0)
    finding_counts = dict.fromkeys(FindingCategory, 0)

    for finding in findings:
        category = finding.category
        raw_points[category] += _severity_points(thresholds, finding.severity)
        finding_counts[category] += 1

    breakdown = [
        ScoreCategoryBreakdown(
            category=category,
            label=CATEGORY_LABELS[category],
            points=raw_points[category],
            cap=_category_cap(thresholds, category),
            deduction=min(raw_points[category], _category_cap(thresholds, category)),
            finding_count=finding_counts[category],
        )
        for category in FindingCategory
    ]
    total_deduction = sum(item.deduction for item in breakdown)
    score = max(0, min(100, 100 - total_deduction))
    deductions = sorted(
        (item for item in breakdown if item.deduction > 0),
        key=lambda item: (-item.deduction, CATEGORY_ORDER[item.category]),
    )

    return HealthScore(
        score=score,
        grade=score_grade(score),
        total_deduction=total_deduction,
        deductions=deductions,
    )


def _severity_points(thresholds: Thresholds, severity: Severity) -> int:
    points: int = getattr(thresholds.severity_points, severity.value)
    return points


def _category_cap(thresholds: Thresholds, category: FindingCategory) -> int:
    cap: int = getattr(thresholds.category_caps, _CAP_FIELDS[category])
    return cap
