"""Rule catalogue: Python 2 -> 3 constructs and legacy Django APIs.

Rules are deliberately conservative regular expressions that run on a *masked*
copy of each source file (string contents and comments blanked out), so they do
not fire inside docstrings or comments. They are heuristics, not a parser: treat
the findings as a worklist to review, not as a guarantee of completeness.

Severity:
    error    breaks on Python 3 / on the Django release in ``removed_in``
    warning  behaves differently, silently stops being used, or the library is gone
    info     cleanup that is worth doing but not blocking
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable

M = re.MULTILINE


@dataclass(frozen=True)
class Rule:
    id: str
    category: str  # "python2" | "django" | "template"
    severity: str  # "error" | "warning" | "info"
    title: str
    explanation: str
    fix: str
    pattern: re.Pattern[str] | None = None
    keep_strings: bool = False  # match on text where only comments are blanked
    skip_file_if: re.Pattern[str] | None = None
    detail: Callable[[re.Match[str]], str] | None = None
    check: Callable[[str], Iterable[tuple[int, str]]] | None = None
    removed_in: str | None = None  # Django release that dropped the API


def _rx(pattern: str, flags: int = M) -> re.Pattern[str]:
    return re.compile(pattern, flags)


# --------------------------------------------------------------------------- #
# Lookup tables used by detail messages
# --------------------------------------------------------------------------- #

OLD_MODULES: dict[str, str] = {
    "urllib2": "urllib.request / urllib.error",
    "urlparse": "urllib.parse",
    "ConfigParser": "configparser",
    "StringIO": "io.StringIO",
    "cStringIO": "io.StringIO / io.BytesIO",
    "cPickle": "pickle",
    "Queue": "queue",
    "Tkinter": "tkinter",
    "tkMessageBox": "tkinter.messagebox",
    "httplib": "http.client",
    "HTMLParser": "html.parser",
    "commands": "subprocess",
    "cookielib": "http.cookiejar",
    "Cookie": "http.cookies",
    "xmlrpclib": "xmlrpc.client",
    "SocketServer": "socketserver",
    "BaseHTTPServer": "http.server",
    "SimpleHTTPServer": "http.server",
    "__builtin__": "builtins",
    "thread": "_thread (or threading)",
    "copy_reg": "copyreg",
    "htmlentitydefs": "html.entities",
    "UserDict": "collections.UserDict",
    "UserList": "collections.UserList",
    "UserString": "collections.UserString",
    "anydbm": "dbm",
    "repr": "reprlib",
}

REMOVED_BUILTINS: dict[str, str] = {
    "raw_input": "input()",
    "execfile": "exec(open(path).read())",
    "unichr": "chr()",
    "cmp": "(a > b) - (a < b), or rich comparisons",
    "reload": "importlib.reload()",
    "apply": "f(*args, **kwargs)",
    "intern": "sys.intern()",
    "coerce": "removed, convert explicitly",
    "buffer": "memoryview()",
    "file": "open()",
}

STRING_MODULE: dict[str, str] = {
    "letters": "string.ascii_letters",
    "lowercase": "string.ascii_lowercase",
    "uppercase": "string.ascii_uppercase",
    "maketrans": "str.maketrans()",
}

ITERTOOLS: dict[str, str] = {
    "izip": "zip()",
    "imap": "map()",
    "ifilter": "filter()",
    "izip_longest": "itertools.zip_longest()",
    "ifilterfalse": "itertools.filterfalse()",
}

DUNDERS: dict[str, str] = {
    "unicode": "__str__ (Python 3 text is str)",
    "nonzero": "__bool__",
    "cmp": "rich comparison methods (__eq__, __lt__, ...)",
    "getslice": "__getitem__ with a slice object",
    "setslice": "__setitem__ with a slice object",
    "delslice": "__delitem__ with a slice object",
    "div": "__truediv__ / __floordiv__",
    "idiv": "__itruediv__ / __ifloordiv__",
    "rdiv": "__rtruediv__ / __rfloordiv__",
    "coerce": "removed",
    "long": "__int__",
    "oct": "__index__",
    "hex": "__index__",
}


def _dict_iter(m: re.Match[str]) -> str:
    return f".{m.group(1)}{m.group(2)}() -> .{m.group(2)}()"


def _removed_builtin(m: re.Match[str]) -> str:
    return f"{m.group(1)}() -> {REMOVED_BUILTINS[m.group(1)]}"


def _old_import(m: re.Match[str]) -> str:
    name = m.group(1) or m.group(2)
    return f"{name} -> {OLD_MODULES[name]}"


def _string_module(m: re.Match[str]) -> str:
    name = m.group(1)
    return f"string.{name} -> {STRING_MODULE.get(name, 'the equivalent str method')}"


def _itertools(m: re.Match[str]) -> str:
    name = m.group(1) or m.group(2)
    return f"itertools.{name} -> {ITERTOOLS[name]}"


def _dunder(m: re.Match[str]) -> str:
    return f"__{m.group(1)}__ -> {DUNDERS[m.group(1)]}"


# --------------------------------------------------------------------------- #
# Custom checks
# --------------------------------------------------------------------------- #

_FIELD_CALL = re.compile(r"(?<![\w])(?:ForeignKey|OneToOneField)[ \t]*\(")


def _top_level_args(args: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    for i, ch in enumerate(args):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(args[start:i])
            start = i + 1
    parts.append(args[start:])
    return [p.strip() for p in parts if p.strip()]


def _check_on_delete(text: str) -> Iterable[tuple[int, str]]:
    """ForeignKey / OneToOneField without on_delete (required since Django 2.0)."""
    for m in _FIELD_CALL.finditer(text):
        i = m.end()
        depth = 1
        while i < len(text) and depth:
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
            i += 1
        args = _top_level_args(text[m.end() : i - 1 if depth == 0 else i])
        if any(a.startswith("on_delete") for a in args):
            continue
        if len(args) >= 2 and "=" not in args[1].split("(")[0]:
            continue  # on_delete passed as the second positional argument
        yield m.start(), "no on_delete argument"


# --------------------------------------------------------------------------- #
# Python 2 -> 3 rules
# --------------------------------------------------------------------------- #

_OLD_NAMES = "|".join(sorted(OLD_MODULES, key=len, reverse=True))
_ITER_NAMES = "|".join(sorted(ITERTOOLS, key=len, reverse=True))
_BUILTIN_NAMES = "|".join(sorted(REMOVED_BUILTINS, key=len, reverse=True))
_DUNDER_NAMES = "|".join(sorted(DUNDERS, key=len, reverse=True))
_STMT_START = r"(?:^|(?<=:)|(?<=;))[ \t]*"

PYTHON2_RULES: list[Rule] = [
    Rule(
        "PY2-PRINT-STMT", "python2", "error", "print statement",
        "`print x` is a SyntaxError on Python 3; print is a function.",
        "Use print(x). Add `from __future__ import print_function` while still on 2.7.",
        _rx(_STMT_START + r"print(?:[ \t]*>>|[ \t]+(?![=(.,])\S|[ \t]*$)"),
    ),
    Rule(
        "PY2-EXCEPT-COMMA", "python2", "error", "except X, e",
        "The comma form of `except` is a SyntaxError on Python 3.",
        "Use `except X as e:` (valid on 2.6+).",
        _rx(r"^[ \t]*except[ \t]+[^:\n]*?,[ \t]*\w+[ \t]*:"),
    ),
    Rule(
        "PY2-RAISE-COMMA", "python2", "error", "raise E, message",
        "`raise E, msg` is a SyntaxError on Python 3.",
        "Use raise E(msg).",
        _rx(r"^[ \t]*raise[ \t]+[\w.]+[ \t]*,[ \t]*\S"),
    ),
    Rule(
        "PY2-HAS-KEY", "python2", "error", "dict.has_key()",
        "`dict.has_key` was removed in Python 3.",
        "Use `key in mapping`.",
        _rx(r"\.has_key[ \t]*\("),
    ),
    Rule(
        "PY2-DICT-ITER", "python2", "error", "iteritems / iterkeys / itervalues / view*",
        "The iter* and view* dict methods were removed in Python 3 (items/keys/values return views).",
        "Use .items() / .keys() / .values(); wrap in list() only if you need a copy.",
        _rx(r"\.(iter|view)(items|keys|values)[ \t]*\("),
        detail=_dict_iter,
    ),
    Rule(
        "PY2-XRANGE", "python2", "error", "xrange()",
        "`xrange` does not exist on Python 3; `range` is already lazy.",
        "Use range().",
        _rx(r"(?<![\w.])xrange[ \t]*\("),
    ),
    Rule(
        "PY2-UNICODE", "python2", "error", "unicode type / builtin",
        "`unicode` does not exist on Python 3; all text is `str`.",
        "Use str (or six.text_type during the transition).",
        _rx(r"(?<![\w.])unicode(?!\w)"),
    ),
    Rule(
        "PY2-BASESTRING", "python2", "error", "basestring",
        "`basestring` was removed in Python 3.",
        "Use str (or six.string_types during the transition).",
        _rx(r"(?<![\w.])basestring\b"),
    ),
    Rule(
        "PY2-LONG", "python2", "error", "long type / builtin",
        "`long` was merged into `int` on Python 3.",
        "Use int.",
        _rx(r"(?<![\w.])long[ \t]*\(|[,(][ \t]*long[ \t]*[,)]"),
    ),
    Rule(
        "PY2-LONG-LITERAL", "python2", "error", "long integer literal (10L)",
        "The `L` suffix on integer literals is a SyntaxError on Python 3.",
        "Drop the suffix.",
        _rx(r"(?<![\w.])(?:0[xX][0-9a-fA-F]+|\d+)[lL](?![\w.])"),
    ),
    Rule(
        "PY2-OCTAL", "python2", "error", "old octal literal (0755)",
        "Leading-zero octal literals are a SyntaxError on Python 3.",
        "Use 0o755.",
        _rx(r"(?<![\w.])0[0-7]*[1-7][0-7]*(?![\w.])"),
    ),
    Rule(
        "PY2-REMOVED-BUILTIN", "python2", "error", "removed builtin",
        "These builtins were removed or moved in Python 3.",
        "Use the replacement shown in the detail column.",
        _rx(r"(?<![\w.])(?<!def )(" + _BUILTIN_NAMES + r")[ \t]*\("),
        detail=_removed_builtin,
    ),
    Rule(
        "PY2-REDUCE", "python2", "warning", "reduce() builtin",
        "`reduce` moved to functools in Python 3.",
        "from functools import reduce.",
        _rx(r"(?<![\w.])(?<!def )reduce[ \t]*\("),
        skip_file_if=_rx(r"from[ \t]+functools[ \t]+import[^\n]*\breduce\b|functools\.reduce"),
    ),
    Rule(
        "PY2-NEXT-METHOD", "python2", "warning", "iterator.next()",
        "Iterators have __next__ on Python 3; the .next() method is gone.",
        "Use next(iterator).",
        _rx(r"\.next[ \t]*\([ \t]*\)"),
    ),
    Rule(
        "PY2-BACKTICK", "python2", "error", "backtick repr",
        "Backticks are a SyntaxError on Python 3.",
        "Use repr(x).",
        _rx(r"`[^`\n]+`"),
    ),
    Rule(
        "PY2-NE-OPERATOR", "python2", "error", "<> operator",
        "The `<>` operator is a SyntaxError on Python 3.",
        "Use !=.",
        _rx(r"(?<![<>=!])<>(?![<>=])"),
    ),
    Rule(
        "PY2-EXEC-STMT", "python2", "error", "exec statement",
        "`exec code in ns` is a SyntaxError on Python 3; exec is a function.",
        "Use exec(code, ns). Reconsider whether exec is needed at all.",
        _rx(_STMT_START + r"exec[ \t]+(?![=(.,])\S"),
    ),
    Rule(
        "PY2-METACLASS", "python2", "warning", "__metaclass__ attribute",
        "The `__metaclass__` class attribute is silently ignored on Python 3.",
        "Use `class C(metaclass=M)`, or six.with_metaclass during the transition.",
        _rx(r"^[ \t]+__metaclass__[ \t]*="),
    ),
    Rule(
        "PY2-CMP-ARG", "python2", "error", "sort(cmp=...)",
        "The cmp argument of sort/sorted was removed in Python 3.",
        "Use key=; functools.cmp_to_key(f) if you must keep a comparison function.",
        _rx(r"\b(?:sort|sorted)[ \t]*\((?:[^()\n]|\([^()\n]*\))*\bcmp[ \t]*="),
    ),
    Rule(
        "PY2-MAXINT", "python2", "error", "sys.maxint",
        "`sys.maxint` was removed in Python 3 (ints are unbounded).",
        "Use sys.maxsize.",
        _rx(r"\bsys\.maxint\b"),
    ),
    Rule(
        "PY2-STRING-MODULE", "python2", "error", "legacy string module functions",
        "string.letters, string.join and friends were removed in Python 3.",
        "Use the str methods or the ascii_* constants.",
        _rx(
            r"(?<![\w.])string\.(letters|lowercase|uppercase|maketrans|join|split|replace|"
            r"strip|lstrip|rstrip|lower|upper|atoi|atof|atol|find|zfill|ljust|rjust)\b"
        ),
        detail=_string_module,
    ),
    Rule(
        "PY2-OLD-IMPORT", "python2", "error", "renamed standard-library module",
        "The module was renamed or reorganised in Python 3.",
        "Import the Python 3 name (see detail); six.moves works on both while migrating.",
        _rx(
            rf"^[ \t]*(?:from[ \t]+({_OLD_NAMES})\b|"
            rf"import[ \t]+(?:[\w.]+[ \t]*,[ \t]*)*({_OLD_NAMES})\b)"
        ),
        detail=_old_import,
    ),
    Rule(
        "PY2-ITERTOOLS", "python2", "error", "itertools.izip / imap / ifilter",
        "These itertools functions were replaced by the lazy builtins in Python 3.",
        "Use zip / map / filter (itertools.zip_longest, itertools.filterfalse).",
        _rx(
            rf"\bitertools\.({_ITER_NAMES})\b|"
            rf"from[ \t]+itertools[ \t]+import[^\n]*\b({_ITER_NAMES})\b"
        ),
        detail=_itertools,
    ),
    Rule(
        "PY2-TUPLE-PARAMS", "python2", "error", "tuple parameter unpacking in def",
        "`def f(a, (b, c))` is a SyntaxError on Python 3.",
        "Take one parameter and unpack inside the function body.",
        _rx(r"\bdef[ \t]+\w+[ \t]*\((?:[^()\n]*,)?[ \t]*\("),
    ),
    Rule(
        "PY2-LAMBDA-TUPLE", "python2", "error", "tuple parameter unpacking in lambda",
        "`lambda (k, v): ...` is a SyntaxError on Python 3.",
        "Use `lambda kv: kv[0]` or a named function.",
        _rx(r"\blambda[ \t]*\("),
    ),
    Rule(
        "PY2-DICT-VIEW-INDEX", "python2", "error", "indexing or sorting a dict view",
        "`d.keys()[0]` and `d.keys().sort()` fail on Python 3 because views are not lists.",
        "Wrap in list() / use sorted(d).",
        _rx(r"\.(?:keys|values|items)\(\)[ \t]*(?:\[|\.sort\()"),
    ),
    Rule(
        "PY2-LEN-ITERATOR", "python2", "error", "len(map/filter/zip(...))",
        "map, filter and zip return iterators on Python 3, which have no len().",
        "Wrap in list() first or restructure.",
        _rx(r"\blen[ \t]*\([ \t]*(?:map|filter|zip)[ \t]*\("),
    ),
    Rule(
        "PY2-DUNDER-METHODS", "python2", "warning", "Python 2-only special methods",
        "Python 3 never calls these methods, so the behaviour silently disappears.",
        "Implement the Python 3 equivalent (see detail).",
        _rx(rf"^[ \t]*def[ \t]+__({_DUNDER_NAMES})__[ \t]*\("),
        detail=_dunder,
    ),
    Rule(
        "PY2-GETCWDU", "python2", "error", "os.getcwdu()",
        "`os.getcwdu` was removed in Python 3.",
        "Use os.getcwd().",
        _rx(r"\bos\.getcwdu[ \t]*\("),
    ),
    Rule(
        "PY2-SETDEFAULTENCODING", "python2", "warning", "sys.setdefaultencoding hack",
        "`reload(sys); sys.setdefaultencoding(...)` does not exist on Python 3 and usually hides bytes/text bugs.",
        "Remove it and fix the underlying str/unicode mixing; decode at the I/O boundary.",
        _rx(r"\bsys\.setdefaultencoding\b|\breload[ \t]*\([ \t]*sys[ \t]*\)"),
    ),
    Rule(
        "PY2-UR-PREFIX", "python2", "error", "ur'' string prefix",
        "The `ur` string prefix is a SyntaxError on Python 3.",
        "Use a plain u'' / r'' literal (u'' is allowed again on 3.3+).",
        _rx(r"(?<![\w.])[uU][rR](?=['\"])"),
    ),
]

# --------------------------------------------------------------------------- #
# Legacy Django rules
# --------------------------------------------------------------------------- #

DJANGO_RULES: list[Rule] = [
    Rule(
        "DJ-PATTERNS", "django", "error", "urlpatterns built with patterns()",
        "`django.conf.urls.patterns` was removed; urlpatterns must be a plain list.",
        "Use a list of url()/re_path()/path() entries.",
        _rx(r"from[ \t]+django\.conf\.urls[ \t]+import[^\n]*\bpatterns\b|(?<![\w.])patterns[ \t]*\("),
        removed_in="1.10",
    ),
    Rule(
        "DJ-URL-STRING-VIEW", "django", "error", "view referenced by dotted string in url()",
        "Passing the view as a string ('app.views.home') was removed.",
        "Import the view and pass the callable.",
        _rx(r"(?<![\w.])url[ \t]*\([ \t]*[rR]?['\"][^'\"\n]*['\"][ \t]*,[ \t]*['\"][\w.]+['\"]"),
        keep_strings=True,
        removed_in="1.10",
    ),
    Rule(
        "DJ-URLS-DEFAULTS", "django", "error", "django.conf.urls.defaults",
        "The `django.conf.urls.defaults` module was removed.",
        "Import url/include from django.conf.urls.",
        _rx(r"django\.conf\.urls\.defaults"),
        removed_in="1.6",
    ),
    Rule(
        "DJ-ADMIN-URLS-INCLUDE", "django", "error", "include(admin.site.urls)",
        "Wrapping admin.site.urls in include() was removed.",
        "Use url(r'^admin/', admin.site.urls) (or path('admin/', admin.site.urls)).",
        _rx(r"include[ \t]*\([ \t]*admin\.site\.urls[ \t]*\)"),
        removed_in="2.0",
    ),
    Rule(
        "DJ-RENDER-TO-RESPONSE", "django", "error", "render_to_response",
        "`render_to_response` was removed.",
        "Use django.shortcuts.render(request, template, context).",
        _rx(r"\brender_to_response\b"),
        removed_in="3.0",
    ),
    Rule(
        "DJ-CONTEXT-INSTANCE", "django", "error", "context_instance=RequestContext(...)",
        "The `context_instance` argument was removed.",
        "Use render(request, ...) or pass `request` to the template engine.",
        _rx(r"\bcontext_instance[ \t]*="),
        removed_in="1.10",
    ),
    Rule(
        "DJ-URLRESOLVERS", "django", "error", "django.core.urlresolvers",
        "The module moved to django.urls and the old path was removed.",
        "from django.urls import reverse, resolve, ...",
        _rx(r"django\.core\.urlresolvers"),
        removed_in="2.0",
    ),
    Rule(
        "DJ-CONTEXT-PROCESSORS", "django", "error", "django.core.context_processors",
        "Context processors moved to django.template.context_processors.",
        "Update the dotted paths (settings and imports).",
        _rx(r"django\.core\.context_processors"),
        keep_strings=True,
        removed_in="1.10",
    ),
    Rule(
        "DJ-MIDDLEWARE-CLASSES", "django", "error", "MIDDLEWARE_CLASSES setting",
        "Replaced by MIDDLEWARE with a new middleware style.",
        "Rename to MIDDLEWARE; convert old-style middleware or use MiddlewareMixin.",
        _rx(r"^[ \t]*MIDDLEWARE_CLASSES[ \t]*="),
        removed_in="2.0",
    ),
    Rule(
        "DJ-TEMPLATE-SETTINGS", "django", "error", "TEMPLATE_* settings",
        "TEMPLATE_DIRS, TEMPLATE_LOADERS, TEMPLATE_CONTEXT_PROCESSORS, TEMPLATE_DEBUG were replaced by TEMPLATES.",
        "Move them into the TEMPLATES setting (available since 1.8).",
        _rx(r"^[ \t]*TEMPLATE_(?:DIRS|LOADERS|CONTEXT_PROCESSORS|DEBUG|STRING_IF_INVALID)[ \t]*="),
        removed_in="1.10",
    ),
    Rule(
        "DJ-SOUTH", "django", "error", "South migrations",
        "South is not compatible with Django 1.7+; Django ships its own migrations.",
        "Convert existing South migrations to Django migrations, then remove South.",
        _rx(r"^[ \t]*(?:from|import)[ \t]+south\b|['\"]south['\"]"),
        keep_strings=True,
    ),
    Rule(
        "DJ-FK-ON-DELETE", "django", "error", "ForeignKey / OneToOneField without on_delete",
        "on_delete became a required argument.",
        "Pass on_delete explicitly (models.CASCADE keeps the old default behaviour).",
        check=_check_on_delete,
        removed_in="2.0",
    ),
    Rule(
        "DJ-PERMALINK", "django", "error", "models.permalink",
        "The `permalink` decorator was removed.",
        "Call reverse() inside get_absolute_url().",
        _rx(r"@(?:models\.)?permalink\b|models\.permalink\b|from[ \t]+django\.db\.models[ \t]+import[^\n]*\bpermalink\b"),
        removed_in="2.1",
    ),
    Rule(
        "DJ-IS-AUTH-CALL", "django", "error", "user.is_authenticated()",
        "is_authenticated / is_anonymous became properties; calling them was removed.",
        "Use user.is_authenticated (no parentheses).",
        _rx(r"\.is_(?:authenticated|anonymous)[ \t]*\([ \t]*\)"),
        removed_in="2.0",
    ),
    Rule(
        "DJ-SIX", "django", "error", "django.utils.six",
        "Django's bundled six was removed along with Python 2 support.",
        "Drop six, or depend on the `six` package directly while still on 2.7.",
        _rx(r"django\.utils\.six\b|from[ \t]+django\.utils[ \t]+import[^\n]*\bsix\b"),
        removed_in="3.0",
    ),
    Rule(
        "DJ-PY2-TEXT-HELPERS", "django", "warning", "python_2_unicode_compatible / force_unicode / smart_unicode",
        "Python 2-era text helpers that no longer exist in current Django.",
        "Define __str__, and use force_str / smart_str.",
        _rx(r"\b(?:python_2_unicode_compatible|smart_unicode|force_unicode)\b"),
    ),
    Rule(
        "DJ-SORTEDDICT", "django", "error", "django.utils.datastructures.SortedDict",
        "SortedDict was removed.",
        "Use collections.OrderedDict.",
        _rx(r"\bSortedDict\b"),
        removed_in="1.9",
    ),
    Rule(
        "DJ-SIMPLEJSON", "django", "error", "django.utils.simplejson",
        "The bundled simplejson was removed.",
        "Use the standard json module.",
        _rx(r"django\.utils\.simplejson|from[ \t]+django\.utils[ \t]+import[^\n]*\bsimplejson\b"),
    ),
    Rule(
        "DJ-ASSIGNMENT-TAG", "django", "error", "register.assignment_tag",
        "`assignment_tag` was removed.",
        "Use simple_tag (it supports `as var`).",
        _rx(r"\.assignment_tag\b"),
        removed_in="2.0",
    ),
    Rule(
        "DJ-GET-MODEL", "django", "error", "django.db.models.get_model / get_models / get_app",
        "The app-loading helpers were removed in favour of the app registry.",
        "Use django.apps.apps.get_model() / apps.get_models().",
        _rx(
            r"\bdjango\.db\.models\.(?:get_model|get_models|get_app)\b|"
            r"from[ \t]+django\.db\.models[ \t]+import[^\n]*\bget_(?:model|models|app)\b"
        ),
        removed_in="1.9",
    ),
]

TEMPLATE_RULES: list[Rule] = [
    Rule(
        "TPL-LOAD-FROM-FUTURE", "template", "error", "{% load ... from future %}",
        "The `future` template tag library was removed.",
        "Delete the load tag; the new behaviour is the default.",
        _rx(r"\{%[ \t]*load[ \t]+[\w ]+?[ \t]+from[ \t]+future[ \t]*%\}"),
        removed_in="1.9",
    ),
]

RULES: list[Rule] = PYTHON2_RULES + DJANGO_RULES + TEMPLATE_RULES
RULES_BY_ID: dict[str, Rule] = {r.id: r for r in RULES}
