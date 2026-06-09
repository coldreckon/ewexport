"""
Main GUI window for EasyWorship to ProPresenter converter
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import os
import re
import threading
import json
import logging
from typing import List, Optional, Dict, Any
from collections import deque
from src.database.easyworship import EasyWorshipDatabase
from src.export.propresenter import ProPresenter6Exporter, DuplicateDecision
from src.gui.settings_window import SettingsWindow
from src.gui.dialogs import DuplicateFileDialog, ExportOptionsDialog
from src.utils.config import get_config
from src.utils.update_checker import UpdateChecker
from src.version import __version__, RELEASE_DATE, RELEASE_YEAR

logger = logging.getLogger(__name__)

class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("EasyWorship to ProPresenter Converter")
        
        # Initialize config manager
        self.config = get_config()
        
        # Load and apply window geometry
        self._apply_window_geometry()
        
        self.db_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.search_var = tk.StringVar()
        self.selected_songs = set()
        self.songs_data = []
        self.filtered_songs = []  # Songs currently shown after filtering
        self.all_songs = []  # All songs from database
        self.search_history = deque(maxlen=10)  # Last 10 searches
        self.db = None
        self.exporter = ProPresenter6Exporter(config=self.config)
        self.export_in_progress = False
        self.export_cancel_event = threading.Event()  # For proper thread cancellation
        self.duplicate_action = None  # For remembering duplicate handling choice
        self.update_checker = UpdateChecker(config=self.config)
        
        # Load search history from settings
        self.load_search_history()
        
        self.setup_ui()
        self.auto_load_database()
        
        # Bind search variable to update function
        self.search_var.trace('w', self.on_search_changed)
        
        # Save geometry on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Check for updates on startup if enabled
        if self.update_checker.should_check_on_startup():
            self.root.after(1000, self.check_for_updates_startup)
        
    def setup_ui(self):
        """Build the main GUI interface"""
        # Create menu bar
        self.create_menu_bar()
        
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Database selection frame
        db_frame = ttk.LabelFrame(main_frame, text="EasyWorship Database", padding="10")
        db_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        db_frame.columnconfigure(1, weight=1)
        
        ttk.Label(db_frame, text="Database Path:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        path_entry = ttk.Entry(db_frame, textvariable=self.db_path, width=50)
        path_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        browse_btn = ttk.Button(db_frame, text="Browse...", command=self.browse_database)
        browse_btn.grid(row=0, column=2, padx=(5, 0))
        
        load_btn = ttk.Button(db_frame, text="Load Songs", command=self.load_songs)
        load_btn.grid(row=0, column=3, padx=(5, 0))
        
        # Song count label
        self.status_label = ttk.Label(db_frame, text="No database loaded")
        self.status_label.grid(row=1, column=0, columnspan=4, sticky=tk.W, pady=(5, 0))
        
        # Song list frame
        list_frame = ttk.LabelFrame(main_frame, text="Songs", padding="10")
        list_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(2, weight=1)  # Changed to row 2 for tree
        
        # Search frame
        search_frame = ttk.Frame(list_frame)
        search_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        search_frame.columnconfigure(1, weight=1)
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        
        # Search combobox with history
        self.search_combo = ttk.Combobox(search_frame, textvariable=self.search_var, width=30)
        self.search_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.search_combo.bind('<Return>', self.add_to_search_history)
        
        # Clear search button
        ttk.Button(search_frame, text="Clear", command=self.clear_search).pack(side=tk.LEFT, padx=(0, 10))
        
        # Result count label
        self.result_count_label = ttk.Label(search_frame, text="")
        self.result_count_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Selection buttons
        button_frame = ttk.Frame(list_frame)
        button_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Button(button_frame, text="Select All", command=self.select_all).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Select None", command=self.select_none).pack(side=tk.LEFT, padx=(0, 5))
        
        self.selected_count_label = ttk.Label(button_frame, text="0 songs selected")
        self.selected_count_label.pack(side=tk.LEFT, padx=(20, 0))
        
        # PanedWindow to split song list and preview
        self.paned = ttk.PanedWindow(list_frame, orient=tk.HORIZONTAL)
        self.paned.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Left pane: Treeview with scrollbars
        tree_frame = ttk.Frame(self.paned)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        # Create Treeview for song list
        columns = ('title', 'author', 'copyright', 'ccli')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='tree headings', selectmode='extended')
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure columns
        self.tree.heading('#0', text='✓', anchor=tk.W)
        self.tree.column('#0', width=30, stretch=False)

        self.tree.heading('title', text='Title')
        self.tree.column('title', width=300)

        self.tree.heading('author', text='Author')
        self.tree.column('author', width=200)

        self.tree.heading('copyright', text='Copyright')
        self.tree.column('copyright', width=200)

        self.tree.heading('ccli', text='CCLI/Ref')
        self.tree.column('ccli', width=100)

        # Add scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.tree.configure(yscrollcommand=vsb.set)

        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.tree.configure(xscrollcommand=hsb.set)

        self.paned.add(tree_frame, weight=3)

        # Right pane: Preview panel
        preview_frame = ttk.Frame(self.paned)
        self._setup_preview_panel(preview_frame)
        self.paned.add(preview_frame, weight=1)

        # Restore saved sash position after layout is computed
        self.root.after(100, self._restore_sash_position)

        # Bind click event for checkbox toggle
        self.tree.bind('<ButtonRelease-1>', self.on_item_click)

        # Bind selection change for keyboard navigation
        self.tree.bind('<<TreeviewSelect>>', self._on_tree_select)
        
        # Export frame
        export_frame = ttk.LabelFrame(main_frame, text="Export Options", padding="10")
        export_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        export_frame.columnconfigure(1, weight=1)
        
        # Output path selection
        ttk.Label(export_frame, text="Output Path:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        output_entry = ttk.Entry(export_frame, textvariable=self.output_path, width=50)
        output_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        browse_output_btn = ttk.Button(export_frame, text="Browse...", command=self.browse_output_path)
        browse_output_btn.grid(row=0, column=2, padx=(5, 0))
        
        # Progress section
        progress_frame = ttk.Frame(export_frame)
        progress_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        progress_frame.columnconfigure(0, weight=1)
        
        # Progress bar
        self.progress = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        # Progress label
        self.progress_label = ttk.Label(progress_frame, text="Ready to export")
        self.progress_label.grid(row=1, column=0, sticky=tk.W)
        
        # Export button
        button_frame = ttk.Frame(export_frame)
        button_frame.grid(row=2, column=0, columnspan=3, pady=(10, 0))
        
        self.export_btn = ttk.Button(button_frame, text="Export Selected Songs", 
                                     command=self.start_export, state='disabled')
        self.export_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.cancel_btn = ttk.Button(button_frame, text="Cancel Export", 
                                     command=self.cancel_export, state='disabled')
        self.cancel_btn.pack(side=tk.LEFT)
        
    def create_menu_bar(self):
        """Create the application menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Load Database...", command=self.browse_database)
        file_menu.add_command(label="Set Export Directory...", command=self.browse_output_path)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Select All", command=self.select_all)
        edit_menu.add_command(label="Select None", command=self.select_none)
        edit_menu.add_separator()
        edit_menu.add_command(label="Section Mappings...", command=self.open_settings)
        edit_menu.add_command(label="Export Options...", command=self.open_export_options)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Check for Updates...", command=self.check_for_updates_manual)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self.show_about)
    
    def open_settings(self):
        """Open the settings window for section mappings"""
        settings = SettingsWindow(parent_window=self)
        self.root.wait_window(settings.window)
        
        # Reload section mappings if they changed
        if hasattr(self, 'db') and self.db:
            self.db.reload_section_mappings()
    
    def reload_section_mappings(self):
        """Reload section mappings after settings change"""
        if hasattr(self, 'db') and self.db:
            self.db.reload_section_mappings()
    
    def open_export_options(self):
        """Open the export options dialog"""
        dialog = ExportOptionsDialog(self.root, self.config)
        self.root.wait_window(dialog.dialog)
    
    def show_about(self):
        """Show about dialog"""
        about_text = f"""EasyWorship to ProPresenter Converter

Version: {__version__}
Released: {RELEASE_DATE}

Converts songs from EasyWorship 6.1 database format
to ProPresenter 6 format with Swedish language support.

Features:
• Real-time search and filtering
• Configurable section mappings
• Batch export with progress tracking
• Full Swedish character support

© {RELEASE_YEAR} - Created with Python and Tkinter
GitHub: https://github.com/karllinder/ewexport"""
        
        messagebox.showinfo("About", about_text)
    
    def auto_load_database(self):
        """Auto-load database from saved path or auto-detection"""
        # First try to load from saved path
        last_db = self.config.get('paths.last_easyworship_path')
        if last_db and Path(last_db).exists() and (Path(last_db) / 'Songs.db').exists():
            self.db_path.set(last_db)
            self.load_songs()
            # Load export path settings
            self.load_export_path_settings()
            return
        
        # If no saved path, try auto-detection
        self.auto_detect_easyworship()
        # Load export path settings
        self.load_export_path_settings()
    
    def load_export_path_settings(self):
        """Load export path settings only"""
        last_export = self.config.get_export_directory()
        if last_export and last_export.exists():
            self.output_path.set(str(last_export))
        else:
            self.set_default_output_path()
    
    def auto_detect_easyworship(self):
        """Try to auto-detect EasyWorship database path"""
        # Common EasyWorship installation paths
        possible_paths = [
            Path(os.environ.get('PROGRAMDATA', 'C:\\ProgramData')) / 'Softouch' / 'Easyworship' / 'Default' / 'Databases' / 'Data',
            Path(os.environ.get('USERPROFILE', '')) / 'Documents' / 'EasyWorship' / 'Default' / 'Databases' / 'Data',
            Path('C:\\Users\\Public\\Documents\\Softouch\\Easyworship\\Default\\Databases\\Data'),
        ]
        
        for path in possible_paths:
            if path.exists() and (path / 'Songs.db').exists():
                self.db_path.set(str(path))
                self.load_songs()
                break
    
    def browse_database(self):
        """Browse for EasyWorship database folder - enhanced to show .db files"""
        # First try to show a file dialog that displays .db files for reference
        # This helps users confirm they're in the right folder
        initial_dir = self.db_path.get() if self.db_path.get() else os.path.expanduser("~")
        
        # Use a custom dialog approach: show a file dialog to let users see .db files,
        # but we actually want the directory path
        db_file = filedialog.askopenfilename(
            title="Select Songs.db or SongWords.db (will use containing folder)",
            initialdir=initial_dir,
            filetypes=[
                ("EasyWorship Database Files", "*.db"),
                ("Songs Database", "Songs.db"),
                ("Words Database", "SongWords.db"),
                ("All Files", "*.*")
            ]
        )
        
        if db_file:
            # Extract the directory from the selected file
            folder = os.path.dirname(db_file)
            
            # Verify it contains the necessary database files
            songs_db = Path(folder) / "Songs.db"
            words_db = Path(folder) / "SongWords.db"
            
            if not songs_db.exists() or not words_db.exists():
                # Warn but still allow selection (user might know what they're doing)
                response = messagebox.askyesno(
                    "Database Files Missing",
                    f"Warning: Could not find both Songs.db and SongWords.db in:\n{folder}\n\n"
                    "Do you want to use this folder anyway?"
                )
                if not response:
                    return
            
            self.db_path.set(folder)
            # Save to config
            self.config.set('paths.last_easyworship_path', folder)
            self.config.add_recent_database(folder)
            self.load_songs()
    
    def load_songs(self):
        """Load songs from the selected database"""
        db_path = self.db_path.get()
        if not db_path:
            messagebox.showwarning("No Path", "Please select a database folder first.")
            return
        
        try:
            self.db = EasyWorshipDatabase(db_path)
            
            if not self.db.validate_database():
                messagebox.showerror("Invalid Database", 
                                   "The selected folder does not contain valid EasyWorship database files.")
                return
            
            # Clear existing items
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.selected_songs.clear()
            self._clear_preview()
            
            # Load songs
            self.all_songs = self.db.get_all_songs()
            self.songs_data = self.all_songs.copy()
            self.filtered_songs = self.all_songs.copy()
            song_count = len(self.all_songs)
            
            # Apply current search filter if any
            if self.search_var.get():
                self.apply_search_filter()
            else:
                self.display_songs(self.filtered_songs)
            
            self.status_label.config(text=f"Loaded {song_count} songs from database")
            self.export_btn.config(state='normal' if song_count > 0 else 'disabled')
            self.update_selected_count()
            self.update_result_count()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load database: {str(e)}")
    
    def on_item_click(self, event):
        """Handle click on tree item to toggle selection and update preview"""
        region = self.tree.identify_region(event.x, event.y)
        item = self.tree.identify_row(event.y)

        if region == "tree":
            if item:
                self.toggle_item_selection(item)
                self._update_preview_for_item(item)
        elif region in ("cell", "heading") and item:
            self._update_preview_for_item(item)
    
    def toggle_item_selection(self, item):
        """Toggle selection state of an item"""
        tags = self.tree.item(item, 'tags')
        if tags and len(tags) > 0:
            song_id = int(tags[0])  # Ensure it's an integer
            
            if song_id in self.selected_songs:
                self.selected_songs.remove(song_id)
                self.tree.item(item, text='☐')
            else:
                self.selected_songs.add(song_id)
                self.tree.item(item, text='☑')
        
        self.update_selected_count()
    
    def select_all(self):
        """Select all songs"""
        for item in self.tree.get_children():
            tags = self.tree.item(item, 'tags')
            if tags and len(tags) > 0:
                song_id = int(tags[0])  # Ensure it's an integer
                self.selected_songs.add(song_id)
                self.tree.item(item, text='☑')
        
        self.update_selected_count()
    
    def select_none(self):
        """Deselect all songs"""
        self.selected_songs.clear()
        for item in self.tree.get_children():
            self.tree.item(item, text='☐')
        
        self.update_selected_count()
    
    def update_selected_count(self):
        """Update the selected songs count label"""
        count = len(self.selected_songs)
        self.selected_count_label.config(text=f"{count} song{'s' if count != 1 else ''} selected")
    
    def set_default_output_path(self):
        """Set default output path"""
        desktop = Path.home() / "Desktop"
        default_path = desktop / "ProPresenter_Export"
        self.output_path.set(str(default_path))
    
    def browse_output_path(self):
        """Browse for output directory"""
        folder = filedialog.askdirectory(
            title="Select Export Directory",
            initialdir=self.output_path.get() if self.output_path.get() else str(Path.home())
        )
        
        if folder:
            self.output_path.set(folder)
            # Save to config
            self.config.set_export_directory(Path(folder))
    
    def start_export(self):
        """Start the export process in a separate thread"""
        if not self.selected_songs:
            messagebox.showinfo("No Selection", "Please select at least one song to export.")
            return
        
        if not self.output_path.get():
            messagebox.showwarning("No Output Path", "Please select an output directory.")
            return
        
        # Confirm export
        count = len(self.selected_songs)
        if not messagebox.askyesno("Confirm Export", 
                                  f"Export {count} selected song{'s' if count != 1 else ''} to ProPresenter 6 format?"):
            return
        
        # Start export in background thread
        self.export_in_progress = True
        self.export_cancel_event.clear()  # Reset cancel event for new export
        self.export_btn.config(state='disabled')
        self.cancel_btn.config(state='normal')
        self.progress.config(mode='determinate', value=0)
        self.progress_label.config(text="Preparing export...")

        self.export_thread = threading.Thread(target=self.export_worker, daemon=True)
        self.export_thread.start()
    
    def export_worker(self):
        """Background worker for export process"""
        try:
            # Collect selected songs with processed lyrics
            songs_to_export = []
            selected_song_ids = list(self.selected_songs)
            
            # Use all_songs instead of songs_data to ensure we export all selected songs
            for song_data in self.all_songs:
                if song_data['rowid'] in selected_song_ids:
                    # Get processed lyrics with sections
                    processed = self.db.get_song_with_processed_lyrics(song_data['rowid'])
                    
                    if processed:
                        # Use the processed song data which has all fields properly filled
                        # This ensures we have consistent data for export
                        if processed.get('sections'):
                            sections = processed['sections']
                            songs_to_export.append((processed, sections))
                        else:
                            # Songs without any parseable content - add with empty section
                            # This will be caught by the exporter's validation
                            empty_sections = []
                            songs_to_export.append((processed, empty_sections))
                    else:
                        # Fallback if processing fails - still try to export with basic data
                        logger.warning(f"Could not process song ID {song_data['rowid']}: {song_data.get('title', 'Unknown')}")
                        songs_to_export.append((song_data, []))
            
            # Export songs
            output_dir = Path(self.output_path.get())
            successful, failed, skipped = self.exporter.export_songs_batch(
                songs_to_export,
                output_dir,
                progress_callback=self.update_export_progress,
                on_duplicate=self._ask_duplicate_decision,
                cancel_event=self.export_cancel_event
            )

            # Update UI in main thread
            self.root.after(0, self.export_complete, successful, failed, skipped)
            
        except Exception as e:
            error_msg = f"Export failed with error: {str(e)}"
            logger.error("Export worker failed", exc_info=True)
            self.root.after(0, self.export_error, error_msg)
    
    def _ask_duplicate_decision(self, file_path: Path, remaining: int) -> DuplicateDecision:
        """Resolve a duplicate export file by asking the user.

        Called from the export worker thread; the dialog must be created on
        the Tk main thread, so marshal via after() and block the worker until
        the user answers.
        """
        holder = {}
        done = threading.Event()

        def show():
            try:
                dialog = DuplicateFileDialog(self.root, file_path, remaining)
                self.root.wait_window(dialog.dialog)
                action, custom_name = dialog.result or ('cancel', None)
                holder['decision'] = DuplicateDecision(action, custom_name, dialog.apply_to_all)
            except Exception:
                logger.error("Duplicate dialog failed", exc_info=True)
                holder['decision'] = DuplicateDecision('cancel')
            finally:
                done.set()

        self.root.after(0, show)
        done.wait()
        return holder['decision']

    def update_export_progress(self, current: int, total: int, song_title: str):
        """Update progress bar and label (called from background thread)"""
        def update_ui():
            if total > 0:
                progress_percent = (current / total) * 100
                self.progress.config(value=progress_percent)
            
            if current < total:
                self.progress_label.config(text=f"Exporting: {song_title} ({current + 1}/{total})")
            else:
                self.progress_label.config(text="Export complete")
        
        self.root.after(0, update_ui)
    
    def export_complete(self, successful: List[str], failed: List[str], skipped: List[str] = None):
        """Handle export completion"""
        if skipped is None:
            skipped = []

        self.export_in_progress = False
        self.export_btn.config(state='normal')
        self.cancel_btn.config(state='disabled')

        # Check if export was cancelled
        was_cancelled = self.export_cancel_event.is_set()
        if was_cancelled:
            self.progress.config(value=0)
            self.progress_label.config(text="Export cancelled")
            success_count = len(successful)
            skip_count = len(skipped)
            message = f"Export was cancelled.\n\n"
            if success_count > 0:
                message += f"{success_count} song{'s were' if success_count != 1 else ' was'} exported before cancellation."
            if skip_count > 0:
                message += f"\n{skip_count} song{'s were' if skip_count != 1 else ' was'} skipped."
            messagebox.showinfo("Export Cancelled", message)
            return

        self.progress.config(value=100)

        # Show results
        success_count = len(successful)
        fail_count = len(failed)
        skip_count = len(skipped)

        if fail_count == 0 and skip_count == 0:
            # All successful, no skips or failures
            message = f"Successfully exported {success_count} song{'s' if success_count != 1 else ''}!\n\n"
            message += f"Files saved to: {self.output_path.get()}"
            messagebox.showinfo("Export Complete", message)

            # Clear selection after successful export
            self.select_none()
        elif fail_count == 0 and skip_count > 0:
            # Some skipped, no failures
            message = f"Export completed.\n\n"
            message += f"Exported: {success_count} song{'s' if success_count != 1 else ''}\n"
            message += f"Skipped: {skip_count} song{'s' if skip_count != 1 else ''}\n\n"
            if skipped:
                message += "Skipped files:\n"
                for title in skipped[:5]:
                    message += f"  {title}\n"
                if len(skipped) > 5:
                    message += f"  ... and {len(skipped) - 5} more"
            message += f"\n\nFiles saved to: {self.output_path.get()}"
            messagebox.showinfo("Export Complete", message)

            # Clear selection
            self.select_none()
        else:
            # Some failures
            message = f"Export completed with some issues:\n\n"
            message += f"Exported: {success_count} song{'s' if success_count != 1 else ''}\n"
            if skip_count > 0:
                message += f"Skipped: {skip_count} song{'s' if skip_count != 1 else ''}\n"
            message += f"Failed: {fail_count} song{'s' if fail_count != 1 else ''}\n\n"

            if failed:
                message += "Failed exports:\n"
                for error in failed[:5]:  # Show first 5 errors
                    message += f"  {error}\n"
                if len(failed) > 5:
                    message += f"  ... and {len(failed) - 5} more errors"

            messagebox.showwarning("Export Completed with Errors", message)

            # Clear selection even if some exports failed
            self.select_none()

        self.progress_label.config(text="Ready to export")
    
    def export_error(self, error_message: str):
        """Handle export error"""
        self.export_in_progress = False
        self.export_btn.config(state='normal')
        self.cancel_btn.config(state='disabled')
        self.progress.config(value=0)
        self.progress_label.config(text="Export failed")
        
        messagebox.showerror("Export Error", error_message)
    
    def cancel_export(self):
        """Cancel the export process"""
        if self.export_in_progress:
            # Signal the export thread to stop
            self.export_cancel_event.set()
            self.export_in_progress = False
            self.export_btn.config(state='normal')
            self.cancel_btn.config(state='disabled')
            self.progress_label.config(text="Cancelling export...")
            # Note: The export thread will check the cancel event and stop gracefully
    
    def on_search_changed(self, *args):
        """Handle search text changes for real-time filtering"""
        self.apply_search_filter()
    
    def apply_search_filter(self):
        """Apply search filter to song list"""
        search_text = self.search_var.get().lower().strip()
        
        if not search_text:
            # No search, show all songs
            self.filtered_songs = self.all_songs.copy()
        else:
            # Filter songs based on search text
            self.filtered_songs = []
            for song in self.all_songs:
                # Search in title, author, copyright, and CCLI number
                if (search_text in (song['title'] or '').lower() or
                    search_text in (song['author'] or '').lower() or
                    search_text in (song['copyright'] or '').lower() or
                    search_text in (song['reference_number'] or '').lower()):
                    self.filtered_songs.append(song)
        
        # Update display
        self.display_songs(self.filtered_songs)
        self.update_result_count()
    
    def display_songs(self, songs: List[Dict[str, Any]]):
        """Display the given list of songs in the tree view"""
        # Remember which songs were selected
        previously_selected = self.selected_songs.copy()
        
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add filtered songs
        for song in songs:
            song_id = song['rowid']
            is_selected = song_id in previously_selected
            
            item_id = self.tree.insert('', 'end', 
                                      text='☑' if is_selected else '☐',
                                      values=(
                                          song['title'],
                                          song['author'] or '-',
                                          song['copyright'] or '-',
                                          song['reference_number'] or '-'
                                      ),
                                      tags=(song_id,))
    
    def update_result_count(self):
        """Update the result count label"""
        total = len(self.all_songs)
        shown = len(self.filtered_songs)
        
        if self.search_var.get():
            self.result_count_label.config(text=f"Showing {shown} of {total} songs")
        else:
            self.result_count_label.config(text=f"Total: {total} songs")
    
    def _setup_preview_panel(self, parent):
        """Create the preview panel with metadata labels and lyrics text widget"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Song Details section
        details_frame = ttk.LabelFrame(parent, text="Song Details", padding="5")
        details_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=2, pady=(0, 5))
        details_frame.columnconfigure(1, weight=1)

        self._preview_title_var = tk.StringVar(value="")
        self._preview_author_var = tk.StringVar(value="")
        self._preview_copyright_var = tk.StringVar(value="")
        self._preview_ccli_var = tk.StringVar(value="")

        ttk.Label(details_frame, text="Title:", font=('TkDefaultFont', 9, 'bold')).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(details_frame, textvariable=self._preview_title_var,
                  font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=1, sticky=tk.W)

        ttk.Label(details_frame, text="Author:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(details_frame, textvariable=self._preview_author_var).grid(row=1, column=1, sticky=tk.W)

        ttk.Label(details_frame, text="Copyright:").grid(row=2, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(details_frame, textvariable=self._preview_copyright_var).grid(row=2, column=1, sticky=tk.W)

        ttk.Label(details_frame, text="CCLI/Ref:").grid(row=3, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Label(details_frame, textvariable=self._preview_ccli_var).grid(row=3, column=1, sticky=tk.W)

        # Lyrics Preview section
        lyrics_frame = ttk.LabelFrame(parent, text="Lyrics Preview", padding="5")
        lyrics_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=2)
        lyrics_frame.columnconfigure(0, weight=1)
        lyrics_frame.rowconfigure(0, weight=1)

        self._preview_text = tk.Text(lyrics_frame, wrap=tk.WORD, state='disabled',
                                     font=('TkDefaultFont', 10))
        self._preview_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        preview_scroll = ttk.Scrollbar(lyrics_frame, orient="vertical",
                                       command=self._preview_text.yview)
        preview_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self._preview_text.configure(yscrollcommand=preview_scroll.set)

        # Configure text tags for formatting
        self._preview_text.tag_configure('section_header',
                                         font=('TkDefaultFont', 10, 'bold'),
                                         foreground='#1a5fb4',
                                         spacing1=10, spacing3=4)
        self._preview_text.tag_configure('lyrics',
                                         font=('TkDefaultFont', 10))
        self._preview_text.tag_configure('no_content',
                                         font=('TkDefaultFont', 10, 'italic'),
                                         foreground='#888888')

        # Show placeholder
        self._clear_preview()

    def _on_tree_select(self, event):
        """Handle Treeview selection change (keyboard navigation)"""
        selection = self.tree.selection()
        if selection:
            self._update_preview_for_item(selection[0])

    def _update_preview_for_item(self, item):
        """Fetch processed lyrics for the selected item and display preview"""
        tags = self.tree.item(item, 'tags')
        if not tags:
            return

        song_id = int(tags[0])

        if not self.db:
            return

        try:
            song_data = self.db.get_song_with_processed_lyrics(song_id)
            if song_data:
                self._display_preview(song_data)
            else:
                self._clear_preview("Could not load song data")
        except Exception as e:
            logger.warning(f"Failed to load preview for song {song_id}: {e}")
            self._clear_preview("Error loading preview")

    def _display_preview(self, song_data):
        """Populate the preview panel with song metadata and formatted sections"""
        # Update metadata labels
        self._preview_title_var.set(song_data.get('title', ''))
        self._preview_author_var.set(song_data.get('author', '') or '-')
        self._preview_copyright_var.set(song_data.get('copyright', '') or '-')
        self._preview_ccli_var.set(song_data.get('reference_number', '') or '-')

        # Update lyrics text
        self._preview_text.configure(state='normal')
        self._preview_text.delete('1.0', tk.END)

        sections = song_data.get('sections', [])
        if not sections:
            self._preview_text.insert(tk.END, "No lyrics available", 'no_content')
            self._preview_text.configure(state='disabled')
            return

        for i, section in enumerate(sections):
            section_type = section.get('type', 'Verse')
            content = section.get('content', '')

            # Section header
            header = f"[{section_type}]"
            self._preview_text.insert(tk.END, header + '\n', 'section_header')

            # Section content
            if content:
                self._preview_text.insert(tk.END, content + '\n', 'lyrics')

            # Add spacing between sections (except after last)
            if i < len(sections) - 1:
                self._preview_text.insert(tk.END, '\n', 'lyrics')

        self._preview_text.configure(state='disabled')

    def _clear_preview(self, message=None):
        """Reset the preview panel to placeholder state"""
        self._preview_title_var.set("")
        self._preview_author_var.set("")
        self._preview_copyright_var.set("")
        self._preview_ccli_var.set("")

        self._preview_text.configure(state='normal')
        self._preview_text.delete('1.0', tk.END)
        self._preview_text.insert(tk.END, message or "Click on a song to preview", 'no_content')
        self._preview_text.configure(state='disabled')

    def _save_sash_position(self):
        """Save the PanedWindow sash position to config"""
        try:
            pos = self.paned.sashpos(0)
            if pos > 0:
                self.config.set('song_list.preview_sash_position', pos)
        except (tk.TclError, IndexError):
            pass

    def _restore_sash_position(self):
        """Restore saved sash position"""
        saved = self.config.get('song_list.preview_sash_position')
        if saved is not None and int(saved) > 0:
            try:
                self.paned.sashpos(0, int(saved))
            except (tk.TclError, ValueError):
                pass

    def clear_search(self):
        """Clear the search field and show all songs"""
        self.search_var.set('')
        self.apply_search_filter()
    
    def add_to_search_history(self, event=None):
        """Add current search to history when Enter is pressed"""
        search_text = self.search_var.get().strip()
        if search_text and search_text not in self.search_history:
            self.search_history.append(search_text)
            self.update_search_combo_values()
            self.save_search_history()
    
    def update_search_combo_values(self):
        """Update the combobox dropdown with search history"""
        self.search_combo['values'] = list(self.search_history)
    
    def load_search_history(self):
        """Load search history from settings file"""
        settings_dir = Path.home() / '.ewexport'
        settings_file = settings_dir / 'search_history.json'
        
        if settings_file.exists():
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    history = data.get('search_history', [])
                    for item in history[-10:]:  # Keep last 10
                        self.search_history.append(item)
            except Exception:
                pass  # Ignore errors loading history
    
    def save_search_history(self):
        """Save search history to settings file"""
        settings_dir = Path.home() / '.ewexport'
        settings_dir.mkdir(exist_ok=True)
        settings_file = settings_dir / 'search_history.json'
        
        try:
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump({'search_history': list(self.search_history)}, f, indent=2)
        except Exception:
            pass  # Ignore errors saving history
    
    def run(self):
        # Set initial search history dropdown values
        self.update_search_combo_values()
        
        # Check first run
        if self.config.is_first_run():
            self._handle_first_run()
        
        self.root.mainloop()
    
    def _apply_window_geometry(self):
        """Apply saved window geometry"""
        geometry_info = self.config.get_window_geometry('main')
        if geometry_info:
            geometry, position, maximized = geometry_info
            if geometry and position:
                # Combine size and position in one call
                x, y = position.split(',')
                self.root.geometry(f"{geometry}+{x}+{y}")
            elif geometry:
                self.root.geometry(geometry)
            if maximized:
                self.root.state('zoomed' if os.name == 'nt' else 'normal')
        else:
            # Default geometry
            self.root.geometry("1200x700")
    
    def _save_window_geometry(self):
        """Save current window geometry"""
        # Get current state
        maximized = self.root.state() == 'zoomed'
        
        # Get geometry (restore first if maximized to get actual size)
        if maximized:
            self.root.state('normal')
            self.root.update_idletasks()
        
        geometry = self.root.geometry()
        # Parse geometry string (e.g., "900x700+100+50")
        match = re.match(r'(\d+x\d+)\+(\d+)\+(\d+)', geometry)
        if match:
            size = match.group(1)
            position = f"{match.group(2)},{match.group(3)}"
            self.config.save_window_geometry('main', size, position, maximized)
        
        # Restore maximized state if needed
        if maximized:
            self.root.state('zoomed')
    
    def on_closing(self):
        """Handle window closing"""
        # Save window geometry
        self._save_window_geometry()

        # Save preview sash position
        self._save_sash_position()

        # Save column widths if tree exists
        if hasattr(self, 'tree'):
            widths = {}
            for col in ['title', 'author', 'copyright', 'ccli']:
                try:
                    widths[col] = self.tree.column(col, 'width')
                except tk.TclError:
                    pass  # Column may not exist
            if widths:
                self.config.save_column_widths(widths)
        
        # Save search history
        self.save_search_history()
        
        # Destroy window
        self.root.destroy()
    
    def _handle_first_run(self):
        """Handle first run setup"""
        # Ask user to select output directory
        result = messagebox.showinfo(
            "Welcome",
            "Welcome to EasyWorship to ProPresenter Converter!\n\n"
            "Please select your default export directory in the next dialog.",
            parent=self.root
        )
        
        # Browse for output directory
        directory = filedialog.askdirectory(
            title="Select Default Export Directory",
            initialdir=str(Path.home() / "Desktop")
        )
        
        if directory:
            self.config.set_export_directory(Path(directory))
            self.output_path.set(directory)
        
        # Mark first run complete
        self.config.mark_first_run_complete()
    
    def check_for_updates_manual(self):
        """Manually check for updates from the Help menu"""
        # Show checking dialog
        checking_dialog = tk.Toplevel(self.root)
        checking_dialog.title("Check for Updates")
        checking_dialog.geometry("300x100")
        checking_dialog.resizable(False, False)
        
        # Center the dialog
        checking_dialog.transient(self.root)
        checking_dialog.grab_set()
        
        ttk.Label(checking_dialog, text="Checking for updates...").pack(pady=20)
        progress = ttk.Progressbar(checking_dialog, mode='indeterminate')
        progress.pack(pady=10, padx=20, fill=tk.X)
        progress.start()
        
        def handle_update_check(update_info):
            checking_dialog.destroy()
            
            if update_info is None:
                messagebox.showerror(
                    "Update Check Failed",
                    "Could not check for updates.\nPlease check your internet connection and try again."
                )
                return
            
            if not update_info.get('available'):
                messagebox.showinfo(
                    "No Updates Available",
                    f"You are running the latest version (v{update_info['current_version']})."
                )
                return
            
            # Show update available dialog
            message = self.update_checker.format_update_message(update_info)
            response = messagebox.askyesno("Update Available", message)
            
            if response:
                # Open the release page
                release_info = update_info.get('release_info', {})
                if release_info.get('html_url'):
                    self.update_checker.open_specific_release(release_info['html_url'])
                else:
                    self.update_checker.open_download_page()
        
        # Check for updates in background
        self.update_checker.check_for_updates_async(handle_update_check)
    
    def check_for_updates_startup(self):
        """Check for updates on application startup (silent unless update available)"""
        def handle_update_check(update_info):
            if update_info and update_info.get('available'):
                # Only show notification if update is available
                message = self.update_checker.format_update_message(update_info)
                
                # Create custom dialog with "Don't show again" option
                dialog = tk.Toplevel(self.root)
                dialog.title("Update Available")
                dialog.geometry("500x400")
                dialog.resizable(False, False)
                dialog.transient(self.root)
                
                # Message
                text_widget = tk.Text(dialog, wrap=tk.WORD, height=15, width=60)
                text_widget.pack(pady=10, padx=10)
                text_widget.insert('1.0', message)
                text_widget.config(state='disabled')
                
                # Checkbox frame
                checkbox_frame = ttk.Frame(dialog)
                checkbox_frame.pack(pady=5)
                
                check_var = tk.BooleanVar(value=True)
                ttk.Checkbutton(
                    checkbox_frame,
                    text="Check for updates on startup",
                    variable=check_var
                ).pack()
                
                # Button frame
                button_frame = ttk.Frame(dialog)
                button_frame.pack(pady=10)
                
                def download_update():
                    release_info = update_info.get('release_info', {})
                    if release_info.get('html_url'):
                        self.update_checker.open_specific_release(release_info['html_url'])
                    else:
                        self.update_checker.open_download_page()
                    self.update_checker.set_check_on_startup(check_var.get())
                    dialog.destroy()
                
                def close_dialog():
                    self.update_checker.set_check_on_startup(check_var.get())
                    dialog.destroy()
                
                ttk.Button(button_frame, text="Download Update", command=download_update).pack(side=tk.LEFT, padx=5)
                ttk.Button(button_frame, text="Not Now", command=close_dialog).pack(side=tk.LEFT, padx=5)
                
                # Center the dialog
                dialog.update_idletasks()
                x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
                y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
                dialog.geometry(f"+{x}+{y}")
        
        # Check for updates in background
        self.update_checker.check_for_updates_async(handle_update_check)