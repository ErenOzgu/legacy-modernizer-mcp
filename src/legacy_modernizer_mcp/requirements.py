"""Parse requirements files and flag packages that block or complicate a migration."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .scanner import MAX_FILE_BYTES, SKIP_DIRS

_REQ_FILE = re.compile(r"^requirements.*\.txt$", re.IGNORECASE)
_LINE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*(.*)$")
_VERSION = re.compile(r"(\d+)\.(\d+)")

KNOWN: dict[str, tuple[str, str]] = {
    "mysql-python": ("error", "Python 2 only. Use `mysqlclient` (drop-in fork) or `PyMySQL`."),
    "pil": ("error", "Unmaintained. Use `Pillow` (same `PIL` import name)."),
    "south": ("error", "Replaced by Django's built-in migrations (Django 1.7+). Convert, then remove."),
    "django-south": ("error", "Replaced by Django's built-in migrations (Django 1.7+). Convert, then remove."),
    "pycrypto": ("error", "Unmaintained. Use `pycryptodome` (drop-in) or `cryptography`."),
    "suds": ("error", "Python 2 only. Use `suds-community` or `zeep`."),
    "beautifulsoup": ("error", "BeautifulSoup 3 is Python 2 only. Use `beautifulsoup4` (import `bs4`)."),
    "enum34": ("error", "Backport of `enum` that conflicts with the standard library on Python 3.6+. Remove."),
    "futures": ("warning", "Python 2 backport of `concurrent.futures`; built in on Python 3."),
    "unittest2": ("warning", "Backport of `unittest`; use the standard library on Python 3."),
    "ipaddress": ("warning", "Backport; `ipaddress` is in the Python 3 standard library."),
    "pysqlite": ("warning", "Use the standard library `sqlite3`."),
    "distribute": ("warning", "Merged back into `setuptools`."),
    "ordereddict": ("warning", "Use `collections.OrderedDict`."),
    "functools32": ("warning", "Python 2 backport; use `functools`."),
    "mock": ("info", "`unittest.mock` is in the standard library on Python 3; the package still works."),
    "simplejson": ("info", "Works on Python 3; the standard `json` module is usually enough."),
    "six": ("info", "Handy during the transition; remove once the code base is Python 3 only."),
    "future": ("info", "Compatibility layer for the transition; remove once Python 3 only."),
    "argparse": ("info", "Part of the standard library on Python 2.7 / 3.2+; the backport is not needed."),
    "importlib": ("info", "Python 2.6 backport; remove."),
}


@dataclass(frozen=True)
class Requirement:
    name: str  # normalised
    raw_name: str
    spec: str
    file: str
    line: int


@dataclass(frozen=True)
class Issue:
    requirement: Requirement
    severity: str
    note: str


@dataclass
class RequirementsReport:
    files: list[str] = field(default_factory=list)
    requirements: list[Requirement] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    unpinned: list[Requirement] = field(default_factory=list)
    django_version: tuple[int, int] | None = None
    django_spec: str = ""


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def find_requirement_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix == ".txt" else []
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info"))
        in_requirements_dir = Path(dirpath).name.lower() == "requirements"
        for name in sorted(filenames):
            path = Path(dirpath, name)
            if path.is_symlink() or not name.lower().endswith(".txt"):
                continue
            if _REQ_FILE.match(name) or in_requirements_dir:
                found.append(path)
    return found


def parse_requirements_file(path: Path, base: Path) -> list[Requirement]:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return []
        text = path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return []
    rel = path.relative_to(base).as_posix()
    out: list[Requirement] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split(" #", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-"):
            if line.startswith(("-e ", "--editable")) and "#egg=" in line:
                name = line.split("#egg=", 1)[1].split("&", 1)[0]
                out.append(Requirement(normalise(name), name, "", rel, number))
            continue
        if "://" in line:
            if "#egg=" in line:
                name = line.split("#egg=", 1)[1].split("&", 1)[0]
                out.append(Requirement(normalise(name), name, "", rel, number))
            continue
        line = line.split(";", 1)[0].strip()
        m = _LINE.match(line)
        if not m:
            continue
        out.append(Requirement(normalise(m.group(1)), m.group(1), m.group(3).strip(), rel, number))
    return out


def analyse(path: str | os.PathLike[str]) -> RequirementsReport:
    root = Path(path).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Path does not exist: {root}")
    base = root if root.is_dir() else root.parent
    report = RequirementsReport()
    for file in find_requirement_files(root):
        report.files.append(file.relative_to(base).as_posix())
        report.requirements.extend(parse_requirements_file(file, base))

    for req in report.requirements:
        if req.name in KNOWN:
            severity, note = KNOWN[req.name]
            report.issues.append(Issue(req, severity, note))
        elif req.name.startswith("backports-"):
            report.issues.append(
                Issue(req, "info", "Standard-library backport; check whether Python 3 already covers it.")
            )
        if not req.spec:
            report.unpinned.append(req)
        if req.name == "django" and report.django_version is None:
            report.django_spec = req.spec
            m = _VERSION.search(req.spec)
            if m:
                report.django_version = (int(m.group(1)), int(m.group(2)))
    return report
