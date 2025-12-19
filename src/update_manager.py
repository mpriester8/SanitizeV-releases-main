"""
Auto-update manager for Sanitize V application.
Handles checking for updates and applying them.
"""

import os
import sys
import json
import shutil
import threading
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Callable
import subprocess


class UpdateManager:
    """Manages application updates."""

    def __init__(self, current_version: str, app_name: str = "Sanitize V"):
        """
        Initialize the UpdateManager.
        
        Args:
            current_version: Current app version (e.g., "1.0.0")
            app_name: Application name for display
        """
        self.current_version = current_version
        self.app_name = app_name
        self.update_available = False
        self.new_version = None
        self.download_url = None
        self.release_notes = ""
        
        # GitHub raw content URL for version info
        # Change this to your GitHub repo
        self.version_check_url = (
            "https://raw.githubusercontent.com/mpriester8/SanitizeV-releases-main/"
            "main/version.json"
        )
        
    def version_tuple(self, version: str) -> tuple:
        """Convert version string to tuple for comparison."""
        try:
            return tuple(map(int, version.split('.')))
        except (ValueError, AttributeError):
            return (0, 0, 0)
    
    def is_newer_version(self, new_version: str) -> bool:
        """
        Check if new_version is newer than current_version.
        
        Args:
            new_version: Version string to check (e.g., "1.0.1")
            
        Returns:
            True if new_version is newer
        """
        return self.version_tuple(new_version) > self.version_tuple(self.current_version)
    
    def check_for_updates(self, timeout: int = 5) -> bool:
        """
        Check if an update is available.
        
        Args:
            timeout: Request timeout in seconds
            
        Returns:
            True if an update is available
        """
        try:
            print(f"Checking for updates at: {self.version_check_url}")
            with urllib.request.urlopen(self.version_check_url, timeout=timeout) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            new_version = data.get('version')
            self.download_url = data.get('download_url')
            self.release_notes = data.get('release_notes', "")
            
            print(f"Remote version: {new_version}")
            print(f"Current version: {self.current_version}")
            
            if new_version and self.is_newer_version(new_version):
                self.new_version = new_version
                self.update_available = True
                print("Update available!")
                return True
            else:
                print("No update available.")
                
        except urllib.error.URLError as e:
            print(f"URL Error - Could not connect to update server: {e}")
        except json.JSONDecodeError as e:
            print(f"JSON Error - Invalid response format: {e}")
        except KeyError as e:
            print(f"Key Error - Missing field in response: {e}")
        except Exception as e:
            print(f"Unexpected error during update check: {e}")
        
        return False
    
    def check_for_updates_async(
        self,
        callback: Optional[Callable[[bool], None]] = None,
        timeout: int = 5
    ) -> None:
        """
        Check for updates asynchronously in a separate thread.
        
        Args:
            callback: Function to call with result (True/False)
            timeout: Request timeout in seconds
        """
        def check():
            result = self.check_for_updates(timeout)
            if callback:
                callback(result)
        
        thread = threading.Thread(target=check, daemon=True)
        thread.start()
    
    def download_update(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Optional[str]:
        """
        Download the update EXE.
        
        Args:
            progress_callback: Function called with (downloaded, total) bytes
            
        Returns:
            Path to downloaded file or None if failed
        """
        if not self.download_url:
            print("No download URL available")
            return None
        
        try:
            # Create temp directory for download
            temp_dir = Path(os.getenv('TEMP')) / 'SanitizeV_Update'
            temp_dir.mkdir(exist_ok=True)
            
            exe_name = f"Sanitize_V_v{self.new_version}.exe"
            download_path = temp_dir / exe_name
            
            print(f"Downloading update to {download_path}...")
            
            def download_progress(block_num, block_size, total_size):
                downloaded = block_num * block_size
                if progress_callback:
                    progress_callback(min(downloaded, total_size), total_size)
            
            urllib.request.urlretrieve(
                self.download_url,
                download_path,
                reporthook=download_progress
            )
            
            print(f"Update downloaded successfully: {download_path}")
            return str(download_path)
        
        except Exception as e:
            print(f"Failed to download update: {e}")
            return None
    
    def apply_update(self, exe_path: str) -> bool:
        """
        Apply the downloaded update by launching the installer.
        
        Args:
            exe_path: Path to the new EXE file
            
        Returns:
            True if update installation started
        """
        try:
            if not os.path.exists(exe_path):
                print(f"EXE not found: {exe_path}")
                return False
            
            # Get the current executable path
            if getattr(sys, 'frozen', False):
                current_exe = sys.executable
            else:
                print("Not running as frozen executable")
                return False
            
            # Start the new version
            subprocess.Popen([exe_path])
            
            # Exit current application
            sys.exit(0)
            
        except Exception as e:
            print(f"Failed to apply update: {e}")
            return False
    
    def cleanup_old_versions(self, keep_count: int = 2) -> None:
        """
        Clean up old downloaded versions.
        
        Args:
            keep_count: Number of recent versions to keep
        """
        try:
            temp_dir = Path(os.getenv('TEMP')) / 'SanitizeV_Update'
            if not temp_dir.exists():
                return
            
            # Get all exe files sorted by modification time (newest first)
            exe_files = sorted(
                temp_dir.glob('Sanitize_V_v*.exe'),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            # Delete old versions
            for old_file in exe_files[keep_count:]:
                try:
                    old_file.unlink()
                    print(f"Cleaned up old version: {old_file.name}")
                except Exception as e:
                    print(f"Could not remove {old_file}: {e}")
        
        except Exception as e:
            print(f"Cleanup failed: {e}")


class UpdateDialog:
    """Simple update notification helper."""
    
    @staticmethod
    def format_update_message(
        current_version: str,
        new_version: str,
        release_notes: str = ""
    ) -> str:
        """
        Format update notification message.
        
        Args:
            current_version: Current version
            new_version: New version available
            release_notes: Release notes to display
            
        Returns:
            Formatted message string
        """
        message = (
            f"A new version of Sanitize V is available!\n\n"
            f"Current version: {current_version}\n"
            f"New version: {new_version}\n"
        )
        
        if release_notes:
            message += f"\nRelease Notes:\n{release_notes}\n"
        
        message += "\nWould you like to download and install the update?"
        
        return message
