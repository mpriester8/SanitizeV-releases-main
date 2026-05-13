"""
Manifest auto-fix actions.

Builds on fivem_utils.validate_manifest by offering safe transforms:
- Add missing fx_version / game (accepts both `game X` and `games { X }`)
- Convert __resource.lua naming to fxmanifest.lua
- Bump fx_version to 'cerulean' (latest stable)
- Remove duplicate dependencies

Edits are applied in place; use version control if you need a safety net.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class FixResult:
    path: str
    success: bool
    changes: list[str]
    error: Optional[str] = None


def auto_fix(resource_path: str, *, write: bool = True) -> FixResult:
    """
    Apply known-safe fixes to a resource's manifest.

    Args:
        resource_path: Resource folder, or a manifest file directly.
        write: When False, returns the diff without saving.
    """
    p = Path(resource_path)
    if p.is_dir():
        manifest = p / "fxmanifest.lua"
        legacy = p / "__resource.lua"
        if not manifest.exists() and legacy.exists():
            manifest = legacy
        if not manifest.exists():
            return FixResult(str(p), False, [], error="No manifest found")
    else:
        manifest = p

    try:
        content = manifest.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return FixResult(str(manifest), False, [], error=f"Failed to read: {e}")

    changes: list[str] = []
    new_content = content

    # 1. Add missing fx_version
    if not re.search(r"(?m)^\s*fx_version\s+", new_content):
        new_content = "fx_version 'cerulean'\n" + new_content
        changes.append("Added missing fx_version 'cerulean'")

    # 2. Add missing game directive — but only if neither `game X` nor
    #    `games { X }` is already present (both are valid FiveM syntax).
    if not re.search(r"(?m)^\s*games?\s+", new_content):
        new_content = "game 'gta5'\n" + new_content
        changes.append("Added missing game 'gta5'")

    # 3. Upgrade old fx_versions
    upgrade_match = re.search(r"(?m)^(\s*fx_version\s+['\"])(adamant|bodacious)(['\"])", new_content)
    if upgrade_match:
        old = upgrade_match.group(2)
        new_content = new_content[:upgrade_match.start(2)] + "cerulean" + new_content[upgrade_match.end(2):]
        changes.append(f"Upgraded fx_version from '{old}' to 'cerulean'")

    # 4. Add lua54 'yes' if missing
    if "lua54" not in new_content:
        new_content = new_content.rstrip() + "\nlua54 'yes'\n"
        changes.append("Enabled Lua 5.4 (lua54 'yes')")

    # 5. De-duplicate dependencies
    new_content, dep_changes = _dedupe_dependencies(new_content)
    changes.extend(dep_changes)

    # 6. Migrate __resource.lua → fxmanifest.lua
    rename_to: Optional[Path] = None
    if manifest.name == "__resource.lua":
        rename_to = manifest.with_name("fxmanifest.lua")
        changes.append("Renamed __resource.lua → fxmanifest.lua")

    if not changes:
        return FixResult(str(manifest), True, [], error="Nothing to fix")

    if write:
        try:
            if rename_to is not None:
                rename_to.write_text(new_content, encoding="utf-8")
                manifest.unlink()
            else:
                manifest.write_text(new_content, encoding="utf-8")
        except Exception as e:
            return FixResult(str(manifest), False, changes, error=f"Failed to write: {e}")

    final_path = str(rename_to or manifest)
    return FixResult(final_path, True, changes)


def _dedupe_dependencies(content: str) -> tuple[str, list[str]]:
    """Remove duplicate names inside dependencies{...} blocks."""
    changes: list[str] = []

    def _process(match: re.Match) -> str:
        block = match.group(2)
        items = re.findall(r"['\"]([^'\"]+)['\"]", block)
        seen: set[str] = set()
        deduped: list[str] = []
        for item in items:
            if item.lower() in seen:
                changes.append(f"Removed duplicate dependency '{item}'")
                continue
            seen.add(item.lower())
            deduped.append(item)
        if len(deduped) == len(items):
            return match.group(0)
        rebuilt = "{\n    " + ",\n    ".join(f"'{d}'" for d in deduped) + "\n}"
        return match.group(1) + rebuilt

    pattern = re.compile(r"(dependenc(?:y|ies)\s*)\{([^}]*)\}", re.DOTALL | re.IGNORECASE)
    new_content = pattern.sub(_process, content)
    return new_content, changes
