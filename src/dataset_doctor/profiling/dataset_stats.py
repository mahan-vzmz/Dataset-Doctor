"""Dataset-level profiling: assemble column profiles and totals."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dataset_doctor.io.duplicates import count_duplicate_rows
from dataset_doctor.profiling.column_stats import profile_columns

if TYPE_CHECKING:
    from dataset_doctor.io.readers import LoadedDataset
    from dataset_doctor.models.profile import DatasetProfile
    from dataset_doctor.models.thresholds import Thresholds


def profile_dataset(loaded: LoadedDataset, thresholds: Thresholds) -> DatasetProfile:
    """Build the full :class:`DatasetProfile` for ``loaded``, including duplicates."""
    from dataset_doctor.models.profile import DatasetProfile as _DatasetProfile

    df = loaded.df
    row_count = df.height
    duplicate_row_count = count_duplicate_rows(loaded)
    columns = profile_columns(df, thresholds.top_k_frequent)

    total_null_count = sum(column.null_count for column in columns)
    cell_count = row_count * df.width

    return _DatasetProfile(
        source_path=str(loaded.path),
        resolved_path=str(loaded.path.resolve()),
        file_format=loaded.file_format,
        file_size_bytes=loaded.file_size_bytes,
        row_count=row_count,
        column_count=df.width,
        duplicate_row_count=duplicate_row_count,
        duplicate_pct=(duplicate_row_count / row_count * 100.0) if row_count else 0.0,
        total_null_count=total_null_count,
        total_null_pct=(total_null_count / cell_count * 100.0) if cell_count else 0.0,
        columns=columns,
    )
