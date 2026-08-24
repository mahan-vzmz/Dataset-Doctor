"""Load user-supplied threshold overrides from a TOML file."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import ValidationError

from dataset_doctor.exceptions import ConfigError
from dataset_doctor.models.thresholds import Thresholds

_MAX_LISTED_ERRORS = 5


def load_thresholds(path_str: str) -> Thresholds:
    """Parse ``path_str`` into a :class:`Thresholds` instance.

    Top-level keys map directly to :class:`Thresholds` fields; nested tables
    map to nested models (``[severity_points]``, ``[category_caps]``).
    """
    path = Path(path_str)
    if not path.exists():
        raise ConfigError(
            f"Config file not found: {path}",
            hint="Pass --config pointing to an existing TOML file.",
        )
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(
            f"Config file is not valid TOML: {path.name}",
            hint=f"TOML parser said: {exc}",
        ) from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"Could not read config file: {path}", hint=str(exc)) from exc

    try:
        return Thresholds.model_validate(data)
    except ValidationError as exc:
        errors = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()[:_MAX_LISTED_ERRORS]
        )
        raise ConfigError(
            f"Invalid configuration in '{path.name}'",
            hint=errors,
        ) from exc
