"""Profiling tests: exact statistics on known data, dtype-aware behavior."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import polars as pl

from dataset_doctor.models.thresholds import Thresholds
from dataset_doctor.profiling.column_stats import profile_column, profile_columns
from dataset_doctor.profiling.dataset_stats import profile_dataset
from tests.conftest import make_loaded


def test_numeric_stats_are_exact(tmp_path: Path) -> None:
    df = pl.DataFrame({"x": [1, 2, 3, 4, 5]})
    column = profile_column(df, "x", top_k=3)

    assert column.semantic_type == "numeric"
    assert column.null_count == 0
    assert column.unique_count == 5
    assert column.mean_value == 3.0
    assert column.median_value == 3.0
    assert column.std_value is not None and abs(column.std_value - 2.5**0.5) < 1e-9
    assert column.q1_value == 2.0
    assert column.q3_value == 4.0
    assert column.skewness is not None and abs(column.skewness) < 1e-9
    assert column.min_value == "1"
    assert column.max_value == "5"


def test_unique_count_excludes_nulls() -> None:
    df = pl.DataFrame({"x": ["a", "a", "b", None, None]})
    column = profile_column(df, "x", top_k=5)
    assert column.null_count == 2
    assert column.unique_count == 2  # 'a' and 'b'; nulls do not count
    assert column.null_pct == 40.0


def test_top_frequent_with_deterministic_ties() -> None:
    df = pl.DataFrame({"c": ["b", "a", "b", "a", "c"]})
    column = profile_column(df, "c", top_k=2)
    top = [(item.value, item.count) for item in column.most_frequent]
    # Both a and b have count 2; ties broken alphabetically.
    assert top == [("a", 2), ("b", 2)]


def test_constant_flag() -> None:
    df = pl.DataFrame({"same": [7, 7, 7], "mixed": [1, 2, 3], "empty": [None, None, None]})
    columns = {column.name: column for column in profile_columns(df, top_k=3)}
    assert columns["same"].constant is True
    assert columns["mixed"].constant is False
    # A fully-null column is reported by missingness rules, not as constant.
    assert columns["empty"].constant is False
    assert columns["empty"].null_pct == 100.0


def test_semantic_type_classification() -> None:
    n = 120
    df = pl.DataFrame(
        {
            "n": [1.5 + (i % 2) for i in range(n)],
            "i": list(range(n)),
            "b": [bool(i % 2) for i in range(n)],
            "d": [date(2024, 1, 1) + timedelta(days=i) for i in range(n)],
            "cat": ["x" if i % 3 else "y" for i in range(n)],
            "text": [f"user-{i}-with-long-name" for i in range(n)],
        }
    ).with_columns(pl.Series("big", [[i] for i in range(n)], dtype=pl.List(pl.Int64)))
    columns = {column.name: column for column in profile_columns(df, top_k=5)}
    assert columns["n"].semantic_type == "numeric"
    assert columns["i"].semantic_type == "numeric"
    assert columns["b"].semantic_type == "boolean"
    assert columns["d"].semantic_type == "datetime"
    assert columns["cat"].semantic_type == "categorical"
    assert columns["text"].semantic_type == "text"
    assert columns["big"].semantic_type == "complex"


def test_text_columns_report_length_not_mean() -> None:
    values = [f"user-{i}-with-long-name" for i in range(80)]
    df = pl.DataFrame({"t": pl.Series(values, dtype=pl.String)})
    column = profile_column(df, "t", top_k=5)
    assert column.semantic_type == "text"
    assert column.mean_value is None  # no numeric stats for text
    expected = sum(len(v) for v in values) / len(values)
    assert column.avg_length is not None and abs(column.avg_length - expected) < 1e-9


def test_datetime_min_max_rendered() -> None:
    df = pl.DataFrame({"d": [date(2024, 3, 1), date(2024, 1, 1)]})
    column = profile_column(df, "d", top_k=5)
    assert column.min_value == "2024-01-01"
    assert column.max_value == "2024-03-01"


def test_dataset_profile_totals(tmp_path: Path) -> None:
    df = pl.DataFrame({"a": [1, 2, None], "b": ["x", None, None]})
    loaded = make_loaded(df, tmp_path)
    profile = profile_dataset(loaded, Thresholds())

    assert profile.row_count == 3
    assert profile.column_count == 2
    assert profile.total_null_count == 3
    assert profile.total_null_pct == 50.0
    assert profile.duplicate_row_count == 0
    assert profile.schema_map == {"a": str(pl.Int64()), "b": str(pl.String())}


def test_duplicate_counts_in_profile(tmp_path: Path) -> None:
    df = pl.DataFrame({"a": [1, 1, 1, 2], "b": ["x", "x", "x", "y"]})
    loaded = make_loaded(df, tmp_path)
    profile = profile_dataset(loaded, Thresholds())
    # 4 rows, 2 unique rows -> 2 redundant rows.
    assert profile.duplicate_row_count == 2
    assert profile.duplicate_pct == 50.0
