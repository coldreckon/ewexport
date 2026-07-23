"""
Centralized version information for EasyWorship to ProPresenter Converter

This module is the single source of truth for version information.
All other modules should import from here rather than defining their own version.
"""

# Application version - update this single location for new releases.
# Keep this numeric (MAJOR.MINOR.PATCH); pre-release builds are marked via
# PRERELEASE below so the numeric tuple stays valid for the Windows resource.
__version__ = "1.4.0"

# Pre-release suffix for beta/rc builds. Empty string ("") for stable releases.
# Examples: "beta.1" -> full version "1.4.0-beta.1" (GitHub release tag
# "v1.4.0-beta.1", marked as a pre-release). Bump for each beta (beta.2, rc.1...).
PRERELEASE = "beta.1"

# Schema versions for configuration files
SETTINGS_SCHEMA_VERSION = "1.2.0"
SECTION_MAPPINGS_SCHEMA_VERSION = "1.2.0"

# Release information
RELEASE_DATE = "June 2026"
RELEASE_YEAR = "2026"

def get_version() -> str:
    """Get the current numeric application version string (e.g. '1.4.0')"""
    return __version__

def get_full_version() -> str:
    """Get the full version including any pre-release suffix.

    Returns e.g. '1.4.0-beta.1' for a pre-release, or '1.4.0' for a stable
    release. Use this for display and release tagging; use __version__ where
    a strictly numeric version is required (e.g. the Windows version resource).
    """
    return f"{__version__}-{PRERELEASE}" if PRERELEASE else __version__

def is_prerelease() -> bool:
    """True when this build is a pre-release (beta/rc)"""
    return bool(PRERELEASE)

def get_release_tag() -> str:
    """Get the git/GitHub release tag for this version (e.g. 'v1.4.0-beta.1')"""
    return f"v{get_full_version()}"

def get_version_tuple() -> tuple:
    """Get the version as a tuple of integers (major, minor, patch)"""
    parts = __version__.split('.')
    return tuple(int(p) for p in parts)

def get_version_for_windows() -> str:
    """Get version string formatted for Windows (x.x.x.0)"""
    return f"{__version__}.0"
