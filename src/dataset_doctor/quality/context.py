"""Detector context shared by all quality rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from dataset_doctor.io.readers import LoadedDataset
    from dataset_doctor.models.profile import DatasetProfile
    from dataset_doctor.models.thresholds import Thresholds


@dataclass(frozen=True)
class AnalysisContext:
    """Everything a detector may need, passed explicitly (no global state)."""

    loaded: LoadedDataset
    profile: DatasetProfile
    thresholds: Thresholds

    @property
    def df(self) -> pl.DataFrame:
        return self.loaded.df
