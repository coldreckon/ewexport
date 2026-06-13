"""
Tests for version module.

Tests that version information is properly centralized and accessible.
"""

import unittest
import sys
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from version import (
    __version__,
    PRERELEASE,
    SETTINGS_SCHEMA_VERSION,
    SECTION_MAPPINGS_SCHEMA_VERSION,
    RELEASE_DATE,
    RELEASE_YEAR,
    get_version,
    get_full_version,
    is_prerelease,
    get_release_tag,
    get_version_tuple,
    get_version_for_windows
)
from packaging import version as pkg_version


class TestVersionModule(unittest.TestCase):
    """Test version module functionality."""

    def test_version_string_format(self):
        """Test that version string is in correct format (x.y.z)."""
        parts = __version__.split('.')
        self.assertEqual(len(parts), 3, f"Version should have 3 parts: {__version__}")

        # All parts should be numeric
        for part in parts:
            self.assertTrue(part.isdigit(), f"Version part should be numeric: {part}")

    def test_get_version_returns_same_as_dunder(self):
        """Test that get_version() returns the same as __version__."""
        self.assertEqual(get_version(), __version__)

    def test_get_version_tuple_format(self):
        """Test that get_version_tuple returns correct tuple format."""
        version_tuple = get_version_tuple()

        self.assertIsInstance(version_tuple, tuple)
        self.assertEqual(len(version_tuple), 3)

        for part in version_tuple:
            self.assertIsInstance(part, int)

    def test_get_version_tuple_matches_string(self):
        """Test that version tuple matches the string version."""
        version_tuple = get_version_tuple()
        expected = tuple(int(p) for p in __version__.split('.'))

        self.assertEqual(version_tuple, expected)

    def test_get_version_for_windows(self):
        """Test Windows version format (x.x.x.0)."""
        windows_version = get_version_for_windows()

        self.assertTrue(windows_version.endswith('.0'))
        self.assertEqual(windows_version, f"{__version__}.0")

    def test_full_version_matches_prerelease_state(self):
        """Full version includes the pre-release suffix only when set."""
        if PRERELEASE:
            self.assertEqual(get_full_version(), f"{__version__}-{PRERELEASE}")
            self.assertTrue(is_prerelease())
        else:
            self.assertEqual(get_full_version(), __version__)
            self.assertFalse(is_prerelease())

    def test_release_tag_format(self):
        """Release tag is 'v' + full version."""
        self.assertEqual(get_release_tag(), f"v{get_full_version()}")
        self.assertTrue(get_release_tag().startswith('v'))

    def test_full_version_is_pep440_parseable(self):
        """Full version must parse so the update checker can compare it."""
        parsed = pkg_version.parse(get_full_version())
        self.assertEqual(parsed.is_prerelease, is_prerelease())
        # A pre-release must sort below the corresponding stable release
        if is_prerelease():
            self.assertLess(parsed, pkg_version.parse(__version__))

    def test_schema_versions_format(self):
        """Test that schema versions are valid version strings."""
        for schema_version in [SETTINGS_SCHEMA_VERSION, SECTION_MAPPINGS_SCHEMA_VERSION]:
            parts = schema_version.split('.')
            self.assertGreaterEqual(len(parts), 2, f"Schema version should have at least 2 parts: {schema_version}")

    def test_release_year_format(self):
        """Test that release year is a 4-digit string."""
        self.assertEqual(len(RELEASE_YEAR), 4)
        self.assertTrue(RELEASE_YEAR.isdigit())
        self.assertTrue(int(RELEASE_YEAR) >= 2024)

    def test_release_date_not_empty(self):
        """Test that release date is not empty."""
        self.assertTrue(len(RELEASE_DATE) > 0)


class TestVersionConsistency(unittest.TestCase):
    """Test version consistency across modules."""

    def test_update_checker_uses_centralized_version(self):
        """Test that UpdateChecker uses the centralized version."""
        from utils.update_checker import UpdateChecker

        checker = UpdateChecker()
        self.assertEqual(checker.CURRENT_VERSION, __version__)
        self.assertEqual(checker.get_current_version(), __version__)

    def test_config_manager_uses_centralized_schema_version(self):
        """Test that ConfigManager uses centralized schema version."""
        from utils.config import ConfigManager

        self.assertEqual(ConfigManager.CURRENT_VERSION, SETTINGS_SCHEMA_VERSION)


if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.DEBUG)

    unittest.main()
