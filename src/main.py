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
            
            # Remove any leftover files from old update system in exe directory
            for old_file in os.listdir(current_dir):
                if old_file.endswith('.old') or old_file.endswith('.vbs') or old_file.endswith('_new.exe'):
                    old_path = os.path.join(current_dir, old_file)
                    try:
                        os.remove(old_path)
                        print(f"Cleaned up old file: {old_file}")
                    except Exception as e:
                        print(f"Could not remove {old_file}: {e}")
            
            # Clean up old files from temp directory
            try:
                import tempfile
                temp_dir = tempfile.gettempdir()
                
                # Remove VBS updater script
                temp_vbs = os.path.join(temp_dir, "sanitize_v_updater.vbs")
                if os.path.exists(temp_vbs):
                    try:
                        os.remove(temp_vbs)
                        print("Cleaned up temp VBS file")
                    except:
                        pass
                
                # Remove any .old exe files in temp
                exe_name = os.path.basename(sys.executable)
                old_exe_in_temp = os.path.join(temp_dir, exe_name + ".old")
                if os.path.exists(old_exe_in_temp):
                    try:
                        os.remove(old_exe_in_temp)
                        print("Cleaned up old exe from temp")
                    except:
                        pass

                # Clean up orphaned PyInstaller _MEI folders (from crashed/failed updates)
                # Only clean folders older than 1 hour to avoid removing active ones
                import time
                current_time = time.time()
                one_hour_ago = current_time - 3600
                current_mei = os.path.basename(getattr(sys, '_MEIPASS', ''))

                for item in os.listdir(temp_dir):
                    if item.startswith('_MEI') and item != current_mei:
                        mei_path = os.path.join(temp_dir, item)
                        try:
                            if os.path.isdir(mei_path):
                                # Only remove if older than 1 hour
                                folder_mtime = os.path.getmtime(mei_path)
                                if folder_mtime < one_hour_ago:
                                    import shutil
                                    shutil.rmtree(mei_path, ignore_errors=True)
                                    print(f"Cleaned up old _MEI folder: {item}")
                        except:
                            pass
            except:
                pass
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
                    # Download and apply update
                    def download_and_install():
                        exe_path = update_manager.download_update()
                        if exe_path:
                            # Show notification before restart
                            def show_restart_notice():
                                messagebox.showinfo(
                                    "Restarting",
                                    f"Update downloaded successfully!\n\n"
                                    f"The application will now restart to complete the update.\n"
                                    f"Please wait..."
                                )
                                # Apply update after user acknowledges (will close this app and restart)
                                update_manager.apply_update(exe_path)

                            # Schedule the messagebox on the main thread
                            root.after(0, show_restart_notice)
                        else:
                            def show_error():
                                messagebox.showerror("Error", "Failed to download update. Please try again later.")
                            root.after(0, show_error)

                    import threading
                    thread = threading.Thread(target=download_and_install, daemon=True)
                    thread.start()
        
        # Check for updates asynchronously
        update_manager.check_for_updates_async(callback=on_check_complete, timeout=5)
    
    # Schedule update check after UI is shown
    root.after(2000, check_updates)
    
    root.mainloop()


if __name__ == "__main__":
    main()
