"""Distribution detectors: IQR outliers, skewness, zero inflation."""

from __future__ import annotations

import math
from pathlib import Path

import polars as pl

from dataset_doctor.models.findings import FindingCategory, Severity
from dataset_doctor.models.thresholds import Thresholds
from dataset_doctor.quality.distribution import run
from tests.conftest import find_one, make_context


def test_injected_outliers_detected(tmp_path: Path) -> None:
    values = [float(i) for i in range(1, 101)] + [1000.0, 1001.0, 1002.0]
    df = pl.DataFrame({"x": values})
    finding = find_one(
        run(make_context(df, tmp_path)),
        category=FindingCategory.DISTRIBUTION,
        column="x",
        severity=Severity.WARNING,
        description_contains="IQR-based expected range",
    )
    assert "3 values" in finding.description
    # Fences must be reported in the evidence.
    assert "Q1 - 1.5xIQR" in finding.evidence


def test_clean_gaussian_has_no_outlier_warning(tmp_path: Path) -> None:
    import random

    rng = random.Random(7)
    values = [rng.gauss(50, 5) for _ in range(500)]
    df = pl.DataFrame({"x": values})
    # Gaussian tails sit near ~0.7% beyond IQR fences; with a 2% floor the
    # clean sample must stay silent (deterministic for this seed).
    thresholds = Thresholds(outlier_min_pct=2.0)
    findings = [
        f for f in run(make_context(df, tmp_path, thresholds=thresholds)) if f.column == "x"
    ]
    assert findings == []


def test_outliers_respect_configurable_bounds(tmp_path: Path) -> None:
    values = [float(i) for i in range(1, 101)] + [1000.0]
    df = pl.DataFrame({"x": values})  # 1/103 < default min pct 0.5? -> 0.97% ok.
    strict = Thresholds(outlier_min_pct=2.0)
    findings = [
        f
        for f in run(make_context(df, tmp_path, thresholds=strict))
        if f.column == "x" and "IQR" in f.description
    ]
    assert findings == []  # 0.97% below the configured 2% floor


def test_highly_skewed_column_warns(tmp_path: Path) -> None:
    values = [math.exp(0.08 * i) for i in range(80)]  # strongly right-skewed
    df = pl.DataFrame({"income": values})
    finding = find_one(
        run(make_context(df, tmp_path)),
        category=FindingCategory.DISTRIBUTION,
        column="income",
        severity=Severity.WARNING,
        description_contains="skewed distribution",
    )
    assert "skewness" in finding.description


def test_symmetric_column_stays_silent(tmp_path: Path) -> None:
    values = [10.0, 20.0] * 30
    df = pl.DataFrame({"sym": values})
    findings = [f for f in run(make_context(df, tmp_path)) if f.column == "sym"]
    assert findings == []


def test_zero_inflation_notice(tmp_path: Path) -> None:
    values = [0.0] * 90 + [1.5, 2.5, 3.5, 4.5, 5.0, 6.0]
    df = pl.DataFrame({"defects": values})
    finding = find_one(
        run(make_context(df, tmp_path)),
        category=FindingCategory.DISTRIBUTION,
        column="defects",
        severity=Severity.NOTICE,
    )
    assert "zero-inflated" in finding.description
    assert "90 of 96" in finding.evidence


def test_small_columns_skip_distribution_checks(tmp_path: Path) -> None:
    df = pl.DataFrame({"x": [1.0, 2.0, 3.0, 100000.0]})
    findings = run(make_context(df, tmp_path))
    assert findings == []  # below stats_min_rows gate


def test_constant_numeric_column_skews_nothing(tmp_path: Path) -> None:
    df = pl.DataFrame({"flat": [5.0] * 50})
    findings = run(make_context(df, tmp_path))
    assert findings == []


def test_zero_iqr_does_not_flag_outliers(tmp_path: Path) -> None:
    # 80 rows of 5.0, 10 rows of 4.0, 10 rows of 6.0 -> Q1=5.0, Q3=5.0, IQR=0
    df = pl.DataFrame({"x": [5.0] * 80 + [4.0] * 10 + [6.0] * 10})
    findings = [f for f in run(make_context(df, tmp_path)) if "IQR" in f.description]
    assert findings == []
