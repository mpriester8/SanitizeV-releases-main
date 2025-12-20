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
    
    # Clean up old exe files from previous update
    # Wait longer for previous process to fully terminate
    import time
    time.sleep(3)  # Increased to 3 seconds to allow complete cleanup
    
    try:
        import os
        import sys
        if getattr(sys, 'frozen', False):
            current_dir = os.path.dirname(sys.executable)
            
            # Also try to clean up old PyInstaller temp directories
            try:
                import tempfile
                temp_base = tempfile.gettempdir()
                for item in os.listdir(temp_base):
                    if item.startswith('_MEI') and item != os.path.basename(getattr(sys, '_MEIPASS', '')):
                        old_temp = os.path.join(temp_base, item)
                        try:
                            import shutil
                            shutil.rmtree(old_temp, ignore_errors=True)
                            print(f"Cleaned up old temp directory: {item}")
                        except:
                            pass
            except:
                pass
            
            # Remove .old files with retry logic
            for old_file in os.listdir(current_dir):
                if old_file.endswith('.old') or old_file.endswith('_new.exe'):
                    old_path = os.path.join(current_dir, old_file)
                    # Try multiple times with longer delays (file might be locked)
                    for attempt in range(10):
                        try:
                            os.remove(old_path)
                            print(f"Cleaned up old update file: {old_file}")
                            break
                        except Exception as e:
                            if attempt < 9:
                                time.sleep(1)  # Increased to 1 second per retry
                                print(f"Retry {attempt + 1}/10: Waiting for {old_file} to unlock...")
                            else:
                                print(f"Could not remove {old_file} after 10 attempts: {e}")
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
