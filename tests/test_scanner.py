from __future__ import annotations

import os

import pytest

from legacy_modernizer_mcp import scanner
from legacy_modernizer_mcp.scanner import scan

EXPECTED_LEGACY = {
    "shop/models.py": {"DJ-PY2-TEXT-HELPERS", "PY2-DUNDER-METHODS", "DJ-PERMALINK", "DJ-FK-ON-DELETE"},
    "shop/settings.py": {
        "DJ-TEMPLATE-SETTINGS",
        "DJ-CONTEXT-PROCESSORS",
        "DJ-SOUTH",
        "DJ-MIDDLEWARE-CLASSES",
    },
    "shop/templates/shop/list.html": {"TPL-LOAD-FROM-FUTURE"},
    "shop/urls.py": {"DJ-PATTERNS", "DJ-URL-STRING-VIEW", "DJ-ADMIN-URLS-INCLUDE"},
    "shop/utils.py": {
        "PY2-ITERTOOLS",
        "PY2-OCTAL",
        "PY2-LONG-LITERAL",
        "PY2-STRING-MODULE",
        "PY2-MAXINT",
        "PY2-HAS-KEY",
        "PY2-NE-OPERATOR",
        "PY2-DICT-VIEW-INDEX",
        "PY2-BACKTICK",
        "PY2-EXEC-STMT",
        "PY2-REMOVED-BUILTIN",
        "PY2-METACLASS",
        "PY2-DUNDER-METHODS",
    },
    "shop/views.py": {
        "PY2-OLD-IMPORT",
        "DJ-URLRESOLVERS",
        "DJ-RENDER-TO-RESPONSE",
        "PY2-DICT-ITER",
        "PY2-PRINT-STMT",
        "PY2-EXCEPT-COMMA",
        "PY2-RAISE-COMMA",
        "DJ-IS-AUTH-CALL",
        "PY2-XRANGE",
        "PY2-UNICODE",
    },
}


def test_legacy_fixture_findings_per_file(legacy_project):
    result = scan(legacy_project)
    by_file: dict[str, set[str]] = {}
    for f in result.findings:
        by_file.setdefault(f.file, set()).add(f.rule_id)
    assert by_file == EXPECTED_LEGACY


def test_legacy_fixture_metadata(legacy_project):
    result = scan(legacy_project)
    assert result.uses_django
    assert result.has_manage_py
    assert result.python_files == 8
    assert result.template_files == 2  # list.html and requirements.txt
    assert result.test_files == 1
    assert result.lines_of_code > 50
    assert result.skipped == []


def test_legacy_fixture_line_numbers_and_snippets(legacy_project):
    result = scan(legacy_project)
    hit = next(f for f in result.findings if f.rule_id == "PY2-PRINT-STMT")
    assert (hit.file, hit.line) == ("shop/views.py", 10)
    assert hit.snippet == 'print "price", key, value'


def test_fk_on_delete_only_flags_calls_without_on_delete(legacy_project):
    lines = [
        f.line
        for f in scan(legacy_project).findings
        if f.rule_id == "DJ-FK-ON-DELETE"
    ]
    assert lines == [18, 19]


def test_clean_project_has_no_findings(clean_project):
    result = scan(clean_project)
    assert result.findings == []
    assert not result.uses_django


def test_scan_single_file(legacy_project):
    result = scan(legacy_project / "shop" / "utils.py")
    assert result.python_files == 1
    assert {f.file for f in result.findings} == {"utils.py"}


def test_scan_missing_path_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        scan(tmp_path / "nope")


def test_scan_is_deterministic(legacy_project):
    assert scan(legacy_project).findings == scan(legacy_project).findings


def test_skip_dirs_are_not_scanned(tmp_path):
    for d in ("venv", ".git", "node_modules", "__pycache__", "pkg.egg-info"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "bad.py").write_text('print "x"\n')
    (tmp_path / "ok.py").write_text("x = 1\n")
    result = scan(tmp_path)
    assert result.python_files == 1
    assert result.findings == []


def test_large_files_are_skipped_and_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(scanner, "MAX_FILE_BYTES", 20)
    (tmp_path / "big.py").write_text("x = 1\n" * 20)
    result = scan(tmp_path)
    assert result.python_files == 0
    assert len(result.skipped) == 1 and "big.py" in result.skipped[0]


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_symlinked_files_are_ignored(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text('print "x"\n')
    project = tmp_path / "project"
    project.mkdir()
    try:
        os.symlink(outside / "secret.py", project / "link.py")
    except OSError:  # pragma: no cover - e.g. Windows without privileges
        pytest.skip("cannot create symlinks")
    assert scan(project).python_files == 0


def test_crlf_and_bom_free_decoding(tmp_path):
    (tmp_path / "w.py").write_bytes(b'x = 1\r\nprint "a"\r\ny = 2\r\n')
    findings = scan(tmp_path).findings
    assert [(f.rule_id, f.line) for f in findings] == [("PY2-PRINT-STMT", 2)]


def test_undecodable_bytes_do_not_crash(tmp_path):
    (tmp_path / "latin.py").write_bytes(b"# caf\xe9\nprint 'x'\n")
    assert {f.rule_id for f in scan(tmp_path).findings} == {"PY2-PRINT-STMT"}


def test_scanner_never_executes_code(tmp_path):
    marker = tmp_path / "marker.txt"
    (tmp_path / "evil.py").write_text(
        f"open({str(marker)!r}, 'w').write('ran')\nprint 'x'\n"
    )
    scan(tmp_path)
    assert not marker.exists()
