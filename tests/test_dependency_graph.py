import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import dependency_graph  # noqa: E402


def _make_resource(root, name, deps=None, exports=None):
    res = root / name
    res.mkdir(parents=True)
    parts = ["fx_version 'cerulean'", "game 'gta5'"]
    if deps:
        parts.append("dependencies {\n" + ",\n".join(f"  '{d}'" for d in deps) + "\n}")
    if exports:
        parts.append("exports {\n" + ",\n".join(f"  '{e}'" for e in exports) + "\n}")
    (res / "fxmanifest.lua").write_text("\n".join(parts), encoding="utf-8")
    return res


def test_basic_graph(tmp_path):
    root = tmp_path / "resources"
    root.mkdir()
    _make_resource(root, "oxmysql", exports=["query", "execute"])
    _make_resource(root, "es_extended", deps=["oxmysql"], exports=["getSharedObject"])
    _make_resource(root, "esx_jobs", deps=["es_extended"])

    g = dependency_graph.build_graph(str(root))
    assert set(g.nodes) == {"oxmysql", "es_extended", "esx_jobs"}
    assert g.nodes["es_extended"].dependencies == ["oxmysql"]
    assert "esx_jobs" in g.nodes["es_extended"].referenced_by
    assert g.cycles == []
    assert not g.nodes["esx_jobs"].missing_deps


def test_missing_dep_detected(tmp_path):
    root = tmp_path / "resources"
    root.mkdir()
    _make_resource(root, "demo", deps=["does_not_exist"])

    g = dependency_graph.build_graph(str(root))
    assert "does_not_exist" in g.nodes["demo"].missing_deps


def test_cycle_detection(tmp_path):
    root = tmp_path / "resources"
    root.mkdir()
    _make_resource(root, "a", deps=["b"])
    _make_resource(root, "b", deps=["a"])

    g = dependency_graph.build_graph(str(root))
    assert g.cycles, "Expected at least one cycle"
    flat = {x for c in g.cycles for x in c}
    assert "a" in flat and "b" in flat


def test_category_folders_supported(tmp_path):
    root = tmp_path / "resources"
    category = root / "[core]"
    category.mkdir(parents=True)
    _make_resource(category, "core_one")
    _make_resource(category, "core_two", deps=["core_one"])

    g = dependency_graph.build_graph(str(root))
    assert "core_one" in g.nodes
    assert "core_two" in g.nodes


def test_deeply_nested_resources_are_found(tmp_path):
    """Regression: user reported nested resources weren't being found."""
    root = tmp_path / "resources"
    _make_resource(root / "myserver" / "scripts", "my_resource")
    _make_resource(root / "third-party" / "esx" / "addons", "esx_addon", deps=["my_resource"])

    g = dependency_graph.build_graph(str(root))
    assert "my_resource" in g.nodes
    assert "esx_addon" in g.nodes
    assert "my_resource" in g.nodes["esx_addon"].dependencies
