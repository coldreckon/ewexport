"""
Configuration management with version handling and persistence
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import logging
from datetime import datetime
from src.version import SETTINGS_SCHEMA_VERSION
from packaging import version as pkg_version

logger = logging.getLogger(__name__)


def get_app_data_dir() -> Path:
    """
    Get the application data directory for settings storage.

    This is the centralized function for determining where app data should be stored.
    All modules should use this function instead of implementing their own path logic.

    Returns:
        Path to the application data directory:
        - Windows: %APPDATA%/EWExport
        - macOS/Linux: ~/.ewexport
    """
    if os.name == 'nt':  # Windows
        app_data = os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming')
        app_dir = Path(app_data) / 'EWExport'
    else:  # Unix-like (macOS, Linux)
        app_dir = Path.home() / '.ewexport'

    # Create directory if it doesn't exist
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir

class ConfigManager:
    """Manages application settings with version tracking and migration support"""

    CURRENT_VERSION = SETTINGS_SCHEMA_VERSION  # Imported from centralized version module

    def __init__(self):
        """Initialize configuration manager"""
        # Determine config location using centralized function
        self.app_data_dir = get_app_data_dir()
        self.settings_file = self.app_data_dir / "settings.json"
        self.section_mappings_file = self.app_data_dir / "section_mappings.json"
        
        # Default settings structure
        self.default_settings = self._get_default_settings()
        
        # Current settings
        self.settings = {}
        
        # Load settings on init
        self.load_settings()
    
    def _get_app_data_dir(self) -> Path:
        """Get application data directory for settings storage.

        Deprecated: Use the module-level get_app_data_dir() function instead.
        This method is kept for backward compatibility.
        """
        return get_app_data_dir()

    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default settings structure"""
        return {
            "version": self.CURRENT_VERSION,
            "app": {
                "last_update_check": None,
                "theme": "default",
                "language": "en",
                "first_run": True
            },
            "paths": {
                "last_easyworship_path": None,
                "last_export_path": None,
                "recent_databases": [],  # List of recently used database paths
                "max_recent": 5
            },
            "window": {
                "main": {
                    "geometry": "1024x768",
                    "position": None,  # Will be "x,y" string
                    "maximized": False
                },
                "settings": {
                    "geometry": "800x600",
                    "position": None
                }
            },
            "export": {
                "output_directory": None,  # User's selected output directory
                "include_ccli_in_filename": False,
                "include_author_in_filename": False,
                "duplicate_handling_action": "ask",  # ask, skip, overwrite, rename
                "export_format": "propresenter6",  # or "propresenter7" in future
                "formatting_enabled": False,  # Master control for custom formatting
                "change_font": False,  # Whether to override font
                "font": {
                    "family": "Arial",
                    "size": 72,
                    "color": "#FFFFFF"
                },
                "slides": {
                    "add_intro_slide": False,
                    "intro_slide_text": "",
                    "intro_slide_group": "Intro",
                    "add_blank_slide": False,
                    "blank_slide_group": "Blank",
                    "max_lines_per_slide": 4,
                    "auto_break_long_lines": True
                }
            },
            "song_list": {
                "column_widths": {
                    "title": 300,
                    "author": 200,
                    "copyright": 200,
                    "ccli": 100,
                    "tags": 150
                },
                "sort_column": "title",
                "sort_ascending": True,
                "show_preview": True,
                "auto_select_all": False
            },
            "duplicate_handling": {
                "default_action": "ask",  # "ask", "skip", "overwrite", "rename"
                "rename_pattern": "{name}_{number}",
                "remember_choice": False
            },
            "logging": {
                "enabled": True,
                "level": "INFO",
                "max_file_size_mb": 10,
                "max_backup_count": 5
            },
            "performance": {
                "batch_size": 50,
                "enable_threading": True,
                "max_workers": 4
            }
        }
    
    def load_settings(self) -> Dict[str, Any]:
        """Load settings from file, handling version migration if needed"""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                
                # Check version and migrate if needed
                file_version = loaded_settings.get('version', '1.0.0')
                if file_version != self.CURRENT_VERSION:
                    logger.info(f"Migrating settings from version {file_version} to {self.CURRENT_VERSION}")
                    loaded_settings = self._migrate_settings(loaded_settings, file_version)
                
                # Merge with defaults to ensure all keys exist
                self.settings = self._deep_merge(self.default_settings.copy(), loaded_settings)
            else:
                # First run - use defaults
                self.settings = self.default_settings.copy()
                self.save_settings()  # Save initial settings
                
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            # Fall back to defaults
            self.settings = self.default_settings.copy()
        
        return self.settings
    
    def save_settings(self) -> bool:
        """Save current settings to file"""
        try:
            # Ensure directory exists
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Update version
            self.settings['version'] = self.CURRENT_VERSION
            
            # Save with pretty formatting
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Settings saved to {self.settings_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False
    
    def _migrate_settings(self, old_settings: Dict[str, Any], from_version: str) -> Dict[str, Any]:
        """Migrate settings from an older version to current version.

        Uses semantic version comparison to handle all version ranges properly.
        Migrations are applied incrementally from older to newer versions.
        """
        migrated = old_settings.copy()

        try:
            current_ver = pkg_version.parse(from_version) if from_version else pkg_version.parse("0.0.0")
        except Exception:
            # If version parsing fails, assume very old version
            logger.warning(f"Could not parse version '{from_version}', treating as 0.0.0")
            current_ver = pkg_version.parse("0.0.0")

        # Migration from pre-1.1.0 to 1.1.0
        if current_ver < pkg_version.parse("1.1.0"):
            logger.info(f"Applying migration: pre-1.1.0 -> 1.1.0")
            # Add new export options if they don't exist
            if 'export' not in migrated:
                migrated['export'] = self.default_settings['export'].copy()
            else:
                # Add font settings if missing
                if 'font' not in migrated['export']:
                    migrated['export']['font'] = self.default_settings['export']['font'].copy()

                # Add slide settings if missing
                if 'slides' not in migrated['export']:
                    migrated['export']['slides'] = self.default_settings['export']['slides'].copy()

            # Add duplicate handling if missing
            if 'duplicate_handling' not in migrated:
                migrated['duplicate_handling'] = self.default_settings['duplicate_handling'].copy()

        # Migration from pre-1.2.0 to 1.2.0
        if current_ver < pkg_version.parse("1.2.0"):
            logger.info(f"Applying migration: pre-1.2.0 -> 1.2.0")
            # Add any 1.2.0 specific migrations here
            # Currently no additional migrations needed
            pass

        # Future migrations would follow the same pattern:
        # if current_ver < pkg_version.parse("1.3.0"):
        #     logger.info(f"Applying migration: pre-1.3.0 -> 1.3.0")
        #     # Add 1.3.0 specific migrations

        return migrated
    
    def _deep_merge(self, base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries, with overlay values taking precedence"""
        result = base.copy()
        
        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Get a setting value using dot notation (e.g., 'export.font.size')"""
        keys = key_path.split('.')
        value = self.settings
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any, save: bool = True) -> bool:
        """Set a setting value using dot notation"""
        keys = key_path.split('.')
        target = self.settings
        
        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        
        # Set the value
        target[keys[-1]] = value
        
        # Optionally save immediately
        if save:
            return self.save_settings()
        
        return True
    
    def get_recent_databases(self) -> list:
        """Get list of recently used database paths"""
        return self.get('paths.recent_databases', [])
    
    def add_recent_database(self, path: str):
        """Add a database path to recent list"""
        recent = self.get_recent_databases()
        
        # Remove if already exists
        if path in recent:
            recent.remove(path)
        
        # Add to front
        recent.insert(0, path)
        
        # Limit to max_recent
        max_recent = self.get('paths.max_recent', 5)
        recent = recent[:max_recent]
        
        self.set('paths.recent_databases', recent)
    
    def get_window_geometry(self, window_name: str = 'main') -> Optional[Tuple[str, str, bool]]:
        """Get window geometry settings"""
        geometry = self.get(f'window.{window_name}.geometry')
        position = self.get(f'window.{window_name}.position')
        maximized = self.get(f'window.{window_name}.maximized', False)
        
        return (geometry, position, maximized) if geometry else None
    
    def save_window_geometry(self, window_name: str, geometry: str, 
                           position: str = None, maximized: bool = False):
        """Save window geometry settings"""
        self.set(f'window.{window_name}.geometry', geometry, save=False)
        self.set(f'window.{window_name}.position', position, save=False)
        self.set(f'window.{window_name}.maximized', maximized, save=False)
        self.save_settings()
    
    def get_export_directory(self) -> Optional[Path]:
        """Get the configured export directory"""
        path = self.get('export.output_directory')
        if path:
            return Path(path)
        return None
    
    def set_export_directory(self, path: Path):
        """Set the export directory"""
        self.set('export.output_directory', str(path))
    
    def get_search_history(self) -> list:
        """Load saved search history (most recent last).

        Falls back to the legacy ~/.ewexport location once, so history
        written by older versions is migrated to the app data directory
        on the next save.
        """
        history_file = self.app_data_dir / 'search_history.json'
        if not history_file.exists():
            legacy_file = Path.home() / '.ewexport' / 'search_history.json'
            if legacy_file == history_file or not legacy_file.exists():
                return []
            history_file = legacy_file

        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return list(data.get('search_history', []))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load search history from {history_file}: {e}")
            return []

    def save_search_history(self, history: list) -> bool:
        """Save search history to the app data directory"""
        history_file = self.app_data_dir / 'search_history.json'
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump({'search_history': list(history)}, f, indent=2, ensure_ascii=False)
            return True
        except OSError as e:
            logger.warning(f"Could not save search history: {e}")
            return False

    def get_column_widths(self) -> Dict[str, int]:
        """Get song list column widths"""
        return self.get('song_list.column_widths', {})
    
    def save_column_widths(self, widths: Dict[str, int]):
        """Save song list column widths"""
        self.set('song_list.column_widths', widths)
    
    def is_first_run(self) -> bool:
        """Check if this is the first run of the application"""
        return self.get('app.first_run', True)
    
    def mark_first_run_complete(self):
        """Mark that first run has been completed"""
        self.set('app.first_run', False)
    
    def get_duplicate_action(self) -> str:
        """Get default duplicate file handling action"""
        return self.get('duplicate_handling.default_action', 'ask')
    
    def set_duplicate_action(self, action: str, remember: bool = False):
        """Set duplicate file handling action"""
        self.set('duplicate_handling.default_action', action, save=False)
        self.set('duplicate_handling.remember_choice', remember, save=True)
    
    def reset_to_defaults(self, section: str = None):
        """Reset settings to defaults, optionally for a specific section"""
        if section:
            if section in self.default_settings:
                self.settings[section] = self.default_settings[section].copy()
        else:
            self.settings = self.default_settings.copy()
        
        self.save_settings()
    
    def export_settings(self, file_path: Path) -> bool:
        """Export settings to a file"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Error exporting settings: {e}")
            return False
    
    def import_settings(self, file_path: Path) -> bool:
        """Import settings from a file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported = json.load(f)
            
            # Validate and migrate if needed
            file_version = imported.get('version', '1.0.0')
            if file_version != self.CURRENT_VERSION:
                imported = self._migrate_settings(imported, file_version)
            
            # Merge with defaults
            self.settings = self._deep_merge(self.default_settings.copy(), imported)
            return self.save_settings()
            
        except Exception as e:
            logger.error(f"Error importing settings: {e}")
            return False


# Global instance
_config_manager = None

def get_config() -> ConfigManager:
    """Get the global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager