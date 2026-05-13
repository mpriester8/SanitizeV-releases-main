import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import fivem_utils  # noqa: E402


def test_plural_games_satisfies_required_game(tmp_path):
    """A manifest with `games { 'gta5' }` must NOT report 'Missing required field: game'."""
    resource = tmp_path / "myres"
    resource.mkdir()
    (resource / "fxmanifest.lua").write_text(
        "fx_version 'cerulean'\n"
        "games {'gta5'}\n"
        "lua54 'yes'\n",
        encoding="utf-8",
    )
    result = fivem_utils.validate_manifest(str(resource))
    missing = [i for i in result.issues if "Missing required field" in i.message]
    assert missing == []
    assert result.is_valid


def test_plural_games_warns_on_unknown_value(tmp_path):
    resource = tmp_path / "myres"
    resource.mkdir()
    (resource / "fxmanifest.lua").write_text(
        "fx_version 'cerulean'\n"
        "games {'gta5', 'unknown_game'}\n",
        encoding="utf-8",
    )
    result = fivem_utils.validate_manifest(str(resource))
    warnings = [i for i in result.issues if "unknown_game" in i.message.lower()]
    assert warnings, f"Expected a warning about 'unknown_game', got {result.issues}"


def test_singular_game_still_works(tmp_path):
    resource = tmp_path / "myres"
    resource.mkdir()
    (resource / "fxmanifest.lua").write_text(
        "fx_version 'cerulean'\ngame 'gta5'\nlua54 'yes'\n",
        encoding="utf-8",
    )
    result = fivem_utils.validate_manifest(str(resource))
    missing = [i for i in result.issues if "Missing required field" in i.message]
    assert missing == []
    assert result.is_valid
