"""
Locale/translation completeness checker for FiveM resources.

Walks each resource's locales/ directory (a common convention for ESX/QBCore-
inspired resources) and reports keys present in one language but missing in
others. Also scans Lua sources for _U(...) / Lang:t(...) calls and reports
keys that are referenced but never defined.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from fivem_utils import find_resources


@dataclass
class LocaleReport:
    resource: str
    languages: list[str]
    missing: dict[str, list[str]]   # lang → keys missing in that lang
    undefined_refs: list[str]       # keys referenced in Lua but not in any locale
    total_keys: int


_KEY_RE = re.compile(r"\[\s*['\"]([^'\"]+)['\"]\s*\]\s*=\s*['\"]")
_DOT_RE = re.compile(r"(\w[\w\.]*)\s*=\s*['\"]")
_USE_RE = re.compile(r"(?:_U|Lang:t|Locale\.t)\s*\(\s*['\"]([^'\"]+)['\"]")


def _parse_locale_file(path: Path) -> set[str]:
    keys: set[str] = set()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return keys

    for m in _KEY_RE.finditer(text):
        keys.add(m.group(1))

    # also handle nested `Locales['en'] = { hello = 'hi' }` style
    # using a permissive line-level regex
    for line in text.splitlines():
        stripped = line.strip()
        if "=" in stripped and stripped.startswith(("['", '["')) is False:
            m = _DOT_RE.match(stripped)
            if m:
                keys.add(m.group(1))
    return keys


def _detect_resources(root: Path):
    """Yield every resource directory under ``root`` that has a locales/ folder."""
    for resource_dir in find_resources(root):
        if (resource_dir / "locales").exists() or (resource_dir / "locale").exists():
            yield resource_dir


def check_resource(resource_dir: Path) -> LocaleReport:
    locales_dir = (resource_dir / "locales") if (resource_dir / "locales").exists() else (resource_dir / "locale")
    files = list(locales_dir.glob("*.lua")) if locales_dir.exists() else []

    keys_by_lang: dict[str, set[str]] = {}
    all_keys: set[str] = set()
    for f in files:
        lang = f.stem
        keys = _parse_locale_file(f)
        keys_by_lang[lang] = keys
        all_keys.update(keys)

    missing: dict[str, list[str]] = {}
    for lang, keys in keys_by_lang.items():
        diff = sorted(all_keys - keys)
        if diff:
            missing[lang] = diff

    # Scan Lua files for usages
    used_keys: set[str] = set()
    for lua_file in resource_dir.rglob("*.lua"):
        if locales_dir in lua_file.parents:
            continue
        try:
            text = lua_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for m in _USE_RE.finditer(text):
            used_keys.add(m.group(1))

    undefined = sorted(used_keys - all_keys)

    return LocaleReport(
        resource=resource_dir.name,
        languages=sorted(keys_by_lang.keys()),
        missing=missing,
        undefined_refs=undefined,
        total_keys=len(all_keys),
    )


def check_resources(resources_path: str) -> list[LocaleReport]:
    return [check_resource(d) for d in _detect_resources(Path(resources_path))]
