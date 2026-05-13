"""
Backup history / snapshots.

Snapshots the FiveM source folder's mods/plugins into a dated, named
directory and lets you diff or restore from any snapshot.
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
class Snapshot:
    id: str
    label: str
    created_at: str
    note: str = ""
    folders: list[str] = field(default_factory=lambda: ["mods", "plugins"])
    file_count: int = 0
    total_bytes: int = 0


def _snapshots_root(backup_dir: str) -> Path:
    return Path(backup_dir) / "_snapshots"


def _index_path(backup_dir: str) -> Path:
    return _snapshots_root(backup_dir) / "index.json"


def load_index(backup_dir: str) -> list[Snapshot]:
    p = _index_path(backup_dir)
    if not p.exists():
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [Snapshot(**s) for s in data]
    except Exception as e:
        logger.warning("Failed to load snapshot index: %s", e)
        return []


def save_index(backup_dir: str, snapshots: list[Snapshot]) -> None:
    p = _index_path(backup_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump([asdict(s) for s in snapshots], f, indent=2)


def create_snapshot(
    source_dir: str,
    backup_dir: str,
    label: str,
    note: str = "",
    folders: Optional[list[str]] = None,
) -> Snapshot:
    folders = folders or ["mods", "plugins"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snap_id = f"{timestamp}_{_safe(label)}"
    snap_root = _snapshots_root(backup_dir) / snap_id
    snap_root.mkdir(parents=True, exist_ok=True)

    file_count = 0
    total_bytes = 0
    for folder in folders:
        src = Path(source_dir) / folder
        if not src.exists():
            continue
        dst = snap_root / folder
        shutil.copytree(src, dst, symlinks=False)
        for f in dst.rglob("*"):
            if f.is_file():
                file_count += 1
                try:
                    total_bytes += f.stat().st_size
                except OSError:
                    pass

    snap = Snapshot(
        id=snap_id,
        label=label,
        created_at=datetime.now().isoformat(timespec="seconds"),
        note=note,
        folders=folders,
        file_count=file_count,
        total_bytes=total_bytes,
    )
    index = load_index(backup_dir)
    index.insert(0, snap)
    save_index(backup_dir, index)
    return snap


def delete_snapshot(backup_dir: str, snap_id: str) -> bool:
    index = load_index(backup_dir)
    remaining = [s for s in index if s.id != snap_id]
    if len(remaining) == len(index):
        return False
    save_index(backup_dir, remaining)
    snap_root = _snapshots_root(backup_dir) / snap_id
    if snap_root.exists():
        shutil.rmtree(snap_root, ignore_errors=True)
    return True


def restore_snapshot(backup_dir: str, snap_id: str, source_dir: str) -> bool:
    snap_root = _snapshots_root(backup_dir) / snap_id
    if not snap_root.exists():
        return False
    index = load_index(backup_dir)
    snap = next((s for s in index if s.id == snap_id), None)
    folders = snap.folders if snap else [p.name for p in snap_root.iterdir() if p.is_dir()]
    for folder in folders:
        dst = Path(source_dir) / folder
        if dst.exists():
            shutil.rmtree(dst)
        src = snap_root / folder
        if src.exists():
            shutil.copytree(src, dst, symlinks=False)
    return True


def diff_snapshots(backup_dir: str, a_id: str, b_id: str) -> dict[str, list[str]]:
    """
    Return {'added': [...], 'removed': [...], 'changed': [...]}
    comparing files in snapshot b versus snapshot a.
    """
    a_root = _snapshots_root(backup_dir) / a_id
    b_root = _snapshots_root(backup_dir) / b_id
    a_files = _walk_relative(a_root)
    b_files = _walk_relative(b_root)

    added = sorted(b_files.keys() - a_files.keys())
    removed = sorted(a_files.keys() - b_files.keys())

    changed: list[str] = []
    for rel in sorted(a_files.keys() & b_files.keys()):
        if a_files[rel] != b_files[rel]:
            changed.append(rel)

    return {"added": added, "removed": removed, "changed": changed}


def _walk_relative(root: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    if not root.exists():
        return out
    for f in root.rglob("*"):
        if f.is_file():
            try:
                out[str(f.relative_to(root)).replace(os.sep, "/")] = f.stat().st_size
            except (OSError, ValueError):
                continue
    return out


def _safe(name: str) -> str:
    keep = [c if c.isalnum() or c in "-_" else "_" for c in name]
    out = "".join(keep).strip("_") or "snapshot"
    return out[:48]


def humanize_bytes(num: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024:
            return f"{num:.1f} {unit}" if unit != "B" else f"{num} B"
        num //= 1024
    return f"{num} PB"
