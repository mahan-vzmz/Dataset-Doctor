"""Missingness detector: severity ladder and edge cases."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from dataset_doctor.models.findings import FindingCategory, Severity
from dataset_doctor.models.thresholds import Thresholds
from dataset_doctor.quality.missingness import run
from tests.conftest import find_one, make_context


def test_empty_column_is_critical(tmp_path: Path) -> None:
    df = pl.DataFrame({"empty": [None, None, None], "x": [1, 2, 3]})
    findings = run(make_context(df, tmp_path))
    finding = find_one(findings, category=FindingCategory.MISSINGNESS, column="empty")
    assert finding.severity is Severity.CRITICAL
    assert "completely empty" in finding.description
    # No second (extreme-missingness) finding for the same column.
    empty_findings = [f for f in findings if f.column == "empty"]
    assert len(empty_findings) == 1


def test_extreme_missingness_is_critical(tmp_path: Path) -> None:
    df = pl.DataFrame({"c": [None] * 6 + [1] * 4})  # 60% missing
    findings = run(make_context(df, tmp_path))
    finding = find_one(findings, category=FindingCategory.MISSINGNESS, severity=Severity.CRITICAL)
    assert "60.0%" in finding.description


def test_high_missingness_is_warning(tmp_path: Path) -> None:
    df = pl.DataFrame({"c": [None] * 3 + [1] * 7})  # 30% missing
    findings = run(make_context(df, tmp_path))
    find_one(findings, category=FindingCategory.MISSINGNESS, severity=Severity.WARNING)


def test_moderate_missingness_is_notice(tmp_path: Path) -> None:
    df = pl.DataFrame({"c": [None] * 8 + [1] * 92})  # 8% missing
    findings = run(make_context(df, tmp_path))
    find_one(findings, category=FindingCategory.MISSINGNESS, severity=Severity.NOTICE)


def test_low_missingness_produces_nothing(tmp_path: Path) -> None:
    df = pl.DataFrame({"c": [None] + [1] * 99})  # 1% missing
    findings = run(make_context(df, tmp_path))
    assert findings == []


def test_thresholds_are_configurable(tmp_path: Path) -> None:
    df = pl.DataFrame({"c": [None] * 25 + [1] * 75})  # 25% missing

    # Raising the warning ladder to 50% downgrades the finding to a notice.
    strict = Thresholds(missing_warning_pct=50.0)
    findings = run(make_context(df, tmp_path, thresholds=strict))
    assert all(f.severity is Severity.NOTICE for f in findings)

    # Raising every rung above 25% silences the column completely.
    silent = Thresholds(missing_notice_pct=30.0, missing_warning_pct=30.0)
    findings = run(make_context(df, tmp_path, thresholds=silent))
    assert findings == []


def test_evidence_contains_counts(tmp_path: Path) -> None:
    df = pl.DataFrame({"c": [None] * 5 + [1] * 5})
    finding = find_one(run(make_context(df, tmp_path)), category=FindingCategory.MISSINGNESS)
    assert "5 of 10" in finding.evidence
