"""Shared fixtures and helpers for the test suite."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import polars as pl
import pytest

from dataset_doctor.io.readers import LoadedDataset
from dataset_doctor.models.findings import Finding, FindingCategory, Severity
from dataset_doctor.models.profile import DatasetProfile
from dataset_doctor.models.thresholds import Thresholds
from dataset_doctor.profiling.dataset_stats import profile_dataset
from dataset_doctor.quality.context import AnalysisContext


def make_loaded(
    df: pl.DataFrame,
    tmp_path: Path,
    fmt: str = "parquet",
    path: Path | None = None,
) -> LoadedDataset:
    """Wrap a frame in a LoadedDataset; ``path`` need not exist on disk."""
    return LoadedDataset(
        df=df,
        file_format=fmt,  # type: ignore[arg-type]
        path=path or (tmp_path / f"dataset.{fmt}"),
        file_size_bytes=1024,
    )


def make_context(
    df: pl.DataFrame,
    tmp_path: Path,
    thresholds: Thresholds | None = None,
    fmt: str = "parquet",
) -> AnalysisContext:
    """Build a full AnalysisContext (with profile) for detector tests."""
    effective = thresholds or Thresholds()
    loaded = make_loaded(df, tmp_path, fmt)
    profile: DatasetProfile = profile_dataset(loaded, effective)
    return AnalysisContext(loaded=loaded, profile=profile, thresholds=effective)


@pytest.fixture
def write_file(tmp_path: Path) -> Callable[[str, str | bytes], Path]:
    """Factory writing content to a file inside tmp_path."""

    def _write(name: str, content: str | bytes) -> Path:
        path = tmp_path / name
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    return _write


def find_one(
    findings: list[Finding],
    *,
    category: FindingCategory,
    column: str | None = None,
    severity: Severity | None = None,
    description_contains: str | None = None,
) -> Finding:
    """Return the single matching finding, failing loudly otherwise."""
    matches = [
        finding
        for finding in findings
        if finding.category is category
        and (column is None or finding.column == column)
        and (severity is None or finding.severity is severity)
        and (description_contains is None or description_contains in finding.description)
    ]
    assert len(matches) == 1, f"expected exactly 1 match, got {len(matches)}: {matches}"
    return matches[0]
