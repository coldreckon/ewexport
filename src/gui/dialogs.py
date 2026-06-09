"""
Dialog windows for user interactions (CustomTkinter)
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from typing import Optional

import customtkinter as ctk

SECTION_FONT = ('', 13, 'bold')


def make_modal(dialog: ctk.CTkToplevel, parent) -> None:
    """Make a CTkToplevel modal over its parent.

    CTkToplevel re-applies window attributes ~200 ms after creation via
    internal after() callbacks; grabbing immediately can leave the dialog
    behind the parent, so the grab is delayed.
    """
    dialog.transient(parent)
    dialog.lift()
    dialog.focus_set()

    def grab():
        try:
            dialog.grab_set()
        except tk.TclError:
            pass  # Dialog already closed

    dialog.after(250, grab)


def center_on_parent(dialog, parent, width: int, height: int) -> None:
    """Size the dialog and center it over the parent window"""
    parent.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width() // 2) - width // 2
    y = parent.winfo_y() + (parent.winfo_height() // 2) - height // 2
    dialog.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")


def section_frame(parent, title: str) -> ctk.CTkFrame:
    """A titled card frame (CustomTkinter has no LabelFrame equivalent)"""
    frame = ctk.CTkFrame(parent)
    ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=13, weight='bold'),
                 anchor='w').pack(anchor=tk.W, padx=10, pady=(8, 2))
    return frame


class DuplicateFileDialog:
    """Dialog for handling duplicate files during export"""

    ACTIONS = {
        'skip': 'Skip this file',
        'overwrite': 'Overwrite existing file',
        'rename': 'Rename with number suffix',
        'rename_custom': 'Choose custom name'
    }

    def __init__(self, parent, file_path: Path, remaining_count: int = 0):
        """
        Initialize duplicate file dialog

        Args:
            parent: Parent window
            file_path: Path to the duplicate file
            remaining_count: Number of remaining duplicates
        """
        self.result = None
        self.apply_to_all = False

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title("Duplicate File Found")
        center_on_parent(self.dialog, parent, 520, 400)
        self.dialog.resizable(False, False)
        make_modal(self.dialog, parent)

        self._build_ui(file_path, remaining_count)

    def _build_ui(self, file_path: Path, remaining_count: int):
        """Build the dialog UI"""
        main_frame = ctk.CTkFrame(self.dialog, fg_color='transparent')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        # Message
        msg = f"The file already exists:\n\n{file_path.name}\n\nWhat would you like to do?"
        ctk.CTkLabel(main_frame, text=msg, wraplength=460,
                     justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 12))

        # Action selection
        self.action_var = tk.StringVar(value='skip')

        actions_frame = section_frame(main_frame, "Choose Action")
        actions_frame.pack(fill=tk.X, pady=(0, 10))

        for action, label in self.ACTIONS.items():
            ctk.CTkRadioButton(actions_frame, text=label, variable=self.action_var,
                               value=action).pack(anchor=tk.W, padx=12, pady=3)
        ctk.CTkFrame(actions_frame, fg_color='transparent', height=6).pack()

        # Apply to all checkbox (if there are more duplicates)
        if remaining_count > 0:
            self.apply_all_var = tk.BooleanVar(value=False)
            msg = f"Apply this action to all {remaining_count + 1} duplicate files"
            ctk.CTkCheckBox(main_frame, text=msg,
                            variable=self.apply_all_var).pack(anchor=tk.W, pady=8)

        # Buttons
        button_frame = ctk.CTkFrame(main_frame, fg_color='transparent')
        button_frame.pack(side=tk.BOTTOM, pady=(10, 0))

        ctk.CTkButton(button_frame, text="OK", command=self._ok_clicked,
                      width=100).pack(side=tk.LEFT, padx=5)
        ctk.CTkButton(button_frame, text="Cancel", command=self._cancel_clicked,
                      width=100, fg_color='transparent',
                      border_width=1).pack(side=tk.LEFT, padx=5)

        # Bind Enter and Escape
        self.dialog.bind('<Return>', lambda e: self._ok_clicked())
        self.dialog.bind('<Escape>', lambda e: self._cancel_clicked())

    def _ok_clicked(self):
        """Handle OK button click"""
        action = self.action_var.get()

        if action == 'rename_custom':
            # Show custom name dialog
            custom_name = self._get_custom_name()
            if custom_name:
                self.result = ('rename_custom', custom_name)
            else:
                return  # User cancelled custom name
        else:
            self.result = (action, None)

        # Check if apply to all
        if hasattr(self, 'apply_all_var'):
            self.apply_to_all = self.apply_all_var.get()

        self.dialog.destroy()

    def _cancel_clicked(self):
        """Handle Cancel button click"""
        self.result = ('cancel', None)
        self.dialog.destroy()

    def _get_custom_name(self) -> Optional[str]:
        """Get custom filename from user"""
        dialog = ctk.CTkToplevel(self.dialog)
        dialog.title("Enter Custom Name")
        center_on_parent(dialog, self.dialog, 420, 170)
        dialog.resizable(False, False)
        make_modal(dialog, self.dialog)

        frame = ctk.CTkFrame(dialog, fg_color='transparent')
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        ctk.CTkLabel(frame, text="Enter new filename (without extension):").pack(anchor=tk.W)

        name_var = tk.StringVar()
        entry = ctk.CTkEntry(frame, textvariable=name_var, width=360)
        entry.pack(fill=tk.X, pady=(5, 12))
        entry.focus_set()

        result = {'name': None}

        def ok_clicked():
            name = name_var.get().strip()
            if name:
                # Sanitize filename
                invalid_chars = r'<>:"/\|?*'
                for char in invalid_chars:
                    name = name.replace(char, '_')
                result['name'] = name
                dialog.destroy()

        def cancel_clicked():
            dialog.destroy()

        # Buttons
        button_frame = ctk.CTkFrame(frame, fg_color='transparent')
        button_frame.pack()

        ctk.CTkButton(button_frame, text="OK", command=ok_clicked,
                      width=100).pack(side=tk.LEFT, padx=5)
        ctk.CTkButton(button_frame, text="Cancel", command=cancel_clicked,
                      width=100, fg_color='transparent',
                      border_width=1).pack(side=tk.LEFT, padx=5)

        # Bindings
        entry.bind('<Return>', lambda e: ok_clicked())
        dialog.bind('<Escape>', lambda e: cancel_clicked())

        # Wait for dialog
        dialog.wait_window()

        return result['name']


class ExportOptionsDialog:
    """Dialog for configuring export options"""

    def __init__(self, parent, config_manager):
        """
        Initialize export options dialog

        Args:
            parent: Parent window
            config_manager: Configuration manager instance
        """
        self.config = config_manager
        self.result = None

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title("Export Options")
        center_on_parent(self.dialog, parent, 680, 720)
        make_modal(self.dialog, parent)

        # Build UI
        self._build_ui()

        # Load current settings
        self._load_settings()

    def _build_ui(self):
        """Build the dialog UI"""
        # Create tab view
        self.tabview = ctk.CTkTabview(self.dialog)
        self.tabview.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 5))

        general_tab = self.tabview.add("General")
        format_tab = self.tabview.add("Formatting")
        slides_tab = self.tabview.add("Slides")

        self._build_general_tab(general_tab)
        self._build_format_tab(format_tab)
        self._build_slides_tab(slides_tab)

        # Bottom buttons
        button_frame = ctk.CTkFrame(self.dialog, fg_color='transparent')
        button_frame.pack(side=tk.BOTTOM, pady=10)

        ctk.CTkButton(button_frame, text="Save", command=self._save_clicked,
                      width=100).pack(side=tk.LEFT, padx=5)
        ctk.CTkButton(button_frame, text="Apply", command=self._apply_clicked,
                      width=100).pack(side=tk.LEFT, padx=5)
        ctk.CTkButton(button_frame, text="Cancel", command=self._cancel_clicked,
                      width=100, fg_color='transparent',
                      border_width=1).pack(side=tk.LEFT, padx=5)

        # Handle window close button
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _build_general_tab(self, parent):
        """Build the general options tab"""
        # Output directory
        dir_frame = section_frame(parent, "Output Directory")
        dir_frame.pack(fill=tk.X, pady=(0, 10))

        dir_row = ctk.CTkFrame(dir_frame, fg_color='transparent')
        dir_row.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.output_dir_var = tk.StringVar()
        ctk.CTkEntry(dir_row, textvariable=self.output_dir_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True)
        ctk.CTkButton(dir_row, text="Browse...", width=90,
                      command=self._browse_output_dir).pack(side=tk.LEFT, padx=(5, 0))

        # File naming
        naming_frame = section_frame(parent, "File Naming")
        naming_frame.pack(fill=tk.X, pady=(0, 10))

        self.include_ccli_var = tk.BooleanVar()
        ctk.CTkCheckBox(naming_frame, text="Include CCLI number in filename",
                        variable=self.include_ccli_var).pack(anchor=tk.W, padx=12, pady=3)

        self.include_author_var = tk.BooleanVar()
        ctk.CTkCheckBox(naming_frame, text="Include author in filename",
                        variable=self.include_author_var).pack(anchor=tk.W, padx=12, pady=(3, 12))

        # Duplicate handling
        dup_frame = section_frame(parent, "Duplicate Files")
        dup_frame.pack(fill=tk.X)

        ctk.CTkLabel(dup_frame, text="When a file already exists:").pack(
            anchor=tk.W, padx=12, pady=(0, 5))

        self.duplicate_action_var = tk.StringVar()
        duplicate_options = [
            ("Ask each time", "ask"),
            ("Skip all duplicates", "skip"),
            ("Overwrite all", "overwrite"),
            ("Rename all (add number suffix)", "rename")
        ]

        for text, value in duplicate_options:
            ctk.CTkRadioButton(dup_frame, text=text, variable=self.duplicate_action_var,
                               value=value).pack(anchor=tk.W, padx=12, pady=2)
        ctk.CTkFrame(dup_frame, fg_color='transparent', height=8).pack()

    def _build_format_tab(self, parent):
        """Build the formatting options tab"""
        # Master formatting control
        master_frame = section_frame(parent, "Formatting Control")
        master_frame.pack(fill=tk.X, pady=(0, 10))

        self.formatting_enabled_var = tk.BooleanVar()
        ctk.CTkCheckBox(master_frame, text="Enable custom formatting",
                        variable=self.formatting_enabled_var,
                        command=self._toggle_formatting_options).pack(anchor=tk.W, padx=12, pady=3)
        ctk.CTkLabel(master_frame, text="When disabled, uses default ProPresenter formatting",
                     font=ctk.CTkFont(size=11),
                     text_color='gray').pack(anchor=tk.W, padx=36, pady=(0, 10))

        # Font settings
        font_frame = section_frame(parent, "Font Settings")
        font_frame.pack(fill=tk.X, pady=(0, 10))

        font_grid = ctk.CTkFrame(font_frame, fg_color='transparent')
        font_grid.pack(fill=tk.X, padx=12, pady=(0, 4))

        # Font family - ttk.Combobox kept on purpose: its dropdown scrolls,
        # which a CTk option menu cannot do with hundreds of system fonts
        ctk.CTkLabel(font_grid, text="Font:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.font_family_var = tk.StringVar()
        available_fonts = self._get_available_fonts()
        self.font_combo = ttk.Combobox(font_grid, textvariable=self.font_family_var,
                                       values=available_fonts, width=30)
        self.font_combo.grid(row=0, column=1, sticky=tk.W, padx=(8, 0), pady=2)

        # Font size with dropdown and custom entry
        ctk.CTkLabel(font_grid, text="Size:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.font_size_var = tk.StringVar()
        common_sizes = ['12', '18', '24', '30', '36', '48', '60', '72', '84', '96', '120', '144', '168', '200']
        self.size_combo = ttk.Combobox(font_grid, textvariable=self.font_size_var,
                                       values=common_sizes, width=8, state='normal')
        self.size_combo.grid(row=1, column=1, sticky=tk.W, padx=(8, 0), pady=2)

        # Validation for custom entries (12-200 range)
        def validate_font_size(event=None):
            try:
                size = int(self.font_size_var.get())
                if size < 12:
                    self.font_size_var.set('12')
                elif size > 200:
                    self.font_size_var.set('200')
            except ValueError:
                self.font_size_var.set('72')

        self.size_combo.bind('<FocusOut>', validate_font_size)
        self.size_combo.bind('<Return>', validate_font_size)

        # Change font checkbox
        self.change_font_var = tk.BooleanVar()
        self.change_font_check = ctk.CTkCheckBox(
            font_frame, text="Override song font with selected font",
            variable=self.change_font_var)
        self.change_font_check.pack(anchor=tk.W, padx=12, pady=(5, 12))

        # Text processing options
        text_opts_frame = section_frame(parent, "Text Processing")
        text_opts_frame.pack(fill=tk.X)

        self.auto_break_lines_var = tk.BooleanVar()
        self.auto_break_check = ctk.CTkCheckBox(
            text_opts_frame, text="Automatically break long lines",
            variable=self.auto_break_lines_var)
        self.auto_break_check.pack(anchor=tk.W, padx=12, pady=3)

        ctk.CTkLabel(text_opts_frame, text="Maximum lines per slide:").pack(
            anchor=tk.W, padx=12, pady=(5, 2))
        self.max_lines_var = tk.IntVar()
        self.max_lines_spin = ttk.Spinbox(text_opts_frame, from_=1, to=10,
                                          textvariable=self.max_lines_var, width=10)
        self.max_lines_spin.pack(anchor=tk.W, padx=12, pady=(0, 12))

        # Widgets toggled by the master formatting checkbox
        self._formatting_widgets = [
            self.font_combo, self.size_combo, self.change_font_check,
            self.auto_break_check, self.max_lines_spin,
        ]

    def _build_slides_tab(self, parent):
        """Build the slides options tab"""
        # Intro slide
        intro_frame = section_frame(parent, "First Slide")
        intro_frame.pack(fill=tk.X, pady=(0, 10))

        self.add_intro_var = tk.BooleanVar()
        ctk.CTkCheckBox(intro_frame, text="Add intro slide as first slide",
                        variable=self.add_intro_var,
                        command=self._toggle_intro_options).pack(anchor=tk.W, padx=12, pady=3)

        ctk.CTkLabel(intro_frame, text="Intro slide text:").pack(anchor=tk.W, padx=12, pady=(5, 2))
        self.intro_text_var = tk.StringVar()
        self.intro_text_entry = ctk.CTkEntry(intro_frame, textvariable=self.intro_text_var,
                                             width=360, state='disabled')
        self.intro_text_entry.pack(anchor=tk.W, padx=12)

        ctk.CTkLabel(intro_frame, text="Group name:").pack(anchor=tk.W, padx=12, pady=(5, 2))
        self.intro_group_var = tk.StringVar()
        self.intro_group_entry = ctk.CTkEntry(intro_frame, textvariable=self.intro_group_var,
                                              width=180, state='disabled')
        self.intro_group_entry.pack(anchor=tk.W, padx=12, pady=(0, 12))

        # Blank slide
        blank_frame = section_frame(parent, "Last Slide")
        blank_frame.pack(fill=tk.X, pady=(0, 10))

        self.add_blank_var = tk.BooleanVar()
        ctk.CTkCheckBox(blank_frame, text="Add blank slide as last slide",
                        variable=self.add_blank_var,
                        command=self._toggle_blank_options).pack(anchor=tk.W, padx=12, pady=3)

        ctk.CTkLabel(blank_frame, text="Group name:").pack(anchor=tk.W, padx=12, pady=(5, 2))
        self.blank_group_var = tk.StringVar()
        self.blank_group_entry = ctk.CTkEntry(blank_frame, textvariable=self.blank_group_var,
                                              width=180, state='disabled')
        self.blank_group_entry.pack(anchor=tk.W, padx=12, pady=(0, 12))

    def _get_available_fonts(self):
        """Get list of available fonts on Windows"""
        try:
            import tkinter.font as tkfont
            # Get all font families available in the system
            fonts = list(tkfont.families())
            # Filter out fonts that start with @ (vertical fonts in Windows)
            fonts = [f for f in fonts if not f.startswith('@')]
            fonts.sort()
            return fonts
        except Exception:
            # Fallback to common fonts if can't get system fonts
            return ['Arial', 'Helvetica', 'Times New Roman', 'Calibri',
                    'Verdana', 'Tahoma', 'Georgia', 'Impact', 'Comic Sans MS']

    def _toggle_formatting_options(self):
        """Enable/disable formatting options based on master control"""
        state = 'normal' if self.formatting_enabled_var.get() else 'disabled'
        for widget in self._formatting_widgets:
            widget.configure(state=state)

    def _toggle_intro_options(self):
        """Enable/disable intro slide options"""
        state = 'normal' if self.add_intro_var.get() else 'disabled'
        self.intro_text_entry.configure(state=state)
        self.intro_group_entry.configure(state=state)

    def _toggle_blank_options(self):
        """Enable/disable blank slide options"""
        state = 'normal' if self.add_blank_var.get() else 'disabled'
        self.blank_group_entry.configure(state=state)

    def _browse_output_dir(self):
        """Browse for output directory"""
        current = self.output_dir_var.get() or str(Path.home())

        directory = filedialog.askdirectory(
            title="Select Output Directory",
            initialdir=current,
            parent=self.dialog
        )

        if directory:
            self.output_dir_var.set(directory)

    def _load_settings(self):
        """Load current settings from config"""
        # General
        output_dir = self.config.get('export.output_directory')
        if output_dir:
            self.output_dir_var.set(output_dir)

        self.include_ccli_var.set(self.config.get('export.include_ccli_in_filename', False))
        self.include_author_var.set(self.config.get('export.include_author_in_filename', False))
        self.duplicate_action_var.set(self.config.get('export.duplicate_handling_action', 'ask'))

        # Formatting
        self.formatting_enabled_var.set(self.config.get('export.formatting_enabled', False))
        self.font_family_var.set(self.config.get('export.font.family', 'Arial'))
        self.font_size_var.set(str(self.config.get('export.font.size', 72)))
        self.change_font_var.set(self.config.get('export.change_font', False))
        self.auto_break_lines_var.set(self.config.get('export.slides.auto_break_long_lines', True))

        # Slides
        self.add_intro_var.set(self.config.get('export.slides.add_intro_slide', False))
        self.intro_text_var.set(self.config.get('export.slides.intro_slide_text', ''))
        self.intro_group_var.set(self.config.get('export.slides.intro_slide_group', 'Intro'))
        self.add_blank_var.set(self.config.get('export.slides.add_blank_slide', False))
        self.blank_group_var.set(self.config.get('export.slides.blank_slide_group', 'Blank'))
        self.max_lines_var.set(self.config.get('export.slides.max_lines_per_slide', 4))

        # Update UI states
        self._toggle_formatting_options()
        self._toggle_intro_options()
        self._toggle_blank_options()

    def _save_settings(self):
        """Save settings to config"""
        # General
        output_dir = self.output_dir_var.get()
        if output_dir:
            self.config.set('export.output_directory', output_dir, save=False)

        self.config.set('export.include_ccli_in_filename', self.include_ccli_var.get(), save=False)
        self.config.set('export.include_author_in_filename', self.include_author_var.get(), save=False)
        self.config.set('export.duplicate_handling_action', self.duplicate_action_var.get(), save=False)

        # Formatting
        self.config.set('export.formatting_enabled', self.formatting_enabled_var.get(), save=False)
        self.config.set('export.font.family', self.font_family_var.get(), save=False)
        # Convert font size string to int for config
        try:
            font_size = int(self.font_size_var.get())
        except ValueError:
            font_size = 72  # Default if invalid
        self.config.set('export.font.size', font_size, save=False)
        self.config.set('export.change_font', self.change_font_var.get(), save=False)
        self.config.set('export.slides.auto_break_long_lines', self.auto_break_lines_var.get(), save=False)

        # Slides
        self.config.set('export.slides.add_intro_slide', self.add_intro_var.get(), save=False)
        self.config.set('export.slides.intro_slide_text', self.intro_text_var.get(), save=False)
        self.config.set('export.slides.intro_slide_group', self.intro_group_var.get(), save=False)
        self.config.set('export.slides.add_blank_slide', self.add_blank_var.get(), save=False)
        self.config.set('export.slides.blank_slide_group', self.blank_group_var.get(), save=False)
        self.config.set('export.slides.max_lines_per_slide', self.max_lines_var.get(), save=False)

        # Save all settings
        self.config.save_settings()

    def _save_clicked(self):
        """Handle Save button click - save and close"""
        self._save_settings()
        self.result = 'saved'
        messagebox.showinfo("Settings Saved", "Export settings have been saved successfully.",
                            parent=self.dialog)
        self.dialog.destroy()

    def _apply_clicked(self):
        """Handle Apply button click - save without closing"""
        self._save_settings()
        messagebox.showinfo("Settings Applied", "Export settings have been applied.",
                            parent=self.dialog)

    def _cancel_clicked(self):
        """Handle Cancel button click - close without saving"""
        response = messagebox.askyesno("Confirm Cancel",
                                       "Are you sure you want to cancel?\nAny unsaved changes will be lost.",
                                       parent=self.dialog)
        if response:
            self.result = 'cancelled'
            self.dialog.destroy()

    def _on_closing(self):
        """Handle window close button"""
        response = messagebox.askyesnocancel("Save Changes",
                                             "Do you want to save your changes before closing?",
                                             parent=self.dialog)
        if response is True:  # Yes - save and close
            self._save_settings()
            self.result = 'saved'
            self.dialog.destroy()
        elif response is False:  # No - close without saving
            self.result = 'cancelled'
            self.dialog.destroy()
        # If None (Cancel), do nothing - keep dialog open
