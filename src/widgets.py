"""
Reusable styled widgets for Sanitize V.

Provides:
- ToastManager / Toast (stackable in-app notifications)
- Sidebar / NavButton (sidebar navigation)
- Card / SectionTitle / Pill (layout helpers)
- IconButton (compact icon-only button)
- RecentPathLineEdit (line edit with a recent-paths dropdown)
"""
from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from typing import Callable, Optional

from PySide6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger(__name__)

RECENTS_FILE = os.path.join(tempfile.gettempdir(), "SanitizeV", "recents.json")


# ─────────────────────────────────────────────────────────────────────
# Toast notifications
# ─────────────────────────────────────────────────────────────────────

class Toast(QtWidgets.QFrame):
    """Single toast notification widget."""

    closed = QtCore.Signal(object)

    def __init__(
        self,
        message: str,
        severity: str = "info",
        duration_ms: int = 4000,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setProperty("severity", severity)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMaximumWidth(420)
        self.setMinimumWidth(280)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 8, 8)
        layout.setSpacing(10)

        icon_text = {"info": "i", "success": "✓", "warning": "!", "error": "✗"}.get(severity, "i")
        icon = QtWidgets.QLabel(icon_text)
        icon.setFixedWidth(18)
        icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-weight: 700;")
        layout.addWidget(icon)

        text = QtWidgets.QLabel(message)
        text.setWordWrap(True)
        layout.addWidget(text, 1)

        close = QtWidgets.QPushButton("×")
        close.setObjectName("IconButton")
        close.setFixedSize(22, 22)
        close.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self._dismiss)
        layout.addWidget(close)

        self._opacity = QtWidgets.QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._anim_in = QtCore.QPropertyAnimation(self._opacity, b"opacity", self)
        self._anim_in.setDuration(180)
        self._anim_in.setStartValue(0.0)
        self._anim_in.setEndValue(1.0)
        self._anim_in.start()

        if duration_ms > 0:
            QtCore.QTimer.singleShot(duration_ms, self._dismiss)

    def _dismiss(self) -> None:
        anim = QtCore.QPropertyAnimation(self._opacity, b"opacity", self)
        anim.setDuration(220)
        anim.setStartValue(self._opacity.opacity())
        anim.setEndValue(0.0)
        anim.finished.connect(lambda: self.closed.emit(self))
        anim.start()
        self._anim_out = anim  # keep reference


class ToastManager(QtCore.QObject):
    """Stacks toasts in the bottom-right of a parent window."""

    def __init__(self, parent: QtWidgets.QWidget) -> None:
        super().__init__(parent)
        self._parent = parent
        self._toasts: list[Toast] = []
        parent.installEventFilter(self)

    @QtCore.Slot(str, str, int)
    def show_toast(self, message: str, severity: str = "info", duration_ms: int = 4000) -> None:
        toast = Toast(message, severity, duration_ms, self._parent)
        toast.closed.connect(self._remove)
        self._toasts.append(toast)
        toast.show()
        self._reposition()

    @QtCore.Slot(str)
    def info(self, msg: str) -> None:    self.show_toast(msg, "info", 3500)
    @QtCore.Slot(str)
    def success(self, msg: str) -> None: self.show_toast(msg, "success", 3500)
    @QtCore.Slot(str)
    def warning(self, msg: str) -> None: self.show_toast(msg, "warning", 4500)
    @QtCore.Slot(str)
    def error(self, msg: str) -> None:   self.show_toast(msg, "error", 6000)

    def _remove(self, toast: Toast) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
        toast.deleteLater()
        self._reposition()

    def _reposition(self) -> None:
        margin = 16
        spacing = 8
        x = self._parent.width() - margin
        y = self._parent.height() - margin
        for toast in reversed(self._toasts):
            toast.adjustSize()
            tw, th = toast.width(), toast.height()
            toast.move(x - tw, y - th)
            y -= th + spacing

    def eventFilter(self, obj: QtCore.QObject, ev: QtCore.QEvent) -> bool:
        if obj is self._parent and ev.type() in (QtCore.QEvent.Type.Resize, QtCore.QEvent.Type.Show):
            self._reposition()
        return False


# ─────────────────────────────────────────────────────────────────────
# Sidebar navigation
# ─────────────────────────────────────────────────────────────────────

class NavButton(QtWidgets.QPushButton):
    def __init__(self, icon_char: str, label: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setText(f"  {icon_char}    {label}")


def _sidebar_logo_path() -> str:
    """Resolve sidebar_logo.png whether frozen by PyInstaller or running from source."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "assets", "sidebar_logo.png")
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sidebar_logo.png")


class Sidebar(QtWidgets.QWidget):
    """Vertical sidebar with title, nav buttons, and a footer area."""

    section_changed = QtCore.Signal(int)

    def __init__(self, title: str = "Sanitize V", subtitle: str = "") -> None:
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(232)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header
        header = QtWidgets.QWidget()
        header.setObjectName("SidebarHeader")
        header_layout = QtWidgets.QVBoxLayout(header)
        header_layout.setContentsMargins(16, 20, 16, 14)
        header_layout.setSpacing(6)

        # Logo image
        logo_label = QtWidgets.QLabel()
        logo_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        logo_path = _sidebar_logo_path()
        if os.path.exists(logo_path):
            pix = QtGui.QPixmap(logo_path).scaled(
                56, 56,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            logo_label.setPixmap(pix)
        header_layout.addWidget(logo_label)

        self._title = QtWidgets.QLabel(title)
        self._title.setObjectName("SidebarTitle")
        self._title.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        self._subtitle = QtWidgets.QLabel(subtitle)
        self._subtitle.setObjectName("SidebarSubtitle")
        self._subtitle.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        header_layout.addWidget(self._title)
        header_layout.addWidget(self._subtitle)
        outer.addWidget(header)

        # Nav area
        self._nav = QtWidgets.QVBoxLayout()
        self._nav.setContentsMargins(10, 8, 10, 8)
        self._nav.setSpacing(2)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_container = QtWidgets.QWidget()
        nav_container.setLayout(self._nav)
        scroll.setWidget(nav_container)
        outer.addWidget(scroll, 1)

        self._group = QtWidgets.QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.idToggled.connect(self._on_toggled)
        self._buttons: list[NavButton] = []

        # Footer
        self._footer = QtWidgets.QVBoxLayout()
        self._footer.setContentsMargins(12, 8, 12, 12)
        self._footer.setSpacing(4)
        outer.addLayout(self._footer)

    def add_item(self, icon: str, label: str) -> int:
        btn = NavButton(icon, label)
        idx = len(self._buttons)
        self._buttons.append(btn)
        self._group.addButton(btn, idx)
        self._nav.addWidget(btn)
        return idx

    def add_section_header(self, text: str) -> None:
        lbl = QtWidgets.QLabel(text.upper())
        lbl.setObjectName("Muted")
        lbl.setStyleSheet("font-size: 8.5pt; font-weight: 700; padding: 14px 6px 4px 6px; letter-spacing: 1px;")
        self._nav.addWidget(lbl)

    def add_stretch(self) -> None:
        self._nav.addStretch()

    def add_footer_widget(self, w: QtWidgets.QWidget) -> None:
        self._footer.addWidget(w)

    def set_active(self, idx: int) -> None:
        if 0 <= idx < len(self._buttons):
            self._buttons[idx].setChecked(True)

    def _on_toggled(self, idx: int, checked: bool) -> None:
        if checked:
            self.section_changed.emit(idx)


# ─────────────────────────────────────────────────────────────────────
# Cards & layout helpers
# ─────────────────────────────────────────────────────────────────────

class Card(QtWidgets.QFrame):
    """Rounded container for grouping related controls."""

    def __init__(self, title: str = "", elevated: bool = False) -> None:
        super().__init__()
        self.setObjectName("CardElevated" if elevated else "Card")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(16, 14, 16, 14)
        self._layout.setSpacing(10)
        if title:
            self._title = SectionTitle(title)
            self._layout.addWidget(self._title)

    def layout(self) -> QtWidgets.QVBoxLayout:  # type: ignore[override]
        return self._layout

    def add(self, w: QtWidgets.QWidget) -> None:
        self._layout.addWidget(w)

    def add_layout(self, lay: QtWidgets.QLayout) -> None:
        self._layout.addLayout(lay)


class SectionTitle(QtWidgets.QLabel):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.setObjectName("Subheading")


class Pill(QtWidgets.QLabel):
    def __init__(self, text: str, color: str = "") -> None:
        super().__init__(text)
        self.setObjectName("Pill")
        if color:
            self.setStyleSheet(f"color: {color}; border-color: {color};")


def hsep() -> QtWidgets.QFrame:
    sep = QtWidgets.QFrame()
    sep.setObjectName("Separator")
    sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
    return sep


# ─────────────────────────────────────────────────────────────────────
# IconButton
# ─────────────────────────────────────────────────────────────────────

class IconButton(QtWidgets.QPushButton):
    def __init__(self, text: str = "", tooltip: str = "") -> None:
        super().__init__(text)
        self.setObjectName("IconButton")
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)
        self.setFixedHeight(28)


# ─────────────────────────────────────────────────────────────────────
# Recent paths (persistent dropdown)
# ─────────────────────────────────────────────────────────────────────

class DropLineEdit(QtWidgets.QLineEdit):
    """QLineEdit subclass that accepts a dropped folder/file path."""

    def __init__(self, text: str = "", parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(text, parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QtGui.QDropEvent) -> None:  # type: ignore[override]
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path:
                self.setText(path)
                event.acceptProposedAction()
                return
        super().dropEvent(event)


class RecentPathLineEdit(QtWidgets.QWidget):
    """LineEdit with a small ▾ button that shows recent paths for a key."""

    text_changed = QtCore.Signal(str)

    def __init__(self, key: str, placeholder: str = "", default: str = "") -> None:
        super().__init__()
        self._key = key
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._edit = DropLineEdit(default)
        self._edit.setPlaceholderText(placeholder)
        self._edit.textChanged.connect(self.text_changed.emit)
        layout.addWidget(self._edit, 1)

        self._dropdown = IconButton("▾", "Recent paths")
        self._dropdown.setFixedWidth(28)
        self._dropdown.clicked.connect(self._show_menu)
        layout.addWidget(self._dropdown)

    def text(self) -> str:
        return self._edit.text()

    def setText(self, value: str) -> None:
        self._edit.setText(value)

    def lineEdit(self) -> QtWidgets.QLineEdit:
        return self._edit

    def remember(self) -> None:
        value = self._edit.text().strip()
        if not value:
            return
        recents = load_recents(self._key)
        if value in recents:
            recents.remove(value)
        recents.insert(0, value)
        save_recents(self._key, recents[:10])

    def _show_menu(self) -> None:
        recents = load_recents(self._key)
        menu = QtWidgets.QMenu(self)
        if not recents:
            act = menu.addAction("(no recents)")
            act.setEnabled(False)
        else:
            for path in recents:
                act = menu.addAction(path)
                act.triggered.connect(lambda _checked=False, p=path: self.setText(p))
            menu.addSeparator()
            clear = menu.addAction("Clear recents")
            clear.triggered.connect(lambda: save_recents(self._key, []))
        menu.exec(self._dropdown.mapToGlobal(self._dropdown.rect().bottomLeft()))


def load_recents(key: str) -> list[str]:
    try:
        if os.path.exists(RECENTS_FILE):
            with open(RECENTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return list(data.get(key, []))
    except Exception as e:
        logger.warning("Failed to load recents: %s", e)
    return []


def save_recents(key: str, values: list[str]) -> None:
    try:
        os.makedirs(os.path.dirname(RECENTS_FILE), exist_ok=True)
        data: dict = {}
        if os.path.exists(RECENTS_FILE):
            try:
                with open(RECENTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data[key] = values
        with open(RECENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        logger.warning("Failed to save recents: %s", e)


# ─────────────────────────────────────────────────────────────────────
# Drop targets
# ─────────────────────────────────────────────────────────────────────

def enable_folder_drop(line_edit) -> None:
    """No-op kept for callsite compatibility. RecentPathLineEdit / DropLineEdit accept drops natively."""
    if isinstance(line_edit, QtWidgets.QLineEdit) and not isinstance(line_edit, DropLineEdit):
        # Best-effort: enable drops via event filter for raw QLineEdit instances.
        line_edit.setAcceptDrops(True)
        if not getattr(line_edit, "_drop_filter_installed", False):
            line_edit.installEventFilter(_DropFilter(line_edit))
            line_edit._drop_filter_installed = True


class _DropFilter(QtCore.QObject):
    """Event filter that converts dropped folders into line edit text."""

    def __init__(self, target: QtWidgets.QLineEdit) -> None:
        super().__init__(target)
        self._target = target

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        et = event.type()
        if et in (QtCore.QEvent.Type.DragEnter, QtCore.QEvent.Type.DragMove):
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
                return True
        elif et == QtCore.QEvent.Type.Drop:
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                if path:
                    self._target.setText(path)
                    event.acceptProposedAction()
                    return True
        return False
