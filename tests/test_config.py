"""
Tests for configuration management, version migration, and cross-platform paths.

Tests the centralized app data directory function, version comparison logic,
and settings migration functionality.
"""

import unittest
import sys
import os
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from utils.config import get_app_data_dir, ConfigManager
from packaging import version as pkg_version


class TestGetAppDataDir(unittest.TestCase):
    """Test the centralized get_app_data_dir function."""

    def test_returns_path_object(self):
        """Test that function returns a Path object."""
        result = get_app_data_dir()
        self.assertIsInstance(result, Path)

    def test_directory_exists(self):
        """Test that the returned directory exists."""
        result = get_app_data_dir()
        self.assertTrue(result.exists())
        self.assertTrue(result.is_dir())

    @patch('os.name', 'nt')
    @patch.dict(os.environ, {'APPDATA': 'C:\\Users\\Test\\AppData\\Roaming'})
    def test_windows_path_with_appdata(self):
        """Test Windows path when APPDATA is set."""
        # Need to reimport to get patched values
        from utils import config
        # Force reload the module to pick up the mocked values
        import importlib
        importlib.reload(config)

        with patch.object(Path, 'mkdir'):
            result = config.get_app_data_dir()
            self.assertIn('EWExport', str(result))

    def test_unix_path_logic(self):
        """Test Unix/Mac path logic without actually creating PosixPath."""
        # We can't instantiate PosixPath on Windows, so test the logic indirectly
        # by checking that the code handles os.name == 'posix' correctly
        from utils import config
        import inspect
        source = inspect.getsource(config.get_app_data_dir)

        # Verify the function has proper cross-platform handling
        self.assertIn("os.name == 'nt'", source)
        self.assertIn(".ewexport", source)
        self.assertIn("Unix-like", source)


class TestVersionComparison(unittest.TestCase):
    """Test that version comparison uses semantic versioning correctly."""

    def test_semantic_version_comparison_basic(self):
        """Test basic semantic version comparison."""
        self.assertTrue(pkg_version.parse("1.0.0") < pkg_version.parse("1.1.0"))
        self.assertTrue(pkg_version.parse("1.1.0") < pkg_version.parse("1.2.0"))
        self.assertTrue(pkg_version.parse("1.2.0") < pkg_version.parse("2.0.0"))

    def test_semantic_version_comparison_double_digits(self):
        """Test version comparison with double-digit minor/patch versions."""
        # This is the critical test - string comparison would fail here
        self.assertTrue(pkg_version.parse("1.9.0") < pkg_version.parse("1.10.0"))
        self.assertTrue(pkg_version.parse("1.10.0") > pkg_version.parse("1.2.0"))
        self.assertTrue(pkg_version.parse("1.99.0") < pkg_version.parse("1.100.0"))

    def test_semantic_version_comparison_patch(self):
        """Test version comparison with patch versions."""
        self.assertTrue(pkg_version.parse("1.0.9") < pkg_version.parse("1.0.10"))
        self.assertTrue(pkg_version.parse("1.0.99") < pkg_version.parse("1.0.100"))

    def test_string_comparison_would_fail(self):
        """Demonstrate why string comparison fails for versions."""
        # String comparison is lexicographic - these are WRONG
        self.assertTrue("1.9.0" > "1.10.0")  # WRONG! Should be <
        self.assertTrue("1.10.0" < "1.2.0")  # WRONG! Should be >

        # But semantic version comparison is correct
        self.assertTrue(pkg_version.parse("1.9.0") < pkg_version.parse("1.10.0"))
        self.assertTrue(pkg_version.parse("1.10.0") > pkg_version.parse("1.2.0"))


class TestSearchHistory(unittest.TestCase):
    """Test search history persistence via ConfigManager."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.fake_home = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.fake_home, ignore_errors=True)

    def _make_config(self):
        with patch('utils.config.get_app_data_dir', return_value=Path(self.temp_dir)):
            return ConfigManager()

    def test_empty_when_no_file(self):
        config = self._make_config()
        with patch.object(Path, 'home', return_value=Path(self.fake_home)):
            self.assertEqual(config.get_search_history(), [])

    def test_round_trip(self):
        config = self._make_config()
        history = ['amazing', 'härlig', 'grace']
        self.assertTrue(config.save_search_history(history))
        self.assertEqual(config.get_search_history(), history)
        # Written to the app data dir, not the legacy location
        self.assertTrue((Path(self.temp_dir) / 'search_history.json').exists())

    def test_reads_legacy_location(self):
        """History saved by older versions in ~/.ewexport is still readable."""
        legacy_dir = Path(self.fake_home) / '.ewexport'
        legacy_dir.mkdir(parents=True)
        with open(legacy_dir / 'search_history.json', 'w', encoding='utf-8') as f:
            json.dump({'search_history': ['old search']}, f)

        config = self._make_config()
        with patch.object(Path, 'home', return_value=Path(self.fake_home)):
            self.assertEqual(config.get_search_history(), ['old search'])

    def test_new_location_wins_over_legacy(self):
        legacy_dir = Path(self.fake_home) / '.ewexport'
        legacy_dir.mkdir(parents=True)
        with open(legacy_dir / 'search_history.json', 'w', encoding='utf-8') as f:
            json.dump({'search_history': ['legacy']}, f)

        config = self._make_config()
        config.save_search_history(['current'])
        with patch.object(Path, 'home', return_value=Path(self.fake_home)):
            self.assertEqual(config.get_search_history(), ['current'])

    def test_corrupt_file_returns_empty(self):
        config = self._make_config()
        with open(Path(self.temp_dir) / 'search_history.json', 'w', encoding='utf-8') as f:
            f.write('not json{')
        with patch.object(Path, 'home', return_value=Path(self.fake_home)):
            self.assertEqual(config.get_search_history(), [])


class TestConfigMigration(unittest.TestCase):
    """Test configuration migration functionality."""

    def setUp(self):
        """Create temporary directory for test config files."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_get_app_data_dir = None

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_migrate_from_pre_1_1_0(self):
        """Test migration from version before 1.1.0."""
        with patch('utils.config.get_app_data_dir', return_value=Path(self.temp_dir)):
            config_manager = ConfigManager()

            old_settings = {
                "version": "1.0.0",
                "paths": {"last_easyworship_path": "/some/path"}
            }

            migrated = config_manager._migrate_settings(old_settings, "1.0.0")

            # Should have added export and duplicate_handling
            self.assertIn('export', migrated)
            self.assertIn('duplicate_handling', migrated)

    def test_migrate_from_1_0_5(self):
        """Test migration from version 1.0.5 (between 1.0.0 and 1.1.0)."""
        with patch('utils.config.get_app_data_dir', return_value=Path(self.temp_dir)):
            config_manager = ConfigManager()

            old_settings = {
                "version": "1.0.5",
                "paths": {"last_easyworship_path": "/some/path"}
            }

            migrated = config_manager._migrate_settings(old_settings, "1.0.5")

            # Should have added export and duplicate_handling (1.0.5 < 1.1.0)
            self.assertIn('export', migrated)
            self.assertIn('duplicate_handling', migrated)

    def test_migrate_from_1_9_0(self):
        """Test migration from version 1.9.0 (tests double-digit handling)."""
        with patch('utils.config.get_app_data_dir', return_value=Path(self.temp_dir)):
            config_manager = ConfigManager()

            old_settings = {
                "version": "1.9.0",
                "paths": {},
                "export": {"font": {}, "slides": {}},
                "duplicate_handling": {}
            }

            # 1.9.0 is > 1.1.0, so pre-1.1.0 migrations should NOT apply
            migrated = config_manager._migrate_settings(old_settings, "1.9.0")

            # Original settings should be preserved
            self.assertEqual(migrated.get('paths'), {})

    def test_migrate_handles_invalid_version(self):
        """Test migration handles invalid version strings gracefully."""
        with patch('utils.config.get_app_data_dir', return_value=Path(self.temp_dir)):
            config_manager = ConfigManager()

            old_settings = {
                "version": "invalid",
                "paths": {}
            }

            # Should not raise, should treat as very old version
            migrated = config_manager._migrate_settings(old_settings, "invalid")

            # Should apply all migrations since version is treated as 0.0.0
            self.assertIn('export', migrated)
            self.assertIn('duplicate_handling', migrated)

    def test_migrate_handles_none_version(self):
        """Test migration handles None version."""
        with patch('utils.config.get_app_data_dir', return_value=Path(self.temp_dir)):
            config_manager = ConfigManager()

            old_settings = {"paths": {}}

            migrated = config_manager._migrate_settings(old_settings, None)

            # Should apply all migrations
            self.assertIn('export', migrated)
            self.assertIn('duplicate_handling', migrated)

    def test_migrate_handles_empty_version(self):
        """Test migration handles empty string version."""
        with patch('utils.config.get_app_data_dir', return_value=Path(self.temp_dir)):
            config_manager = ConfigManager()

            old_settings = {"version": "", "paths": {}}

            migrated = config_manager._migrate_settings(old_settings, "")

            # Should apply all migrations
            self.assertIn('export', migrated)
            self.assertIn('duplicate_handling', migrated)


class TestSettingsWindowMigration(unittest.TestCase):
    """Test settings window migration functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_section_mappings_migration_semantic_version(self):
        """Test that section mappings migration uses semantic versioning."""
        # Import here to avoid GUI initialization issues
        with patch('utils.config.get_app_data_dir', return_value=Path(self.temp_dir)):
            # Create a mock settings window just to test migrate_config
            from gui.settings_window import SettingsWindow

            # We can't fully instantiate SettingsWindow without Tk, so test the logic directly
            # by checking that packaging.version is imported
            import gui.settings_window as sw
            self.assertTrue(hasattr(sw, 'pkg_version'))


class TestCrossplatformPaths(unittest.TestCase):
    """Test that all modules use centralized path handling."""

    def test_config_uses_centralized_function(self):
        """Test that ConfigManager uses get_app_data_dir."""
        import utils.config as config_module
        self.assertTrue(hasattr(config_module, 'get_app_data_dir'))

        # Check that ConfigManager calls get_app_data_dir
        source = open(config_module.__file__).read()
        self.assertIn('get_app_data_dir()', source)

    def test_main_uses_centralized_function(self):
        """Test that main.py uses get_app_data_dir."""
        main_path = Path(__file__).parent.parent / 'src' / 'main.py'
        source = open(main_path).read()
        self.assertIn('from src.utils.config import get_app_data_dir', source)
        self.assertIn('get_app_data_dir()', source)

    def test_section_detector_uses_centralized_function(self):
        """Test that section_detector uses get_app_data_dir."""
        detector_path = Path(__file__).parent.parent / 'src' / 'processing' / 'section_detector.py'
        source = open(detector_path).read()
        self.assertIn('get_app_data_dir', source)

    def test_settings_window_uses_centralized_function(self):
        """Test that settings_window uses get_app_data_dir."""
        window_path = Path(__file__).parent.parent / 'src' / 'gui' / 'settings_window.py'
        source = open(window_path).read()
        self.assertIn('from src.utils.config import get_app_data_dir', source)


class TestVersionInMain(unittest.TestCase):
    """Test that main.py uses centralized version."""

    def test_main_imports_version(self):
        """Test that main.py imports version from centralized module."""
        main_path = Path(__file__).parent.parent / 'src' / 'main.py'
        source = open(main_path).read()
        self.assertIn('from src.version import SECTION_MAPPINGS_SCHEMA_VERSION', source)
        self.assertIn('SECTION_MAPPINGS_SCHEMA_VERSION', source)

    def test_main_does_not_hardcode_version(self):
        """Test that main.py doesn't have hardcoded version strings."""
        main_path = Path(__file__).parent.parent / 'src' / 'main.py'
        source = open(main_path).read()
        # Should not contain hardcoded version like "1.2.4"
        self.assertNotIn('"1.2.4"', source)
        self.assertNotIn('"1.2.5"', source)


if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
