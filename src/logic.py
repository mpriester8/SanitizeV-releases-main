"""
Core logic functions for Sanitize V.
"""

import os
import shutil
import json
import tempfile
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Any

try:
    from security_utils import validate_path_in_directory, sanitize_filename, SecurityError
except ImportError:
    from src.security_utils import validate_path_in_directory, sanitize_filename, SecurityError

logger = logging.getLogger(__name__)

# State File in Temp Directory
TEMP_DIR = tempfile.gettempdir()
STATE_DIR = os.path.join(TEMP_DIR, "SanitizeV")
STATE_FILE = os.path.join(STATE_DIR, "sanitize_v_state.json")


def load_state() -> dict[str, Any]:
    """Load application state from JSON file."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            logger.warning("Failed to load state: %s", e)
            return {}
    return {}


def save_state(data: dict[str, Any]) -> None:
    """Save application state to JSON file."""
    try:
        if not os.path.exists(STATE_DIR):
            os.makedirs(STATE_DIR)
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except IOError as e:
        logger.warning("Failed to save state: %s", e)


def clear_cache_logic(
    source_dir: str,
    log_callback: Callable[[str], None] = print,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_event: Optional[threading.Event] = None
) -> tuple[bool, Optional[str]]:
    """
    Deletes cache folders from FiveM data directory.
    Target folders in /data/: "cache", "server-cache", "server-cache-priv"
    
    Args:
        source_dir: Base directory containing /data folder
        log_callback: Function to call for logging messages
        progress_callback: Optional callback for progress updates (completed, total)
        cancel_event: Optional event to signal cancellation
        
    Returns:
        Tuple of (success: bool, timestamp: Optional[str])
    """
    try:
        # Validate path to prevent traversal attacks
        try:
            source_path = Path(source_dir).resolve()
            data_dir = str(source_path / 'data')
        except (ValueError, OSError) as e:
            log_callback(f"Error: Invalid source directory: {e}")
            return False, None
        
        if not os.path.exists(data_dir):
            log_callback(f"Error: Data directory not found at {data_dir}")
            return False, None

        targets = ["cache", "server-cache", "server-cache-priv"]

        total = len(targets)
        completed = 0

        for target in targets:
            # Check for cancellation
            if cancel_event and cancel_event.is_set():
                log_callback("Cache clear cancelled by user.")
                return False, None

            target_path = os.path.join(data_dir, target)
            # Atomic operation - attempt delete without separate exists check (fixes TOCTOU)
            try:
                log_callback(f"Deleting {target_path}...")
                shutil.rmtree(target_path)
            except FileNotFoundError:
                log_callback(f"{target} not found (already clean).")
            except OSError as e:
                log_callback(f"Failed to delete {target}: {e}")

            completed += 1
            if progress_callback:
                try:
                    progress_callback(completed, total)
                except Exception as e:
                    logger.warning("Progress callback failed: %s", e)

        # Update timestamp
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state = load_state()
        state['last_cache_clear'] = now_str
        save_state(state)

        log_callback("Cache cleaning process finished.")
        return True, now_str

    except OSError as e:
        log_callback(f"File system error clearing cache: {str(e)}")
        logger.exception("Cache clear failed")
        return False, None
    except Exception as e:
        log_callback(f"Unexpected error clearing cache: {str(e)}")
        logger.exception("Unexpected cache clear failure")
        return False, None


def move_files_logic(
    source_dir: str,
    folder1_name: str,
    folder2_name: str,
    xml_source_dir: str,
    xml_filename: str,
    replacement_xml_path: str,
    destination_dir: str,
    include_mods: bool = True,
    include_plugins: bool = True,
    include_xml: bool = True,
    log_callback: Callable[[str], None] = print,
    prompt_callback: Optional[Callable[[str, str], Optional[str]]] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_event: Optional[threading.Event] = None
) -> bool:
    """
    Logic to move folders and optionally handle XML replacement (Forward Operation).
    
    Args:
        source_dir: Source directory containing folders to move
        folder1_name: Name of first folder (typically 'mods')
        folder2_name: Name of second folder (typically 'plugins')
        xml_source_dir: Directory containing XML file
        xml_filename: Name of XML file
        replacement_xml_path: Path to replacement XML file
        destination_dir: Destination directory for moved files
        include_mods: Whether to move mods folder
        include_plugins: Whether to move plugins folder
        include_xml: Whether to perform XML swap
        log_callback: Function for logging messages
        prompt_callback: Function to prompt user for input
        progress_callback: Function for progress updates
        cancel_event: Event to signal cancellation
        
    Returns:
        True if operation succeeded, False otherwise
    """
    try:
        # Validate and canonicalize paths to prevent traversal attacks
        try:
            source_path = Path(source_dir).resolve()
            dest_path = Path(destination_dir).resolve()
            
            # Validate folder names don't contain path separators or traversal sequences
            for name, label in [(folder1_name, "folder1"), (folder2_name, "folder2")]:
                if any(char in name for char in ['..', '/', '\\']):
                    raise SecurityError(f"{label} name contains invalid path characters: {name}")
            
            folder1_src = str(validate_path_in_directory(source_path, folder1_name))
            folder2_src = str(validate_path_in_directory(source_path, folder2_name))
            folder1_dest = str(dest_path / folder1_name)
            folder2_dest = str(dest_path / folder2_name)
            
            source_dir = str(source_path)
            destination_dir = str(dest_path)
            
        except SecurityError as e:
            log_callback(f"Security Error: {e}")
            logger.error("Path validation failed: %s", e)
            return False

        if include_xml:
            xml_source_dir = os.path.abspath(xml_source_dir)
            replacement_xml_path = os.path.abspath(replacement_xml_path)
            xml_src = os.path.join(xml_source_dir, xml_filename)

            if xml_source_dir == destination_dir:
                log_callback(
                    "Error: XML source directory and Destination directory are the same.")
                return False
            if not os.path.exists(xml_source_dir):
                raise FileNotFoundError(
                    f"XML source dir not found: {xml_source_dir}")
            if not os.path.exists(xml_src):
                raise FileNotFoundError(
                    f"XML file not found in Source: {xml_src}")
            if not os.path.exists(replacement_xml_path):
                raise FileNotFoundError(
                    f"Replacement XML not found: {replacement_xml_path}")

        # Validation
        if include_mods or include_plugins:
            if source_dir == destination_dir:
                log_callback(
                    "Error: Source folder directory and Destination directory are the same.")
                return False
            if not os.path.exists(source_dir):
                raise FileNotFoundError(
                    f"Source folder dir not found: {source_dir}")

        if include_mods and not os.path.exists(folder1_src):
            raise FileNotFoundError(
                f"Folder 1 (mods) not found in Source: {folder1_src}")
        if include_plugins and not os.path.exists(folder2_src):
            raise FileNotFoundError(
                f"Folder 2 (plugins) not found in Source: {folder2_src}")

        if not os.path.exists(destination_dir):
            log_callback(
                f"Destination directory does not exist. Creating: {destination_dir}")
            os.makedirs(destination_dir, exist_ok=True)

        # 1. Move 'mods' (If enabled)
        if include_mods:
            if cancel_event and cancel_event.is_set():
                log_callback("Sanitize cancelled before moving mods.")
                return False
            # Atomic operation to fix TOCTOU race condition
            try:
                log_callback(f"Moving {folder1_src} -> {folder1_dest}...")
                shutil.move(folder1_src, folder1_dest)
            except FileExistsError:
                log_callback(f"Warning: {folder1_dest} already exists. Overwriting...")
                shutil.rmtree(folder1_dest)
                shutil.move(folder1_src, folder1_dest)
            if progress_callback:
                try:
                    progress_callback(1, 3)
                except Exception:
                    pass

        # 2. Move 'plugins' (If enabled)
        if include_plugins:
            if cancel_event and cancel_event.is_set():
                log_callback("Sanitize cancelled before moving plugins.")
                return False
            # Atomic operation to fix TOCTOU race condition
            try:
                log_callback(f"Moving {folder2_src} -> {folder2_dest}...")
                shutil.move(folder2_src, folder2_dest)
            except FileExistsError:
                log_callback(f"Warning: {folder2_dest} already exists. Overwriting...")
                shutil.rmtree(folder2_dest)
                shutil.move(folder2_src, folder2_dest)
            if progress_callback:
                try:
                    progress_callback(2, 3)
                except Exception:
                    pass

        # 3. Move XML (If enabled)
        if include_xml:
            # Prompt user for a label for the file being moved (the "previous" xml)
            label = "backup"
            if prompt_callback:
                user_label = prompt_callback(
                    "Backup Label",
                    "Enter a label for the current XML settings (e.g. 'Original', 'Ultra'):"
                )
                if user_label:
                    # Sanitize filename using secure utility
                    label = sanitize_filename(user_label)

            # Construct destination filename with label
            # e.g., gta5_settings.xml -> gta5_settings_Original.xml
            name, ext = os.path.splitext(xml_filename)
            labeled_xml_filename = f"{name}_{label}{ext}"
            labeled_xml_dest = os.path.join(
                destination_dir, labeled_xml_filename)

            if os.path.exists(labeled_xml_dest):
                log_callback(
                    f"Warning: {labeled_xml_dest} already exists. Overwriting...")
                os.remove(labeled_xml_dest)

            log_callback(f"Moving {xml_src} -> {labeled_xml_dest}...")
            shutil.move(xml_src, labeled_xml_dest)

            # 4. Replace XML in original location
            log_callback(
                f"Copying replacement XML {replacement_xml_path} -> {xml_src}...")
            shutil.copy2(replacement_xml_path, xml_src)
            if progress_callback:
                try:
                    progress_callback(3, 3)
                except Exception:
                    pass

        log_callback("Sanitize (Move) Operation completed successfully!")
        return True

    except SecurityError as e:
        log_callback(f"Security Error: {str(e)}")
        logger.error("Security violation in move_files: %s", e)
        return False
    except FileNotFoundError as e:
        log_callback(f"File Not Found: {str(e)}")
        logger.error("File not found in move_files: %s", e)
        return False
    except OSError as e:
        log_callback(f"File System Error: {str(e)}")
        logger.exception("OS error in move_files")
        return False
    except Exception as e:
        log_callback(f"Unexpected Error: {str(e)}")
        logger.exception("Unexpected error in move_files")
        return False


def revert_files_logic(
    source_dir: str,
    folder1_name: str,
    folder2_name: str,
    xml_source_dir: str,
    xml_filename: str,
    destination_dir: str,
    include_mods: bool = True,
    include_plugins: bool = True,
    include_xml: bool = True,
    restore_xml_path: Optional[str] = None,
    log_callback: Callable[[str], None] = print,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_event: Optional[threading.Event] = None
) -> bool:
    """
    Logic to restore folders and XML back to original source (Reverse Operation).
    
    Args:
        source_dir: Source directory to restore to
        folder1_name: Name of first folder
        folder2_name: Name of second folder
        xml_source_dir: Directory for XML file
        xml_filename: Name of XML file
        destination_dir: Directory containing backed up files
        include_mods: Whether to restore mods
        include_plugins: Whether to restore plugins
        include_xml: Whether to restore XML
        restore_xml_path: Full path to specific XML backup file
        log_callback: Function for logging
        progress_callback: Function for progress updates
        cancel_event: Event to signal cancellation
        
    Returns:
        True if operation succeeded
    """
    try:
        # Validate and canonicalize paths to prevent traversal attacks
        try:
            source_path = Path(source_dir).resolve()
            dest_path = Path(destination_dir).resolve()
            
            # Validate folder names don't contain path separators or traversal sequences
            for name, label in [(folder1_name, "folder1"), (folder2_name, "folder2")]:
                if any(char in name for char in ['..', '/', '\\']):
                    raise SecurityError(f"{label} name contains invalid path characters: {name}")
            
            source_dir = str(source_path)
            destination_dir = str(dest_path)
            
        except SecurityError as e:
            log_callback(f"Security Error: {e}")
            logger.error("Path validation failed: %s", e)
            return False

        folder1_in_dest = os.path.join(destination_dir, folder1_name)
        folder2_in_dest = os.path.join(destination_dir, folder2_name)
        folder1_in_src = os.path.join(source_dir, folder1_name)
        folder2_in_src = os.path.join(source_dir, folder2_name)

        if include_xml:
            xml_source_dir = os.path.abspath(xml_source_dir)
            xml_in_src = os.path.join(xml_source_dir, xml_filename)

            # Use the specifically provided XML path, or fallback to default filename in dest
            if restore_xml_path:
                xml_in_dest = restore_xml_path
            else:
                xml_in_dest = os.path.join(destination_dir, xml_filename)

            if xml_source_dir == destination_dir:
                return False
            if not os.path.exists(xml_in_dest):
                raise FileNotFoundError(
                    f"Backup XML file not found: {xml_in_dest}")
            if not os.path.exists(xml_source_dir):
                os.makedirs(xml_source_dir, exist_ok=True)

        # Validation
        if source_dir == destination_dir:
            return False
        if not os.path.exists(destination_dir):
            raise FileNotFoundError(
                f"Destination dir not found: {destination_dir}")

        if include_mods:
            if not os.path.exists(folder1_in_dest):
                raise FileNotFoundError(
                    f"Folder 1 (mods) not found in Destination: {folder1_in_dest}"
                )
        if include_plugins:
            if not os.path.exists(folder2_in_dest):
                raise FileNotFoundError(
                    f"Folder 2 (plugins) not found in Destination: {folder2_in_dest}"
                )

        if include_mods or include_plugins:
            if not os.path.exists(source_dir):
                os.makedirs(source_dir, exist_ok=True)

        # 1. Move 'mods' Back (If enabled)
        if include_mods:
            if cancel_event and cancel_event.is_set():
                log_callback("Restore cancelled before restoring mods.")
                return False
            # Atomic operation to fix race condition
            try:
                log_callback(f"Restoring {folder1_in_dest} -> {folder1_in_src}...")
                shutil.move(folder1_in_dest, folder1_in_src)
            except FileExistsError:
                log_callback(f"Warning: {folder1_in_src} already exists in Source. Overwriting...")
                shutil.rmtree(folder1_in_src)
                shutil.move(folder1_in_dest, folder1_in_src)
        if progress_callback:
            try:
                progress_callback(1, 3)
            except Exception:
                pass

        # 2. Move 'plugins' Back (If enabled)
        if include_plugins:
            if cancel_event and cancel_event.is_set():
                log_callback("Restore cancelled before restoring plugins.")
                return False
            # Atomic operation to fix race condition
            try:
                log_callback(f"Restoring {folder2_in_dest} -> {folder2_in_src}...")
                shutil.move(folder2_in_dest, folder2_in_src)
            except FileExistsError:
                log_callback(f"Warning: {folder2_in_src} already exists in Source. Overwriting...")
                shutil.rmtree(folder2_in_src)
                shutil.move(folder2_in_dest, folder2_in_src)
        if progress_callback:
            try:
                progress_callback(2, 3)
            except Exception:
                pass

        # 3. Move XML Back (If enabled)
        if include_xml:
            if cancel_event and getattr(cancel_event, 'is_set', lambda: False)():
                log_callback("Restore cancelled before restoring XML.")
                return False
            if os.path.exists(xml_in_src):
                log_callback(
                    f"Warning: Overwriting current XML in Source: {xml_in_src}...")
                os.remove(xml_in_src)
            log_callback(f"Restoring {xml_in_dest} -> {xml_in_src}...")
            shutil.move(xml_in_dest, xml_in_src)
        if progress_callback:
            try:
                progress_callback(3, 3)
            except Exception:
                pass

        log_callback("Restore/Back Operation completed successfully!")
        return True

    except FileNotFoundError as e:
        log_callback(f"File Not Found: {str(e)}")
        logger.error("File not found in revert_files: %s", e)
        return False
    except OSError as e:
        log_callback(f"File System Error: {str(e)}")
        logger.exception("OS error in revert_files")
        return False
    except Exception as e:
        log_callback(f"Unexpected Error: {str(e)}")
        logger.exception("Unexpected error in revert_files")
        return False
