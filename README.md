# Sanitize V

A powerful all-in-one toolkit for FiveM server developers and GTA V modders. Manage your mods, tweak graphics settings, validate server resources, scan commands, scaffold new resources, tail logs, and more — all from one clean interface.

![Version](https://img.shields.io/badge/version-2.1.0-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![Python](https://img.shields.io/badge/python-3.12+-green)

---

## What's New in 2.1

Version 2.1 is a top-to-bottom redesign with eight new tools:

- **Sidebar navigation** with grouped sections — Mods, Graphics & Resources, Server tools
- **Light & dark themes** with 10 accent color presets, persisted between launches
- **Command palette** — press **Ctrl+K** to fuzzy-search every tool, action, and snippet
- **Toast notifications** stack in the bottom-right, dismissing themselves
- **Mod Profiles** — save and switch named mod loadouts in one click
- **Manifest auto-fix** — apply safe transforms (fx_version, lua54, dedupe deps, rename to fxmanifest)
- **Live Log Tailer** — colored severity, regex filtering, resource extraction
- **server.cfg Editor** — friendly form for common convars with descriptions
- **Dependency Graph** — find missing deps and circular references between resources
- **Resource Scaffolder** — generate basic, ESX, or QBCore resources from templates
- **Locale Checker** — find missing translations and orphaned `_U(...)` references
- **Backup History** — dated, labelled snapshots with file-level diff between any two

---

## Features

### Sanitize & Restore
Quickly toggle your mods on and off without deleting anything. When you "sanitize," your `mods` and `plugins` folders get moved to a backup location. Hit restore when you're ready to play modded again.

- One-click enable/disable for all mods
- Custom backup location support
- Preserves folder structure

### Graphics Editor
Edit your `gta5_settings.xml` through a friendly GUI instead of digging through XML tags. Dropdowns for quality settings, sliders for distance values—it just works.

- Smart controls that match each setting type
- Validates values before saving (no more broken configs)
- Auto-loads your current settings on startup

### Manifest Validator
Point it at your resources folder and it'll check every `fxmanifest.lua` and `__resource.lua` for issues:

- Missing required fields (`fx_version`, `game`)
- Deprecated Lua 5.1 usage
- Files referenced but not found on disk
- Syntax problems in the manifest itself

### Server Console
A scratchpad for server commands. Build your RCON commands, copy them to clipboard, and keep track of what you've run.

### Command Scanner
Scans your server's Lua files and finds every registered command—native `RegisterCommand`, ESX commands, QBCore commands, even chat suggestions. Shows you:

- Command name (cleaned up, no weird prefixes)
- What framework it uses
- What permissions are required (Everyone, Admin, ACE, Job-based)
- Which file it came from

You can export the list to CSV or TXT, and import lists from other sources.

### Conflict Detector
Finds duplicate YMAP files across your resources that would cause in-game conflicts (flickering, Z-fighting, objects loading twice). Flags exact duplicates vs. same-name-different-content situations.

### Developer Utilities
Quick access to commonly-needed stuff:

- **Quick Commands** — copy frequently-used server commands with one click
- **Code Snippets** — boilerplate for events, callbacks, threads, etc.
- **ACE Permission Help** — explains how FiveM's permission system works

### Cache Maintenance
Clear your FiveM cache folders with one click. Tracks when you last cleared them so you don't forget.

### Mod Profiles
Save named loadouts (e.g. "SP racing", "FiveM dev", "vanilla") and switch between them with one click. Each profile keeps its own stash on disk and the active loadout is captured automatically before swapping.

### Live Log Tailer
Tail `server.log` in real time. Each line is colored by severity (error/warning/success/debug), prefixed with the originating resource when one is detected, and filterable by regex.

### server.cfg Editor
Form-based editor for the common convars — `sv_hostname`, `sv_maxclients`, `onesync`, `rcon_password`, `sv_enforceGameBuild`, and more. The resources panel lets you flip an entry between `ensure` and `stop` without hand-editing the file.

### Dependency Graph
Builds the full dependency graph for a resources folder: declared dependencies, exports, reverse references, missing deps, and circular dependency detection.

### Resource Scaffolder
Generates a new resource folder with a complete `fxmanifest.lua` and starter client/server/shared files. Pick from three templates: basic, ESX (registers an ESX command on init), or QBCore.

### Locale Checker
For each resource with a `locales/` folder, lists translation keys missing in some languages and keys that are referenced in Lua (`_U(...)`, `Lang:t(...)`) but never defined.

### Backup History
Take dated, labelled snapshots of your mods/plugins folders. Restore any snapshot, or compare two of them to see exactly which files were added, removed, or changed.

---

## Installation

### Option 1: Download the Executable
Grab the latest `Sanitize V.exe` from the [Releases](https://github.com/mpriester8/SanitizeV/releases) page. No installation needed—just run it.

### Option 2: Run from Source

1. Make sure you have Python 3.12 or newer
2. Clone the repo:
   ```bash
   git clone https://github.com/mpriester8/SanitizeV.git
   cd SanitizeV
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run it:
   ```bash
   python src/main.py
   ```

### Building the Executable

Double-click `build.bat` or run:
```bash
pyinstaller --onefile --windowed --add-data "assets;assets" --name "Sanitize V" src/main.py
```

The `.exe` ends up in the `dist/` folder.

---

## Requirements

- Windows 10 or 11
- Python 3.12+ (only if running from source)
- Internet connection (for update checks)

---

## Auto-Updates

The app checks for updates automatically when you launch it. If there's a new version:

1. You'll get a notification
2. Click "Yes" to download and install
3. The new version launches automatically

No need to manually download anything.

---

## Permissions Legend

When scanning commands, you'll see these permission levels:

| Color | Permission | Meaning |
|-------|------------|---------|
| 🟢 Green | Everyone | No restrictions, any player can use it |
| 🟠 Orange | ACE | Requires server.cfg ACE permission |
| 🔴 Red | Admin | Requires admin rank in ESX/QBCore |
| 🔵 Blue | Job | Requires specific job (police, EMS, etc.) |
| 🟣 Purple | Custom | Resource-specific permission |

Hover over any permission in the app for a detailed explanation.

---

## Troubleshooting

**The app won't start**
- Make sure you have the Visual C++ Redistributable installed
- Try running as administrator

**Command scanner misses some commands**
- It looks for standard patterns (`RegisterCommand`, `ESX.RegisterCommand`, `QBCore.Commands.Add`, `chat:addSuggestion`)
- Custom command systems might not be detected

**Conflict detector finds too many false positives**
- It only flags YMAP files now (not manifests or other configs)
- Exact duplicates are usually safe to have

---

## Contributing

Found a bug? Have an idea? Open an issue or submit a PR. Just keep it clean and test your changes.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Credits

Built by [mpriester8](https://github.com/mpriester8). Thanks to everyone who's reported bugs and suggested features.
