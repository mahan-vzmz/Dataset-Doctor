"""Top-level report model returned by the analysis pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from dataset_doctor.models.findings import Finding
from dataset_doctor.models.profile import DatasetProfile
from dataset_doctor.models.score import HealthScore


class ReportSummary(BaseModel):
    """Counts of findings by severity."""

    critical: int = Field(ge=0)
    warning: int = Field(ge=0)
    notice: int = Field(ge=0)

    @property
    def total(self) -> int:
        return self.critical + self.warning + self.notice


class SummaryCheck(BaseModel):
    """One line of the positive-checks section (e.g. "Schema consistency: GOOD")."""

    name: str
    status: str
    passed: bool
    detail: str | None = None


class DoctorReport(BaseModel):
    """Everything the CLI needs to render any output format."""

    tool: Literal["dataset-doctor"] = "dataset-doctor"
    version: str
    generated_at: datetime
    source_path: str
    health_score: HealthScore
    summary: ReportSummary
    dataset: DatasetProfile
    findings: list[Finding] = Field(default_factory=list)
    checks: list[SummaryCheck] = Field(default_factory=list)
