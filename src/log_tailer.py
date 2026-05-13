"""
Live log tailer for FiveM server logs.

A QThread wrapper that follows a log file and emits color-classified lines.
Supports regex filtering and recognizes resource boundaries.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Optional

from PySide6 import QtCore


@dataclass
class LogLine:
    raw: str
    level: str   # 'info' | 'warning' | 'error' | 'debug' | 'success'
    resource: Optional[str]


_LEVEL_PATTERNS = (
    (re.compile(r"\b(error|exception|traceback|fatal|failed)\b", re.I), "error"),
    (re.compile(r"\b(warn|warning|deprecat)\b", re.I), "warning"),
    (re.compile(r"\b(success|started|loaded|ready|connect(?:ed)?)\b", re.I), "success"),
    (re.compile(r"\b(debug|trace)\b", re.I), "debug"),
)
_RESOURCE_RE = re.compile(r"\[\s*(?:script|resource)?\s*:?\s*([\w\-]+)\s*\]", re.I)


def classify(line: str) -> LogLine:
    level = "info"
    for rx, lvl in _LEVEL_PATTERNS:
        if rx.search(line):
            level = lvl
            break
    resource: Optional[str] = None
    m = _RESOURCE_RE.search(line)
    if m:
        resource = m.group(1)
    return LogLine(raw=line.rstrip("\n"), level=level, resource=resource)


class LogTailWorker(QtCore.QThread):
    line_emitted = QtCore.Signal(object)  # LogLine
    error_emitted = QtCore.Signal(str)
    stopped = QtCore.Signal()

    def __init__(self, path: str, follow: bool = True, poll_seconds: float = 0.4, parent=None):
        super().__init__(parent)
        self.path = path
        self.follow = follow
        self.poll_seconds = poll_seconds
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        if not os.path.exists(self.path):
            self.error_emitted.emit(f"Log file not found: {self.path}")
            self.stopped.emit()
            return

        try:
            with open(self.path, "r", encoding="utf-8", errors="replace") as f:
                # Replay last ~200 lines so the user sees context
                try:
                    f.seek(0, os.SEEK_END)
                    size = f.tell()
                    chunk = min(size, 64 * 1024)
                    f.seek(max(0, size - chunk))
                    tail = f.readlines()[-200:]
                    for raw in tail:
                        if self._stop:
                            break
                        self.line_emitted.emit(classify(raw))
                except Exception:
                    f.seek(0, os.SEEK_END)

                if not self.follow:
                    self.stopped.emit()
                    return

                while not self._stop:
                    line = f.readline()
                    if not line:
                        time.sleep(self.poll_seconds)
                        continue
                    self.line_emitted.emit(classify(line))
        except Exception as e:
            self.error_emitted.emit(f"Log tail failed: {e}")
        finally:
            self.stopped.emit()
