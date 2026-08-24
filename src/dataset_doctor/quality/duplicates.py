"""Duplicate-row finding (the count itself comes from :mod:`dataset_doctor.io`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dataset_doctor.models.findings import Finding, FindingCategory, Severity
from dataset_doctor.utils import format_count, format_pct

if TYPE_CHECKING:
    from dataset_doctor.quality.context import AnalysisContext


def run(ctx: AnalysisContext) -> list[Finding]:
    """Flag datasets whose exact duplicate share crosses the warning threshold."""
    profile = ctx.profile
    duplicates = profile.duplicate_row_count
    if duplicates == 0:
        return []

    thresholds = ctx.thresholds
    crosses = (
        profile.duplicate_pct >= thresholds.duplicate_warning_pct
        or duplicates >= thresholds.duplicate_warning_min_rows
    )
    if not crosses:
        return []

    unique_rows = profile.row_count - duplicates
    return [
        Finding(
            severity=Severity.WARNING,
            category=FindingCategory.DUPLICATES,
            column=None,
            description=(
                f"{format_count(duplicates)} rows "
                f"({format_pct(profile.duplicate_pct)}) are exact duplicates"
            ),
            evidence=(
                f"Comparing all {profile.column_count} columns: "
                f"{format_count(unique_rows)} unique rows among "
                f"{format_count(profile.row_count)} total rows."
            ),
            confidence=1.0,
            recommendation=(
                "Deduplicate before analysis and investigate whether duplicates "
                "come from joins, retries, or upstream double-loads."
            ),
        )
    ]
