"""Dataset Doctor - a health check for tabular datasets."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dataset_doctor.models.report import DoctorReport
    from dataset_doctor.models.thresholds import Thresholds

from dataset_doctor._version import get_version

__version__ = get_version()


def analyze(
    path: str,
    thresholds: Thresholds | None = None,
) -> DoctorReport:
    """Analyze a dataset file and produce a full health report.

    This is the programmatic entry point equivalent to running
    ``dataset-doctor <path>`` on the command line.
    """
    from dataset_doctor.engine import analyze as _analyze

    return _analyze(path, thresholds)


__all__ = ["__version__", "analyze"]
