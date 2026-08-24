"""Report rendering: JSON structure, HTML safety, console determinism."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from dataset_doctor.engine import analyze
from dataset_doctor.models.report import DoctorReport
from dataset_doctor.reporting.console import render_report
from dataset_doctor.reporting.html_report import render_html
from dataset_doctor.reporting.json_report import render_json


def _analyze_csv(path: Path) -> DoctorReport:
    from dataset_doctor.models.thresholds import Thresholds

    return analyze(str(path), Thresholds())


def test_json_round_trip(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("data.csv", "a,b\n1,1.5\n2,\n1,3.5\n")
    report = _analyze_csv(path)
    payload = json.loads(render_json(report))

    assert payload["tool"] == "dataset-doctor"
    assert payload["version"]
    assert payload["health_score"]["score"] == payload["health_score"]["score"]  # stable key
    assert isinstance(payload["health_score"]["score"], int)
    assert payload["dataset"]["row_count"] == 3
    assert {f["severity"] for f in payload["findings"]} <= {"critical", "warning", "notice"}
    for finding in payload["findings"]:
        assert set(finding) == {
            "severity",
            "category",
            "column",
            "description",
            "evidence",
            "confidence",
            "recommendation",
        }


def test_json_is_deterministic_apart_from_timestamp(
    write_file: Callable[[str, str | bytes], Path],
) -> None:
    path = write_file("data.csv", "a,b\n1,x\n2,y\n")
    first = json.loads(render_json(_analyze_csv(path)))
    second = json.loads(render_json(_analyze_csv(path)))
    # Everything except the timestamp must be identical between runs.
    del first["generated_at"], second["generated_at"]
    assert first == second


def test_html_escapes_hostile_column_names(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file(
        "evil.csv",
        '"<script>alert(1)</script>",b\n1,2\n2,3\n',
    )
    html = render_html(_analyze_csv(path))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_html_contains_core_sections(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("ok.csv", "a,b\n1,x\n2,y\n")
    html = render_html(_analyze_csv(path))
    for marker in ("Dataset Doctor", "/100", "Checks", "Column profiles"):
        assert marker in html


def test_console_render_smoke(
    write_file: Callable[[str, str | bytes], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = write_file("data.csv", "a,b\n1,x\n2,y\n")
    render_report(_analyze_csv(path))
    output = capsys.readouterr().out
    assert "Dataset Health" in output
    assert "Rows:" in output
    assert "Issues Found:" in output
