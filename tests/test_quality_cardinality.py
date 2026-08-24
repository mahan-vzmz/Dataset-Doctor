"""Cardinality detectors: constants, identifiers, messy category labels."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from dataset_doctor.models.findings import FindingCategory, Severity
from dataset_doctor.quality.cardinality import run
from tests.conftest import find_one, make_context


def test_constant_column_warns(tmp_path: Path) -> None:
    df = pl.DataFrame({"country": ["USA"] * 20, "v": list(range(20))})
    finding = find_one(
        run(make_context(df, tmp_path)),
        category=FindingCategory.CARDINALITY,
        column="country",
        severity=Severity.WARNING,
    )
    assert "'USA'" in finding.description


def test_variant_labels_warn(tmp_path: Path) -> None:
    labels = ["NYC", "NYC ", "nyc"] * 10
    df = pl.DataFrame({"city": labels})
    finding = find_one(
        run(make_context(df, tmp_path)),
        category=FindingCategory.CARDINALITY,
        column="city",
        severity=Severity.WARNING,
    )
    assert "inconsistent category labels" in finding.description
    assert "collapse to 1" in finding.description or "collapse to" in finding.description


def test_clean_categories_stay_silent(tmp_path: Path) -> None:
    df = pl.DataFrame({"city": ["Berlin", "Paris", "Madrid"] * 10})
    findings = run(make_context(df, tmp_path))
    assert findings == []


def test_fully_unique_text_is_identifier_warning(tmp_path: Path) -> None:
    n = 150
    df = pl.DataFrame(
        {
            "user_uuid": [f"id-{i:04d}" for i in range(n)],
            "value": [float(i) for i in range(n)],
        }
    )
    finding = find_one(
        run(make_context(df, tmp_path)),
        category=FindingCategory.CARDINALITY,
        column="user_uuid",
        severity=Severity.WARNING,
    )
    assert "every one of them is unique" in finding.description


def test_high_cardinality_partial_is_notice(tmp_path: Path) -> None:
    # 190 distinct values across 200 rows: high but not fully unique.
    keys = [f"s-{i}" for i in range(190)] + [f"s-{i}" for i in range(180, 190)]
    df = pl.DataFrame({"session_key": pl.Series(keys, dtype=pl.String)})
    finding = find_one(
        run(make_context(df, tmp_path)),
        category=FindingCategory.CARDINALITY,
        column="session_key",
        severity=Severity.NOTICE,
    )
    assert "very high cardinality" in finding.description


def test_cardinality_checks_need_minimum_rows(tmp_path: Path) -> None:
    df = pl.DataFrame({"k": ["a", "b", "c", "d"], "v": [1.0, 2, 3, 4]})
    findings = [f for f in run(make_context(df, tmp_path)) if f.column == "k"]
    assert findings == []
