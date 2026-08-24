"""Configurable thresholds for quality detection and health scoring."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SeverityPoints(BaseModel):
    """Health-score points contributed by a single finding of each severity."""

    model_config = ConfigDict(extra="forbid")

    critical: int = Field(default=10, ge=0)
    warning: int = Field(default=4, ge=0)
    notice: int = Field(default=1, ge=0)


class CategoryCaps(BaseModel):
    """Maximum deduction each scoring category can contribute."""

    model_config = ConfigDict(extra="forbid")

    missingness: int = Field(default=35, ge=0)
    duplicates: int = Field(default=15, ge=0)
    #: Named ``schema_issues`` to avoid clashing with reserved model attributes.
    schema_issues: int = Field(default=20, ge=0)
    distribution: int = Field(default=20, ge=0)
    cardinality: int = Field(default=10, ge=0)


class Thresholds(BaseModel):
    """Every tunable knob used by detectors and the scorer.

    Values can be overridden from a TOML file; keys map directly to field
    names (nested tables for ``severity_points`` / ``category_caps``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # --- missingness (% of null values in a column) -------------------------
    missing_critical_pct: float = Field(default=50.0, ge=0.0, le=100.0)
    missing_warning_pct: float = Field(default=20.0, ge=0.0, le=100.0)
    missing_notice_pct: float = Field(default=5.0, ge=0.0, le=100.0)

    # --- duplicate rows ------------------------------------------------------
    #: Flag when redundant rows exceed this share of the dataset...
    duplicate_warning_pct: float = Field(default=1.0, ge=0.0, le=100.0)
    # ...or exceed this absolute count (keeps large files from slipping by).
    duplicate_warning_min_rows: int = Field(default=10_000, ge=0)

    # --- numeric distributions ----------------------------------------------
    #: IQR multiplier for outlier fences.
    outlier_iqr_factor: float = Field(default=1.5, gt=0.0)
    #: Outliers are reported only between these bounds of the column;
    #: above ``outlier_max_pct`` the shape is treated as a distribution issue.
    outlier_min_pct: float = Field(default=0.5, ge=0.0)
    outlier_max_pct: float = Field(default=25.0, le=100.0)
    skew_warning_abs: float = Field(default=1.0, ge=0.0)
    skew_notice_abs: float = Field(default=0.5, ge=0.0)
    #: Columns with fewer non-null values skip distribution statistics.
    stats_min_rows: int = Field(default=30, ge=0)
    #: Share of exact-zero values that marks a numeric column as zero-inflated.
    zero_inflation_pct: float = Field(default=80.0, ge=0.0, le=100.0)

    # --- type consistency in string columns ---------------------------------
    mixed_type_critical_ratio: float = Field(default=0.6, ge=0.0, le=1.0)
    mixed_type_warning_ratio: float = Field(default=0.3, ge=0.0, le=1.0)

    # --- cardinality ---------------------------------------------------------
    #: Unique/non-null ratio above which a column looks like an identifier.
    id_like_unique_ratio: float = Field(default=0.95, ge=0.0, le=1.0)
    #: Minimum non-null rows before cardinality heuristics apply.
    cardinality_min_rows: int = Field(default=100, ge=0)
    #: Flag category columns whose distinct count collapses after trimming /
    #: case-folding to less than this fraction of the original.
    variant_collapse_ratio: float = Field(default=0.9, ge=0.0, le=1.0)
    #: Upper bound on distinct values for the variant-collapse heuristic.
    variant_max_unique: int = Field(default=500, ge=2)

    # --- profiling / reporting ----------------------------------------------
    top_k_frequent: int = Field(default=5, ge=1)

    # --- scoring --------------------------------------------------------------
    severity_points: SeverityPoints = SeverityPoints()
    category_caps: CategoryCaps = CategoryCaps()

    @model_validator(mode="after")
    def _check_ladders(self) -> Thresholds:
        if not (self.missing_notice_pct <= self.missing_warning_pct <= self.missing_critical_pct):
            raise ValueError(
                "missingness thresholds must satisfy "
                f"notice ({self.missing_notice_pct}) <= warning "
                f"({self.missing_warning_pct}) <= critical ({self.missing_critical_pct})"
            )
        if self.skew_notice_abs > self.skew_warning_abs:
            raise ValueError("skew_notice_abs must be <= skew_warning_abs")
        if self.outlier_min_pct > self.outlier_max_pct:
            raise ValueError("outlier_min_pct must be <= outlier_max_pct")
        if self.mixed_type_warning_ratio > self.mixed_type_critical_ratio:
            raise ValueError("mixed_type_warning_ratio must be <= mixed_type_critical_ratio")
        return self
