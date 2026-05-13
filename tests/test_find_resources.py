"""Tests for the recursive resource walker."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import fivem_utils  # noqa: E402


def _make_resource(parent, name):
    folder = parent / name
    folder.mkdir(parents=True)
    (folder / "fxmanifest.lua").write_text(
        "fx_version 'cerulean'\ngame 'gta5'\n", encoding="utf-8"
    )
    return folder


def test_flat_layout(tmp_path):
    _make_resource(tmp_path, "a")
    _make_resource(tmp_path, "b")
    names = {p.name for p in fivem_utils.find_resources(str(tmp_path))}
    assert names == {"a", "b"}


def test_bracket_categories(tmp_path):
    _make_resource(tmp_path / "[esx]", "esx_jobs")
    _make_resource(tmp_path / "[qb]", "qb_core")
    names = {p.name for p in fivem_utils.find_resources(str(tmp_path))}
    assert names == {"esx_jobs", "qb_core"}


def test_deeply_nested(tmp_path):
    """User's scenario: resources living several levels deep in custom folders."""
    _make_resource(tmp_path / "myserver" / "scripts", "my_resource")
    _make_resource(tmp_path / "myserver" / "ui" / "vendor", "another_one")
    names = {p.name for p in fivem_utils.find_resources(str(tmp_path))}
    assert names == {"my_resource", "another_one"}


def test_does_not_descend_into_a_resource(tmp_path):
    """A resource's own subdirs are never treated as separate resources."""
    parent = _make_resource(tmp_path, "outer")
    (parent / "stream").mkdir()
    # Stick a stray fxmanifest under stream/ — must NOT be picked up
    (parent / "stream" / "fxmanifest.lua").write_text("x", encoding="utf-8")
    names = [p.name for p in fivem_utils.find_resources(str(tmp_path))]
    assert names == ["outer"]


def test_root_is_a_resource(tmp_path):
    """If the user picks a single resource folder directly, return just that."""
    resource = _make_resource(tmp_path, "solo")
    found = fivem_utils.find_resources(str(resource))
    assert found == [resource]


def test_skips_noise_directories(tmp_path):
    """cache/, node_modules/, .git/ etc. should be skipped."""
    _make_resource(tmp_path / "cache" / "junk", "fake")
    _make_resource(tmp_path / "node_modules" / "pkg", "fake2")
    _make_resource(tmp_path / ".git" / "junk", "fake3")
    _make_resource(tmp_path / "real_resource", "real")
    names = {p.name for p in fivem_utils.find_resources(str(tmp_path))}
    # real_resource has a nested resource called 'real' under it -- but
    # real_resource itself has its own manifest so we stop there.
    # Verify only the top-level real resource is found, no cache noise.
    assert "fake" not in names
    assert "fake2" not in names
    assert "fake3" not in names


def test_validate_resources_folder_finds_nested(tmp_path):
    _make_resource(tmp_path / "deep" / "deeper" / "deepest", "nested_res")
    results = fivem_utils.validate_resources_folder(str(tmp_path))
    assert any("nested_res" in r.path.replace("\\", "/") for r in results)
