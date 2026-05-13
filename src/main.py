"""
Entry point for Sanitize V application.
"""

from __future__ import annotations

import logging
import sys

# Try to import PySide6 frontend
try:
    from gui_pyside import main as pyside_main
except ImportError:
    print("Error: PySide6 is not installed. Please install it to run Sanitize V.")
    sys.exit(1)


def main() -> None:
    """Main function to start the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Enable High DPI Awareness on Windows where available
    try:
        from ctypes import windll  # pylint: disable=import-outside-toplevel
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    pyside_main()


if __name__ == "__main__":
    main()
