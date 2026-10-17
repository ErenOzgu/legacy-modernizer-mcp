"""Markdown renderers shared by the MCP tools, the CLI and the plan generator."""

from __future__ import annotations

from collections import Counter

from .requirements import RequirementsReport
from .rules import RULES, RULES_BY_ID
from .scanner import Finding, ScanResult

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
SEVERITY_WEIGHT = {"error": 3, "warning": 2, "info": 1}


def _severity_counts(findings: list[Finding]) -> Counter[str]:
    return Counter(RULES_BY_ID[f.rule_id].severity for f in findings)


def severity_summary(findings: list[Finding]) -> str:
    c = _severity_counts(findings)
    return f"{c['error']} errors, {c['warning']} warnings, {c['info']} info"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_findings(
    result: ScanResult,
    categories: tuple[str, ...],
    title: str,
    max_findings: int = 100,
) -> str:
    findings = [f for f in result.findings if RULES_BY_ID[f.rule_id].category in categories]
    lines = [
        f"## {title}",
        "",
        f"Scanned {result.python_files} Python files ({result.lines_of_code} non-blank lines) "
        f"and {result.template_files} template/text files under `{result.root}`.",
        f"Findings: {severity_summary(findings)}.",
    ]
    if result.skipped:
        lines.append(f"Skipped {len(result.skipped)} file(s): " + ", ".join(result.skipped[:5]))
    if not findings:
        lines += ["", "No findings. The heuristics found nothing to flag in these files."]
        return "\n".join(lines)

    counts = Counter(f.rule_id for f in findings)
    ordered = sorted(
        counts,
        key=lambda rid: (SEVERITY_ORDER[RULES_BY_ID[rid].severity], -counts[rid], rid),
    )
    lines += ["", "### By rule", "", "| Rule | Severity | Count | Meaning | Fix |", "|---|---|---|---|---|"]
    for rid in ordered:
        r = RULES_BY_ID[rid]
        lines.append(
            f"| `{rid}` | {r.severity} | {counts[rid]} | {_cell(r.title + ': ' + r.explanation)} | {_cell(r.fix)} |"
        )

    shown = sorted(
        findings,
        key=lambda f: (SEVERITY_ORDER[RULES_BY_ID[f.rule_id].severity], f.file, f.line),
    )[:max_findings]
    lines += ["", f"### Findings (showing {len(shown)} of {len(findings)})", ""]
    for f in shown:
        detail = f" ({f.detail})" if f.detail else ""
        lines.append(f"- `{f.file}:{f.line}` **{f.rule_id}**{detail}: `{f.snippet}`")
    return "\n".join(lines)


def render_requirements(report: RequirementsReport) -> str:
    if not report.files:
        return (
            "## Dependencies\n\nNo requirements files found (looked for `requirements*.txt` and "
            "`requirements/*.txt`). Pass the project root, or the file itself."
        )
    lines = [
        "## Dependencies",
        "",
        f"Read {len(report.requirements)} requirement(s) from: " + ", ".join(f"`{f}`" for f in report.files) + ".",
    ]
    if report.django_version:
        lines.append(f"Django: `{report.django_spec}` (detected {report.django_version[0]}.{report.django_version[1]}).")
    elif any(r.name == "django" for r in report.requirements):
        lines.append("Django is listed but the version could not be determined from the specifier.")
    if report.issues:
        lines += ["", "| Package | Specifier | Severity | Note |", "|---|---|---|---|"]
        for issue in sorted(report.issues, key=lambda i: (SEVERITY_ORDER[i.severity], i.requirement.name)):
            r = issue.requirement
            lines.append(f"| `{r.raw_name}` | `{r.spec or '-'}` | {issue.severity} | {_cell(issue.note)} |")
    else:
        lines += ["", "No known Python 2-only or obsolete packages found in the list."]
    if report.unpinned:
        names = ", ".join(f"`{r.raw_name}`" for r in report.unpinned[:15])
        more = "" if len(report.unpinned) <= 15 else f" and {len(report.unpinned) - 15} more"
        lines += [
            "",
            f"{len(report.unpinned)} requirement(s) have no version specifier ({names}{more}). "
            "Pin them before migrating so you know what you are upgrading from.",
        ]
    lines += [
        "",
        "_Package notes are a short built-in list, not a full compatibility database. "
        "Check each dependency's release notes for Python 3 support._",
    ]
    return "\n".join(lines)


def render_rules(category: str | None = None) -> str:
    names = {"python2": "Python 2 -> 3", "django": "Legacy Django", "template": "Django templates"}
    lines: list[str] = []
    for cat, label in names.items():
        if category and category != cat:
            continue
        lines += [f"### {label}", "", "| Rule | Severity | What it flags | Removed in Django |", "|---|---|---|---|"]
        for r in (r for r in RULES if r.category == cat):
            lines.append(f"| `{r.id}` | {r.severity} | {_cell(r.title)} | {r.removed_in or ''} |")
        lines.append("")
    return "\n".join(lines).rstrip()
