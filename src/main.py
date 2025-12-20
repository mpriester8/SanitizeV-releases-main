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
    # Suppress PyInstaller cleanup warnings
    import warnings
    warnings.filterwarnings("ignore")
    
    # Clean up old files from previous update attempts (if any exist)
    try:
        import os
        import sys
        if getattr(sys, 'frozen', False):
            current_dir = os.path.dirname(sys.executable)
            
            # Remove any leftover files from old update system
            for old_file in os.listdir(current_dir):
                if old_file.endswith('.old') or old_file.endswith('.vbs') or old_file.endswith('_new.exe'):
                    old_path = os.path.join(current_dir, old_file)
                    try:
                        os.remove(old_path)
                        print(f"Cleaned up old file: {old_file}")
                    except Exception as e:
                        print(f"Could not remove {old_file}: {e}")
    except Exception as e:
        print(f"Cleanup error: {e}")
    
    # Enable High DPI Awareness
    try:
        from ctypes import windll  # pylint: disable=import-outside-toplevel
        windll.shcore.SetProcessDpiAwareness(1)
    except (ImportError, AttributeError, OSError):
        pass

    root = tk.Tk()
    
    # Set window icon
    try:
        import os
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'app_icon.ico')
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception:
        pass
    
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
                from ctypes import windll, c_int, byref  # pylint: disable=import-outside-toplevel
                # Get window handle - try multiple methods
                try:
                    hwnd = windll.user32.GetParent(root.winfo_id())
                except Exception:
                    try:
                        hwnd = int(root.wm_frame(), 16)
                    except Exception:
                        return
                
                # Set dark theme for title bar and borders (Windows 10/11)
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                DWMWA_WINDOW_CORNER_PREFERENCE = 33
                DWMWA_MICA_EFFECT = 1029  # For Windows 11
                
                try:
                    # Determine if dark mode should be enabled
                    is_dark = c_int(1 if app.theme.is_dark() else 0)
                    
                    # Try to set dark mode (use byref for proper pointer passing)
                    windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, 
                        DWMWA_USE_IMMERSIVE_DARK_MODE, 
                        byref(is_dark), 
                        4
                    )
                    
                    # Try to set window corner preference (rounded corners)
                    corner_pref = c_int(2)  # DWMWCP_ROUND
                    windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, 
                        DWMWA_WINDOW_CORNER_PREFERENCE, 
                        byref(corner_pref), 
                        4
                    )
                except Exception as e:
                    print(f"Could not set title bar theme: {e}")
        except (ImportError, AttributeError, OSError, ValueError, TypeError) as e:
            print(f"Title bar theming not supported: {e}")
    
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
                message += "\nWould you like to download the update?"
                
                if messagebox.askyesno("Update Available", message):
                    # Ask user where to save the new version
                    from tkinter import filedialog
                    save_path = filedialog.asksaveasfilename(
                        title="Save Update",
                        defaultextension=".exe",
                        initialfile=f"Sanitize_V_v{update_manager.new_version}.exe",
                        filetypes=[("Executable", "*.exe")]
                    )
                    
                    if save_path:
                        # Download in a separate thread to not freeze UI
                        def download_update():
                            result = update_manager.download_update(save_path=save_path)
                            if result:
                                messagebox.showinfo(
                                    "Download Complete",
                                    f"Update downloaded successfully to:\n{save_path}\n\n"
                                    "You can run the new version when you're ready."
                                )
                            else:
                                messagebox.showerror("Error", "Failed to download update.")
                        
                        import threading
                        thread = threading.Thread(target=download_update, daemon=True)
                        thread.start()
        
        # Check for updates asynchronously
        update_manager.check_for_updates_async(callback=on_check_complete, timeout=5)
    
    # Schedule update check after UI is shown
    root.after(2000, check_updates)
    
    root.mainloop()


if __name__ == "__main__":
    main()
