"""
PySide6 frontend for Sanitize V.

Sidebar navigation, themed dark/light UI, toast notifications, command
palette, and a suite of FiveM development tools.
"""
from __future__ import annotations

import logging
import os
import re
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from constants import (
    DEFAULT_SOURCE_DIR, FOLDER1_NAME, FOLDER2_NAME, DEFAULT_XML_SOURCE_DIR,
    XML_FILENAME, VERSION, SETTINGS_SCHEMA,
)
from logic import move_files_logic, revert_files_logic, clear_cache_logic
from fivem_utils import (
    validate_manifest, validate_resources_folder, ManifestValidationResult,
    detect_conflicts, ConflictReport,
    fix_ymap_conflicts, YmapFixResult,
    get_quick_commands, CODE_SNIPPETS,
    scan_server_commands, ServerCommand,
)

import theme
import widgets
import command_palette
import mod_profiles
import manifest_fixer
import server_cfg as scfg
import dependency_graph
import scaffolder
import locale_checker
import backup_history
from log_tailer import LogTailWorker, LogLine

logger = logging.getLogger(__name__)


def resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), relative_path)


# ─────────────────────────────────────────────────────────────────────
# Main window
# ─────────────────────────────────────────────────────────────────────

class MainWindow(QtWidgets.QMainWindow):
    _toast_signal = QtCore.Signal(str, str, int)  # message, severity, duration_ms

    PAGE_HOME = 0
    PAGE_SANITIZE = 1
    PAGE_PROFILES = 2
    PAGE_GRAPHICS = 3
    PAGE_MANIFEST = 4
    PAGE_DEPGRAPH = 5
    PAGE_CONFLICTS = 6
    PAGE_COMMANDS = 7
    PAGE_LOCALES = 8
    PAGE_SCAFFOLD = 9
    PAGE_SERVER_CFG = 10
    PAGE_LOG_TAIL = 11
    PAGE_CONSOLE = 12
    PAGE_BACKUPS = 13
    PAGE_DEV = 14
    PAGE_SETTINGS = 15

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Sanitize V — v{VERSION}")
        self.resize(1180, 800)
        self.setMinimumSize(960, 640)

        icon_path = resource_path(os.path.join("assets", "app_icon.ico"))
        if not os.path.exists(icon_path):
            icon_path = resource_path(os.path.join("assets", "app_icon.png"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QtGui.QIcon(icon_path))

        # ── Layout: sidebar | stacked pages ─────────────────────────
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = widgets.Sidebar("Sanitize V", f"v{VERSION}")
        root.addWidget(self.sidebar)

        self.stack = QtWidgets.QStackedWidget()
        root.addWidget(self.stack, 1)

        self._scanned_commands: list[ServerCommand] = []
        self._last_conflict_report: Optional[ConflictReport] = None
        self._log_worker: Optional[LogTailWorker] = None
        self._tail_filter_regex: Optional[re.Pattern] = None

        # Build pages (order must match PAGE_* constants)
        self._build_sidebar_items()
        self.sidebar.section_changed.connect(self.stack.setCurrentIndex)

        self._build_home_page()
        self._build_sanitize_page()
        self._build_profiles_page()
        self._build_graphics_page()
        self._build_manifest_page()
        self._build_depgraph_page()
        self._build_conflicts_page()
        self._build_commands_page()
        self._build_locales_page()
        self._build_scaffold_page()
        self._build_server_cfg_page()
        self._build_log_tail_page()
        self._build_console_page()
        self._build_backups_page()
        self._build_dev_page()
        self._build_settings_page()

        self.sidebar.set_active(self.PAGE_HOME)
        self.stack.setCurrentIndex(self.PAGE_HOME)

        # Toast manager (bottom-right notifications)
        self.toasts = widgets.ToastManager(self)
        self._toast_signal.connect(self.toasts.show_toast)

        # Status bar (kept for hovered tooltips & long-running operations)
        self.status = self.statusBar()
        self.status.showMessage("Ready")

        # Command palette shortcut
        command_palette.install_shortcut(self, self._palette_actions)

    # Thread-safe toast helpers (call these from anywhere, including worker threads)
    def toast(self, message: str, severity: str = "info", duration_ms: int = 4000) -> None:
        self._toast_signal.emit(message, severity, duration_ms)

    # ─────────────────────────────────────────────────────────────────
    # Sidebar items
    # ─────────────────────────────────────────────────────────────────
    def _build_sidebar_items(self) -> None:
        sb = self.sidebar
        sb.add_section_header("Mods")
        sb.add_item("⌂", "Home")
        sb.add_item("⚙", "Sanitize / Restore")
        sb.add_item("⚑", "Mod Profiles")
        sb.add_section_header("Graphics & Resources")
        sb.add_item("◐", "Graphics Editor")
        sb.add_item("✓", "Manifest Validator")
        sb.add_item("⇆", "Dependency Graph")
        sb.add_item("≡", "Conflict Detector")
        sb.add_section_header("Server tools")
        sb.add_item("⌘", "Command Scanner")
        sb.add_item("✎", "Locale Checker")
        sb.add_item("✚", "Scaffold Resource")
        sb.add_item("◧", "server.cfg Editor")
        sb.add_item("≣", "Log Tailer")
        sb.add_item(">_", "Server Console")
        sb.add_section_header("Other")
        sb.add_item("↻", "Backups")
        sb.add_item("⚒", "Dev Utilities")
        sb.add_item("⚙", "Settings")
        sb.add_stretch()

        # Footer: a labeled theme toggle + Ctrl+K search hint
        footer_row = QtWidgets.QWidget()
        flay = QtWidgets.QHBoxLayout(footer_row)
        flay.setContentsMargins(0, 0, 0, 0)
        flay.setSpacing(8)

        self._theme_toggle = QtWidgets.QPushButton(self._theme_label())
        self._theme_toggle.setObjectName("GhostButton")
        self._theme_toggle.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._theme_toggle.setToolTip("Switch between dark and light themes")
        self._theme_toggle.clicked.connect(self._toggle_theme)
        flay.addWidget(self._theme_toggle, 1)

        sb.add_footer_widget(footer_row)

        hint = QtWidgets.QLabel("Press  Ctrl+K  to search")
        hint.setObjectName("Dim")
        hint.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("font-size: 9pt; padding-top: 4px;")
        sb.add_footer_widget(hint)

    @staticmethod
    def _path_with_browse(path_widget: QtWidgets.QWidget, on_browse) -> QtWidgets.QWidget:
        """Wrap a path widget with a labeled Browse… button (for QFormLayout rows)."""
        container = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(container)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        h.addWidget(path_widget, 1)
        btn = QtWidgets.QPushButton("Browse…")
        btn.clicked.connect(on_browse)
        h.addWidget(btn)
        return container

    def _theme_label(self) -> str:
        mode = theme.get_state().mode
        if mode == "dark":
            return "☾  Dark theme"
        if mode == "light":
            return "☀  Light theme"
        return "◐  System theme"

    def _goto(self, page: int) -> None:
        self.sidebar.set_active(page)
        self.stack.setCurrentIndex(page)

    # ─────────────────────────────────────────────────────────────────
    # Page: Home (dashboard)
    # ─────────────────────────────────────────────────────────────────
    def _build_home_page(self) -> None:
        page = QtWidgets.QWidget()
        outer = QtWidgets.QVBoxLayout(page)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(14)

        title = QtWidgets.QLabel("Welcome to Sanitize V")
        title.setObjectName("Heading")
        subtitle = QtWidgets.QLabel("Your FiveM developer toolkit. Pick a tool from the sidebar, or press Ctrl+K.")
        subtitle.setObjectName("Muted")
        outer.addWidget(title)
        outer.addWidget(subtitle)

        # Quick-access grid of cards
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(12)
        outer.addLayout(grid)

        def quick_card(emoji: str, label: str, desc: str, target: int) -> widgets.Card:
            card = widgets.Card()
            card.layout().setSpacing(6)
            row = QtWidgets.QHBoxLayout()
            row.setSpacing(10)
            ic = QtWidgets.QLabel(emoji)
            ic.setStyleSheet("font-size: 22pt;")
            row.addWidget(ic)
            colv = QtWidgets.QVBoxLayout()
            tl = QtWidgets.QLabel(label); tl.setObjectName("Subheading")
            dl = QtWidgets.QLabel(desc); dl.setObjectName("Muted"); dl.setWordWrap(True)
            colv.addWidget(tl); colv.addWidget(dl)
            row.addLayout(colv, 1)
            card.add_layout(row)
            btn = QtWidgets.QPushButton("Open →")
            btn.setObjectName("GhostButton")
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda: self._goto(target))
            card.add(btn)
            return card

        grid.addWidget(quick_card("⚙", "Sanitize / Restore", "Toggle mods on/off and clear caches.", self.PAGE_SANITIZE), 0, 0)
        grid.addWidget(quick_card("⚑", "Mod Profiles", "Switch between named mod loadouts in one click.", self.PAGE_PROFILES), 0, 1)
        grid.addWidget(quick_card("✓", "Manifest Validator", "Scan and auto-fix fxmanifest.lua issues.", self.PAGE_MANIFEST), 0, 2)
        grid.addWidget(quick_card("⇆", "Dependency Graph", "Visualize how resources depend on each other.", self.PAGE_DEPGRAPH), 1, 0)
        grid.addWidget(quick_card("≣", "Log Tailer", "Tail server.log live with colored levels and filtering.", self.PAGE_LOG_TAIL), 1, 1)
        grid.addWidget(quick_card("◧", "server.cfg Editor", "Edit common convars with descriptions and validation.", self.PAGE_SERVER_CFG), 1, 2)
        grid.addWidget(quick_card("⌘", "Command Scanner", "Find every registered command across your server.", self.PAGE_COMMANDS), 2, 0)
        grid.addWidget(quick_card("✚", "Scaffold Resource", "Generate a new resource (basic, ESX, or QBCore).", self.PAGE_SCAFFOLD), 2, 1)
        grid.addWidget(quick_card("↻", "Backups", "Take dated snapshots of mods and diff between them.", self.PAGE_BACKUPS), 2, 2)

        # Tip card
        tip = widgets.Card()
        tip.layout().setSpacing(4)
        tip_title = QtWidgets.QLabel("Pro tip"); tip_title.setObjectName("Subheading")
        tip_text = QtWidgets.QLabel(
            "Press <b>Ctrl+K</b> anywhere to open the command palette — fuzzy-search every tool, recent folder, and snippet."
        )
        tip_text.setWordWrap(True)
        tip.add(tip_title); tip.add(tip_text)
        outer.addWidget(tip)
        outer.addStretch()

        self.stack.addWidget(page)

    # ─────────────────────────────────────────────────────────────────
    # Page: Sanitize / Restore
    # ─────────────────────────────────────────────────────────────────
    def _build_sanitize_page(self) -> None:
        page = _scrollable()
        layout = page.layout
        _page_title(layout, "Sanitize / Restore", "Move your mods aside, then restore them when you're done playing online.")

        card = widgets.Card()
        grid = QtWidgets.QGridLayout()
        grid.setColumnStretch(1, 1)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        grid.addWidget(QtWidgets.QLabel("Source directory"), 0, 0)
        self.source_edit = widgets.RecentPathLineEdit("source_dir", "FiveM data folder", DEFAULT_SOURCE_DIR)
        widgets.enable_folder_drop(self.source_edit)
        grid.addWidget(self.source_edit, 0, 1)
        btn_src = QtWidgets.QPushButton("Browse…")
        btn_src.clicked.connect(lambda: _pick_dir(self, self.source_edit, "Select Source Directory"))
        grid.addWidget(btn_src, 0, 2)

        grid.addWidget(QtWidgets.QLabel("Backup directory"), 1, 0)
        self.backup_edit = widgets.RecentPathLineEdit("backup_dir", "Where mods are stashed when sanitized")
        widgets.enable_folder_drop(self.backup_edit)
        grid.addWidget(self.backup_edit, 1, 1)
        btn_bk = QtWidgets.QPushButton("Browse…")
        btn_bk.clicked.connect(lambda: _pick_dir(self, self.backup_edit, "Select Backup Directory"))
        grid.addWidget(btn_bk, 1, 2)

        card.add_layout(grid)

        opts = QtWidgets.QHBoxLayout()
        self.chk_mods = QtWidgets.QCheckBox("Move 'mods' folder"); self.chk_mods.setChecked(True)
        self.chk_plugins = QtWidgets.QCheckBox("Move 'plugins' folder"); self.chk_plugins.setChecked(True)
        opts.addWidget(self.chk_mods); opts.addWidget(self.chk_plugins); opts.addStretch()
        card.add_layout(opts)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        self.btn_sanitize = QtWidgets.QPushButton("Sanitize"); self.btn_sanitize.setObjectName("PrimaryButton")
        self.btn_sanitize.clicked.connect(self._run_sanitize)
        self.btn_restore = QtWidgets.QPushButton("Restore")
        self.btn_restore.clicked.connect(self._run_restore)
        self.btn_clear_cache = QtWidgets.QPushButton("Clear cache")
        self.btn_clear_cache.clicked.connect(self._run_clear_cache)
        btn_row.addWidget(self.btn_sanitize); btn_row.addWidget(self.btn_restore); btn_row.addWidget(self.btn_clear_cache)
        card.add_layout(btn_row)

        self.progress = QtWidgets.QProgressBar(); self.progress.setRange(0, 100)
        card.add(self.progress)
        layout.addWidget(card)

        log_card = widgets.Card("Log")
        self.log = QtWidgets.QTextEdit(); self.log.setReadOnly(True); self.log.setObjectName("Code")
        log_card.add(self.log)
        layout.addWidget(log_card, 1)

        self.stack.addWidget(page.widget)

    def _run_sanitize(self) -> None:
        src = self.source_edit.text(); dest = self.backup_edit.text()
        if not dest:
            self.toasts.warning("Pick a backup directory first."); return
        self.source_edit.remember(); self.backup_edit.remember()
        include_mods = self.chk_mods.isChecked(); include_plugins = self.chk_plugins.isChecked()

        def worker():
            success = move_files_logic(
                src, FOLDER1_NAME, FOLDER2_NAME, DEFAULT_XML_SOURCE_DIR, XML_FILENAME, "",
                dest, include_mods=include_mods, include_plugins=include_plugins,
                include_xml=False, log_callback=self._append_log,
                progress_callback=self._progress_cb, cancel_event=None,
            )
            self._progress_cb(0, 1)
            QtCore.QMetaObject.invokeMethod(
                self, "_toast_result", QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(bool, success), QtCore.Q_ARG(str, "Sanitize"),
            )
        threading.Thread(target=worker, daemon=True).start()

    def _run_restore(self) -> None:
        src = self.source_edit.text(); dest = self.backup_edit.text()
        if not dest:
            self.toasts.warning("Pick a backup directory first."); return
        self.source_edit.remember(); self.backup_edit.remember()
        include_mods = self.chk_mods.isChecked(); include_plugins = self.chk_plugins.isChecked()

        def worker():
            success = revert_files_logic(
                src, FOLDER1_NAME, FOLDER2_NAME, DEFAULT_XML_SOURCE_DIR, XML_FILENAME, dest,
                include_mods=include_mods, include_plugins=include_plugins,
                include_xml=False, restore_xml_path=None, log_callback=self._append_log,
                progress_callback=self._progress_cb, cancel_event=None,
            )
            self._progress_cb(0, 1)
            QtCore.QMetaObject.invokeMethod(
                self, "_toast_result", QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(bool, success), QtCore.Q_ARG(str, "Restore"),
            )
        threading.Thread(target=worker, daemon=True).start()

    def _run_clear_cache(self) -> None:
        src = self.source_edit.text()
        if not src:
            self.toasts.warning("Source directory is invalid."); return
        if QtWidgets.QMessageBox.question(self, "Confirm", "Delete all cache files? This cannot be undone.") != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        def worker():
            success, timestamp = clear_cache_logic(src, self._append_log, progress_callback=self._progress_cb, cancel_event=None)
            self._progress_cb(0, 1)
            QtCore.QMetaObject.invokeMethod(
                self, "_toast_result", QtCore.Qt.QueuedConnection,
                QtCore.Q_ARG(bool, success), QtCore.Q_ARG(str, f"Cache clear (at {timestamp})" if timestamp else "Cache clear"),
            )
        threading.Thread(target=worker, daemon=True).start()

    @QtCore.Slot(bool, str)
    def _toast_result(self, success: bool, label: str) -> None:
        (self.toasts.success if success else self.toasts.error)(f"{label} {'completed' if success else 'reported issues'}.")

    def _append_log(self, msg: str) -> None:
        QtCore.QMetaObject.invokeMethod(self.log, "append", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, msg))

    def _progress_cb(self, completed: int, total: int) -> None:
        pct = int((completed / total) * 100) if total else 0
        QtCore.QMetaObject.invokeMethod(self.progress, "setValue", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(int, pct))

    # ─────────────────────────────────────────────────────────────────
    # Page: Mod Profiles
    # ─────────────────────────────────────────────────────────────────
    def _build_profiles_page(self) -> None:
        page = _scrollable()
        layout = page.layout
        _page_title(layout, "Mod Profiles", "Save named loadouts of mods/plugins and switch between them with one click.")

        cfg_card = widgets.Card("Locations")
        f = QtWidgets.QFormLayout()
        self.profile_source = widgets.RecentPathLineEdit("profile_source", "FiveM source folder", DEFAULT_SOURCE_DIR)
        self.profile_backup = widgets.RecentPathLineEdit("profile_backup", "Where to store the profile stash")
        widgets.enable_folder_drop(self.profile_source); widgets.enable_folder_drop(self.profile_backup)
        for w in (self.profile_source.lineEdit(), self.profile_backup.lineEdit()):
            w.editingFinished.connect(self._refresh_profiles)
        f.addRow("Source", self._path_with_browse(
            self.profile_source,
            lambda: _pick_dir(self, self.profile_source, "Select FiveM source folder"),
        ))
        f.addRow("Backup", self._path_with_browse(
            self.profile_backup,
            lambda: _pick_dir(self, self.profile_backup, "Select profile stash folder"),
        ))
        cfg_card.add_layout(f)
        layout.addWidget(cfg_card)

        list_card = widgets.Card("Profiles")
        toolbar = QtWidgets.QHBoxLayout()
        btn_new = QtWidgets.QPushButton("New profile…"); btn_new.setObjectName("PrimaryButton")
        btn_new.clicked.connect(self._create_profile)
        btn_capture = QtWidgets.QPushButton("Capture current → active profile")
        btn_capture.clicked.connect(self._capture_active_profile)
        btn_refresh = QtWidgets.QPushButton("Refresh"); btn_refresh.setObjectName("GhostButton")
        btn_refresh.clicked.connect(self._refresh_profiles)
        toolbar.addWidget(btn_new); toolbar.addWidget(btn_capture); toolbar.addStretch(); toolbar.addWidget(btn_refresh)
        list_card.add_layout(toolbar)

        self.profile_list = QtWidgets.QTreeWidget()
        self.profile_list.setHeaderLabels(["Profile", "Folders", "Last used", "Status"])
        self.profile_list.setRootIsDecorated(False)
        self.profile_list.setAlternatingRowColors(True)
        self.profile_list.itemDoubleClicked.connect(lambda *_: self._activate_profile())
        list_card.add(self.profile_list)

        btn_row = QtWidgets.QHBoxLayout()
        btn_activate = QtWidgets.QPushButton("Activate"); btn_activate.setObjectName("PrimaryButton")
        btn_activate.clicked.connect(self._activate_profile)
        btn_delete = QtWidgets.QPushButton("Delete…"); btn_delete.setObjectName("DangerButton")
        btn_delete.clicked.connect(self._delete_profile)
        btn_row.addStretch(); btn_row.addWidget(btn_activate); btn_row.addWidget(btn_delete)
        list_card.add_layout(btn_row)
        layout.addWidget(list_card, 1)

        self.stack.addWidget(page.widget)

    def _load_profile_store(self) -> Optional[mod_profiles.ProfileStore]:
        backup = self.profile_backup.text().strip()
        if not backup:
            return None
        return mod_profiles.load_store(backup)

    @QtCore.Slot()
    def _refresh_profiles(self) -> None:
        store = self._load_profile_store()
        self.profile_list.clear()
        if store is None:
            return
        for p in store.profiles:
            item = QtWidgets.QTreeWidgetItem([
                p.name, ", ".join(p.folders), p.last_used or "—",
                "Active" if store.active == p.name else "",
            ])
            if store.active == p.name:
                f = item.font(0); f.setBold(True)
                for col in range(4):
                    item.setFont(col, f)
                    item.setForeground(col, QtGui.QColor(theme.palette().accent))
            self.profile_list.addTopLevelItem(item)

    def _selected_profile(self) -> Optional[str]:
        item = self.profile_list.currentItem()
        return item.text(0) if item else None

    def _create_profile(self) -> None:
        store = self._load_profile_store()
        if store is None:
            self.toasts.warning("Pick a backup directory first."); return
        name, ok = QtWidgets.QInputDialog.getText(self, "New profile", "Profile name:")
        if not ok or not name.strip():
            return
        desc, _ = QtWidgets.QInputDialog.getText(self, "Description", "Optional description:")
        try:
            mod_profiles.create_profile(store, name.strip(), desc.strip())
            self.toasts.success(f"Created profile '{name}'")
            self._refresh_profiles()
        except ValueError as e:
            self.toasts.error(str(e))

    def _capture_active_profile(self) -> None:
        store = self._load_profile_store()
        if store is None or store.active is None:
            self.toasts.warning("Activate a profile first."); return
        try:
            mod_profiles.capture_current(store, store.active, self.profile_source.text())
            self.toasts.success(f"Snapshot saved to profile '{store.active}'")
        except Exception as e:
            self.toasts.error(str(e))

    def _activate_profile(self) -> None:
        store = self._load_profile_store()
        if store is None:
            self.toasts.warning("Pick a backup directory first."); return
        name = self._selected_profile()
        if not name:
            self.toasts.warning("Select a profile first."); return

        def worker():
            try:
                mod_profiles.activate_profile(store, name, self.profile_source.text())
                self.toast(f"Activated profile '{name}'", "success")
                QtCore.QMetaObject.invokeMethod(self, "_refresh_profiles", QtCore.Qt.QueuedConnection)
            except Exception as e:
                self.toast(str(e), "error", 6000)
        threading.Thread(target=worker, daemon=True).start()

    def _delete_profile(self) -> None:
        store = self._load_profile_store()
        name = self._selected_profile()
        if not store or not name:
            return
        choice = QtWidgets.QMessageBox.question(
            self, "Delete profile",
            f"Delete '{name}' from the index AND remove its stash on disk?\n\nClick 'Yes' to delete both, 'No' to only forget it.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No | QtWidgets.QMessageBox.StandardButton.Cancel,
        )
        if choice == QtWidgets.QMessageBox.StandardButton.Cancel:
            return
        mod_profiles.delete_profile(store, name, remove_files=(choice == QtWidgets.QMessageBox.StandardButton.Yes))
        self.toasts.info(f"Deleted profile '{name}'")
        self._refresh_profiles()

    # ─────────────────────────────────────────────────────────────────
    # Page: Graphics Editor (XML)
    # ─────────────────────────────────────────────────────────────────
    def _build_graphics_page(self) -> None:
        import xml.etree.ElementTree as ET
        page = _scrollable()
        layout = page.layout
        _page_title(layout, "Graphics Editor", "Tweak gta5_settings.xml without digging through tags.")

        file_card = widgets.Card("Settings file")
        row = QtWidgets.QHBoxLayout()
        self.gfx_xml_path = widgets.RecentPathLineEdit("gfx_xml", "Path to gta5_settings.xml",
                                                       os.path.join(DEFAULT_XML_SOURCE_DIR, XML_FILENAME))
        widgets.enable_folder_drop(self.gfx_xml_path)
        row.addWidget(self.gfx_xml_path, 1)
        btn_browse = QtWidgets.QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse_gfx_xml)
        row.addWidget(btn_browse)
        btn_load = QtWidgets.QPushButton("Load")
        btn_load.clicked.connect(self._load_gfx_settings)
        row.addWidget(btn_load)
        file_card.add_layout(row)
        layout.addWidget(file_card)

        self.gfx_settings_card = widgets.Card("Settings")
        self.gfx_settings_widget = QtWidgets.QWidget()
        self.gfx_settings_layout = QtWidgets.QGridLayout(self.gfx_settings_widget)
        self.gfx_settings_layout.setSpacing(8)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True); scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setWidget(self.gfx_settings_widget)
        self.gfx_settings_card.add(scroll)
        layout.addWidget(self.gfx_settings_card, 1)

        self.gfx_editor_vars: dict[str, QtWidgets.QWidget] = {}
        self.gfx_current_tree = None

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        btn_save = QtWidgets.QPushButton("Save Settings")
        btn_save.setObjectName("PrimaryButton")
        btn_save.clicked.connect(self._save_gfx_settings)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

        if os.path.exists(self.gfx_xml_path.text()):
            QtCore.QTimer.singleShot(150, self._load_gfx_settings)

        self.stack.addWidget(page.widget)

    def _browse_gfx_xml(self) -> None:
        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select XML", "", "XML Files (*.xml)")
        if filepath:
            self.gfx_xml_path.setText(filepath)

    def _load_gfx_settings(self) -> None:
        import xml.etree.ElementTree as ET
        try:
            from security_utils import validate_xml_safe, SecurityError
        except ImportError:
            validate_xml_safe = None; SecurityError = Exception

        path = self.gfx_xml_path.text()
        if not os.path.exists(path):
            self.toasts.error("File not found."); return
        if validate_xml_safe:
            try:
                validate_xml_safe(path, max_size_mb=10)
            except SecurityError as e:
                self.toasts.error(f"XML validation failed: {e}"); return
        try:
            tree = ET.parse(path); self.gfx_current_tree = tree; root = tree.getroot()

            while self.gfx_settings_layout.count():
                item = self.gfx_settings_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self.gfx_editor_vars.clear()

            graphics, video = [], []
            for tag, meta in SETTINGS_SCHEMA.items():
                (video if meta.get("section") == "video" else graphics).append((tag, meta))

            row = 0
            for label_text, group in [("Graphics", graphics), ("Video", video)]:
                if not group:
                    continue
                hdr = QtWidgets.QLabel(label_text); hdr.setObjectName("Subheading")
                self.gfx_settings_layout.addWidget(hdr, row, 0, 1, 4); row += 1
                for tag, meta in group:
                    row = self._add_gfx_setting_row(root, tag, meta, row)
                row += 1
            self.gfx_settings_layout.setRowStretch(row, 1)
            self.gfx_xml_path.remember()
            self.toasts.success(f"Loaded {os.path.basename(path)}")
        except Exception as e:
            self.toasts.error(f"Failed to parse XML: {e}")

    def _add_gfx_setting_row(self, root, tag: str, meta: dict, row: int) -> int:
        section_node = root.find(meta.get("section", "graphics"))
        current_val = None
        if section_node is not None:
            node = section_node.find(tag)
            if node is not None:
                current_val = node.get("value")
        if current_val is None:
            current_val = meta["options"][0][0] if meta["type"] == "combobox" else str(meta["xml_range"][0])

        label = QtWidgets.QLabel(meta["label"]); label.setMinimumWidth(180)
        self.gfx_settings_layout.addWidget(label, row, 0)

        if meta["type"] == "combobox":
            combo = QtWidgets.QComboBox(); combo.setMinimumWidth(150); cur = 0
            for idx, (val, desc) in enumerate(meta["options"]):
                combo.addItem(desc, val)
                if str(val).lower() == str(current_val).lower(): cur = idx
            combo.setCurrentIndex(cur)
            self.gfx_settings_layout.addWidget(combo, row, 1)
            self.gfx_editor_vars[tag] = combo
        else:
            ui_min, ui_max = meta["ui_range"]; xml_min, xml_max = meta["xml_range"]
            try:
                f_val = float(current_val)
                ratio = (f_val - xml_min) / (xml_max - xml_min) if xml_max != xml_min else 0
                ui_val = int(ui_min + ratio * (ui_max - ui_min))
            except ValueError:
                ui_val = ui_min
            slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            slider.setRange(ui_min, ui_max); slider.setValue(ui_val); slider.setMinimumWidth(120)
            value_label = QtWidgets.QLabel(str(ui_val)); value_label.setMinimumWidth(30)
            slider.valueChanged.connect(lambda v, lbl=value_label: lbl.setText(str(v)))
            self.gfx_settings_layout.addWidget(slider, row, 1)
            self.gfx_settings_layout.addWidget(value_label, row, 2)
            self.gfx_editor_vars[tag] = slider
        return row + 1

    def _save_gfx_settings(self) -> None:
        import xml.etree.ElementTree as ET
        import shutil
        if not self.gfx_current_tree:
            self.toasts.warning("Load a file first."); return
        try:
            root = self.gfx_current_tree.getroot()
            for sec in ["graphics", "video"]:
                if root.find(sec) is None:
                    ET.SubElement(root, sec)
            for tag, meta in SETTINGS_SCHEMA.items():
                section_node = root.find(meta.get("section", "graphics"))
                widget = self.gfx_editor_vars.get(tag)
                if not widget:
                    continue
                if meta["type"] == "combobox":
                    final = widget.currentData()
                else:
                    ui_val = widget.value()
                    ui_min, ui_max = meta["ui_range"]; xml_min, xml_max = meta["xml_range"]
                    ratio = (ui_val - ui_min) / (ui_max - ui_min) if ui_max != ui_min else 0
                    final = f"{xml_min + ratio * (xml_max - xml_min):.6f}"
                node = section_node.find(tag)
                if node is not None:
                    node.set("value", str(final))
                else:
                    ET.SubElement(section_node, tag).set("value", str(final))

            ref_combo = self.gfx_editor_vars.get("ReflectionQuality")
            if isinstance(ref_combo, QtWidgets.QComboBox):
                mip = "true" if ref_combo.currentData() in ["2", "3"] else "false"
                g = root.find("graphics")
                if g is not None:
                    mnode = g.find("Reflection_MipBlur")
                    if mnode is None:
                        mnode = ET.SubElement(g, "Reflection_MipBlur")
                    mnode.set("value", mip)

            target = self.gfx_xml_path.text()
            if os.path.exists(target):
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                shutil.copy2(target, f"{target}.{ts}.bak")
            self.gfx_current_tree.write(target, encoding="unicode", xml_declaration=True)
            self.toasts.success(f"Settings saved · backup created")
        except Exception as e:
            self.toasts.error(f"Failed to save: {e}")

    # ─────────────────────────────────────────────────────────────────
    # Page: Manifest Validator (with auto-fix)
    # ─────────────────────────────────────────────────────────────────
    def _build_manifest_page(self) -> None:
        page = _scrollable()
        layout = page.layout
        _page_title(layout, "Manifest Validator", "Find issues in fxmanifest.lua / __resource.lua — and auto-fix the safe ones.")

        path_card = widgets.Card()
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Resources folder"))
        self.manifest_path_edit = widgets.RecentPathLineEdit("manifest_path", "Path to resources/ or a single resource")
        widgets.enable_folder_drop(self.manifest_path_edit)
        row.addWidget(self.manifest_path_edit, 1)
        btn = QtWidgets.QPushButton("Browse…")
        btn.clicked.connect(lambda: _pick_dir(self, self.manifest_path_edit, "Select Resources Folder"))
        row.addWidget(btn)
        path_card.add_layout(row)

        btns = QtWidgets.QHBoxLayout()
        b_one = QtWidgets.QPushButton("Validate single resource"); b_one.clicked.connect(self._validate_single_manifest)
        b_all = QtWidgets.QPushButton("Validate all resources"); b_all.setObjectName("PrimaryButton"); b_all.clicked.connect(self._validate_all_manifests)
        b_fix = QtWidgets.QPushButton("Auto-fix selected"); b_fix.clicked.connect(self._auto_fix_manifest)
        b_fix_all = QtWidgets.QPushButton("Auto-fix all invalid"); b_fix_all.clicked.connect(self._auto_fix_all_manifests)
        btns.addWidget(b_one); btns.addWidget(b_all); btns.addStretch(); btns.addWidget(b_fix); btns.addWidget(b_fix_all)
        path_card.add_layout(btns)
        layout.addWidget(path_card)

        tree_card = widgets.Card("Results")
        self.manifest_tree = QtWidgets.QTreeWidget()
        self.manifest_tree.setHeaderLabels(["Resource / Issue", "Severity", "Line"])
        self.manifest_tree.setColumnWidth(0, 420); self.manifest_tree.setColumnWidth(1, 80)
        self.manifest_tree.setAlternatingRowColors(True)
        tree_card.add(self.manifest_tree)
        layout.addWidget(tree_card, 1)

        self.stack.addWidget(page.widget)

    def _validate_single_manifest(self) -> None:
        path = self.manifest_path_edit.text()
        if not path:
            self.toasts.warning("Pick a path."); return
        self.manifest_path_edit.remember()
        self._display_manifest_results([validate_manifest(path)])

    def _validate_all_manifests(self) -> None:
        path = self.manifest_path_edit.text()
        if not path:
            self.toasts.warning("Pick a path."); return
        results = validate_resources_folder(path)
        if not results:
            self.toasts.info("No resources found in that folder."); return
        self.manifest_path_edit.remember()
        self._display_manifest_results(results)

    def _display_manifest_results(self, results: list[ManifestValidationResult]) -> None:
        self.manifest_tree.clear()
        for result in results:
            item = QtWidgets.QTreeWidgetItem([
                os.path.basename(os.path.dirname(result.path)) or result.path,
                "✓ Valid" if result.is_valid else "✗ Invalid",
                "",
            ])
            item.setForeground(1, QtGui.QColor(theme.palette().success if result.is_valid else theme.palette().danger))
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, result.path)
            for issue in result.issues:
                color = {
                    "error": theme.palette().danger,
                    "warning": theme.palette().warning,
                    "info": theme.palette().info,
                }.get(issue.severity, theme.palette().text)
                child = QtWidgets.QTreeWidgetItem([issue.message, issue.severity.upper(), str(issue.line) if issue.line else ""])
                child.setForeground(1, QtGui.QColor(color))
                item.addChild(child)
            self.manifest_tree.addTopLevelItem(item)
            item.setExpanded(True)
        self.toasts.success(f"Validated {len(results)} resource(s)")

    def _auto_fix_manifest(self) -> None:
        item = self.manifest_tree.currentItem()
        if not item:
            self.toasts.warning("Select a resource."); return
        top = item
        while top.parent():
            top = top.parent()
        path = top.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if not path:
            return
        result = manifest_fixer.auto_fix(path)
        if result.success and result.changes:
            self.toasts.success(f"Fixed: {', '.join(result.changes[:3])}{'…' if len(result.changes) > 3 else ''}")
            self._validate_single_manifest()
        elif result.error == "Nothing to fix":
            self.toasts.info("Nothing to fix on that resource.")
        else:
            self.toasts.error(result.error or "Auto-fix failed")

    def _auto_fix_all_manifests(self) -> None:
        path = self.manifest_path_edit.text()
        if not path:
            return
        results = validate_resources_folder(path)
        fixed = 0
        for r in results:
            if r.is_valid:
                continue
            res = manifest_fixer.auto_fix(r.path)
            if res.success and res.changes:
                fixed += 1
        self.toasts.success(f"Auto-fixed {fixed} resource(s)")
        self._validate_all_manifests()

    # ─────────────────────────────────────────────────────────────────
    # Page: Dependency Graph
    # ─────────────────────────────────────────────────────────────────
    def _build_depgraph_page(self) -> None:
        page = _scrollable()
        layout = page.layout
        _page_title(layout, "Dependency Graph", "Map of how your resources depend on each other.")

        path_card = widgets.Card()
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Resources folder"))
        self.dep_path = widgets.RecentPathLineEdit("dep_path", "Path to resources/")
        widgets.enable_folder_drop(self.dep_path)
        row.addWidget(self.dep_path, 1)
        btn = QtWidgets.QPushButton("Browse…"); btn.clicked.connect(lambda: _pick_dir(self, self.dep_path, "Select Resources Folder"))
        row.addWidget(btn)
        btn_build = QtWidgets.QPushButton("Build graph"); btn_build.setObjectName("PrimaryButton")
        btn_build.clicked.connect(self._build_dep_graph)
        row.addWidget(btn_build)
        path_card.add_layout(row)
        layout.addWidget(path_card)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        self.dep_tree = QtWidgets.QTreeWidget()
        self.dep_tree.setHeaderLabels(["Resource", "Deps", "Used by", "Missing"])
        self.dep_tree.setColumnWidth(0, 260)
        self.dep_tree.setAlternatingRowColors(True)
        self.dep_tree.currentItemChanged.connect(self._on_dep_select)
        splitter.addWidget(self.dep_tree)

        side = QtWidgets.QWidget()
        side_lay = QtWidgets.QVBoxLayout(side); side_lay.setContentsMargins(8, 0, 0, 0)
        self.dep_details = QtWidgets.QTextEdit(); self.dep_details.setReadOnly(True)
        side_lay.addWidget(self.dep_details)
        splitter.addWidget(side)
        splitter.setSizes([520, 380])

        self.stack.addWidget(page.widget)

    def _build_dep_graph(self) -> None:
        path = self.dep_path.text()
        if not path:
            self.toasts.warning("Pick a resources folder."); return
        self.dep_path.remember()
        graph = dependency_graph.build_graph(path)
        self._current_graph = graph
        self.dep_tree.clear()
        for name in sorted(graph.nodes):
            node = graph.nodes[name]
            item = QtWidgets.QTreeWidgetItem([
                name,
                str(len(node.dependencies)),
                str(len(node.referenced_by)),
                str(len(node.missing_deps)),
            ])
            if node.missing_deps:
                item.setForeground(3, QtGui.QColor(theme.palette().danger))
            self.dep_tree.addTopLevelItem(item)

        msg_parts = [f"{len(graph.nodes)} resources"]
        if graph.cycles:
            msg_parts.append(f"{len(graph.cycles)} cycle(s)")
        missing = sum(len(n.missing_deps) for n in graph.nodes.values())
        if missing:
            msg_parts.append(f"{missing} missing dep refs")
        self.toasts.success(" · ".join(msg_parts))

        if graph.cycles:
            self.dep_details.setPlainText(
                "Cycles detected:\n\n" + "\n".join(" → ".join(c) for c in graph.cycles)
            )

    def _on_dep_select(self, current, _previous) -> None:
        if not current or not hasattr(self, "_current_graph"):
            return
        name = current.text(0)
        node = self._current_graph.nodes.get(name)
        if not node:
            return
        lines = [f"<b>{node.name}</b>", f"<span style='color:{theme.palette().text_muted}'>{node.path}</span>", ""]
        lines.append("<b>Dependencies</b>")
        lines.append("  " + (", ".join(node.dependencies) if node.dependencies else "—"))
        if node.missing_deps:
            color = theme.palette().danger
            lines.append(f"<span style='color:{color}'><b>Missing:</b> {', '.join(node.missing_deps)}</span>")
        lines.append("")
        lines.append("<b>Used by</b>")
        lines.append("  " + (", ".join(node.referenced_by) if node.referenced_by else "—"))
        lines.append("")
        lines.append("<b>Exports</b>")
        lines.append("  " + (", ".join(node.exports) if node.exports else "—"))
        self.dep_details.setHtml("<br/>".join(lines))

    # ─────────────────────────────────────────────────────────────────
    # Page: Conflict Detector
    # ─────────────────────────────────────────────────────────────────
    def _build_conflicts_page(self) -> None:
        page = _scrollable()
        layout = page.layout
        _page_title(layout, "Conflict Detector", "Spot duplicate YMAPs and other files that cause in-game issues.")

        path_card = widgets.Card("Scan location")
        prow = QtWidgets.QHBoxLayout()
        prow.addWidget(QtWidgets.QLabel("Resources folder"))
        self.conflict_folder = widgets.RecentPathLineEdit("conflict_path", "Path to resources/")
        widgets.enable_folder_drop(self.conflict_folder)
        prow.addWidget(self.conflict_folder, 1)
        bb = QtWidgets.QPushButton("Browse…"); bb.clicked.connect(lambda: _pick_dir(self, self.conflict_folder, "Select Resources Folder"))
        prow.addWidget(bb)
        path_card.add_layout(prow)

        opts = QtWidgets.QHBoxLayout()
        self.conflict_check_hashes = QtWidgets.QCheckBox("Compare file contents (slower but exact)")
        self.conflict_check_hashes.setChecked(True)
        opts.addWidget(self.conflict_check_hashes); opts.addStretch()
        self.conflict_scan_btn = QtWidgets.QPushButton("Scan for conflicts"); self.conflict_scan_btn.setObjectName("PrimaryButton")
        self.conflict_scan_btn.clicked.connect(self._run_conflict_scan)
        opts.addWidget(self.conflict_scan_btn)
        path_card.add_layout(opts)
        layout.addWidget(path_card)

        # Summary cards row
        summary_row = QtWidgets.QHBoxLayout(); summary_row.setSpacing(12)
        self.dup_count_label = self._summary_card(summary_row, "Duplicate files", "0", theme.palette().warning)
        self.col_count_label = self._summary_card(summary_row, "YMAP conflicts", "0", theme.palette().danger)
        self.total_count_label = self._summary_card(summary_row, "Total issues", "0", theme.palette().info)
        layout.addLayout(summary_row)

        tree_card = widgets.Card("Conflict details")
        self.conflict_tree = QtWidgets.QTreeWidget()
        self.conflict_tree.setHeaderLabels(["File / type", "Location(s)"])
        self.conflict_tree.setColumnWidth(0, 280)
        self.conflict_tree.setAlternatingRowColors(True)
        tree_card.add(self.conflict_tree)
        layout.addWidget(tree_card, 1)

        export_row = QtWidgets.QHBoxLayout()
        export_row.addStretch()
        btn_copy = QtWidgets.QPushButton("Copy to clipboard"); btn_copy.clicked.connect(self._copy_conflicts_to_clipboard)
        btn_export = QtWidgets.QPushButton("Export…"); btn_export.clicked.connect(self._export_conflict_report)
        self.conflict_fix_btn = QtWidgets.QPushButton("Fix YMAP conflicts…")
        self.conflict_fix_btn.setToolTip(
            "Attempt to automatically fix detected conflicts:\n"
            "• Duplicate YMAPs (same content) — delete extra copies, keep first\n"
            "• .ymap.xml name collisions — merge unique entities into primary,\n"
            "  discard duplicates, delete secondary (resolves streaming conflict)\n"
            "• Binary .ymap collisions — entity-aware fix:\n"
            "    - True duplicates (no unique entities) → secondary deleted safely\n"
            "    - Files with unique entities → skipped; fix log lists exactly\n"
            "      which archetype hashes/positions need manual CodeWalker merge\n"
            "  (RSC7 binary format cannot be safely auto-merged without CodeWalker)\n\n"
            "A .bak backup is written next to every modified file."
        )
        self.conflict_fix_btn.clicked.connect(self._run_fix_conflicts)
        export_row.addWidget(btn_copy); export_row.addWidget(btn_export); export_row.addWidget(self.conflict_fix_btn)
        layout.addLayout(export_row)

        self.stack.addWidget(page.widget)

    def _summary_card(self, parent_layout: QtWidgets.QHBoxLayout, label: str, value: str, color: str) -> QtWidgets.QLabel:
        card = widgets.Card()
        big = QtWidgets.QLabel(value)
        big.setStyleSheet(f"font-size: 26pt; font-weight: 700; color: {color};")
        big.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        desc = QtWidgets.QLabel(label); desc.setObjectName("Muted")
        desc.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        card.add(big); card.add(desc)
        parent_layout.addWidget(card, 1)
        return big

    def _run_conflict_scan(self) -> None:
        folder = self.conflict_folder.text()
        if not folder:
            self.toasts.warning("Pick a folder."); return
        self.conflict_folder.remember()
        check_hashes = self.conflict_check_hashes.isChecked()
        self.conflict_scan_btn.setEnabled(False)

        def worker() -> None:
            try:
                def progress_cb(current_path: str) -> None:
                    try:
                        rel = os.path.relpath(current_path, folder)
                    except ValueError:
                        rel = current_path
                    QtCore.QMetaObject.invokeMethod(self.status, "showMessage",
                                                    QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, f"Scanning: {rel}"))
                report = detect_conflicts(folder, check_hashes=check_hashes, progress_callback=progress_cb)
                self._last_conflict_report = report
                QtCore.QMetaObject.invokeMethod(self, "_apply_conflict_report", QtCore.Qt.QueuedConnection)
            except Exception as e:
                QtCore.QMetaObject.invokeMethod(self, "_show_conflict_error", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, str(e)))
            finally:
                QtCore.QMetaObject.invokeMethod(self.conflict_scan_btn, "setEnabled", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(bool, True))

        threading.Thread(target=worker, daemon=True).start()

    @QtCore.Slot(str)
    def _show_conflict_error(self, message: str) -> None:
        self.toasts.error(message)

    @QtCore.Slot()
    def _apply_conflict_report(self) -> None:
        report = self._last_conflict_report
        if not report:
            return
        total_dups = len(report.duplicates) + len(report.ymap_duplicates)
        self.dup_count_label.setText(str(total_dups))
        self.col_count_label.setText(str(len(report.name_collisions)))
        self.total_count_label.setText(str(report.total_issues))
        self.conflict_tree.clear()

        def add_section(label: str, items, expand: bool, color: str) -> None:
            top = QtWidgets.QTreeWidgetItem([f"{label} ({len(items)})", ""])
            top.setForeground(0, QtGui.QColor(color))
            f = top.font(0); f.setBold(True); top.setFont(0, f)
            for conflict in items:
                child = QtWidgets.QTreeWidgetItem([f"  {conflict.filename}", ""])
                for loc in conflict.locations:
                    child.addChild(QtWidgets.QTreeWidgetItem(["", loc]))
                top.addChild(child)
            self.conflict_tree.addTopLevelItem(top)
            top.setExpanded(expand)

        if report.ymap_duplicates:
            add_section("Duplicate YMAPs", report.ymap_duplicates, True, theme.palette().warning)
        if report.duplicates:
            add_section("Other duplicate files", report.duplicates, False, theme.palette().warning)
        if report.name_collisions:
            add_section("YMAP conflicts (different content)", report.name_collisions, True, theme.palette().danger)
        if report.total_issues == 0:
            ok = QtWidgets.QTreeWidgetItem(["✓ No conflicts detected", "Your resources folder is clean"])
            ok.setForeground(0, QtGui.QColor(theme.palette().success))
            self.conflict_tree.addTopLevelItem(ok)

        self.toasts.success(f"Scan complete · {report.total_issues} issue(s)")

    def _copy_conflicts_to_clipboard(self) -> None:
        if not self._last_conflict_report:
            self.toasts.info("Run a scan first."); return
        text = self._format_conflict_report(self._last_conflict_report)
        QtWidgets.QApplication.clipboard().setText(text)
        self.toasts.success("Report copied to clipboard")

    def _export_conflict_report(self) -> None:
        if not self._last_conflict_report:
            self.toasts.info("Run a scan first."); return
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export report", "conflict_report.md",
                                                            "Markdown (*.md);;Text (*.txt)")
        if not filepath:
            return
        text = self._format_conflict_report(self._last_conflict_report, markdown=filepath.endswith(".md"))
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)
        self.toasts.success(f"Saved {os.path.basename(filepath)}")

    def _format_conflict_report(self, report, markdown: bool = False) -> str:
        h1, h2, bullet = ("# ", "## ", "- ") if markdown else ("=== ", "--- ", "  - ")
        out = [h1 + "Conflict Detector Report", ""]
        if report.ymap_duplicates:
            out.append(h2 + f"Duplicate YMAPs ({len(report.ymap_duplicates)})")
            for c in report.ymap_duplicates:
                out.append(bullet + c.filename)
                for loc in c.locations:
                    out.append((bullet + "  ") + loc if markdown else f"      → {loc}")
            out.append("")
        if report.duplicates:
            out.append(h2 + f"Other duplicates ({len(report.duplicates)})")
            for c in report.duplicates:
                out.append(bullet + c.filename)
                for loc in c.locations:
                    out.append((bullet + "  ") + loc if markdown else f"      → {loc}")
            out.append("")
        if report.name_collisions:
            out.append(h2 + f"YMAP conflicts ({len(report.name_collisions)})")
            for c in report.name_collisions:
                out.append(bullet + c.filename)
                for loc in c.locations:
                    out.append((bullet + "  ") + loc if markdown else f"      → {loc}")
            out.append("")
        out.append(f"Total issues: {report.total_issues}")
        return "\n".join(out)

    def _run_fix_conflicts(self) -> None:
        report = getattr(self, "_last_conflict_report", None)
        if not report:
            self.toasts.info("Run a scan first."); return
        folder = self.conflict_folder.text()
        if not folder:
            self.toasts.warning("No folder selected."); return

        fixable = len(report.ymap_duplicates) + len(report.name_collisions)
        if fixable == 0:
            self.toasts.info("Nothing to fix."); return

        # Build a concise description for the confirmation dialog
        lines = ["The following automatic fixes will be applied:\n"]
        if report.ymap_duplicates:
            lines.append(f"• {len(report.ymap_duplicates)} duplicate YMAP group(s) — extra copies will be deleted")
        xml_collisions = [c for c in report.name_collisions if c.filename.lower().endswith(".ymap.xml")]
        bin_collisions = [c for c in report.name_collisions if not c.filename.lower().endswith(".ymap.xml")]
        if xml_collisions:
            lines.append(
                f"• {len(xml_collisions)} .ymap.xml name collision(s):\n"
                "  Unique entities from each secondary file are absorbed into the\n"
                "  primary, duplicate entities are discarded, then the secondary\n"
                "  file is deleted — resolving the streaming name conflict."
            )
        if bin_collisions:
            lines.append(
                f"• {len(bin_collisions)} binary .ymap collision(s) — entity-aware fix:\n"
                "  True duplicates (no unique entities) will be deleted.\n"
                "  Files with unique entities will be skipped; the fix log will\n"
                "  list exactly which archetype hashes/positions need manual\n"
                "  merging in CodeWalker (RSC7 binary format cannot be auto-merged)."
            )
        lines.append("\nA .bak backup is written next to every changed file.")
        lines.append("Continue?")

        reply = QtWidgets.QMessageBox.question(
            self, "Fix YMAP Conflicts", "\n".join(lines),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        self.conflict_fix_btn.setEnabled(False)
        self.conflict_scan_btn.setEnabled(False)

        def worker() -> None:
            try:
                def log_cb(msg: str) -> None:
                    QtCore.QMetaObject.invokeMethod(
                        self.status, "showMessage",
                        QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, msg),
                    )

                def progress_cb(path: str) -> None:
                    try:
                        rel = os.path.relpath(path, folder)
                    except ValueError:
                        rel = path
                    QtCore.QMetaObject.invokeMethod(
                        self.status, "showMessage",
                        QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, f"Fixing: {rel}"),
                    )

                fix_result: YmapFixResult = fix_ymap_conflicts(
                    report, folder,
                    log_callback=log_cb,
                    progress_callback=progress_cb,
                )
                self._pending_fix_result = fix_result
                QtCore.QMetaObject.invokeMethod(
                    self, "_apply_fix_result",
                    QtCore.Qt.QueuedConnection,
                )
            except Exception as e:
                QtCore.QMetaObject.invokeMethod(
                    self, "_show_conflict_error",
                    QtCore.Qt.QueuedConnection,
                    QtCore.Q_ARG(str, str(e)),
                )
            finally:
                QtCore.QMetaObject.invokeMethod(
                    self.conflict_fix_btn, "setEnabled",
                    QtCore.Qt.QueuedConnection, QtCore.Q_ARG(bool, True),
                )
                QtCore.QMetaObject.invokeMethod(
                    self.conflict_scan_btn, "setEnabled",
                    QtCore.Qt.QueuedConnection, QtCore.Q_ARG(bool, True),
                )

        threading.Thread(target=worker, daemon=True).start()

    @QtCore.Slot()
    def _apply_fix_result(self) -> None:
        fix_result: YmapFixResult = getattr(self, "_pending_fix_result", None)
        if fix_result is None:
            return
        fixed_n = len(fix_result.fixed)
        skipped_n = len(fix_result.skipped)
        error_n = len(fix_result.errors)

        if error_n:
            self.toasts.warning(
                f"Fix complete — {fixed_n} fixed, {skipped_n} skipped, "
                f"{error_n} error(s). Check the log for details."
            )
        else:
            self.toasts.success(
                f"Fix complete — {fixed_n} fixed, {skipped_n} skipped."
            )

        # If anything was changed, trigger a fresh scan so the tree updates
        if fixed_n:
            self._run_conflict_scan()

    # ─────────────────────────────────────────────────────────────────
    # Page: Command Scanner
    # ─────────────────────────────────────────────────────────────────
    def _build_commands_page(self) -> None:
        page = _scrollable()
        layout = page.layout
        _page_title(layout, "Command Scanner", "Find every registered command across your server resources.")

        path_card = widgets.Card()
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Server path"))
        self.cmd_scan_folder = widgets.RecentPathLineEdit("cmd_scan_path", "Path to server-data or resources folder")
        widgets.enable_folder_drop(self.cmd_scan_folder)
        row.addWidget(self.cmd_scan_folder, 1)
        bb = QtWidgets.QPushButton("Browse…"); bb.clicked.connect(lambda: _pick_dir(self, self.cmd_scan_folder, "Select Folder"))
        row.addWidget(bb)
        path_card.add_layout(row)

        controls = QtWidgets.QHBoxLayout()
        btn_scan = QtWidgets.QPushButton("Scan"); btn_scan.setObjectName("PrimaryButton")
        btn_scan.clicked.connect(self._run_command_scan)
        controls.addWidget(btn_scan); controls.addStretch()
        controls.addWidget(QtWidgets.QLabel("Filter"))
        self.cmd_scan_filter = QtWidgets.QComboBox()
        self.cmd_scan_filter.addItem("All", None)
        for name, val in [("Native", "native"), ("ESX", "esx"), ("QBCore", "qbcore"), ("Chat", "chat_suggestion")]:
            self.cmd_scan_filter.addItem(name, val)
        self.cmd_scan_filter.currentIndexChanged.connect(self._filter_scanned_commands)
        controls.addWidget(self.cmd_scan_filter)
        self.cmd_scan_search = QtWidgets.QLineEdit()
        self.cmd_scan_search.setPlaceholderText("Search…"); self.cmd_scan_search.setMaximumWidth(180)
        self.cmd_scan_search.textChanged.connect(self._filter_scanned_commands)
        controls.addWidget(self.cmd_scan_search)
        path_card.add_layout(controls)
        layout.addWidget(path_card)

        self.cmd_scan_summary = QtWidgets.QLabel("Point to your server folder to discover commands.")
        self.cmd_scan_summary.setObjectName("Muted")
        layout.addWidget(self.cmd_scan_summary)

        table_card = widgets.Card()
        self.cmd_scan_table = QtWidgets.QTableWidget()
        self.cmd_scan_table.setColumnCount(5)
        self.cmd_scan_table.setHorizontalHeaderLabels(["Command", "Description", "Framework", "Source File", "Permissions"])
        h = self.cmd_scan_table.horizontalHeader()
        h.setStretchLastSection(True)
        h.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.cmd_scan_table.setAlternatingRowColors(True)
        self.cmd_scan_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.cmd_scan_table.setSortingEnabled(True)
        table_card.add(self.cmd_scan_table)
        layout.addWidget(table_card, 1)

        io_row = QtWidgets.QHBoxLayout()
        btn_copy = QtWidgets.QPushButton("Copy list"); btn_copy.clicked.connect(self._copy_scanned_commands)
        btn_export = QtWidgets.QPushButton("Export…"); btn_export.clicked.connect(self._export_scanned_commands)
        io_row.addStretch(); io_row.addWidget(btn_copy); io_row.addWidget(btn_export)
        layout.addLayout(io_row)

        self.stack.addWidget(page.widget)

    def _run_command_scan(self) -> None:
        folder = self.cmd_scan_folder.text()
        if not folder:
            self.toasts.warning("Pick a folder."); return
        self.cmd_scan_folder.remember()
        self.status.showMessage("Scanning…")
        QtWidgets.QApplication.processEvents()
        result = scan_server_commands(folder)
        self._scanned_commands = result.commands
        self.cmd_scan_summary.setText(f"<b>{len(result.commands)}</b> commands · {result.files_scanned} Lua files scanned")
        self._populate_command_table(result.commands)
        self.toasts.success(f"Found {len(result.commands)} commands")

    def _populate_command_table(self, commands: list[ServerCommand]) -> None:
        self.cmd_scan_table.setSortingEnabled(False)
        self.cmd_scan_table.setRowCount(len(commands))
        colors = {
            "native": theme.palette().info,
            "esx": theme.palette().warning,
            "qbcore": theme.palette().success,
            "chat_suggestion": "#ce93d8",
        }
        for i, cmd in enumerate(commands):
            name_item = QtWidgets.QTableWidgetItem(f"/{cmd.name}")
            self.cmd_scan_table.setItem(i, 0, name_item)
            self.cmd_scan_table.setItem(i, 1, QtWidgets.QTableWidgetItem(cmd.description or "—"))
            fw = QtWidgets.QTableWidgetItem(cmd.framework.upper())
            fw.setForeground(QtGui.QColor(colors.get(cmd.framework, theme.palette().text_muted)))
            self.cmd_scan_table.setItem(i, 2, fw)
            self.cmd_scan_table.setItem(i, 3, QtWidgets.QTableWidgetItem(cmd.source_file))
            perm = QtWidgets.QTableWidgetItem(getattr(cmd, "permissions", "Everyone"))
            perm.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            pl = perm.text().lower()
            if pl in ("admin", "superadmin", "moderator"):
                perm.setForeground(QtGui.QColor(theme.palette().danger))
            elif pl.startswith("ace"):
                perm.setForeground(QtGui.QColor(theme.palette().warning))
            elif pl.startswith("job"):
                perm.setForeground(QtGui.QColor(theme.palette().info))
            elif pl == "everyone":
                perm.setForeground(QtGui.QColor(theme.palette().success))
            self.cmd_scan_table.setItem(i, 4, perm)
        self.cmd_scan_table.setSortingEnabled(True)

    def _filter_scanned_commands(self) -> None:
        fw = self.cmd_scan_filter.currentData()
        q = self.cmd_scan_search.text().lower()
        filtered = []
        for cmd in self._scanned_commands:
            if fw and cmd.framework != fw:
                continue
            if q and q not in cmd.name.lower() and q not in cmd.description.lower():
                continue
            filtered.append(cmd)
        self._populate_command_table(filtered)

    def _copy_scanned_commands(self) -> None:
        if not self._scanned_commands:
            self.toasts.info("Run a scan first."); return
        lines = [f"/{c.name}  -  {c.description}  [{c.framework}]" for c in self._scanned_commands]
        QtWidgets.QApplication.clipboard().setText("\n".join(lines))
        self.toasts.success(f"Copied {len(self._scanned_commands)} commands")

    def _export_scanned_commands(self) -> None:
        if not self._scanned_commands:
            self.toasts.info("Run a scan first."); return
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export commands", "server_commands.md",
                                                            "Markdown (*.md);;CSV (*.csv);;Text (*.txt)")
        if not filepath:
            return
        if filepath.endswith(".csv"):
            lines = ["Command,Description,Framework,Source File,Permissions"]
            for cmd in self._scanned_commands:
                d = cmd.description.replace('"', '""'); perms = getattr(cmd, "permissions", "Everyone")
                lines.append(f'"{cmd.name}","{d}","{cmd.framework}","{cmd.source_file}","{perms}"')
        elif filepath.endswith(".md"):
            lines = ["# Server commands", "", "| Command | Description | Framework | Permissions |", "| --- | --- | --- | --- |"]
            for c in self._scanned_commands:
                lines.append(f"| /{c.name} | {c.description or '—'} | {c.framework} | {getattr(c, 'permissions', 'Everyone')} |")
        else:
            lines = ["=== Server Commands ===", ""]
            for c in self._scanned_commands:
                lines.append(f"/{c.name}  [{c.framework}]  {getattr(c, 'permissions', 'Everyone')}")
                if c.description:
                    lines.append(f"  Description: {c.description}")
                lines.append(f"  Source: {c.source_file}")
                lines.append("")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        self.toasts.success(f"Exported to {os.path.basename(filepath)}")

    # ─────────────────────────────────────────────────────────────────
    # Page: Locale Checker
    # ─────────────────────────────────────────────────────────────────
    def _build_locales_page(self) -> None:
        page = _scrollable()
        layout = page.layout
        _page_title(layout, "Locale Checker", "Find missing translation keys and orphaned references across your resources.")

        path_card = widgets.Card()
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Resources folder"))
        self.locale_path = widgets.RecentPathLineEdit("locale_path", "Path to resources/")
        widgets.enable_folder_drop(self.locale_path)
        row.addWidget(self.locale_path, 1)
        bb = QtWidgets.QPushButton("Browse…"); bb.clicked.connect(lambda: _pick_dir(self, self.locale_path, "Select Resources Folder"))
        row.addWidget(bb)
        btn_scan = QtWidgets.QPushButton("Check"); btn_scan.setObjectName("PrimaryButton"); btn_scan.clicked.connect(self._run_locale_check)
        row.addWidget(btn_scan)
        path_card.add_layout(row)
        layout.addWidget(path_card)

        tree_card = widgets.Card("Results")
        self.locale_tree = QtWidgets.QTreeWidget()
        self.locale_tree.setHeaderLabels(["Resource / Issue", "Detail"])
        self.locale_tree.setColumnWidth(0, 320)
        self.locale_tree.setAlternatingRowColors(True)
        tree_card.add(self.locale_tree)
        layout.addWidget(tree_card, 1)

        self.stack.addWidget(page.widget)

    def _run_locale_check(self) -> None:
        path = self.locale_path.text()
        if not path:
            self.toasts.warning("Pick a folder."); return
        self.locale_path.remember()
        reports = locale_checker.check_resources(path)
        self.locale_tree.clear()
        if not reports:
            self.toasts.info("No resources with a locales/ folder found.")
            return
        for r in reports:
            head = QtWidgets.QTreeWidgetItem([r.resource, f"{len(r.languages)} language(s) · {r.total_keys} keys"])
            head.setFont(0, _bold(head.font(0)))
            self.locale_tree.addTopLevelItem(head)
            if r.missing:
                missing_group = QtWidgets.QTreeWidgetItem(["Missing translations", ""])
                missing_group.setForeground(0, QtGui.QColor(theme.palette().warning))
                for lang, keys in r.missing.items():
                    lang_item = QtWidgets.QTreeWidgetItem([f"  {lang}", f"{len(keys)} missing"])
                    for k in keys[:60]:
                        lang_item.addChild(QtWidgets.QTreeWidgetItem(["", k]))
                    if len(keys) > 60:
                        lang_item.addChild(QtWidgets.QTreeWidgetItem(["", f"... +{len(keys) - 60} more"]))
                    missing_group.addChild(lang_item)
                head.addChild(missing_group)
            if r.undefined_refs:
                ud = QtWidgets.QTreeWidgetItem(["Used but never defined", f"{len(r.undefined_refs)}"])
                ud.setForeground(0, QtGui.QColor(theme.palette().danger))
                for k in r.undefined_refs[:60]:
                    ud.addChild(QtWidgets.QTreeWidgetItem(["", k]))
                head.addChild(ud)
            head.setExpanded(True)
        self.toasts.success(f"Checked {len(reports)} resource(s)")

    # ─────────────────────────────────────────────────────────────────
    # Page: Scaffolder
    # ─────────────────────────────────────────────────────────────────
    def _build_scaffold_page(self) -> None:
        page = _scrollable()
        layout = page.layout
        _page_title(layout, "Scaffold Resource", "Generate a new FiveM resource with a complete fxmanifest.lua and starter files.")

        form_card = widgets.Card("New resource")
        form = QtWidgets.QFormLayout()
        self.scaf_parent = widgets.RecentPathLineEdit("scaffold_parent", "Parent folder (e.g., resources/)")
        widgets.enable_folder_drop(self.scaf_parent)
        form.addRow("Parent folder", self._path_with_browse(
            self.scaf_parent,
            lambda: _pick_dir(self, self.scaf_parent, "Select parent folder"),
        ))
        self.scaf_name = QtWidgets.QLineEdit(); self.scaf_name.setPlaceholderText("my_resource")
        form.addRow("Name", self.scaf_name)
        self.scaf_template = QtWidgets.QComboBox()
        self.scaf_template.addItems(list(scaffolder.TEMPLATES))
        form.addRow("Template", self.scaf_template)
        self.scaf_author = QtWidgets.QLineEdit(); form.addRow("Author", self.scaf_author)
        self.scaf_desc = QtWidgets.QLineEdit(); form.addRow("Description", self.scaf_desc)
        self.scaf_version = QtWidgets.QLineEdit("1.0.0"); form.addRow("Version", self.scaf_version)
        form_card.add_layout(form)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        btn_create = QtWidgets.QPushButton("Generate"); btn_create.setObjectName("PrimaryButton")
        btn_create.clicked.connect(self._do_scaffold)
        btn_row.addWidget(btn_create)
        form_card.add_layout(btn_row)
        layout.addWidget(form_card)
        layout.addStretch()

        self.stack.addWidget(page.widget)

    def _do_scaffold(self) -> None:
        try:
            res = scaffolder.scaffold_resource(
                self.scaf_parent.text(),
                self.scaf_name.text(),
                self.scaf_template.currentText(),
                author=self.scaf_author.text(),
                description=self.scaf_desc.text(),
                version=self.scaf_version.text() or "1.0.0",
            )
            self.scaf_parent.remember()
            self.toasts.success(f"Created {res.path} ({len(res.files)} files)")
        except Exception as e:
            self.toasts.error(str(e))

    # ─────────────────────────────────────────────────────────────────
    # Page: server.cfg Editor
    # ─────────────────────────────────────────────────────────────────
    def _build_server_cfg_page(self) -> None:
        page = _scrollable()
        layout = page.layout
        _page_title(layout, "server.cfg Editor", "Friendly editor for common convars. Originals stay intact.")

        path_card = widgets.Card()
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("server.cfg"))
        self.cfg_path = widgets.RecentPathLineEdit("server_cfg", "Path to server.cfg")
        widgets.enable_folder_drop(self.cfg_path)
        row.addWidget(self.cfg_path, 1)
        bb = QtWidgets.QPushButton("Browse…")
        bb.clicked.connect(self._pick_server_cfg)
        row.addWidget(bb)
        btn_load = QtWidgets.QPushButton("Load"); btn_load.clicked.connect(self._load_server_cfg)
        row.addWidget(btn_load)
        btn_save = QtWidgets.QPushButton("Save"); btn_save.setObjectName("PrimaryButton"); btn_save.clicked.connect(self._save_server_cfg)
        row.addWidget(btn_save)
        path_card.add_layout(row)
        layout.addWidget(path_card)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        # Convar form
        form_card = widgets.Card("Convars")
        self._cfg_form_layout = QtWidgets.QFormLayout()
        self._cfg_inputs: dict[str, QtWidgets.QLineEdit] = {}
        for name, meta in scfg.COMMON_CONVARS.items():
            edit = QtWidgets.QLineEdit()
            edit.setPlaceholderText(meta["desc"])
            edit.setToolTip(meta["desc"])
            if meta["type"] == "secret":
                edit.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
            self._cfg_inputs[name] = edit
            label = QtWidgets.QLabel(name)
            label.setToolTip(meta["desc"])
            self._cfg_form_layout.addRow(label, edit)
        form_card.add_layout(self._cfg_form_layout)
        splitter.addWidget(form_card)

        # Resources panel
        res_card = widgets.Card("Resources started")
        self.cfg_resources_list = QtWidgets.QListWidget()
        self.cfg_resources_list.setAlternatingRowColors(True)
        res_card.add(self.cfg_resources_list)
        toggle = QtWidgets.QPushButton("Toggle ensure/stop on selected")
        toggle.clicked.connect(self._toggle_cfg_resource)
        res_card.add(toggle)
        splitter.addWidget(res_card)
        splitter.setSizes([520, 380])

        self.stack.addWidget(page.widget)

    def _pick_server_cfg(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select server.cfg", "", "Config files (*.cfg *.conf);;All files (*)")
        if path:
            self.cfg_path.setText(path)

    def _load_server_cfg(self) -> None:
        path = self.cfg_path.text()
        if not path or not os.path.exists(path):
            self.toasts.error("File not found."); return
        self._parsed_cfg = scfg.parse_cfg(path)
        for name, edit in self._cfg_inputs.items():
            edit.setText(scfg.get_value(self._parsed_cfg, name) or "")
        self.cfg_resources_list.clear()
        for name, started, _line in scfg.list_resources(self._parsed_cfg):
            item = QtWidgets.QListWidgetItem(f"{'✓' if started else '✗'}  {name}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, name)
            self.cfg_resources_list.addItem(item)
        self.cfg_path.remember()
        self.toasts.success(f"Loaded {os.path.basename(path)}")

    def _save_server_cfg(self) -> None:
        if not getattr(self, "_parsed_cfg", None):
            self.toasts.warning("Load a file first."); return
        for name, edit in self._cfg_inputs.items():
            val = edit.text().strip()
            if val:
                scfg.set_value(self._parsed_cfg, name, val)
        scfg.save_cfg(self._parsed_cfg)
        self.toasts.success("server.cfg saved")

    def _toggle_cfg_resource(self) -> None:
        if not getattr(self, "_parsed_cfg", None):
            return
        item = self.cfg_resources_list.currentItem()
        if not item:
            return
        name = item.data(QtCore.Qt.ItemDataRole.UserRole)
        for line in self._parsed_cfg.lines:
            if line.kind == "directive" and line.args and line.args[0] == name:
                if line.directive.lower() in ("ensure", "start"):
                    line.directive = "stop"; line.raw = f"stop {name}"
                else:
                    line.directive = "ensure"; line.raw = f"ensure {name}"
                break
        self._load_server_cfg_from_parsed()

    def _load_server_cfg_from_parsed(self) -> None:
        self.cfg_resources_list.clear()
        for name, started, _line in scfg.list_resources(self._parsed_cfg):
            item = QtWidgets.QListWidgetItem(f"{'✓' if started else '✗'}  {name}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, name)
            self.cfg_resources_list.addItem(item)

    # ─────────────────────────────────────────────────────────────────
    # Page: Log Tailer
    # ─────────────────────────────────────────────────────────────────
    def _build_log_tail_page(self) -> None:
        page = _scrollable()
        layout = page.layout
        _page_title(layout, "Log Tailer", "Tail server.log live, colored by severity, with regex filtering.")

        path_card = widgets.Card()
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Log file"))
        self.tail_path = widgets.RecentPathLineEdit("tail_path", "Path to server.log")
        widgets.enable_folder_drop(self.tail_path)
        row.addWidget(self.tail_path, 1)
        bb = QtWidgets.QPushButton("Browse…"); bb.clicked.connect(self._pick_log)
        row.addWidget(bb)
        self.btn_tail_start = QtWidgets.QPushButton("Start"); self.btn_tail_start.setObjectName("PrimaryButton")
        self.btn_tail_start.clicked.connect(self._start_tail)
        row.addWidget(self.btn_tail_start)
        self.btn_tail_stop = QtWidgets.QPushButton("Stop"); self.btn_tail_stop.setEnabled(False)
        self.btn_tail_stop.clicked.connect(self._stop_tail)
        row.addWidget(self.btn_tail_stop)
        path_card.add_layout(row)

        filter_row = QtWidgets.QHBoxLayout()
        filter_row.addWidget(QtWidgets.QLabel("Regex filter"))
        self.tail_filter = QtWidgets.QLineEdit()
        self.tail_filter.setPlaceholderText("e.g.  esx|qb-core    (leave blank to show everything)")
        self.tail_filter.textChanged.connect(self._update_tail_filter)
        filter_row.addWidget(self.tail_filter, 1)
        self.tail_autoscroll = QtWidgets.QCheckBox("Auto-scroll"); self.tail_autoscroll.setChecked(True)
        filter_row.addWidget(self.tail_autoscroll)
        btn_clear = QtWidgets.QPushButton("Clear"); btn_clear.setObjectName("GhostButton")
        btn_clear.clicked.connect(lambda: self.tail_view.clear())
        filter_row.addWidget(btn_clear)
        path_card.add_layout(filter_row)
        layout.addWidget(path_card)

        view_card = widgets.Card()
        self.tail_view = QtWidgets.QPlainTextEdit()
        self.tail_view.setReadOnly(True)
        self.tail_view.setObjectName("Code")
        self.tail_view.setMaximumBlockCount(5000)
        view_card.add(self.tail_view)
        layout.addWidget(view_card, 1)

        self.stack.addWidget(page.widget)

    def _pick_log(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Pick log file", "", "Log files (*.log *.txt);;All files (*)")
        if path:
            self.tail_path.setText(path)

    def _update_tail_filter(self, text: str) -> None:
        try:
            self._tail_filter_regex = re.compile(text, re.IGNORECASE) if text.strip() else None
        except re.error:
            self._tail_filter_regex = None

    def _start_tail(self) -> None:
        path = self.tail_path.text()
        if not path or not os.path.exists(path):
            self.toasts.error("Pick an existing log file."); return
        self.tail_path.remember()
        self._stop_tail()
        self._log_worker = LogTailWorker(path, follow=True)
        self._log_worker.line_emitted.connect(self._on_log_line)
        self._log_worker.error_emitted.connect(self.toasts.error)
        self._log_worker.stopped.connect(self._tail_stopped)
        self._log_worker.start()
        self.btn_tail_start.setEnabled(False); self.btn_tail_stop.setEnabled(True)
        self.toasts.info("Tailing started")

    def _stop_tail(self) -> None:
        if self._log_worker:
            self._log_worker.stop()
            self._log_worker.wait(800)
            self._log_worker = None
        self.btn_tail_start.setEnabled(True); self.btn_tail_stop.setEnabled(False)

    def _tail_stopped(self) -> None:
        self.btn_tail_start.setEnabled(True); self.btn_tail_stop.setEnabled(False)

    def _on_log_line(self, line: LogLine) -> None:
        if self._tail_filter_regex and not self._tail_filter_regex.search(line.raw):
            return
        color = {
            "error":   theme.palette().danger,
            "warning": theme.palette().warning,
            "success": theme.palette().success,
            "debug":   theme.palette().text_dim,
            "info":    theme.palette().text,
        }[line.level]
        safe = line.raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.tail_view.appendHtml(f"<span style='color:{color};'>{safe}</span>")
        if self.tail_autoscroll.isChecked():
            self.tail_view.verticalScrollBar().setValue(self.tail_view.verticalScrollBar().maximum())

    # ─────────────────────────────────────────────────────────────────
    # Page: Server Console
    # ─────────────────────────────────────────────────────────────────
    def _build_console_page(self) -> None:
        page = _scrollable()
        layout = page.layout
        _page_title(layout, "Server Console", "Build commands locally and copy them to your RCON client.")

        conn_card = widgets.Card("Connection (reference)")
        grid = QtWidgets.QGridLayout(); grid.setColumnStretch(1, 1)
        self.console_host = QtWidgets.QLineEdit("127.0.0.1")
        self.console_port = QtWidgets.QSpinBox(); self.console_port.setRange(1, 65535); self.console_port.setValue(30120)
        self.console_password = QtWidgets.QLineEdit(); self.console_password.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.console_password.setPlaceholderText("RCON password")
        grid.addWidget(QtWidgets.QLabel("Host"), 0, 0); grid.addWidget(self.console_host, 0, 1)
        grid.addWidget(QtWidgets.QLabel("Port"), 0, 2); grid.addWidget(self.console_port, 0, 3)
        grid.addWidget(QtWidgets.QLabel("Password"), 1, 0); grid.addWidget(self.console_password, 1, 1, 1, 3)
        conn_card.add_layout(grid)
        layout.addWidget(conn_card)

        cmd_card = widgets.Card()
        cmd_row = QtWidgets.QHBoxLayout()
        cmd_row.addWidget(QtWidgets.QLabel("Quick command"))
        self.quick_cmd_combo = QtWidgets.QComboBox(); self.quick_cmd_combo.setMinimumWidth(220)
        for cmd in get_quick_commands():
            self.quick_cmd_combo.addItem(f"{cmd.name} ({cmd.category})", cmd)
        cmd_row.addWidget(self.quick_cmd_combo)
        self.cmd_arg_edit = QtWidgets.QLineEdit(); self.cmd_arg_edit.setPlaceholderText("Argument (resource, id, identifier…)")
        cmd_row.addWidget(self.cmd_arg_edit, 1)
        btn_insert = QtWidgets.QPushButton("Insert"); btn_insert.clicked.connect(self._insert_quick_command)
        cmd_row.addWidget(btn_insert)
        cmd_card.add_layout(cmd_row)

        input_row = QtWidgets.QHBoxLayout()
        self.console_input = QtWidgets.QLineEdit(); self.console_input.setPlaceholderText("Type a command and press Enter…")
        self.console_input.returnPressed.connect(self._send_console_command)
        input_row.addWidget(self.console_input, 1)
        send = QtWidgets.QPushButton("Send"); send.setObjectName("PrimaryButton"); send.clicked.connect(self._send_console_command)
        input_row.addWidget(send)
        cmd_card.add_layout(input_row)
        layout.addWidget(cmd_card)

        self.console_output = QtWidgets.QTextEdit(); self.console_output.setReadOnly(True); self.console_output.setObjectName("Code")
        layout.addWidget(self.console_output, 1)
        note = QtWidgets.QLabel("Note: This is a local scratchpad. Use txAdmin or your RCON client to actually send commands.")
        note.setObjectName("Dim")
        layout.addWidget(note)

        self.stack.addWidget(page.widget)

    def _insert_quick_command(self) -> None:
        cmd = self.quick_cmd_combo.currentData()
        if not cmd:
            return
        text = cmd.command
        arg = self.cmd_arg_edit.text().strip()
        if arg:
            for token in ("{resource}", "{id}", "{identifier}"):
                text = text.replace(token, arg)
        self.console_input.setText(text)

    def _send_console_command(self) -> None:
        cmd = self.console_input.text().strip()
        if not cmd:
            return
        self.console_output.append(f"> {cmd}")
        self.console_input.clear()
        if cmd == "status":
            self.console_output.append("Server is running. Players: 0/32")
        elif cmd == "refresh":
            self.console_output.append("Resource list refreshed.")
        elif cmd.startswith("restart "):
            self.console_output.append(f"Restarting resource: {cmd.split(' ', 1)[1]}")
        else:
            self.console_output.append(f"Command queued: {cmd}")

    # ─────────────────────────────────────────────────────────────────
    # Page: Backups (snapshots)
    # ─────────────────────────────────────────────────────────────────
    def _build_backups_page(self) -> None:
        page = _scrollable()
        layout = page.layout
        _page_title(layout, "Backups", "Dated snapshots of your mods/plugins. Restore or diff at any time.")

        loc_card = widgets.Card("Locations")
        f = QtWidgets.QFormLayout()
        self.bk_source = widgets.RecentPathLineEdit("bk_source", "FiveM source folder", DEFAULT_SOURCE_DIR)
        self.bk_backup = widgets.RecentPathLineEdit("bk_backup", "Where snapshots live")
        widgets.enable_folder_drop(self.bk_source); widgets.enable_folder_drop(self.bk_backup)
        for w in (self.bk_source.lineEdit(), self.bk_backup.lineEdit()):
            w.editingFinished.connect(self._refresh_snapshots)
        f.addRow("Source", self._path_with_browse(
            self.bk_source,
            lambda: _pick_dir(self, self.bk_source, "Select FiveM source folder"),
        ))
        f.addRow("Backups", self._path_with_browse(
            self.bk_backup,
            lambda: _pick_dir(self, self.bk_backup, "Select snapshots folder"),
        ))
        loc_card.add_layout(f)
        btn_take = QtWidgets.QPushButton("Take snapshot now…"); btn_take.setObjectName("PrimaryButton")
        btn_take.clicked.connect(self._take_snapshot)
        loc_card.add(btn_take)
        layout.addWidget(loc_card)

        list_card = widgets.Card("Snapshots")
        self.snap_table = QtWidgets.QTableWidget()
        self.snap_table.setColumnCount(4)
        self.snap_table.setHorizontalHeaderLabels(["Label", "Created", "Files", "Size"])
        self.snap_table.horizontalHeader().setStretchLastSection(True)
        self.snap_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.snap_table.setAlternatingRowColors(True)
        self.snap_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        list_card.add(self.snap_table)
        btns = QtWidgets.QHBoxLayout()
        btn_restore = QtWidgets.QPushButton("Restore selected"); btn_restore.clicked.connect(self._restore_snapshot)
        btn_diff = QtWidgets.QPushButton("Diff two selected"); btn_diff.clicked.connect(self._diff_snapshots)
        btn_del = QtWidgets.QPushButton("Delete"); btn_del.setObjectName("DangerButton"); btn_del.clicked.connect(self._delete_snapshot)
        btns.addStretch(); btns.addWidget(btn_diff); btns.addWidget(btn_restore); btns.addWidget(btn_del)
        list_card.add_layout(btns)
        layout.addWidget(list_card, 1)

        self.stack.addWidget(page.widget)

    def _refresh_snapshots(self) -> None:
        bk = self.bk_backup.text().strip()
        snaps = backup_history.load_index(bk) if bk else []
        self.snap_table.setRowCount(len(snaps))
        for i, s in enumerate(snaps):
            self.snap_table.setItem(i, 0, QtWidgets.QTableWidgetItem(s.label))
            self.snap_table.setItem(i, 1, QtWidgets.QTableWidgetItem(s.created_at))
            self.snap_table.setItem(i, 2, QtWidgets.QTableWidgetItem(str(s.file_count)))
            self.snap_table.setItem(i, 3, QtWidgets.QTableWidgetItem(backup_history.humanize_bytes(s.total_bytes)))
            self.snap_table.item(i, 0).setData(QtCore.Qt.ItemDataRole.UserRole, s.id)

    def _take_snapshot(self) -> None:
        source = self.bk_source.text().strip()
        backup = self.bk_backup.text().strip()
        if not source or not backup:
            self.toasts.warning("Pick both source and backup folders."); return
        label, ok = QtWidgets.QInputDialog.getText(self, "Snapshot label", "Label this snapshot:")
        if not ok or not label.strip():
            return
        try:
            snap = backup_history.create_snapshot(source, backup, label.strip())
            self.toasts.success(f"Snapshot '{snap.label}' captured ({snap.file_count} files)")
            self._refresh_snapshots()
        except Exception as e:
            self.toasts.error(str(e))

    def _selected_snap_ids(self) -> list[str]:
        ids: list[str] = []
        for row in {idx.row() for idx in self.snap_table.selectedIndexes()}:
            item = self.snap_table.item(row, 0)
            if item:
                sid = item.data(QtCore.Qt.ItemDataRole.UserRole)
                if sid:
                    ids.append(sid)
        return ids

    def _restore_snapshot(self) -> None:
        ids = self._selected_snap_ids()
        if not ids:
            self.toasts.warning("Select a snapshot."); return
        if len(ids) > 1:
            self.toasts.warning("Pick exactly one snapshot to restore."); return
        if QtWidgets.QMessageBox.question(self, "Restore", "Restore this snapshot? Current mods/plugins will be overwritten.") != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        if backup_history.restore_snapshot(self.bk_backup.text(), ids[0], self.bk_source.text()):
            self.toasts.success("Snapshot restored")
        else:
            self.toasts.error("Restore failed")

    def _delete_snapshot(self) -> None:
        ids = self._selected_snap_ids()
        if not ids:
            return
        if QtWidgets.QMessageBox.question(self, "Delete", f"Permanently delete {len(ids)} snapshot(s)?") != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        for sid in ids:
            backup_history.delete_snapshot(self.bk_backup.text(), sid)
        self.toasts.info(f"Deleted {len(ids)} snapshot(s)")
        self._refresh_snapshots()

    def _diff_snapshots(self) -> None:
        ids = self._selected_snap_ids()
        if len(ids) != 2:
            self.toasts.warning("Select exactly two snapshots."); return
        diff = backup_history.diff_snapshots(self.bk_backup.text(), ids[0], ids[1])
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Snapshot diff")
        dlg.resize(720, 480)
        v = QtWidgets.QVBoxLayout(dlg)
        for label, color in [("added", theme.palette().success), ("removed", theme.palette().danger), ("changed", theme.palette().warning)]:
            files = diff[label]
            h = QtWidgets.QLabel(f"<b>{label.title()} ({len(files)})</b>")
            h.setStyleSheet(f"color: {color};")
            v.addWidget(h)
            te = QtWidgets.QPlainTextEdit("\n".join(files) or "(none)"); te.setReadOnly(True); te.setObjectName("Code")
            te.setMaximumHeight(150)
            v.addWidget(te)
        close = QtWidgets.QPushButton("Close"); close.clicked.connect(dlg.accept)
        v.addWidget(close)
        dlg.exec()

    # ─────────────────────────────────────────────────────────────────
    # Page: Dev Utilities (quick commands & snippets)
    # ─────────────────────────────────────────────────────────────────
    def _build_dev_page(self) -> None:
        page = _scrollable()
        layout = page.layout
        _page_title(layout, "Developer Utilities", "Boilerplate snippets and quick command references.")

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        # Quick commands
        left = widgets.Card("Quick commands")
        self.cmd_filter = QtWidgets.QComboBox()
        self.cmd_filter.addItem("All categories", None)
        for cat in sorted({c.category for c in get_quick_commands()}):
            self.cmd_filter.addItem(cat.title(), cat)
        self.cmd_filter.currentIndexChanged.connect(self._filter_commands)
        left.add(self.cmd_filter)
        self.cmd_list = QtWidgets.QTableWidget(); self.cmd_list.setColumnCount(2)
        self.cmd_list.setHorizontalHeaderLabels(["Command", "Description"])
        self.cmd_list.horizontalHeader().setStretchLastSection(True)
        self.cmd_list.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.cmd_list.setAlternatingRowColors(True)
        self.cmd_list.itemDoubleClicked.connect(self._copy_command)
        left.add(self.cmd_list)
        splitter.addWidget(left)

        # Snippets
        right = widgets.Card("Code snippets")
        self.snippet_category = QtWidgets.QComboBox()
        for cat in CODE_SNIPPETS:
            self.snippet_category.addItem(cat)
        self.snippet_category.currentIndexChanged.connect(self._update_snippets)
        right.add(self.snippet_category)
        self.snippet_list = QtWidgets.QListWidget()
        self.snippet_list.currentItemChanged.connect(self._show_snippet)
        right.add(self.snippet_list)
        self.snippet_preview = QtWidgets.QTextEdit()
        self.snippet_preview.setReadOnly(True); self.snippet_preview.setObjectName("Code")
        right.add(self.snippet_preview)
        btn_copy = QtWidgets.QPushButton("Copy snippet"); btn_copy.clicked.connect(self._copy_snippet)
        right.add(btn_copy)
        splitter.addWidget(right)
        splitter.setSizes([460, 460])

        self._populate_commands()
        self._update_snippets()

        self.stack.addWidget(page.widget)

    def _populate_commands(self, category: str | None = None) -> None:
        commands = get_quick_commands(category)
        self.cmd_list.setRowCount(len(commands))
        for i, c in enumerate(commands):
            self.cmd_list.setItem(i, 0, QtWidgets.QTableWidgetItem(c.command))
            self.cmd_list.setItem(i, 1, QtWidgets.QTableWidgetItem(c.description))

    def _filter_commands(self) -> None:
        self._populate_commands(self.cmd_filter.currentData())

    def _copy_command(self, item: QtWidgets.QTableWidgetItem) -> None:
        cmd = self.cmd_list.item(item.row(), 0).text()
        QtWidgets.QApplication.clipboard().setText(cmd)
        self.toasts.success(f"Copied: {cmd}")

    def _update_snippets(self) -> None:
        cat = self.snippet_category.currentText()
        self.snippet_list.clear()
        for name in CODE_SNIPPETS.get(cat, {}):
            self.snippet_list.addItem(name)

    def _show_snippet(self, current, _previous) -> None:
        if not current:
            return
        cat = self.snippet_category.currentText(); name = current.text()
        self.snippet_preview.setPlainText(CODE_SNIPPETS.get(cat, {}).get(name, ""))

    def _copy_snippet(self) -> None:
        text = self.snippet_preview.toPlainText()
        if text:
            QtWidgets.QApplication.clipboard().setText(text)
            self.toasts.success("Snippet copied")

    # ─────────────────────────────────────────────────────────────────
    # Page: Settings
    # ─────────────────────────────────────────────────────────────────
    def _build_settings_page(self) -> None:
        page = _scrollable()
        layout = page.layout
        _page_title(layout, "Settings", "Tweak how the app looks and behaves.")

        appearance = widgets.Card("Appearance")
        form = QtWidgets.QFormLayout()
        state = theme.get_state()
        self.theme_mode = QtWidgets.QComboBox()
        self.theme_mode.addItems(["Dark", "Light", "System"])
        self.theme_mode.setCurrentText(state.mode.title())
        form.addRow("Mode", self.theme_mode)

        self.theme_accent = QtWidgets.QComboBox()
        for name in theme.ACCENT_PRESETS:
            self.theme_accent.addItem(name)
        self.theme_accent.setCurrentText(state.accent)
        form.addRow("Accent color", self.theme_accent)

        self.theme_font = QtWidgets.QSpinBox()
        self.theme_font.setRange(8, 16); self.theme_font.setValue(state.font_size)
        form.addRow("Base font size", self.theme_font)

        appearance.add_layout(form)
        btn_apply = QtWidgets.QPushButton("Apply"); btn_apply.setObjectName("PrimaryButton")
        btn_apply.clicked.connect(self._apply_settings)
        btn_row = QtWidgets.QHBoxLayout(); btn_row.addStretch(); btn_row.addWidget(btn_apply)
        appearance.add_layout(btn_row)
        layout.addWidget(appearance)

        # Changelog
        cl_card = widgets.Card("What's new")
        cl_view = QtWidgets.QTextBrowser()
        cl_view.setOpenExternalLinks(True)
        cl_path = resource_path("RELEASE_NOTES.md")
        try:
            content = Path(cl_path).read_text(encoding="utf-8") if os.path.exists(cl_path) else "No release notes file found."
        except Exception as e:
            content = f"Failed to read release notes: {e}"
        cl_view.setMarkdown(content)
        cl_view.setMinimumHeight(280)
        cl_card.add(cl_view)
        layout.addWidget(cl_card, 1)

        about = QtWidgets.QLabel(
            f"Sanitize V v{VERSION} · MIT License · "
            f"<a href='https://github.com/mpriester8/SanitizeV'>github.com/mpriester8/SanitizeV</a>"
        )
        about.setOpenExternalLinks(True); about.setObjectName("Muted")
        layout.addWidget(about)

        self.stack.addWidget(page.widget)

    def _apply_settings(self) -> None:
        state = theme.get_state()
        state.mode = self.theme_mode.currentText().lower()
        state.accent = self.theme_accent.currentText()
        state.font_size = self.theme_font.value()
        theme.set_state(state)
        theme.apply_theme(QtWidgets.QApplication.instance())
        if hasattr(self, "_theme_toggle"):
            self._theme_toggle.setText(self._theme_label())
        self.toasts.success("Theme applied")

    def _toggle_theme(self) -> None:
        state = theme.get_state()
        state.mode = "light" if state.mode == "dark" else "dark"
        theme.set_state(state)
        theme.apply_theme(QtWidgets.QApplication.instance())
        if hasattr(self, "_theme_toggle"):
            self._theme_toggle.setText(self._theme_label())
        if hasattr(self, "theme_mode"):
            self.theme_mode.setCurrentText(state.mode.title())

    # ─────────────────────────────────────────────────────────────────
    # Command palette
    # ─────────────────────────────────────────────────────────────────
    def _palette_actions(self) -> list[command_palette.PaletteAction]:
        Action = command_palette.PaletteAction
        pages = [
            ("Home",                   self.PAGE_HOME,       "Dashboard"),
            ("Sanitize / Restore",     self.PAGE_SANITIZE,   "Mods on/off"),
            ("Mod Profiles",           self.PAGE_PROFILES,   "Named loadouts"),
            ("Graphics Editor",        self.PAGE_GRAPHICS,   "gta5_settings.xml"),
            ("Manifest Validator",     self.PAGE_MANIFEST,   "fxmanifest.lua issues"),
            ("Dependency Graph",       self.PAGE_DEPGRAPH,   "How resources depend"),
            ("Conflict Detector",      self.PAGE_CONFLICTS,  "YMAP duplicates"),
            ("Command Scanner",        self.PAGE_COMMANDS,   "Find all commands"),
            ("Locale Checker",         self.PAGE_LOCALES,    "Translations"),
            ("Scaffold Resource",      self.PAGE_SCAFFOLD,   "Generate new resource"),
            ("server.cfg Editor",      self.PAGE_SERVER_CFG, "Convars + ensure"),
            ("Log Tailer",             self.PAGE_LOG_TAIL,   "Live server log"),
            ("Server Console",         self.PAGE_CONSOLE,    "Local scratchpad"),
            ("Backups",                self.PAGE_BACKUPS,    "Snapshots"),
            ("Developer Utilities",    self.PAGE_DEV,        "Snippets, quick commands"),
            ("Settings",               self.PAGE_SETTINGS,   "Theme, accent"),
        ]
        actions: list[command_palette.PaletteAction] = [
            Action(title=f"Go to {name}", subtitle=sub, category="Page", callback=lambda p=p: self._goto(p))
            for name, p, sub in pages
        ]
        actions += [
            Action("Toggle theme (dark/light)", "Switch the mode", self._toggle_theme, "Action", "dark light"),
            Action("Take a backup snapshot now", "Capture mods/plugins to backup history",
                   lambda: (self._goto(self.PAGE_BACKUPS), self._take_snapshot()), "Action", "save backup"),
            Action("Build dependency graph", "Build the resource dep graph",
                   lambda: (self._goto(self.PAGE_DEPGRAPH), self._build_dep_graph()), "Action", "deps graph"),
            Action("Validate all manifests", "Scan all manifests in current path",
                   lambda: (self._goto(self.PAGE_MANIFEST), self._validate_all_manifests()), "Action", "fxmanifest"),
            Action("Scan for conflicts", "Run the conflict detector",
                   lambda: (self._goto(self.PAGE_CONFLICTS), self._run_conflict_scan()), "Action", "duplicates ymap"),
        ]
        for cat, snips in CODE_SNIPPETS.items():
            for name, body in snips.items():
                def make_cb(b=body, n=name):
                    return lambda: (QtWidgets.QApplication.clipboard().setText(b), self.toasts.success(f"Copied snippet: {n}"))
                actions.append(Action(f"Copy snippet · {name}", cat, make_cb(), "Snippet", cat))
        return actions


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

class _PageContainer:
    """Container with a vertical layout for a scrollable page."""

    def __init__(self) -> None:
        self.widget = QtWidgets.QScrollArea()
        self.widget.setWidgetResizable(True)
        self.widget.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        inner = QtWidgets.QWidget()
        self.layout = QtWidgets.QVBoxLayout(inner)
        self.layout.setContentsMargins(28, 22, 28, 22)
        self.layout.setSpacing(14)
        self.widget.setWidget(inner)


def _scrollable() -> _PageContainer:
    return _PageContainer()


def _page_title(layout: QtWidgets.QVBoxLayout, title: str, subtitle: str) -> None:
    t = QtWidgets.QLabel(title); t.setObjectName("Heading")
    s = QtWidgets.QLabel(subtitle); s.setObjectName("Muted"); s.setWordWrap(True)
    layout.addWidget(t); layout.addWidget(s)


def _pick_dir(parent: QtWidgets.QWidget, target, title: str) -> None:
    d = QtWidgets.QFileDialog.getExistingDirectory(parent, title)
    if d:
        target.setText(d)


def _bold(font: QtGui.QFont) -> QtGui.QFont:
    f = QtGui.QFont(font); f.setBold(True); return f


# ─────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────

def main() -> None:
    try:
        from ctypes import windll
        windll.shell32.SetCurrentProcessExplicitAppUserModelID("SanitizeV.App.1.0")
    except Exception:
        pass

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")

    icon_path = resource_path(os.path.join("assets", "app_icon.ico"))
    if not os.path.exists(icon_path):
        icon_path = resource_path(os.path.join("assets", "app_icon.png"))
    if os.path.exists(icon_path):
        app.setWindowIcon(QtGui.QIcon(icon_path))

    theme.apply_theme(app)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
