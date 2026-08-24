"""Numeric distribution findings: outliers, skewness, zero inflation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dataset_doctor.models.findings import Finding, FindingCategory, Severity
from dataset_doctor.utils import format_count, format_number, format_pct

if TYPE_CHECKING:
    import polars as pl

    from dataset_doctor.models.profile import ColumnProfile
    from dataset_doctor.models.thresholds import Thresholds
    from dataset_doctor.quality.context import AnalysisContext


def run(ctx: AnalysisContext) -> list[Finding]:
    """Distributional checks for numeric columns with enough data."""
    thresholds = ctx.thresholds
    findings: list[Finding] = []

    for column in ctx.profile.columns:
        if column.semantic_type != "numeric":
            continue
        non_null_count = column.row_count - column.null_count
        if non_null_count < thresholds.stats_min_rows:
            continue

        findings.extend(_outlier_finding(ctx, column, non_null_count, thresholds))
        findings.extend(_skewness_finding(column, non_null_count, thresholds))
        findings.extend(_zero_inflation_finding(ctx, column, non_null_count, thresholds))
    return findings


def _outlier_finding(
    ctx: AnalysisContext,
    column: ColumnProfile,
    non_null_count: int,
    thresholds: Thresholds,
) -> list[Finding]:
    """Flag values beyond the Tukey fences Q1 - f*IQR / Q3 + f*IQR."""
    if column.q1_value is None or column.q3_value is None:
        return []
    iqr = column.q3_value - column.q1_value
    factor = thresholds.outlier_iqr_factor
    lower = column.q1_value - factor * iqr
    upper = column.q3_value + factor * iqr

    series = ctx.df.get_column(column.name).drop_nulls()
    outside = series.filter((series < lower) | (series > upper))
    count = outside.len()
    pct = count / non_null_count * 100.0

    if count == 0 or not (thresholds.outlier_min_pct <= pct <= thresholds.outlier_max_pct):
        return []

    return [
        Finding(
            severity=Severity.WARNING,
            category=FindingCategory.DISTRIBUTION,
            column=column.name,
            description=(
                f"'{column.name}' contains {format_count(count)} values outside the "
                f"IQR-based expected range [{format_number(lower)}, {format_number(upper)}]"
            ),
            evidence=(
                f"Fences are Q1 - {factor}xIQR and Q3 + {factor}xIQR; "
                f"{format_pct(pct, 2)} of {format_count(non_null_count)} non-null values "
                f"fall outside them."
            ),
            confidence=0.75,
            recommendation=(
                "Inspect the flagged values: they may be data-entry errors or "
                "genuine tail events. Consider robust scaling or capping."
            ),
        )
    ]


def _skewness_finding(
    column: ColumnProfile,
    non_null_count: int,
    thresholds: Thresholds,
) -> list[Finding]:
    """Flag strongly asymmetric numeric distributions."""
    skew = column.skewness
    if skew is None:
        return []

    magnitude = abs(skew)
    direction = "right" if skew > 0 else "left"
    if magnitude >= thresholds.skew_warning_abs:
        severity = Severity.WARNING
        confidence = 0.9
    elif magnitude >= thresholds.skew_notice_abs:
        severity = Severity.NOTICE
        confidence = 0.7
    else:
        return []

    return [
        Finding(
            severity=severity,
            category=FindingCategory.DISTRIBUTION,
            column=column.name,
            description=(
                f"'{column.name}' has a skewed distribution (skewness = {format_number(skew)})"
            ),
            evidence=(
                f"Sample skewness over {format_count(non_null_count)} non-null values; "
                f"|{format_number(thresholds.skew_warning_abs)}|+ indicates strong "
                f"asymmetry to the {direction}."
            ),
            confidence=confidence,
            recommendation=(
                f"The tail points to the {direction}; consider a log/sqrt transform "
                f"for modeling or report medians instead of means."
            ),
        )
    ]


def _zero_inflation_finding(
    ctx: AnalysisContext,
    column: ColumnProfile,
    non_null_count: int,
    thresholds: Thresholds,
) -> list[Finding]:
    """Notice heavily zero-dominated numeric columns."""
    series: pl.Series = ctx.df.get_column(column.name).drop_nulls()
    zeros = int((series == 0).sum())
    pct = zeros / non_null_count * 100.0
    if zeros == 0 or pct < thresholds.zero_inflation_pct:
        return []

    return [
        Finding(
            severity=Severity.NOTICE,
            category=FindingCategory.DISTRIBUTION,
            column=column.name,
            description=(
                f"'{column.name}' is heavily zero-inflated ({format_pct(pct)} exact zeros)"
            ),
            evidence=(
                f"{format_count(zeros)} of {format_count(non_null_count)} non-null "
                f"values equal exactly 0."
            ),
            confidence=0.85,
            recommendation=(
                "Consider modeling this as presence plus amount, or use "
                "zero-inflated methods; plain means will be misleading."
            ),
        )
    ]
