"""Input loading and format handling."""

from __future__ import annotations

from dataset_doctor.io.duplicates import count_duplicate_rows
from dataset_doctor.io.readers import (
    SUPPORTED_SUFFIXES,
    FileFormat,
    LoadedDataset,
    detect_format,
    load_dataset,
)

__all__ = [
    "SUPPORTED_SUFFIXES",
    "FileFormat",
    "LoadedDataset",
    "count_duplicate_rows",
    "detect_format",
    "load_dataset",
]
