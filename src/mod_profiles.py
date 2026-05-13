"""
Mod profile manager.

A profile is a named selection of folders/files to keep in the FiveM source
directory. Switching profiles moves the *current* enabled mods into a stash
folder under <backup>/_profiles/<name>/ and moves the requested profile's
contents back into the source directory.

State is stored as JSON next to the backup directory so it survives reboots.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Profile:
    name: str
    description: str = ""
    created_at: str = ""
    last_used: str = ""
    folders: list[str] = field(default_factory=lambda: ["mods", "plugins"])


@dataclass
class ProfileStore:
    backup_dir: str
    profiles: list[Profile] = field(default_factory=list)
    active: Optional[str] = None


def _state_path(backup_dir: str) -> Path:
    return Path(backup_dir) / "_profiles" / "profiles.json"


def _profile_dir(backup_dir: str, name: str) -> Path:
    return Path(backup_dir) / "_profiles" / _safe_name(name)


def _safe_name(name: str) -> str:
    keep = [c if c.isalnum() or c in "-_ " else "_" for c in name]
    out = "".join(keep).strip().replace(" ", "_")
    return out or "profile"


def load_store(backup_dir: str) -> ProfileStore:
    path = _state_path(backup_dir)
    if not path.exists():
        return ProfileStore(backup_dir=backup_dir, profiles=[])
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        profiles = [Profile(**p) for p in data.get("profiles", [])]
        return ProfileStore(
            backup_dir=backup_dir,
            profiles=profiles,
            active=data.get("active"),
        )
    except Exception as e:
        logger.warning("Failed to load profiles: %s", e)
        return ProfileStore(backup_dir=backup_dir, profiles=[])


def save_store(store: ProfileStore) -> None:
    path = _state_path(store.backup_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "active": store.active,
        "profiles": [asdict(p) for p in store.profiles],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def create_profile(store: ProfileStore, name: str, description: str = "", folders: Optional[list[str]] = None) -> Profile:
    if any(p.name.lower() == name.lower() for p in store.profiles):
        raise ValueError(f"Profile '{name}' already exists")
    profile = Profile(
        name=name,
        description=description,
        created_at=datetime.now().isoformat(timespec="seconds"),
        folders=folders or ["mods", "plugins"],
    )
    store.profiles.append(profile)
    save_store(store)
    return profile


def delete_profile(store: ProfileStore, name: str, remove_files: bool = False) -> None:
    store.profiles = [p for p in store.profiles if p.name != name]
    if store.active == name:
        store.active = None
    save_store(store)
    if remove_files:
        target = _profile_dir(store.backup_dir, name)
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)


def capture_current(store: ProfileStore, name: str, source_dir: str) -> None:
    """Snapshot the current source folders into the given profile."""
    profile = _find(store, name)
    if profile is None:
        raise ValueError(f"Profile '{name}' not found")

    target = _profile_dir(store.backup_dir, name)
    target.mkdir(parents=True, exist_ok=True)

    for folder in profile.folders:
        src = Path(source_dir) / folder
        dst = target / folder
        if dst.exists():
            shutil.rmtree(dst)
        if src.exists():
            shutil.copytree(src, dst, symlinks=False)


def activate_profile(store: ProfileStore, name: str, source_dir: str) -> Profile:
    """
    Activate the named profile.

    - Captures the currently active profile's folders back to its stash (so the
      user doesn't lose anything).
    - Removes those folders from source_dir.
    - Copies the requested profile's folders into source_dir.
    """
    new = _find(store, name)
    if new is None:
        raise ValueError(f"Profile '{name}' not found")

    if store.active and store.active != name:
        try:
            capture_current(store, store.active, source_dir)
        except Exception as e:
            logger.warning("Failed to capture old profile %s: %s", store.active, e)

    # Wipe the relevant folders in source dir
    for folder in new.folders:
        src = Path(source_dir) / folder
        if src.exists():
            shutil.rmtree(src)

    # Restore profile contents
    profile_root = _profile_dir(store.backup_dir, name)
    for folder in new.folders:
        src = profile_root / folder
        dst = Path(source_dir) / folder
        if src.exists():
            shutil.copytree(src, dst, symlinks=False)
        else:
            # An empty profile: create an empty folder
            dst.mkdir(parents=True, exist_ok=True)

    new.last_used = datetime.now().isoformat(timespec="seconds")
    store.active = name
    save_store(store)
    return new


def _find(store: ProfileStore, name: str) -> Optional[Profile]:
    for p in store.profiles:
        if p.name == name:
            return p
    return None
