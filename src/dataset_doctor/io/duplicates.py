"""Exact duplicate-row detection.

Primary engine is DuckDB querying the file natively (no full second parse into
Python objects, and no Arrow dependency). When the file cannot be mapped to a
DuckDB reader with identical types - or DuckDB itself fails - we fall back to
an equivalent pure-Polars computation so results stay correct everywhere.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import duckdb
import polars as pl

if TYPE_CHECKING:
    from dataset_doctor.io.readers import LoadedDataset


def count_duplicate_rows(loaded: LoadedDataset) -> int:
    """Return the number of redundant rows (rows beyond the first occurrence).

    For a dataset of N rows containing G unique rows this returns ``N - G``.
    """
    df = loaded.df
    if df.height <= 1 or df.width == 0:
        return 0

    source = _duckdb_source(loaded)
    if source is not None:
        sql = f"SELECT COUNT(*) FROM (SELECT DISTINCT * FROM {source})"
        try:
            with duckdb.connect() as connection:
                distinct_rows = connection.execute(sql).fetchone()
            if distinct_rows is not None:
                return max(df.height - int(distinct_rows[0]), 0)
        except duckdb.Error:
            pass  # fall through to the Polars implementation

    return _count_duplicate_rows_polars(df)


def _duckdb_source(loaded: LoadedDataset) -> str | None:
    """Build a DuckDB table function expression, or ``None`` to use the fallback."""
    path_sql = str(loaded.path).replace("'", "''")
    match loaded.file_format:
        case "parquet":
            return f"read_parquet('{path_sql}')"
        case "jsonl":
            return f"read_ndjson('{path_sql}')"
        case "csv":
            column_types = [
                f"'{name.replace(chr(39), chr(39) * 2)}': '{_duckdb_type(dtype)}'"
                for name, dtype in loaded.df.schema.items()
            ]
            if any("NULL" in type_sql for type_sql in column_types):
                return None
            joined = ", ".join(column_types)
            return f"read_csv('{path_sql}', header=true, columns={{{joined}}})"
        case _:
            return None


def _duckdb_type(dtype: pl.DataType) -> str:
    """Map a Polars dtype to a DuckDB type string ('NULL' means unmappable)."""
    base = dtype.base_type()

    simple = {
        pl.Int8: "TINYINT",
        pl.Int16: "SMALLINT",
        pl.Int32: "INTEGER",
        pl.Int64: "BIGINT",
        pl.UInt8: "UTINYINT",
        pl.UInt16: "USMALLINT",
        pl.UInt32: "UINTEGER",
        pl.UInt64: "UBIGINT",
        pl.Float32: "REAL",
        pl.Float64: "DOUBLE",
        pl.String: "VARCHAR",
        pl.Boolean: "BOOLEAN",
        pl.Date: "DATE",
        pl.Time: "TIME",
    }
    if base in simple:
        return simple[base]
    if isinstance(dtype, pl.Datetime):
        time_unit = dtype.time_unit
        precision = {"ms": 3, "us": 6, "ns": 9}.get(time_unit)
        if dtype.time_zone is None and precision is not None:
            return f"TIMESTAMP({precision})"
        return "NULL"
    return "NULL"


def _count_duplicate_rows_polars(df: pl.DataFrame) -> int:
    """Count redundant rows as total rows minus distinct rows."""
    distinct_rows = df.unique(keep="any").height
    return df.height - distinct_rows
