"""
Command palette for Sanitize V (Ctrl+K).

Fuzzy-search across all registered actions, sections, snippets, and recents.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from PySide6 import QtCore, QtGui, QtWidgets


@dataclass
class PaletteAction:
    title: str
    subtitle: str
    callback: Callable[[], None]
    category: str = ""
    keywords: str = ""


def _score(query: str, action: PaletteAction) -> int:
    """Return a relevance score. Higher is better; <=0 means no match."""
    if not query:
        return 1
    q = query.lower()
    haystack = f"{action.title} {action.subtitle} {action.category} {action.keywords}".lower()

    if q in haystack:
        score = 100
        if action.title.lower().startswith(q):
            score += 200
        elif q in action.title.lower():
            score += 100
        return score

    # subsequence match (chars appear in order)
    i = 0
    for ch in haystack:
        if i < len(q) and ch == q[i]:
            i += 1
    return 30 if i == len(q) else 0


class CommandPalette(QtWidgets.QDialog):
    """Modal floating palette."""

    def __init__(self, parent: QtWidgets.QWidget, actions: list[PaletteAction]) -> None:
        super().__init__(parent)
        self._actions = actions
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.Dialog
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setFixedWidth(620)

        wrapper = QtWidgets.QVBoxLayout(self)
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.setSpacing(0)

        frame = QtWidgets.QFrame()
        frame.setObjectName("Palette")
        frame_layout = QtWidgets.QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 8)
        frame_layout.setSpacing(0)
        wrapper.addWidget(frame)

        self._input = QtWidgets.QLineEdit()
        self._input.setObjectName("PaletteInput")
        self._input.setPlaceholderText("Search actions, pages, snippets...")
        self._input.textChanged.connect(self._refresh)
        self._input.returnPressed.connect(self._activate_current)
        frame_layout.addWidget(self._input)

        self._results = QtWidgets.QListWidget()
        self._results.setObjectName("PaletteResults")
        self._results.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._results.itemActivated.connect(lambda _i: self._activate_current())
        self._results.itemClicked.connect(lambda _i: self._activate_current())
        self._results.setMinimumHeight(360)
        frame_layout.addWidget(self._results, 1)

        # Shortcut hint
        hint = QtWidgets.QLabel("↑↓ navigate    ↵ select    esc close")
        hint.setObjectName("Dim")
        hint.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("padding: 4px;")
        frame_layout.addWidget(hint)

        self._refresh()
        self._input.setFocus()

    def _refresh(self) -> None:
        query = self._input.text().strip()
        ranked: list[tuple[int, PaletteAction]] = []
        for a in self._actions:
            s = _score(query, a)
            if s > 0:
                ranked.append((s, a))
        ranked.sort(key=lambda t: -t[0])

        self._results.clear()
        for score, a in ranked[:50]:
            label = a.title
            if a.category:
                label += f"   ·  {a.category}"
            if a.subtitle:
                label += f"\n{a.subtitle}"
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, a)
            self._results.addItem(item)

        if self._results.count():
            self._results.setCurrentRow(0)

    def _activate_current(self) -> None:
        item = self._results.currentItem()
        if not item:
            return
        action: PaletteAction = item.data(QtCore.Qt.ItemDataRole.UserRole)
        self.accept()
        try:
            action.callback()
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Palette action failed: %s", action.title)

    def keyPressEvent(self, ev: QtGui.QKeyEvent) -> None:
        if ev.key() == QtCore.Qt.Key.Key_Escape:
            self.reject()
            return
        if ev.key() in (QtCore.Qt.Key.Key_Down, QtCore.Qt.Key.Key_Up):
            self._results.setFocus()
            self._results.event(ev)
            self._input.setFocus()
            return
        super().keyPressEvent(ev)

    def showEvent(self, ev: QtGui.QShowEvent) -> None:
        # Center over parent
        parent = self.parentWidget()
        if parent:
            geo = parent.geometry()
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + 80
            self.move(x, y)
        super().showEvent(ev)


def install_shortcut(window: QtWidgets.QMainWindow, get_actions: Callable[[], list[PaletteAction]]) -> None:
    """Register Ctrl+K (and Cmd+K) to open the palette."""
    def open_palette() -> None:
        dlg = CommandPalette(window, get_actions())
        dlg.exec()

    for key in ("Ctrl+K", "Ctrl+P", "Meta+K"):
        sc = QtGui.QShortcut(QtGui.QKeySequence(key), window)
        sc.activated.connect(open_palette)
