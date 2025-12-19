"""
Entry point for Sanitize V application.
"""

import tkinter as tk
from tkinter import messagebox
from gui import FileMoverApp
from constants import VERSION, DEFAULT_SOURCE_DIR
from update_manager import UpdateManager


def main():
    """Main function to start the application."""
    # Enable High DPI Awareness
    try:
        from ctypes import windll  # pylint: disable=import-outside-toplevel
        windll.shcore.SetProcessDpiAwareness(1)
    except (ImportError, AttributeError, OSError):
        pass

    root = tk.Tk()
    app = FileMoverApp(root)
    
    # Check for auto-clear on startup
    def check_auto_clear():
        """Check if cache should be auto-cleared on startup."""
        from cache_scheduler import check_and_auto_clear
        def log_callback(msg):
            print(msg)
        
        # Run auto-clear if enabled
        check_and_auto_clear(DEFAULT_SOURCE_DIR, log_callback)
    
    # Schedule auto-clear check after UI is initialized
    root.after(1000, check_auto_clear)
    
    # Enable dark title bar on Windows 11/10 when in dark mode
    def set_dark_title_bar():
        """Set dark title bar for Windows."""
        try:
            import sys
            if sys.platform == 'win32':
                from ctypes import windll, c_int  # pylint: disable=import-outside-toplevel
                # Get window handle
                hwnd = int(root.wm_frame(), 16)
                # Set dark theme for title bar and borders (Windows 10/11)
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                DWMWA_WINDOW_CORNER_PREFERENCE = 33
                try:
                    # Try to set dark mode
                    windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 
                                                        c_int(1 if app.theme.is_dark() else 0), 4)
                    # Try to set window corner preference
                    windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, 
                                                        c_int(2), 4)
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
        except (ImportError, AttributeError, OSError, ValueError, TypeError):
            pass
    
    # Set title bar after window is created and visible
    root.update()
    set_dark_title_bar()
    
    # Check for updates on startup (non-blocking)
    def check_updates():
        """Check for updates after UI is initialized."""
        update_manager = UpdateManager(VERSION)
        
        def on_check_complete(update_available):
            """Callback when update check completes."""
            if update_available:
                message = (
                    f"A new version of Sanitize V is available!\n\n"
                    f"Current version: {VERSION}\n"
                    f"New version: {update_manager.new_version}\n"
                )
                if update_manager.release_notes:
                    message += f"\nRelease Notes:\n{update_manager.release_notes}\n"
                message += "\nWould you like to download and install the update?"
                
                if messagebox.askyesno("Update Available", message):
                    # Download in a separate thread to not freeze UI
                    def download_and_update():
                        exe_path = update_manager.download_update()
                        if exe_path:
                            if messagebox.askyesno(
                                "Update Downloaded",
                                "Update downloaded successfully. "
                                "The application will now close and install the update."
                            ):
                                update_manager.apply_update(exe_path)
                        else:
                            messagebox.showerror("Error", "Failed to download update.")
                    
                    import threading
                    thread = threading.Thread(target=download_and_update, daemon=True)
                    thread.start()
        
        # Check for updates asynchronously
        update_manager.check_for_updates_async(callback=on_check_complete, timeout=5)
    
    # Schedule update check after UI is shown
    root.after(2000, check_updates)
    
    root.mainloop()


if __name__ == "__main__":
    main()
