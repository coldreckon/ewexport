"""
Centralized version information for EasyWorship to ProPresenter Converter

This module is the single source of truth for version information.
All other modules should import from here rather than defining their own version.
"""

# Application version - update this single location for new releases
__version__ = "1.4.0"

# Schema versions for configuration files
SETTINGS_SCHEMA_VERSION = "1.2.0"
SECTION_MAPPINGS_SCHEMA_VERSION = "1.2.0"

# Release information
RELEASE_DATE = "June 2026"
RELEASE_YEAR = "2026"

def get_version() -> str:
    """Get the current application version string"""
    return __version__

def get_version_tuple() -> tuple:
    """Get the version as a tuple of integers (major, minor, patch)"""
    parts = __version__.split('.')
    return tuple(int(p) for p in parts)

def get_version_for_windows() -> str:
    """Get version string formatted for Windows (x.x.x.0)"""
    return f"{__version__}.0"
