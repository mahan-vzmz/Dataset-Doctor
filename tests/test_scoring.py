"""Health score: exact arithmetic, caps, grades, and floor behavior."""

from __future__ import annotations

import pytest

from dataset_doctor.models.findings import Finding, FindingCategory, Severity
from dataset_doctor.models.thresholds import CategoryCaps, SeverityPoints, Thresholds
from dataset_doctor.scoring.scorer import compute_health_score


def _finding(
    severity: Severity,
    category: FindingCategory,
    column: str | None = "c",
) -> Finding:
    return Finding(
        severity=severity,
        category=category,
        column=column,
        description="d",
        evidence="e",
        confidence=1.0,
        recommendation="r",
    )


def test_perfect_dataset_scores_100() -> None:
    score = compute_health_score([], Thresholds())
    assert score.score == 100
    assert score.grade == "GOOD"
    assert score.deductions == []
    assert score.is_perfect


def test_single_critical_deducts_10() -> None:
    findings = [_finding(Severity.CRITICAL, FindingCategory.MISSINGNESS)]
    score = compute_health_score(findings, Thresholds())
    assert score.score == 90
    item = score.deductions[0]
    assert item.category is FindingCategory.MISSINGNESS
    assert (item.points, item.cap, item.deduction) == (10, 35, 10)


def test_category_cap_is_applied() -> None:
    # 5 critical missingness findings = 50 raw points, capped at 35.
    findings = [
        _finding(Severity.CRITICAL, FindingCategory.MISSINGNESS, column=f"c{i}") for i in range(5)
    ]
    score = compute_health_score(findings, Thresholds())
    assert score.score == 100 - 35
    assert score.deductions[0].points == 50
    assert score.deductions[0].deduction == 35


def test_severity_points_are_configurable() -> None:
    thresholds = Thresholds(severity_points=SeverityPoints(critical=20, warning=8, notice=2))
    findings = [_finding(Severity.WARNING, FindingCategory.DUPLICATES)]
    score = compute_health_score(findings, thresholds)
    assert score.score == 92
    assert score.deductions[0].points == 8


def test_category_caps_are_configurable() -> None:
    thresholds = Thresholds(category_caps=CategoryCaps(missingness=5))
    findings = [_finding(Severity.CRITICAL, FindingCategory.MISSINGNESS)]
    score = compute_health_score(findings, thresholds)
    assert score.score == 95  # capped at 5 instead of the full 10
    assert score.deductions[0].cap == 5


def test_all_categories_saturated_reaches_zero() -> None:
    findings = [
        *[
            _finding(Severity.CRITICAL, FindingCategory.MISSINGNESS, column=f"m{i}")
            for i in range(4)
        ],
        *[_finding(Severity.CRITICAL, FindingCategory.DUPLICATES)],
        *[
            _finding(Severity.CRITICAL, FindingCategory.DISTRIBUTION, column=f"d{i}")
            for i in range(2)
        ],
        *[_finding(Severity.CRITICAL, FindingCategory.SCHEMA, column=f"s{i}") for i in range(2)],
        _finding(Severity.CRITICAL, FindingCategory.CARDINALITY),
    ]
    score = compute_health_score(findings, Thresholds())
    # 40->35, 10->15? no: duplicates raw 10 cap 15 => 10; distribution 20/20;
    # schema 20/20; cardinality 10/10. Total = 35+10+20+20+10 = 95.
    assert score.score == 5
    assert score.total_deduction == 95


def test_floor_at_zero_is_possible_with_custom_caps() -> None:
    thresholds = Thresholds(
        category_caps=CategoryCaps(missingness=100),
        severity_points=SeverityPoints(critical=30),
    )
    findings = [
        _finding(Severity.CRITICAL, FindingCategory.MISSINGNESS, column=f"c{i}") for i in range(4)
    ]  # raw 120, cap 100
    score = compute_health_score(findings, thresholds)
    assert score.score == 0
    assert score.grade == "CRITICAL"


@pytest.mark.parametrize(
    ("score_value", "grade"),
    [
        (100, "GOOD"),
        (85, "GOOD"),
        (84, "FAIR"),
        (70, "FAIR"),
        (69, "POOR"),
        (50, "POOR"),
        (49, "CRITICAL"),
        (0, "CRITICAL"),
    ],
)
def test_grade_boundaries(score_value: int, grade: str) -> None:
    from dataset_doctor.models.score import score_grade

    assert score_grade(score_value) == grade


def test_deductions_sorted_by_amount_desc() -> None:
    findings = [
        _finding(Severity.WARNING, FindingCategory.MISSINGNESS),  # -4
        _finding(Severity.CRITICAL, FindingCategory.CARDINALITY),  # -10
        _finding(Severity.NOTICE, FindingCategory.DUPLICATES),  # -1
    ]
    score = compute_health_score(findings, Thresholds())
    amounts = [item.deduction for item in score.deductions]
    assert amounts == sorted(amounts, reverse=True)
    assert amounts == [10, 4, 1]
