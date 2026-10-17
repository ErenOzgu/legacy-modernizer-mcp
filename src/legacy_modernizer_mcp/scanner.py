"""Read-only source scanner.

Walks a directory (or a single file), masks strings and comments, and runs the
rules from :mod:`legacy_modernizer_mcp.rules`. Nothing is executed or imported
from the scanned project.
"""

from __future__ import annotations

import bisect
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .rules import RULES, Rule

SKIP_DIRS = frozenset(
    {
        ".git", ".hg", ".svn", ".tox", ".eggs", ".venv", "venv", "virtualenv",
        "node_modules", "__pycache__", "site-packages", ".mypy_cache",
        ".pytest_cache", ".idea", ".vscode",
    }
)
MAX_FILE_BYTES = 1_000_000
PY_SUFFIXES = frozenset({".py"})
TEMPLATE_SUFFIXES = frozenset({".html", ".htm", ".txt"})

_TEST_FILE = re.compile(r"^(?:test_.*\.py|.*_test\.py|tests\.py)$")
_DJANGO_IMPORT = re.compile(r"^[ \t]*(?:from|import)[ \t]+django\b", re.MULTILINE)
_PLAIN = re.compile(r"[^#'\"]+")


# --------------------------------------------------------------------------- #
# Masking
# --------------------------------------------------------------------------- #


def _string_end(source: str, start: int) -> int:
    """Index just past the string literal that starts at ``start``."""
    n = len(source)
    quote = source[start]
    if source.startswith(quote * 3, start):
        j = start + 3
        while j < n:
            if source[j] == "\\":
                j += 2
            elif source.startswith(quote * 3, j):
                return j + 3
            else:
                j += 1
        return n
    j = start + 1
    while j < n:
        ch = source[j]
        if ch == "\\":
            j += 2
        elif ch == quote:
            return j + 1
        elif ch == "\n":
            return j  # unterminated: stop at end of line
        else:
            j += 1
    return n


def _blank_string(segment: str, quote: str) -> str:
    """Keep the delimiters, replace the body with 'x' (newlines survive)."""
    if segment.startswith(quote * 3):
        open_len = 3
        close_len = 3 if len(segment) >= 6 and segment.endswith(quote * 3) else 0
    else:
        open_len = 1
        close_len = 1 if len(segment) >= 2 and segment.endswith(quote) else 0
    body = segment[open_len : len(segment) - close_len]
    masked = "".join(ch if ch == "\n" else "x" for ch in body)
    return quote * open_len + masked + quote * close_len


def mask_source(source: str, keep_strings: bool = False) -> str:
    """Blank out comments (and string bodies unless ``keep_strings``).

    The result has the same length and the same newlines as the input, so
    offsets and line numbers map one-to-one onto the original text.
    """
    out: list[str] = []
    i, n = 0, len(source)
    while i < n:
        m = _PLAIN.match(source, i)
        if m:
            out.append(m.group())
            i = m.end()
            continue
        c = source[i]
        if c == "#":
            j = source.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i))
            i = j
        else:  # a quote
            j = _string_end(source, i)
            segment = source[i:j]
            out.append(segment if keep_strings else _blank_string(segment, c))
            i = j
    return "".join(out)


# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Finding:
    rule_id: str
    file: str
    line: int
    snippet: str
    detail: str = ""


@dataclass
class ScanResult:
    root: str
    python_files: int = 0
    template_files: int = 0
    lines_of_code: int = 0
    test_files: int = 0
    uses_django: bool = False
    has_manage_py: bool = False
    findings: list[Finding] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def counts_by_rule(self) -> Counter[str]:
        return Counter(f.rule_id for f in self.findings)


# --------------------------------------------------------------------------- #
# Walking and scanning
# --------------------------------------------------------------------------- #


def iter_files(root: Path):
    """Yield candidate files, pruning virtualenvs, VCS folders and symlinks."""
    if root.is_file():
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info")
        )
        for name in sorted(filenames):
            path = Path(dirpath, name)
            if path.suffix in PY_SUFFIXES | TEMPLATE_SUFFIXES and not path.is_symlink():
                yield path


def _line_starts(text: str) -> list[int]:
    return [0] + [m.end() for m in re.finditer("\n", text)]


def _run_rules(
    rules: list[Rule],
    rel: str,
    original_lines: list[str],
    masked: str,
    kept: str,
    out: set[Finding],
) -> None:
    starts = _line_starts(masked)

    def add(rule: Rule, offset: int, detail: str) -> None:
        line = bisect.bisect_right(starts, offset)
        snippet = original_lines[line - 1].strip()[:160] if line <= len(original_lines) else ""
        out.add(Finding(rule.id, rel, line, snippet, detail))

    for rule in rules:
        if rule.skip_file_if and rule.skip_file_if.search(masked):
            continue
        text = kept if rule.keep_strings else masked
        if rule.pattern is not None:
            for m in rule.pattern.finditer(text):
                add(rule, m.start(), rule.detail(m) if rule.detail else "")
        if rule.check is not None:
            for offset, detail in rule.check(masked):
                add(rule, offset, detail)


def scan(path: str | os.PathLike[str]) -> ScanResult:
    """Scan ``path`` (a directory or a single file) and return all findings."""
    root = Path(path).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Path does not exist: {root}")
    base = root if root.is_dir() else root.parent
    result = ScanResult(root=str(root))

    code_rules = [r for r in RULES if r.category in ("python2", "django")]
    template_rules = [r for r in RULES if r.category == "template"]
    found: set[Finding] = set()

    for file in iter_files(root):
        rel = file.relative_to(base).as_posix()
        try:
            size = file.stat().st_size
            if size > MAX_FILE_BYTES:
                result.skipped.append(f"{rel} (larger than {MAX_FILE_BYTES // 1000} kB)")
                continue
            source = file.read_bytes().decode("utf-8", errors="replace")
        except OSError as exc:
            result.skipped.append(f"{rel} ({exc.__class__.__name__})")
            continue
        source = source.replace("\r\n", "\n").replace("\r", "\n")
        lines = source.split("\n")

        if file.suffix in PY_SUFFIXES:
            result.python_files += 1
            result.lines_of_code += sum(1 for ln in lines if ln.strip())
            if file.name == "manage.py":
                result.has_manage_py = True
            if _TEST_FILE.match(file.name) or "tests" in file.relative_to(base).parts[:-1]:
                result.test_files += 1
            masked = mask_source(source)
            kept = mask_source(source, keep_strings=True)
            if _DJANGO_IMPORT.search(masked):
                result.uses_django = True
            _run_rules(code_rules, rel, lines, masked, kept, found)
        else:
            result.template_files += 1
            _run_rules(template_rules, rel, lines, source, source, found)

    result.findings = sorted(found, key=lambda f: (f.file, f.line, f.rule_id))
    return result
