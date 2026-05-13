import os
import sys
import shutil
import json

import pytest

# Ensure src is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.logic import (
    move_files_logic,
    revert_files_logic,
    clear_cache_logic,
    load_state,
)


def cleanup_state_file():
    try:
        import src.logic as logic
        if os.path.exists(logic.STATE_FILE):
            os.remove(logic.STATE_FILE)
            # remove STATE_DIR if empty
            try:
                os.rmdir(logic.STATE_DIR)
            except OSError:
                pass
    except Exception:
        pass


def test_move_and_revert_files_and_xml(tmp_path):
    # Setup source, xml source, replacement and destination
    source = tmp_path / "source"
    source.mkdir()
    mods = source / "mods"
    plugins = source / "plugins"
    mods.mkdir()
    plugins.mkdir()
    (mods / "m1.txt").write_text("modcontent")
    (plugins / "p1.dll").write_text("plugcontent")

    xml_src_dir = tmp_path / "xml_src"
    xml_src_dir.mkdir()
    xml_filename = "gta5_settings.xml"
    xml_path = xml_src_dir / xml_filename
    xml_path.write_text("<root><orig/></root>")

    replacement = tmp_path / "replacement.xml"
    replacement.write_text("<root><repl/></root>")

    dest = tmp_path / "dest"
    dest.mkdir()

    # Run move operation with a prompt callback that returns a label
    label = "UnitTest"
    prompt_cb = lambda *args: label

    try:
        success = move_files_logic(
            str(source),
            "mods",
            "plugins",
            str(xml_src_dir),
            xml_filename,
            str(replacement),
            str(dest),
            include_mods=True,
            include_plugins=True,
            include_xml=True,
            log_callback=lambda m: None,
            prompt_callback=prompt_cb,
        )

        assert success

        # Mods and plugins should have been moved to dest
        assert not (source / "mods").exists()
        assert not (source / "plugins").exists()
        assert (dest / "mods").exists()
        assert (dest / "plugins").exists()

        # Labeled xml should be in dest
        labeled_name = f"{os.path.splitext(xml_filename)[0]}_{label}{os.path.splitext(xml_filename)[1]}"
        labeled_path = dest / labeled_name
        assert labeled_path.exists()

        # Original xml path should now contain replacement content
        assert xml_path.exists()
        assert xml_path.read_text() == replacement.read_text()

        # Now revert using the labeled backup path
        success_revert = revert_files_logic(
            str(source),
            "mods",
            "plugins",
            str(xml_src_dir),
            xml_filename,
            str(dest),
            include_mods=True,
            include_plugins=True,
            include_xml=True,
            restore_xml_path=str(labeled_path),
            log_callback=lambda m: None,
        )

        assert success_revert

        # Mods and plugins should be back in source
        assert (source / "mods").exists()
        assert (source / "plugins").exists()

        # XML should be restored to original content
        assert xml_path.exists()
        assert xml_path.read_text() == "<root><orig/></root>"

    finally:
        cleanup_state_file()


def test_clear_cache_logic(tmp_path):
    # Create fake data directory with caches
    source = tmp_path / "source"
    data = source / "data"
    cache = data / "cache"
    s_cache = data / "server-cache"
    s_cache_priv = data / "server-cache-priv"
    s_cache_priv.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    s_cache.mkdir(parents=True, exist_ok=True)

    (cache / "f1.bin").write_text("x")
    (s_cache / "f2.bin").write_text("y")
    (s_cache_priv / "f3.bin").write_text("z")

    logs = []
    def log_cb(m):
        logs.append(m)

    try:
        success, timestamp = clear_cache_logic(str(source), log_callback=log_cb)
        assert success
        assert timestamp is not None
        # cache folders should be removed
        assert not cache.exists()
        assert not s_cache.exists()
        assert not s_cache_priv.exists()

        # state should have been saved
        state = load_state()
        assert 'last_cache_clear' in state
    finally:
        cleanup_state_file()
