"""MCP server and command-line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer
    from mcp.server.fastmcp.exceptions import ToolError

try:
    from mcp.types import ToolAnnotations

    _READ_ONLY = ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
    )
except ImportError:  # pragma: no cover - very old SDKs
    _READ_ONLY = None

from . import __version__
from .plan import build_plan
from .report import render_findings, render_requirements, render_rules
from .requirements import analyse
from .rules import RULES_BY_ID
from .scanner import scan

INSTRUCTIONS = (
    "Static analysis for legacy Python 2 / Django projects. All tools are read-only: they read source "
    "files under the path you give and never execute or import them. Start with `generate_migration_plan` "
    "for an overview, then drill down with `scan_python2_issues`, `scan_django_legacy` and "
    "`analyze_requirements`. Findings are heuristic: confirm each one in context before editing."
)

mcp = MCPServer("legacy-modernizer", instructions=INSTRUCTIONS)


def _check_path(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        raise ToolError(f"Path not found: {p}. Pass an existing directory or file.")
    return str(p)


def _limit(value: int) -> int:
    return max(1, min(int(value), 500))


@mcp.tool(annotations=_READ_ONLY)
def scan_python2_issues(path: str, max_findings: int = 100) -> str:
    """Scan a code base for Python 2 constructs that break or change behaviour on Python 3.

    Reports findings per rule (print statements, `except X, e`, `unicode`, `iteritems`,
    renamed stdlib modules, removed builtins, ...) with file, line and a suggested fix.
    Read-only. `path` is a directory or a single .py file; `max_findings` caps the
    detailed list (1-500), counts are always complete.
    """
    result = scan(_check_path(path))
    return render_findings(result, ("python2",), "Python 2 -> 3 findings", _limit(max_findings))


@mcp.tool(annotations=_READ_ONLY)
def scan_django_legacy(path: str, max_findings: int = 100) -> str:
    """Scan a Django project for APIs that were removed in newer Django releases.

    Covers urlpatterns/patterns(), render_to_response, MIDDLEWARE_CLASSES, TEMPLATE_* settings,
    South, ForeignKey without on_delete, is_authenticated(), django.utils.six, old template tags and
    more. Each rule notes the Django release that removed the API. Read-only.
    """
    result = scan(_check_path(path))
    return render_findings(result, ("django", "template"), "Legacy Django findings", _limit(max_findings))


@mcp.tool(annotations=_READ_ONLY)
def analyze_requirements(path: str) -> str:
    """Read requirements*.txt files and flag Python 2-only or obsolete packages.

    Detects the pinned Django version, suggests replacements (MySQL-python -> mysqlclient,
    PIL -> Pillow, South -> built-in migrations, ...) and lists unpinned requirements.
    `path` is a project directory or a requirements file. Read-only.
    """
    return render_requirements(analyse(_check_path(path)))


@mcp.tool(annotations=_READ_ONLY)
def generate_migration_plan(path: str) -> str:
    """Produce an ordered Python 2 -> 3 (and Django LTS upgrade) migration plan for a project.

    Combines all scans into a snapshot, a ranked list of hot-spot files, phases with the most
    frequent fixes first, the Django APIs that block each upgrade, dependency notes, and a manual
    review checklist for things static analysis cannot see. Read-only.
    """
    return build_plan(_check_path(path))


@mcp.tool(annotations=_READ_ONLY)
def list_rules(category: str = "") -> str:
    """List the built-in rules. `category` may be python2, django, template, or empty for all."""
    if category and category not in {"python2", "django", "template"}:
        raise ToolError("category must be one of: python2, django, template (or empty)")
    return render_rules(category or None)


@mcp.tool(annotations=_READ_ONLY)
def explain_rule(rule_id: str) -> str:
    """Explain one rule: what it flags, why it matters, how to fix it. Example: PY2-PRINT-STMT."""
    rule = RULES_BY_ID.get(rule_id.strip().upper())
    if rule is None:
        known = ", ".join(sorted(RULES_BY_ID))
        raise ToolError(f"Unknown rule '{rule_id}'. Known rules: {known}")
    lines = [
        f"## {rule.id}: {rule.title}",
        f"- Category: {rule.category}",
        f"- Severity: {rule.severity}",
        f"- Why it matters: {rule.explanation}",
        f"- Fix: {rule.fix}",
    ]
    if rule.removed_in:
        lines.append(f"- Removed in Django {rule.removed_in}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="legacy-modernizer-mcp",
        description="MCP server for legacy Python 2 / Django migration planning. "
        "Run with no arguments to start the server on stdio.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")
    plan_parser = sub.add_parser("plan", help="print a migration plan for PATH and exit")
    plan_parser.add_argument("path")
    sub.add_parser("rules", help="print the rule catalogue and exit")
    args = parser.parse_args(argv)

    if args.command == "plan":
        try:
            print(build_plan(_check_path(args.path)))
        except ToolError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(2)
        return
    if args.command == "rules":
        print(render_rules())
        return
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
