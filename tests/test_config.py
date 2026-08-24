"""Config loading: defaults, overrides, and failure modes."""

from __future__ import annotations

from pathlib import Path

import pytest

from dataset_doctor.config import load_thresholds
from dataset_doctor.exceptions import ConfigError
from dataset_doctor.models.thresholds import Thresholds


def test_defaults_when_no_file() -> None:
    thresholds = Thresholds()
    assert thresholds.missing_critical_pct == 50.0
    assert thresholds.severity_points.warning == 4
    assert thresholds.category_caps.missingness == 35


def test_load_overrides_from_toml(tmp_path: Path) -> None:
    path = tmp_path / "doctor.toml"
    path.write_text(
        "missing_critical_pct = 40.0\ntop_k_frequent = 3\n"
        "[severity_points]\nwarning = 6\n"
        "[category_caps]\nschema_issues = 12\n",
        encoding="utf-8",
    )
    thresholds = load_thresholds(str(path))
    assert thresholds.missing_critical_pct == 40.0
    assert thresholds.top_k_frequent == 3
    assert thresholds.severity_points.warning == 6
    assert thresholds.category_caps.schema_issues == 12


def test_missing_config_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_thresholds(str(tmp_path / "missing.toml"))


def test_invalid_toml(tmp_path: Path) -> None:
    path = tmp_path / "broken.toml"
    path.write_text("this is [ not toml", encoding="utf-8")
    with pytest.raises(ConfigError, match="valid TOML"):
        load_thresholds(str(path))


def test_unknown_key_rejected(tmp_path: Path) -> None:
    path = tmp_path / "typo.toml"
    path.write_text("missing_critcal_pct = 10.0\n", encoding="utf-8")  # typo
    with pytest.raises(ConfigError):
        load_thresholds(str(path))


def test_inconsistent_ladder_rejected(tmp_path: Path) -> None:
    path = tmp_path / "ladder.toml"
    path.write_text("missing_warning_pct = 90.0\n", encoding="utf-8")  # > critical 50
    with pytest.raises(ConfigError) as excinfo:
        load_thresholds(str(path))
    hint = excinfo.value.hint
    assert hint is not None and "notice" in hint


def test_non_utf8_config(tmp_path: Path) -> None:
    path = tmp_path / "latin.toml"
    path.write_bytes(b"missing_critical_pct = \xff\n")
    with pytest.raises(ConfigError):
        load_thresholds(str(path))
