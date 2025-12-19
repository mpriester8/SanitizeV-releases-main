"""
GUI implementation for Sanitize V using Tkinter.
"""

import os
import shutil
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk, simpledialog
import xml.etree.ElementTree as ET
from datetime import datetime
from PIL import Image, ImageTk
import json

from constants import (
    DEFAULT_SOURCE_DIR, FOLDER1_NAME, FOLDER2_NAME,
    DEFAULT_XML_SOURCE_DIR, XML_FILENAME, SETTINGS_SCHEMA,
    VERSION
)
from logic import move_files_logic, revert_files_logic, clear_cache_logic, load_state
from theme import DarkMode, apply_dark_mode_to_widget


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS  # pylint: disable=no-member, protected-access
    except AttributeError:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class FileMoverApp:
    """Main application class for Sanitize V."""

    def __init__(self, root):
        self.root = root
        self.root.title(f"Sanitize V - v{VERSION}")
        self.root.geometry("850x1000")
        self.root.minsize(850, 600)
        self.root.resizable(True, True)

        # Initialize theme
        self.theme = DarkMode(theme=self.load_theme_preference())
        self.apply_theme()

        # Variables
        self.source_dir = tk.StringVar(value=DEFAULT_SOURCE_DIR)
        self.folder1_name = tk.StringVar(value=FOLDER1_NAME)
        self.folder2_name = tk.StringVar(value=FOLDER2_NAME)

        self.include_mods = tk.BooleanVar(value=True)
        self.include_plugins = tk.BooleanVar(value=True)

        self.include_xml = tk.BooleanVar(value=False)
        self.xml_source_dir = tk.StringVar(value=DEFAULT_XML_SOURCE_DIR)
        self.xml_filename = tk.StringVar(value=XML_FILENAME)
        self.replacement_xml = tk.StringVar()

        self.dest_dir = tk.StringVar()

        # Indicator Vars
        self.status_mods = tk.StringVar(value="Checking...")
        self.status_plugins = tk.StringVar(value="Checking...")
        self.last_cache_time = tk.StringVar(value="Never")

        # Load initial state
        state = load_state()
        if 'last_cache_clear' in state:
            self.last_cache_time.set(state['last_cache_clear'])

        # Load Banner Image
        self.original_banner = None
        self.photo_banner = None
        try:
            img_path = resource_path("assets/banner.png")
            if os.path.exists(img_path):
                self.original_banner = Image.open(img_path)
                # Static Resize to fit width 850
                target_width = 850
                orig_w, orig_h = self.original_banner.size
                aspect = orig_h / orig_w
                new_h = int(target_width * aspect)
                resized = self.original_banner.resize(
                    (target_width, new_h), Image.Resampling.LANCZOS
                )
                self.photo_banner = ImageTk.PhotoImage(resized)
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Failed to load banner: {e}")

        # Placeholder attributes to be defined in create_widgets
        self.control_bar = None
        self.theme_label = None
        self.theme_button = None
        self.banner_frame = None
        self.banner_label = None
        self.notebook = None
        self.tab_sanitize = None
        self.tab_xml_swap = None
        self.tab_graphics = None
        self.tab_cache = None
        self.frame_src_dir = None
        self.frame_mods = None
        self.lbl_mods_status = None
        self.frame_plugins = None
        self.lbl_plugins_status = None
        self.log_area = None
        self.frame_xml_src = None
        self.frame_rep_xml = None
        self.editor_xml_path = None
        self.editor_canvas_frame = None
        self.editor_canvas = None
        self.editor_scrollbar = None
        self.editor_scrollable_frame = None
        self.editor_vars = {}
        self.current_tree = None
        self.btn_clear_cache = None

        self._debounce_timer = None

        self.create_widgets()
        
        # Apply theme to all newly created widgets
        self.apply_theme()
        if self.theme.is_dark():
            apply_dark_mode_to_widget(self.root, self.theme, recursive=True)

        # Listeners for updates
        self.source_dir.trace_add(
            'write', lambda *args: self.update_status_indicators())

        # Initial Check
        self.update_status_indicators()

        # Auto-load XML if file exists (silent mode)
        self.load_xml_to_editor(suppress_error=True)

    def create_widgets(self):
        """Create and pack all GUI widgets."""
        # Top Control Bar with Theme Toggle
        self.control_bar = tk.Frame(self.root)
        self.control_bar.pack(fill=tk.X, padx=5, pady=5)
        
        self.theme_label = tk.Label(self.control_bar, text="Theme:")
        self.theme_label.pack(side=tk.LEFT, padx=(0, 5))
        
        self.theme_button = tk.Button(
            self.control_bar,
            text="🌙 Dark Mode" if self.theme.current_theme == 'light' else "☀️ Light Mode",
            command=self.toggle_dark_mode
        )
        self.theme_button.pack(side=tk.LEFT)

        # Banner Area (Top)
        if self.photo_banner:
            self.banner_frame = tk.Frame(self.root, bg="black")
            self.banner_frame.pack(fill=tk.X, side=tk.TOP)

            self.banner_label = tk.Label(
                self.banner_frame, image=self.photo_banner, bg="black")
            self.banner_label.pack(fill=tk.BOTH, expand=True)

        # Tab Control
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tab 1: Sanitize
        self.tab_sanitize = tk.Frame(self.notebook)
        self.notebook.add(self.tab_sanitize, text="Sanitize / Restore")
        self.setup_sanitize_tab(self.tab_sanitize)

        # Tab 2: XML Swap
        self.tab_xml_swap = tk.Frame(self.notebook)
        self.notebook.add(self.tab_xml_swap, text="XML Swap")
        self.setup_xml_swap_tab(self.tab_xml_swap)

        # Tab 3: Graphics Editor
        self.tab_graphics = tk.Frame(self.notebook)
        self.notebook.add(self.tab_graphics, text="Graphics Editor")
        self.setup_graphics_editor(self.tab_graphics)

        # Tab 4: Cache Maintenance
        self.tab_cache = tk.Frame(self.notebook)
        self.notebook.add(self.tab_cache, text="Cache Maintenance")
        self.setup_cache_tab(self.tab_cache)

    def setup_sanitize_tab(self, parent):
        """Setup widgets for the Sanitize/Restore tab."""
        # Main Content Container for Sanitize Tab
        container = tk.Frame(parent, padx=15, pady=15)
        container.pack(fill=tk.BOTH, expand=True)

        # --- Bottom Section: Buttons & Log (Packed FIRST to reserve space) ---
        bottom_frame = tk.Frame(container)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=False)

        # --- Top Section: Settings Stack ---
        top_frame = tk.Frame(container)
        top_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # --- Section 1: Mods & Plugins ---
        group_folders = tk.LabelFrame(
            top_frame, text="Mods & Plugins", padx=10, pady=10)
        group_folders.pack(fill=tk.X, pady=5)

        # Source Dir Display
        self.frame_src_dir = tk.Frame(group_folders)
        self.frame_src_dir.pack(fill=tk.X, pady=5)
        tk.Label(self.frame_src_dir, text="FiveM Source Dir:",
                 anchor='w').pack(fill=tk.X)
        src_entry_frame = tk.Frame(self.frame_src_dir)
        src_entry_frame.pack(fill=tk.X)
        tk.Entry(
            src_entry_frame, textvariable=self.source_dir
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(
            src_entry_frame, text="...", width=3,
            command=lambda: self.source_dir.set(filedialog.askdirectory())
        ).pack(side=tk.LEFT, padx=(5, 0))

        # Mods Controls
        self.frame_mods = tk.Frame(group_folders)
        self.frame_mods.pack(fill=tk.X, pady=5)
        tk.Checkbutton(
            self.frame_mods, text="Move 'mods' folder?", variable=self.include_mods
        ).pack(anchor='w')
        status_frame_m = tk.Frame(self.frame_mods)
        status_frame_m.pack(fill=tk.X, padx=20)
        tk.Label(status_frame_m, text="Status:",
                 width=6, anchor='w').pack(side=tk.LEFT)
        self.lbl_mods_status = tk.Label(
            status_frame_m, textvariable=self.status_mods, font=(
                "Arial", 9, "bold")
        )
        self.lbl_mods_status.pack(side=tk.LEFT)

        # Plugins Controls
        self.frame_plugins = tk.Frame(group_folders)
        self.frame_plugins.pack(fill=tk.X, pady=5)
        tk.Checkbutton(
            self.frame_plugins, text="Move 'plugins' folder?", variable=self.include_plugins
        ).pack(anchor='w')
        status_frame_p = tk.Frame(self.frame_plugins)
        status_frame_p.pack(fill=tk.X, padx=20)
        tk.Label(status_frame_p, text="Status:",
                 width=6, anchor='w').pack(side=tk.LEFT)
        self.lbl_plugins_status = tk.Label(
            status_frame_p, textvariable=self.status_plugins, font=(
                "Arial", 9, "bold")
        )
        self.lbl_plugins_status.pack(side=tk.LEFT)

        # --- Section 2: Backup Location (Moved underneath Mods) ---
        group_dest = tk.LabelFrame(
            top_frame, text="Backup/Storage Location", padx=10, pady=10)
        group_dest.pack(fill=tk.X, pady=10)

        self.create_path_entry_compact(
            group_dest, "Backup Directory:", self.dest_dir, True)

        # Actions
        btn_frame = tk.Frame(bottom_frame)
        btn_frame.pack(pady=(10, 10), fill=tk.X)

        btn_run = tk.Button(
            btn_frame, text="SANITIZE\n(Disable Selected)", command=self.run_forward,
            bg="#d9534f", fg="white", font=("Arial", 10, "bold"), height=2
        )
        btn_run.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        btn_revert = tk.Button(
            btn_frame, text="RESTORE\n(Enable Selected)", command=self.run_revert,
            bg="#5cb85c", fg="white", font=("Arial", 10, "bold"), height=2
        )
        btn_revert.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # Log Area
        tk.Label(bottom_frame, text="Status Log:", anchor='w').pack(fill=tk.X)
        self.log_area = scrolledtext.ScrolledText(bottom_frame, height=6)
        self.log_area.pack(fill=tk.BOTH, expand=True)

    def setup_xml_swap_tab(self, parent):
        """Setup widgets for the XML Swap tab."""
        container = tk.Frame(parent, padx=15, pady=15)
        container.pack(fill=tk.BOTH, expand=True)

        # Info
        tk.Label(
            container, text="XML Replacement Configuration", font=("Arial", 14, "bold")
        ).pack(pady=(0, 10), anchor='w')
        tk.Label(
            container,
            text="Configure how the gta5_settings.xml file is handled during the Sanitize process.",
            anchor='w'
        ).pack(pady=(0, 20), anchor='w')

        # --- Graphic Settings (XML) ---
        group_xml = tk.LabelFrame(
            container, text="Graphic Settings (XML)", padx=10, pady=10)
        group_xml.pack(fill=tk.X, pady=5)

        # Checkbox
        tk.Checkbutton(
            group_xml, text="Enable XML Swap",
            variable=self.include_xml, command=self.toggle_xml_inputs
        ).pack(anchor='w')

        # XML Source Dir
        self.frame_xml_src = tk.Frame(group_xml)
        self.frame_xml_src.pack(fill=tk.X, pady=5)
        tk.Label(self.frame_xml_src, text="XML Source Dir:",
                 anchor='w').pack(fill=tk.X)
        tk.Entry(
            self.frame_xml_src, textvariable=self.xml_source_dir, state='readonly', bg="#f0f0f0"
        ).pack(fill=tk.X)

        # Replacement XML Picker
        self.frame_rep_xml = tk.Frame(group_xml)
        self.frame_rep_xml.pack(fill=tk.X, pady=5)
        self.create_path_entry_compact(
            self.frame_rep_xml, "New XML File:", self.replacement_xml, False
        )

        # Init state
        self.toggle_xml_inputs()

    def setup_cache_tab(self, parent):
        """Setup widgets for the Cache Maintenance tab."""
        # Center container
        container = tk.Frame(parent, padx=30, pady=30)
        container.pack(fill=tk.BOTH, expand=True)

        # Info
        tk.Label(
            container, text="Cache Maintenance", font=("Arial", 16, "bold")
        ).pack(pady=(0, 20))
        tk.Label(
            container,
            text="This will delete the 'cache', 'server-cache', and 'server-cache-priv'\n"
                 "folders from your FiveM application data directory.",
            justify=tk.CENTER
        ).pack(pady=(0, 20))

        # Status
        status_frame = tk.Frame(container)
        status_frame.pack(pady=10)
        tk.Label(status_frame, text="Last Cleared:",
                 font=("Arial", 10)).pack(side=tk.LEFT)
        tk.Label(
            status_frame, textvariable=self.last_cache_time,
            font=("Arial", 10, "bold"), fg="blue"
        ).pack(side=tk.LEFT, padx=5)

        # Action
        self.btn_clear_cache = tk.Button(
            container, text="CLEAR CACHE NOW", command=self.run_clear_cache,
            bg="orange", fg="white", font=("Arial", 12, "bold"), height=2, width=20
        )
        self.btn_clear_cache.pack(pady=20)

    def setup_graphics_editor(self, parent):
        """Setup widgets for the Graphics Editor tab."""
        # Top: File Loading
        top_frame = tk.Frame(parent, padx=10, pady=10)
        top_frame.pack(fill=tk.X)

        tk.Label(top_frame, text="XML File Path:").pack(side=tk.LEFT)
        self.editor_xml_path = tk.StringVar(
            value=os.path.join(DEFAULT_XML_SOURCE_DIR, XML_FILENAME)
        )
        tk.Entry(
            top_frame, textvariable=self.editor_xml_path
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(
            top_frame, text="Browse",
            command=lambda: self.editor_xml_path.set(
                filedialog.askopenfilename(filetypes=[("XML files", "*.xml")])
            )
        ).pack(side=tk.LEFT)
        tk.Button(
            top_frame, text="LOAD", command=self.load_xml_to_editor,
            bg="#5bc0de", fg="white", font=("Arial", 9, "bold")
        ).pack(side=tk.LEFT, padx=5)

        # Middle: Scrollable Editor Area
        self.editor_canvas_frame = tk.Frame(parent)
        self.editor_canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10)

        self.editor_canvas = tk.Canvas(self.editor_canvas_frame)
        self.editor_scrollbar = ttk.Scrollbar(
            self.editor_canvas_frame, orient="vertical", command=self.editor_canvas.yview
        )
        self.editor_scrollable_frame = tk.Frame(self.editor_canvas)

        self.editor_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.editor_canvas.configure(
                scrollregion=self.editor_canvas.bbox("all"))
        )

        self.editor_canvas.create_window(
            (0, 0), window=self.editor_scrollable_frame, anchor="nw")
        self.editor_canvas.configure(yscrollcommand=self.editor_scrollbar.set)

        self.editor_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.editor_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mousewheel scrolling
        def _on_mousewheel(event):
            self.editor_canvas.yview_scroll(
                int(-1 * (event.delta / 120)), "units")
        self.editor_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _update_scroll_region(event):
            self.editor_canvas.configure(
                scrollregion=self.editor_canvas.bbox("all"))

        self.editor_scrollable_frame.bind("<Configure>", _update_scroll_region)

        # Bottom: Save
        bottom_frame = tk.Frame(parent, padx=10, pady=10)
        bottom_frame.pack(fill=tk.X)
        tk.Button(
            bottom_frame, text="SAVE NEW XML", command=self.save_xml_from_editor,
            bg="#5cb85c", fg="white", font=("Arial", 10, "bold"), height=2
        ).pack(fill=tk.X)

        self.editor_vars = {}  # Dictionary to hold TK variables mapped to XML keys/paths
        self.current_tree = None

    def load_xml_to_editor(self, suppress_error=False):
        """Load XML file content into the editor."""
        path = self.editor_xml_path.get()
        if not os.path.exists(path):
            if not suppress_error:
                messagebox.showerror("Error", "File not found.")
            return

        try:
            tree = ET.parse(path)
            self.current_tree = tree
            root = tree.getroot()

            # Clear existing widgets in scrollable frame
            for widget in self.editor_scrollable_frame.winfo_children():
                widget.destroy()
            self.editor_vars = {}

            # We iterate through SETTINGS_SCHEMA and find each setting in its respective section

            # Create a container frame
            lf = tk.LabelFrame(
                self.editor_scrollable_frame, text="SETTINGS",
                padx=5, pady=5, font=("Arial", 10, "bold")
            )
            lf.pack(fill=tk.X, pady=5, padx=5)

            # Configure Grid for 2 columns
            lf.grid_columnconfigure(0, weight=1)
            lf.grid_columnconfigure(1, weight=1)

            for i, (tag, meta) in enumerate(SETTINGS_SCHEMA.items()):
                # Calculate Grid Position
                row_idx = i // 2
                col_idx = i % 2

                # Find section
                section_name = meta.get("section", "graphics")
                section_node = root.find(section_name)

                current_val = None
                if section_node is not None:
                    node = section_node.find(tag)
                    if node is not None:
                        current_val = node.get("value")

                # Default if missing
                if current_val is None:
                    if meta["type"] == "combobox":
                        current_val = meta["options"][0][0]  # First option
                    else:
                        current_val = str(meta["xml_range"][0])  # Min value

                # Create Row Frame
                f = tk.Frame(lf, pady=2)
                f.grid(row=row_idx, column=col_idx,
                       sticky='ew', padx=5, pady=5)

                # Use grid inside the item frame as well for alignment, or pack left
                tk.Label(f, text=meta["label"], width=25,
                         anchor='w').pack(side=tk.LEFT)

                if meta["type"] == "combobox":
                    # Combobox Logic
                    options_display = [
                        f"{desc} ({val})" for val, desc in meta["options"]]

                    current_selection = ""
                    for val, desc in meta["options"]:
                        # Case insensitive check for boolean strings if needed
                        if str(val).lower() == str(current_val).lower():
                            current_selection = f"{desc} ({val})"
                            break

                    if not current_selection:
                        current_selection = current_val  # Fallback

                    var = tk.StringVar(value=current_selection)
                    cb = ttk.Combobox(
                        f, textvariable=var, values=options_display, state="readonly", width=25
                    )
                    cb.pack(side=tk.LEFT)
                    self.editor_vars[tag] = var

                elif meta["type"] == "slider":
                    # Slider Logic
                    ui_min, ui_max = meta["ui_range"]
                    xml_min, xml_max = meta["xml_range"]

                    # Convert XML float to UI int/float
                    try:
                        f_val = float(current_val)
                        # Linear mapping
                        if xml_max == xml_min:  # Avoid div by zero
                            ratio = 0
                        else:
                            ratio = (f_val - xml_min) / (xml_max - xml_min)

                        ui_val = ui_min + ratio * (ui_max - ui_min)
                    except ValueError:
                        ui_val = ui_min

                    var = tk.DoubleVar(value=ui_val)
                    scale = tk.Scale(
                        f, variable=var, from_=ui_min, to=ui_max,
                        orient=tk.HORIZONTAL, resolution=1, length=120
                    )
                    scale.pack(side=tk.LEFT)

                    # Add value label to show current value
                    val_label = tk.Label(f, text=f"{ui_val:.0f}")
                    val_label.pack(side=tk.LEFT, padx=5)
                    # Update label on change

                    def update_label(v, lbl=val_label):
                        lbl.config(text=f"{float(v):.0f}")
                    scale.config(command=update_label)

                    self.editor_vars[tag] = var

        except Exception as e:  # pylint: disable=broad-exception-caught
            messagebox.showerror("Error", f"Failed to parse XML: {e}")
        
        # Apply theme to all newly created widgets
        apply_dark_mode_to_widget(self.editor_scrollable_frame, self.theme, recursive=True)

    def save_xml_from_editor(self):
        """Save the current editor values back to the XML file."""
        if not self.current_tree:
            return

        try:
            root = self.current_tree.getroot()

            # Ensure sections exist
            for sec in ["graphics", "video"]:
                if root.find(sec) is None:
                    ET.SubElement(root, sec)

            # Update Tree
            for tag, meta in SETTINGS_SCHEMA.items():
                section_name = meta.get("section", "graphics")
                section_node = root.find(section_name)

                var = self.editor_vars.get(tag)
                if not var:
                    continue

                final_val = ""

                if meta["type"] == "combobox":
                    display_val = var.get()
                    # Extract raw value inside ()
                    if '(' in display_val and display_val.endswith(')'):
                        final_val = display_val.split(
                            '(')[-1].replace(')', '').strip()
                    else:
                        final_val = display_val

                elif meta["type"] == "slider":
                    ui_val = var.get()
                    ui_min, ui_max = meta["ui_range"]
                    xml_min, xml_max = meta["xml_range"]

                    # Map back
                    if ui_max == ui_min:
                        ratio = 0
                    else:
                        ratio = (ui_val - ui_min) / (ui_max - ui_min)

                    f_val = xml_min + ratio * (xml_max - xml_min)
                    final_val = f"{f_val:.6f}"  # Format as float string

                # Update Node
                node = section_node.find(tag)
                if node is not None:
                    node.set("value", final_val)
                else:
                    new_node = ET.SubElement(section_node, tag)
                    new_node.set("value", final_val)

            # Automatic Logic: Reflection_MipBlur
            # Enabled if ReflectionQuality is Very High (2) or Ultra (3), else disabled
            ref_qual_var = self.editor_vars.get("ReflectionQuality")
            if ref_qual_var:
                display_val = ref_qual_var.get()
                # Extract raw value: "Ultra (3)" -> "3"
                if '(' in display_val and display_val.endswith(')'):
                    raw_ref_val = display_val.split(
                        '(')[-1].replace(')', '').strip()
                else:
                    raw_ref_val = display_val

                mip_blur_val = "false"
                if raw_ref_val in ["2", "3"]:
                    mip_blur_val = "true"

                # Update/Create Reflection_MipBlur in graphics section
                g_sec = root.find("graphics")
                if g_sec is not None:
                    mip_node = g_sec.find("Reflection_MipBlur")
                    if mip_node is not None:
                        mip_node.set("value", mip_blur_val)
                    else:
                        new_mip = ET.SubElement(g_sec, "Reflection_MipBlur")
                        new_mip.set("value", mip_blur_val)

            # Logic: Save to new file, then Backup Original, then Replace Original
            target_path = self.editor_xml_path.get()

            # 1. Create Backup of Original
            if os.path.exists(target_path):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"{target_path}.{timestamp}.bak"
                shutil.copy2(target_path, backup_path)
                backup_msg = f"Backup created at:\n{backup_path}"
            else:
                backup_msg = "Original file not found, skipping backup."

            # 2. Overwrite Original with New Data
            self.current_tree.write(
                target_path, encoding="UTF-8", xml_declaration=True)

            messagebox.showinfo("Success", f"Settings Saved!\n\n{backup_msg}")

        except Exception as e:  # pylint: disable=broad-exception-caught
            messagebox.showerror("Error", f"Failed to save XML: {e}")

    def create_path_entry_compact(self, parent, label_text, variable, is_dir):
        """Helper to create a path entry with browse button."""
        tk.Label(parent, text=label_text, anchor='w').pack(fill=tk.X)
        f = tk.Frame(parent)
        f.pack(fill=tk.X)
        tk.Entry(f, textvariable=variable).pack(
            side=tk.LEFT, fill=tk.X, expand=True)
        if is_dir:
            def cmd(): return variable.set(filedialog.askdirectory())
        else:
            def cmd(): return variable.set(
                filedialog.askopenfilename(
                    filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
                )
            )
        tk.Button(f, text="...", width=3, command=cmd).pack(
            side=tk.LEFT, padx=(5, 0))

    def toggle_xml_inputs(self):
        """Enable/Disable XML input widgets based on checkbox."""
        state = 'normal' if self.include_xml.get() else 'disabled'

        def set_state(widget):
            try:
                widget.configure(state=state)
            except tk.TclError:
                pass
            for child in widget.winfo_children():
                set_state(child)
        for child in self.frame_rep_xml.winfo_children():
            set_state(child)

    def update_status_indicators(self):
        """Schedule status update with debouncing."""
        if hasattr(self, '_debounce_timer') and self._debounce_timer is not None:
            self.root.after_cancel(self._debounce_timer)

        # 500ms delay to debounce user input
        self._debounce_timer = self.root.after(
            500, self._perform_status_update)

    def _perform_status_update(self):
        """Update the status labels checking for existence of mods/plugins."""
        self._debounce_timer = None

        src = self.source_dir.get()
        f1 = self.folder1_name.get()
        f2 = self.folder2_name.get()

        # Check Mods
        mods_path = os.path.join(src, f1)
        if os.path.exists(mods_path):
            try:
                file_count = 0
                for _, _, files in os.walk(mods_path):
                    file_count += len(files)
                self.status_mods.set(f"FOUND ({file_count} files)")
                self.lbl_mods_status.config(fg="green")
            except OSError:
                self.status_mods.set("FOUND (Error counting)")
                self.lbl_mods_status.config(fg="orange")
        else:
            self.status_mods.set("NOT FOUND")
            self.lbl_mods_status.config(fg="red")

        # Check Plugins
        if os.path.exists(os.path.join(src, f2)):
            self.status_plugins.set("FOUND (Active)")
            self.lbl_plugins_status.config(fg="green")
        else:
            self.status_plugins.set("NOT FOUND")
            self.lbl_plugins_status.config(fg="red")

    def log(self, message):
        """Append message to the log area."""
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.root.update_idletasks()

    def validate_inputs(self):
        """Validate required inputs before running operations."""
        dest = self.dest_dir.get()
        if not dest:
            messagebox.showerror("Error", "Please select a Backup Directory.")
            return None
        return True

    def run_clear_cache(self):
        """Execute cache clearing logic."""
        src = self.source_dir.get()
        if not src:
            messagebox.showerror("Error", "Source Directory is invalid.")
            return

        if not messagebox.askyesno(
            "Confirm Cache Clear",
            "Are you sure you want to delete all cache files?\nThis cannot be undone."
        ):
            return

        success, timestamp = clear_cache_logic(src, self.log)
        if success:
            self.last_cache_time.set(timestamp)
            messagebox.showinfo("Success", "Cache folders cleared.")
        else:
            messagebox.showwarning(
                "Warning", "Issues encountered clearing cache. Check logs.")

    def run_forward(self):
        """Execute the sanitize (forward) operation."""
        self.log_area.delete(1.0, tk.END)
        if not self.validate_inputs():
            return

        src_dir = self.source_dir.get()
        f1 = self.folder1_name.get()
        f2 = self.folder2_name.get()
        xml_src_dir = self.xml_source_dir.get()
        xml_file = self.xml_filename.get()
        dest = self.dest_dir.get()

        inc_mods = self.include_mods.get()
        inc_plugins = self.include_plugins.get()
        inc_xml = self.include_xml.get()

        rep_xml_path = ""
        if inc_xml:
            rep_xml_path = self.replacement_xml.get()
            if not rep_xml_path:
                messagebox.showerror(
                    "Error", "Please select a Replacement XML file.")
                return

        success = move_files_logic(
            src_dir, f1, f2, xml_src_dir, xml_file, rep_xml_path, dest,
            include_mods=inc_mods, include_plugins=inc_plugins,
            include_xml=inc_xml, log_callback=self.log,
            prompt_callback=simpledialog.askstring
        )
        if success:
            messagebox.showinfo(
                "Success", "Sanitization Complete (Selected Items Disabled).")
        self.update_status_indicators()

    def run_revert(self):
        """Execute the restore (revert) operation."""
        self.log_area.delete(1.0, tk.END)
        if not self.validate_inputs():
            return

        src_dir = self.source_dir.get()
        f1 = self.folder1_name.get()
        f2 = self.folder2_name.get()
        xml_src_dir = self.xml_source_dir.get()
        xml_file = self.xml_filename.get()
        dest = self.dest_dir.get()

        inc_mods = self.include_mods.get()
        inc_plugins = self.include_plugins.get()
        inc_xml = self.include_xml.get()

        restore_xml_target = None
        if inc_xml:
            # We need to ask the user which XML to restore if there are options,
            # or if the default name doesn't exist.
            # Simple approach: Ask user to select the backup XML file.
            msg = (
                "Please select the Backup XML file to restore.\n"
                "(It was likely renamed during backup, e.g. gta5_settings_Original.xml)"
            )
            messagebox.showinfo("Select Backup XML", msg)
            restore_xml_target = filedialog.askopenfilename(
                initialdir=dest, title="Select Backup XML to Restore",
                filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
            )
            if not restore_xml_target:
                self.log("Restore Cancelled: No backup XML selected.")
                return

        success = revert_files_logic(
            src_dir, f1, f2, xml_src_dir, xml_file, dest,
            include_mods=inc_mods, include_plugins=inc_plugins,
            include_xml=inc_xml, restore_xml_path=restore_xml_target,
            log_callback=self.log
        )
        if success:
            messagebox.showinfo(
                "Success", "Restoration Complete (Selected Items Enabled).")
        self.update_status_indicators()
    def load_theme_preference(self):
        """Load theme preference from settings."""
        try:
            # First try APPDATA (new location)
            appdata_dir = os.path.expandvars(r"%APPDATA%\SanitizeV")
            if not os.path.exists(appdata_dir):
                os.makedirs(appdata_dir, exist_ok=True)
            settings_file = os.path.join(appdata_dir, "app_settings.json")
            
            # If not found in APPDATA, check TEMP (old location)
            if not os.path.exists(settings_file):
                temp_dir = os.path.expandvars(r"%TEMP%\SanitizeV")
                temp_settings_file = os.path.join(temp_dir, "app_settings.json")
                if os.path.exists(temp_settings_file):
                    with open(temp_settings_file, 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                        theme = settings.get('theme', 'light')
                        # Save to new location for future use
                        self._save_to_appdata(appdata_dir, settings_file, settings)
                        return theme
            
            if os.path.exists(settings_file):
                with open(settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    return settings.get('theme', 'light')
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        return 'light'
    
    def _save_to_appdata(self, appdata_dir, settings_file, settings):
        """Helper method to save settings to APPDATA."""
        try:
            if not os.path.exists(appdata_dir):
                os.makedirs(appdata_dir, exist_ok=True)
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def save_theme_preference(self):
        """Save theme preference to settings."""
        try:
            appdata_dir = os.path.expandvars(r"%APPDATA%\SanitizeV")
            if not os.path.exists(appdata_dir):
                os.makedirs(appdata_dir, exist_ok=True)
            settings_file = os.path.join(appdata_dir, "app_settings.json")
            settings = {'theme': self.theme.current_theme}
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def apply_theme(self):
        """Apply current theme to the application."""
        colors = self.theme.get_colors()
        self.root.config(bg=colors['bg'])
        self.theme.create_ttk_style()
        
        # Apply theme to control bar (only if widgets have been created)
        if hasattr(self, 'control_bar') and self.control_bar:
            self.control_bar.config(bg=colors['bg'])
        if hasattr(self, 'theme_label') and self.theme_label:
            self.theme_label.config(bg=colors['bg'], fg=colors['fg'])
        if hasattr(self, 'theme_button') and self.theme_button:
            self.theme_button.config(bg=colors['button_bg'], fg=colors['fg'], 
                                     activebackground=colors['accent'], activeforeground='white')
        
        # Apply theme to status log if it exists
        if hasattr(self, 'log_area') and self.log_area:
            self.log_area.config(
                bg=colors['text_bg'],
                fg=colors['text_fg'],
                insertbackground=colors['fg']
            )

    def toggle_dark_mode(self):
        """Toggle between light and dark mode."""
        new_theme = 'dark' if self.theme.current_theme == 'light' else 'light'
        self.theme.set_theme(new_theme)
        self.save_theme_preference()
        self.apply_theme()
        
        # Update theme button text
        if self.theme_button:
            self.theme_button.config(
                text="🌙 Dark Mode" if self.theme.current_theme == 'light' else "☀️ Light Mode"
            )
        
        # Apply theme recursively to all widgets
        apply_dark_mode_to_widget(self.root, self.theme, recursive=True)
        
        # Force update of all widgets
        self.root.update_idletasks()
        
        # Update title bar for Windows
        try:
            import sys
            if sys.platform == 'win32':
                from ctypes import windll, c_int  # pylint: disable=import-outside-toplevel
                hwnd = int(self.root.wm_frame(), 16)
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                DWMWA_WINDOW_CORNER_PREFERENCE = 33
                try:
                    windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 
                                                        c_int(1 if self.theme.is_dark() else 0), 4)
                    windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, 
                                                        c_int(2), 4)
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
        except (ImportError, AttributeError, OSError, ValueError, TypeError):
            pass
        
        messagebox.showinfo(
            "Theme Changed", 
            f"Switched to {new_theme.upper()} mode."
        )