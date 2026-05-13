"""
FiveM development utilities for Sanitize V.

This module provides:
- Manifest validation (fxmanifest.lua / __resource.lua)
- Asset optimization (image compression)
- Conflict detection (duplicate files, overlapping assets)
- Developer utilities (quick commands, snippets)
"""
from __future__ import annotations

import os
import re
import shutil
import hashlib
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, Any
from dataclasses import dataclass, field

try:
    from ymap_binary import parse_binary_ymap_entities, BinaryEntity
except ImportError:
    from src.ymap_binary import parse_binary_ymap_entities, BinaryEntity

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Manifest Validator
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ManifestIssue:
    """Represents an issue found in a manifest file."""
    severity: str  # 'error', 'warning', 'info'
    message: str
    line: int | None = None


@dataclass
class ManifestValidationResult:
    """Result of manifest validation."""
    path: str
    is_valid: bool
    issues: list[ManifestIssue] = field(default_factory=list)
    manifest_type: str = "unknown"  # 'fxmanifest', '__resource', 'none'


# Required fields for fxmanifest.lua
FXMANIFEST_REQUIRED = ["fx_version", "game"]
# Valid fx_version values
VALID_FX_VERSIONS = ["adamant", "bodacious", "cerulean"]
# Valid game values
VALID_GAMES = ["gta5", "rdr3", "common"]

# Common directive patterns
MANIFEST_DIRECTIVES = [
    "client_script", "client_scripts",
    "server_script", "server_scripts",
    "shared_script", "shared_scripts",
    "file", "files",
    "data_file",
    "export", "exports",
    "server_export", "server_exports",
    "dependency", "dependencies",
    "provide", "provides",
    "ui_page",
    "loadscreen",
    "this_is_a_map",
    "resource_manifest_version",
    "author", "description", "version",
]


def validate_manifest(resource_path: str) -> ManifestValidationResult:
    """
    Validate a FiveM resource manifest (fxmanifest.lua or __resource.lua).

    Args:
        resource_path: Path to the resource folder or manifest file.

    Returns:
        ManifestValidationResult with issues found.
    """
    path = Path(resource_path)

    # Determine manifest file
    if path.is_file():
        manifest_path = path
        resource_dir = path.parent
    else:
        resource_dir = path
        fxmanifest = path / "fxmanifest.lua"
        resource_lua = path / "__resource.lua"

        if fxmanifest.exists():
            manifest_path = fxmanifest
        elif resource_lua.exists():
            manifest_path = resource_lua
        else:
            return ManifestValidationResult(
                path=str(path),
                is_valid=False,
                issues=[ManifestIssue("error", "No manifest file found (fxmanifest.lua or __resource.lua)")],
                manifest_type="none"
            )

    issues: list[ManifestIssue] = []
    manifest_type = "fxmanifest" if manifest_path.name == "fxmanifest.lua" else "__resource"

    try:
        content = manifest_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return ManifestValidationResult(
            path=str(manifest_path),
            is_valid=False,
            issues=[ManifestIssue("error", f"Failed to read manifest: {e}")],
            manifest_type=manifest_type
        )

    lines = content.splitlines()

    # Check for required fields (fxmanifest.lua only)
    if manifest_type == "fxmanifest":
        for req in FXMANIFEST_REQUIRED:
            # `game 'gta5'` and `games { 'gta5' }` are both valid declarations.
            if req == "game":
                pattern = r"^\s*games?\s+"
            else:
                pattern = rf"^\s*{req}\s+"
            if not any(re.match(pattern, line) for line in lines):
                issues.append(ManifestIssue("error", f"Missing required field: {req}"))

        # Check fx_version value
        for i, line in enumerate(lines, 1):
            match = re.match(r"^\s*fx_version\s+['\"]?(\w+)['\"]?", line)
            if match:
                version = match.group(1)
                if version not in VALID_FX_VERSIONS:
                    issues.append(ManifestIssue("warning", f"Unknown fx_version '{version}'. Expected one of: {', '.join(VALID_FX_VERSIONS)}", i))

        # Check game value(s) — supports both `game 'gta5'` and `games { 'gta5', 'rdr3' }`
        for i, line in enumerate(lines, 1):
            singular = re.match(r"^\s*game\s+['\"]?(\w+)['\"]?", line)
            if singular:
                value = singular.group(1)
                if value not in VALID_GAMES:
                    issues.append(ManifestIssue("warning", f"Unknown game '{value}'. Expected one of: {', '.join(VALID_GAMES)}", i))
        for m in re.finditer(r"games\s*\{([^}]*)\}", content, re.DOTALL):
            line_no = content[: m.start()].count("\n") + 1
            for token in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)):
                if token not in VALID_GAMES:
                    issues.append(ManifestIssue("warning", f"Unknown game '{token}'. Expected one of: {', '.join(VALID_GAMES)}", line_no))

    # Check for deprecated __resource.lua
    if manifest_type == "__resource":
        issues.append(ManifestIssue("warning", "__resource.lua is deprecated. Consider migrating to fxmanifest.lua"))

    # Check for referenced files that don't exist
    file_patterns = [
        (r"client_scripts?\s*\{([^}]+)\}", "client script"),
        (r"server_scripts?\s*\{([^}]+)\}", "server script"),
        (r"shared_scripts?\s*\{([^}]+)\}", "shared script"),
        (r"files?\s*\{([^}]+)\}", "file"),
    ]

    for pattern, file_type in file_patterns:
        for match in re.finditer(pattern, content, re.DOTALL):
            block = match.group(1)
            # Extract quoted strings
            for file_match in re.finditer(r"['\"]([^'\"]+)['\"]", block):
                filename = file_match.group(1)
                # Skip glob patterns
                if "*" in filename or "@" in filename:
                    continue
                file_path = resource_dir / filename
                if not file_path.exists():
                    issues.append(ManifestIssue("error", f"Referenced {file_type} not found: {filename}"))

    # Check for empty exports
    for i, line in enumerate(lines, 1):
        if re.match(r"^\s*exports?\s*\{\s*\}", line):
            issues.append(ManifestIssue("warning", "Empty exports block", i))
        if re.match(r"^\s*server_exports?\s*\{\s*\}", line):
            issues.append(ManifestIssue("warning", "Empty server_exports block", i))

    # Check for duplicate dependencies
    deps: list[str] = []
    for match in re.finditer(r"dependenc(?:y|ies)\s*\{([^}]+)\}", content, re.DOTALL):
        block = match.group(1)
        for dep_match in re.finditer(r"['\"]([^'\"]+)['\"]", block):
            dep = dep_match.group(1)
            if dep in deps:
                issues.append(ManifestIssue("warning", f"Duplicate dependency: {dep}"))
            deps.append(dep)

    is_valid = not any(i.severity == "error" for i in issues)

    return ManifestValidationResult(
        path=str(manifest_path),
        is_valid=is_valid,
        issues=issues,
        manifest_type=manifest_type
    )


# Directory names to skip when walking a resources tree for nested resources.
# Stops us descending into caches, VCS data, dependency folders, etc.
RESOURCE_SCAN_SKIP_DIRS: frozenset[str] = frozenset({
    "cache", "server-cache", "server-cache-priv",
    "node_modules", "__pycache__", ".git", ".svn", ".hg",
    ".venv", "venv", ".idea", ".vscode", ".github",
    "build", "dist", ".pytest_cache",
    "stream",  # resource asset folder; never contains another resource
})

# How deep to recurse looking for resources. FiveM resources folders never
# nest more than a handful of levels in practice.
RESOURCE_SCAN_MAX_DEPTH = 8


def is_resource_dir(path: Path) -> bool:
    return (path / "fxmanifest.lua").exists() or (path / "__resource.lua").exists()


def find_resources(root: str | Path, max_depth: int = RESOURCE_SCAN_MAX_DEPTH) -> list[Path]:
    """
    Recursively find every FiveM resource under ``root``.

    A resource is any directory containing ``fxmanifest.lua`` or ``__resource.lua``.
    Once a resource directory is found, the walker does NOT descend into it (a
    resource's own subfolders never contain other resources).

    Handles common layouts:
        resources/my_res/                            (flat)
        resources/[esx]/esx_jobs/                    (category folders)
        server-data/resources/[scripts]/[ui]/foo/    (deeply nested categories)
    """
    root = Path(root)
    out: list[Path] = []
    if not root.exists():
        return out

    # The root itself might be a single resource (user pointed at one).
    if is_resource_dir(root):
        return [root]

    def walk(d: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            children = list(d.iterdir())
        except (OSError, PermissionError):
            return
        for child in children:
            if not child.is_dir():
                continue
            name = child.name
            if name.startswith(".") or name in RESOURCE_SCAN_SKIP_DIRS:
                continue
            if is_resource_dir(child):
                out.append(child)
                continue   # Don't descend further; we're inside a resource now.
            walk(child, depth + 1)

    walk(root, 0)
    return sorted(out, key=lambda p: str(p).lower())


def validate_resources_folder(resources_path: str) -> list[ManifestValidationResult]:
    """
    Validate every resource discovered under ``resources_path``.

    Recurses through nested folders (e.g. ``[esx]``, ``[scripts]``, or arbitrary
    grouping directories) so that resources nested several levels deep are still
    found. The walker stops descending the moment it enters a resource itself.
    """
    return [validate_manifest(str(p)) for p in find_resources(resources_path)]


# ─────────────────────────────────────────────────────────────────────────────
# Asset Optimizer
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OptimizationResult:
    """Result of asset optimization."""
    path: str
    original_size: int
    optimized_size: int
    savings_percent: float
    success: bool
    error: str | None = None


def optimize_image(
    image_path: str,
    output_path: str | None = None,
    quality: int = 85,
    max_width: int | None = None,
    max_height: int | None = None
) -> OptimizationResult:
    """
    Optimize an image file (PNG, JPG, etc.).

    Args:
        image_path: Path to the image file.
        output_path: Output path (defaults to overwrite original).
        quality: JPEG quality (1-100).
        max_width: Maximum width (resize if larger).
        max_height: Maximum height (resize if larger).

    Returns:
        OptimizationResult with size savings.
    """
    try:
        from PIL import Image
    except ImportError:
        return OptimizationResult(
            path=image_path,
            original_size=0,
            optimized_size=0,
            savings_percent=0,
            success=False,
            error="Pillow not installed"
        )

    path = Path(image_path)
    if not path.exists():
        return OptimizationResult(
            path=image_path,
            original_size=0,
            optimized_size=0,
            savings_percent=0,
            success=False,
            error="File not found"
        )

    original_size = path.stat().st_size
    output = Path(output_path) if output_path else path

    try:
        with Image.open(path) as img:
            # Resize if needed
            if max_width or max_height:
                w, h = img.size
                new_w, new_h = w, h

                if max_width and w > max_width:
                    ratio = max_width / w
                    new_w = max_width
                    new_h = int(h * ratio)

                if max_height and new_h > max_height:
                    ratio = max_height / new_h
                    new_h = max_height
                    new_w = int(new_w * ratio)

                if (new_w, new_h) != (w, h):
                    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # Determine format
            fmt = img.format or path.suffix.upper().lstrip(".")
            if fmt == "JPG":
                fmt = "JPEG"

            # Save with optimization
            save_kwargs: dict[str, Any] = {"optimize": True}
            if fmt == "JPEG":
                save_kwargs["quality"] = quality
            elif fmt == "PNG":
                save_kwargs["compress_level"] = 9

            # Convert RGBA to RGB for JPEG
            if fmt == "JPEG" and img.mode == "RGBA":
                background = Image.new("RGB", img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background

            img.save(output, format=fmt, **save_kwargs)

        optimized_size = output.stat().st_size
        savings = ((original_size - optimized_size) / original_size * 100) if original_size else 0

        return OptimizationResult(
            path=str(path),
            original_size=original_size,
            optimized_size=optimized_size,
            savings_percent=round(savings, 2),
            success=True
        )

    except Exception as e:
        return OptimizationResult(
            path=image_path,
            original_size=original_size,
            optimized_size=original_size,
            savings_percent=0,
            success=False,
            error=str(e)
        )


def optimize_folder(
    folder_path: str,
    extensions: list[str] | None = None,
    quality: int = 85,
    recursive: bool = True,
    progress_callback: Callable[[int, int], None] | None = None
) -> list[OptimizationResult]:
    """
    Optimize all images in a folder.

    Args:
        folder_path: Path to the folder.
        extensions: File extensions to optimize (default: png, jpg, jpeg).
        quality: JPEG quality.
        recursive: Whether to process subdirectories.
        progress_callback: Callback for progress updates.

    Returns:
        List of OptimizationResult for each file.
    """
    if extensions is None:
        extensions = [".png", ".jpg", ".jpeg", ".webp"]

    path = Path(folder_path)
    if not path.exists():
        return []

    # Collect files
    files: list[Path] = []
    if recursive:
        for ext in extensions:
            files.extend(path.rglob(f"*{ext}"))
    else:
        for ext in extensions:
            files.extend(path.glob(f"*{ext}"))

    results: list[OptimizationResult] = []
    total = len(files)

    for i, file in enumerate(files, 1):
        result = optimize_image(str(file), quality=quality)
        results.append(result)
        if progress_callback:
            progress_callback(i, total)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Conflict Detector
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FileConflict:
    """Represents a file conflict."""
    filename: str
    locations: list[str]
    conflict_type: str  # 'duplicate', 'hash_mismatch', 'name_collision'


@dataclass
class ConflictReport:
    """Report of detected conflicts."""
    duplicates: list[FileConflict]
    name_collisions: list[FileConflict]
    ymap_duplicates: list[FileConflict]
    total_issues: int


def _get_file_hash(path: Path) -> str:
    """Calculate MD5 hash of a file using chunked reading to save memory."""
    hasher = hashlib.md5()
    with open(path, "rb") as f:
        # Read in 8KB chunks
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def detect_conflicts(
    resources_path: str,
    check_hashes: bool = True,
    progress_callback: Callable[[str], None] | None = None,
    max_file_size_mb: int = 50
) -> ConflictReport:
    """
    Detect file conflicts in resources folder, focusing on ymap files.

    Args:
        resources_path: Path to the resources folder.
        check_hashes: Whether to check file hashes for true duplicates.
        progress_callback: Optional callback with current file path.
        max_file_size_mb: Maximum file size to hash (default 50MB, skip larger files).

    Returns:
        ConflictReport with detected issues.
    """
    path = Path(resources_path)
    if not path.exists():
        return ConflictReport(duplicates=[], name_collisions=[], ymap_duplicates=[], total_issues=0)

    # Files to ignore - these are expected to exist in every resource
    IGNORED_FILES = {
        "fxmanifest.lua",
        "__resource.lua",
        "stream.ini",
        ".gitignore",
        ".gitkeep",
        "readme.md",
        "readme.txt",
        "license",
        "license.md",
        "license.txt",
    }

    # File extensions to focus on (ymap files are the primary concern)
    YMAP_EXTENSIONS = {".ymap", ".ymap.xml"}
    max_file_bytes = max_file_size_mb * 1024 * 1024
    
    # Directories to skip entirely (must match exactly as path component)
    SKIP_DIRS = {
        "cache", "server-cache", "server-cache-priv",  # FiveM cache folders
        "__pycache__", ".git", ".svn", ".venv", "node_modules",  # Dev folders
        "build", "dist", ".pytest_cache",  # Build artifacts
        ".github", ".vscode", ".idea"  # Editor/IDE folders
    }

    # Track files by name and hash
    files_by_name: dict[str, list[str]] = {}
    files_by_hash: dict[str, list[str]] = {}
    file_hashes: dict[str, str] = {}  # Cache hashes to avoid recalculating

    # Track files by size for optimization (only hash if size is shared)
    files_by_size: dict[int, list[tuple[Path, str]]] = {}

    # Scan all files - First pass (Metadata only)
    for i, file in enumerate(path.rglob("*"), 1):
        if file.is_file():
            # Skip files in cache or build directories - check all parent parts
            skip_file = False
            for part in file.parts:
                if part in SKIP_DIRS:
                    skip_file = True
                    break
            if skip_file:
                continue
            
            if progress_callback and i % 200 == 1:
                try:
                    progress_callback(str(file))
                except Exception:
                    pass
                
            name = file.name.lower()

            # Skip ignored manifest and common files
            if name in IGNORED_FILES:
                continue

            rel_path = str(file.relative_to(path))

            # Track by name
            if name not in files_by_name:
                files_by_name[name] = []
            files_by_name[name].append(rel_path)

            # Track by size (for optimized hashing)
            if check_hashes:
                try:
                    file_size = file.stat().st_size
                    if file_size <= max_file_bytes:
                        if file_size not in files_by_size:
                            files_by_size[file_size] = []
                        files_by_size[file_size].append((file, rel_path))
                except OSError:
                    pass  # Skip if we can't get size

    # Calculate hashes - Second pass (Only for potential duplicates)
    if check_hashes:
        for size, file_list in files_by_size.items():
            # Only hash if multiple files share the same size
            if len(file_list) > 1:
                for file, rel_path in file_list:
                    try:
                        if progress_callback:
                            try:
                                progress_callback(str(file))
                            except Exception:
                                pass

                        # Read file in chunks to avoid loading entire file into memory
                        hasher = hashlib.md5()
                        with file.open('rb') as f:
                            while chunk := f.read(8192):  # 8KB chunks
                                hasher.update(chunk)
                        file_hash = hasher.hexdigest()
                        file_hashes[rel_path] = file_hash
                        if file_hash not in files_by_hash:
                            files_by_hash[file_hash] = []
                        files_by_hash[file_hash].append(rel_path)
                    except OSError as e:
                        logger.warning("Error hashing file %s: %s", rel_path, e)
                    except Exception as e:
                        logger.exception("Unexpected error hashing file %s: %s", rel_path, e)

    # Find duplicates (same hash, different locations)
    duplicates: list[FileConflict] = []
    ymap_duplicates: list[FileConflict] = []

    if check_hashes:
        for hash_val, locations in files_by_hash.items():
            if len(locations) > 1:
                # Get all unique filenames for this hash
                unique_filenames = set(Path(loc).name for loc in locations)
                
                # Use a descriptive label if multiple different filenames share the same content
                if len(unique_filenames) > 1:
                    filename = f"{len(unique_filenames)} files with identical content"
                else:
                    filename = Path(locations[0]).name
                
                conflict = FileConflict(
                    filename=filename,
                    locations=locations,
                    conflict_type="duplicate"
                )

                # Categorize YMAP duplicates separately
                first_filename = Path(locations[0]).name
                is_ymap = any(first_filename.lower().endswith(ext) for ext in YMAP_EXTENSIONS)
                if is_ymap:
                    ymap_duplicates.append(conflict)
                else:
                    duplicates.append(conflict)

    # Find name collisions (same name, different content) - focus on ymaps
    name_collisions: list[FileConflict] = []
    for name, locations in files_by_name.items():
        if len(locations) > 1:
            # Only report name collisions for ymap files (primary concern)
            is_ymap = any(name.endswith(ext) for ext in YMAP_EXTENSIONS)
            if not is_ymap:
                continue

            # Skip if they're true duplicates (same hash) - use cached hashes
            is_true_duplicate = False
            if check_hashes:
                hashes = set()
                for loc in locations:
                    if loc in file_hashes:
                        hashes.add(file_hashes[loc])
                if len(hashes) == 1:
                    is_true_duplicate = True

            if not is_true_duplicate:
                name_collisions.append(FileConflict(
                    filename=name,
                    locations=locations,
                    conflict_type="name_collision"
                ))

    total_issues = len(duplicates) + len(name_collisions) + len(ymap_duplicates)

    return ConflictReport(
        duplicates=duplicates,
        name_collisions=name_collisions,
        ymap_duplicates=ymap_duplicates,
        total_issues=total_issues
    )


# ─────────────────────────────────────────────────────────────────────────────
# YMAP Conflict Fixer
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class YmapFixResult:
    """Result of a YMAP conflict fix operation."""
    fixed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _entity_key(item: ET.Element) -> tuple[str, str, str, str] | None:
    """
    Build a deduplication key for a CEntityDef <Item> element.

    The key is (archetypeName, rounded_x, rounded_y, rounded_z) so that
    entities placed at the same world position with the same archetype are
    treated as duplicates regardless of which resource they come from.
    Returns None if the element cannot be keyed.
    """
    arch = item.findtext("archetypeName")
    if arch is None:
        return None
    pos = item.find("position")
    if pos is None:
        return None
    try:
        # Round to 2 decimal places (~1 cm) to tolerate floating-point jitter
        x = f"{float(pos.get('x', '0')):.2f}"
        y = f"{float(pos.get('y', '0')):.2f}"
        z = f"{float(pos.get('z', '0')):.2f}"
    except (ValueError, TypeError):
        return None
    return (arch.strip().lower(), x, y, z)


def deduplicate_ymap_xml_entities(
    primary_path: Path,
    secondary_path: Path,
    output_path: Path,
    log_callback: Callable[[str], None] | None = None,
) -> tuple[bool, int]:
    """
    Resolve a .ymap.xml name collision by:
      1. Finding entities in *secondary_path* that are NOT in *primary_path*
         (unique to the secondary, matched by archetypeName + world position).
      2. Appending those unique entities to *primary_path*'s entity list.
      3. Writing the merged primary to *output_path*.

    The secondary file should be deleted by the caller after a successful
    return — removing it resolves the streaming name collision in FiveM/GTA V.

    Args:
        primary_path:   The file that will be kept; unique secondary entities
                        are added into it.
        secondary_path: The file that will be removed by the caller; its
                        unique entities are saved into the primary first.
        output_path:    Destination for the updated primary (may equal
                        primary_path).
        log_callback:   Optional per-message log callable.

    Returns:
        (success, merged_count) where merged_count is the number of unique
        entities copied from secondary into primary (0 means the secondary had
        no entities that weren't already in the primary).
    """
    def log(msg: str) -> None:
        logger.info(msg)
        if log_callback:
            try:
                log_callback(msg)
            except Exception:
                pass

    try:
        primary_tree = ET.parse(str(primary_path))
        primary_root = primary_tree.getroot()
    except ET.ParseError as e:
        log(f"[ERROR] Cannot parse {primary_path.name}: {e}")
        return False, 0

    try:
        secondary_tree = ET.parse(str(secondary_path))
        secondary_root = secondary_tree.getroot()
    except ET.ParseError as e:
        log(f"[ERROR] Cannot parse {secondary_path.name}: {e}")
        return False, 0

    # Build a set of entity keys already present in the primary
    primary_keys: set[tuple[str, str, str, str]] = set()
    primary_entities = primary_root.find("entities")
    if primary_entities is not None:
        for item in primary_entities:
            key = _entity_key(item)
            if key is not None:
                primary_keys.add(key)

    # Collect entities from secondary that do NOT exist in primary
    secondary_entities = secondary_root.find("entities")
    unique_to_secondary: list[ET.Element] = []
    if secondary_entities is not None:
        for item in secondary_entities:
            key = _entity_key(item)
            if key is None or key not in primary_keys:
                arch = item.findtext("archetypeName", "?")
                pos = item.find("position")
                pos_str = (
                    f"({pos.get('x','?')}, {pos.get('y','?')}, {pos.get('z','?')})"
                    if pos is not None else ""
                )
                log(f"  [UNIQUE] Keeping entity '{arch}' at {pos_str} from {secondary_path.name}")
                unique_to_secondary.append(item)
            else:
                arch = item.findtext("archetypeName", "?")
                log(f"  [DUP] Discarding duplicate entity '{arch}' — already in {primary_path.name}")

    merged = len(unique_to_secondary)

    # Append unique secondary entities into the primary's entity list
    if unique_to_secondary:
        if primary_entities is None:
            primary_entities = ET.SubElement(primary_root, "entities")
        for item in unique_to_secondary:
            primary_entities.append(item)

    # Recalculate extents to cover all entities now in the primary
    _recalc_extents(primary_root)

    try:
        try:
            ET.indent(primary_tree, space="  ")
        except AttributeError:
            pass  # Python < 3.9
        primary_tree.write(str(output_path), encoding="unicode", xml_declaration=True)
        return True, merged
    except OSError as e:
        log(f"[ERROR] Cannot write merged file to {output_path}: {e}")
        return False, 0


def _recalc_extents(root: ET.Element) -> None:
    """
    Recompute entitiesExtentsMin/Max and streamingExtentsMin/Max from the
    position attributes of surviving <Item> elements.

    This is a best-effort approximation — it does not apply archetypeRadius or
    lodDist, but it prevents the extents from pointing at removed entities.
    """
    entities = root.find("entities")
    if entities is None:
        return

    xs, ys, zs = [], [], []
    for item in entities:
        pos = item.find("position")
        if pos is None:
            continue
        try:
            xs.append(float(pos.get("x", "0")))
            ys.append(float(pos.get("y", "0")))
            zs.append(float(pos.get("z", "0")))
        except (ValueError, TypeError):
            pass

    if not xs:
        return

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    # Add a small buffer so the extents encompass each entity's immediate volume
    pad = 5.0

    def _set_vec(tag: str, x: float, y: float, z: float) -> None:
        elem = root.find(tag)
        if elem is not None:
            elem.set("x", f"{x:.6f}")
            elem.set("y", f"{y:.6f}")
            elem.set("z", f"{z:.6f}")

    _set_vec("entitiesExtentsMin", min_x - pad, min_y - pad, min_z - pad)
    _set_vec("entitiesExtentsMax", max_x + pad, max_y + pad, max_z + pad)
    _set_vec("streamingExtentsMin", min_x - pad * 10, min_y - pad * 10, min_z - pad * 10)
    _set_vec("streamingExtentsMax", max_x + pad * 10, max_y + pad * 10, max_z + pad * 10)


def fix_ymap_conflicts(
    report: ConflictReport,
    resources_path: str,
    log_callback: Callable[[str], None] | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> YmapFixResult:
    """
    Attempt to automatically fix YMAP conflicts from a ConflictReport.

    Behaviour by conflict type:

    - **Duplicate YMAPs** (identical content, multiple locations):
      All copies except the alphabetically-first path are deleted.

    - **YMAP name collisions — .ymap.xml** (same filename, different content):
      For each collision group, one file is chosen as primary (alphabetically
      first). Any entities unique to each secondary file are absorbed into
      the primary; entities already present in the primary at the same
      position + archetypeName are discarded. The secondary file is then
      deleted, eliminating the streaming name conflict. Extents are
      recalculated on the merged primary. .bak backups are written first.

    - **YMAP name collisions — binary .ymap**:
      Skipped. Binary files require CodeWalker for entity-level editing.

    A ``.bak`` backup is written alongside every file that is modified or
    deleted before the change is applied.

    Args:
        report: A ConflictReport produced by ``detect_conflicts()``.
        resources_path: Absolute path to the resources root used during scan.
        log_callback: Optional per-action log callback.
        progress_callback: Optional callback called with the current file path.

    Returns:
        YmapFixResult summarising fixed, skipped, and errored items.
    """
    result = YmapFixResult()
    base = Path(resources_path)

    def log(msg: str) -> None:
        logger.info(msg)
        if log_callback:
            try:
                log_callback(msg)
            except Exception:
                pass

    def _report_progress(path: str) -> None:
        if progress_callback:
            try:
                progress_callback(path)
            except Exception:
                pass

    def _backup(path: Path) -> bool:
        """Write a .bak copy next to *path*. Returns True on success."""
        bak = path.with_suffix(path.suffix + ".bak")
        try:
            shutil.copy2(str(path), str(bak))
            return True
        except OSError as e:
            log(f"[WARN] Could not back up {path.name}: {e}")
            return False

    # ── Fix 1: Duplicate YMAPs (same hash) ───────────────────────────────────
    for conflict in report.ymap_duplicates:
        locations = sorted(conflict.locations)
        keep_rel = locations[0]
        for rel_path in locations[1:]:
            full_path = base / rel_path
            if not full_path.exists():
                log(f"[SKIP] Already gone: {rel_path}")
                result.skipped.append(rel_path)
                continue
            _backup(full_path)
            try:
                full_path.unlink()
                log(f"[OK] Removed duplicate YMAP: {rel_path}  (kept {keep_rel})")
                result.fixed.append(f"Removed duplicate: {rel_path}")
            except OSError as e:
                log(f"[ERROR] Could not remove {rel_path}: {e}")
                result.errors.append(f"{rel_path}: {e}")
        _report_progress(keep_rel)

    # ── Fix 2: YMAP name collisions (different content, same name) ────────────
    for conflict in report.name_collisions:
        locations = sorted(conflict.locations)
        filename = conflict.filename

        if not filename.lower().endswith(".ymap.xml"):
            # ── Binary .ymap: entity-aware fix ────────────────────────────────
            # Binary .ymap files use the RSC7/Meta format.  A true merge would
            # require rebuilding the entire RSC7 binary (pointer fixup, page
            # re-allocation) — equivalent to CodeWalker's MetaBuilder.
            # Additionally, archetype names are stored only as Jenkins hashes
            # in the binary, so we cannot convert entities to .ymap.xml without
            # the original string table.
            #
            # Strategy:
            #   • If the secondary is a TRUE DUPLICATE (no unique entities)
            #     → delete it safely; nothing is lost.
            #   • If the secondary has UNIQUE ENTITIES the primary lacks
            #     → skip auto-fix; log exactly which hashes/positions need
            #       manual merging in CodeWalker so the user has a concrete
            #       action list.

            # Parse entity data from all copies.
            parsed: dict[str, list[BinaryEntity]] = {}
            for loc in locations:
                ents = parse_binary_ymap_entities(base / loc)
                if ents is not None:
                    parsed[loc] = ents

            all_parsed = len(parsed) == len(locations)

            # Choose the copy with the most entities as primary.
            if all_parsed and parsed:
                primary_rel = max(parsed, key=lambda l: len(parsed[l]))
            else:
                primary_rel = locations[0]

            secondaries = [l for l in locations if l != primary_rel]
            primary_keys: set[tuple] = {
                e.key() for e in parsed.get(primary_rel, [])
            }

            log(
                f"[INFO] Primary: {primary_rel}  "
                f"({len(parsed.get(primary_rel, []))} entities)"
                if all_parsed else
                f"[INFO] Primary (parse failed, using first): {primary_rel}"
            )

            for secondary_rel in secondaries:
                secondary_path = base / secondary_rel
                if not secondary_path.exists():
                    log(f"[SKIP] Already gone: {secondary_rel}")
                    result.skipped.append(secondary_rel)
                    continue

                sec_entities = parsed.get(secondary_rel, [])
                unique_to_secondary = [
                    e for e in sec_entities if e.key() not in primary_keys
                ]

                if not all_parsed:
                    # Could not parse one or both files — skip to avoid silent loss.
                    log(
                        f"[SKIP] {secondary_rel}  "
                        f"(parse failed — open both files in CodeWalker to merge manually)"
                    )
                    result.skipped.append(
                        f"{secondary_rel} (binary parse failed — merge manually in CodeWalker)"
                    )

                elif unique_to_secondary:
                    # Has unique content → cannot safely auto-merge binary format.
                    log(
                        f"[SKIP] {secondary_rel}  "
                        f"has {len(unique_to_secondary)} unique entity/entities "
                        f"not present in {primary_rel} — manual CodeWalker merge required:"
                    )
                    for e in unique_to_secondary:
                        log(
                            f"         archetype hash 0x{e.archetype_hash:08X}  "
                            f"pos ({e.x:.2f}, {e.y:.2f}, {e.z:.2f})"
                        )
                    result.skipped.append(
                        f"{secondary_rel} — {len(unique_to_secondary)} unique entities "
                        f"need manual CodeWalker merge into {primary_rel}"
                    )

                else:
                    # True duplicate: every entity in secondary exists in primary.
                    _backup(secondary_path)
                    try:
                        secondary_path.unlink()
                        log(
                            f"[OK] Deleted {secondary_rel}  "
                            f"(true duplicate — all {len(sec_entities)} "
                            f"entities present in {primary_rel}; .bak saved)"
                        )
                        result.fixed.append(
                            f"Deleted {secondary_rel} — true duplicate of {primary_rel} "
                            f"({len(sec_entities)} entities, none lost)"
                        )
                    except OSError as e:
                        log(f"[ERROR] Could not delete {secondary_rel}: {e}")
                        result.errors.append(f"Delete failed: {secondary_rel}: {e}")

            _report_progress(primary_rel)
            continue

        # ── .ymap.xml: merge unique entities into primary, delete secondary ───
        primary_rel = locations[0]
        primary_path = base / primary_rel
        if not primary_path.exists():
            log(f"[ERROR] Primary file missing: {primary_rel}")
            result.errors.append(f"Primary missing: {primary_rel}")
            continue

        for secondary_rel in locations[1:]:
            secondary_path = base / secondary_rel
            if not secondary_path.exists():
                log(f"[SKIP] Secondary already gone: {secondary_rel}")
                result.skipped.append(secondary_rel)
                continue

            # Backup both files before any modification
            _backup(primary_path)
            _backup(secondary_path)

            log(
                f"[MERGE] Absorbing unique entities from {secondary_rel} "
                f"into {primary_rel}, then deleting {secondary_rel}"
            )
            ok, merged = deduplicate_ymap_xml_entities(
                primary_path, secondary_path, primary_path,
                log_callback=log_callback,
            )
            if ok:
                try:
                    secondary_path.unlink()
                    log(
                        f"[OK] Merged {merged} unique entity/entities from "
                        f"{secondary_rel} into {primary_rel} and removed {secondary_rel}"
                    )
                    result.fixed.append(
                        f"Merged {merged} unique entities from {secondary_rel} "
                        f"into {primary_rel}"
                    )
                except OSError as e:
                    log(f"[ERROR] Could not delete {secondary_rel} after merge: {e}")
                    result.errors.append(f"Delete failed after merge: {secondary_rel}: {e}")
            else:
                log(f"[ERROR] Merge failed for {secondary_rel} — no files were changed")
                result.errors.append(f"Merge failed: {secondary_rel}")

        _report_progress(primary_rel)

    return result



# ─────────────────────────────────────────────────────────────────────────────
# Server Command Scanner
# ─────────────────────────────────────────────────────────────────────────────

def _clean_command_name(raw_name: str) -> str:
    """
    Clean a command name by removing common prefixes and normalizing format.
    
    Handles patterns like:
    - /-helicam_lock -> helicam_lock
    - /_interact_Heli_Cam -> interact_Heli_Cam  
    - /0r-weaponReality:X -> weaponReality:X
    - __internal -> (skip)
    
    But preserves names like:
    - 911 -> 911 (emergency command)
    - 911e -> 911e
    """
    # Only strip if the name starts with clear "garbage" prefixes like -_, 0r-, etc.
    # Pattern: strip leading combos of -, _, /, and numbers ONLY if followed by - or _
    # This keeps "911" and "911e" but strips "0r-weapon" to "weapon"
    
    # First, strip leading slashes
    cleaned = raw_name.lstrip('/')
    
    # Strip patterns like "0r-", "-", "_" at the start (prefix garbage)
    # But keep pure numeric commands like "911"
    cleaned = re.sub(r'^[0-9]*[\-_]+', '', cleaned)
    
    # If that made it empty or it's just numbers, use original (minus slash)
    if not cleaned:
        cleaned = raw_name.lstrip('/')
    
    return cleaned


@dataclass
class ServerCommand:
    """Represents a discovered server command."""
    name: str
    description: str
    source_file: str
    line_number: int
    framework: str  # 'native', 'esx', 'qbcore', 'chat_suggestion', 'other'
    restricted: bool = False
    permissions: str = "Everyone"  # 'Everyone', 'Admin', 'Superadmin', 'Job: X', 'ACE: X', etc.


@dataclass
class CommandScanResult:
    """Result of scanning server files for commands."""
    commands: list[ServerCommand]
    files_scanned: int
    errors: list[str]


def scan_server_commands(server_path: str) -> CommandScanResult:
    """
    Scan FiveM server files for registered commands.

    Detects:
    - RegisterCommand() - Native FiveM
    - ESX.RegisterCommand() - ESX Framework
    - QBCore.Commands.Add() - QBCore Framework
    - chat:addSuggestion events - Chat suggestions

    Args:
        server_path: Path to server-data or resources folder.

    Returns:
        CommandScanResult with discovered commands.
    """
    path = Path(server_path)
    if not path.exists():
        return CommandScanResult(commands=[], files_scanned=0, errors=["Path does not exist"])

    commands: list[ServerCommand] = []
    errors: list[str] = []
    files_scanned = 0

    # Regex patterns for different command registration methods
    patterns = {
        # RegisterCommand("name", function(source, args, rawCommand)
        "native": re.compile(
            r'RegisterCommand\s*\(\s*["\']([^"\']+)["\']',
            re.IGNORECASE
        ),
        # ESX.RegisterCommand("name", "group", function(xPlayer, args, showError)
        "esx": re.compile(
            r'ESX\.RegisterCommand\s*\(\s*["\']([^"\']+)["\'](?:\s*,\s*["\']([^"\']*)["\'])?',
            re.IGNORECASE
        ),
        # QBCore.Commands.Add("name", "description", {...}, restricted, function(source, args)
        "qbcore": re.compile(
            r'QBCore\.Commands\.Add\s*\(\s*["\']([^"\']+)["\'](?:\s*,\s*["\']([^"\']*)["\'])?',
            re.IGNORECASE
        ),
        # TriggerEvent('chat:addSuggestion', '/command', 'description'
        "chat_suggestion": re.compile(
            r'TriggerEvent\s*\(\s*["\']chat:addSuggestion["\']\s*,\s*["\']/?([^"\']+)["\'](?:\s*,\s*["\']([^"\']*)["\'])?',
            re.IGNORECASE
        ),
        # exports['chat']:addSuggestion
        "chat_export": re.compile(
            r'exports\s*\[\s*["\']chat["\']\s*\]\s*:\s*addSuggestion\s*\(\s*["\']/?([^"\']+)["\'](?:\s*,\s*["\']([^"\']*)["\'])?',
            re.IGNORECASE
        ),
    }

    # Scan all Lua files
    lua_files = list(path.rglob("*.lua"))

    for lua_file in lua_files:
        try:
            content = lua_file.read_text(encoding="utf-8", errors="ignore")
            rel_path = str(lua_file.relative_to(path))
            files_scanned += 1
            
            content_lines = content.splitlines()

            for line_num, line in enumerate(content_lines, 1):
                # Skip comments
                stripped = line.strip()
                if stripped.startswith("--"):
                    continue

                # Check each pattern
                for framework, pattern in patterns.items():
                    for match in pattern.finditer(line):
                        raw_cmd_name = match.group(1)
                        
                        # Clean up command name - remove all leading non-letter characters
                        cmd_name = _clean_command_name(raw_cmd_name)
                        
                        # Skip empty or internal commands
                        if not cmd_name or cmd_name.startswith("__"):
                            continue
                        
                        description = match.group(2) if match.lastindex and match.lastindex >= 2 else ""

                        # Clean up description
                        if description is None:
                            description = ""

                        # Try to extract description from nearby comments if none found
                        if not description:
                            description = _extract_command_description(content_lines, line_num - 1, cmd_name)

                        # Determine permissions from framework-specific patterns
                        restricted = False
                        permissions = "Everyone"
                        
                        # ESX group check (second parameter is the permission group)
                        if framework == "esx" and match.lastindex and match.lastindex >= 2:
                            group = match.group(2)
                            if group:
                                group_lower = group.lower()
                                if group_lower in ["admin", "superadmin", "mod", "moderator"]:
                                    restricted = True
                                    permissions = group.title()
                                elif group_lower.startswith("job."):
                                    permissions = f"Job: {group[4:]}"
                                elif group_lower != "user":
                                    permissions = group.title()
                        
                        # Check for ACE permissions in native RegisterCommand
                        # ACE = Access Control Entry (FiveM's built-in permission system)
                        if framework == "native":
                            # Look for restricted=true parameter
                            if re.search(r',\s*true\s*\)', line, re.IGNORECASE):
                                restricted = True
                                permissions = "ACE (Server Permission)"
                            # Try to find ACE permission name nearby
                            ace_match = re.search(r'IsPlayerAceAllowed.*["\']([^"\'\.]+)["\']', content)
                            if ace_match:
                                permissions = f"ACE: {ace_match.group(1)}"
                                restricted = True
                        
                        # QBCore permission check
                        if framework == "qbcore":
                            # QBCore.Commands.Add has restricted parameter
                            if re.search(r',\s*true\s*,\s*function', line, re.IGNORECASE):
                                restricted = True
                                permissions = "Admin"

                        # Generate a default description based on command name if still empty
                        if not description:
                            description = _generate_command_description(cmd_name, framework)

                        commands.append(ServerCommand(
                            name=cmd_name,
                            description=description.strip(),
                            source_file=rel_path,
                            line_number=line_num,
                            framework=framework if framework != "chat_export" else "chat_suggestion",
                            restricted=restricted,
                            permissions=permissions
                        ))

        except Exception as e:
            errors.append(f"{lua_file.name}: {e}")

    # Remove duplicates (same command name), keeping first occurrence
    seen: dict[str, ServerCommand] = {}
    for cmd in commands:
        key = cmd.name.lower()
        if key not in seen:
            seen[key] = cmd

    unique_commands = sorted(seen.values(), key=lambda c: c.name.lower())

    return CommandScanResult(
        commands=unique_commands,
        files_scanned=files_scanned,
        errors=errors
    )


def _extract_command_description(lines: list[str], cmd_line_idx: int, cmd_name: str) -> str:
    """Try to extract a description from comments near the command registration."""
    # Bounds check
    if cmd_line_idx < 0 or cmd_line_idx >= len(lines):
        return ""
    
    # Look at the line before for a comment
    if cmd_line_idx > 0:
        prev_line = lines[cmd_line_idx - 1].strip()
        if prev_line.startswith("--"):
            comment = prev_line.lstrip("-").strip()
            # Skip generic comments
            if comment and not comment.lower().startswith(("todo", "fixme", "hack", "note:")):
                return comment
    
    # Look at the same line for an inline comment
    current_line = lines[cmd_line_idx]
    if "--" in current_line:
        comment_start = current_line.find("--")
        comment = current_line[comment_start + 2:].strip()
        if comment:
            return comment
    
    # Look 2 lines before for block comments
    if cmd_line_idx > 1:
        prev_line = lines[cmd_line_idx - 2].strip()
        if prev_line.startswith("--"):
            comment = prev_line.lstrip("-").strip()
            if comment and not comment.lower().startswith(("todo", "fixme", "hack")):
                return comment
    
    return ""


def _generate_command_description(cmd_name: str, framework: str) -> str:
    """Generate a descriptive label based on command name patterns."""
    name_lower = cmd_name.lower()
    
    # Common command patterns and their descriptions
    patterns = {
        # Player actions
        "spawn": "Spawn player or entity",
        "tp": "Teleport player",
        "teleport": "Teleport to location",
        "goto": "Go to player or location",
        "bring": "Bring player to you",
        "heal": "Heal player",
        "revive": "Revive player",
        "kill": "Kill player",
        "kick": "Kick player from server",
        "ban": "Ban player",
        "unban": "Unban player",
        "warn": "Warn player",
        "freeze": "Freeze player",
        "unfreeze": "Unfreeze player",
        "spectate": "Spectate player",
        "noclip": "Toggle noclip mode",
        "god": "Toggle god mode",
        "invisible": "Toggle invisibility",
        "invis": "Toggle invisibility",
        
        # Vehicle
        "car": "Spawn vehicle",
        "vehicle": "Spawn or manage vehicle",
        "veh": "Spawn vehicle",
        "dv": "Delete vehicle",
        "deletevehicle": "Delete vehicle",
        "repair": "Repair vehicle",
        "fix": "Fix/repair vehicle",
        "wash": "Wash vehicle",
        "flip": "Flip vehicle",
        "tune": "Tune vehicle",
        "mods": "Vehicle modifications",
        
        # Inventory/Items
        "give": "Give item to player",
        "giveitem": "Give item to player",
        "additem": "Add item to inventory",
        "removeitem": "Remove item from inventory",
        "clearinventory": "Clear inventory",
        "setmoney": "Set player money",
        "addmoney": "Add money to player",
        "removemoney": "Remove money from player",
        
        # Admin/Staff
        "admin": "Admin menu or toggle",
        "staff": "Staff menu or toggle",
        "mod": "Moderator command",
        "announce": "Server announcement",
        "broadcast": "Broadcast message",
        "say": "Server message",
        "restart": "Restart resource",
        "refresh": "Refresh resources",
        "stop": "Stop resource",
        "start": "Start resource",
        
        # Jobs/Economy
        "job": "Job related command",
        "setjob": "Set player job",
        "duty": "Toggle duty status",
        "onduty": "Go on duty",
        "offduty": "Go off duty",
        "clock": "Clock in/out",
        
        # Misc
        "help": "Display help",
        "menu": "Open menu",
        "settings": "Open settings",
        "coords": "Show coordinates",
        "pos": "Show position",
        "id": "Show player ID",
        "report": "Report player/issue",
        "ooc": "Out of character chat",
        "me": "Action/emote message",
        "do": "Environment action",
        "tweet": "Send tweet",
    }
    
    # Check for exact matches
    if name_lower in patterns:
        return patterns[name_lower]
    
    # Check for partial matches
    for key, desc in patterns.items():
        if key in name_lower or name_lower in key:
            return desc
    
    # Framework-specific defaults
    if framework == "esx":
        return "ESX framework command"
    elif framework == "qbcore":
        return "QBCore framework command"
    elif framework == "chat_suggestion":
        return "Chat command"
    
    return "Server command"


# ─────────────────────────────────────────────────────────────────────────────
# Developer Utilities / Quick Commands
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class QuickCommand:
    """A quick command for FiveM development."""
    name: str
    description: str
    command: str
    category: str = "general"


# Common FiveM server commands
QUICK_COMMANDS: list[QuickCommand] = [
    QuickCommand("Restart Resource", "Restart a specific resource", "restart {resource}", "resources"),
    QuickCommand("Refresh Resources", "Refresh the resource list", "refresh", "resources"),
    QuickCommand("Start Resource", "Start a resource", "start {resource}", "resources"),
    QuickCommand("Stop Resource", "Stop a resource", "stop {resource}", "resources"),
    QuickCommand("Ensure Resource", "Ensure a resource is started", "ensure {resource}", "resources"),

    QuickCommand("Kick Player", "Kick a player by ID", "kick {id} {reason}", "players"),
    QuickCommand("Ban Player", "Ban a player by ID", "ban {id} {reason}", "players"),
    QuickCommand("Unban Player", "Unban a player by identifier", "unban {identifier}", "players"),

    QuickCommand("Set Routing Bucket", "Set player routing bucket", "setroutingbucket {id} {bucket}", "advanced"),
    QuickCommand("Execute SQL", "Execute SQL via txAdmin", "txasql {query}", "advanced"),

    QuickCommand("Server Status", "Show server status", "status", "info"),
    QuickCommand("Player Count", "Show current players", "players", "info"),
    QuickCommand("Resources List", "List loaded resources", "resources", "info"),

    QuickCommand("Whitelist Add", "Add to whitelist", "whitelist add {identifier}", "access"),
    QuickCommand("Whitelist Remove", "Remove from whitelist", "whitelist remove {identifier}", "access"),
]


# Common code snippets for FiveM development
CODE_SNIPPETS: dict[str, dict[str, str]] = {
    "Client": {
        "Register Command": '''RegisterCommand("{command}", function(source, args, rawCommand)
    -- Your code here
end, false)''',
        "Create Thread": '''Citizen.CreateThread(function()
    while true do
        Citizen.Wait(0)
        -- Your code here
    end
end)''',
        "Register Key Mapping": '''RegisterKeyMapping("{command}", "{description}", "keyboard", "{key}")''',
        "Trigger Server Event": '''TriggerServerEvent("{eventName}", arg1, arg2)''',
        "Register Net Event": '''RegisterNetEvent("{eventName}")
AddEventHandler("{eventName}", function(data)
    -- Your code here
end)''',
        "Draw Text 3D": '''function DrawText3D(x, y, z, text)
    SetTextScale(0.35, 0.35)
    SetTextFont(4)
    SetTextProportional(1)
    SetTextColour(255, 255, 255, 215)
    SetTextEntry("STRING")
    SetTextCentre(true)
    AddTextComponentString(text)
    SetDrawOrigin(x, y, z, 0)
    DrawText(0.0, 0.0)
    ClearDrawOrigin()
end''',
    },
    "Server": {
        "Register Server Event": '''RegisterNetEvent("{eventName}")
AddEventHandler("{eventName}", function(data)
    local src = source
    -- Your code here
end)''',
        "Trigger Client Event": '''TriggerClientEvent("{eventName}", source, arg1, arg2)''',
        "Trigger All Clients": '''TriggerClientEvent("{eventName}", -1, arg1, arg2)''',
        "Add Ace Permission": '''ExecuteCommand("add_ace identifier.{identifier} {permission} allow")''',
        "MySQL Query (oxmysql)": '''MySQL.query("SELECT * FROM {table} WHERE id = ?", {id}, function(result)
    if result then
        -- Your code here
    end
end)''',
        "MySQL Async (oxmysql)": '''local result = MySQL.query.await("SELECT * FROM {table} WHERE id = ?", {id})''',
    },
    "Shared": {
        "Export Function": '''exports("{exportName}", function(...)
    return yourFunction(...)
end)''',
        "Use Export": '''local result = exports["{resourceName}"]:exportName(args)''',
        "Config Table": '''Config = {}

Config.Debug = false
Config.Locale = "en"

Config.Locations = {
    { x = 0.0, y = 0.0, z = 0.0, heading = 0.0 },
}''',
    },
}


def get_quick_commands(category: str | None = None) -> list[QuickCommand]:
    """Get quick commands, optionally filtered by category."""
    if category:
        return [cmd for cmd in QUICK_COMMANDS if cmd.category == category]
    return QUICK_COMMANDS


def get_code_snippets(category: str | None = None) -> dict[str, dict[str, str]]:
    """Get code snippets, optionally filtered by category."""
    if category and category in CODE_SNIPPETS:
        return {category: CODE_SNIPPETS[category]}
    return CODE_SNIPPETS


def format_command(command: QuickCommand, **kwargs: str) -> str:
    """
    Format a quick command with provided arguments.

    Args:
        command: The QuickCommand to format.
        **kwargs: Arguments to substitute (e.g., resource="myresource").

    Returns:
        Formatted command string.
    """
    result = command.command
    for key, value in kwargs.items():
        result = result.replace(f"{{{key}}}", value)
    return result
