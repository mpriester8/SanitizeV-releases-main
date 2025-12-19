"""
Profile management system for Sanitize V.
Allows saving and loading complete configurations.
"""

import os
import json
import shutil
from datetime import datetime
from typing import Dict, List, Optional
from logic import STATE_DIR


PROFILES_DIR = os.path.join(STATE_DIR, "profiles")
PROFILES_FILE = os.path.join(STATE_DIR, "profiles_index.json")


def ensure_profiles_dir():
    """Ensure the profiles directory exists."""
    if not os.path.exists(PROFILES_DIR):
        os.makedirs(PROFILES_DIR)


def load_profiles_index() -> Dict:
    """Load the profiles index file."""
    if os.path.exists(PROFILES_FILE):
        try:
            with open(PROFILES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            return {"profiles": []}
    return {"profiles": []}


def save_profiles_index(index: Dict):
    """Save the profiles index file."""
    try:
        ensure_profiles_dir()
        with open(PROFILES_FILE, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2)
    except IOError:
        pass


def get_all_profiles() -> List[Dict]:
    """Get all saved profiles."""
    index = load_profiles_index()
    return index.get("profiles", [])


def save_profile(name: str, description: str, config: Dict) -> bool:
    """
    Save a new profile.
    
    Args:
        name: Profile name
        description: Profile description
        config: Dictionary containing:
            - mods_enabled: bool
            - plugins_enabled: bool
            - xml_backup_name: str (optional)
            - graphics_settings: dict (optional)
            - source_dir: str
            - dest_dir: str
    
    Returns:
        True if successful, False otherwise
    """
    try:
        ensure_profiles_dir()
        
        # Create profile data
        profile_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        profile_data = {
            "id": profile_id,
            "name": name,
            "description": description,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "config": config
        }
        
        # Save profile file
        profile_file = os.path.join(PROFILES_DIR, f"{profile_id}.json")
        with open(profile_file, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, indent=2)
        
        # Update index
        index = load_profiles_index()
        index["profiles"].append({
            "id": profile_id,
            "name": name,
            "description": description,
            "created": profile_data["created"]
        })
        save_profiles_index(index)
        
        return True
    except Exception as e:
        print(f"Error saving profile: {e}")
        return False


def load_profile(profile_id: str) -> Optional[Dict]:
    """Load a specific profile by ID."""
    try:
        profile_file = os.path.join(PROFILES_DIR, f"{profile_id}.json")
        if os.path.exists(profile_file):
            with open(profile_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading profile: {e}")
    return None


def delete_profile(profile_id: str) -> bool:
    """Delete a profile by ID."""
    try:
        # Remove profile file
        profile_file = os.path.join(PROFILES_DIR, f"{profile_id}.json")
        if os.path.exists(profile_file):
            os.remove(profile_file)
        
        # Update index
        index = load_profiles_index()
        index["profiles"] = [p for p in index["profiles"] if p["id"] != profile_id]
        save_profiles_index(index)
        
        return True
    except Exception as e:
        print(f"Error deleting profile: {e}")
        return False
