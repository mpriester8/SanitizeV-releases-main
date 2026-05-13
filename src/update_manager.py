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
import tempfile
import logging

try:
    from security_utils import compute_file_hash, verify_file_integrity, SecurityError
except ImportError:
    from src.security_utils import compute_file_hash, verify_file_integrity, SecurityError


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
        self.new_version: Optional[str] = None
        self.download_url: Optional[str] = None
        self.release_notes = ""
        self.expected_sha256: Optional[str] = None
        
        # GitHub raw content URL for version info
        # Change this to your GitHub repo
        self.version_check_url = (
            "https://raw.githubusercontent.com/mpriester8/SanitizeV/"
            "main/version.json"
        )
        # Logger
        self.logger = logging.getLogger(__name__)
        
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
            self.logger.info("Checking for updates at: %s", self.version_check_url)
            with urllib.request.urlopen(self.version_check_url, timeout=timeout) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            new_version = data.get('version')
            self.download_url = data.get('download_url')
            self.release_notes = data.get('release_notes', "")
            self.expected_sha256 = data.get('sha256')  # SECURITY: Get expected hash
            
            # Security: Require SHA-256 hash for verification
            if not self.expected_sha256:
                self.logger.warning("Update available but no SHA-256 hash provided - SECURITY RISK")
                # Still set update_available but log the security concern
            
            self.logger.info("Remote version: %s", new_version)
            self.logger.info("Current version: %s", self.current_version)
            
            if new_version and self.is_newer_version(new_version):
                self.new_version = new_version
                self.update_available = True
                self.logger.info("Update available: %s", new_version)
                return True
            else:
                self.logger.info("No update available.")
                
        except urllib.error.URLError as e:
            self.logger.warning("URL Error - Could not connect to update server: %s", e)
        except json.JSONDecodeError as e:
            self.logger.warning("JSON Error - Invalid response format: %s", e)
        except KeyError as e:
            self.logger.warning("Key Error - Missing field in response: %s", e)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.exception("Unexpected error during update check: %s", e)
        
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
        Download the update EXE with integrity verification.
        
        Args:
            progress_callback: Function called with (downloaded, total) bytes
            
        Returns:
            Path to downloaded file or None if failed
            
        Raises:
            SecurityError: If integrity check fails
        """
        if not self.download_url:
            self.logger.warning("No download URL available")
            return None
        
        try:
            # Create temp directory for download with secure naming
            temp_root = os.getenv('TEMP') or tempfile.gettempdir()
            # Use a random suffix to prevent symlink attacks
            import secrets
            random_suffix = secrets.token_hex(8)
            temp_dir = Path(temp_root) / f'SanitizeV_Update_{random_suffix}'
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            exe_name = f"Sanitize_V_v{self.new_version}.exe"
            download_path = temp_dir / exe_name
            
            self.logger.info("Downloading update to %s...", download_path)
            
            def download_progress(block_num: int, block_size: int, total_size: int) -> None:
                downloaded = block_num * block_size
                if progress_callback:
                    progress_callback(min(downloaded, total_size), total_size)
            
            urllib.request.urlretrieve(
                self.download_url,
                download_path,
                reporthook=download_progress
            )

            # SECURITY: Verify file integrity if SHA-256 was provided
            if self.expected_sha256:
                self.logger.info("Verifying download integrity...")
                if not verify_file_integrity(download_path, self.expected_sha256):
                    self.logger.error("SECURITY: Downloaded file failed integrity check!")
                    download_path.unlink()  # Delete compromised file
                    raise SecurityError(
                        "Downloaded update failed integrity verification. "
                        "The file may be corrupted or tampered with."
                    )
                self.logger.info("Download integrity verified ✓")
            else:
                self.logger.warning(
                    "SECURITY WARNING: No SHA-256 hash available - cannot verify file integrity"
                )

            self.logger.info("Update downloaded successfully: %s", download_path)
            return str(download_path)
        
        except SecurityError:
            # Re-raise security errors
            raise
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.exception("Failed to download update: %s", e)
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
                self.logger.error("EXE not found: %s", exe_path)
                return False
            
            # Get the current executable path
            if getattr(sys, 'frozen', False):
                current_exe = sys.executable
            else:
                print("Not running as frozen executable")
                return False
            
            # Start the new version. On Windows prefer startfile for user context.
            try:
                if sys.platform == 'win32':
                    os.startfile(exe_path)  # type: ignore[attr-defined]
                else:
                    subprocess.Popen([exe_path])
            except Exception:
                # Fallback to Popen if startfile fails
                subprocess.Popen([exe_path])

            # Exit current application
            sys.exit(0)
            
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.exception("Failed to apply update: %s", e)
            return False
    
    def cleanup_old_versions(self, keep_count: int = 2) -> None:
        """
        Clean up old downloaded versions.
        
        Args:
            keep_count: Number of recent versions to keep
        """
        try:
            temp_root = os.getenv('TEMP') or tempfile.gettempdir()
            temp_root_path = Path(temp_root)
            
            # Find all SanitizeV_Update directories (including random-suffixed ones)
            update_dirs = list(temp_root_path.glob('SanitizeV_Update*'))
            
            # Collect all exe files from all update directories
            exe_files: list[Path] = []
            for update_dir in update_dirs:
                if update_dir.is_dir():
                    exe_files.extend(update_dir.glob('Sanitize_V_v*.exe'))
            
            if not exe_files:
                return
            
            # Sort by modification time (newest first)
            exe_files = sorted(exe_files, key=lambda p: p.stat().st_mtime, reverse=True)
            
            # Delete old versions (keep only keep_count most recent)
            for old_file in exe_files[keep_count:]:
                try:
                    old_file.unlink()
                    self.logger.info("Cleaned up old version: %s", old_file.name)
                    
                    # Try to remove parent directory if empty
                    parent = old_file.parent
                    if parent.is_dir() and not any(parent.iterdir()):
                        parent.rmdir()
                        self.logger.info("Removed empty update directory: %s", parent.name)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    self.logger.warning("Could not remove %s: %s", old_file, e)
        
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.exception("Cleanup failed: %s", e)


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
