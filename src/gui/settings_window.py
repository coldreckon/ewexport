"""
Settings window for configuring section mappings
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import logging
import re
from pathlib import Path
from src.utils import section_mappings

logger = logging.getLogger(__name__)

class SettingsWindow:

    def __init__(self, parent_window=None):
        self.parent = parent_window
        self.window = tk.Toplevel() if parent_window else tk.Tk()
        self.window.title("Section Mapping Settings")
        self.window.geometry("800x600")

        # Make window modal if has parent
        if parent_window:
            self.window.transient(parent_window.root)
            self.window.grab_set()

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
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Title and description
        title_frame = ttk.Frame(main_frame)
        title_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(title_frame, text="Section Name Mappings", 
                 font=('TkDefaultFont', 12, 'bold')).pack(anchor=tk.W)
        ttk.Label(title_frame, 
                 text="Configure how section names are translated from Swedish to English for ProPresenter export",
                 wraplength=750).pack(anchor=tk.W, pady=(5, 0))
        
        # Main content area with tabs
        notebook = ttk.Notebook(main_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Mappings tab
        mappings_frame = ttk.Frame(notebook)
        notebook.add(mappings_frame, text="Section Mappings")
        self.setup_mappings_tab(mappings_frame)
        
        # Preview tab
        preview_frame = ttk.Frame(notebook)
        notebook.add(preview_frame, text="Preview & Test")
        self.setup_preview_tab(preview_frame)
        
        # Bottom button bar
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, sticky=(tk.W, tk.E))
        
        # Left side buttons
        left_buttons = ttk.Frame(button_frame)
        left_buttons.pack(side=tk.LEFT)
        
        ttk.Button(left_buttons, text="Import...", 
                  command=self.import_mappings).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(left_buttons, text="Export...", 
                  command=self.export_mappings).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(left_buttons, text="Reset to Defaults", 
                  command=self.reset_to_defaults).pack(side=tk.LEFT)
        
        # Right side buttons
        right_buttons = ttk.Frame(button_frame)
        right_buttons.pack(side=tk.RIGHT)
        
        ttk.Button(right_buttons, text="Apply", 
                  command=self.apply_changes).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(right_buttons, text="Save", 
                  command=self.save_changes).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(right_buttons, text="Cancel", 
                  command=self.on_close).pack(side=tk.LEFT)
    
    def setup_mappings_tab(self, parent):
        """Setup the mappings configuration tab"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        
        # Toolbar
        toolbar = ttk.Frame(parent)
        toolbar.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        ttk.Button(toolbar, text="Add Mapping", 
                  command=self.add_mapping).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="Edit Selected", 
                  command=self.edit_mapping).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="Delete Selected", 
                  command=self.delete_mapping).pack(side=tk.LEFT)
        
        # Create treeview for mappings
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
        info_label = ttk.Label(parent, 
                             text="Note: Mappings are case-insensitive. Numbers in section names are preserved automatically.",
                             font=('TkDefaultFont', 9))
        info_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
    
    def setup_preview_tab(self, parent):
        """Setup the preview and testing tab"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        
        # Test input frame
        input_frame = ttk.LabelFrame(parent, text="Test Input", padding="10")
        input_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        input_frame.columnconfigure(1, weight=1)
        
        ttk.Label(input_frame, text="Swedish Text:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        
        self.test_input = tk.StringVar(value="vers 1")
        test_entry = ttk.Entry(input_frame, textvariable=self.test_input, width=40)
        test_entry.grid(row=0, column=1, sticky=(tk.W, tk.E))
        test_entry.bind('<KeyRelease>', self.update_preview)
        
        ttk.Button(input_frame, text="Test", 
                  command=self.update_preview).grid(row=0, column=2, padx=(5, 0))
        
        # Results frame
        results_frame = ttk.LabelFrame(parent, text="Preview Results", padding="10")
        results_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Preview text widget
        self.preview_text = tk.Text(results_frame, height=10, width=60, wrap=tk.WORD)
        self.preview_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        preview_scroll = ttk.Scrollbar(results_frame, orient="vertical", 
                                      command=self.preview_text.yview)
        preview_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.preview_text.configure(yscrollcommand=preview_scroll.set)
        
        # Common examples frame
        examples_frame = ttk.LabelFrame(parent, text="Common Examples", padding="10")
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
        
        ttk.Label(examples_frame, text=examples_text, justify=tk.LEFT).pack(anchor=tk.W)
        
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
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x150")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center on parent
        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 200
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 75
        self.dialog.geometry(f"+{x}+{y}")
        
        # Create form
        frame = ttk.Frame(self.dialog, padding="20")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Label(frame, text="Swedish/Source:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.swedish_var = tk.StringVar(value=initial_swedish)
        self.swedish_entry = ttk.Entry(frame, textvariable=self.swedish_var, width=30)
        self.swedish_entry.grid(row=0, column=1, pady=5, padx=(10, 0))
        
        ttk.Label(frame, text="English/Target:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.english_var = tk.StringVar(value=initial_english)
        self.english_entry = ttk.Entry(frame, textvariable=self.english_var, width=30)
        self.english_entry.grid(row=1, column=1, pady=5, padx=(10, 0))
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(15, 0))
        
        ttk.Button(button_frame, text="OK", command=self.ok_clicked).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel_clicked).pack(side=tk.LEFT)
        
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
