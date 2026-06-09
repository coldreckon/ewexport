"""
Theme handling for the CustomTkinter GUI.

Centralizes appearance-mode setup and the ttk styling needed for the
widgets that have no CustomTkinter equivalent (Treeview, PanedWindow,
Scrollbar). Call apply_ttk_styles() again after every appearance-mode
change so the ttk widgets follow the CTk theme.
"""

import logging
from tkinter import ttk

import customtkinter as ctk

logger = logging.getLogger(__name__)

APPEARANCE_MODES = ('light', 'dark', 'system')


def init_appearance(config) -> None:
    """Apply the saved appearance mode and accent color theme"""
    mode = (config.get('app.theme', 'system') or 'system').lower()
    if mode not in APPEARANCE_MODES:
        mode = 'system'  # tolerate legacy values like "default"
    ctk.set_appearance_mode(mode)
    ctk.set_default_color_theme('blue')


def set_appearance(config, mode: str) -> None:
    """Switch appearance mode at runtime and persist the choice"""
    ctk.set_appearance_mode(mode)
    apply_ttk_styles()
    config.set('app.theme', mode)


def _pick(value):
    """CTk theme colors are [light, dark] pairs or plain strings"""
    if isinstance(value, (list, tuple)):
        return value[1] if ctk.get_appearance_mode() == 'Dark' else value[0]
    return value


def get_colors() -> dict:
    """Resolve commonly used colors for the active appearance mode"""
    theme = ctk.ThemeManager.theme
    return {
        'bg': _pick(theme['CTkFrame']['fg_color']),
        'card': _pick(theme['CTkFrame']['top_fg_color']),
        'field': _pick(theme['CTkEntry']['fg_color']),
        'text': _pick(theme['CTkLabel']['text_color']),
        'accent': _pick(theme['CTkButton']['fg_color']),
        'accent_text': _pick(theme['CTkButton']['text_color']),
        'border': _pick(theme['CTkEntry']['border_color']),
    }


def apply_ttk_styles() -> None:
    """Style ttk.Treeview/Scrollbar/PanedWindow to match the CTk theme"""
    colors = get_colors()
    style = ttk.Style()
    # 'clam' is the only built-in ttk theme whose Treeview colors are
    # fully configurable (the Windows-native themes ignore most options)
    style.theme_use('clam')

    style.configure('Treeview',
                    background=colors['field'],
                    fieldbackground=colors['field'],
                    foreground=colors['text'],
                    bordercolor=colors['border'],
                    borderwidth=0,
                    rowheight=26)
    style.configure('Treeview.Heading',
                    background=colors['bg'],
                    foreground=colors['text'],
                    bordercolor=colors['border'],
                    relief='flat',
                    padding=4)
    style.map('Treeview',
              background=[('selected', colors['accent'])],
              foreground=[('selected', colors['accent_text'])])
    style.map('Treeview.Heading',
              background=[('active', colors['card'])])

    style.configure('TPanedwindow', background=colors['bg'])
    style.configure('Vertical.TScrollbar',
                    background=colors['card'],
                    troughcolor=colors['bg'],
                    bordercolor=colors['bg'],
                    arrowcolor=colors['text'])
    style.configure('Horizontal.TScrollbar',
                    background=colors['card'],
                    troughcolor=colors['bg'],
                    bordercolor=colors['bg'],
                    arrowcolor=colors['text'])
