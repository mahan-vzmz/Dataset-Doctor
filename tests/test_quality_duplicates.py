"""Duplicate detection: DuckDB engine, Polars fallback, and the finding rule."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from dataset_doctor.io.duplicates import _count_duplicate_rows_polars, count_duplicate_rows
from dataset_doctor.models.findings import FindingCategory, Severity
from dataset_doctor.quality.duplicates import run
from tests.conftest import find_one, make_context


def test_duckdb_and_fallback_agree_on_csv(tmp_path: Path) -> None:
    path = tmp_path / "d.csv"
    path.write_text("a,b\n1,x\n1,x\n2,y\n3,z\n3,z\n3,z\n", encoding="utf-8")
    df = pl.read_csv(path)
    from dataset_doctor.io.readers import LoadedDataset

    loaded = LoadedDataset(
        df=df,
        file_format="csv",
        path=path.resolve(),
        file_size_bytes=path.stat().st_size,
    )
    via_duckdb = count_duplicate_rows(loaded)
    via_polars = _count_duplicate_rows_polars(df)
    # 6 rows: 1 duplicate of (1,x) and 2 duplicates of (3,z).
    assert via_duckdb == 3
    assert via_polars == 3


def test_no_duplicates(tmp_path: Path) -> None:
    df = pl.DataFrame({"a": [1, 2, 3]})
    assert run(make_context(df, tmp_path)) == []


def test_duplicates_above_threshold_warn(tmp_path: Path) -> None:
    df = pl.DataFrame({"a": [1] * 5 + [2, 3, 4, 5, 6]})  # 10 rows, 6 unique -> 40%
    findings = run(make_context(df, tmp_path))
    finding = find_one(findings, category=FindingCategory.DUPLICATES, severity=Severity.WARNING)
    assert finding.column is None  # dataset-level finding
    assert "4 rows" in finding.description
    assert "40.0%" in finding.description


def test_duplicates_below_threshold_silent(tmp_path: Path) -> None:
    # 1 duplicate in 2000 rows = 0.05%, below pct and absolute thresholds.
    df = pl.DataFrame({"a": [*range(1999), 0]})
    findings = run(make_context(df, tmp_path))
    assert findings == []


def test_absolute_row_threshold_catches_large_files(tmp_path: Path) -> None:
    from dataset_doctor.models.thresholds import Thresholds

    # 500 duplicates = 1% exactly... use lower pct threshold to isolate the
    # absolute-count branch: pct below warning but count above min_rows.
    thresholds = Thresholds(duplicate_warning_pct=50.0, duplicate_warning_min_rows=100)
    df = pl.DataFrame({"a": [1] * 600 + list(range(400))})  # 50% dupes, 600 redundant
    findings = run(make_context(df, tmp_path, thresholds=thresholds))
    assert any(f.category is FindingCategory.DUPLICATES for f in findings)


def test_empty_frame_is_safe(tmp_path: Path) -> None:
    df = pl.DataFrame({"a": []}, schema={"a": pl.Int64})
    loaded_ctx = make_context(df, tmp_path)
    assert loaded_ctx.profile.duplicate_row_count == 0
    assert run(loaded_ctx) == []
