"""Deterministic quality detectors."""

from __future__ import annotations

from dataset_doctor.quality.cardinality import run as run_cardinality
from dataset_doctor.quality.context import AnalysisContext
from dataset_doctor.quality.distribution import run as run_distribution
from dataset_doctor.quality.duplicates import run as run_duplicates
from dataset_doctor.quality.missingness import run as run_missingness
from dataset_doctor.quality.schema_types import run as run_schema_types

#: Fixed evaluation order; final ordering is applied by the engine's sort.
DETECTOR_PIPELINE = (
    run_schema_types,
    run_missingness,
    run_duplicates,
    run_distribution,
    run_cardinality,
)

__all__ = ["DETECTOR_PIPELINE", "AnalysisContext"]
