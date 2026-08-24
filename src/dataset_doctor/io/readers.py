"""Load a tabular file into a Polars DataFrame.

Format detection is extension-based; parsing errors are translated into
:class:`DataLoadError` with actionable hints so the CLI never shows a
raw traceback for bad input.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import polars as pl

from dataset_doctor.exceptions import (
    DataLoadError,
    DatasetDoctorError,
    UnsupportedFormatError,
)

FileFormat = Literal["csv", "parquet", "jsonl", "json"]

_SUFFIX_TO_FORMAT: dict[str, FileFormat] = {
    ".csv": "csv",
    ".parquet": "parquet",
    ".pq": "parquet",
    ".jsonl": "jsonl",
    ".ndjson": "jsonl",
    ".json": "json",
}

SUPPORTED_SUFFIXES: tuple[str, ...] = tuple(sorted(_SUFFIX_TO_FORMAT))

_MAX_DETAIL_LENGTH = 300


@dataclass(frozen=True)
class LoadedDataset:
    """The materialized DataFrame plus metadata about its source file."""

    df: pl.DataFrame
    file_format: FileFormat
    path: Path
    file_size_bytes: int | None


def detect_format(path: Path) -> FileFormat:
    """Return the file format implied by ``path``'s extension."""
    suffix = path.suffix.lower()
    fmt = _SUFFIX_TO_FORMAT.get(suffix)
    if fmt is None:
        raise UnsupportedFormatError(
            f"Unsupported file format '{suffix or '<no extension>'}': {path.name}",
            hint=f"Supported formats: {', '.join(SUPPORTED_SUFFIXES)}",
        )
    return fmt


def load_dataset(path_str: str) -> LoadedDataset:
    """Detect the format of ``path_str`` and read it into memory."""
    path = Path(path_str)
    if not path.exists():
        raise DataLoadError(
            f"File not found: {path}",
            hint="Check the path and make sure the file exists.",
        )
    if path.is_dir():
        raise DataLoadError(
            f"Expected a file but found a directory: {path}",
            hint="Pass the path to a single CSV, Parquet, JSON or JSONL file.",
        )

    file_format = detect_format(path)
    file_size_bytes = path.stat().st_size
    if file_size_bytes == 0:
        raise DataLoadError(
            f"File is empty (0 bytes): {path.name}",
            hint="Export the dataset again, or check whether the write was interrupted.",
        )

    reader = {
        "csv": _read_csv,
        "parquet": _read_parquet,
        "jsonl": _read_jsonl,
        "json": _read_json,
    }[file_format]

    try:
        df = reader(path)
    except DatasetDoctorError:
        raise
    except (pl.exceptions.PolarsError, UnicodeDecodeError, OSError, ValueError) as exc:
        raise DataLoadError(
            f"Failed to parse {file_format.upper()} file '{path.name}': {_detail(exc)}",
            hint=_hint_for(file_format),
        ) from exc

    if df.width == 0:
        raise DataLoadError(
            f"'{path.name}' contains no columns.",
            hint="The file parsed successfully but has no usable header/schema.",
        )
    return LoadedDataset(
        df=df,
        file_format=file_format,
        path=path,
        file_size_bytes=file_size_bytes,
    )


def _read_csv(path: Path) -> pl.DataFrame:
    try:
        # Trailing blank lines would otherwise be parsed as phantom all-null
        # rows, poisoning every statistic; normalize the tail before parsing.
        normalized = _strip_trailing_blank_lines(path.read_bytes())
        df = pl.read_csv(
            io.BytesIO(normalized),
            try_parse_dates=True,
        )
    except pl.exceptions.NoDataError:
        # Header-only CSV: salvage the schema so a 0-row report is possible.
        header = _peek_csv_header(path)
        if header is not None:
            return pl.DataFrame(schema=dict.fromkeys(header, pl.String))
        raise
    return df


def _strip_trailing_blank_lines(data: bytes) -> bytes:
    """Trim any run of newline characters after the final data line."""
    body = data.rstrip(b"\r\n")
    if not body or len(body) == len(data):
        return data
    terminator = b"\r\n" if data.endswith(b"\r\n") else data[-1:]
    return body + terminator


def _read_parquet(path: Path) -> pl.DataFrame:
    return pl.read_parquet(path)


def _read_jsonl(path: Path) -> pl.DataFrame:
    return pl.read_ndjson(path)


def _read_json(path: Path) -> pl.DataFrame:
    try:
        return pl.read_json(path)
    except pl.exceptions.PolarsError:
        # Some .json files are actually newline-delimited; retry that shape.
        return pl.read_ndjson(path)


def _peek_csv_header(path: Path) -> list[str] | None:
    import csv

    try:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            row = next(csv.reader(handle), None)
    except (OSError, UnicodeDecodeError):
        return None
    return row if row else None


def _hint_for(file_format: FileFormat) -> str:
    hints = {
        "csv": (
            "Check the delimiter, quoting and encoding. The file must be "
            "valid UTF-8 with one consistent number of fields per row."
        ),
        "parquet": "The file may be truncated or corrupted; re-export it from the source.",
        "jsonl": (
            "Each line must be a flat JSON object. Nested documents are stored "
            "as-is; malformed lines will fail the whole read."
        ),
        "json": "Expected an array of flat JSON objects or newline-delimited objects.",
    }
    return hints[file_format]


def _detail(exc: Exception) -> str:
    text = " ".join(str(exc).split())
    if len(text) > _MAX_DETAIL_LENGTH:
        text = text[: _MAX_DETAIL_LENGTH - 3].rstrip() + "..."
    return text
