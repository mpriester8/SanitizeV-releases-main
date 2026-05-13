import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import manifest_fixer  # noqa: E402


def test_adds_missing_fx_version_and_game(tmp_path):
    resource = tmp_path / "myres"
    resource.mkdir()
    (resource / "fxmanifest.lua").write_text(
        "name 'myres'\nauthor 'me'\nclient_scripts { 'client.lua' }\n",
        encoding="utf-8",
    )

    result = manifest_fixer.auto_fix(str(resource))

    assert result.success
    text = (resource / "fxmanifest.lua").read_text(encoding="utf-8")
    assert "fx_version 'cerulean'" in text
    assert "game 'gta5'" in text
    assert any("Added missing fx_version" in c for c in result.changes)
    assert any("Added missing game" in c for c in result.changes)


def test_no_bak_files_left_behind(tmp_path):
    """We rely on version control; auto-fix should never write *.bak files."""
    resource = tmp_path / "myres"
    resource.mkdir()
    (resource / "fxmanifest.lua").write_text(
        "name 'myres'\nauthor 'me'\n",
        encoding="utf-8",
    )

    manifest_fixer.auto_fix(str(resource))

    bak_files = list(resource.glob("*.bak"))
    assert bak_files == [], f"Auto-fix left backup files behind: {bak_files}"


def test_plural_games_form_is_accepted(tmp_path):
    """`games { 'gta5' }` already satisfies the game requirement — don't add a duplicate."""
    resource = tmp_path / "myres"
    resource.mkdir()
    (resource / "fxmanifest.lua").write_text(
        "fx_version 'cerulean'\n"
        "games {'gta5'}\n"
        "lua54 'yes'\n",
        encoding="utf-8",
    )

    result = manifest_fixer.auto_fix(str(resource))

    text = (resource / "fxmanifest.lua").read_text(encoding="utf-8")
    assert "game 'gta5'" not in text   # singular form must NOT be added
    assert "games {'gta5'}" in text     # original plural form preserved
    assert result.error == "Nothing to fix"


def test_upgrades_old_fx_version(tmp_path):
    resource = tmp_path / "myres"
    resource.mkdir()
    (resource / "fxmanifest.lua").write_text(
        "fx_version 'adamant'\ngame 'gta5'\nlua54 'yes'\n",
        encoding="utf-8",
    )

    result = manifest_fixer.auto_fix(str(resource))

    assert result.success
    text = (resource / "fxmanifest.lua").read_text(encoding="utf-8")
    assert "fx_version 'cerulean'" in text
    assert "adamant" not in text
    assert any("Upgraded fx_version" in c for c in result.changes)


def test_dedupes_dependencies(tmp_path):
    resource = tmp_path / "myres"
    resource.mkdir()
    (resource / "fxmanifest.lua").write_text(
        "fx_version 'cerulean'\ngame 'gta5'\nlua54 'yes'\n"
        "dependencies { 'es_extended', 'oxmysql', 'es_extended' }\n",
        encoding="utf-8",
    )

    result = manifest_fixer.auto_fix(str(resource))

    assert result.success
    text = (resource / "fxmanifest.lua").read_text(encoding="utf-8")
    assert text.count("es_extended") == 1
    assert any("duplicate dependency" in c for c in result.changes)


def test_migrates_resource_lua_to_fxmanifest(tmp_path):
    resource = tmp_path / "old"
    resource.mkdir()
    (resource / "__resource.lua").write_text(
        "fx_version 'cerulean'\ngame 'gta5'\nlua54 'yes'\n",
        encoding="utf-8",
    )

    result = manifest_fixer.auto_fix(str(resource))

    assert result.success
    assert (resource / "fxmanifest.lua").exists()
    assert not (resource / "__resource.lua").exists()


def test_no_changes_when_clean(tmp_path):
    resource = tmp_path / "myres"
    resource.mkdir()
    (resource / "fxmanifest.lua").write_text(
        "fx_version 'cerulean'\ngame 'gta5'\nlua54 'yes'\n",
        encoding="utf-8",
    )

    result = manifest_fixer.auto_fix(str(resource))
    assert result.error == "Nothing to fix"
