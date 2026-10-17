from __future__ import annotations

import asyncio

import pytest

from legacy_modernizer_mcp import __version__
from legacy_modernizer_mcp.rules import RULES
from legacy_modernizer_mcp.server import ToolError, main, mcp

try:
    from mcp.server.mcpserver.exceptions import UnexpectedToolError
except ImportError:  # mcp 1.x wraps every error in ToolError with the original message
    UnexpectedToolError = ()  # type: ignore[assignment]

EXPECTED_TOOLS = {
    "scan_python2_issues",
    "scan_django_legacy",
    "analyze_requirements",
    "generate_migration_plan",
    "list_rules",
    "explain_rule",
}


def _text(result) -> str:
    content = getattr(result, "content", None)
    if content is None:  # mcp 1.x returns the content list (or a tuple with structured output)
        content = result[0] if isinstance(result, tuple) else result
    return "\n".join(block.text for block in content)


def _call(name: str, **arguments) -> str:
    return _text(asyncio.run(mcp.call_tool(name, arguments)))


def test_tools_are_registered_and_read_only():
    tools = asyncio.run(mcp.list_tools())
    assert {t.name for t in tools} == EXPECTED_TOOLS
    for tool in tools:
        hints = tool.annotations.model_dump(by_alias=True, exclude_none=True)
        assert hints["readOnlyHint"] is True
        assert hints["destructiveHint"] is False
        assert tool.description


def test_scan_python2_issues_tool(legacy_project):
    out = _call("scan_python2_issues", path=str(legacy_project))
    assert "PY2-PRINT-STMT" in out and "shop/views.py:10" in out
    assert "DJ-PATTERNS" not in out


def test_scan_django_legacy_tool(legacy_project):
    out = _call("scan_django_legacy", path=str(legacy_project))
    assert "DJ-FK-ON-DELETE" in out and "TPL-LOAD-FROM-FUTURE" in out
    assert "PY2-PRINT-STMT" not in out


def test_max_findings_truncates_detail_list(legacy_project):
    out = _call("scan_python2_issues", path=str(legacy_project), max_findings=1)
    assert out.count("shop/") <= 3  # one detailed entry, not all of them


def test_analyze_requirements_tool(legacy_project):
    out = _call("analyze_requirements", path=str(legacy_project))
    assert "mysqlclient" in out and "Pillow" in out


def test_generate_migration_plan_tool(legacy_project):
    assert "# Migration plan" in _call("generate_migration_plan", path=str(legacy_project))


def test_list_rules_tool():
    out = _call("list_rules")
    assert all(rule.id in out for rule in RULES)
    only_django = _call("list_rules", category="django")
    assert "DJ-PATTERNS" in only_django and "PY2-PRINT-STMT" not in only_django


def test_explain_rule_is_case_insensitive():
    out = _call("explain_rule", rule_id="dj-fk-on-delete")
    assert "DJ-FK-ON-DELETE" in out and "Removed in Django 2.0" in out


def test_errors_carry_a_readable_message(tmp_path):
    # Plain exceptions are hidden from clients by the SDK; ToolError messages reach the model.
    with pytest.raises(ToolError, match="Path not found") as exc:
        _call("scan_python2_issues", path=str(tmp_path / "missing"))
    assert not isinstance(exc.value, UnexpectedToolError)
    with pytest.raises(ToolError, match="Unknown rule"):
        _call("explain_rule", rule_id="NOPE")
    with pytest.raises(ToolError, match="category"):
        _call("list_rules", category="java")


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_cli_plan(legacy_project, capsys):
    main(["plan", str(legacy_project)])
    assert "# Migration plan: legacy_project" in capsys.readouterr().out


def test_cli_plan_missing_path(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["plan", str(tmp_path / "missing")])
    assert exc.value.code == 2
    assert "Path not found" in capsys.readouterr().err


def test_cli_rules(capsys):
    main(["rules"])
    out = capsys.readouterr().out
    assert "PY2-PRINT-STMT" in out and "TPL-LOAD-FROM-FUTURE" in out
