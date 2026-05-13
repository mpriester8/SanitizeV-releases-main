"""
Parser & editor helpers for FiveM server.cfg files.

Just enough structure to surface the common convars and ensure/start lines
in a friendly UI without losing the original ordering or comments.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CfgLine:
    raw: str
    kind: str            # 'comment', 'blank', 'directive', 'unknown'
    directive: str = ""  # e.g. 'sv_hostname'
    args: list[str] = field(default_factory=list)


@dataclass
class ParsedCfg:
    path: str
    lines: list[CfgLine]


# Common known convars with friendly descriptions and types.
COMMON_CONVARS: dict[str, dict[str, str]] = {
    "sv_hostname":       {"type": "string", "desc": "Server display name in the FiveM browser"},
    "sv_maxclients":     {"type": "int",    "desc": "Maximum concurrent players (1-128 for FiveM)"},
    "sv_licenseKey":     {"type": "secret", "desc": "Server license key from keymaster.fivem.net"},
    "rcon_password":     {"type": "secret", "desc": "Password for the txAdmin / RCON console"},
    "sv_endpointprivacy":{"type": "bool",   "desc": "Hide your server endpoint from the player list"},
    "onesync":           {"type": "string", "desc": "OneSync mode: 'on' or 'legacy'"},
    "sv_scriptHookAllowed": {"type": "bool", "desc": "Allow Script Hook (single-player mods)"},
    "sv_enforceGameBuild":  {"type": "int",  "desc": "GTA V game build to enforce (e.g., 2802)"},
    "load_server_icon":  {"type": "string", "desc": "Path to a 96x96 PNG to use as server icon"},
    "tags":              {"type": "string", "desc": "Comma-separated tags shown in the server list"},
    "locale":            {"type": "string", "desc": "Server locale (en-US, de-DE, etc.)"},
}


def parse_cfg(path: str) -> ParsedCfg:
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    lines: list[CfgLine] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            lines.append(CfgLine(raw=raw, kind="blank"))
            continue
        if stripped.startswith("#"):
            lines.append(CfgLine(raw=raw, kind="comment"))
            continue

        # Tokenize, respecting double quotes
        tokens = _tokenize(stripped)
        if not tokens:
            lines.append(CfgLine(raw=raw, kind="unknown"))
            continue
        lines.append(CfgLine(raw=raw, kind="directive", directive=tokens[0], args=tokens[1:]))
    return ParsedCfg(path=str(p), lines=lines)


def _tokenize(line: str) -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    in_q = False
    for ch in line:
        if ch == '"':
            in_q = not in_q
            continue
        if ch.isspace() and not in_q:
            if cur:
                out.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        out.append("".join(cur))
    return out


def list_resources(cfg: ParsedCfg) -> list[tuple[str, bool, int]]:
    """Return (name, started, line_index) for each start/ensure directive."""
    found: list[tuple[str, bool, int]] = []
    for i, line in enumerate(cfg.lines):
        if line.kind != "directive":
            continue
        if line.directive.lower() in ("start", "ensure"):
            if line.args:
                found.append((line.args[0], True, i))
        elif line.directive.lower() == "stop":
            if line.args:
                found.append((line.args[0], False, i))
    return found


def get_value(cfg: ParsedCfg, name: str) -> Optional[str]:
    """Return last set value (joined args) for a given convar/directive."""
    value: Optional[str] = None
    for line in cfg.lines:
        if line.kind == "directive" and line.directive.lower() == name.lower():
            value = " ".join(line.args)
    return value


def set_value(cfg: ParsedCfg, name: str, value: str) -> None:
    """Update or append a 'name "value"' directive."""
    quoted = f'"{value}"' if any(c.isspace() for c in value) else value
    found = False
    for line in cfg.lines:
        if line.kind == "directive" and line.directive.lower() == name.lower():
            line.args = [value]
            line.raw = f"{name} {quoted}"
            found = True
    if not found:
        cfg.lines.append(CfgLine(raw=f"{name} {quoted}", kind="directive", directive=name, args=[value]))


def render(cfg: ParsedCfg) -> str:
    return "\n".join(line.raw for line in cfg.lines) + "\n"


def save_cfg(cfg: ParsedCfg, path: Optional[str] = None) -> str:
    target = Path(path or cfg.path)
    target.write_text(render(cfg), encoding="utf-8")
    return str(target)


def all_convars(cfg: ParsedCfg) -> dict[str, str]:
    """Return a dict of {convar: value} (only single-arg `set/setr/sets`)."""
    out: dict[str, str] = {}
    for line in cfg.lines:
        if line.kind != "directive":
            continue
        d = line.directive.lower()
        if d in ("set", "setr", "sets") and len(line.args) >= 2:
            out[line.args[0]] = " ".join(line.args[1:])
        elif d in COMMON_CONVARS and line.args:
            out[line.directive] = " ".join(line.args)
    return out
