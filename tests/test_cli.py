"""End-to-end CLI behavior via Typer's test runner."""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from dataset_doctor.cli import app

runner = CliRunner()


def _combined(result: Result) -> str:
    """Stdout and stderr combined, regardless of click's capture mode."""
    stderr_text = ""
    with contextlib.suppress(ValueError, AttributeError):
        stderr_text = result.stderr
    return str(result.output) + "\n" + stderr_text


def test_human_report_on_clean_data(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("clean.csv", "a,b\n1,x\n2,y\n3,z\n")
    result = runner.invoke(app, [str(path)])
    assert result.exit_code == 0
    assert "Dataset Health" in result.output
    assert "100/100" in result.output


def test_json_output_flag(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("data.csv", "a,b\n1,x\n2,y\n")
    result = runner.invoke(app, [str(path), "--format", "json"])
    assert result.exit_code == 0
    assert '"tool": "dataset-doctor"' in result.output


def test_output_and_html_flags(
    write_file: Callable[[str, str | bytes], Path], tmp_path: Path
) -> None:
    path = write_file("data.csv", "a,b\n1,x\n2,y\n")
    json_path = tmp_path / "out.json"
    html_path = tmp_path / "out.html"
    result = runner.invoke(
        app,
        [
            str(path),
            "--output",
            str(json_path),
            "--html",
            str(html_path),
        ],
    )
    assert result.exit_code == 0
    assert json_path.exists() and html_path.exists()
    assert '"findings"' in json_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html_path.read_text(encoding="utf-8")
    assert "Report written" in result.output


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "dataset-doctor" in result.output


def test_nonexistent_file_exit_2(tmp_path: Path) -> None:
    result = runner.invoke(app, [str(tmp_path / "missing.csv")])
    assert result.exit_code == 2
    assert "not found" in _combined(result).lower()


def test_unsupported_format_exit_2(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("sheet.xlsx", "binary-ish")
    result = runner.invoke(app, [str(path)])
    assert result.exit_code == 2
    assert "unsupported" in _combined(result).lower()
    # No raw traceback for user errors.
    assert "Traceback" not in _combined(result)


def test_empty_file_exit_2(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("empty.csv", "")
    result = runner.invoke(app, [str(path)])
    assert result.exit_code == 2
    assert "0 bytes" in _combined(result)


def test_malformed_csv_exit_2_no_traceback(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("ragged.csv", b"a,b,c\n1,2,3\n9,9\n\xff\xfe\n")
    result = runner.invoke(app, [str(path)])
    assert result.exit_code == 2
    assert "Traceback" not in _combined(result)


def test_header_only_csv_succeeds(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("header_only.csv", "a,b\n")
    result = runner.invoke(app, [str(path)])
    assert result.exit_code == 0
    assert "Rows:" in result.output
    assert "0" in result.output


def test_single_column_csv_succeeds(write_file: Callable[[str, str | bytes], Path]) -> None:
    path = write_file("single.csv", "v\n3\n1\n2\n")
    result = runner.invoke(app, [str(path)])
    assert result.exit_code == 0


@pytest.mark.parametrize(
    "toml",
    [
        "not_valid_toml [[",
        "unknown_key = 1\n",
        "missing_warning_pct = 90.0\n",
    ],
)
def test_bad_config_exit_2(
    write_file: Callable[[str, str | bytes], Path],
    toml: str,
) -> None:
    data = write_file("data.csv", "a\n1\n")
    config = write_file("cfg.toml", toml)
    result = runner.invoke(app, [str(data), "--config", str(config)])
    assert result.exit_code == 2
    assert "Traceback" not in _combined(result)


def test_good_config_changes_result(write_file: Callable[[str, str | bytes], Path]) -> None:
    # 25% missing column: warning under defaults, silent when threshold raised.
    rows = "\n".join([""] * 25 + ["1"] * 75)
    data = write_file("partial.csv", f"c\n{rows}\n")
    config = write_file("relaxed.toml", "missing_warning_pct = 30.0\n")

    default_run = runner.invoke(app, [str(data), "--format", "json"])
    relaxed_run = runner.invoke(app, [str(data), "--format", "json", "--config", str(config)])

    assert default_run.exit_code == 0 and relaxed_run.exit_code == 0
    import json

    default_score = json.loads(default_run.output)["health_score"]["score"]
    relaxed_score = json.loads(relaxed_run.output)["health_score"]["score"]
    assert relaxed_score > default_score


def test_unwritable_output_target(
    write_file: Callable[[str, str | bytes], Path], tmp_path: Path
) -> None:
    data = write_file("data.csv", "a\n1\n")
    target = tmp_path / "no-such-dir" / "report.json"  # parent does not exist
    result = runner.invoke(app, [str(data), "--output", str(target)])
    assert result.exit_code == 2
    assert "Could not write report" in _combined(result)


def test_help_mentions_examples() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--format" in result.output
    assert "--html" in result.output
