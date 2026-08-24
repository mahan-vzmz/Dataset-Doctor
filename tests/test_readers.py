"""Reader tests: supported formats and every handled failure mode."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import polars as pl
import pytest

from dataset_doctor.exceptions import DataLoadError, UnsupportedFormatError
from dataset_doctor.io.readers import detect_format, load_dataset


def test_load_csv(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("data.csv", "a,b\n1,x\n2,y\n")
    loaded = load_dataset(str(path))
    assert loaded.file_format == "csv"
    assert loaded.df.height == 2
    assert loaded.df.columns == ["a", "b"]
    assert loaded.file_size_bytes == path.stat().st_size


def test_load_parquet(tmp_path: Path) -> None:
    path = tmp_path / "data.parquet"
    pl.DataFrame({"a": [1, 2], "b": ["x", "y"]}).write_parquet(path)
    loaded = load_dataset(str(path))
    assert loaded.file_format == "parquet"
    assert loaded.df.height == 2


def test_load_jsonl(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("data.jsonl", '{"a": 1}\n{"a": 2}\n')
    loaded = load_dataset(str(path))
    assert loaded.file_format == "jsonl"
    assert loaded.df["a"].to_list() == [1, 2]


def test_load_json_array(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("data.json", '[{"a": 1}, {"a": 2}]')
    loaded = load_dataset(str(path))
    assert loaded.file_format == "json"
    assert loaded.df["a"].to_list() == [1, 2]


def test_csv_dates_parsed(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("dates.csv", "d\n2024-01-01\n2024-06-15\n")
    loaded = load_dataset(str(path))
    assert loaded.df["d"].dtype == pl.Date


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(DataLoadError, match="not found"):
        load_dataset(str(tmp_path / "nope.csv"))


def test_directory_input(tmp_path: Path) -> None:
    with pytest.raises(DataLoadError, match="directory"):
        load_dataset(str(tmp_path))


def test_unsupported_extension(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("data.xlsx", "junk")
    with pytest.raises(UnsupportedFormatError, match="xlsx"):
        load_dataset(str(path))


def test_no_extension(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("datafile", "a\n1")
    with pytest.raises(UnsupportedFormatError, match="no extension"):
        load_dataset(str(path))


def test_empty_file(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("empty.csv", "")
    with pytest.raises(DataLoadError, match="0 bytes"):
        load_dataset(str(path))


def test_invalid_utf8_csv(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("bad.csv", b"a,b\nc\xff\xfe,\n")
    with pytest.raises(DataLoadError, match="Failed to parse CSV"):
        load_dataset(str(path))


def test_corrupted_parquet(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("broken.parquet", b"PAR1 definitely not a parquet file")
    with pytest.raises(DataLoadError, match="parquet"):
        load_dataset(str(path))


def test_malformed_jsonl(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("bad.jsonl", '{"a": 1}\n{not json at all}\n')
    with pytest.raises(DataLoadError):
        load_dataset(str(path))


def test_header_only_csv_yields_zero_rows(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("header_only.csv", "a,b,c\n")
    loaded = load_dataset(str(path))
    assert loaded.df.height == 0
    assert loaded.df.columns == ["a", "b", "c"]


def test_single_column_dataset(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("single.csv", "only_col\n1\n2\n3\n")
    loaded = load_dataset(str(path))
    assert loaded.df.width == 1
    assert loaded.df.height == 3


def test_detect_format_case_insensitive(tmp_path: Path) -> None:
    assert detect_format(Path("X.CSV")) == "csv"
    assert detect_format(Path("x.Parquet")) == "parquet"
    assert detect_format(Path("x.NDJSON")) == "jsonl"
