# Health Score Methodology

Dataset Doctor's health score is a **deterministic, explainable** number in
`[0, 100]`. Given the same dataset and thresholds, the score is always
identical. This document specifies the exact computation.

## Inputs

The only inputs are the set of findings produced by the detectors and the
scoring configuration (see `[severity_points]` / `[category_caps]` in the TOML
config).

Severity points per finding (defaults):

| Severity | Points |
|----------|--------|
| critical | 10     |
| warning  | 4      |
| notice   | 1      |

Category caps (maximum deduction, defaults):

| Category                | Cap |
|-------------------------|-----|
| missingness             | 35  |
| duplicates              | 15  |
| distribution            | 20  |
| schema & types          | 20  |
| cardinality & constants | 10  |

## Computation

```
raw_points[c]   = Σ severity_points[f.severity]   for all findings f in category c
deduction[c]    = min(raw_points[c], cap[c])
total_deduction = Σ deduction[c]
score           = clamp(100 − total_deduction, 0, 100)
```

Grades: `GOOD ≥ 85`, `FAIR ≥ 70`, `POOR ≥ 50`, otherwise `CRITICAL`.

Because caps sum to exactly 100, the score can always reach 0 for a
sufficiently broken dataset, and an issue-free dataset always scores 100.

## Worked example

Findings on `examples/data/messy_sales.csv` (actual output):

| Category | Findings | Raw points | Cap | Deduction |
|---|---|---|---|---|
| schema & types | 1 critical (mixed-type text) | 10 | 20 | 10 |
| cardinality & constants | 2 warnings + 2 notices | 10 | 10 | 10 |
| outliers & distribution | 2 warnings + 1 notice | 9 | 20 | 9 |
| missing values | 1 notice | 1 | 35 | 1 |

Total deduction = `10 + 10 + 9 + 1` = **30** → **score 70/100 (FAIR)**.

## Why this design?

- **Explainable:** every deduction appears on the report with raw points and
  the applied cap; nothing is hidden inside a weighted average.
- **Monotone:** more/severer findings never increase the score.
- **Bounded:** category caps prevent one pathological column from masking
  other problems.
- **Configurable:** teams with different risk tolerance can retune severity
  weights or caps without touching code.

## Detector-to-category mapping

| Detector module | Category |
|---|---|
| `quality/missingness.py` | missingness |
| `quality/duplicates.py` | duplicates |
| `quality/distribution.py` | distribution |
| `quality/schema_types.py` | schema |
| `quality/cardinality.py` | cardinality |

## Threshold defaults

Detection thresholds (separate from scoring) also live in `Thresholds`
(`src/dataset_doctor/models/thresholds.py`) with documented defaults:

- missingness rungs: notice 5% / warning 20% / critical 50%
- duplicate warning: 1% of rows or 10,000 redundant rows
- outlier fences: Q1 − 1.5·IQR / Q3 + 1.5·IQR, reported when between
  0.5% and 25% of non-null values are outside
- skewness: warning at |skew| ≥ 1.0, notice at ≥ 0.5 (sample skewness)
- zero inflation: notice at ≥ 80% exact zeros
- mixed-type text columns: critical ≥ 60% parseable-but-text, notice at 100%
