# Dataset Doctor

**A health check for tabular datasets.** Point it at a CSV, Parquet, JSON or
JSONL file and get an evidence-based report of what's wrong with your data -
no LLM required.

```text
Dataset Doctor
────────────────────────────────

Dataset Health: 70/100  (FAIR)

Rows:           403
Columns:         10
File size:   27.1 KB
Duplicate rows: 0.7% (3 rows)
Null cells:     2.0% of all values

Issues Found: 7

● WARNING (4)
    age → 'age' contains 3 values outside the IQR-based expected range [14, 62]
      ...
```

## Why Dataset Doctor exists

Most data quality tools are heavyweight platforms; most ad-hoc checks are a
pile of one-off notebooks. Dataset Doctor sits in between: a single, fast,
deterministic CLI that answers *"can I trust this file?"* before you build
anything on top of it - during ingestion triage, dataset onboarding, or
pre-flight checks in CI pipelines.

Every finding is backed by concrete numbers (counts, percentages, thresholds)
and every score deduction is itemized and explainable. No black boxes.

## Features

- **Formats:** CSV, Parquet, NDJSON (`.jsonl`/`.ndjson`) and flat JSON arrays
- **Profiling:** row/column counts, duplicate rows, per-column dtypes, nulls,
  uniqueness, numeric statistics (min/max/mean/median/std/quartiles/skewness),
  most frequent values, constants
- **Detection:** missingness ladder, exact duplicates, constant columns,
  IQR outliers, skewness, zero inflation, mixed-type text columns, duplicate
  or blank headers, inconsistent category labels, identifier-like columns
- **Scoring:** deterministic 0-100 health score with an itemized deduction
  breakdown
- **Output:** human terminal report (Rich), JSON (`--format json`,
  `--output`), self-contained HTML (`--html`)
- **Configurable:** every threshold tunable via a TOML file

## Installation

Requires Python **3.12+**. Using [uv](https://docs.astral.sh/uv/):

```bash
uv tool install dataset-doctor        # as a CLI tool (once published)
```

Or from a checkout of this repository:

```bash
git clone https://github.com/mahan-vzmz/Dataset-Doctor.git
cd Dataset-Doctor
uv sync                               # creates .venv and installs everything
uv run dataset-doctor --help
```

Or plain pip:

```bash
pip install .
dataset-doctor --help
```

## Quick start

```bash
dataset-doctor data.csv
```

That's it. The exit code is `0` when a report was produced and `2` when the
input could not be processed (missing file, unparsable content, bad config).

## CLI examples

```bash
# Human-readable report to the terminal
dataset-doctor data.csv

# Machine-readable JSON to stdout
dataset-doctor data.csv --format json

# Write reports to files
dataset-doctor data.csv --output report.json
dataset-doctor data.csv --html report.html

# Relax the missingness warning threshold via TOML config
dataset-doctor data.csv --config doctor.toml
```

Example `doctor.toml`:

```toml
missing_warning_pct = 30.0        # default 20.0
duplicate_warning_pct = 0.5       # default 1.0

[severity_points]                 # score points per finding severity
critical = 10
warning = 4
notice = 1

[category_caps]                   # max deduction per scoring category
schema_issues = 20                # note: "schema" is reserved, hence the name
```

## Example output

See [`examples/reports/`](examples/reports/) for real generated reports:

- [`messy_sales_report.html`](examples/reports/messy_sales_report.html) /
  `.json` / generated from [`examples/data/messy_sales.csv`](examples/data/messy_sales.csv)
- `healthy_customers_report.*` - a clean dataset that scores 96/100

Regenerate everything with:

```bash
uv run python scripts/generate_examples.py
```

## Health score methodology

The score is fully deterministic. For the complete formula with worked
examples see [`docs/health-score.md`](docs/health-score.md). In short:

1. Each finding contributes points by severity (critical 10 / warning 4 /
   notice 1 by default).
2. Points are summed per category: *missingness*, *duplicates*,
   *distribution*, *schema & types*, *cardinality & constants*.
3. Each category's deduction is capped (35 / 15 / 20 / 20 / 10 by default) so
   no single problem dominates.
4. `score = clamp(100 − Σ deductions, 0, 100)`.

Every non-zero deduction is printed with its raw points and cap, so you can
always reconstruct exactly why a dataset scored what it scored.

## Architecture

```text
src/dataset_doctor/
├── cli.py            # Typer app: flags, error rendering, exit codes
├── engine.py         # pipeline orchestration: load → profile → detect → score
├── config.py         # TOML threshold loading
├── io/               # format detection, readers, DuckDB duplicate scan
├── profiling/        # dataset-level and dtype-aware column statistics
├── quality/          # deterministic detectors (one module per concern)
├── scoring/          # capped-deduction health score
├── reporting/        # Rich console, JSON, self-contained HTML renderers
└── models/           # Pydantic domain models shared by all layers
```

Design notes:

- **Polars** is the primary dataframe engine: multithreaded, memory-efficient,
  with a strict dtype system.
- **DuckDB** scans files natively for set-based duplicate detection
  (`SELECT DISTINCT` over all columns); a pure-Polars fallback keeps results
  correct for inputs DuckDB cannot map.
- **Pydantic v2** models give validated profiles/findings and free JSON
  serialization.
- Detectors are pure functions over an immutable analysis context - no global
  state, fully deterministic ordering.

More detail in [`docs/architecture.md`](docs/architecture.md).

## Testing

```bash
uv run pytest          # 104 tests covering readers, profiling, detectors,
                       # scoring, reporting, config and CLI behavior
```

Synthetic datasets in the test suite are designed to trigger specific known
problems (injected outliers, variant labels, ragged CSVs, invalid UTF-8, ...).

## Development

```bash
uv sync                        # set up environment (Python 3.12)
uv run pytest                  # run tests
uv run ruff check .            # lint
uv run ruff format .           # format
uv run mypy src tests          # type check (strict-ish)
```

CI runs all four on Python 3.12 and 3.13 via GitHub Actions
(`.github/workflows/ci.yml`).

## Roadmap

- Streaming/lazy mode (DuckDB-backed) for larger-than-memory files
- Additional detectors: cross-column contradictions, date-order violations,
  encoding mojibake detection, near-duplicate fuzzy matching
- Schema drift comparison between two runs (`dataset-doctor diff`)
- Pluggable custom rules (Python entry-point based)
- SARIF output for native CI integration

## Limitations

- Datasets must fit in memory for full column profiling (the duplicate scan
  itself already streams from disk via DuckDB).
- Duplicate detection compares exact values only; `"1"` vs `1.0` across
  formats is handled by forcing identical types where possible.
- JSON support targets flat records; deeply nested documents are profiled at
  the top level with complex columns reported as such.
- The IQR outlier heuristic can flag legitimate tail values (~0.7% of Gaussian
  data); findings say so explicitly and thresholds are adjustable.
