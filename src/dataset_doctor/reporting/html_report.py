"""Self-contained HTML report (no external assets or JavaScript)."""

from __future__ import annotations

import html
from pathlib import Path
from typing import TYPE_CHECKING

from dataset_doctor.models.findings import Severity
from dataset_doctor.models.score import ScoreCategoryBreakdown
from dataset_doctor.utils import format_bytes, format_count, format_pct

if TYPE_CHECKING:
    from dataset_doctor.models.findings import Finding
    from dataset_doctor.models.profile import ColumnProfile
    from dataset_doctor.models.report import DoctorReport

_SEVERITY_LABELS = {
    Severity.CRITICAL: "CRITICAL",
    Severity.WARNING: "WARNING",
    Severity.NOTICE: "NOTICE",
}

_CSS = """
:root { --bg:#f6f8fa; --card:#ffffff; --text:#1f2328; --muted:#656d76;
        --critical:#cf222e; --warning:#bc4c00; --notice:#9a6700; --ok:#1a7f37;
        --border:#d0d7de; }
* { box-sizing:border-box; }
body { margin:0; padding:2rem; background:var(--bg); color:var(--text);
       font:15px/1.5 system-ui,-apple-system,'Segoe UI',sans-serif; }
main { max-width:1080px; margin:0 auto; }
h1 { font-size:1.6rem; margin:0 0 .25rem; }
.meta { color:var(--muted); font-size:.85rem; margin-bottom:1.5rem; }
.card { background:var(--card); border:1px solid var(--border);
        border-radius:10px; padding:1.25rem 1.5rem; margin-bottom:1.25rem; }
.score-row { display:flex; align-items:center; gap:1.25rem; }
.score { font-size:3rem; font-weight:700; }
.grade { padding:.2rem .75rem; border-radius:999px; color:#fff;
         font-weight:600; font-size:.85rem; }
.grid { display:flex; flex-wrap:wrap; gap:.5rem 2rem; }
.stat b { display:block; font-size:1.05rem; }
.stat span { color:var(--muted); font-size:.8rem; }
table { border-collapse:collapse; width:100%; margin-top:.5rem; }
th, td { text-align:left; padding:.4rem .6rem; border-bottom:1px solid var(--border); }
th { color:var(--muted); font-weight:600; font-size:.85rem; }
.finding { border-left:4px solid var(--border); padding:.35rem 0 .35rem .85rem;
           margin:.6rem 0; }
.finding.critical { border-color:var(--critical); }
.finding.warning { border-color:var(--warning); }
.finding.notice { border-color:var(--notice); }
.badge { font-size:.72rem; font-weight:700; letter-spacing:.05em; }
.sev-critical { color:var(--critical); } .sev-warning { color:var(--warning); }
.sev-notice { color:var(--notice); }
.col-name { font-weight:600; }
.evidence, .fix { color:var(--muted); font-size:.88rem; }
.fix::before { content:'Fix: '; color:var(--ok); font-weight:600; }
.checks li { list-style:none; padding:.15rem 0; }
.checks ul { padding-left:0; margin:.4rem 0 0; }
.pass { color:var(--ok); } .fail { color:var(--critical); }
footer { color:var(--muted); font-size:.8rem; margin-top:1.5rem; }
"""


def render_html(report: DoctorReport) -> str:
    """Render the report as a single self-contained HTML document."""
    profile = report.dataset
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>Dataset Doctor - {html.escape(profile.source_path)}</title>",
        f"<style>{_CSS}</style></head><body><main>",
        "<h1>Dataset Doctor</h1>",
        _meta_line(report),
        _score_card(report),
        _stats_grid(report),
        _deductions_table(report.health_score.deductions),
        _checks_section(report),
        _findings_section(report),
        _columns_section(profile.columns),
        f"<footer>Generated {html.escape(report.generated_at.isoformat(timespec='seconds'))} "
        f"by dataset-doctor v{html.escape(report.version)}. "
        f"Score methodology: severity points capped per category.</footer>",
        "</main></body></html>",
    ]
    return "\n".join(parts)


def write_html(report: DoctorReport, path: Path) -> None:
    """Write the HTML report to ``path`` (UTF-8)."""
    path.write_text(render_html(report), encoding="utf-8")


def _meta_line(report: DoctorReport) -> str:
    return (
        f"<p class='meta'>Source: <code>{html.escape(report.source_path)}</code>"
        f" &middot; format: {html.escape(report.dataset.file_format)}</p>"
    )


def _score_card(report: DoctorReport) -> str:
    score = report.health_score
    grade_colors = {
        "GOOD": "#1a7f37",
        "FAIR": "#9a6700",
        "POOR": "#bc4c00",
        "CRITICAL": "#cf222e",
    }
    color = grade_colors.get(score.grade, "#656d76")
    return (
        "<div class='card'><div class='score-row'>"
        "<div class='score'>"
        f"{score.score}<span style='font-size:1.4rem;color:#656d76'>/100</span></div>"
        "<div><span class='grade' style='background:"
        f"{color}'>{html.escape(score.grade)}</span>"
        "<p style='margin:.4rem 0 0;color:#656d76;font-size:.9rem'>"
        "Deterministic score: severity points per finding, capped per category."
        "</p></div></div></div>"
    )


def _stats_grid(report: DoctorReport) -> str:
    profile = report.dataset
    stats = [
        ("Rows", format_count(profile.row_count)),
        ("Columns", format_count(profile.column_count)),
        ("File size", format_bytes(profile.file_size_bytes) or "n/a"),
        (
            "Duplicate rows",
            f"{format_pct(profile.duplicate_pct)} ({format_count(profile.duplicate_row_count)})",
        ),
        ("Null cells", f"{format_pct(profile.total_null_pct)}"),
    ]
    cells = "".join(
        f"<div class='stat'><b>{html.escape(value)}</b><span>{html.escape(label)}</span></div>"
        for label, value in stats
    )
    return f"<div class='card'><div class='grid'>{cells}</div></div>"


def _deductions_table(deductions: list[ScoreCategoryBreakdown]) -> str:
    if not deductions:
        return "<div class='card'><b>Deductions:</b> none - no issues found.</div>"
    rows = "".join(
        f"<tr><td>{html.escape(item.label)}</td><td>-{item.deduction}</td>"
        f"<td>{item.points}</td><td>{item.cap}</td><td>{item.finding_count}</td></tr>"
        for item in deductions
    )
    return (
        "<div class='card'><b>Deductions by category</b>"
        "<table><tr><th>Category</th><th>Deduction</th><th>Raw points</th>"
        f"<th>Cap</th><th>Findings</th></tr>{rows}</table></div>"
    )


def _checks_section(report: DoctorReport) -> str:
    items = "".join(
        f"<li><span class='{'pass' if check.passed else 'fail'}'>"
        f"{'&#10003;' if check.passed else '&#10007;'}</span> "
        f"{html.escape(check.name)}: <b>{html.escape(check.status)}</b></li>"
        for check in report.checks
    )
    return f"<div class='card checks'><b>Checks</b><ul>{items}</ul></div>"


def _findings_section(report: DoctorReport) -> str:
    if not report.findings:
        return "<div class='card'><b>No issues detected with current thresholds.</b></div>"
    blocks: list[str] = [
        f"<div class='card'><b>Issues found ({format_count(len(report.findings))})</b>"
    ]
    for severity in Severity:
        findings = [f for f in report.findings if f.severity is severity]
        if not findings:
            continue
        for finding in findings:
            blocks.append(_finding_block(finding))
    blocks.append("</div>")
    return "".join(blocks)


def _finding_block(finding: Finding) -> str:
    subject = finding.column if finding.column is not None else "(dataset)"
    confidence = f"{finding.confidence:.0%}"
    return (
        f"<div class='finding {finding.severity.value}'>"
        f"<span class='badge sev-{finding.severity.value}'>"
        f"{_SEVERITY_LABELS[finding.severity]}</span> "
        f"&middot; {html.escape(finding.category.value)} &middot; "
        f"confidence {confidence}"
        f"<div><span class='col-name'>{html.escape(subject)}</span> \u2192 "
        f"{html.escape(finding.description)}</div>"
        f"<div class='evidence'>{html.escape(finding.evidence)}</div>"
        f"<div class='fix'>{html.escape(finding.recommendation)}</div>"
        "</div>"
    )


def _columns_section(columns: list[ColumnProfile]) -> str:
    rows = []
    for column in columns:
        rows.append(
            "<tr>"
            f"<td>{html.escape(column.name)}</td>"
            f"<td>{html.escape(column.dtype)}</td>"
            f"<td>{html.escape(column.semantic_type)}</td>"
            f"<td>{format_pct(column.null_pct)}</td>"
            f"<td>{format_pct(column.unique_pct)}</td>"
            f"<td>{html.escape(column.min_value or '-')}</td>"
            f"<td>{html.escape(column.max_value or '-')}</td>"
            f"<td>{column.mean_value if column.mean_value is not None else '-'}</td>"
            f"<td>{column.std_value if column.std_value is not None else '-'}</td>"
            "</tr>"
        )
    return (
        "<div class='card'><b>Column profiles</b>"
        "<table><tr><th>Column</th><th>Type</th><th>Semantic</th><th>Null %</th>"
        "<th>Unique %</th><th>Min</th><th>Max</th><th>Mean</th><th>Std</th></tr>"
        f"{''.join(rows)}</table></div>"
    )
