"""
Scheduled cache clearing system for Sanitize V.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional
from logic import STATE_DIR, load_state, save_state


CACHE_SETTINGS_FILE = os.path.join(STATE_DIR, "cache_settings.json")


def load_cache_settings() -> dict:
    """Load cache clearing settings."""
    if os.path.exists(CACHE_SETTINGS_FILE):
        try:
            with open(CACHE_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            pass
    
    # Default settings
    return {
        "auto_clear_enabled": False,
        "auto_clear_on_startup": False,
        "auto_clear_days": 7,  # Clear every N days
        "last_auto_clear": None
    }


def save_cache_settings(settings: dict):
    """Save cache clearing settings."""
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(CACHE_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
    except IOError as e:
        print(f"Error saving cache settings: {e}")


def should_auto_clear() -> bool:
    """
    Check if cache should be automatically cleared based on settings.
    
    Returns:
        True if cache should be cleared
    """
    settings = load_cache_settings()
    
    if not settings.get("auto_clear_enabled", False):
        return False
    
    last_clear = settings.get("last_auto_clear")
    if last_clear is None:
        # Never cleared with auto-clear, should clear
        return True
    
    try:
        last_clear_date = datetime.strptime(last_clear, "%Y-%m-%d %H:%M:%S")
        days_since = (datetime.now() - last_clear_date).days
        
        clear_interval = settings.get("auto_clear_days", 7)
        return days_since >= clear_interval
    except (ValueError, TypeError):
        return True


def check_and_auto_clear(source_dir: str, log_callback=print) -> bool:
    """
    Check if auto-clear should run and execute if needed.
    
    Args:
        source_dir: FiveM directory path
        log_callback: Function to log messages
    
    Returns:
        True if cache was cleared
    """
    settings = load_cache_settings()
    
    # Check startup clear
    if settings.get("auto_clear_on_startup", False):
        from logic import clear_cache_logic
        success, timestamp = clear_cache_logic(source_dir, log_callback)
        if success:
            settings["last_auto_clear"] = timestamp
            save_cache_settings(settings)
            return True
        return False
    
    # Check scheduled clear
    if should_auto_clear():
        from logic import clear_cache_logic
        log_callback("Auto-clearing cache based on schedule...")
        success, timestamp = clear_cache_logic(source_dir, log_callback)
        if success:
            settings["last_auto_clear"] = timestamp
            save_cache_settings(settings)
            return True
    
    return False


def update_cache_settings(auto_clear_enabled: bool, 
                         auto_clear_on_startup: bool,
                         auto_clear_days: int):
    """
    Update cache clearing settings.
    
    Args:
        auto_clear_enabled: Enable scheduled auto-clear
        auto_clear_on_startup: Clear cache on app startup
        auto_clear_days: Days between auto-clears
    """
    settings = load_cache_settings()
    settings["auto_clear_enabled"] = auto_clear_enabled
    settings["auto_clear_on_startup"] = auto_clear_on_startup
    settings["auto_clear_days"] = max(1, auto_clear_days)  # Minimum 1 day
    save_cache_settings(settings)


def get_next_auto_clear_date() -> Optional[str]:
    """
    Get the next scheduled auto-clear date.
    
    Returns:
        Date string or None if auto-clear is disabled
    """
    settings = load_cache_settings()
    
    if not settings.get("auto_clear_enabled", False):
        return None
    
    last_clear = settings.get("last_auto_clear")
    if last_clear is None:
        return "Next startup"
    
    try:
        last_clear_date = datetime.strptime(last_clear, "%Y-%m-%d %H:%M:%S")
        interval = settings.get("auto_clear_days", 7)
        next_clear = last_clear_date + timedelta(days=interval)
        return next_clear.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return "Unknown"
