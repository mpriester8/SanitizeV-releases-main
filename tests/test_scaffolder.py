import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import pytest  # noqa: E402

import scaffolder  # noqa: E402


def test_scaffold_basic(tmp_path):
    result = scaffolder.scaffold_resource(str(tmp_path), "my_demo", "basic", author="me", description="demo")
    root = tmp_path / "my_demo"
    assert root.exists()
    assert (root / "fxmanifest.lua").exists()
    assert (root / "client.lua").exists()
    assert (root / "server.lua").exists()
    manifest = (root / "fxmanifest.lua").read_text(encoding="utf-8")
    assert "fx_version 'cerulean'" in manifest
    assert "game 'gta5'" in manifest
    assert "my_demo" in manifest
    assert set(result.files) == {"fxmanifest.lua", "client.lua", "server.lua", "config.lua"}


def test_scaffold_esx_emits_esx_command(tmp_path):
    scaffolder.scaffold_resource(str(tmp_path), "esx_demo", "esx")
    server = (tmp_path / "esx_demo" / "server.lua").read_text(encoding="utf-8")
    assert "ESX.RegisterCommand" in server


def test_scaffold_qbcore_emits_qb_command(tmp_path):
    scaffolder.scaffold_resource(str(tmp_path), "qb_demo", "qbcore")
    server = (tmp_path / "qb_demo" / "server.lua").read_text(encoding="utf-8")
    assert "QBCore.Commands.Add" in server


def test_existing_folder_rejected(tmp_path):
    (tmp_path / "already").mkdir()
    with pytest.raises(FileExistsError):
        scaffolder.scaffold_resource(str(tmp_path), "already", "basic")


def test_invalid_template_rejected(tmp_path):
    with pytest.raises(ValueError):
        scaffolder.scaffold_resource(str(tmp_path), "bad", "nonexistent")
