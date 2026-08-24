"""Generate the example datasets under ``examples/data``.

Deterministic: seeded RNG, no network access.

Usage:
    uv run python scripts/generate_examples.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from random import Random

import polars as pl

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples" / "data"

CITIES = ["Berlin", "Paris", "Madrid", "Vienna", "Warsaw"]


def healthy_customers(rng: Random) -> pl.DataFrame:
    """A clean dataset that should score near 100."""
    n = 600
    first_names = ["Alex", "Sam", "Robin", "Jamie", "Casey"]
    return pl.DataFrame(
        {
            "customer_id": list(range(1000, 1000 + n)),
            # Repeated real-world names keep cardinality natural (not ID-like).
            "name": [f"{rng.choice(first_names)} {i % 120}" for i in range(n)],
            "email": [f"user{i % 520}@example.com" for i in range(n)],
            "age": [min(max(int(rng.gauss(40, 8)), 22), 72) for _ in range(n)],
            "city": [CITIES[i % len(CITIES)] for i in range(n)],
            "signup_date": [date(2022, 1, 1) + timedelta(days=i % 900) for i in range(n)],
            "is_active": [bool(i % 3) for i in range(n)],
            "monthly_spend": [round(abs(rng.gauss(50, 15)), 2) for _ in range(n)],
        }
    )


def messy_sales(rng: Random) -> pl.DataFrame:
    """Deliberately broken: triggers findings across all categories."""
    n = 400
    rows = []
    for i in range(n):
        age = int(rng.gauss(38, 9))
        if i == 17:
            age = 999  # outlier
        if i % 5 == 0:
            age = None  # 20% missingness -> warning
        city = rng.choice(["NYC", "NYC ", "nyc", "Boston"])
        income = max(int(rng.lognormvariate(0, 0.4)) * 1000, 0)  # right-skewed
        # Mostly numeric strings, some '$'-prefixed: forces the column to text.
        amount = rng.randrange(100, 999)
        price_text = f"${amount}" if rng.random() < 0.2 else str(amount)
        rows.append(
            {
                "order_id": f"ORD-{rng.randrange(10_000)}",
                "customer_id": i,
                "age": age,
                "income": income,
                "city": city,
                "country": "USA",  # constant
                "price_text": price_text,
                "discount_code": rng.choice(["", "", "SAVE10", "SAVE20"]),
                "notes": f"note {i} - {rng.random():.6f}",
                "created": date(2024, 3, 1) + timedelta(days=i % 60),
            }
        )
    frame = pl.DataFrame(rows)
    # Exact duplicate rows -> duplicate detection.
    frame = pl.concat([frame, frame[3], frame[7], frame[7]])
    return frame


def sensor_readings(rng: Random) -> pl.DataFrame:
    """Medium-quality parquet dataset: some nulls, few duplicates."""
    n = 300
    temperature = []
    for _ in range(n):
        value = round(rng.gauss(21, 2), 1)
        temperature.append(None if rng.random() < 0.08 else value)  # moderate nulls
    frame = pl.DataFrame(
        {
            "sensor_id": [f"S{i % 12:02d}" for i in range(n)],
            "temperature_c": pl.Series(temperature, dtype=pl.Float64),
            "humidity_pct": [round(min(max(rng.gauss(45, 8), 0), 100), 1) for _ in range(n)],
            "error_count": [
                0 if rng.random() < 0.85 else int(rng.randrange(1, 5)) for _ in range(n)
            ],
            "reading_ts": [(date(2025, 1, 1) + timedelta(minutes=i)).isoformat() for i in range(n)],
        }
    )
    return pl.concat([frame, frame[11]])


def main() -> None:
    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    rng = Random(42)

    healthy_path = EXAMPLES_DIR / "healthy_customers.csv"
    healthy_customers(rng).write_csv(healthy_path)

    messy_path = EXAMPLES_DIR / "messy_sales.csv"
    messy_sales(rng).write_csv(messy_path)

    sensor_path = EXAMPLES_DIR / "sensor_readings.parquet"
    sensor_readings(rng).write_parquet(sensor_path)

    print(f"Wrote: {healthy_path}")
    print(f"Wrote: {messy_path}")
    print(f"Wrote: {sensor_path}")
    sys.exit(0)


if __name__ == "__main__":
    main()
