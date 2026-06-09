"""
Section-name mapping configuration (single source of truth).

The mappings file lives in the app data directory and translates
Swedish/English section labels (e.g. "vers 1") to the English names
ProPresenter expects ("Verse 1"). The GUI settings window and the
section detector both read it through this module.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

from packaging import version as pkg_version

from src.version import SECTION_MAPPINGS_SCHEMA_VERSION
from src.utils.config import get_app_data_dir

logger = logging.getLogger(__name__)

DEFAULT_SECTION_MAPPINGS: Dict[str, str] = {
    # Swedish source labels
    "vers": "Verse",
    "refräng": "Chorus",
    "brygga": "Bridge",
    "förrefräng": "Pre-Chorus",
    "slut": "Outro",
    # English source labels
    "verse": "Verse",
    "chorus": "Chorus",
    "bridge": "Bridge",
    "pre-chorus": "Pre-Chorus",
    "prechorus": "Pre-Chorus",
    "intro": "Intro",
    "outro": "Outro",
    "tag": "Tag",
    "ending": "Ending",
}

DEFAULT_NUMBER_RULES: Dict[str, Any] = {
    "preserve_numbers": True,
    "start_from_one": True,
    "format": "{section_name} {number}",
}


def get_default_config() -> Dict[str, Any]:
    """Full default content of section_mappings.json"""
    return {
        "version": SECTION_MAPPINGS_SCHEMA_VERSION,
        "section_mappings": dict(DEFAULT_SECTION_MAPPINGS),
        "number_mapping_rules": dict(DEFAULT_NUMBER_RULES),
        "gui_settings": {
            "editable_via_gui": True,
            "description": "Section name mappings from Swedish/English to English for ProPresenter export"
        },
        "notes": [
            "This file maps Swedish and English section names to English equivalents",
            "Numbers are preserved: 'vers 1' becomes 'Verse 1'",
            "Case-insensitive matching is applied",
            "These mappings can be edited from Edit -> Section Mappings in the GUI"
        ],
    }


def get_mappings_file() -> Path:
    """Path to section_mappings.json in the app data directory"""
    return get_app_data_dir() / "section_mappings.json"


def ensure_mappings_file() -> Path:
    """Create the mappings file with defaults if it does not exist"""
    mappings_file = get_mappings_file()
    if not mappings_file.exists():
        with open(mappings_file, 'w', encoding='utf-8') as f:
            json.dump(get_default_config(), f, indent=2, ensure_ascii=False)
        logger.info(f"Created default section mappings at {mappings_file}")
    return mappings_file


def migrate_config(data: Dict[str, Any], from_version: str) -> Dict[str, Any]:
    """Migrate a mappings config from an older schema version.

    Uses semantic version comparison to handle all version ranges properly.
    """
    try:
        current_ver = pkg_version.parse(from_version) if from_version else pkg_version.parse("0.0.0")
    except Exception:
        logger.warning(f"Could not parse version '{from_version}', treating as 0.0.0")
        current_ver = pkg_version.parse("0.0.0")

    # Migration from pre-1.1.0 to 1.1.0: Add version field if missing
    if current_ver < pkg_version.parse("1.1.0"):
        logger.info("Applying section mappings migration: pre-1.1.0 -> 1.1.0")
        data["version"] = SECTION_MAPPINGS_SCHEMA_VERSION
        if "notes" not in data:
            data["notes"] = get_default_config()["notes"]

    # Migration from pre-1.2.0 to 1.2.0
    if current_ver < pkg_version.parse("1.2.0"):
        logger.info("Applying section mappings migration: pre-1.2.0 -> 1.2.0")
        data["version"] = SECTION_MAPPINGS_SCHEMA_VERSION

    # Future migrations would follow the same pattern:
    # if current_ver < pkg_version.parse("1.3.0"):
    #     # Migrate from pre-1.3.0 to 1.3.0

    return data


def load_config() -> Dict[str, Any]:
    """Load the full mappings config, migrating and rewriting if needed"""
    mappings_file = ensure_mappings_file()
    with open(mappings_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    file_version = data.get('version', '1.0.0')
    if file_version != SECTION_MAPPINGS_SCHEMA_VERSION:
        data = migrate_config(data, file_version)
        with open(mappings_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    return data


def load_mappings() -> Dict[str, str]:
    """Load just the section mappings, with lowercase keys"""
    data = load_config()
    return {k.lower(): v for k, v in data.get('section_mappings', {}).items()}


def save_mappings(mappings: Dict[str, str]) -> None:
    """Save section mappings, preserving other fields in the config file"""
    mappings_file = get_mappings_file()
    data: Dict[str, Any] = {}
    if mappings_file.exists():
        try:
            with open(mappings_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Could not read existing mappings file, rewriting: {e}")

    data['version'] = SECTION_MAPPINGS_SCHEMA_VERSION
    data['section_mappings'] = dict(mappings)
    data.setdefault('number_mapping_rules', dict(DEFAULT_NUMBER_RULES))
    data.setdefault('gui_settings', get_default_config()['gui_settings'])

    with open(mappings_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
