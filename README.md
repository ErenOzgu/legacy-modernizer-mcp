# legacy-modernizer-mcp

[![CI](https://github.com/ErenOzgu/legacy-modernizer-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/ErenOzgu/legacy-modernizer-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

An [MCP](https://modelcontextprotocol.io) server that helps an AI assistant (Claude Desktop, Claude Code, any MCP client) **assess and plan the migration of a legacy Python 2 / old Django code base**.

Point it at a project directory and it answers the questions you have before touching a line of code: *How bad is it? Where is the work? In what order should I do it? Which dependencies will block me?*

- **52 rules**: 31 for Python 2 → 3, 20 for Django APIs removed between 1.x and 5.x, 1 for templates. Every rule has an explanation, a fix and (for Django) the release that removed the API.
- **Requirements analysis**: detects the pinned Django version, flags Python 2-only or obsolete packages (`MySQL-python`, `PIL`, `South`, ...) and unpinned requirements.
- **Migration plan**: phased and ordered (safety net → Python 2/3 compatibility → Django 1.11 on 2.7 → switch to Python 3 → climb LTS releases), with the files that need the most work and a checklist for what static analysis cannot see.
- **Read-only and safe**: it reads source files as text. It never imports, executes or modifies the code it scans, and it skips symlinks, virtualenvs, `.git`, `node_modules` and files over 1 MB.

> Findings are **heuristic** (regular expressions over source with comments and string contents masked out), not a parse tree. Counts are a lower bound; confirm each finding in context. See [Limitations](#limitations).

## Tools

| Tool | What it does |
|---|---|
| `generate_migration_plan(path)` | Full plan: snapshot, hot-spot files, ordered phases, blocking Django APIs, dependency notes, manual checklist. **Start here.** |
| `scan_python2_issues(path, max_findings=100)` | Python 2 constructs that break or change behaviour on Python 3, grouped by rule with file:line and fix. |
| `scan_django_legacy(path, max_findings=100)` | Django APIs removed in newer releases, each tagged with the release that removed it. |
| `analyze_requirements(path)` | Reads `requirements*.txt`, flags problem packages, detects the Django version. |
| `list_rules(category="")` | The rule catalogue (`python2`, `django`, `template`). |
| `explain_rule(rule_id)` | What a rule flags, why it matters, how to fix it. |

All tools are annotated `readOnlyHint=true`, so clients can run them without a confirmation prompt.

## Install

Requires Python 3.11+. The easiest way is [`uv`](https://docs.astral.sh/uv/), which runs the server straight from GitHub with no manual install:

```bash
uvx --from git+https://github.com/ErenOzgu/legacy-modernizer-mcp legacy-modernizer-mcp --version
```

or with pip:

```bash
pip install git+https://github.com/ErenOzgu/legacy-modernizer-mcp
```

### Claude Code

```bash
claude mcp add legacy-modernizer -- uvx --from git+https://github.com/ErenOzgu/legacy-modernizer-mcp legacy-modernizer-mcp
```

### Claude Desktop

Add this to `claude_desktop_config.json` and restart the app:

```json
{
  "mcpServers": {
    "legacy-modernizer": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/ErenOzgu/legacy-modernizer-mcp",
        "legacy-modernizer-mcp"
      ]
    }
  }
}
```

Then ask, for example: *"Use legacy-modernizer to plan the Python 3 migration of ~/work/my-old-django-app."*

### Without an MCP client

The same analysis is available from the command line:

```bash
legacy-modernizer-mcp plan path/to/project   # print a migration plan
legacy-modernizer-mcp rules                  # print the rule catalogue
legacy-modernizer-mcp                        # no arguments: run the MCP server on stdio
```

## Example

Abridged output of `legacy-modernizer-mcp plan tests/fixtures/legacy_project` (a small deliberately-old Django 1.7 app; the full output is in [`examples/sample-output.md`](examples/sample-output.md)):

```text
## Snapshot

|                           |                               |
|---------------------------|-------------------------------|
| Python files              | 8 (90 non-blank lines)        |
| Django                    | 1.7 (from `==1.7.11`)         |
| Python 2 -> 3 findings    | 18 errors, 3 warnings, 0 info |
| Legacy Django findings    | 18 errors, 2 warnings, 0 info |
| Dependency issues         | 6 flagged, 1 unpinned         |

## Where the work is

1. `shop/utils.py`: score 37, 11 error(s)
2. `shop/views.py`: score 33, 11 error(s)
3. `shop/settings.py`: score 18, 6 error(s)
...

#### Django APIs that block upgrades in this code base

| Fix before moving to | Rule | Count |
|---|---|---|
| Django 1.10 | `DJ-PATTERNS`: urlpatterns built with patterns() | 2 |
| Django 2.0  | `DJ-FK-ON-DELETE`: ForeignKey / OneToOneField without on_delete | 2 |
| Django 3.0  | `DJ-RENDER-TO-RESPONSE`: render_to_response | 2 |
...
```

## Rules

**Python 2 → 3**

| Rule | Severity | What it flags | Removed in |
|---|---|---|---|
| `PY2-PRINT-STMT` | error | print statement | — |
| `PY2-EXCEPT-COMMA` | error | except X, e | — |
| `PY2-RAISE-COMMA` | error | raise E, message | — |
| `PY2-HAS-KEY` | error | dict.has_key() | — |
| `PY2-DICT-ITER` | error | iteritems / iterkeys / itervalues / view* | — |
| `PY2-XRANGE` | error | xrange() | — |
| `PY2-UNICODE` | error | unicode type / builtin | — |
| `PY2-BASESTRING` | error | basestring | — |
| `PY2-LONG` | error | long type / builtin | — |
| `PY2-LONG-LITERAL` | error | long integer literal (10L) | — |
| `PY2-OCTAL` | error | old octal literal (0755) | — |
| `PY2-REMOVED-BUILTIN` | error | removed builtin | — |
| `PY2-REDUCE` | warning | reduce() builtin | — |
| `PY2-NEXT-METHOD` | warning | iterator.next() | — |
| `PY2-BACKTICK` | error | backtick repr | — |
| `PY2-NE-OPERATOR` | error | <> operator | — |
| `PY2-EXEC-STMT` | error | exec statement | — |
| `PY2-METACLASS` | warning | __metaclass__ attribute | — |
| `PY2-CMP-ARG` | error | sort(cmp=...) | — |
| `PY2-MAXINT` | error | sys.maxint | — |
| `PY2-STRING-MODULE` | error | legacy string module functions | — |
| `PY2-OLD-IMPORT` | error | renamed standard-library module | — |
| `PY2-ITERTOOLS` | error | itertools.izip / imap / ifilter | — |
| `PY2-TUPLE-PARAMS` | error | tuple parameter unpacking in def | — |
| `PY2-LAMBDA-TUPLE` | error | tuple parameter unpacking in lambda | — |
| `PY2-DICT-VIEW-INDEX` | error | indexing or sorting a dict view | — |
| `PY2-LEN-ITERATOR` | error | len(map/filter/zip(...)) | — |
| `PY2-DUNDER-METHODS` | warning | Python 2-only special methods | — |
| `PY2-GETCWDU` | error | os.getcwdu() | — |
| `PY2-SETDEFAULTENCODING` | warning | sys.setdefaultencoding hack | — |
| `PY2-UR-PREFIX` | error | ur'' string prefix | — |

**Django**

| Rule | Severity | What it flags | Removed in |
|---|---|---|---|
| `DJ-PATTERNS` | error | urlpatterns built with patterns() | 1.10 |
| `DJ-URL-STRING-VIEW` | error | view referenced by dotted string in url() | 1.10 |
| `DJ-URLS-DEFAULTS` | error | django.conf.urls.defaults | 1.6 |
| `DJ-ADMIN-URLS-INCLUDE` | error | include(admin.site.urls) | 2.0 |
| `DJ-RENDER-TO-RESPONSE` | error | render_to_response | 3.0 |
| `DJ-CONTEXT-INSTANCE` | error | context_instance=RequestContext(...) | 1.10 |
| `DJ-URLRESOLVERS` | error | django.core.urlresolvers | 2.0 |
| `DJ-CONTEXT-PROCESSORS` | error | django.core.context_processors | 1.10 |
| `DJ-MIDDLEWARE-CLASSES` | error | MIDDLEWARE_CLASSES setting | 2.0 |
| `DJ-TEMPLATE-SETTINGS` | error | TEMPLATE_* settings | 1.10 |
| `DJ-SOUTH` | error | South migrations | — |
| `DJ-FK-ON-DELETE` | error | ForeignKey / OneToOneField without on_delete | 2.0 |
| `DJ-PERMALINK` | error | models.permalink | 2.1 |
| `DJ-IS-AUTH-CALL` | error | user.is_authenticated() | 2.0 |
| `DJ-SIX` | error | django.utils.six | 3.0 |
| `DJ-PY2-TEXT-HELPERS` | warning | python_2_unicode_compatible / force_unicode / smart_unicode | — |
| `DJ-SORTEDDICT` | error | django.utils.datastructures.SortedDict | 1.9 |
| `DJ-SIMPLEJSON` | error | django.utils.simplejson | — |
| `DJ-ASSIGNMENT-TAG` | error | register.assignment_tag | 2.0 |
| `DJ-GET-MODEL` | error | django.db.models.get_model / get_models / get_app | 1.9 |

**Django templates**

| Rule | Severity | What it flags | Removed in |
|---|---|---|---|
| `TPL-LOAD-FROM-FUTURE` | error | {% load ... from future %} | 1.9 |

Run `legacy-modernizer-mcp rules` or the `explain_rule` tool for the full explanation and fix of each rule.

## How it works

1. `scanner.py` walks the project and, for each file, builds a *masked* copy of the source in which comments are blanked and string contents are replaced by filler (same length, same newlines), so `print "x"` inside a docstring is not a finding but the real thing is. Rules that need string text (for example `'south'` in `INSTALLED_APPS`) run on a variant that keeps strings.
2. `rules.py` is a declarative table of `Rule` objects (id, severity, explanation, fix, pattern). One rule, `DJ-FK-ON-DELETE`, uses a small custom check that reads the call's arguments so `ForeignKey(User, models.CASCADE)` is not reported.
3. `requirements.py`, `plan.py` and `report.py` turn findings into the requirements analysis, the plan and the Markdown that the tools return.

## Limitations

- **Heuristic, not a parser.** No data-flow, no type information. Constructs split in unusual ways across lines or built dynamically can be missed; some patterns (`.keys()[0]`, `len(map(...))`) can in rare cases be false positives. Treat counts as a lower bound.
- **Text/bytes bugs are invisible.** The hardest part of a Python 3 migration (implicit `str`/`bytes` conversions, I/O encodings, pickles) cannot be found statically; the plan ends with a checklist for it.
- **Dependency notes are a short built-in list**, not a compatibility database.
- **Not a rewriter.** It tells you what and in which order. For mechanical rewrites use tools such as `python-modernize` or `futurize`, and review the diffs.
- Only `requirements*.txt` files are read (no `Pipfile`, `pyproject.toml` or `setup.py` yet).

## Development

```bash
git clone https://github.com/ErenOzgu/legacy-modernizer-mcp
cd legacy-modernizer-mcp
pip install -e ".[dev]"
pytest
```

Adding a rule: append a `Rule(...)` to the right list in `src/legacy_modernizer_mcp/rules.py`, add a positive and a negative example in `tests/test_rules.py` (a test fails if a rule has no positive example).

## Roadmap

- `pyproject.toml` / `Pipfile` / `setup.py` dependency parsing
- Per-file `explain_finding` with surrounding context
- Optional diff-style fix suggestions for the mechanical rules
- SARIF output for CI use

## Author

Eren Özgü ([@ErenOzgu](https://github.com/ErenOzgu)), built with Claude Code.

## License

[MIT](LICENSE)
