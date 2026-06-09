"""
Tests for the shared section-mappings configuration module.
"""

import unittest
import sys
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from src.utils import section_mappings
from src.version import SECTION_MAPPINGS_SCHEMA_VERSION


class TestSectionMappings(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.patcher = patch('src.utils.section_mappings.get_app_data_dir',
                             return_value=Path(self.temp_dir))
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ensure_creates_default_file(self):
        mappings_file = section_mappings.ensure_mappings_file()
        self.assertTrue(mappings_file.exists())
        with open(mappings_file, encoding='utf-8') as f:
            data = json.load(f)
        self.assertEqual(data['version'], SECTION_MAPPINGS_SCHEMA_VERSION)
        self.assertEqual(data['section_mappings']['refräng'], 'Chorus')

    def test_ensure_does_not_overwrite_existing(self):
        mappings_file = Path(self.temp_dir) / 'section_mappings.json'
        custom = {'version': SECTION_MAPPINGS_SCHEMA_VERSION,
                  'section_mappings': {'custom': 'Custom'}}
        with open(mappings_file, 'w', encoding='utf-8') as f:
            json.dump(custom, f)

        section_mappings.ensure_mappings_file()
        self.assertEqual(section_mappings.load_mappings(), {'custom': 'Custom'})

    def test_load_creates_defaults_when_missing(self):
        mappings = section_mappings.load_mappings()
        self.assertEqual(mappings['vers'], 'Verse')
        self.assertEqual(mappings['slut'], 'Outro')

    def test_load_lowercases_keys(self):
        mappings_file = Path(self.temp_dir) / 'section_mappings.json'
        with open(mappings_file, 'w', encoding='utf-8') as f:
            json.dump({'version': SECTION_MAPPINGS_SCHEMA_VERSION,
                       'section_mappings': {'VERS': 'Verse'}}, f)
        self.assertEqual(section_mappings.load_mappings(), {'vers': 'Verse'})

    def test_old_version_migrated_and_rewritten(self):
        mappings_file = Path(self.temp_dir) / 'section_mappings.json'
        with open(mappings_file, 'w', encoding='utf-8') as f:
            json.dump({'version': '1.0.0',
                       'section_mappings': {'vers': 'Verse'}}, f)

        section_mappings.load_mappings()

        with open(mappings_file, encoding='utf-8') as f:
            data = json.load(f)
        self.assertEqual(data['version'], SECTION_MAPPINGS_SCHEMA_VERSION)
        self.assertIn('notes', data)

    def test_save_round_trip(self):
        section_mappings.save_mappings({'vers': 'Verse', 'extra': 'Extra'})
        self.assertEqual(section_mappings.load_mappings(),
                         {'vers': 'Verse', 'extra': 'Extra'})

    def test_save_preserves_other_fields(self):
        section_mappings.ensure_mappings_file()
        section_mappings.save_mappings({'only': 'One'})
        with open(Path(self.temp_dir) / 'section_mappings.json', encoding='utf-8') as f:
            data = json.load(f)
        self.assertIn('number_mapping_rules', data)
        self.assertIn('gui_settings', data)
        self.assertEqual(data['section_mappings'], {'only': 'One'})

    def test_migrate_unparseable_version(self):
        data = section_mappings.migrate_config({'section_mappings': {}}, 'garbage')
        self.assertEqual(data['version'], SECTION_MAPPINGS_SCHEMA_VERSION)


if __name__ == '__main__':
    unittest.main()
