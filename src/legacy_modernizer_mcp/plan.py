"""Turn scan results into an ordered migration plan (Markdown)."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from .report import SEVERITY_WEIGHT, render_requirements, severity_summary
from .requirements import analyse
from .rules import RULES_BY_ID
from .scanner import scan

LTS_STEPS = ["1.8", "1.11", "2.2", "3.2", "4.2", "5.2"]
PY2_COMPATIBLE_STEPS = {"1.8", "1.11"}

CHECKLIST = [
    "**Text vs bytes.** Python 3 separates `str` and `bytes`. Review every place data crosses a boundary: "
    "files opened in text vs binary mode, sockets, subprocess output, hashing, base64, pickles, database drivers.",
    "**Division.** `/` on integers is true division on Python 3. Use `//` where floor division was intended "
    "(or add `from __future__ import division` while still on 2.7 and run the tests).",
    "**Dict views and iterators.** `keys()`, `values()`, `items()`, `map()`, `filter()`, `zip()` and `range()` "
    "no longer return lists. Code that indexes, sorts, mutates while iterating, or iterates twice needs a look.",
    "**Implicit relative imports.** `import sibling` inside a package worked on Python 2 and fails on Python 3. "
    "Use absolute imports or explicit relative imports.",
    "**Ordering.** `cmp` is gone and comparing unrelated types raises `TypeError`. Check sorting and `min`/`max` "
    "over mixed data.",
    "**Numbers.** `round()` rounds half to even on Python 3; integer overflow to `long` no longer exists.",
    "**Persisted data.** Pickles, shelves and marshal files written by Python 2 may not load on Python 3. "
    "Test real data, not fixtures.",
    "**Exceptions.** `e.message` is gone; `sys.exc_clear()` is gone; exception variables are deleted after the "
    "`except` block.",
    "**Compiled and system dependencies.** C extensions, database drivers and system packages need Python 3 "
    "builds; verify them early because they are the usual long pole.",
]


def _vt(version: str) -> tuple[int, int]:
    major, minor = version.split(".")[:2]
    return int(major), int(minor)


def _hot_spots(findings, limit: int = 10):
    score: Counter[str] = Counter()
    errors: Counter[str] = Counter()
    for f in findings:
        sev = RULES_BY_ID[f.rule_id].severity
        score[f.file] += SEVERITY_WEIGHT[sev]
        if sev == "error":
            errors[f.file] += 1
    return [(file, pts, errors[file]) for file, pts in score.most_common(limit)]


def build_plan(path: str) -> str:
    root = Path(path).expanduser().resolve()
    result = scan(root)
    reqs = analyse(root)

    py2 = [f for f in result.findings if RULES_BY_ID[f.rule_id].category == "python2"]
    dj = [f for f in result.findings if RULES_BY_ID[f.rule_id].category in ("django", "template")]
    uses_django = result.uses_django or result.has_manage_py or reqs.django_version is not None or bool(dj)
    django_now = reqs.django_version

    if django_now:
        django_label = f"{django_now[0]}.{django_now[1]} (from `{reqs.django_spec}`)"
    elif uses_django:
        django_label = "used, version not detected"
    else:
        django_label = "not detected"

    lines = [
        f"# Migration plan: {root.name}",
        "",
        "## Snapshot",
        "",
        "| | |",
        "|---|---|",
        f"| Python files | {result.python_files} ({result.lines_of_code} non-blank lines) |",
        f"| Templates / text files scanned | {result.template_files} |",
        f"| Test files | {result.test_files} |",
        f"| Django | {django_label} |",
        f"| Python 2 -> 3 findings | {severity_summary(py2)} |",
        f"| Legacy Django findings | {severity_summary(dj)} |",
        f"| Dependency issues | {len(reqs.issues)} flagged, {len(reqs.unpinned)} unpinned |",
    ]
    if not result.python_files:
        lines += ["", "No Python files were found under this path, so there is nothing to plan."]
        return "\n".join(lines)

    hot = _hot_spots(result.findings)
    if hot:
        lines += ["", "## Where the work is", "", "Files ranked by weighted findings (error 3, warning 2, info 1):", ""]
        for i, (file, pts, errs) in enumerate(hot, start=1):
            lines.append(f"{i}. `{file}`: score {pts}, {errs} error(s)")

    # Phase 0
    lines += ["", "## Phases", "", "### Phase 0: safety net"]
    if result.test_files == 0:
        lines.append(
            "- **No tests detected.** Before changing anything, write characterization tests for the flows that "
            "matter (login, the main create/read/update paths, reports, external integrations). This is the "
            "most valuable step in the whole migration."
        )
    else:
        lines.append(
            f"- {result.test_files} test file(s) detected. Run them on the current stack and record the baseline, "
            "including known failures, so later regressions are unambiguous."
        )
    lines += [
        "- Pin every dependency (`pip freeze`) and record the exact Python, OS and database versions in use.",
        "- Set up CI that runs the suite on the current stack.",
    ]

    # Phase 1
    lines += ["", "### Phase 1: make the code run on Python 2.7 and 3 (no behaviour change)"]
    errors = Counter(f.rule_id for f in py2 if RULES_BY_ID[f.rule_id].severity == "error")
    if errors:
        lines.append("Fix the constructs that stop working on Python 3, most frequent first:")
        for rid, n in errors.most_common(8):
            r = RULES_BY_ID[rid]
            lines.append(f"- `{rid}` x{n}: {r.title}. {r.fix}")
        if len(errors) > 8:
            lines.append(f"- ...and {len(errors) - 8} more rule(s); see `scan_python2_issues`.")
    else:
        lines.append("- No blocking Python 2 constructs were found by the heuristics.")
    warns = Counter(f.rule_id for f in py2 if RULES_BY_ID[f.rule_id].severity == "warning")
    if warns:
        lines.append(
            "- Warnings (behaviour changes silently): "
            + ", ".join(f"`{rid}` x{n}" for rid, n in warns.most_common(6))
            + "."
        )
    lines += [
        "- Run the suite with `python2.7 -3` and `-Wd` to surface incompatibilities and deprecations the "
        "heuristics cannot see.",
        "- Automated rewriters (`python-modernize`, `futurize`) can do the mechanical part; review every diff.",
        "- Replace renamed standard-library imports with `six.moves` or the Python 3 names behind a compat shim.",
    ]

    # Phase 2 and 3/4 (Django) or generic
    if uses_django:
        steps = [s for s in LTS_STEPS if django_now is None or _vt(s) > django_now]
        py2_steps = [s for s in steps if s in PY2_COMPATIBLE_STEPS]
        py3_steps = [s for s in steps if s not in PY2_COMPATIBLE_STEPS]
        lines += ["", "### Phase 2: move Django forward while still on Python 2.7"]
        if py2_steps:
            start = f"{django_now[0]}.{django_now[1]}" if django_now else "current"
            path_txt = " -> ".join([start, *py2_steps])
            lines.append(
                f"- Upgrade one LTS at a time: {path_txt}. Django 1.11 is the last release that supports "
                "Python 2.7 and the first one comfortable on Python 3."
            )
            lines.append("- At each step: read the release notes, run the tests with `-Wd`, fix every deprecation warning, then upgrade.")
        else:
            lines.append("- Django is already at or beyond 1.11; skip this phase.")
        lines += ["", "### Phase 3: switch the interpreter to Python 3"]
        lines += [
            "- With Django 1.11 and green tests on 2.7, run the suite on a Python 3 version Django 1.11 supports "
            "(3.4 to 3.7), fix what breaks, then move the deployment.",
            "- Work through the manual review checklist below on real data, not just on tests.",
        ]
        lines += ["", "### Phase 4: climb the remaining LTS releases on Python 3"]
        if py3_steps:
            lines.append(
                f"- {' -> '.join(py3_steps)}, one at a time, moving the Python version forward as each release "
                "requires. Check the supported Python versions in each release's notes."
            )
        else:
            lines.append("- Already on the latest LTS in this list.")
        if dj:
            by_version: dict[str, Counter[str]] = defaultdict(Counter)
            for f in dj:
                rule = RULES_BY_ID[f.rule_id]
                by_version[rule.removed_in or "any"][f.rule_id] += 1
            lines += ["", "#### Django APIs that block upgrades in this code base", "",
                      "| Fix before moving to | Rule | Count |", "|---|---|---|"]
            order = sorted(by_version, key=lambda v: (v == "any", _vt(v) if v != "any" else (0, 0)))
            for version in order:
                label = "any (fix early)" if version == "any" else f"Django {version}"
                for rid, n in by_version[version].most_common():
                    lines.append(f"| {label} | `{rid}`: {RULES_BY_ID[rid].title} | {n} |")
    else:
        lines += [
            "",
            "### Phase 2: switch the interpreter to Python 3",
            "- With green tests on 2.7 and the compatibility fixes in place, run the suite on a current Python 3, "
            "fix what breaks, then move the deployment.",
            "- Work through the manual review checklist below on real data, not just on tests.",
        ]

    lines += [
        "",
        "### Final phase: clean up",
        "- Remove `six`, `future` and compatibility shims; delete `from __future__` lines.",
        "- Add type checking and linting; run CI on the Python versions you support.",
    ]

    lines += ["", render_requirements(reqs)]
    lines += ["", "## Manual review checklist (not detectable statically)", ""]
    lines += [f"- {item}" for item in CHECKLIST]
    lines += [
        "",
        "_Generated from heuristic scanning: it flags patterns, it does not parse or run your code. "
        "Treat counts as a lower bound and the checklist as mandatory._",
    ]
    return "\n".join(lines)
