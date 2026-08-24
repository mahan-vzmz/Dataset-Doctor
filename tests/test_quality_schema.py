"""Schema and type-consistency detectors: header problems, mistyped columns."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from dataset_doctor.io.readers import LoadedDataset
from dataset_doctor.models.findings import FindingCategory, Severity
from dataset_doctor.models.thresholds import Thresholds
from dataset_doctor.profiling.dataset_stats import profile_dataset
from dataset_doctor.quality.context import AnalysisContext
from dataset_doctor.quality.schema_types import run
from tests.conftest import find_one, make_context


def _csv_context(path: Path, thresholds: Thresholds | None = None) -> AnalysisContext:
    df = pl.read_csv(path, infer_schema_length=0)  # force all-String to see raw text
    loaded = LoadedDataset(
        df=df,
        file_format="csv",
        path=path,
        file_size_bytes=path.stat().st_size,
    )
    effective = thresholds or Thresholds()
    profile = profile_dataset(loaded, effective)
    return AnalysisContext(loaded=loaded, profile=profile, thresholds=effective)


def test_duplicate_header_names_are_critical(tmp_path: Path) -> None:
    path = tmp_path / "dup.csv"
    path.write_text("id,id\n1,2\n3,4\n", encoding="utf-8")
    findings = run(_csv_context(path))
    finding = find_one(findings, category=FindingCategory.SCHEMA, severity=Severity.CRITICAL)
    assert "Duplicate column name 'id'" in finding.description


def test_blank_column_name_is_critical(tmp_path: Path) -> None:
    path = tmp_path / "blank.csv"
    path.write_text("ok,\n1,2\n", encoding="utf-8")
    findings = run(_csv_context(path))
    finding = find_one(findings, category=FindingCategory.SCHEMA)
    assert finding.severity is Severity.CRITICAL
    assert "empty or whitespace-only" in finding.description


def test_unnamed_index_column_is_warning(tmp_path: Path) -> None:
    path = tmp_path / "unnamed.csv"
    path.write_text("Unnamed: 0,val\n1,2\n", encoding="utf-8")
    findings = run(_csv_context(path))
    finding = find_one(findings, category=FindingCategory.SCHEMA, severity=Severity.WARNING)
    assert "Unnamed" in finding.description


def test_whitespace_in_header_name_is_notice(tmp_path: Path) -> None:
    path = tmp_path / "spacey.csv"
    path.write_text(" value ,val\n1,2\n", encoding="utf-8")
    findings = run(_csv_context(path))
    finding = find_one(findings, category=FindingCategory.SCHEMA, severity=Severity.NOTICE)
    assert "whitespace" in finding.description


def test_mostly_numeric_text_column_is_critical(tmp_path: Path) -> None:
    values = [str(i) for i in range(90)] + ["$12"] * 10  # 90% numeric-like
    df = pl.DataFrame({"price": pl.Series(values, dtype=pl.String)})
    findings = run(make_context(df, tmp_path))
    finding = find_one(
        findings,
        category=FindingCategory.SCHEMA,
        column="price",
        severity=Severity.CRITICAL,
    )
    assert "90.0%" in finding.description


def test_fully_numeric_text_column_is_notice(tmp_path: Path) -> None:
    values = [str(i) for i in range(20)]
    df = pl.DataFrame({"zip": pl.Series(values, dtype=pl.String)})
    findings = run(make_context(df, tmp_path))
    finding = find_one(
        findings,
        category=FindingCategory.SCHEMA,
        column="zip",
        severity=Severity.NOTICE,
    )
    assert "stored as text" in finding.description


def test_properly_typed_columns_stay_silent(tmp_path: Path) -> None:
    df = pl.DataFrame(
        {
            "n": list(range(50)),
            "s": [f"abc{i}" for i in range(50)],  # no numeric pattern matches
        }
    )
    findings = run(make_context(df, tmp_path))
    schema_findings = [
        f for f in findings if f.category is FindingCategory.SCHEMA and f.column is not None
    ]
    assert schema_findings == []


def test_small_columns_skip_type_check(tmp_path: Path) -> None:
    df = pl.DataFrame({"price": pl.Series(["1", "$2"], dtype=pl.String)})
    findings = run(make_context(df, tmp_path))
    assert findings == []  # below the 10-value noise gate
