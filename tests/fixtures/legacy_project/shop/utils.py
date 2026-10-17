import string
import sys
from itertools import izip

MODE = 0755
BIG = 10L
LETTERS = string.letters
LIMIT = sys.maxint


def first_key(mapping):
    if mapping.has_key("a") <> 0:
        return mapping.keys()[0]
    return `mapping`


def run(code):
    exec code in {}
    return raw_input("> ")


class Legacy(object):
    __metaclass__ = type

    def __nonzero__(self):
        return True
