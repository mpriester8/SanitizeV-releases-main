import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import server_cfg  # noqa: E402


SAMPLE = """\
# Comment line
sv_hostname "My FiveM Server"
sv_maxclients 32
set onesync on

ensure es_extended
ensure oxmysql
stop legacy_resource
"""


def test_parse_directives_and_resources(tmp_path):
    path = tmp_path / "server.cfg"
    path.write_text(SAMPLE, encoding="utf-8")

    cfg = server_cfg.parse_cfg(str(path))
    assert server_cfg.get_value(cfg, "sv_hostname") == "My FiveM Server"
    assert server_cfg.get_value(cfg, "sv_maxclients") == "32"

    resources = server_cfg.list_resources(cfg)
    names = {r[0] for r in resources}
    assert names == {"es_extended", "oxmysql", "legacy_resource"}
    started = {name for name, ok, _ in resources if ok}
    assert "es_extended" in started
    assert "legacy_resource" not in started


def test_update_and_save(tmp_path):
    path = tmp_path / "server.cfg"
    path.write_text(SAMPLE, encoding="utf-8")
    cfg = server_cfg.parse_cfg(str(path))

    server_cfg.set_value(cfg, "sv_hostname", "Renamed Server")
    server_cfg.set_value(cfg, "rcon_password", "hunter2")
    server_cfg.save_cfg(cfg)

    reloaded = server_cfg.parse_cfg(str(path))
    assert server_cfg.get_value(reloaded, "sv_hostname") == "Renamed Server"
    assert server_cfg.get_value(reloaded, "rcon_password") == "hunter2"


def test_all_convars_picks_up_set_directives(tmp_path):
    path = tmp_path / "server.cfg"
    path.write_text(SAMPLE, encoding="utf-8")
    cfg = server_cfg.parse_cfg(str(path))
    convars = server_cfg.all_convars(cfg)
    assert convars.get("onesync") == "on"
    assert "sv_hostname" in convars
