"""Missingness findings per column, with a severity ladder."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dataset_doctor.models.findings import Finding, FindingCategory, Severity
from dataset_doctor.utils import format_count, format_pct

if TYPE_CHECKING:
    from dataset_doctor.models.profile import ColumnProfile
    from dataset_doctor.models.thresholds import Thresholds
    from dataset_doctor.quality.context import AnalysisContext


_RECOMMENDATIONS = {
    "empty": ("Drop this column or fix its source; it currently carries no information."),
    "extreme": (
        "Investigate why values are missing (collection bug vs. genuinely optional); "
        "consider excluding the column or documenting the missingness mechanism."
    ),
    "high": (
        "Check whether missingness correlates with other fields and decide on an "
        "explicit strategy: imputation, a sentinel value, or exclusion."
    ),
    "moderate": ("Usually acceptable, but confirm downstream consumers handle nulls correctly."),
}


def run(ctx: AnalysisContext) -> list[Finding]:
    """Emit at most one missingness finding per column."""
    thresholds = ctx.thresholds
    findings: list[Finding] = []

    for column in ctx.profile.columns:
        severity, kind = _classify(column, thresholds)
        if severity is None:
            continue
        findings.append(
            Finding(
                severity=severity,
                category=FindingCategory.MISSINGNESS,
                column=column.name,
                description=(
                    f"'{column.name}' is {format_pct(column.null_pct)} missing ({_label(kind)})"
                ),
                evidence=(
                    f"{format_count(column.null_count)} of "
                    f"{format_count(column.row_count)} rows have no value."
                ),
                confidence=1.0,
                recommendation=_RECOMMENDATIONS[kind],
            )
        )
    return findings


def _classify(
    column: ColumnProfile,
    thresholds: Thresholds,
) -> tuple[Severity | None, str]:
    if column.row_count > 0 and column.null_count == column.row_count:
        return Severity.CRITICAL, "empty"
    if column.null_pct >= thresholds.missing_critical_pct:
        return Severity.CRITICAL, "extreme"
    if column.null_pct >= thresholds.missing_warning_pct:
        return Severity.WARNING, "high"
    if column.null_pct >= thresholds.missing_notice_pct:
        return Severity.NOTICE, "moderate"
    return None, "none"


def _label(kind: str) -> str:
    return {
        "empty": "completely empty",
        "extreme": "extremely high",
        "high": "high",
        "moderate": "moderate",
    }[kind]
