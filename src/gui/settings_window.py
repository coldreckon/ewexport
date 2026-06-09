"""
Settings window for configuring section mappings
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import logging
import re
from pathlib import Path

import customtkinter as ctk

from src.utils import section_mappings
from src.gui.dialogs import make_modal, center_on_parent

logger = logging.getLogger(__name__)

class SettingsWindow:

    def __init__(self, parent_window=None):
        self.parent = parent_window
        self.window = ctk.CTkToplevel() if parent_window else ctk.CTk()
        self.window.title("Section Mapping Settings")
        self.window.geometry("820x640")

        # Make window modal if has parent
        if parent_window:
            make_modal(self.window, parent_window.root)

        # Load current mappings (file lives in the app data directory)
        self.mappings = {}
        self.original_mappings = {}
        self.load_mappings()
        
        # Track changes
        self.has_changes = False
        
        # Setup UI
        self.setup_ui()
        
        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def setup_ui(self):
        """Build the settings UI"""
        main_frame = ctk.CTkFrame(self.window, fg_color='transparent')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title and description
        title_frame = ctk.CTkFrame(main_frame, fg_color='transparent')
        title_frame.pack(fill=tk.X, pady=(0, 5))

        ctk.CTkLabel(title_frame, text="Section Name Mappings",
                     font=ctk.CTkFont(size=15, weight='bold')).pack(anchor=tk.W)
        ctk.CTkLabel(title_frame,
                     text="Configure how section names are translated from Swedish to English for ProPresenter export",
                     wraplength=760).pack(anchor=tk.W, pady=(2, 0))

        # Main content area with tabs
        self.tabview = ctk.CTkTabview(main_frame)
        self.tabview.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        mappings_frame = self.tabview.add("Section Mappings")
        self.setup_mappings_tab(mappings_frame)

        preview_frame = self.tabview.add("Preview & Test")
        self.setup_preview_tab(preview_frame)

        # Bottom button bar
        button_frame = ctk.CTkFrame(main_frame, fg_color='transparent')
        button_frame.pack(fill=tk.X)

        # Left side buttons
        left_buttons = ctk.CTkFrame(button_frame, fg_color='transparent')
        left_buttons.pack(side=tk.LEFT)

        ctk.CTkButton(left_buttons, text="Import...", width=90,
                      command=self.import_mappings).pack(side=tk.LEFT, padx=(0, 5))
        ctk.CTkButton(left_buttons, text="Export...", width=90,
                      command=self.export_mappings).pack(side=tk.LEFT, padx=(0, 5))
        ctk.CTkButton(left_buttons, text="Reset to Defaults", width=130,
                      fg_color='transparent', border_width=1,
                      command=self.reset_to_defaults).pack(side=tk.LEFT)

        # Right side buttons
        right_buttons = ctk.CTkFrame(button_frame, fg_color='transparent')
        right_buttons.pack(side=tk.RIGHT)

        ctk.CTkButton(right_buttons, text="Apply", width=90,
                      command=self.apply_changes).pack(side=tk.LEFT, padx=(0, 5))
        ctk.CTkButton(right_buttons, text="Save", width=90,
                      command=self.save_changes).pack(side=tk.LEFT, padx=(0, 5))
        ctk.CTkButton(right_buttons, text="Cancel", width=90,
                      fg_color='transparent', border_width=1,
                      command=self.on_close).pack(side=tk.LEFT)
    
    def setup_mappings_tab(self, parent):
        """Setup the mappings configuration tab"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Toolbar
        toolbar = ctk.CTkFrame(parent, fg_color='transparent')
        toolbar.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)

        ctk.CTkButton(toolbar, text="Add Mapping", width=110,
                      command=self.add_mapping).pack(side=tk.LEFT, padx=(0, 5))
        ctk.CTkButton(toolbar, text="Edit Selected", width=110,
                      command=self.edit_mapping).pack(side=tk.LEFT, padx=(0, 5))
        ctk.CTkButton(toolbar, text="Delete Selected", width=110,
                      fg_color='transparent', border_width=1,
                      command=self.delete_mapping).pack(side=tk.LEFT)

        # Treeview kept for the mappings table (no CTk equivalent;
        # styled to match the theme via theme.apply_ttk_styles)
        columns = ('swedish', 'english')
        self.mappings_tree = ttk.Treeview(parent, columns=columns, show='headings',
                                         selectmode='browse', height=15)
        self.mappings_tree.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S),
                               padx=5, pady=(0, 5))

        # Configure columns
        self.mappings_tree.heading('swedish', text='Swedish/Source')
        self.mappings_tree.column('swedish', width=300)

        self.mappings_tree.heading('english', text='English/Target')
        self.mappings_tree.column('english', width=300)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(parent, orient="vertical",
                                 command=self.mappings_tree.yview)
        scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S), pady=(0, 5))
        self.mappings_tree.configure(yscrollcommand=scrollbar.set)

        # Double-click to edit
        self.mappings_tree.bind('<Double-Button-1>', lambda e: self.edit_mapping())

        # Load mappings into tree
        self.refresh_mappings_tree()

        # Info label
        info_label = ctk.CTkLabel(parent,
                             text="Note: Mappings are case-insensitive. Numbers in section names are preserved automatically.",
                             font=ctk.CTkFont(size=11))
        info_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
    
    def setup_preview_tab(self, parent):
        """Setup the preview and testing tab"""
        from src.gui.dialogs import section_frame

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Test input frame
        input_frame = section_frame(parent, "Test Input")
        input_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)

        input_row = ctk.CTkFrame(input_frame, fg_color='transparent')
        input_row.pack(fill=tk.X, padx=10, pady=(0, 10))

        ctk.CTkLabel(input_row, text="Swedish Text:").pack(side=tk.LEFT, padx=(0, 5))

        self.test_input = tk.StringVar(value="vers 1")
        test_entry = ctk.CTkEntry(input_row, textvariable=self.test_input)
        test_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        test_entry.bind('<KeyRelease>', self.update_preview)

        ctk.CTkButton(input_row, text="Test", width=80,
                      command=self.update_preview).pack(side=tk.LEFT, padx=(5, 0))

        # Results frame
        results_frame = section_frame(parent, "Preview Results")
        results_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        # Preview text widget
        self.preview_text = ctk.CTkTextbox(results_frame, wrap=tk.WORD)
        self.preview_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Common examples frame
        examples_frame = section_frame(parent, "Common Examples")
        examples_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)

        examples = [
            ("vers 1", "Verse 1"),
            ("refräng", "Chorus"),
            ("brygga 2", "Bridge 2"),
            ("förrefräng", "Pre-Chorus"),
            ("slut", "Outro")
        ]

        examples_text = "Examples of mappings:\n"
        for swedish, english in examples:
            examples_text += f"  • {swedish} → {english}\n"

        ctk.CTkLabel(examples_frame, text=examples_text,
                     justify=tk.LEFT).pack(anchor=tk.W, padx=10, pady=(0, 8))

        # Initial preview
        self.update_preview()
    
    def refresh_mappings_tree(self):
        """Refresh the mappings tree view"""
        # Clear existing items
        for item in self.mappings_tree.get_children():
            self.mappings_tree.delete(item)
        
        # Add mappings
        for swedish, english in sorted(self.mappings.items()):
            self.mappings_tree.insert('', 'end', values=(swedish, english))
    
    def add_mapping(self):
        """Add a new mapping"""
        dialog = MappingDialog(self.window, title="Add Mapping")
        self.window.wait_window(dialog.dialog)
        
        if dialog.result:
            swedish, english = dialog.result
            
            # Validate
            if swedish.lower() in (k.lower() for k in self.mappings.keys()):
                messagebox.showwarning("Duplicate Entry", 
                                     f"A mapping for '{swedish}' already exists.")
                return
            
            # Add mapping
            self.mappings[swedish.lower()] = english
            self.refresh_mappings_tree()
            self.has_changes = True
            self.update_preview()
    
    def edit_mapping(self):
        """Edit selected mapping"""
        selection = self.mappings_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a mapping to edit.")
            return
        
        item = self.mappings_tree.item(selection[0])
        old_swedish, old_english = item['values']
        
        dialog = MappingDialog(self.window, title="Edit Mapping", 
                             initial_swedish=old_swedish, 
                             initial_english=old_english)
        self.window.wait_window(dialog.dialog)
        
        if dialog.result:
            new_swedish, new_english = dialog.result
            
            # Remove old mapping if key changed
            if old_swedish.lower() != new_swedish.lower():
                del self.mappings[old_swedish.lower()]
                
                # Check for duplicate
                if new_swedish.lower() in (k.lower() for k in self.mappings.keys()):
                    messagebox.showwarning("Duplicate Entry", 
                                         f"A mapping for '{new_swedish}' already exists.")
                    # Restore old mapping
                    self.mappings[old_swedish.lower()] = old_english
                    return
            
            # Update mapping
            self.mappings[new_swedish.lower()] = new_english
            self.refresh_mappings_tree()
            self.has_changes = True
            self.update_preview()
    
    def delete_mapping(self):
        """Delete selected mapping"""
        selection = self.mappings_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a mapping to delete.")
            return
        
        item = self.mappings_tree.item(selection[0])
        swedish, english = item['values']
        
        if messagebox.askyesno("Confirm Delete", 
                              f"Delete mapping '{swedish}' → '{english}'?"):
            del self.mappings[swedish.lower()]
            self.refresh_mappings_tree()
            self.has_changes = True
            self.update_preview()
    
    def update_preview(self, event=None):
        """Update the preview based on test input"""
        test_text = self.test_input.get()
        
        # Clear preview
        self.preview_text.delete('1.0', tk.END)
        
        if not test_text:
            self.preview_text.insert('1.0', "Enter Swedish text to see the English translation")
            return
        
        # Apply mapping
        result = self.apply_section_mapping(test_text)
        
        # Show results
        preview = f"Input: {test_text}\n"
        preview += f"Output: {result}\n\n"
        preview += "Mapping Process:\n"

        # Extract base name and number
        match = re.match(r'^(.*?)(\s+\d+)?$', test_text.lower().strip())
        if match:
            base = match.group(1)
            number = match.group(2) or ""
            
            if base in self.mappings:
                preview += f"  • Found mapping: '{base}' → '{self.mappings[base]}'\n"
                if number:
                    preview += f"  • Preserved number: '{number.strip()}'\n"
            else:
                preview += f"  • No mapping found for '{base}', using original\n"
        
        self.preview_text.insert('1.0', preview)
    
    def apply_section_mapping(self, text: str) -> str:
        """Apply section mapping to text"""
        # Extract section name and optional number
        match = re.match(r'^(.*?)(\s+\d+)?$', text.strip())
        if not match:
            return text
        
        section_name = match.group(1).lower()
        number = match.group(2) or ""
        
        # Look up mapping
        if section_name in self.mappings:
            english_name = self.mappings[section_name]
            return f"{english_name}{number}"
        
        # Return original if no mapping found
        return text
    
    def import_mappings(self):
        """Import mappings from file"""
        file_path = filedialog.askopenfilename(
            title="Import Mappings",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=str(Path.home())
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'section_mappings' in data:
                mappings = data['section_mappings']
            else:
                mappings = data  # Assume direct mapping dict
            
            # Validate
            if not isinstance(mappings, dict):
                raise ValueError("Invalid mappings format")
            
            # Ask to merge or replace
            if self.mappings:
                choice = messagebox.askyesnocancel(
                    "Import Mappings",
                    "Do you want to merge with existing mappings?\n\n"
                    "Yes: Merge (existing mappings will be kept)\n"
                    "No: Replace all existing mappings\n"
                    "Cancel: Cancel import"
                )
                
                if choice is None:  # Cancel
                    return
                elif choice:  # Yes - merge
                    mappings.update(self.mappings)
            
            self.mappings = {k.lower(): v for k, v in mappings.items()}
            self.refresh_mappings_tree()
            self.has_changes = True
            self.update_preview()
            
            messagebox.showinfo("Import Complete", 
                              f"Successfully imported {len(mappings)} mappings.")
            
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import mappings:\n{str(e)}")
    
    def export_mappings(self):
        """Export mappings to file"""
        file_path = filedialog.asksaveasfilename(
            title="Export Mappings",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="section_mappings_export.json",
            initialdir=str(Path.home())
        )
        
        if not file_path:
            return
        
        try:
            # Create export data
            export_data = {
                "section_mappings": self.mappings,
                "number_mapping_rules": {
                    "preserve_numbers": True,
                    "format": "{section_name} {number}"
                },
                "exported_from": "EasyWorship to ProPresenter Converter",
                "description": "Custom section name mappings"
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            messagebox.showinfo("Export Complete", 
                              f"Successfully exported mappings to:\n{file_path}")
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export mappings:\n{str(e)}")
    
    def reset_to_defaults(self):
        """Reset mappings to defaults"""
        if not messagebox.askyesno("Reset to Defaults", 
                                  "This will replace all current mappings with the default set.\n\n"
                                  "Are you sure you want to continue?"):
            return
        
        self.mappings = dict(section_mappings.DEFAULT_SECTION_MAPPINGS)

        self.refresh_mappings_tree()
        self.has_changes = True
        self.update_preview()

        messagebox.showinfo("Reset Complete", "Mappings have been reset to defaults.")

    def load_mappings(self):
        """Load mappings via the shared section_mappings module"""
        try:
            self.mappings = section_mappings.load_mappings()
            self.original_mappings = self.mappings.copy()
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to load mappings:\n{str(e)}")
            self.mappings = dict(section_mappings.DEFAULT_SECTION_MAPPINGS)
            self.original_mappings = self.mappings.copy()

    def save_mappings(self):
        """Save mappings via the shared section_mappings module"""
        try:
            section_mappings.save_mappings(self.mappings)
            self.original_mappings = self.mappings.copy()
            self.has_changes = False
            return True
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save mappings:\n{str(e)}")
            return False
    
    def apply_changes(self):
        """Apply changes without closing window"""
        if self.save_mappings():
            messagebox.showinfo("Changes Applied", "Mappings have been saved successfully.")
            
            # Notify parent window if exists
            if self.parent and hasattr(self.parent, 'reload_section_mappings'):
                self.parent.reload_section_mappings()
    
    def save_changes(self):
        """Save changes and close window"""
        if self.save_mappings():
            # Notify parent window if exists
            if self.parent and hasattr(self.parent, 'reload_section_mappings'):
                self.parent.reload_section_mappings()
            
            self.window.destroy()
    
    def on_close(self):
        """Handle window close"""
        if self.has_changes:
            response = messagebox.askyesnocancel(
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save them before closing?"
            )
            
            if response is None:  # Cancel
                return
            elif response:  # Yes - save
                self.save_changes()
                return
        
        self.window.destroy()


class MappingDialog:
    """Dialog for adding/editing a mapping"""

    def __init__(self, parent, title="Add Mapping",
                 initial_swedish="", initial_english=""):
        self.result = None

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title(title)
        center_on_parent(self.dialog, parent, 420, 190)
        self.dialog.resizable(False, False)
        make_modal(self.dialog, parent)

        # Create form
        frame = ctk.CTkFrame(self.dialog, fg_color='transparent')
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)
        frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Swedish/Source:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.swedish_var = tk.StringVar(value=initial_swedish)
        self.swedish_entry = ctk.CTkEntry(frame, textvariable=self.swedish_var, width=240)
        self.swedish_entry.grid(row=0, column=1, pady=5, padx=(10, 0), sticky=tk.EW)

        ctk.CTkLabel(frame, text="English/Target:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.english_var = tk.StringVar(value=initial_english)
        self.english_entry = ctk.CTkEntry(frame, textvariable=self.english_var, width=240)
        self.english_entry.grid(row=1, column=1, pady=5, padx=(10, 0), sticky=tk.EW)

        # Buttons
        button_frame = ctk.CTkFrame(frame, fg_color='transparent')
        button_frame.grid(row=2, column=0, columnspan=2, pady=(15, 0))

        ctk.CTkButton(button_frame, text="OK", width=100,
                      command=self.ok_clicked).pack(side=tk.LEFT, padx=5)
        ctk.CTkButton(button_frame, text="Cancel", width=100,
                      fg_color='transparent', border_width=1,
                      command=self.cancel_clicked).pack(side=tk.LEFT)

        # Focus and bindings
        self.swedish_entry.focus()
        self.swedish_entry.bind('<Return>', lambda e: self.english_entry.focus())
        self.english_entry.bind('<Return>', lambda e: self.ok_clicked())
        self.dialog.bind('<Escape>', lambda e: self.cancel_clicked())
    
    def ok_clicked(self):
        """Handle OK button"""
        swedish = self.swedish_var.get().strip()
        english = self.english_var.get().strip()
        
        if not swedish or not english:
            messagebox.showwarning("Invalid Input", 
                                 "Both Swedish and English names are required.",
                                 parent=self.dialog)
            return
        
        self.result = (swedish, english)
        self.dialog.destroy()
    
    def cancel_clicked(self):
        """Handle Cancel button"""
        self.dialog.destroy()
