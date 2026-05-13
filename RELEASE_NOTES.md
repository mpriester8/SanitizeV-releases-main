# Release Notes

## Version 2.1.0 — Design Overhaul & New Tools

A massive UI refresh plus eight new features for FiveM developers.

### 🎨 Brand new look

- **Sidebar navigation** replaces the top tab bar. Tools are grouped (Mods · Graphics & Resources · Server tools · Other) and labelled with icons, so you can scan the app at a glance.
- **Centralized theme system** (`src/theme.py`) — every color, radius, padding, and shadow comes from one place. No more ad-hoc `setStyleSheet` scattered across tabs.
- **Light & dark modes**, with optional auto-detection from system preference. Toggle from Settings or the sidebar footer button.
- **Accent color picker** — 10 presets (Amber, Orange, Red, Pink, Purple, Indigo, Blue, Cyan, Teal, Green). Theme + accent persist between launches.
- **Toast notifications** stack in the bottom-right and dismiss themselves. They replaced the old fading status bar for most user feedback.
- **Card-based layouts** within each page (rounded panels, subtle borders) instead of bare grids.

### ⌨️ Command palette

- Press **Ctrl+K** (or Ctrl+P) anywhere to fuzzy-search every tool, action, and snippet.
- ↑↓ to navigate, ↵ to run. Includes shortcuts for "Take a backup snapshot now," "Build dependency graph," and one-click snippet copying.

### 🆕 New tools

- **Mod Profiles** — Save named loadouts (e.g., "SP racing", "FiveM dev", "vanilla") and switch between them in one click. Each profile keeps its own stash under `_profiles/`.
- **Manifest Auto-fix** — Beyond reporting issues, the validator can now apply safe transforms: add missing `fx_version`/`game`, bump older versions to `cerulean`, enable `lua54`, de-dupe dependencies, migrate `__resource.lua` → `fxmanifest.lua`. Every fix takes a timestamped `.bak`.
- **Live Log Tailer** — Tail `server.log` in real time with color-coded severity (error/warning/success/debug), regex filtering, resource extraction, and auto-scroll.
- **server.cfg Editor** — Friendly form for the common convars (`sv_hostname`, `sv_maxclients`, `onesync`, etc.) with descriptions, password masking, and a resources panel where you can toggle `ensure` ↔ `stop`.
- **Dependency Graph** — Parses every resource's manifest, surfaces dependencies, exports, reverse references, missing dep names, and detected cycles.
- **Resource Scaffolder** — Wizard that generates a new resource folder with a clean `fxmanifest.lua`, `client.lua`, `server.lua`, and `config.lua` for one of three templates: basic, ESX, or QBCore.
- **Locale Checker** — For each resource with a `locales/` folder, lists missing keys per language plus translation keys referenced in Lua (`_U(...)`, `Lang:t(...)`) but never defined.
- **Backup History** — Take dated, labelled snapshots of your mods/plugins folders. Restore any snapshot, or diff two of them to see added/removed/changed files.

### 🛠 Quality-of-life

- **Recent paths dropdown** on every folder/file input (▾ button next to the field).
- **Drag-and-drop** a folder onto any path input to set it.
- **Markdown export** for command lists and conflict reports (in addition to CSV/TXT).
- **In-app changelog viewer** on the Settings page reads `RELEASE_NOTES.md` directly.
- **Home dashboard** with quick-access cards for the most-used tools.

### 🧰 Under the hood

- New modules: `theme.py`, `widgets.py`, `command_palette.py`, `mod_profiles.py`, `manifest_fixer.py`, `log_tailer.py`, `server_cfg.py`, `dependency_graph.py`, `scaffolder.py`, `locale_checker.py`, `backup_history.py`.
- 28 new unit tests covering the logic of every new module (60 total tests passing).
- All worker-thread → UI updates now flow through a typed `Signal` to avoid `QMetaObject.invokeMethod` pitfalls.

---

## Version 2.0.0 — The Big One

This is a ground-up rewrite. The old Tkinter UI is gone, replaced with a modern PySide6 (Qt) interface. We've also added a bunch of new tools specifically for FiveM server developers.

### 🎨 Completely New Interface

- **PySide6/Qt Framework** — The entire app has been rebuilt using Qt. It's faster, looks better, and scales properly on high-DPI displays.
- **Fusion Style** — Clean, modern look that works the same on every Windows machine.
- **Auto-Fading Status Bar** — Status messages now fade out after a few seconds instead of sitting there forever.
- **Proper Taskbar Icon** — The app icon now shows correctly in the Windows taskbar (no more generic Python icon).

### 🔧 New Tools for FiveM Developers

- **Command Scanner**
  - Scans your entire server resources folder for registered commands
  - Detects native `RegisterCommand`, ESX commands, QBCore commands, and chat suggestions
  - Shows permission requirements (Everyone, Admin, ACE, Job-based) with color coding
  - Cleans up messy command names (strips leading `/-_0` prefixes automatically)
  - Export to CSV or TXT, import from external lists
  - Built-in ACE permission documentation with examples

- **Manifest Validator**
  - Validates `fxmanifest.lua` and `__resource.lua` files across your resources
  - Catches missing required fields, deprecated Lua versions, and file reference errors
  - Shows results in a clear, organized table

- **Conflict Detector**
  - Finds duplicate YMAP files that cause in-game conflicts (flickering objects, Z-fighting)
  - Distinguishes between exact duplicates and same-name-different-content conflicts
  - Exports detailed reports for fixing issues

- **Developer Utilities**
  - Quick Commands tab with common server commands (one-click copy)
  - Code Snippets for events, threads, callbacks, and more
  - Detailed ACE permission reference with server.cfg examples

### 🛠 Improvements to Existing Features

- **Graphics Editor** — Same functionality, cleaner layout. Dropdowns and sliders now look and feel better.
- **Server Console** — Simple command scratchpad for building RCON commands.
- **Cache Cleaner** — Still one-click, still tracks when you last cleared it.

### 🗑 Removed

- **Asset Optimizer** — Removed. It was rarely used and added unnecessary complexity.
- **Legacy Tkinter UI** — Gone. If PySide6 fails to load, the app will tell you instead of falling back to the old interface.

### 📝 Technical Notes

- Python 3.12+ required
- Dependencies: PySide6, Pillow, requests, pyinstaller (for building)
- Windows 10/11 only (Linux/Mac not tested)

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
