"""
Centralized theming for Sanitize V.

Provides:
- Design tokens (colors, radii, spacing, typography)
- Dynamic QSS generation for the entire app
- Light/dark mode with system-preference detection
- Persistent accent color picker
- Helper to apply the active theme to a QApplication
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, asdict
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger(__name__)

THEME_STATE_FILE = os.path.join(tempfile.gettempdir(), "SanitizeV", "theme.json")


@dataclass(frozen=True)
class Palette:
    """A complete color palette for one theme variant."""
    bg: str            # window background
    bg_alt: str        # cards / panels
    bg_elevated: str   # hover/elevated surfaces
    surface: str       # input controls
    border: str        # subtle borders
    border_strong: str # focused borders
    text: str
    text_muted: str
    text_dim: str
    accent: str
    accent_hover: str
    accent_pressed: str
    success: str
    warning: str
    danger: str
    info: str


DARK = Palette(
    bg="#16181d",
    bg_alt="#1d2026",
    bg_elevated="#262a32",
    surface="#22262d",
    border="#2e333c",
    border_strong="#3a414c",
    text="#e6e8ec",
    text_muted="#9aa0aa",
    text_dim="#6b7280",
    accent="#f59e0b",
    accent_hover="#fbbf24",
    accent_pressed="#d97706",
    success="#22c55e",
    warning="#f59e0b",
    danger="#ef4444",
    info="#3b82f6",
)

LIGHT = Palette(
    bg="#f7f8fa",
    bg_alt="#ffffff",
    bg_elevated="#f0f2f5",
    surface="#ffffff",
    border="#e5e7eb",
    border_strong="#d1d5db",
    text="#1f2937",
    text_muted="#4b5563",
    text_dim="#9ca3af",
    accent="#d97706",
    accent_hover="#f59e0b",
    accent_pressed="#b45309",
    success="#16a34a",
    warning="#d97706",
    danger="#dc2626",
    info="#2563eb",
)


# Spacing & shape tokens
RADIUS_SM = 4
RADIUS_MD = 6
RADIUS_LG = 10
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16

ACCENT_PRESETS: dict[str, tuple[str, str, str]] = {
    "Amber":  ("#f59e0b", "#fbbf24", "#d97706"),
    "Orange": ("#f97316", "#fb923c", "#ea580c"),
    "Red":    ("#ef4444", "#f87171", "#dc2626"),
    "Pink":   ("#ec4899", "#f472b6", "#db2777"),
    "Purple": ("#a855f7", "#c084fc", "#9333ea"),
    "Indigo": ("#6366f1", "#818cf8", "#4f46e5"),
    "Blue":   ("#3b82f6", "#60a5fa", "#2563eb"),
    "Cyan":   ("#06b6d4", "#22d3ee", "#0891b2"),
    "Teal":   ("#14b8a6", "#2dd4bf", "#0d9488"),
    "Green":  ("#22c55e", "#4ade80", "#16a34a"),
}


@dataclass
class ThemeState:
    mode: str = "dark"           # "dark", "light", "system"
    accent: str = "Amber"
    font_size: int = 10

    def palette(self) -> Palette:
        base = DARK if self._resolve_mode() == "dark" else LIGHT
        if self.accent in ACCENT_PRESETS:
            a, ah, ap = ACCENT_PRESETS[self.accent]
            return Palette(
                **{**asdict(base), "accent": a, "accent_hover": ah, "accent_pressed": ap}
            )
        return base

    def _resolve_mode(self) -> str:
        if self.mode == "system":
            try:
                hints = QtGui.QGuiApplication.styleHints()
                if hints.colorScheme() == QtCore.Qt.ColorScheme.Light:
                    return "light"
            except Exception:
                pass
            return "dark"
        return self.mode


_state: Optional[ThemeState] = None


def get_state() -> ThemeState:
    global _state
    if _state is None:
        _state = _load_state()
    return _state


def set_state(state: ThemeState) -> None:
    global _state
    _state = state
    _save_state(state)


def _load_state() -> ThemeState:
    try:
        if os.path.exists(THEME_STATE_FILE):
            with open(THEME_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ThemeState(**{k: v for k, v in data.items() if k in ThemeState.__annotations__})
    except Exception as e:
        logger.warning("Failed to load theme state: %s", e)
    return ThemeState()


def _save_state(state: ThemeState) -> None:
    try:
        os.makedirs(os.path.dirname(THEME_STATE_FILE), exist_ok=True)
        with open(THEME_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(state), f)
    except Exception as e:
        logger.warning("Failed to save theme state: %s", e)


def build_qss(p: Palette) -> str:
    """Generate the full app stylesheet for a palette."""
    return f"""
    /* ─── Global ─────────────────────────────────────────────────── */
    QWidget {{
        background-color: {p.bg};
        color: {p.text};
        selection-background-color: {p.accent};
        selection-color: {p.bg};
    }}
    QMainWindow, QDialog {{
        background-color: {p.bg};
    }}
    QToolTip {{
        background-color: {p.bg_elevated};
        color: {p.text};
        border: 1px solid {p.border_strong};
        padding: 6px 8px;
        border-radius: {RADIUS_SM}px;
    }}

    /* ─── Sidebar (objectName='Sidebar') ─────────────────────────── */
    QWidget#Sidebar {{
        background-color: {p.bg_alt};
        border-right: 1px solid {p.border};
    }}
    QWidget#SidebarHeader {{
        background-color: {p.bg_alt};
        border-bottom: 1px solid {p.border};
    }}
    QLabel#SidebarTitle {{
        color: {p.text};
        font-size: 14pt;
        font-weight: 700;
        padding: 2px 0px;
    }}
    QLabel#SidebarSubtitle {{
        color: {p.text_muted};
        font-size: 9pt;
    }}
    QPushButton#NavButton {{
        background-color: transparent;
        color: {p.text_muted};
        border: none;
        border-radius: {RADIUS_MD}px;
        padding: 9px 14px;
        text-align: left;
        font-size: 10pt;
        font-weight: 500;
    }}
    QPushButton#NavButton:hover {{
        background-color: {p.bg_elevated};
        color: {p.text};
    }}
    QPushButton#NavButton:checked {{
        background-color: {p.accent};
        color: {p.bg};
        font-weight: 600;
    }}
    QPushButton#NavButton:checked:hover {{
        background-color: {p.accent_hover};
    }}

    /* ─── Buttons ─────────────────────────────────────────────────── */
    QPushButton {{
        background-color: {p.bg_elevated};
        color: {p.text};
        border: 1px solid {p.border};
        border-radius: {RADIUS_MD}px;
        padding: 7px 14px;
        font-size: 10pt;
    }}
    QPushButton:hover {{
        background-color: {p.surface};
        border-color: {p.border_strong};
    }}
    QPushButton:pressed {{
        background-color: {p.bg_alt};
    }}
    QPushButton:disabled {{
        color: {p.text_dim};
        background-color: {p.bg_alt};
    }}
    QPushButton#PrimaryButton {{
        background-color: {p.accent};
        color: {p.bg};
        border: 1px solid {p.accent};
        font-weight: 600;
    }}
    QPushButton#PrimaryButton:hover {{
        background-color: {p.accent_hover};
        border-color: {p.accent_hover};
    }}
    QPushButton#PrimaryButton:pressed {{
        background-color: {p.accent_pressed};
        border-color: {p.accent_pressed};
    }}
    QPushButton#DangerButton {{
        background-color: {p.danger};
        color: {p.bg};
        border: 1px solid {p.danger};
        font-weight: 600;
    }}
    QPushButton#GhostButton {{
        background-color: transparent;
        border: 1px solid transparent;
    }}
    QPushButton#GhostButton:hover {{
        background-color: {p.bg_elevated};
        border-color: {p.border};
    }}
    QPushButton#IconButton {{
        background-color: transparent;
        border: none;
        padding: 4px;
        border-radius: {RADIUS_SM}px;
    }}
    QPushButton#IconButton:hover {{
        background-color: {p.bg_elevated};
    }}

    /* ─── Inputs ──────────────────────────────────────────────────── */
    QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {p.surface};
        color: {p.text};
        border: 1px solid {p.border};
        border-radius: {RADIUS_MD}px;
        padding: 6px 9px;
        selection-background-color: {p.accent};
        selection-color: {p.bg};
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus,
    QDoubleSpinBox:focus, QComboBox:focus {{
        border-color: {p.accent};
    }}
    QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled {{
        color: {p.text_dim};
        background-color: {p.bg_alt};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {p.text_muted};
        margin-right: 6px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {p.bg_elevated};
        color: {p.text};
        border: 1px solid {p.border_strong};
        border-radius: {RADIUS_SM}px;
        outline: 0;
        selection-background-color: {p.accent};
        selection-color: {p.bg};
        padding: 4px;
    }}

    /* ─── Labels & Group boxes ───────────────────────────────────── */
    QLabel {{ background-color: transparent; }}
    QLabel#Heading {{ font-size: 16pt; font-weight: 700; color: {p.text}; }}
    QLabel#Subheading {{ font-size: 12pt; font-weight: 600; color: {p.text}; }}
    QLabel#Muted {{ color: {p.text_muted}; }}
    QLabel#Dim   {{ color: {p.text_dim}; }}
    QGroupBox {{
        background-color: {p.bg_alt};
        border: 1px solid {p.border};
        border-radius: {RADIUS_MD}px;
        margin-top: 14px;
        padding: 10px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 6px;
        color: {p.text_muted};
        left: 10px;
    }}

    /* ─── Card frame ──────────────────────────────────────────────── */
    QFrame#Card {{
        background-color: {p.bg_alt};
        border: 1px solid {p.border};
        border-radius: {RADIUS_LG}px;
    }}
    QFrame#CardElevated {{
        background-color: {p.bg_elevated};
        border: 1px solid {p.border};
        border-radius: {RADIUS_LG}px;
    }}
    QFrame#Separator {{
        background-color: {p.border};
        max-height: 1px;
        min-height: 1px;
    }}

    /* ─── Tabs (kept for sub-tabs) ───────────────────────────────── */
    QTabWidget::pane {{
        border: 1px solid {p.border};
        border-radius: {RADIUS_MD}px;
        background: {p.bg_alt};
        top: -1px;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {p.text_muted};
        padding: 8px 14px;
        border: 1px solid transparent;
        border-bottom: none;
        border-top-left-radius: {RADIUS_SM}px;
        border-top-right-radius: {RADIUS_SM}px;
        margin-right: 2px;
    }}
    QTabBar::tab:hover {{ color: {p.text}; }}
    QTabBar::tab:selected {{
        background: {p.bg_alt};
        color: {p.accent};
        border-color: {p.border};
        font-weight: 600;
    }}

    /* ─── Checkboxes & radios ────────────────────────────────────── */
    QCheckBox, QRadioButton {{ color: {p.text}; spacing: 8px; }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 16px; height: 16px;
        border: 1px solid {p.border_strong};
        background: {p.surface};
    }}
    QCheckBox::indicator {{ border-radius: 3px; }}
    QRadioButton::indicator {{ border-radius: 8px; }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background: {p.accent};
        border-color: {p.accent};
    }}

    /* ─── Sliders & progress ─────────────────────────────────────── */
    QSlider::groove:horizontal {{
        background: {p.bg_elevated};
        height: 6px;
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: {p.accent};
        border: none;
        width: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }}
    QSlider::handle:horizontal:hover {{ background: {p.accent_hover}; }}
    QProgressBar {{
        background-color: {p.bg_elevated};
        border: 1px solid {p.border};
        border-radius: {RADIUS_SM}px;
        text-align: center;
        color: {p.text};
        height: 14px;
    }}
    QProgressBar::chunk {{
        background-color: {p.accent};
        border-radius: {RADIUS_SM}px;
    }}

    /* ─── Tables & trees ─────────────────────────────────────────── */
    QTableWidget, QTreeWidget, QListWidget {{
        background-color: {p.bg_alt};
        color: {p.text};
        gridline-color: {p.border};
        alternate-background-color: {p.bg_elevated};
        border: 1px solid {p.border};
        border-radius: {RADIUS_MD}px;
        outline: 0;
    }}
    QTableWidget::item, QTreeWidget::item, QListWidget::item {{
        padding: 4px 6px;
        border: none;
    }}
    QTableWidget::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {{
        background-color: {p.accent};
        color: {p.bg};
    }}
    QHeaderView::section {{
        background-color: {p.bg_alt};
        color: {p.text_muted};
        padding: 6px;
        border: none;
        border-bottom: 1px solid {p.border};
        font-weight: 600;
    }}
    QHeaderView::section:hover {{ color: {p.text}; }}

    /* ─── Scrollbars ─────────────────────────────────────────────── */
    QScrollBar:vertical, QScrollBar:horizontal {{
        background: transparent; border: none;
    }}
    QScrollBar:vertical {{ width: 10px; }}
    QScrollBar:horizontal {{ height: 10px; }}
    QScrollBar::handle {{
        background: {p.border_strong};
        border-radius: 5px;
        min-height: 24px;
        min-width: 24px;
    }}
    QScrollBar::handle:hover {{ background: {p.text_dim}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; background: none; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

    /* ─── Status bar & menus ─────────────────────────────────────── */
    QStatusBar {{
        background-color: {p.bg_alt};
        color: {p.text_muted};
        border-top: 1px solid {p.border};
    }}
    QStatusBar::item {{ border: none; }}
    QMenu {{
        background-color: {p.bg_elevated};
        color: {p.text};
        border: 1px solid {p.border_strong};
        padding: 4px;
        border-radius: {RADIUS_SM}px;
    }}
    QMenu::item {{ padding: 6px 18px; border-radius: 3px; }}
    QMenu::item:selected {{ background-color: {p.accent}; color: {p.bg}; }}
    QMenu::separator {{ background: {p.border}; height: 1px; margin: 4px 6px; }}

    /* ─── Code / monospace areas ─────────────────────────────────── */
    QPlainTextEdit#Code, QTextEdit#Code {{
        font-family: "Consolas", "Cascadia Code", "Menlo", monospace;
        background: {p.bg};
        border: 1px solid {p.border};
        border-radius: {RADIUS_MD}px;
    }}

    /* ─── Toast (objectName='Toast' + severity property) ─────────── */
    QFrame#Toast {{
        background-color: {p.bg_elevated};
        color: {p.text};
        border: 1px solid {p.border_strong};
        border-left: 3px solid {p.info};
        border-radius: {RADIUS_MD}px;
        padding: 8px 12px;
    }}
    QFrame#Toast[severity="success"] {{ border-left-color: {p.success}; }}
    QFrame#Toast[severity="warning"] {{ border-left-color: {p.warning}; }}
    QFrame#Toast[severity="error"]   {{ border-left-color: {p.danger}; }}
    QFrame#Toast[severity="info"]    {{ border-left-color: {p.info}; }}

    /* ─── Command Palette ────────────────────────────────────────── */
    QFrame#Palette {{
        background-color: {p.bg_elevated};
        border: 1px solid {p.border_strong};
        border-radius: {RADIUS_LG}px;
    }}
    QLineEdit#PaletteInput {{
        background-color: transparent;
        border: none;
        border-bottom: 1px solid {p.border};
        border-radius: 0;
        padding: 12px 14px;
        font-size: 12pt;
    }}
    QListWidget#PaletteResults {{
        background: transparent;
        border: none;
    }}
    QListWidget#PaletteResults::item {{
        padding: 8px 14px;
        border-radius: {RADIUS_SM}px;
    }}
    QListWidget#PaletteResults::item:selected {{
        background-color: {p.accent};
        color: {p.bg};
    }}

    /* ─── Pill / tag (QLabel#Pill) ───────────────────────────────── */
    QLabel#Pill {{
        background-color: {p.bg_elevated};
        color: {p.text_muted};
        border: 1px solid {p.border};
        border-radius: 10px;
        padding: 2px 8px;
        font-size: 9pt;
    }}
    """


def apply_theme(app: QtWidgets.QApplication) -> None:
    """Apply the active theme to the entire application."""
    state = get_state()
    p = state.palette()

    # Set palette so native widgets (dialogs, menus) also match
    qpal = QtGui.QPalette()
    qpal.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(p.bg))
    qpal.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(p.text))
    qpal.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(p.surface))
    qpal.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(p.bg_elevated))
    qpal.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor(p.bg_elevated))
    qpal.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor(p.text))
    qpal.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(p.text))
    qpal.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(p.bg_elevated))
    qpal.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(p.text))
    qpal.setColor(QtGui.QPalette.ColorRole.BrightText, QtGui.QColor(p.danger))
    qpal.setColor(QtGui.QPalette.ColorRole.Link, QtGui.QColor(p.accent))
    qpal.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(p.accent))
    qpal.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor(p.bg))
    qpal.setColor(QtGui.QPalette.ColorRole.PlaceholderText, QtGui.QColor(p.text_dim))
    app.setPalette(qpal)

    app.setStyleSheet(build_qss(p))

    # Font sizing
    font = app.font()
    font.setPointSize(state.font_size)
    app.setFont(font)


def palette() -> Palette:
    """Return active palette (for inline color lookups)."""
    return get_state().palette()
