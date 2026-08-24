"""Deterministic, locale-independent value formatting helpers."""

from __future__ import annotations

import math


def format_count(value: int) -> str:
    """Format an integer with thousands separators (e.g. ``124,532``)."""
    return f"{value:,}"


def format_pct(value: float, digits: int = 1) -> str:
    """Format a percentage with fixed digits (e.g. ``3.1%``)."""
    return f"{value:.{digits}f}%"


def format_number(value: float | int | None, *, integer_hint: bool = False) -> str | None:
    """Render a number without float noise.

    ``integer_hint`` forces integer formatting even for float-typed values
    whose fractional part is zero.
    """
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        return str(value)
    if integer_hint or number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.6g}"


_BYTE_UNITS = ("bytes", "KB", "MB", "GB", "TB")


def format_bytes(size: int | None) -> str | None:
    """Humanize a byte count (e.g. ``12.3 MB``)."""
    if size is None:
        return None
    display = float(size)
    unit_index = 0
    while display >= 1024.0 and unit_index < len(_BYTE_UNITS) - 1:
        display /= 1024.0
        unit_index += 1
    if unit_index == 0:
        return f"{int(display)} {_BYTE_UNITS[0]}"
    return f"{display:.1f} {_BYTE_UNITS[unit_index]}"
