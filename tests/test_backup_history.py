import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import backup_history  # noqa: E402


def _make_source(tmp_path):
    src = tmp_path / "source"
    (src / "mods").mkdir(parents=True)
    (src / "plugins").mkdir(parents=True)
    (src / "mods" / "a.txt").write_text("a")
    (src / "plugins" / "p.txt").write_text("p")
    return src


def test_create_and_list(tmp_path):
    src = _make_source(tmp_path)
    backup = tmp_path / "bk"
    backup.mkdir()

    snap = backup_history.create_snapshot(str(src), str(backup), "first")
    assert snap.file_count == 2
    snaps = backup_history.load_index(str(backup))
    assert len(snaps) == 1
    assert snaps[0].label == "first"


def test_diff_two_snapshots(tmp_path):
    src = _make_source(tmp_path)
    backup = tmp_path / "bk"
    backup.mkdir()

    a = backup_history.create_snapshot(str(src), str(backup), "alpha")
    # Mutate
    (src / "mods" / "a.txt").write_text("a-modified")
    (src / "mods" / "b.txt").write_text("b-new")
    (src / "plugins" / "p.txt").unlink()
    b = backup_history.create_snapshot(str(src), str(backup), "beta")

    diff = backup_history.diff_snapshots(str(backup), a.id, b.id)
    assert "mods/a.txt" in diff["changed"]
    assert "mods/b.txt" in diff["added"]
    assert "plugins/p.txt" in diff["removed"]


def test_restore_roundtrip(tmp_path):
    src = _make_source(tmp_path)
    backup = tmp_path / "bk"
    backup.mkdir()

    snap = backup_history.create_snapshot(str(src), str(backup), "saved")
    # Wreck source state
    (src / "mods" / "a.txt").write_text("changed")
    (src / "mods" / "wreck.txt").write_text("oops")

    ok = backup_history.restore_snapshot(str(backup), snap.id, str(src))
    assert ok
    assert (src / "mods" / "a.txt").read_text() == "a"
    assert not (src / "mods" / "wreck.txt").exists()


def test_delete_snapshot(tmp_path):
    src = _make_source(tmp_path)
    backup = tmp_path / "bk"
    backup.mkdir()
    snap = backup_history.create_snapshot(str(src), str(backup), "first")
    assert backup_history.delete_snapshot(str(backup), snap.id)
    assert backup_history.load_index(str(backup)) == []
