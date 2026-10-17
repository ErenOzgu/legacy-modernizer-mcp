from __future__ import annotations

from pathlib import Path

import pytest

from legacy_modernizer_mcp.scanner import scan

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def legacy_project() -> Path:
    return FIXTURES / "legacy_project"


@pytest.fixture
def clean_project() -> Path:
    return FIXTURES / "clean_project"


@pytest.fixture
def rule_ids(tmp_path):
    """Return the set of rule ids found in a snippet written to ``filename``."""

    def _run(source: str, filename: str = "sample.py") -> set[str]:
        target = tmp_path / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
        return {f.rule_id for f in scan(target).findings}

    return _run
