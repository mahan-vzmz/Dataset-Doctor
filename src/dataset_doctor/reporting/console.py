"""Human-readable terminal report rendered with Rich."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from dataset_doctor.models.findings import Severity
from dataset_doctor.utils import format_bytes, format_count, format_pct

if TYPE_CHECKING:
    from dataset_doctor.models.findings import Finding
    from dataset_doctor.models.report import DoctorReport


def _pick_symbol(preferred: str, fallback: str) -> str:
    """Prefer Unicode symbols but degrade cleanly on limited consoles (cp1252)."""
    encoding = sys.stdout.encoding or "ascii"
    try:
        preferred.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return fallback
    return preferred


DOT = _pick_symbol("\u25cf", "*")
CHECK_MARK = _pick_symbol("\u2713", "+")
CROSS_MARK = _pick_symbol("\u2717", "x")
ARROW = _pick_symbol("\u2192", "->")

SEVERITY_SYMBOLS: dict[Severity, str] = {
    Severity.CRITICAL: f"[red]{DOT}[/red]",
    Severity.WARNING: f"[dark_orange]{DOT}[/dark_orange]",
    Severity.NOTICE: f"[yellow]{DOT}[/yellow]",
}

GRADE_STYLES: dict[str, str] = {
    "GOOD": "bold green",
    "FAIR": "bold yellow",
    "POOR": "bold dark_orange",
    "CRITICAL": "bold red",
}


def render_report(report: DoctorReport, console: Console | None = None) -> None:
    """Print the full human-readable report."""
    console = console or Console()

    console.print(
        Panel(
            Text.assemble(
                ("Dataset Doctor ", "bold cyan"),
                (f"v{report.version}", "dim"),
            ),
            subtitle=f"[dim]{report.source_path}[/dim]",
            expand=False,
        )
    )

    score_style = GRADE_STYLES.get(report.health_score.grade, "bold white")
    console.print()
    console.print(
        Text.assemble(
            ("Dataset Health: ", "bold"),
            (f"{report.health_score.score}/100", score_style),
            (f"  ({report.health_score.grade})", "dim"),
        )
    )
    _print_deductions(report, console)
    _print_dataset_stats(report, console)

    total_issues = report.summary.total
    issues_line = Text.assemble(("Issues Found: ", "bold"), (format_count(total_issues), "bold"))
    console.print(issues_line)
    if total_issues == 0:
        console.print("[green]No issues detected with current thresholds.[/green]")

    for severity in Severity:
        findings = [f for f in report.findings if f.severity is severity]
        if not findings:
            continue
        console.print()
        count_label = format_count(len(findings))
        console.print(
            f"{SEVERITY_SYMBOLS[severity]} [bold]{severity.value.upper()}[/bold] ({count_label})"
        )
        for finding in findings:
            _print_finding(console, finding)

    console.print()
    for check in report.checks:
        mark = CHECK_MARK if check.passed else CROSS_MARK
        line = f"{mark} {check.name}: {check.status}"
        if check.detail:
            line += f" [dim]({check.detail})[/dim]"
        console.print(line)

    console.print()
    console.print(
        f"[dim]Generated {report.generated_at.isoformat(timespec='seconds')} "
        f"by dataset-doctor v{report.version}[/dim]"
    )


def _print_deductions(report: DoctorReport, console: Console) -> None:
    deductions = report.health_score.deductions
    if not deductions:
        return
    table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
    table.add_column(justify="left")
    table.add_column(justify="right")
    table.add_column("Cap", justify="right", style="dim")
    for item in deductions:
        table.add_row(item.label, f"-{item.deduction}", f"(raw {item.points}, cap {item.cap})")
    console.print(Text("Deductions:", "bold"))
    console.print(table)


def _print_dataset_stats(report: DoctorReport, console: Console) -> None:
    profile = report.dataset
    size = format_bytes(profile.file_size_bytes) or "n/a"
    grid = Table.grid(padding=(0, 3))
    grid.add_column(style="bold", justify="right")
    grid.add_column()
    rows = [
        ("Rows:", format_count(profile.row_count)),
        ("Columns:", format_count(profile.column_count)),
        ("File size:", size),
        (
            "Duplicate rows:",
            (
                f"{format_pct(profile.duplicate_pct)} "
                f"({format_count(profile.duplicate_row_count)} rows)"
                if profile.duplicate_row_count
                else "NONE"
            ),
        ),
        (
            "Null cells:",
            f"{format_pct(profile.total_null_pct)} of all values" if profile.row_count else "n/a",
        ),
    ]
    for label, value in rows:
        grid.add_row(label, value)
    console.print(grid)


def _print_finding(console: Console, finding: Finding) -> None:
    subject = finding.column if finding.column is not None else "(dataset)"
    console.print(f"    [bold]{subject}[/bold] {ARROW} {finding.description}")
    console.print(f"      [dim]{finding.evidence}[/dim]")
    console.print(f"      [cyan]Fix:[/cyan] {finding.recommendation}")
