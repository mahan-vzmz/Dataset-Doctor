"""Finding model: one deterministic, evidence-backed data quality issue."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    """How badly a finding threatens dataset usability."""

    CRITICAL = "critical"
    WARNING = "warning"
    NOTICE = "notice"


class FindingCategory(StrEnum):
    """Scoring category a finding belongs to."""

    MISSINGNESS = "missingness"
    DUPLICATES = "duplicates"
    SCHEMA = "schema"
    DISTRIBUTION = "distribution"
    CARDINALITY = "cardinality"


SEVERITY_ORDER: dict[Severity, int] = {
    Severity.CRITICAL: 0,
    Severity.WARNING: 1,
    Severity.NOTICE: 2,
}

CATEGORY_ORDER: dict[FindingCategory, int] = {
    category: index for index, category in enumerate(FindingCategory)
}


class Finding(BaseModel):
    """A single data quality observation.

    ``column`` is ``None`` for dataset-level findings (e.g. duplicate rows).
    """

    severity: Severity
    category: FindingCategory
    column: str | None = None
    description: str
    evidence: str
    confidence: float = Field(ge=0.0, le=1.0)
    recommendation: str

    @property
    def sort_key(self) -> tuple[int, int, str, str]:
        """Deterministic ordering: severity, then category, column, description."""
        return (
            SEVERITY_ORDER[self.severity],
            CATEGORY_ORDER[self.category],
            self.column or "",
            self.description,
        )
