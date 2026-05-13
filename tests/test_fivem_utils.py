import os
import sys
import pytest
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.fivem_utils import detect_conflicts, ConflictReport, FileConflict

def test_detect_conflicts(tmp_path):
    """
    Test detect_conflicts with various scenarios:
    - True duplicates (same content)
    - YMAP duplicates (same content, .ymap extension)
    - Name collisions (same name, different content, .ymap)
    - Ignored name collisions (non-ymap)
    """

    # Create resources structure
    res1 = tmp_path / "res1"
    res1.mkdir()
    res2 = tmp_path / "res2"
    res2.mkdir()

    # 1. True Duplicates (Regular files)
    # content "A" in res1/dup.txt and res2/dup.txt
    (res1 / "dup.txt").write_text("content A")
    (res2 / "dup.txt").write_text("content A")

    # 2. YMAP Duplicates (True duplicates)
    # content "B" in res1/map.ymap and res2/map.ymap
    (res1 / "map.ymap").write_text("content B")
    (res2 / "map.ymap").write_text("content B")

    # 3. Name Collision (YMAP - different content)
    # res1/coll.ymap="C1", res2/coll.ymap="C2"
    (res1 / "coll.ymap").write_text("content C1")
    (res2 / "coll.ymap").write_text("content C2")

    # 4. Name Collision (Regular file - different content) - Should be IGNORED
    # res1/ignore.txt="D1", res2/ignore.txt="D2"
    (res1 / "ignore.txt").write_text("content D1")
    (res2 / "ignore.txt").write_text("content D2")

    # 5. Unique file
    (res1 / "unique.txt").write_text("unique")

    # Run detection
    report = detect_conflicts(str(tmp_path), check_hashes=True)

    # Assertions

    # Check regular duplicates
    # dup.txt should be in duplicates
    dup_names = [d.filename for d in report.duplicates]
    assert "dup.txt" in dup_names
    assert "map.ymap" not in dup_names # Should be in ymap_duplicates

    # Check YMAP duplicates
    ymap_dup_names = [d.filename for d in report.ymap_duplicates]
    assert "map.ymap" in ymap_dup_names

    # Check Name Collisions
    coll_names = [c.filename for c in report.name_collisions]
    assert "coll.ymap" in coll_names
    assert "ignore.txt" not in coll_names # Should be ignored

    # verify locations count
    for dup in report.duplicates:
        if dup.filename == "dup.txt":
            assert len(dup.locations) == 2

    for col in report.name_collisions:
        if col.filename == "coll.ymap":
            assert len(col.locations) == 2
