"""
Dark mode theme support for Sanitize V.
"""

from tkinter import ttk


class DarkMode:
    """Dark mode theme definitions and utilities."""
    
    # Color palette
    COLORS = {
        # Light theme
        'light': {
            'bg': '#ffffff',
            'fg': '#000000',
            'button_bg': '#f0f0f0',
            'button_fg': '#000000',
            'entry_bg': '#ffffff',
            'entry_fg': '#000000',
            'frame_bg': '#f5f5f5',
            'label_bg': '#f5f5f5',
            'text_bg': '#ffffff',
            'text_fg': '#000000',
            'accent': '#0078d4',
            'disabled': '#cccccc',
        },
        # Dark theme
        'dark': {
            'bg': '#1e1e1e',
            'fg': '#e0e0e0',
            'button_bg': '#2d2d2d',
            'button_fg': '#e0e0e0',
            'entry_bg': '#2d2d2d',
            'entry_fg': '#f0f0f0',
            'frame_bg': '#252525',
            'label_bg': '#1e1e1e',
            'text_bg': '#1a1a1a',
            'text_fg': '#f0f0f0',
            'accent': '#0078d4',
            'disabled': '#555555',
            'tab_bg': '#2d2d2d',
            'tab_fg': '#f0f0f0',
        }
    }
    
    def __init__(self, theme='light'):
        """Initialize theme."""
        self.current_theme = theme if theme in self.COLORS else 'light'
    
    def get_colors(self):
        """Get current theme colors."""
        return self.COLORS[self.current_theme]
    
    def set_theme(self, theme):
        """Set the current theme."""
        if theme in self.COLORS:
            self.current_theme = theme
    
    def is_dark(self):
        """Check if dark mode is enabled."""
        return self.current_theme == 'dark'
    
    def create_ttk_style(self):
        """Create and configure ttk style for current theme."""
        style = ttk.Style()
        colors = self.get_colors()
        
        style.theme_use('clam')
        
        # Configure colors for different elements
        style.configure(
            'TFrame',
            background=colors['frame_bg'],
            foreground=colors['fg']
        )
        
        style.configure(
            'TLabel',
            background=colors['label_bg'],
            foreground=colors['fg']
        )
        
        style.configure(
            'TButton',
            background=colors['button_bg'],
            foreground=colors['fg'],
            borderwidth=1
        )
        style.map(
            'TButton',
            background=[('active', colors['accent'])],
            foreground=[('active', '#ffffff')]
        )
        
        style.configure(
            'TEntry',
            fieldbackground=colors['entry_bg'],
            foreground=colors['entry_fg'],
            borderwidth=1
        )
        
        style.configure(
            'TCheckbutton',
            background=colors['frame_bg'],
            foreground=colors['fg']
        )
        
        style.configure(
            'TRadiobutton',
            background=colors['frame_bg'],
            foreground=colors['fg']
        )
        
        style.configure(
            'TNotebook',
            background=colors['bg'],
            foreground=colors['fg']
        )
        
        style.configure(
            'TNotebook.Tab',
            background=colors.get('tab_bg', colors['button_bg']),
            foreground=colors.get('tab_fg', colors['fg']),
            padding=[10, 5]
        )
        style.map(
            'TNotebook.Tab',
            background=[('selected', colors['accent'])],
            foreground=[('selected', '#ffffff')]
        )
        
        style.configure(
            'TLabelframe',
            background=colors['frame_bg'],
            foreground=colors['fg'],
            borderwidth=1
        )
        
        style.configure(
            'TLabelframe.Label',
            background=colors['frame_bg'],
            foreground=colors['fg']
        )
        
        style.configure(
            'TCombobox',
            fieldbackground=colors['entry_bg'],
            background=colors['entry_bg'],
            foreground=colors['entry_fg'],
            borderwidth=1
        )
        style.map(
            'TCombobox',
            fieldbackground=[('readonly', colors['entry_bg'])],
            background=[('readonly', colors['entry_bg']), ('active', colors['button_bg'])],
            foreground=[('readonly', colors['entry_fg']), ('active', colors['entry_fg'])]
        )
        
        style.configure(
            'Scale',
            background=colors['frame_bg'],
            foreground=colors['fg'],
            troughcolor=colors['button_bg'],
            darkcolor=colors['button_bg'],
            lightcolor=colors['button_bg']
        )
        
        return style


def apply_dark_mode_to_widget(widget, theme_obj, recursive=True):
    """
    Apply dark mode colors to a widget and optionally its children.
    
    Args:
        widget: The Tkinter widget to style
        theme_obj: DarkMode instance
        recursive: Whether to apply to child widgets
    """
    colors = theme_obj.get_colors()
    
    try:
        widget_class = widget.__class__.__name__
        
        # Configure based on widget type
        if widget_class == 'LabelFrame':
            widget.config(bg=colors['frame_bg'], fg=colors['fg'], borderwidth=1)
        elif widget_class == 'Frame':
            widget.config(bg=colors['frame_bg'])
        elif widget_class == 'Label':
            # Always ensure labels match current theme
            current_bg = widget.cget('bg')
            # Check if it's a system/default color or a light color
            is_light_bg = current_bg in ('SystemButtonFace', '#f0f0f0', '#f5f5f5', '#ffffff', 'white', '#e0e0e0', '#d0d0d0')
            is_dark_bg = current_bg in ('#1e1e1e', '#252525', '#2d2d2d', '#1a1a1a')
            
            # Update if it's a light background or dark background (to ensure proper theming)
            if is_light_bg or is_dark_bg:
                widget.config(bg=colors['frame_bg'], fg=colors['fg'])
            else:
                # For other backgrounds, just update foreground
                widget.config(fg=colors['fg'])
        elif widget_class == 'Button':
            # Skip orange buttons (like CLEAR CACHE NOW button)
            current_bg = widget.cget('bg')
            if current_bg in ('orange', '#FFA500'):
                # Keep orange buttons orange regardless of theme
                widget.config(fg='white')
            else:
                widget.config(bg=colors['button_bg'], fg=colors['fg'], activebackground=colors['accent'])
        elif widget_class == 'Entry':
            # Always update Entry widgets to match theme, regardless of their current color
            current_bg = widget.cget('bg')
            # Check if it's a light color that needs updating
            is_light_bg = current_bg in ('#f0f0f0', '#ffffff', 'white', '#eeeeee', '#dddddd', 'SystemWindow')
            
            if is_light_bg or widget_class == 'Entry':
                widget.config(bg=colors['entry_bg'], fg=colors['entry_fg'], insertbackground=colors['fg'], 
                             selectbackground=colors['accent'], selectforeground='white')
        elif widget_class in ('Text', 'ScrolledText'):
            widget.config(bg=colors['text_bg'], fg=colors['text_fg'], insertbackground=colors['fg'],
                         selectbackground=colors['accent'], selectforeground='white')
            # Also style the scrollbar if it exists
            try:
                if hasattr(widget, 'vbar'):
                    widget.vbar.config(bg=colors['frame_bg'])
                if hasattr(widget, 'hbar'):
                    widget.hbar.config(bg=colors['frame_bg'])
            except (tk.TclError, AttributeError):
                pass
        elif widget_class in ('Checkbutton', 'Radiobutton'):
            widget.config(bg=colors['frame_bg'], fg=colors['fg'], activebackground=colors['accent'],
                         selectcolor=colors['button_bg'])
        elif widget_class == 'Canvas':
            widget.config(bg=colors['frame_bg'])
        elif widget_class == 'Listbox':
            widget.config(bg=colors['text_bg'], fg=colors['text_fg'], selectbackground=colors['accent'],
                         selectforeground='white')
        elif widget_class == 'Combobox':
            widget.config(fieldbackground=colors['entry_bg'], foreground=colors['entry_fg'])
            # Note: Other Combobox styling is handled via ttk.Style
        elif widget_class == 'Scale':
            widget.config(bg=colors['frame_bg'], fg=colors['fg'], troughcolor=colors['button_bg'],
                         activebackground=colors['accent'], highlightbackground=colors['frame_bg'],
                         highlightcolor=colors['frame_bg'])
    except (tk.TclError, AttributeError):
        pass
    
    # Recursively apply to children
    if recursive:
        try:
            for child in widget.winfo_children():
                apply_dark_mode_to_widget(child, theme_obj, recursive=True)
        except (tk.TclError, AttributeError):
            pass


# Import at end to avoid circular imports
import tkinter as tk
