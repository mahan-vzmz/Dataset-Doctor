"""Report renderers: Rich console, JSON, and HTML."""

from __future__ import annotations

from dataset_doctor.reporting.console import render_report
from dataset_doctor.reporting.html_report import render_html, write_html
from dataset_doctor.reporting.json_report import render_json, write_json

__all__ = [
    "render_html",
    "render_json",
    "render_report",
    "write_html",
    "write_json",
]
