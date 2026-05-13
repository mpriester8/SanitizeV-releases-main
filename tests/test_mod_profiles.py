import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import pytest  # noqa: E402

import mod_profiles  # noqa: E402


def _make_source(tmp_path):
    src = tmp_path / "source"
    (src / "mods").mkdir(parents=True)
    (src / "plugins").mkdir(parents=True)
    (src / "mods" / "a.txt").write_text("mod-a")
    (src / "plugins" / "p.dll").write_text("plugin-p")
    return src


def test_create_and_capture_profile(tmp_path):
    src = _make_source(tmp_path)
    backup = tmp_path / "backup"
    backup.mkdir()

    store = mod_profiles.ProfileStore(backup_dir=str(backup), profiles=[])
    profile = mod_profiles.create_profile(store, "alpha", "first")
    assert profile.name == "alpha"
    assert profile.folders == ["mods", "plugins"]

    mod_profiles.capture_current(store, "alpha", str(src))
    stash_root = backup / "_profiles" / "alpha"
    assert (stash_root / "mods" / "a.txt").read_text() == "mod-a"
    assert (stash_root / "plugins" / "p.dll").read_text() == "plugin-p"


def test_activate_swaps_loadouts(tmp_path):
    src = _make_source(tmp_path)
    backup = tmp_path / "backup"
    backup.mkdir()

    store = mod_profiles.ProfileStore(backup_dir=str(backup), profiles=[])
    mod_profiles.create_profile(store, "alpha")
    mod_profiles.create_profile(store, "beta")

    # Capture alpha = current source state
    mod_profiles.capture_current(store, "alpha", str(src))

    # Mutate source state, capture as beta
    (src / "mods" / "a.txt").write_text("mod-a-v2")
    (src / "mods" / "b.txt").write_text("mod-b")
    mod_profiles.capture_current(store, "beta", str(src))

    # Activate alpha → should restore original a.txt and remove b.txt
    mod_profiles.activate_profile(store, "alpha", str(src))
    assert (src / "mods" / "a.txt").read_text() == "mod-a"
    assert not (src / "mods" / "b.txt").exists()
    assert store.active == "alpha"

    # Activate beta → should bring beta state back
    mod_profiles.activate_profile(store, "beta", str(src))
    assert (src / "mods" / "a.txt").read_text() == "mod-a-v2"
    assert (src / "mods" / "b.txt").read_text() == "mod-b"
    assert store.active == "beta"


def test_persistence_roundtrip(tmp_path):
    backup = tmp_path / "bk"
    backup.mkdir()

    store = mod_profiles.ProfileStore(backup_dir=str(backup), profiles=[])
    mod_profiles.create_profile(store, "alpha", "desc")
    loaded = mod_profiles.load_store(str(backup))
    assert any(p.name == "alpha" and p.description == "desc" for p in loaded.profiles)


def test_duplicate_name_rejected(tmp_path):
    backup = tmp_path / "bk"
    backup.mkdir()
    store = mod_profiles.ProfileStore(backup_dir=str(backup), profiles=[])
    mod_profiles.create_profile(store, "alpha")
    with pytest.raises(ValueError):
        mod_profiles.create_profile(store, "Alpha")
