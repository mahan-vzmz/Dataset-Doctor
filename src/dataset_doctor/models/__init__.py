"""Pydantic domain models for profiles, findings, scores and reports."""

from __future__ import annotations

from dataset_doctor.models.findings import (
    CATEGORY_ORDER,
    SEVERITY_ORDER,
    Finding,
    FindingCategory,
    Severity,
)
from dataset_doctor.models.profile import (
    ColumnProfile,
    DatasetProfile,
    FrequentValue,
    SemanticType,
)
from dataset_doctor.models.report import DoctorReport, ReportSummary, SummaryCheck
from dataset_doctor.models.score import HealthScore, ScoreCategoryBreakdown
from dataset_doctor.models.thresholds import (
    CategoryCaps,
    SeverityPoints,
    Thresholds,
)

__all__ = [
    "CATEGORY_ORDER",
    "SEVERITY_ORDER",
    "CategoryCaps",
    "ColumnProfile",
    "DatasetProfile",
    "DoctorReport",
    "Finding",
    "FindingCategory",
    "FrequentValue",
    "HealthScore",
    "ReportSummary",
    "ScoreCategoryBreakdown",
    "SemanticType",
    "Severity",
    "SeverityPoints",
    "SummaryCheck",
    "Thresholds",
]

#: Display order for scoring categories in reports.
CATEGORY_CAPS_ORDER: list[FindingCategory] = [
    FindingCategory.MISSINGNESS,
    FindingCategory.DUPLICATES,
    FindingCategory.DISTRIBUTION,
    FindingCategory.SCHEMA,
    FindingCategory.CARDINALITY,
]
