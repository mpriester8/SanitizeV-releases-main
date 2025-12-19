"""
Core logic functions for Sanitize V.
"""

import os
import shutil
import json
import tempfile
from datetime import datetime

# State File in Temp Directory
TEMP_DIR = tempfile.gettempdir()
STATE_DIR = os.path.join(TEMP_DIR, "SanitizeV")
STATE_FILE = os.path.join(STATE_DIR, "sanitize_v_state.json")


def load_state():
    """Load application state from JSON file."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            return {}
    return {}


def save_state(data):
    """Save application state to JSON file."""
    try:
        if not os.path.exists(STATE_DIR):
            os.makedirs(STATE_DIR)
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except IOError:
        pass


def clear_cache_logic(source_dir, log_callback=print):
    """
    Deletes cache folders from FiveM data directory.
    Target folders in /data/: "cache", "server-cache", "server-cache-priv"
    """
    try:
        data_dir = os.path.join(source_dir, 'data')
        if not os.path.exists(data_dir):
            log_callback(f"Error: Data directory not found at {data_dir}")
            return False, None

        targets = ["cache", "server-cache", "server-cache-priv"]

        for target in targets:
            target_path = os.path.join(data_dir, target)
            if os.path.exists(target_path):
                log_callback(f"Deleting {target_path}...")
                try:
                    shutil.rmtree(target_path)
                except OSError as e:
                    log_callback(f"Failed to delete {target}: {e}")
            else:
                log_callback(f"{target} not found (already clean).")

        # Update timestamp
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state = load_state()
        state['last_cache_clear'] = now_str
        save_state(state)

        log_callback("Cache cleaning process finished.")
        return True, now_str

    except Exception as e:  # pylint: disable=broad-exception-caught
        log_callback(f"Error clearing cache: {str(e)}")
        return False, None


def move_files_logic(source_dir, folder1_name, folder2_name,
                     xml_source_dir, xml_filename,
                     replacement_xml_path, destination_dir,
                     include_mods=True, include_plugins=True, include_xml=True, log_callback=print,
                     prompt_callback=None):
    """
    Logic to move folders and optionally handle XML replacement (Forward Operation).
    """
    try:
        # Canonicalize paths
        source_dir = os.path.abspath(source_dir)
        destination_dir = os.path.abspath(destination_dir)

        folder1_src = os.path.join(source_dir, folder1_name)
        folder2_src = os.path.join(source_dir, folder2_name)
        folder1_dest = os.path.join(destination_dir, folder1_name)
        folder2_dest = os.path.join(destination_dir, folder2_name)

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
            if os.path.exists(folder1_dest):
                log_callback(
                    f"Warning: {folder1_dest} already exists. Overwriting...")
                shutil.rmtree(folder1_dest)
            log_callback(f"Moving {folder1_src} -> {folder1_dest}...")
            shutil.move(folder1_src, folder1_dest)

        # 2. Move 'plugins' (If enabled)
        if include_plugins:
            if os.path.exists(folder2_dest):
                log_callback(
                    f"Warning: {folder2_dest} already exists. Overwriting...")
                shutil.rmtree(folder2_dest)
            log_callback(f"Moving {folder2_src} -> {folder2_dest}...")
            shutil.move(folder2_src, folder2_dest)

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
                    # Sanitize filename
                    label = "".join(
                        [c for c in user_label if c.isalnum() or c in (' ', '-', '_')]
                    ).strip()

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

        log_callback("Sanitize (Move) Operation completed successfully!")
        return True

    except Exception as e:  # pylint: disable=broad-exception-caught
        log_callback(f"Error: {str(e)}")
        return False


def revert_files_logic(source_dir, folder1_name, folder2_name,
                       xml_source_dir, xml_filename,
                       destination_dir,
                       include_mods=True, include_plugins=True, include_xml=True,
                       restore_xml_path=None, log_callback=print):
    """
    Logic to restore folders and XML back to original source (Reverse Operation).
    restore_xml_path: The full path to the specific XML file in the backup directory to restore.
    """
    try:
        # Canonicalize paths
        source_dir = os.path.abspath(source_dir)
        destination_dir = os.path.abspath(destination_dir)

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
            if os.path.exists(folder1_in_src):
                log_callback(
                    f"Warning: {folder1_in_src} already exists in Source. Overwriting...")
                shutil.rmtree(folder1_in_src)
            log_callback(f"Restoring {folder1_in_dest} -> {folder1_in_src}...")
            shutil.move(folder1_in_dest, folder1_in_src)

        # 2. Move 'plugins' Back (If enabled)
        if include_plugins:
            if os.path.exists(folder2_in_src):
                log_callback(
                    f"Warning: {folder2_in_src} already exists in Source. Overwriting...")
                shutil.rmtree(folder2_in_src)
            log_callback(f"Restoring {folder2_in_dest} -> {folder2_in_src}...")
            shutil.move(folder2_in_dest, folder2_in_src)

        # 3. Move XML Back (If enabled)
        if include_xml:
            if os.path.exists(xml_in_src):
                log_callback(
                    f"Warning: Overwriting current XML in Source: {xml_in_src}...")
                os.remove(xml_in_src)
            log_callback(f"Restoring {xml_in_dest} -> {xml_in_src}...")
            shutil.move(xml_in_dest, xml_in_src)

        log_callback("Restore/Back Operation completed successfully!")
        return True

    except Exception as e:  # pylint: disable=broad-exception-caught
        log_callback(f"Error: {str(e)}")
        return False
