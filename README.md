# Sanitize V v1.1.2

Sanitize V is a comprehensive utility for managing FiveM/GTA V modifications, configuration files, and cache. It allows users to easily toggle mods, swap graphics configurations, edit settings via a GUI, and clear cache files. The application automatically checks for updates and notifies you when new versions are available, and features a customizable dark mode theme.

## Features

### 1. Sanitize / Restore
- **Mod Management**: Easily move `mods` and `plugins` folders from your FiveM application data to a backup directory ("Sanitize") and restore them back ("Restore").
- **Backup Location**: Customize where your mods and settings are stored when disabled.

### 2. XML Swap
- **Config Management**: Swap your active `gta5_settings.xml` with different preset files.
- **Auto-Backup**: When sanitizing, the current settings file is moved to the backup folder with a custom label (e.g., `_Original`).
- **Safe Restore**: Restore specific configuration files from your backup folder.

### 3. Graphics Editor
- **GUI Editor**: Edit `gta5_settings.xml` without touching raw XML code.
- **Smart Controls**: Uses Dropdowns for quality settings (Normal, High, Ultra) and Sliders for distance/density settings.
- **Schema Validation**: Only allows valid values for specific settings (e.g., Shadow Quality, Tessellation, MSAA).
- **Auto-Logic**: Automatically handles dependent settings (e.g., enabling `Reflection MipBlur` only when Reflection Quality is Very High/Ultra).
- **Auto-Load**: Automatically loads your current settings on startup.

### 4. Cache Maintenance
- **One-Click Cleaning**: Clears `cache`, `server-cache`, and `server-cache-priv` folders from the FiveM data directory.
- **History**: Tracks and displays the last time the cache was cleared.

### 5. Auto-Update System
- **Automatic Version Checking**: The application automatically checks for updates when you launch it.
- **Background Downloads**: Updates are downloaded silently in the background without interrupting your workflow.
- **One-Click Installation**: When an update is available, simply click "Yes" in the notification dialog to download and install the latest version.
- **No Source Files Required**: Users only need the executable file from releases—the update system handles everything automatically.

### 6. Dark Mode
- **Theme Toggle**: Switch between light and dark modes with a single click using the theme button.
- **Persistent Settings**: Your theme preference is automatically saved and restored on next launch.
- **Eye Comfort**: Dark mode reduces eye strain in low-light environments with a carefully designed color palette.
- **Full Coverage**: All UI elements adapt to the selected theme for a consistent experience.

## How to Run (Source Code)

1.  Ensure Python 3.x is installed.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run the application:
    ```bash
    python file_mover.py
    ```

## How to Build .exe (Windows)

To create a standalone executable:

1.  Double-click `build.bat`.
    *   This script installs `pyinstaller` and `Pillow`.
    *   It runs PyInstaller with the correct flags to bundle the `banner.png` asset and hide the console.
2.  The resulting `Sanitize V.exe` will be found in the `dist/` folder.

## Requirements
- Windows 10/11
- Python 3.12+ (for source execution/building)
- Internet connection (for auto-update checks)

## Getting Updates

Sanitize V includes an automatic update system:

1. **Launch the application** - it automatically checks for updates 2 seconds after starting
2. **Get notified** - if a new version is available, you'll see a notification dialog
3. **Download & Install** - click "Yes" to download and install the update automatically
4. **Restart** - the new version will launch immediately after installation

All releases are available on the [GitHub Releases](https://github.com/mpriester8/SanitizeV/releases) page.
