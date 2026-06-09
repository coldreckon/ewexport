"""
Tests for ProPresenter 6 export functionality.

Covers filename sanitization/generation, slide splitting, single-song XML
export, and batch export with duplicate handling. These tests pin the
exporter's external behavior before refactoring and GUI changes.
"""

import unittest
import sys
import base64
import tempfile
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from export.propresenter import ProPresenter6Exporter


class ConfigStub:
    """Minimal dict-backed stand-in for ConfigManager (dot-key get)."""

    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)


def make_song(**overrides):
    song = {
        'rowid': 1,
        'title': 'Amazing Grace',
        'author': 'John Newton',
        'copyright': 'Public Domain',
        'administrator': '',
        'reference_number': '22025',
    }
    song.update(overrides)
    return song


def make_sections():
    return [
        {'type': 'Verse 1', 'content': 'Amazing grace how sweet the sound\nThat saved a wretch like me'},
        {'type': 'Chorus', 'content': 'Praise God\nPraise God'},
    ]


class TestSanitizeFilename(unittest.TestCase):

    def setUp(self):
        self.exporter = ProPresenter6Exporter()

    def test_removes_control_characters(self):
        self.assertEqual(self.exporter.sanitize_filename('Song\nTitle\twith\rcontrols'),
                         'SongTitlewithcontrols')

    def test_replaces_invalid_windows_characters(self):
        self.assertEqual(self.exporter.sanitize_filename('A<B>C:D"E/F\\G|H?I*J'),
                         'A_B_C_D_E_F_G_H_I_J')

    def test_strips_leading_trailing_spaces_and_dots(self):
        self.assertEqual(self.exporter.sanitize_filename('  .Song Title.  '), 'Song Title')

    def test_collapses_multiple_spaces(self):
        self.assertEqual(self.exporter.sanitize_filename('Song    Title'), 'Song Title')

    def test_limits_length_to_200(self):
        result = self.exporter.sanitize_filename('x' * 300)
        self.assertLessEqual(len(result), 200)

    def test_empty_becomes_untitled(self):
        self.assertEqual(self.exporter.sanitize_filename(''), 'Untitled_Song')
        self.assertEqual(self.exporter.sanitize_filename('...'), 'Untitled_Song')

    def test_swedish_characters_preserved(self):
        self.assertEqual(self.exporter.sanitize_filename('Härlig är jorden'), 'Härlig är jorden')


class TestGenerateFilename(unittest.TestCase):

    def test_plain_title(self):
        exporter = ProPresenter6Exporter(config=ConfigStub())
        self.assertEqual(exporter._generate_filename(make_song()), 'Amazing Grace.pro6')

    def test_includes_ccli_when_configured(self):
        exporter = ProPresenter6Exporter(config=ConfigStub({
            'export.include_ccli_in_filename': True,
        }))
        self.assertEqual(exporter._generate_filename(make_song()), 'Amazing Grace_22025.pro6')

    def test_includes_author_when_configured(self):
        exporter = ProPresenter6Exporter(config=ConfigStub({
            'export.include_author_in_filename': True,
        }))
        self.assertEqual(exporter._generate_filename(make_song()), 'Amazing Grace_John Newton.pro6')

    def test_missing_ccli_not_appended(self):
        exporter = ProPresenter6Exporter(config=ConfigStub({
            'export.include_ccli_in_filename': True,
        }))
        song = make_song(reference_number='')
        self.assertEqual(exporter._generate_filename(song), 'Amazing Grace.pro6')


class TestSplitContentIntoSlides(unittest.TestCase):

    def test_splits_on_blank_lines(self):
        exporter = ProPresenter6Exporter()
        slides = exporter.split_content_into_slides('line1\nline2\n\nline3\nline4')
        self.assertEqual(slides, ['line1\nline2', 'line3\nline4'])

    def test_auto_breaks_long_sections(self):
        exporter = ProPresenter6Exporter(config=ConfigStub({
            'export.formatting_enabled': True,
            'export.slides.max_lines_per_slide': 2,
            'export.slides.auto_break_long_lines': True,
        }))
        slides = exporter.split_content_into_slides('a\nb\nc\nd\ne')
        self.assertEqual(slides, ['a\nb', 'c\nd', 'e'])

    def test_no_auto_break_keeps_section_whole(self):
        exporter = ProPresenter6Exporter(config=ConfigStub({
            'export.formatting_enabled': True,
            'export.slides.max_lines_per_slide': 2,
            'export.slides.auto_break_long_lines': False,
        }))
        slides = exporter.split_content_into_slides('a\nb\nc\nd\ne')
        self.assertEqual(slides, ['a\nb\nc\nd\ne'])

    def test_single_block_without_blank_lines(self):
        exporter = ProPresenter6Exporter()
        slides = exporter.split_content_into_slides('a\nb')
        self.assertEqual(slides, ['a\nb'])


class TestExportSong(unittest.TestCase):

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.exporter = ProPresenter6Exporter(config=ConfigStub())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_creates_valid_pro6_file(self):
        success, result = self.exporter.export_song(make_song(), make_sections(), self.temp_dir)
        self.assertTrue(success, result)

        file_path = self.temp_dir / 'Amazing Grace.pro6'
        self.assertTrue(file_path.exists())

        tree = ET.parse(file_path)
        root = tree.getroot()
        self.assertEqual(root.tag, 'RVPresentationDocument')
        self.assertEqual(root.get('versionNumber'), '600')
        self.assertEqual(root.get('CCLISongTitle'), 'Amazing Grace')
        self.assertEqual(root.get('CCLIAuthor'), 'John Newton')
        self.assertEqual(root.get('CCLISongNumber'), '22025')

    def test_group_count_matches_sections(self):
        self.exporter.export_song(make_song(), make_sections(), self.temp_dir)
        root = ET.parse(self.temp_dir / 'Amazing Grace.pro6').getroot()
        groups = root.findall(".//array[@rvXMLIvarName='groups']/RVSlideGrouping")
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0].get('name'), 'Verse 1')
        self.assertEqual(groups[1].get('name'), 'Chorus')

    def test_plain_text_round_trips_with_crlf(self):
        self.exporter.export_song(make_song(), make_sections(), self.temp_dir)
        root = ET.parse(self.temp_dir / 'Amazing Grace.pro6').getroot()
        first_group = root.find(".//array[@rvXMLIvarName='groups']/RVSlideGrouping")
        plain = first_group.find(".//NSString[@rvXMLIvarName='PlainText']")
        decoded = base64.b64decode(plain.text).decode('utf-8')
        self.assertEqual(decoded,
                         'Amazing grace how sweet the sound\r\nThat saved a wretch like me')

    def test_no_self_closing_array_tags(self):
        self.exporter.export_song(make_song(), make_sections(), self.temp_dir)
        raw = (self.temp_dir / 'Amazing Grace.pro6').read_text(encoding='utf-8')
        self.assertNotRegex(raw, r'<array[^>]*/>')

    def test_song_without_content_fails(self):
        success, message = self.exporter.export_song(
            make_song(), [{'type': 'Verse 1', 'content': '   '}], self.temp_dir)
        self.assertFalse(success)
        self.assertIn('no lyrics', message)
        self.assertFalse(list(self.temp_dir.glob('*.pro6')))

    def test_empty_sections_skipped_in_groups(self):
        sections = make_sections() + [{'type': 'Bridge', 'content': ''}]
        self.exporter.export_song(make_song(), sections, self.temp_dir)
        root = ET.parse(self.temp_dir / 'Amazing Grace.pro6').getroot()
        groups = root.findall(".//array[@rvXMLIvarName='groups']/RVSlideGrouping")
        self.assertEqual(len(groups), 2)

    def test_intro_and_blank_slides_added_when_configured(self):
        exporter = ProPresenter6Exporter(config=ConfigStub({
            'export.slides.add_intro_slide': True,
            'export.slides.intro_slide_text': '',
            'export.slides.intro_slide_group': 'Intro',
            'export.slides.add_blank_slide': True,
            'export.slides.blank_slide_group': 'Blank',
        }))
        exporter.export_song(make_song(), make_sections(), self.temp_dir)
        root = ET.parse(self.temp_dir / 'Amazing Grace.pro6').getroot()
        groups = root.findall(".//array[@rvXMLIvarName='groups']/RVSlideGrouping")
        names = [g.get('name') for g in groups]
        self.assertEqual(names, ['Intro', 'Verse 1', 'Chorus', 'Blank'])


class TestExportSongsBatch(unittest.TestCase):

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _batch(self):
        return [
            (make_song(rowid=1, title='Song One'), make_sections()),
            (make_song(rowid=2, title='Song Two'), make_sections()),
        ]

    def test_happy_path(self):
        exporter = ProPresenter6Exporter(config=ConfigStub())
        successful, failed, skipped = exporter.export_songs_batch(self._batch(), self.temp_dir)
        self.assertEqual(len(successful), 2)
        self.assertEqual(failed, [])
        self.assertEqual(skipped, [])
        self.assertTrue((self.temp_dir / 'Song One.pro6').exists())
        self.assertTrue((self.temp_dir / 'Song Two.pro6').exists())

    def test_progress_callback_invoked(self):
        exporter = ProPresenter6Exporter(config=ConfigStub())
        calls = []
        exporter.export_songs_batch(
            self._batch(), self.temp_dir,
            progress_callback=lambda cur, total, title: calls.append((cur, total, title)))
        self.assertEqual(calls[0], (0, 2, 'Song One'))
        self.assertEqual(calls[-1], (2, 2, 'Export complete'))

    def test_duplicate_skip(self):
        (self.temp_dir / 'Song One.pro6').write_text('existing', encoding='utf-8')
        exporter = ProPresenter6Exporter(config=ConfigStub({
            'export.duplicate_handling_action': 'skip',
        }))
        successful, failed, skipped = exporter.export_songs_batch(self._batch(), self.temp_dir)
        self.assertEqual(skipped, ['Song One'])
        self.assertEqual(len(successful), 1)
        # Existing file untouched
        self.assertEqual((self.temp_dir / 'Song One.pro6').read_text(encoding='utf-8'), 'existing')

    def test_duplicate_overwrite(self):
        (self.temp_dir / 'Song One.pro6').write_text('existing', encoding='utf-8')
        exporter = ProPresenter6Exporter(config=ConfigStub({
            'export.duplicate_handling_action': 'overwrite',
        }))
        successful, failed, skipped = exporter.export_songs_batch(self._batch(), self.temp_dir)
        self.assertEqual(len(successful), 2)
        self.assertEqual(skipped, [])
        content = (self.temp_dir / 'Song One.pro6').read_text(encoding='utf-8')
        self.assertIn('RVPresentationDocument', content)

    def test_duplicate_auto_rename(self):
        (self.temp_dir / 'Song One.pro6').write_text('existing', encoding='utf-8')
        exporter = ProPresenter6Exporter(config=ConfigStub({
            'export.duplicate_handling_action': 'rename',
        }))
        successful, failed, skipped = exporter.export_songs_batch(self._batch(), self.temp_dir)
        self.assertEqual(len(successful), 2)
        self.assertTrue((self.temp_dir / 'Song One_1.pro6').exists())
        # Original left untouched
        self.assertEqual((self.temp_dir / 'Song One.pro6').read_text(encoding='utf-8'), 'existing')

    def test_song_without_content_reported_failed(self):
        exporter = ProPresenter6Exporter(config=ConfigStub())
        batch = [(make_song(title='Empty Song'), [])]
        successful, failed, skipped = exporter.export_songs_batch(batch, self.temp_dir)
        self.assertEqual(successful, [])
        self.assertEqual(len(failed), 1)
        self.assertIn('Empty Song', failed[0])


if __name__ == '__main__':
    unittest.main()
