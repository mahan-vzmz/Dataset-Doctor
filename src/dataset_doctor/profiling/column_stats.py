"""Column-level profiling.

Statistics are dtype-aware: numeric columns get distributional statistics,
temporal columns get min/max, string columns get frequency and length
statistics, and complex types (structs/lists) only get null/uniqueness counts.
Meaningless statistics are simply left out rather than computed incorrectly.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Literal

import polars as pl

if TYPE_CHECKING:
    from dataset_doctor.models.profile import (
        ColumnProfile,
        FrequentValue,
        SemanticType,
    )

_STRING_BASES = frozenset({pl.String, pl.Categorical, pl.Enum})
_INTEGER_BASES = frozenset(
    {
        pl.Int8,
        pl.Int16,
        pl.Int32,
        pl.Int64,
        pl.UInt8,
        pl.UInt16,
        pl.UInt32,
        pl.UInt64,
    }
)
_FLOAT_BASES = frozenset({pl.Float32, pl.Float64})
_TEMPORAL_BASES = frozenset({pl.Datetime, pl.Date, pl.Time})

#: A "categorical" string column has few distinct values...
_CATEGORICAL_MAX_UNIQUE = 50
#: ...or distinct values for at most this share of non-null rows.
_CATEGORICAL_MAX_UNIQUE_RATIO = 0.5

#: Internal dtype families; string columns are refined to categorical/text
#: once cardinality is known.
SemanticFamily = Literal[
    "numeric", "boolean", "datetime", "categorical", "text", "complex", "string"
]


def classify_semantic_family(dtype: pl.DataType) -> SemanticFamily:
    """Map a Polars dtype to a coarse family used by the profiler."""
    base = dtype.base_type()
    if base is pl.Boolean:
        return "boolean"
    if base in _INTEGER_BASES or base in _FLOAT_BASES:
        return "numeric"
    if base in _TEMPORAL_BASES:
        return "datetime"
    if base in _STRING_BASES:
        return "string"  # refined to categorical/text once cardinality is known
    return "complex"


def profile_columns(df: pl.DataFrame, top_k: int) -> list[ColumnProfile]:
    """Profile every column of ``df``."""
    return [profile_column(df, name, top_k) for name in df.columns]


def profile_column(df: pl.DataFrame, name: str, top_k: int) -> ColumnProfile:
    """Compute the profile of one column."""
    from dataset_doctor.models.profile import ColumnProfile as _ColumnProfile

    series = df.get_column(name)
    row_count = df.height
    null_count = series.null_count()
    non_null_count = row_count - null_count

    unique_count = _unique_count(series, null_count)
    unique_pct = (unique_count / non_null_count * 100.0) if non_null_count else 0.0
    constant = unique_count <= 1 and null_count < row_count

    semantic = classify_semantic_family(series.dtype)
    stats: dict[str, object] = {}
    if semantic == "numeric":
        stats = _numeric_stats(df, name)
    elif semantic == "datetime":
        stats = _temporal_stats(series)
    elif semantic == "string":
        semantic, stats = _string_semantics(
            df,
            name,
            unique_count=unique_count,
            non_null_count=non_null_count,
            top_k=top_k,
        )

    frequent: list[FrequentValue] = []
    if semantic in ("boolean", "categorical", "text"):
        frequent = _top_frequent_values(series, non_null_count=non_null_count, top_k=top_k)

    return _ColumnProfile(
        name=name,
        dtype=str(series.dtype),
        semantic_type=semantic,
        row_count=row_count,
        null_count=null_count,
        null_pct=(null_count / row_count * 100.0) if row_count else 0.0,
        unique_count=unique_count,
        unique_pct=unique_pct,
        constant=constant,
        most_frequent=frequent,
        **stats,  # type: ignore[arg-type]
    )


def _unique_count(series: pl.Series, null_count: int) -> int:
    """Distinct *non-null* values (Polars' ``n_unique`` includes the null)."""
    raw = int(series.n_unique())
    return max(raw - (1 if null_count > 0 else 0), 0)


def _finite(value: object) -> float | None:
    if value is None:
        return None
    number = float(value)  # type: ignore[arg-type]
    return number if math.isfinite(number) else None


def _numeric_stats(df: pl.DataFrame, name: str) -> dict[str, object]:
    row = df.select(
        pl.col(name).min().alias("min"),
        pl.col(name).max().alias("max"),
        pl.col(name).mean().alias("mean"),
        pl.col(name).median().alias("median"),
        pl.col(name).std(ddof=1).alias("std"),
        pl.col(name).quantile(0.25, interpolation="linear").alias("q1"),
        pl.col(name).quantile(0.75, interpolation="linear").alias("q3"),
        pl.col(name).skew().alias("skew"),
    ).row(0)

    minimum, maximum = _finite(row[0]), _finite(row[1])
    is_integer = df.get_column(name).dtype.base_type() in _INTEGER_BASES
    return {
        "min_value": _render_number(minimum, is_integer),
        "max_value": _render_number(maximum, is_integer),
        "mean_value": _finite(row[2]),
        "median_value": _finite(row[3]),
        "std_value": _finite(row[4]),
        "q1_value": _finite(row[5]),
        "q3_value": _finite(row[6]),
        "skewness": _finite(row[7]),
    }


def _temporal_stats(series: pl.Series) -> dict[str, object]:
    minimum = series.min()
    maximum = series.max()
    return {
        "min_value": str(minimum) if minimum is not None else None,
        "max_value": str(maximum) if maximum is not None else None,
    }


def _string_semantics(
    df: pl.DataFrame,
    name: str,
    *,
    unique_count: int,
    non_null_count: int,
    top_k: int,
) -> tuple[SemanticType, dict[str, object]]:
    """Decide categorical vs text and compute matching statistics."""
    unique_ratio = (unique_count / non_null_count) if non_null_count else 0.0
    is_categorical = (
        unique_count <= _CATEGORICAL_MAX_UNIQUE or unique_ratio <= _CATEGORICAL_MAX_UNIQUE_RATIO
    )
    stats: dict[str, object] = {}
    if not is_categorical:
        lengths = df.select(pl.col(name).str.len_chars().mean()).item()
        avg_length = _finite(lengths)
        if avg_length is not None:
            stats["avg_length"] = avg_length
    return ("categorical" if is_categorical else "text"), stats


def _top_frequent_values(
    series: pl.Series,
    *,
    non_null_count: int,
    top_k: int,
) -> list[FrequentValue]:
    """Most frequent non-null values with deterministic tie-breaking."""
    from dataset_doctor.models.profile import FrequentValue as _FrequentValue

    if non_null_count == 0:
        return []

    values = series.drop_nulls()
    if values.dtype.base_type() not in {pl.String}:
        values = values.cast(pl.String)

    value_name = values.name or "value"
    counts = (
        values.to_frame(value_name)
        .group_by(value_name)
        .agg(pl.len().alias("_count"))
        .sort(["_count", value_name], descending=[True, False])
        .head(top_k)
    )
    return [
        _FrequentValue(
            value=str(row[0]),
            count=int(row[1]),
            pct=(int(row[1]) / non_null_count * 100.0),
        )
        for row in counts.iter_rows()
    ]


def _render_number(value: float | None, is_integer_dtype: bool) -> str | None:
    """Render a number without float noise; integers keep integer formatting."""
    if value is None:
        return None
    if is_integer_dtype or (isinstance(value, int) or float(value).is_integer()):
        return f"{int(value):,}"
    return f"{value:,.6g}"
