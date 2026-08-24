"""Typer CLI for Dataset Doctor."""

from __future__ import annotations

import os
import sys
import traceback
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

from dataset_doctor._version import get_version
from dataset_doctor.config import load_thresholds
from dataset_doctor.engine import analyze
from dataset_doctor.exceptions import DatasetDoctorError
from dataset_doctor.models.thresholds import Thresholds
from dataset_doctor.reporting import render_html, render_json, render_report

app = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
)

_stdout = Console()


def _stderr_console() -> Console:
    """Fresh stderr console so output honors stream redirection/capture."""
    return Console(file=sys.stderr)


def _stderr_print(renderable: object) -> None:
    _stderr_console().print(renderable)


class OutputFormat(StrEnum):
    """Supported stdout formats."""

    HUMAN = "human"
    JSON = "json"


def _fail(error: DatasetDoctorError) -> None:
    """Render a handled error to stderr without a traceback."""
    _stderr_print(Panel(f"[bold red]{error.message}[/bold red]", title="Error", expand=False))
    if error.hint:
        _stderr_print(f"[yellow]Hint:[/yellow] {error.hint}")


def _show_version(value: bool) -> None:
    if value:
        _stdout.print(f"dataset-doctor {get_version()}")
        raise typer.Exit()


@app.command()
def main(
    path: Annotated[
        Path,
        typer.Argument(help="Path to the dataset (.csv, .parquet, .json or .jsonl)."),
    ],
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Stdout report format."),
    ] = OutputFormat.HUMAN,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write a JSON report file."),
    ] = None,
    html_output: Annotated[
        Path | None,
        typer.Option("--html", help="Write an HTML report file."),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="TOML file overriding quality thresholds."),
    ] = None,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_show_version,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """Analyze a tabular dataset and print its health report."""
    try:
        thresholds = load_thresholds(str(config)) if config else Thresholds()
    except DatasetDoctorError as error:
        _fail(error)
        raise typer.Exit(code=2) from None

    try:
        report = analyze(str(path), thresholds)
        # Render everything up front so formatting bugs surface on the
        # guarded path instead of mid-write.
        json_text = render_json(report)
        html_text = render_html(report) if html_output is not None else None
    except DatasetDoctorError as error:
        _fail(error)
        raise typer.Exit(code=2) from None
    except Exception as error:
        if os.environ.get("DATASET_DOCTOR_DEBUG"):
            traceback.print_exc()
        _stderr_print(
            Panel(
                "[bold red]Internal error while analyzing the dataset.[/bold red]\n"
                f"{type(error).__name__}: {error}",
                title="Unexpected error",
                expand=False,
            )
        )
        _stderr_print(
            "Set DATASET_DOCTOR_DEBUG=1 to see the full traceback and please report this issue."
        )
        raise typer.Exit(code=1) from None

    if output_format is OutputFormat.JSON:
        # Raw stdout write: machine-readable output must never be wrapped
        # or styled by the terminal renderer.
        sys.stdout.write(json_text + "\n")
        sys.stdout.flush()
    else:
        render_report(report, _stdout)

    exit_code = 0
    for text, target in ((json_text, output), (html_text, html_output)):
        if target is None or text is None:
            continue
        try:
            target.write_text(text + "\n", encoding="utf-8")
        except OSError as error:
            _fail(DatasetDoctorError(f"Could not write report to '{target}': {error}"))
            exit_code = 2
            continue
        _stdout.print(f"[green]Report written:[/green] {target}")

    raise typer.Exit(code=exit_code)


if __name__ == "__main__":
    app()
