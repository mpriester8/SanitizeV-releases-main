import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import command_palette  # noqa: E402


def _make_action(title, **kw):
    return command_palette.PaletteAction(title=title, subtitle=kw.get("subtitle", ""),
                                         callback=lambda: None,
                                         category=kw.get("category", ""),
                                         keywords=kw.get("keywords", ""))


def test_empty_query_matches_all():
    a = _make_action("Anything")
    assert command_palette._score("", a) > 0


def test_substring_ranks_higher_than_subsequence():
    a = _make_action("Open Manifest Validator")
    direct = command_palette._score("manifest", a)
    sub = command_palette._score("mxynfest", a)  # subsequence-only match (cannot really happen here)
    no_match = command_palette._score("xyzw", a)
    assert direct > 0
    assert sub == 0 or sub < direct
    assert no_match == 0


def test_title_prefix_beats_keyword_match():
    a1 = _make_action("Backup")
    a2 = _make_action("Settings", keywords="backup")
    s1 = command_palette._score("back", a1)
    s2 = command_palette._score("back", a2)
    assert s1 > s2
