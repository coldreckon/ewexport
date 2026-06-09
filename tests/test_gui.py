"""
GUI unit tests.

These tests create real CustomTkinter windows (no mainloop - events are
pumped manually with update()) and drive the widget logic directly. They
need a desktop session; they are unit tests for widget wiring, not a
replacement for a manual pass.
"""

import unittest
import sys
import tempfile
import shutil
import threading
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

# Repo root for src.* imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.export.propresenter import DuplicateDecision
from src.gui.main_window import MainWindow
from src.utils.update_checker import UpdateChecker
import src.utils.config as config_module


def make_songs():
    return [
        {'rowid': 1, 'title': 'Amazing Grace', 'author': 'John Newton',
         'copyright': 'Public Domain', 'reference_number': '22025'},
        {'rowid': 2, 'title': 'Härlig är jorden', 'author': 'Traditional',
         'copyright': '', 'reference_number': ''},
        {'rowid': 3, 'title': 'Cornerstone', 'author': 'Hillsong',
         'copyright': '© 2011', 'reference_number': '6158927'},
    ]


def pump(root, seconds):
    """Process Tk events for the given duration (instead of mainloop)"""
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


# One shared MainWindow for the whole module: creating a fresh Tcl
# interpreter per test class intermittently fails on Windows with
# "Can't find a usable init.tcl" when many are created in one process.
_shared = {}


def _get_shared_app():
    if 'app' not in _shared:
        temp_dir = tempfile.mkdtemp()
        patches = [
            patch('src.utils.config.get_app_data_dir', return_value=Path(temp_dir)),
            patch('src.utils.section_mappings.get_app_data_dir', return_value=Path(temp_dir)),
            patch.object(MainWindow, 'auto_load_database', lambda self: None),
            patch.object(UpdateChecker, 'should_check_on_startup', lambda self: False),
        ]
        for p in patches:
            p.start()

        # Bypass the cached global config manager so the temp dir is used
        config_module._config_manager = None

        app = MainWindow()
        app.root.update()
        _shared.update(app=app, temp_dir=temp_dir, patches=patches)
    return _shared['app']


def tearDownModule():
    if 'app' in _shared:
        try:
            _shared['app'].root.update()
            _shared['app'].root.destroy()
        except tk.TclError:
            pass
        for p in _shared['patches']:
            p.stop()
        config_module._config_manager = None
        shutil.rmtree(_shared['temp_dir'], ignore_errors=True)
        _shared.clear()


class MainWindowTestCase(unittest.TestCase):
    """Base class: all test classes share one MainWindow and config dir"""

    @classmethod
    def setUpClass(cls):
        cls.app = _get_shared_app()
        cls.temp_dir = _shared['temp_dir']

    def setUp(self):
        app = self.app
        app.all_songs = make_songs()
        app.songs_data = list(app.all_songs)
        app.filtered_songs = list(app.all_songs)
        app.selected_songs.clear()
        app.search_var.set('')
        app.display_songs(app.filtered_songs)
        app.root.update()

    def tree_titles(self):
        return [self.app.tree.item(i, 'values')[0]
                for i in self.app.tree.get_children()]


class TestSearchFiltering(MainWindowTestCase):

    def test_no_search_shows_all_songs(self):
        self.app.apply_search_filter()
        self.assertEqual(len(self.app.tree.get_children()), 3)

    def test_filter_by_title(self):
        self.app.search_var.set('grace')
        self.app.root.update()
        self.assertEqual(self.tree_titles(), ['Amazing Grace'])

    def test_filter_by_author(self):
        self.app.search_var.set('hillsong')
        self.app.root.update()
        self.assertEqual(self.tree_titles(), ['Cornerstone'])

    def test_filter_swedish_characters(self):
        self.app.search_var.set('härlig')
        self.app.root.update()
        self.assertEqual(self.tree_titles(), ['Härlig är jorden'])

    def test_filter_by_ccli(self):
        self.app.search_var.set('6158927')
        self.app.root.update()
        self.assertEqual(self.tree_titles(), ['Cornerstone'])

    def test_typing_in_search_entry_filters_live(self):
        """Regression: text typed into the CTkComboBox entry must reach
        search_var (and thus the live filter) without pressing Enter."""
        entry = self.app.search_combo._entry
        entry.delete(0, tk.END)
        entry.insert(0, 'corner')
        self.app.root.update()
        self.assertEqual(self.app.search_var.get(), 'corner')
        self.assertEqual(self.tree_titles(), ['Cornerstone'])

    def test_clear_search_restores_all(self):
        self.app.search_var.set('grace')
        self.app.root.update()
        self.app.clear_search()
        self.app.root.update()
        self.assertEqual(len(self.app.tree.get_children()), 3)

    def test_result_count_label(self):
        self.app.search_var.set('grace')
        self.app.root.update()
        self.assertIn('Showing 1 of 3', self.app.result_count_label.cget('text'))
        self.app.clear_search()
        self.app.root.update()
        self.assertIn('Total: 3', self.app.result_count_label.cget('text'))

    def test_search_history_added_on_enter(self):
        self.app.search_history.clear()
        self.app.search_var.set('mysearch')
        self.app.add_to_search_history()
        self.assertIn('mysearch', self.app.search_history)
        # And persisted via the config manager
        self.assertIn('mysearch', self.app.config.get_search_history())


class TestSongListPaneVisible(MainWindowTestCase):
    """Regression for the 'search results not shown' bug: the song-list
    pane collapsed to zero width because the sash was restored before the
    CTk root applied its (lazy) geometry."""

    def test_song_list_pane_has_width_after_startup(self):
        self.app.root.deiconify()
        # Collapse the pane the way the old bug left it
        self.app.paned.sashpos(0, 0)
        self.app._restore_sash_position()
        pump(self.app.root, 1.0)

        sash = self.app.paned.sashpos(0)
        self.assertGreater(sash, 150,
                           f"song list pane collapsed (sash at {sash})")
        tree_pane = self.app.paned.nametowidget(self.app.paned.panes()[0])
        self.assertGreater(tree_pane.winfo_width(), 150)

    def test_saved_sash_position_is_clamped(self):
        """A saved position beyond the window width must not hide the preview"""
        self.app.config.set('song_list.preview_sash_position', 99999)
        self.app._restore_sash_position()
        pump(self.app.root, 0.6)
        width = self.app.paned.winfo_width()
        self.assertLessEqual(self.app.paned.sashpos(0), width - 150)


class TestSelection(MainWindowTestCase):

    def test_select_all(self):
        self.app.select_all()
        self.assertEqual(self.app.selected_songs, {1, 2, 3})
        marks = [self.app.tree.item(i, 'text') for i in self.app.tree.get_children()]
        self.assertEqual(marks, ['☑', '☑', '☑'])
        self.assertIn('3 songs selected', self.app.selected_count_label.cget('text'))

    def test_select_none(self):
        self.app.select_all()
        self.app.select_none()
        self.assertEqual(self.app.selected_songs, set())
        marks = [self.app.tree.item(i, 'text') for i in self.app.tree.get_children()]
        self.assertEqual(marks, ['☐', '☐', '☐'])

    def test_toggle_item(self):
        item = self.app.tree.get_children()[0]
        self.app.toggle_item_selection(item)
        self.assertEqual(self.app.selected_songs, {1})
        self.app.toggle_item_selection(item)
        self.assertEqual(self.app.selected_songs, set())

    def test_selection_survives_filtering(self):
        self.app.select_all()
        self.app.search_var.set('grace')
        self.app.root.update()
        self.app.clear_search()
        self.app.root.update()
        self.assertEqual(self.app.selected_songs, {1, 2, 3})
        marks = [self.app.tree.item(i, 'text') for i in self.app.tree.get_children()]
        self.assertEqual(marks, ['☑', '☑', '☑'])


class TestProgressAndExportUi(MainWindowTestCase):

    def test_progress_uses_zero_to_one_scale(self):
        self.app.update_export_progress(1, 4, 'Test Song')
        pump(self.app.root, 0.1)
        self.assertAlmostEqual(self.app.progress.get(), 0.25)
        self.assertIn('Test Song (2/4)', self.app.progress_label.cget('text'))

    def test_progress_complete(self):
        self.app.update_export_progress(4, 4, 'done')
        pump(self.app.root, 0.1)
        self.assertAlmostEqual(self.app.progress.get(), 1.0)
        self.assertIn('Export complete', self.app.progress_label.cget('text'))

    def test_export_complete_resets_ui(self):
        self.app.select_all()
        with patch('src.gui.main_window.messagebox'):
            self.app.export_complete(['Song A', 'Song B'], [], [])
        self.assertEqual(self.app.export_btn.cget('state'), 'normal')
        self.assertEqual(self.app.cancel_btn.cget('state'), 'disabled')
        # Selection is cleared after a successful export
        self.assertEqual(self.app.selected_songs, set())

    def test_export_error_resets_ui(self):
        with patch('src.gui.main_window.messagebox'):
            self.app.export_error('boom')
        self.assertEqual(self.app.export_btn.cget('state'), 'normal')
        self.assertAlmostEqual(self.app.progress.get(), 0.0)


class TestDuplicateDecisionMarshalling(MainWindowTestCase):
    """The exporter worker thread asks for duplicate decisions; the dialog
    must be created on the Tk main thread and the worker must receive the
    user's answer."""

    def test_worker_thread_receives_decision(self):
        class FakeDialog:
            def __init__(self, parent, file_path, remaining):
                self.dialog = tk.Toplevel(parent)
                self.result = ('rename', None)
                self.apply_to_all = True
                self.dialog.after(50, self.dialog.destroy)

        results = []

        def worker_body():
            try:
                results.append(self.app._ask_duplicate_decision(Path('x.pro6'), 2))
            finally:
                self.app.root.after(0, self.app.root.quit)

        # root.after() from a worker thread requires the main thread to be
        # inside mainloop (as it is in production), so run a real mainloop
        # here instead of pumping update().
        with patch('src.gui.main_window.DuplicateFileDialog', FakeDialog):
            self.app.root.after(
                100, lambda: threading.Thread(target=worker_body, daemon=True).start())
            safety = self.app.root.after(5000, self.app.root.quit)
            self.app.root.mainloop()
            self.app.root.after_cancel(safety)

        self.assertEqual(results, [DuplicateDecision('rename', None, True)])


class TestDuplicateFileDialog(MainWindowTestCase):

    def _make_dialog(self, remaining=2):
        from src.gui.dialogs import DuplicateFileDialog
        dialog = DuplicateFileDialog(self.app.root, Path('Song.pro6'), remaining)
        self.app.root.update()
        return dialog

    def test_ok_returns_selected_action(self):
        dialog = self._make_dialog()
        dialog.action_var.set('overwrite')
        dialog.apply_all_var.set(True)
        dialog._ok_clicked()
        self.assertEqual(dialog.result, ('overwrite', None))
        self.assertTrue(dialog.apply_to_all)

    def test_cancel(self):
        dialog = self._make_dialog()
        dialog._cancel_clicked()
        self.assertEqual(dialog.result, ('cancel', None))

    def test_no_apply_all_checkbox_without_remaining(self):
        dialog = self._make_dialog(remaining=0)
        dialog.action_var.set('skip')
        dialog._ok_clicked()
        self.assertEqual(dialog.result, ('skip', None))
        self.assertFalse(dialog.apply_to_all)


class TestExportOptionsDialog(MainWindowTestCase):

    def test_save_and_reload_round_trip(self):
        from src.gui.dialogs import ExportOptionsDialog

        dialog = ExportOptionsDialog(self.app.root, self.app.config)
        self.app.root.update()

        dialog.include_ccli_var.set(True)
        dialog.formatting_enabled_var.set(True)
        dialog.font_family_var.set('Verdana')
        dialog.font_size_var.set('90')
        dialog.duplicate_action_var.set('rename')
        dialog._save_settings()
        dialog.dialog.destroy()

        config = self.app.config
        self.assertTrue(config.get('export.include_ccli_in_filename'))
        self.assertTrue(config.get('export.formatting_enabled'))
        self.assertEqual(config.get('export.font.family'), 'Verdana')
        self.assertEqual(config.get('export.font.size'), 90)
        self.assertEqual(config.get('export.duplicate_handling_action'), 'rename')

        # A new dialog loads the saved values back
        dialog2 = ExportOptionsDialog(self.app.root, self.app.config)
        self.app.root.update()
        self.assertTrue(dialog2.include_ccli_var.get())
        self.assertEqual(dialog2.font_family_var.get(), 'Verdana')
        self.assertEqual(dialog2.font_size_var.get(), '90')
        dialog2.dialog.destroy()

    def test_invalid_font_size_falls_back_to_default(self):
        from src.gui.dialogs import ExportOptionsDialog

        dialog = ExportOptionsDialog(self.app.root, self.app.config)
        self.app.root.update()
        dialog.font_size_var.set('not-a-number')
        dialog._save_settings()
        dialog.dialog.destroy()
        self.assertEqual(self.app.config.get('export.font.size'), 72)


class TestSettingsWindow(MainWindowTestCase):

    class FakeParent:
        def __init__(self, root):
            self.root = root
            self.reloaded = False

        def reload_section_mappings(self):
            self.reloaded = True

    def _make_window(self):
        from src.gui.settings_window import SettingsWindow
        parent = self.FakeParent(self.app.root)
        window = SettingsWindow(parent_window=parent)
        self.app.root.update()
        return window, parent

    def test_loads_default_mappings(self):
        window, _ = self._make_window()
        self.assertEqual(window.mappings.get('vers'), 'Verse')
        self.assertEqual(window.mappings.get('refräng'), 'Chorus')
        # Tree is populated
        self.assertEqual(len(window.mappings_tree.get_children()),
                         len(window.mappings))
        window.window.destroy()

    def test_apply_section_mapping_preserves_numbers(self):
        window, _ = self._make_window()
        self.assertEqual(window.apply_section_mapping('vers 2'), 'Verse 2')
        self.assertEqual(window.apply_section_mapping('refräng'), 'Chorus')
        self.assertEqual(window.apply_section_mapping('unknown 3'), 'unknown 3')
        window.window.destroy()

    def test_save_notifies_parent_and_persists(self):
        window, parent = self._make_window()
        window.mappings['testsection'] = 'TestSection'
        window.has_changes = True
        self.assertTrue(window.save_mappings())

        from src.utils import section_mappings
        self.assertEqual(section_mappings.load_mappings().get('testsection'),
                         'TestSection')

        window.window.destroy()


if __name__ == '__main__':
    unittest.main()
