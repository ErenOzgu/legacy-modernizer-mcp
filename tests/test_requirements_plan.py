from __future__ import annotations

from legacy_modernizer_mcp.plan import build_plan
from legacy_modernizer_mcp.requirements import analyse, normalise


def test_normalise_names():
    assert normalise("MySQL_python") == normalise("mysql-python") == normalise("MySQL.python")


def test_requirements_fixture(legacy_project):
    report = analyse(legacy_project)
    assert report.django_version == (1, 7)
    assert report.files == ["requirements.txt"]
    assert len(report.requirements) == 7
    flagged = {i.requirement.name: i.severity for i in report.issues}
    assert flagged["mysql-python"] == "error"
    assert flagged["pil"] == "error"
    assert flagged["south"] == "error"
    assert flagged["simplejson"] == "info"
    assert [r.name for r in report.unpinned] == ["simplejson"]


def test_requirements_parsing_edge_cases(tmp_path):
    (tmp_path / "requirements.txt").write_text(
        "# comment\n"
        "\n"
        "-r base.txt\n"
        "--index-url https://example.invalid/simple\n"
        "Django>=1.11,<2.0  # inline comment\n"
        "requests[security]==2.0 ; python_version < '3'\n"
        "git+https://example.invalid/repo.git#egg=thing\n"
    )
    report = analyse(tmp_path)
    names = [r.name for r in report.requirements]
    assert "django" in names and "requests" in names
    assert report.django_version == (1, 11)


def test_no_requirements_files(tmp_path):
    report = analyse(tmp_path)
    assert report.requirements == []
    assert report.django_version is None


def test_requirements_dir_variants(tmp_path):
    (tmp_path / "requirements").mkdir()
    (tmp_path / "requirements" / "dev.txt").write_text("PIL\n")
    (tmp_path / "requirements-test.txt").write_text("mock\n")
    names = {r.name for r in analyse(tmp_path).requirements}
    assert names == {"pil", "mock"}


def test_plan_for_legacy_project(legacy_project):
    plan = build_plan(str(legacy_project))
    assert plan.startswith("# Migration plan: legacy_project")
    for heading in (
        "## Snapshot",
        "## Where the work is",
        "### Phase 0: safety net",
        "### Phase 1",
        "### Phase 2",
        "### Phase 3",
        "### Phase 4",
        "### Final phase",
        "## Dependencies",
        "## Manual review checklist",
    ):
        assert heading in plan
    assert "1.7 -> 1.8 -> 1.11" in plan
    assert "shop/utils.py" in plan
    assert "`DJ-FK-ON-DELETE`" in plan
    assert "mysqlclient" in plan


def test_plan_for_clean_project_has_no_django_phases(clean_project):
    plan = build_plan(str(clean_project))
    assert "0 errors, 0 warnings" in plan
    assert "Django | not detected" in plan
    assert "move Django forward" not in plan
    assert "LTS" not in plan.split("## Manual review checklist")[0]


def test_plan_for_empty_directory(tmp_path):
    plan = build_plan(str(tmp_path))
    assert "Python files | 0" in plan
