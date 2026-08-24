"""Exception hierarchy for handled errors.

The CLI catches :class:`DatasetDoctorError` and renders a friendly message;
anything else escaping to the CLI boundary is reported as an internal error.
"""

from __future__ import annotations


class DatasetDoctorError(Exception):
    """Base class for all expected, user-facing errors."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class UnsupportedFormatError(DatasetDoctorError):
    """The input file has an extension we cannot handle."""


class DataLoadError(DatasetDoctorError):
    """The file exists but could not be loaded or parsed."""


class ConfigError(DatasetDoctorError):
    """A user-supplied configuration file is invalid."""
