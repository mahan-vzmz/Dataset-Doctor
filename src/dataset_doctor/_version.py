"""Single source of truth for the package version."""

from __future__ import annotations

import importlib.metadata

_FALLBACK_VERSION = "0.0.0+unknown"


def get_version() -> str:
    """Return the installed distribution version, or a fallback marker."""
    try:
        return importlib.metadata.version("dataset-doctor")
    except importlib.metadata.PackageNotFoundError:
        return _FALLBACK_VERSION
