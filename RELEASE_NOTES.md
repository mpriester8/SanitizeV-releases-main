# Release Notes

## Version 1.1.4 (December 19, 2025)

### 🎉 New Features

**Graphics Profiles**
- Save current graphics settings from XML as named profiles
- Quickly apply different graphics configurations with one click
- Perfect for switching between Performance, Quality, and custom setups
- Easy profile management integrated into Graphics Editor

**Scheduled Cache Clearing**
- Auto-clear cache on app startup (optional)
- Schedule cache clearing every N days (1-30 days)
- Configurable auto-clear settings with easy toggle
- Never worry about cache buildup again

**Graphics Presets**
- Custom graphics profiles for saving and loading configurations
- Integrated directly into Graphics Editor for streamlined workflow

### 🔧 Improvements
- Enhanced Graphics Editor with integrated custom profiles
- Better cache management with scheduling options
- Streamlined interface with focused feature set
- Updated to use correct GitHub repository for updates
- Improved custom input dialogs with better sizing and formatting

### 🐛 Bug Fixes
- Fixed update URL to match SanitizeV-releases-main repository
- Fixed dialog windows showing buttons properly
- Better validation for profile data

---

## Version 1.1.2

### 🐛 Bug Fixes

*   **Dark Mode Hotfix**
    *   Fixed dark mode not persisting on application restart when saved to `%APPDATA%` directory.
    *   Improved theme migration from old `%TEMP%` location to persistent `%APPDATA%\SanitizeV` directory.
    *   Fixed real-time theme switching—all UI elements now update immediately without requiring restart.
    *   Enhanced dark mode styling for all widget types including dropdowns, sliders, and text fields.
    *   Fixed Graphics Editor tab to properly apply dark mode on startup.
    *   Windows 11/10 title bar now properly matches selected theme.

### 🎨 UI Improvements

*   **Complete Theme Coverage**: All tabs, controls, and dynamically created widgets now properly theme in real-time.
*   **Orange Button Preservation**: "CLEAR CACHE NOW" button maintains orange color in both light and dark modes.
*   **Better Color Contrast**: Improved text colors and backgrounds for better readability in dark mode.

## Version 1.1.1

### 🎨 New Features

*   **Dark Mode Support**
    *   Toggle between light and dark themes with a single click.
    *   Theme preference is automatically saved and persisted across sessions.
    *   Complete color scheme redesign for comfortable viewing in low-light environments.
    *   Easy-to-use theme button in the top control bar.

### 🔧 Technical Improvements

*   **New `theme.py` Module**: Provides comprehensive theming system with configurable color palettes.
*   **Persistent Theme Settings**: Saves user theme preference to local settings file.
*   **Dynamic Theme Application**: Applies theme colors to all widget types automatically.

## Version 1.1.0

### 🚀 New Features

*   **Automatic Update System**
    *   Application now automatically checks for updates on startup.
    *   Users receive notifications when new versions are available.
    *   One-click update installation—just click "Yes" in the notification dialog.
    *   Updates are downloaded silently in the background without freezing the application.
    *   No source files required; users only need the executable.

### 🔧 Technical Improvements

*   **New `update_manager.py` Module**: Handles version checking, downloading, and installation.
*   **Asynchronous Update Checking**: Updates are checked in a separate thread to prevent UI blocking.
*   **Automatic Cleanup**: Old downloaded versions are automatically cleaned up from the temp directory.
*   **Version Comparison**: Intelligent version comparison system ensures only actual updates are installed.

## Version 1.0.2

### ⚡ Performance Improvements
*   **Debounced File Counting:** Optimized the "Mods & Plugins" check to reduce UI lag. The application now waits for you to stop typing before scanning directories, making the interface significantly more responsive when editing path fields.

## Version 1.0.0 (Initial Release)

We are excited to announce the first major release of **Sanitize V**, the ultimate utility for managing your FiveM/GTA V environment.

### 🌟 New Features

*   **Sanitize & Restore Workflow**
    *   One-click functionality to disable (move) `mods` and `plugins` folders to a backup location.
    *   Easily restore them back to your FiveM directory when ready to play.
    *   Customizable source and backup directory paths.

*   **XML Configuration Swapping**
    *   Swap your `gta5_settings.xml` file with a replacement version for better FPS or different visual styles.
    *   Automatic backup of your original settings file during the swap.

*   **Visual Graphics Editor**
    *   User-friendly GUI to edit `gta5_settings.xml` graphics and video settings.
    *   Adjust Shadow Quality, Texture Quality, Water Quality, and more using simple dropdowns.
    *   Fine-tune distance scaling and density with sliders.
    *   Safety features: Automatically validates inputs and creates backups before saving changes.

*   **Cache Maintenance**
    *   Instantly clear `cache`, `server-cache`, and `server-cache-priv` folders to fix game issues or free up space.
    *   Keeps track of the last time you cleared your cache.

*   **User Interface**
    *   Clean, tabbed interface organized by function.
    *   High DPI awareness for sharp rendering on modern displays.
    *   Version number display in the window title.

### 🛠 Technical Details

*   **Dependencies**: Built with Python and Tkinter. Requires `Pillow` for image handling.
*   **Standalone Support**: Includes a `build.bat` script to compile a single-file `.exe` using PyInstaller.
*   **State Persistence**: Application state (last cache clear time) is saved to a JSON file in the temp directory.
