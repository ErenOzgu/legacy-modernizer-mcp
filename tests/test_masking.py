from __future__ import annotations

import pytest

from legacy_modernizer_mcp.scanner import mask_source

SAMPLES = [
    'x = "print hello"  # print "comment"\n',
    "y = '''multi\nline print \"a\"\n'''\nz = 1\n",
    's = "escaped \\" quote"\n',
    'r = r"raw \\" print"\n',
    "f = b'bytes' + u\"uni\"\n",
    "# only a comment\n",
    "",
]


@pytest.mark.parametrize("source", SAMPLES)
def test_masking_preserves_length_and_newlines(source):
    masked = mask_source(source)
    assert len(masked) == len(source)
    assert masked.count("\n") == source.count("\n")
    kept = mask_source(source, keep_strings=True)
    assert len(kept) == len(source)
    assert kept.count("\n") == source.count("\n")


def test_comments_are_blanked():
    assert "print" not in mask_source('# print "x"\nvalue = 1\n')


def test_string_bodies_are_blanked_but_delimiters_stay():
    masked = mask_source('name = "print foo"\n')
    assert "print" not in masked
    assert masked.startswith('name = "')


def test_triple_quoted_strings_are_blanked():
    masked = mask_source('doc = """\nprint "inside"\n"""\n')
    assert "print" not in masked


def test_keep_strings_keeps_text_but_still_drops_comments():
    kept = mask_source('x = "south"  # comment south\n', keep_strings=True)
    assert "south" in kept
    assert kept.count("south") == 1


def test_code_outside_strings_is_untouched():
    source = "def f(a):\n    return a + 1\n"
    assert mask_source(source) == source
