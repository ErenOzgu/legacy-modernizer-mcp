from __future__ import annotations

import pytest

from legacy_modernizer_mcp.rules import RULES, RULES_BY_ID

# (rule id, snippet that must trigger it)
POSITIVE = [
    ("PY2-PRINT-STMT", 'print "hello"\n'),
    ("PY2-PRINT-STMT", "print x, y\n"),
    ("PY2-PRINT-STMT", "print >>sys.stderr, 'x'\n"),
    ("PY2-PRINT-STMT", "def f():\n    print\n"),
    ("PY2-EXCEPT-COMMA", "try:\n    pass\nexcept ValueError, e:\n    pass\n"),
    ("PY2-RAISE-COMMA", 'raise ValueError, "boom"\n'),
    ("PY2-HAS-KEY", "d.has_key('a')\n"),
    ("PY2-DICT-ITER", "for k in d.iteritems():\n    pass\n"),
    ("PY2-DICT-ITER", "d.itervalues()\n"),
    ("PY2-XRANGE", "for i in xrange(3):\n    pass\n"),
    ("PY2-UNICODE", "s = unicode(x)\n"),
    ("PY2-BASESTRING", "isinstance(x, basestring)\n"),
    ("PY2-LONG", "n = long(3)\n"),
    ("PY2-LONG-LITERAL", "n = 10L\n"),
    ("PY2-LONG-LITERAL", "mask = 0xFFL\n"),
    ("PY2-OCTAL", "os.chmod(p, 0755)\n"),
    ("PY2-REMOVED-BUILTIN", "x = raw_input('?')\n"),
    ("PY2-REMOVED-BUILTIN", "execfile('a.py')\n"),
    ("PY2-REDUCE", "total = reduce(add, xs)\n"),
    ("PY2-NEXT-METHOD", "it.next()\n"),
    ("PY2-BACKTICK", "s = `x`\n"),
    ("PY2-NE-OPERATOR", "if a <> b:\n    pass\n"),
    ("PY2-EXEC-STMT", "exec code in ns\n"),
    ("PY2-METACLASS", "class A(object):\n    __metaclass__ = Meta\n"),
    ("PY2-CMP-ARG", "xs.sort(cmp=lambda a, b: a - b)\n"),
    ("PY2-CMP-ARG", "sorted(xs, cmp=compare)\n"),
    ("PY2-MAXINT", "x = sys.maxint\n"),
    ("PY2-STRING-MODULE", "string.letters\n"),
    ("PY2-STRING-MODULE", "string.join(parts, ',')\n"),
    ("PY2-OLD-IMPORT", "import urllib2\n"),
    ("PY2-OLD-IMPORT", "import ConfigParser\n"),
    ("PY2-OLD-IMPORT", "from StringIO import StringIO\n"),
    ("PY2-OLD-IMPORT", "import cPickle\n"),
    ("PY2-ITERTOOLS", "from itertools import izip\n"),
    ("PY2-ITERTOOLS", "itertools.imap(f, xs)\n"),
    ("PY2-TUPLE-PARAMS", "def f(a, (b, c)):\n    pass\n"),
    ("PY2-LAMBDA-TUPLE", "f = lambda (a, b): a + b\n"),
    ("PY2-DICT-VIEW-INDEX", "first = d.keys()[0]\n"),
    ("PY2-DICT-VIEW-INDEX", "d.values().sort()\n"),
    ("PY2-LEN-ITERATOR", "n = len(map(f, xs))\n"),
    ("PY2-LEN-ITERATOR", "n = len(filter(f, xs))\n"),
    ("PY2-DUNDER-METHODS", "class A:\n    def __unicode__(self):\n        return ''\n"),
    ("PY2-DUNDER-METHODS", "class A:\n    def __nonzero__(self):\n        return True\n"),
    ("PY2-GETCWDU", "os.getcwdu()\n"),
    ("PY2-SETDEFAULTENCODING", "sys.setdefaultencoding('utf-8')\n"),
    ("PY2-UR-PREFIX", "s = ur'abc'\n"),
    # Django
    ("DJ-PATTERNS", "urlpatterns = patterns('', url(r'^$', v))\n"),
    ("DJ-URL-STRING-VIEW", "urlpatterns = [url(r'^$', 'app.views.home')]\n"),
    ("DJ-URLS-DEFAULTS", "from django.conf.urls.defaults import *\n"),
    ("DJ-ADMIN-URLS-INCLUDE", "url(r'^admin/', include(admin.site.urls))\n"),
    ("DJ-RENDER-TO-RESPONSE", "return render_to_response('a.html', {})\n"),
    ("DJ-CONTEXT-INSTANCE", "render(request, 'a.html', {}, context_instance=RequestContext(request))\n"),
    ("DJ-URLRESOLVERS", "from django.core.urlresolvers import reverse\n"),
    ("DJ-CONTEXT-PROCESSORS", "'django.core.context_processors.request',\n"),
    ("DJ-MIDDLEWARE-CLASSES", "MIDDLEWARE_CLASSES = ('a.B',)\n"),
    ("DJ-TEMPLATE-SETTINGS", "TEMPLATE_DIRS = ('t',)\n"),
    ("DJ-TEMPLATE-SETTINGS", "TEMPLATE_LOADERS = ()\n"),
    ("DJ-SOUTH", "INSTALLED_APPS = ('django.contrib.auth', 'south')\n"),
    ("DJ-SOUTH", "from south.db import db\n"),
    ("DJ-FK-ON-DELETE", "owner = models.ForeignKey(User)\n"),
    ("DJ-FK-ON-DELETE", "owner = models.OneToOneField('auth.User', null=True)\n"),
    ("DJ-FK-ON-DELETE", "owner = models.ForeignKey(\n    User,\n    related_name='x',\n)\n"),
    ("DJ-PERMALINK", "@models.permalink\ndef get_absolute_url(self):\n    pass\n"),
    ("DJ-IS-AUTH-CALL", "if request.user.is_authenticated():\n    pass\n"),
    ("DJ-IS-AUTH-CALL", "if request.user.is_anonymous():\n    pass\n"),
    ("DJ-SIX", "from django.utils import six\n"),
    ("DJ-SIX", "from django.utils.six.moves import urllib\n"),
    ("DJ-PY2-TEXT-HELPERS", "from django.utils.encoding import force_unicode\n"),
    ("DJ-PY2-TEXT-HELPERS", "@python_2_unicode_compatible\nclass A:\n    pass\n"),
    ("DJ-SORTEDDICT", "from django.utils.datastructures import SortedDict\n"),
    ("DJ-SIMPLEJSON", "from django.utils import simplejson\n"),
    ("DJ-SIMPLEJSON", "import django.utils.simplejson\n"),
    ("DJ-ASSIGNMENT-TAG", "@register.assignment_tag\ndef t():\n    pass\n"),
    ("DJ-GET-MODEL", "from django.db.models import get_model\n"),
]

# Valid modern code that must NOT trigger the given rule.
NEGATIVE = [
    ("PY2-PRINT-STMT", "print('hello')\n"),
    ("PY2-PRINT-STMT", "print(x, file=sys.stderr)\n"),
    ("PY2-PRINT-STMT", "print = logger.info\n"),
    ("PY2-PRINT-STMT", "pprint(x)\n"),
    ("PY2-PRINT-STMT", "blueprint x\n"),
    ("PY2-EXCEPT-COMMA", "try:\n    pass\nexcept (ValueError, TypeError) as e:\n    pass\n"),
    ("PY2-EXCEPT-COMMA", "try:\n    pass\nexcept (ValueError, TypeError):\n    pass\n"),
    ("PY2-RAISE-COMMA", "raise ValueError('boom')\n"),
    ("PY2-HAS-KEY", "'a' in d\n"),
    ("PY2-DICT-ITER", "for k, v in d.items():\n    pass\n"),
    ("PY2-XRANGE", "for i in range(3):\n    pass\n"),
    ("PY2-UNICODE", "s = str(x)\nunicode_literals = 1\n"),
    ("PY2-LONG", "n = int(3)\nbelong(1)\n"),
    ("PY2-LONG-LITERAL", "n = 10\nname = 'x10L'\nvalue = 0xF\n"),
    ("PY2-OCTAL", "mode = 0o755\nzero = 0\nfloat_ = 0.5\nhexa = 0x755\n"),
    ("PY2-REMOVED-BUILTIN", "x = input('?')\n"),
    ("PY2-NE-OPERATOR", "if a != b:\n    pass\n"),
    ("PY2-BACKTICK", "s = 'a `code` b'\n# `comment`\n"),
    ("PY2-EXEC-STMT", "exec(code, ns)\n"),
    ("PY2-MAXINT", "x = sys.maxsize\n"),
    ("PY2-STRING-MODULE", "string.ascii_letters\nstring.Template\n"),
    ("PY2-OLD-IMPORT", "import urllib.request\nimport configparser\n"),
    ("PY2-ITERTOOLS", "from itertools import chain\nitertools.zip_longest(a, b)\n"),
    ("PY2-DICT-VIEW-INDEX", "first = list(d.keys())[0]\nfor k in d.keys():\n    pass\n"),
    ("PY2-LEN-ITERATOR", "n = len(list(map(f, xs)))\n"),
    ("PY2-DUNDER-METHODS", "class A:\n    def __str__(self):\n        return ''\n"),
    ("DJ-PATTERNS", "urlpatterns = [url(r'^$', v)]\n"),
    ("DJ-URL-STRING-VIEW", "urlpatterns = [url(r'^$', views.home), url(r'^a/', include('a.urls'))]\n"),
    ("DJ-ADMIN-URLS-INCLUDE", "path('admin/', admin.site.urls)\n"),
    ("DJ-RENDER-TO-RESPONSE", "return render(request, 'a.html', {})\n"),
    ("DJ-MIDDLEWARE-CLASSES", "MIDDLEWARE = ['a.B']\n"),
    ("DJ-TEMPLATE-SETTINGS", "TEMPLATES = [{'DIRS': []}]\n"),
    ("DJ-SOUTH", "INSTALLED_APPS = ['django.contrib.auth', 'southside']\n"),
    ("DJ-FK-ON-DELETE", "owner = models.ForeignKey(User, on_delete=models.CASCADE)\n"),
    ("DJ-FK-ON-DELETE", "owner = models.ForeignKey(User, models.CASCADE)\n"),
    ("DJ-FK-ON-DELETE", "owner = models.OneToOneField(User, models.SET_NULL, null=True)\n"),
    ("DJ-FK-ON-DELETE", "owner = models.ForeignKey(\n    User,\n    related_name='x',\n    on_delete=models.PROTECT,\n)\n"),
    ("DJ-FK-ON-DELETE", "# owner = models.ForeignKey(User)\n"),
    ("DJ-FK-ON-DELETE", "x = 'models.ForeignKey(User)'\n"),
    ("DJ-IS-AUTH-CALL", "if request.user.is_authenticated:\n    pass\n"),
    ("DJ-GET-MODEL", "from django.apps import apps\nModel = apps.get_model('a', 'B')\n"),
]


@pytest.mark.parametrize(("rule_id", "source"), POSITIVE)
def test_rule_triggers(rule_id, source, rule_ids):
    assert rule_id in rule_ids(source)


@pytest.mark.parametrize(("rule_id", "source"), NEGATIVE)
def test_rule_does_not_trigger(rule_id, source, rule_ids):
    assert rule_id not in rule_ids(source)


def test_every_rule_has_at_least_one_positive_example():
    covered = {rule_id for rule_id, _ in POSITIVE} | {"TPL-LOAD-FROM-FUTURE"}
    assert covered == set(RULES_BY_ID)


def test_template_rule(rule_ids):
    assert "TPL-LOAD-FROM-FUTURE" in rule_ids("{% load url from future %}\n", "page.html")
    assert "TPL-LOAD-FROM-FUTURE" not in rule_ids("{% load static %}\n", "page.html")


def test_template_rules_do_not_run_on_python_files(rule_ids):
    assert "TPL-LOAD-FROM-FUTURE" not in rule_ids("{% load url from future %}\n")


def test_rule_ids_are_unique_and_well_formed():
    ids = [r.id for r in RULES]
    assert len(ids) == len(set(ids)) == 52
    for r in RULES:
        assert r.category in {"python2", "django", "template"}
        assert r.severity in {"error", "warning", "info"}
        assert r.title and r.explanation and r.fix
        assert r.pattern is not None or r.check is not None


def test_fk_on_delete_reports_each_missing_call_once(rule_ids, tmp_path):
    from legacy_modernizer_mcp.scanner import scan

    source = (
        "a = models.ForeignKey(A)\n"
        "b = models.ForeignKey(B, on_delete=models.CASCADE)\n"
        "c = models.OneToOneField(C)\n"
    )
    target = tmp_path / "models.py"
    target.write_text(source)
    hits = [f for f in scan(target).findings if f.rule_id == "DJ-FK-ON-DELETE"]
    assert [f.line for f in hits] == [1, 3]
