# Migration plan: legacy_project

## Snapshot

| | |
|---|---|
| Python files | 8 (90 non-blank lines) |
| Templates / text files scanned | 2 |
| Test files | 1 |
| Django | 1.7 (from `==1.7.11`) |
| Python 2 -> 3 findings | 18 errors, 3 warnings, 0 info |
| Legacy Django findings | 18 errors, 2 warnings, 0 info |
| Dependency issues | 6 flagged, 1 unpinned |

## Where the work is

Files ranked by weighted findings (error 3, warning 2, info 1):

1. `shop/utils.py`: score 37, 11 error(s)
2. `shop/views.py`: score 33, 11 error(s)
3. `shop/settings.py`: score 18, 6 error(s)
4. `shop/models.py`: score 15, 3 error(s)
5. `shop/urls.py`: score 12, 4 error(s)
6. `shop/templates/shop/list.html`: score 3, 1 error(s)

## Phases

### Phase 0: safety net
- 1 test file(s) detected. Run them on the current stack and record the baseline, including known failures, so later regressions are unambiguous.
- Pin every dependency (`pip freeze`) and record the exact Python, OS and database versions in use.
- Set up CI that runs the suite on the current stack.

### Phase 1: make the code run on Python 2.7 and 3 (no behaviour change)
Fix the constructs that stop working on Python 3, most frequent first:
- `PY2-ITERTOOLS` x1: itertools.izip / imap / ifilter. Use zip / map / filter (itertools.zip_longest, itertools.filterfalse).
- `PY2-OCTAL` x1: old octal literal (0755). Use 0o755.
- `PY2-LONG-LITERAL` x1: long integer literal (10L). Drop the suffix.
- `PY2-STRING-MODULE` x1: legacy string module functions. Use the str methods or the ascii_* constants.
- `PY2-MAXINT` x1: sys.maxint. Use sys.maxsize.
- `PY2-HAS-KEY` x1: dict.has_key(). Use `key in mapping`.
- `PY2-NE-OPERATOR` x1: <> operator. Use !=.
- `PY2-DICT-VIEW-INDEX` x1: indexing or sorting a dict view. Wrap in list() / use sorted(d).
- ...and 10 more rule(s); see `scan_python2_issues`.
- Warnings (behaviour changes silently): `PY2-DUNDER-METHODS` x2, `PY2-METACLASS` x1.
- Run the suite with `python2.7 -3` and `-Wd` to surface incompatibilities and deprecations the heuristics cannot see.
- Automated rewriters (`python-modernize`, `futurize`) can do the mechanical part; review every diff.
- Replace renamed standard-library imports with `six.moves` or the Python 3 names behind a compat shim.

### Phase 2: move Django forward while still on Python 2.7
- Upgrade one LTS at a time: 1.7 -> 1.8 -> 1.11. Django 1.11 is the last release that supports Python 2.7 and the first one comfortable on Python 3.
- At each step: read the release notes, run the tests with `-Wd`, fix every deprecation warning, then upgrade.

### Phase 3: switch the interpreter to Python 3
- With Django 1.11 and green tests on 2.7, run the suite on a Python 3 version Django 1.11 supports (3.4 to 3.7), fix what breaks, then move the deployment.
- Work through the manual review checklist below on real data, not just on tests.

### Phase 4: climb the remaining LTS releases on Python 3
- 2.2 -> 3.2 -> 4.2 -> 5.2, one at a time, moving the Python version forward as each release requires. Check the supported Python versions in each release's notes.

#### Django APIs that block upgrades in this code base

| Fix before moving to | Rule | Count |
|---|---|---|
| Django 1.9 | `TPL-LOAD-FROM-FUTURE`: {% load ... from future %} | 1 |
| Django 1.10 | `DJ-TEMPLATE-SETTINGS`: TEMPLATE_* settings | 3 |
| Django 1.10 | `DJ-PATTERNS`: urlpatterns built with patterns() | 2 |
| Django 1.10 | `DJ-CONTEXT-PROCESSORS`: django.core.context_processors | 1 |
| Django 1.10 | `DJ-URL-STRING-VIEW`: view referenced by dotted string in url() | 1 |
| Django 2.0 | `DJ-FK-ON-DELETE`: ForeignKey / OneToOneField without on_delete | 2 |
| Django 2.0 | `DJ-MIDDLEWARE-CLASSES`: MIDDLEWARE_CLASSES setting | 1 |
| Django 2.0 | `DJ-ADMIN-URLS-INCLUDE`: include(admin.site.urls) | 1 |
| Django 2.0 | `DJ-URLRESOLVERS`: django.core.urlresolvers | 1 |
| Django 2.0 | `DJ-IS-AUTH-CALL`: user.is_authenticated() | 1 |
| Django 2.1 | `DJ-PERMALINK`: models.permalink | 1 |
| Django 3.0 | `DJ-RENDER-TO-RESPONSE`: render_to_response | 2 |
| any (fix early) | `DJ-PY2-TEXT-HELPERS`: python_2_unicode_compatible / force_unicode / smart_unicode | 2 |
| any (fix early) | `DJ-SOUTH`: South migrations | 1 |

### Final phase: clean up
- Remove `six`, `future` and compatibility shims; delete `from __future__` lines.
- Add type checking and linting; run CI on the Python versions you support.

## Dependencies

Read 7 requirement(s) from: `requirements.txt`.
Django: `==1.7.11` (detected 1.7).

| Package | Specifier | Severity | Note |
|---|---|---|---|
| `MySQL-python` | `==1.2.5` | error | Python 2 only. Use `mysqlclient` (drop-in fork) or `PyMySQL`. |
| `PIL` | `==1.1.7` | error | Unmaintained. Use `Pillow` (same `PIL` import name). |
| `South` | `==1.0.2` | error | Replaced by Django's built-in migrations (Django 1.7+). Convert, then remove. |
| `mock` | `==1.0.1` | info | `unittest.mock` is in the standard library on Python 3; the package still works. |
| `simplejson` | `-` | info | Works on Python 3; the standard `json` module is usually enough. |
| `six` | `==1.10.0` | info | Handy during the transition; remove once the code base is Python 3 only. |

1 requirement(s) have no version specifier (`simplejson`). Pin them before migrating so you know what you are upgrading from.

_Package notes are a short built-in list, not a full compatibility database. Check each dependency's release notes for Python 3 support._

## Manual review checklist (not detectable statically)

- **Text vs bytes.** Python 3 separates `str` and `bytes`. Review every place data crosses a boundary: files opened in text vs binary mode, sockets, subprocess output, hashing, base64, pickles, database drivers.
- **Division.** `/` on integers is true division on Python 3. Use `//` where floor division was intended (or add `from __future__ import division` while still on 2.7 and run the tests).
- **Dict views and iterators.** `keys()`, `values()`, `items()`, `map()`, `filter()`, `zip()` and `range()` no longer return lists. Code that indexes, sorts, mutates while iterating, or iterates twice needs a look.
- **Implicit relative imports.** `import sibling` inside a package worked on Python 2 and fails on Python 3. Use absolute imports or explicit relative imports.
- **Ordering.** `cmp` is gone and comparing unrelated types raises `TypeError`. Check sorting and `min`/`max` over mixed data.
- **Numbers.** `round()` rounds half to even on Python 3; integer overflow to `long` no longer exists.
- **Persisted data.** Pickles, shelves and marshal files written by Python 2 may not load on Python 3. Test real data, not fixtures.
- **Exceptions.** `e.message` is gone; `sys.exc_clear()` is gone; exception variables are deleted after the `except` block.
- **Compiled and system dependencies.** C extensions, database drivers and system packages need Python 3 builds; verify them early because they are the usual long pole.

_Generated from heuristic scanning: it flags patterns, it does not parse or run your code. Treat counts as a lower bound and the checklist as mandatory._
