"""Docstring mentioning print "x", xrange(10) and `except X, e:` must not be flagged."""
from __future__ import print_function, unicode_literals

from functools import reduce

# print "commented out"
MESSAGE = 'iteritems() has_key() unicode(x) 0755 10L'
TEXT = """
print "inside a triple-quoted string"
"""
MODE = 0o755
ZERO = 0


def total(values):
    print("sum:", sum(values))
    return reduce(lambda a, b: a + b, values, 0)
