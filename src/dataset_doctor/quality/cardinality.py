"""Cardinality findings: constants, identifier-like columns, messy labels."""

from __future__ import annotations

from typing import TYPE_CHECKING

import polars as pl

from dataset_doctor.models.findings import Finding, FindingCategory, Severity
from dataset_doctor.utils import format_count, format_pct

if TYPE_CHECKING:
    from dataset_doctor.models.profile import ColumnProfile
    from dataset_doctor.models.thresholds import Thresholds
    from dataset_doctor.quality.context import AnalysisContext


def run(ctx: AnalysisContext) -> list[Finding]:
    """Cardinality checks for every column."""
    findings: list[Finding] = []
    for column in ctx.profile.columns:
        findings.extend(_constant_finding(ctx, column))
        if not column.constant:
            findings.extend(_identifier_findings(column, ctx.thresholds))
            findings.extend(_variant_label_finding(ctx, column, ctx.thresholds))
    return findings


def _constant_finding(
    ctx: AnalysisContext,
    column: ColumnProfile,
) -> list[Finding]:
    non_null = column.row_count - column.null_count
    if not column.constant or non_null == 0:
        return []

    value: str | None
    if column.most_frequent:
        value = column.most_frequent[0].value
    else:
        series = ctx.df.get_column(column.name).drop_nulls()
        first = series.first()
        value = str(first) if first is not None else None
    shown = repr(value) if value is not None else "<unrenderable>"

    return [
        Finding(
            severity=Severity.WARNING,
            category=FindingCategory.CARDINALITY,
            column=column.name,
            description=f"'{column.name}' is constant: every non-null row equals {shown}",
            evidence=(
                f"1 distinct value across {format_count(non_null)} non-null rows "
                f"({format_pct(column.unique_pct, 1)} uniqueness)."
            ),
            confidence=1.0,
            recommendation="Drop the column or find out why it never varies in this extract.",
        )
    ]


def _identifier_findings(
    column: ColumnProfile,
    thresholds: Thresholds,
) -> list[Finding]:
    """Warn on 'categorical' columns that are really identifiers; notice high cardinality."""
    non_null = column.row_count - column.null_count
    if (
        column.semantic_type not in ("categorical", "text")
        or non_null < thresholds.cardinality_min_rows
    ):
        return []

    unique_ratio = column.unique_count / non_null
    findings: list[Finding] = []
    if column.unique_count == non_null and column.unique_count > 50:
        findings.append(
            Finding(
                severity=Severity.WARNING,
                category=FindingCategory.CARDINALITY,
                column=column.name,
                description=(
                    f"'{column.name}' has {format_count(column.unique_count)} values "
                    f"and every one of them is unique"
                ),
                evidence=(
                    f"{format_count(column.unique_count)} distinct values in "
                    f"{format_count(non_null)} rows (100% uniqueness) - typical of "
                    f"an ID/primary-key column stored as text."
                ),
                confidence=0.9,
                recommendation=(
                    "Treat as an identifier: exclude it from categorical encodings "
                    "and aggregations."
                ),
            )
        )
    elif unique_ratio >= thresholds.id_like_unique_ratio:
        findings.append(
            Finding(
                severity=Severity.NOTICE,
                category=FindingCategory.CARDINALITY,
                column=column.name,
                description=(
                    f"'{column.name}' has very high cardinality "
                    f"({format_count(column.unique_count)} distinct values, "
                    f"{unique_ratio:.0%} of rows)"
                ),
                evidence=(
                    "High-cardinality text columns behave like identifiers and are "
                    "poor categorical features."
                ),
                confidence=0.85,
                recommendation=(
                    "Verify whether this is a key; exclude from group-bys and encodings."
                ),
            )
        )
    return findings


def _variant_label_finding(
    ctx: AnalysisContext,
    column: ColumnProfile,
    thresholds: Thresholds,
) -> list[Finding]:
    """Detect category labels that differ only by whitespace or letter case."""
    if column.semantic_type != "categorical":
        return []
    raw_unique = column.unique_count
    if not (2 <= raw_unique <= thresholds.variant_max_unique):
        return []

    series = (
        ctx.df.get_column(column.name)
        .drop_nulls()
        .cast(pl.String)
        .str.strip_chars()
        .str.to_lowercase()
    )
    normalized_unique = int(series.n_unique())
    if normalized_unique >= raw_unique:
        return []

    return [
        Finding(
            severity=Severity.WARNING,
            category=FindingCategory.CARDINALITY,
            column=column.name,
            description=(
                f"'{column.name}' has inconsistent category labels: "
                f"{format_count(raw_unique)} distinct values collapse to "
                f"{format_count(normalized_unique)} after trimming whitespace "
                f"and case-folding"
            ),
            evidence=(
                "Values differing only by surrounding spaces or letter case "
                "(e.g. ' NY ' vs 'NY' vs 'ny') split otherwise identical categories."
            ),
            confidence=0.85,
            recommendation=(
                "Normalize labels (strip + lowercase or a mapping table) before "
                "grouping or encoding."
            ),
        )
    ]
