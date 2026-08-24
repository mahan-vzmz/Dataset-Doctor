"""Schema-level findings: header problems and text columns with mistyped content."""

from __future__ import annotations

import csv
import re
from typing import TYPE_CHECKING

import polars as pl

from dataset_doctor.models.findings import Finding, FindingCategory, Severity
from dataset_doctor.utils import format_count, format_pct

if TYPE_CHECKING:
    from pathlib import Path

    from dataset_doctor.io.readers import LoadedDataset
    from dataset_doctor.models.thresholds import Thresholds
    from dataset_doctor.quality.context import AnalysisContext

_NUMERIC_PATTERN = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")
_DATE_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?(Z|[+-]\d{2}:?\d{2})?$"
)
_UNNAMED_PATTERN = re.compile(r"^unnamed([:_\s]*\d+)?$", re.IGNORECASE)

#: Below this many non-null values, type-consistency checks are too noisy.
_MIN_VALUES_FOR_TYPE_CHECK = 10


def run(ctx: AnalysisContext) -> list[Finding]:
    """Header problems (CSV) plus string columns whose values look mistyped."""
    return _header_findings(ctx.loaded) + _type_consistency_findings(ctx)


def _header_findings(loaded: LoadedDataset) -> list[Finding]:
    if loaded.file_format != "csv":
        return []
    header = _read_header(loaded.path)
    if header is None:
        return []

    findings: list[Finding] = []
    seen: dict[str, int] = {}
    for position, name in enumerate(header):
        stripped = name.strip()
        if name in seen:
            findings.append(
                Finding(
                    severity=Severity.CRITICAL,
                    category=FindingCategory.SCHEMA,
                    column=name,
                    description=(
                        f"Duplicate column name '{name}' appears "
                        f"{format_count(seen[name] + 1)} times in the file header"
                    ),
                    evidence=(
                        f"Positions {format_count(seen[name])} and {position} "
                        f"(0-based) share the same name; downstream tools must guess."
                    ),
                    confidence=1.0,
                    recommendation=(
                        "Rename duplicate headers so every column is uniquely addressable."
                    ),
                )
            )
        else:
            seen[name] = position

        if stripped == "":
            findings.append(
                Finding(
                    severity=Severity.CRITICAL,
                    category=FindingCategory.SCHEMA,
                    column=f"<column {position}>",
                    description=(
                        f"Column at position {position} has an empty or whitespace-only name"
                    ),
                    evidence=f"Raw header value: {name!r}",
                    confidence=1.0,
                    recommendation="Give every column a non-empty, trimmed name.",
                )
            )
            continue
        if name != stripped:
            findings.append(
                Finding(
                    severity=Severity.NOTICE,
                    category=FindingCategory.SCHEMA,
                    column=name,
                    description=(
                        f"Column name '{stripped}' has leading/trailing whitespace in the header"
                    ),
                    evidence=f"Raw header value: {name!r}",
                    confidence=1.0,
                    recommendation="Trim whitespace from column names to avoid lookup surprises.",
                )
            )
        elif _UNNAMED_PATTERN.match(name):
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    category=FindingCategory.SCHEMA,
                    column=name,
                    description=(
                        f"Column '{name}' looks like an unnamed index column from an export"
                    ),
                    evidence=(
                        "Name matches the 'Unnamed: N' pattern produced by spreadsheet exports."
                    ),
                    confidence=0.9,
                    recommendation="Drop the stray index column or give it a meaningful name.",
                )
            )
    return findings


def _read_header(path: Path) -> list[str] | None:
    try:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            row = next(csv.reader(handle), None)
    except (OSError, UnicodeDecodeError):
        return None
    return row


def _type_consistency_findings(ctx: AnalysisContext) -> list[Finding]:
    """Detect string columns that mostly contain numbers or dates."""
    thresholds = ctx.thresholds
    findings: list[Finding] = []

    for column in ctx.profile.columns:
        if column.semantic_type not in ("categorical", "text"):
            continue
        non_null_count = column.row_count - column.null_count
        if non_null_count < _MIN_VALUES_FOR_TYPE_CHECK:
            continue

        series = ctx.df.get_column(column.name).drop_nulls().cast(pl.String).str.strip_chars()

        numeric_matches = series.str.contains(_NUMERIC_PATTERN.pattern).sum()
        numeric_ratio = int(numeric_matches) / non_null_count
        date_matches = series.str.contains(_DATE_PATTERN.pattern).sum()
        date_ratio = int(date_matches) / non_null_count

        for kind, ratio in (("numbers", numeric_ratio), ("dates", date_ratio)):
            finding = _type_finding(column.name, kind, ratio, non_null_count, thresholds)
            if finding is not None:
                findings.append(finding)
    return findings


def _type_finding(
    name: str,
    kind: str,
    ratio: float,
    non_null_count: int,
    thresholds: Thresholds,
) -> Finding | None:
    """Build a finding for a text column that looks like ``kind`` values."""
    pct = ratio * 100.0
    fully_typed = ratio >= 1.0 - 1e-9
    if not fully_typed and ratio >= thresholds.mixed_type_critical_ratio:
        return Finding(
            severity=Severity.CRITICAL,
            category=FindingCategory.SCHEMA,
            column=name,
            description=(
                f"'{name}' is stored as text but {format_pct(pct)} of its values "
                f"parse as {kind}, while the rest do not"
            ),
            evidence=(
                f"{format_count(round(ratio * non_null_count))} of "
                f"{format_count(non_null_count)} non-null values match a {kind} pattern; "
                f"the remainder forced the column to text type."
            ),
            confidence=0.85,
            recommendation=(
                f"Fix or standardize the {kind}-like values and parse the column "
                f"into its natural type at load time."
            ),
        )
    if not fully_typed and ratio >= thresholds.mixed_type_warning_ratio:
        return Finding(
            severity=Severity.WARNING,
            category=FindingCategory.SCHEMA,
            column=name,
            description=(
                f"'{name}' is stored as text but {format_pct(pct)} of its values look like {kind}"
            ),
            evidence=(
                f"{format_count(round(ratio * non_null_count))} of "
                f"{format_count(non_null_count)} non-null values match a {kind} pattern."
            ),
            confidence=0.8,
            recommendation="Verify the column's intended type and cast it explicitly when loading.",
        )
    if fully_typed:
        return Finding(
            severity=Severity.NOTICE,
            category=FindingCategory.SCHEMA,
            column=name,
            description=(f"'{name}' is fully composed of {kind}-like values but is stored as text"),
            evidence=(
                f"All {format_count(non_null_count)} non-null values match a "
                f"{kind} pattern (e.g. zip codes or IDs may legitimately be text)."
            ),
            confidence=0.8,
            recommendation=(
                f"Cast to a numeric/date type if the values are true {kind}; "
                f"keep as text if leading zeros or formatting matter."
            ),
        )
    return None
