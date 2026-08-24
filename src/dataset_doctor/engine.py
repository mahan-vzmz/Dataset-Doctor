"""Analysis pipeline: load -> profile -> detect -> score -> report."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from dataset_doctor._version import get_version
from dataset_doctor.io.readers import load_dataset
from dataset_doctor.models.findings import FindingCategory, Severity
from dataset_doctor.models.report import DoctorReport, ReportSummary, SummaryCheck
from dataset_doctor.models.thresholds import Thresholds
from dataset_doctor.profiling.dataset_stats import profile_dataset
from dataset_doctor.quality import DETECTOR_PIPELINE, AnalysisContext
from dataset_doctor.scoring.scorer import compute_health_score
from dataset_doctor.utils import format_count, format_pct

if TYPE_CHECKING:
    from dataset_doctor.models.findings import Finding
    from dataset_doctor.models.profile import DatasetProfile


def analyze(path: str, thresholds: Thresholds | None = None) -> DoctorReport:
    """Run the full analysis pipeline on the file at ``path``."""
    effective_thresholds = thresholds if thresholds is not None else Thresholds()
    loaded = load_dataset(path)
    profile = profile_dataset(loaded, effective_thresholds)

    context = AnalysisContext(
        loaded=loaded,
        profile=profile,
        thresholds=effective_thresholds,
    )
    findings: list[Finding] = []
    for detector in DETECTOR_PIPELINE:
        findings.extend(detector(context))
    findings.sort(key=lambda finding: finding.sort_key)

    health_score = compute_health_score(findings, effective_thresholds)
    return DoctorReport(
        version=get_version(),
        generated_at=datetime.now(UTC),
        source_path=str(loaded.path),
        health_score=health_score,
        summary=_summarize(findings),
        dataset=profile,
        findings=findings,
        checks=_build_checks(profile, findings),
    )


def _summarize(findings: list[Finding]) -> ReportSummary:
    return ReportSummary(
        critical=sum(1 for f in findings if f.severity is Severity.CRITICAL),
        warning=sum(1 for f in findings if f.severity is Severity.WARNING),
        notice=sum(1 for f in findings if f.severity is Severity.NOTICE),
    )


def _build_checks(profile: DatasetProfile, findings: list[Finding]) -> list[SummaryCheck]:
    """Positive-check lines mirroring the classic report footer."""
    blocking_schema = [
        f
        for f in findings
        if f.category is FindingCategory.SCHEMA
        and f.severity in (Severity.CRITICAL, Severity.WARNING)
    ]
    constant_columns = [c for c in profile.columns if c.constant]
    missingness_blocking = [
        f
        for f in findings
        if f.category is FindingCategory.MISSINGNESS
        and f.severity in (Severity.CRITICAL, Severity.WARNING)
    ]

    return [
        SummaryCheck(
            name="Schema consistency",
            status="GOOD" if not blocking_schema else "ISSUES FOUND",
            passed=not blocking_schema,
            detail=(
                None if not blocking_schema else f"{format_count(len(blocking_schema))} issue(s)"
            ),
        ),
        SummaryCheck(
            name="Constant columns",
            status="NONE" if not constant_columns else format_count(len(constant_columns)),
            passed=not constant_columns,
            detail=(", ".join(c.name for c in constant_columns[:3]) if constant_columns else None),
        ),
        SummaryCheck(
            name="Duplicate rows",
            status=(
                "NONE" if profile.duplicate_row_count == 0 else format_pct(profile.duplicate_pct)
            ),
            passed=profile.duplicate_row_count == 0,
        ),
        SummaryCheck(
            name="Missing values",
            status="OK" if not missingness_blocking else "REVIEW",
            passed=not missingness_blocking,
            detail=f"{format_pct(profile.total_null_pct)} of all cells are null",
        ),
    ]
