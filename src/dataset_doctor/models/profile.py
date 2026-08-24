"""Profile models describing a dataset and each of its columns."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SemanticType = Literal["numeric", "boolean", "datetime", "categorical", "text", "complex"]


class FrequentValue(BaseModel):
    """One entry of a column's most-frequent-value list."""

    value: str
    count: int = Field(ge=0)
    #: Share of *non-null* values this value represents.
    pct: float = Field(ge=0.0, le=100.0)


class ColumnProfile(BaseModel):
    """Statistics for a single column.

    ``unique_count`` counts distinct non-null values; ``unique_pct`` is that
    count as a share of non-null rows. Numeric statistics use sample standard
    deviation (ddof=1).
    """

    name: str
    dtype: str
    semantic_type: SemanticType
    row_count: int = Field(ge=0)
    null_count: int = Field(ge=0)
    null_pct: float = Field(ge=0.0, le=100.0)
    unique_count: int = Field(ge=0)
    unique_pct: float = Field(ge=0.0, le=100.0)
    constant: bool

    # Rendered extreme values (numbers formatted, datetimes in ISO 8601).
    min_value: str | None = None
    max_value: str | None = None

    # Numeric-only statistics.
    mean_value: float | None = None
    std_value: float | None = None
    median_value: float | None = None
    q1_value: float | None = None
    q3_value: float | None = None
    skewness: float | None = None

    # Text-only statistics.
    avg_length: float | None = None

    most_frequent: list[FrequentValue] = Field(default_factory=list)


class DatasetProfile(BaseModel):
    """Dataset-level profile assembled from every :class:`ColumnProfile`."""

    source_path: str
    resolved_path: str
    file_format: str
    file_size_bytes: int | None
    row_count: int = Field(ge=0)
    column_count: int = Field(ge=0)
    duplicate_row_count: int = Field(ge=0)
    duplicate_pct: float = Field(ge=0.0, le=100.0)
    total_null_count: int = Field(ge=0)
    total_null_pct: float = Field(ge=0.0, le=100.0)
    columns: list[ColumnProfile] = Field(default_factory=list)

    @property
    def schema_map(self) -> dict[str, str]:
        """Mapping of column name to physical dtype string."""
        return {column.name: column.dtype for column in self.columns}

    def column(self, name: str) -> ColumnProfile | None:
        """Return the profile for ``name``, if present."""
        for column in self.columns:
            if column.name == name:
                return column
        return None
