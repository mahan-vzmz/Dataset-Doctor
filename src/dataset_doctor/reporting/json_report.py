"""JSON report rendering."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dataset_doctor.models.report import DoctorReport


def render_json(report: DoctorReport, *, pretty: bool = True) -> str:
    """Serialize the report to JSON (enums as values, datetimes as ISO 8601)."""
    return report.model_dump_json(indent=2 if pretty else None)


def write_json(report: DoctorReport, path: Path) -> None:
    """Write the JSON report to ``path`` (UTF-8)."""
    path.write_text(render_json(report) + "\n", encoding="utf-8")
