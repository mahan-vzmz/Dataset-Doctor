# Architecture

This document explains how Dataset Doctor is structured, why each dependency
exists, and how data flows through the pipeline.

## Pipeline

```
            ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐    ┌───────────┐
 file ─────► │   io    │───►│ profiling│───►│ quality  │───►│scoring │───►│ reporting │
             │readers  │    │          │    │detectors │    │        │    │           │
             └─────────┘    └──────────┘    └──────────┘    └────────┘    └───────────┘
                polars         polars         pure funcs     pure func      rich/json/html
                duckdb
```

`engine.analyze(path, thresholds)` orchestrates five steps:

1. **Load** (`io/readers.py`) - detect format by extension, read into a
   Polars `DataFrame`. All parse failures become `DataLoadError` with a hint.
2. **Profile** (`profiling/`) - dataset totals plus per-column statistics,
   computed dtype-aware (see below). Duplicate-row counting happens here via
   `io/duplicates.py`.
3. **Detect** (`quality/`) - five detector modules receive an immutable
   `AnalysisContext` (loaded data + profile + thresholds) and return
   `Finding` models. Findings are sorted deterministically.
4. **Score** (`scoring/scorer.py`) - aggregate findings into the capped-
   deduction health score (see `docs/health-score.md`).
5. **Report** (`reporting/`) - render the same `DoctorReport` model as a Rich
   terminal report, JSON, or self-contained HTML. The CLI never re-derives
   content; every output format is a projection of one model.

## Engine choices

### Polars (primary dataframe engine)

Chosen over pandas for three reasons:

- **Speed:** multithreaded Rust core; column profiling runs vectorized
  expressions instead of Python loops.
- **Dtypes:** strict dtypes make "don't compute meaningless statistics"
  enforceable - a `Float64` column *is* numeric, not "object with maybe
  numbers inside".
- **Interop:** Arrow-native memory layout keeps the door open for zero-copy
  exchange with DuckDB and other engines.

### DuckDB (set-based analytics)

Duplicate-row detection is a set operation: `COUNT(DISTINCT *)`. DuckDB
executes it against the **file on disk** (its native CSV/Parquet/NDJSON
readers), so:

- no Arrow/pyarrow bridge is required;
- large files stream through DuckDB's out-of-core aggregations rather than
  materializing twice;
- CSV columns are type-pinned from the Polars-inferred schema so both engines
  interpret rows identically.

When a dataset cannot be mapped (plain `.json` arrays, unmappable dtypes, or
any DuckDB error), `io/duplicates.py` falls back to an equivalent Polars
computation (`df.height − df.unique().height`). Results are identical; only
the engine differs.

### Pydantic v2 (models)

All cross-layer data structures are Pydantic models in `models/`: validated
construction, immutable-ish value semantics, and JSON serialization for free.
`Thresholds(frozen=True)` guarantees detectors cannot mutate configuration.

## Detector model

Each detector is a module exposing `run(ctx: AnalysisContext) -> list[Finding]`.
They are registered in a fixed pipeline tuple in `quality/__init__.py`.
Rules of the road:

- **Deterministic:** same input → same findings, same order (findings are
  sorted by severity → category → column → description).
- **Evidence-based:** every finding carries exact counts/percentages/thresholds
  used in the decision, plus a confidence value for heuristic rules.
- **No hidden state:** detectors read the context; they never touch the
  filesystem except the CSV header peek in the schema detector, which uses the
  path already recorded in the context.

## Error handling philosophy

- Expected user mistakes raise `DatasetDoctorError` subclasses carrying a
  message + optional hint. The CLI renders them as panels on stderr with exit
  code 2 - no tracebacks.
- Anything unexpected is caught at the CLI boundary, reported concisely, and
  exits 1; setting `DATASET_DOCTOR_DEBUG=1` prints the full traceback.
- Partial results are preferred over crashes where meaningful: a header-only
  CSV still yields a valid 0-row report; complex (struct/list) columns are
  profiled minimally instead of failing.

## Extension points

- **New format:** add a suffix mapping and a reader function in
  `io/readers.py`; optionally teach `io/duplicates.py` to map it for DuckDB.
- **New detector:** add `quality/<topic>.py` with `run(ctx)` and register it
  in `DETECTOR_PIPELINE`; add its scoring category/cap if needed.
- **New output format:** add a `render_*`/`write_*` pair under `reporting/`
  consuming `DoctorReport`.

## Testing strategy

Tests verify behavior, not internals: synthetic datasets are crafted to
trigger known problems (injected outliers, variant labels, ragged rows,
invalid UTF-8), and assertions check findings/scores/output text. The CLI is
tested through Typer's runner exactly as a user would drive it.
