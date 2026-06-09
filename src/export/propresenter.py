"""
ProPresenter 6 XML export functionality - Corrected format
Based on propresenter-parser documentation
"""

import xml.etree.ElementTree as ET
import xml.dom.minidom
import uuid
import re
import base64
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DuplicateDecision:
    """Decision for handling an export target file that already exists."""
    action: str  # 'skip' | 'overwrite' | 'rename' | 'rename_custom' | 'cancel'
    custom_name: Optional[str] = None
    apply_to_all: bool = False


# Callback invoked when an export target already exists:
# (existing_path, remaining_duplicate_count) -> DuplicateDecision
DuplicateResolver = Callable[[Path, int], DuplicateDecision]

class ProPresenter6Exporter:
    """Handles export to ProPresenter 6 (.pro6) format with correct XML structure"""
    
    def __init__(self, config=None):
        self.slide_width = 1920
        self.slide_height = 1080
        self.default_font_size = 60
        self.text_padding = 20
        self.config = config
        self.duplicate_action = None  # For batch duplicate handling
        
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for Windows file system"""
        # First, remove all control characters including newlines, tabs, carriage returns
        # This handles \n, \r, \t and other control characters (ASCII 0-31 and 127)
        filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)
        
        # Remove or replace invalid Windows filename characters
        invalid_chars = r'[<>:"/\\|?*]'
        filename = re.sub(invalid_chars, '_', filename)
        
        # Remove leading/trailing spaces and dots
        filename = filename.strip(' .')
        
        # Replace multiple consecutive spaces with single space
        filename = re.sub(r'\s+', ' ', filename)
        
        # Limit length to reasonable size
        if len(filename) > 200:
            filename = filename[:200].strip()
        
        # Ensure filename is not empty
        if not filename:
            filename = "Untitled_Song"
            
        return filename
    
    def generate_guid(self) -> str:
        """Generate a GUID for ProPresenter elements"""
        return str(uuid.uuid4()).upper()
    
    def encode_base64(self, text: str) -> str:
        """Encode text to base64 for ProPresenter fields"""
        return base64.b64encode(text.encode('utf-8')).decode('ascii')
    
    def create_rtf_data(self, content: str) -> str:
        """Create RTF data for text content and encode to base64"""
        # Escape special RTF characters
        content = content.replace('\\', '\\\\')
        content = content.replace('{', '\\{')
        content = content.replace('}', '\\}')
        
        # Get font settings from config
        font_family = 'Arial'  # Default
        font_size = 72  # Default
        
        if self.config:
            # Check if formatting is enabled and font should be changed
            if self.config.get('export.formatting_enabled', False) and self.config.get('export.change_font', False):
                font_family = self.config.get('export.font.family', 'Arial')
                font_size = self.config.get('export.font.size', 72)
        
        # Map font size to RTF size (RTF uses half-points, so multiply by 2)
        rtf_font_size = font_size * 2
        
        # Convert line breaks to RTF paragraphs  
        lines = content.split('\n')
        rtf_lines = []
        
        # Build RTF content with proper formatting
        rtf_header = (
            r'{\rtf1\prortf1\ansi\ansicpg1252\uc1\htmautsp\deff2'
            r'{\fonttbl{\f0\fcharset0 Times New Roman;}{\f2\fcharset0 Georgia;}{\f3\fcharset0 ' + font_family + r';}{\f4\fcharset0 Impact;}}'
            r'{\colortbl;\red0\green0\blue0;\red255\green255\blue255;}'
            r'\loch\hich\dbch\pard\slleading0\plain\ltrpar\itap0'
            r'{\lang1033\fs' + str(rtf_font_size) + r'\f3\cf1 \cf1\qc'
        )
        
        for i, line in enumerate(lines):
            if i > 0:
                rtf_lines.append(r'\par}')
            # Use configured font size
            rtf_lines.append(r'{\fs' + str(rtf_font_size) + r'\f3 {\cf2\ltrch ' + line + r'}\li0\sa0\sb0\fi0\qc')
        
        # Close the RTF structure without adding extra paragraph break
        rtf_content = rtf_header + ''.join(rtf_lines) + r'}}}' 
        
        # Encode to base64
        return base64.b64encode(rtf_content.encode('utf-8')).decode('ascii')
    
    def create_winflow_data(self, content: str) -> str:
        """Create Windows Flow document data and encode to base64"""
        lines = content.split('\n')
        paragraphs = []
        
        # Get font settings from config
        font_family = 'Arial'  # Default
        font_size = 72  # Default
        
        if self.config:
            # Check if formatting is enabled and font should be changed
            if self.config.get('export.formatting_enabled', False) and self.config.get('export.change_font', False):
                font_family = self.config.get('export.font.family', 'Arial')
                font_size = self.config.get('export.font.size', 72)
        
        for line in lines:
            # Escape XML special characters
            line = line.replace('&', '&amp;')
            line = line.replace('<', '&lt;')
            line = line.replace('>', '&gt;')
            line = line.replace('"', '&quot;')
            line = line.replace("'", '&apos;')
            
            paragraph = (
                f'<Paragraph Margin="0,0,0,0" TextAlignment="Center" FontFamily="{font_family}" FontSize="{font_size}">'
                f'<Run FontFamily="{font_family}" FontStretch="Normal" FontSize="{font_size}" Foreground="#FFFFFFFF" '
                f'Block.TextAlignment="Center">{line}</Run></Paragraph>'
            )
            paragraphs.append(paragraph)
        
        winflow = (
            '<FlowDocument TextAlignment="Center" PagePadding="5,0,5,0" AllowDrop="True" '
            'xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation">'
            + ''.join(paragraphs) +
            '</FlowDocument>'
        )
        
        return base64.b64encode(winflow.encode('utf-8')).decode('ascii')
    
    def create_winfont_data(self) -> str:
        """Create Windows font data and encode to base64"""
        winfont = (
            '<?xml version="1.0" encoding="utf-16"?>'
            '<RVFont xmlns:i="http://www.w3.org/2001/XMLSchema-instance" '
            'xmlns="http://schemas.datacontract.org/2004/07/ProPresenter.Common">'
            '<Kerning>0</Kerning><LineSpacing>0</LineSpacing>'
            '<OutlineColor xmlns:d2p1="http://schemas.datacontract.org/2004/07/System.Windows.Media">'
            '<d2p1:A>255</d2p1:A><d2p1:B>0</d2p1:B><d2p1:G>0</d2p1:G><d2p1:R>0</d2p1:R>'
            '<d2p1:ScA>1</d2p1:ScA><d2p1:ScB>0</d2p1:ScB><d2p1:ScG>0</d2p1:ScG><d2p1:ScR>0</d2p1:ScR>'
            '</OutlineColor><OutlineWidth>0</OutlineWidth><Variants>Normal</Variants></RVFont>'
        )
        
        # Note: ProPresenter expects UTF-16 encoding for this field
        return base64.b64encode(winfont.encode('utf-16')).decode('ascii')
    
    def get_group_color(self, section_type: str) -> str:
        """Get the color for a slide group based on section type"""
        colors = {
            'verse': '0 0 1 1',        # Blue
            'chorus': '1 0.39 0.39 1',  # Red-ish
            'bridge': '0 0.5 1 1',      # Light blue
            'pre-chorus': '0.5 0 1 1',  # Purple
            'intro': '0.5 0.5 0.5 1',   # Gray
            'outro': '0.5 0.5 0.5 1',   # Gray
            'ending': '0.5 0.5 0.5 1',  # Gray
            'tag': '1 0.5 0 1',         # Orange
            'interlude': '0 1 0.5 1',   # Green
            'blank': '0.3 0.3 0.3 1'    # Dark gray
        }
        return colors.get(section_type.lower(), '0 0 0 1')
    
    def format_section_name(self, section_type: str) -> str:
        """Format section name for ProPresenter display"""
        # Section detector now returns properly formatted names like "Verse 1", "Chorus", etc.
        # If it already contains a space and number, use as-is
        if ' ' in section_type and section_type.split()[-1].isdigit():
            return section_type
        
        # Otherwise, apply legacy mapping for backwards compatibility
        section_map = {
            'verse': 'Verse',
            'chorus': 'Chorus', 
            'refrain': 'Chorus',
            'bridge': 'Bridge',
            'pre-chorus': 'Pre-Chorus',
            'intro': 'Intro',
            'outro': 'Outro',
            'ending': 'Outro',
            'tag': 'Tag',
            'interlude': 'Interlude',
            'blank': 'Blank'
        }
        
        return section_map.get(section_type.lower(), section_type.title())
    
    def split_content_into_slides(self, content: str) -> List[str]:
        """Split content into individual slides based on max lines setting"""
        slides = []
        
        # Get max lines per slide from config
        max_lines = 4  # Default
        if self.config:
            if self.config.get('export.formatting_enabled', False):
                max_lines = self.config.get('export.slides.max_lines_per_slide', 4)
        
        # Check if we should auto-break long sections
        auto_break = True  # Default
        if self.config:
            if self.config.get('export.formatting_enabled', False):
                auto_break = self.config.get('export.slides.auto_break_long_lines', True)
        
        # First, split by empty lines (natural slide breaks)
        natural_slides = []
        lines = content.split('\n')
        current_section = []
        
        for line in lines:
            line = line.strip()
            if not line:
                # Empty line marks a natural slide break
                if current_section:
                    natural_slides.append('\n'.join(current_section))
                    current_section = []
            else:
                current_section.append(line)
        
        # Add final section if exists
        if current_section:
            natural_slides.append('\n'.join(current_section))
        
        # Now process each natural slide
        for natural_slide in natural_slides:
            slide_lines = natural_slide.split('\n')
            
            if auto_break and len(slide_lines) > max_lines:
                # Break this slide into multiple slides based on max_lines
                for i in range(0, len(slide_lines), max_lines):
                    chunk = slide_lines[i:i + max_lines]
                    slides.append('\n'.join(chunk))
            else:
                # Keep as single slide (even if longer than max_lines when auto_break is off)
                slides.append(natural_slide)
        
        # If no slides created, treat entire content as one slide
        if not slides and content.strip():
            slides = [content.strip()]
            
        return slides
    
    def create_pro6_document(self, song_data: Dict[str, Any], sections: List[Dict[str, str]]) -> ET.Element:
        """Create the root ProPresenter 6 XML document with correct structure"""
        
        # Root element with proper attributes
        root = ET.Element('RVPresentationDocument')
        root.set('height', str(self.slide_height))
        root.set('width', str(self.slide_width))
        root.set('docType', '0')
        root.set('versionNumber', '600')
        root.set('usedCount', '0')
        root.set('backgroundColor', '0 0 0 1')
        root.set('drawingBackgroundColor', 'false')
        root.set('CCLIDisplay', 'true' if song_data.get('reference_number') else 'false')
        root.set('lastDateUsed', datetime.now().strftime('%Y-%m-%dT%H:%M:%S+00:00'))
        root.set('selectedArrangementID', '')
        root.set('category', 'Song')
        root.set('resourcesDirectory', '')
        root.set('notes', '')
        
        # CCLI metadata
        root.set('CCLIAuthor', song_data.get('author', ''))
        root.set('CCLIArtistCredits', song_data.get('author', ''))
        root.set('CCLISongTitle', song_data.get('title', 'Untitled'))
        root.set('CCLIPublisher', song_data.get('administrator', ''))
        root.set('CCLICopyrightYear', '')
        root.set('CCLISongNumber', song_data.get('reference_number', ''))
        root.set('chordChartPath', '')
        root.set('os', '1')
        root.set('buildNumber', '6016')
        
        # Timeline
        timeline = ET.SubElement(root, 'RVTimeline')
        timeline.set('timeOffset', '0')
        timeline.set('duration', '0')
        timeline.set('selectedMediaTrackIndex', '-1')
        timeline.set('loop', 'false')
        timeline.set('rvXMLIvarName', 'timeline')
        
        # Time cues array
        time_cues = ET.SubElement(timeline, 'array')
        time_cues.set('rvXMLIvarName', 'timeCues')
        
        # Media tracks array
        media_tracks = ET.SubElement(timeline, 'array')
        media_tracks.set('rvXMLIvarName', 'mediaTracks')
        
        # Groups array for slide groups
        groups_array = ET.SubElement(root, 'array')
        groups_array.set('rvXMLIvarName', 'groups')
        
        # Add intro slide if configured
        if self.config and self.config.get('export.slides.add_intro_slide', False):
            intro_text = self.config.get('export.slides.intro_slide_text', '')
            intro_group_name = self.config.get('export.slides.intro_slide_group', 'Intro')
            # Add intro slide even if text is empty (for title slides)
            intro_section = {
                'type': 'intro',
                'content': intro_text  # Can be empty for blank intro slide
            }
            intro_group = self.create_slide_group(intro_section, custom_name=intro_group_name)
            groups_array.append(intro_group)
        
        # Create slide groups for each section
        for section in sections:
            if not section.get('content', '').strip():
                continue
                
            group = self.create_slide_group(section)
            groups_array.append(group)
        
        # Add blank slide if configured
        if self.config and self.config.get('export.slides.add_blank_slide', False):
            blank_group_name = self.config.get('export.slides.blank_slide_group', 'Blank')
            blank_section = {
                'type': 'blank',
                'content': ''  # Empty string for blank slide
            }
            blank_group = self.create_slide_group(blank_section, custom_name=blank_group_name)
            groups_array.append(blank_group)
        
        # Arrangements array (empty for now)
        arrangements = ET.SubElement(root, 'array')
        arrangements.set('rvXMLIvarName', 'arrangements')
        
        return root
    
    def create_slide_group(self, section: Dict[str, str], custom_name: Optional[str] = None) -> ET.Element:
        """Create a slide group with proper ProPresenter 6 structure"""
        
        section_type = section.get('type', 'verse')
        group_name = custom_name if custom_name else self.format_section_name(section_type)
        
        group = ET.Element('RVSlideGrouping')
        group.set('name', group_name)
        group.set('color', self.get_group_color(section_type))
        group.set('uuid', self.generate_guid())
        
        # Slides array
        slides_array = ET.SubElement(group, 'array')
        slides_array.set('rvXMLIvarName', 'slides')
        
        # Split content into individual slides
        content = section.get('content', '').strip()
        
        # Special handling for blank and intro slides - allow empty content
        if not content and section.get('type') not in ['blank', 'intro']:
            return group
            
        # For blank and intro slides, use empty string if no content
        if section.get('type') in ['blank', 'intro'] and not content:
            content = ''
            
        slides = self.split_content_into_slides(content) if content else ['']
        
        for slide_content in slides:
            slide = self.create_slide(slide_content)
            slides_array.append(slide)
        
        return group
    
    def create_slide(self, content: str) -> ET.Element:
        """Create an individual slide with ProPresenter 6 structure"""
        
        slide = ET.Element('RVDisplaySlide')
        slide.set('backgroundColor', '0 0 0 0')
        slide.set('highlightColor', '')
        slide.set('drawingBackgroundColor', 'false')
        slide.set('enabled', 'true')
        slide.set('hotKey', '')
        slide.set('label', '')
        slide.set('notes', '')
        slide.set('UUID', self.generate_guid())
        slide.set('chordChartPath', '')
        
        # Cues array (empty)
        cues = ET.SubElement(slide, 'array')
        cues.set('rvXMLIvarName', 'cues')
        
        # Display elements array
        display_elements = ET.SubElement(slide, 'array')
        display_elements.set('rvXMLIvarName', 'displayElements')
        
        # Create text element
        text_element = self.create_text_element(content)
        display_elements.append(text_element)
        
        return slide
    
    def create_text_element(self, content: str) -> ET.Element:
        """Create a text element with proper encoding and structure"""
        
        element = ET.Element('RVTextElement')
        element.set('displayName', 'Default')
        element.set('UUID', self.generate_guid())
        element.set('typeID', '0')
        element.set('displayDelay', '0')
        element.set('locked', 'false')
        element.set('persistent', '0')
        element.set('fromTemplate', 'false')
        element.set('opacity', '1')
        element.set('source', '')
        element.set('bezelRadius', '0')
        element.set('rotation', '0')
        element.set('drawingFill', 'false')
        element.set('drawingShadow', 'false')
        element.set('drawingStroke', 'false')
        element.set('fillColor', '1 1 1 1')
        element.set('adjustsHeightToFit', 'false')
        element.set('verticalAlignment', '0')
        element.set('revealType', '0')
        
        # Position - ProPresenter uses special format: {x y z width height}
        position = ET.SubElement(element, 'RVRect3D')
        position.set('rvXMLIvarName', 'position')
        # Calculate position with padding
        x = self.text_padding
        y = self.text_padding
        width = self.slide_width - (self.text_padding * 2)
        height = self.slide_height - (self.text_padding * 2)
        position.text = f'{{{x} {y} 0 {width} {height}}}'
        
        # Shadow
        shadow = ET.SubElement(element, 'shadow')
        shadow.set('rvXMLIvarName', 'shadow')
        shadow.text = '10|0 0 0 1|{4.94974746830583, -4.94974746830583}'
        
        # Stroke dictionary
        stroke_dict = ET.SubElement(element, 'dictionary')
        stroke_dict.set('rvXMLIvarName', 'stroke')
        
        stroke_color = ET.SubElement(stroke_dict, 'NSColor')
        stroke_color.set('rvXMLDictionaryKey', 'RVShapeElementStrokeColorKey')
        stroke_color.text = '0 0 0 1'
        
        stroke_width = ET.SubElement(stroke_dict, 'NSNumber')
        stroke_width.set('rvXMLDictionaryKey', 'RVShapeElementStrokeWidthKey')
        stroke_width.set('hint', 'double')
        stroke_width.text = '0'
        
        # Plain text (base64 encoded)
        plain_text = ET.SubElement(element, 'NSString')
        plain_text.set('rvXMLIvarName', 'PlainText')
        # Ensure content is properly trimmed and convert line endings
        trimmed_content = content.strip()
        clean_content = trimmed_content.replace('\r\n', '\n').replace('\n', '\r\n')
        plain_text.text = self.encode_base64(clean_content)
        
        # RTF data (base64 encoded)
        rtf_data = ET.SubElement(element, 'NSString')
        rtf_data.set('rvXMLIvarName', 'RTFData')
        rtf_data.text = self.create_rtf_data(trimmed_content)
        
        # WinFlow data (base64 encoded)
        winflow_data = ET.SubElement(element, 'NSString')
        winflow_data.set('rvXMLIvarName', 'WinFlowData')
        winflow_data.text = self.create_winflow_data(trimmed_content)
        
        # WinFont data (base64 encoded)
        winfont_data = ET.SubElement(element, 'NSString')
        winfont_data.set('rvXMLIvarName', 'WinFontData')
        winfont_data.text = self.create_winfont_data()
        
        return element
        
    def ensure_proper_array_tags(self, element):
        """Ensure empty array elements have proper opening/closing tags by adding empty text"""
        for array_elem in element.iter('array'):
            if array_elem.text is None and len(list(array_elem)) == 0:
                # Add empty text to prevent self-closing
                array_elem.text = ''
    
    def fix_self_closing_tags(self, xml_string: str) -> str:
        """Fix self-closing array tags to have proper opening/closing tags"""
        # Pattern to match self-closing array tags
        pattern = r'<array([^>]*?)rvXMLIvarName="([^"]*?)"([^>]*?)/>'
        
        # Replace with opening and closing tags
        def replace_func(match):
            attrs_before = match.group(1)
            var_name = match.group(2)
            attrs_after = match.group(3)
            return f'<array{attrs_before}rvXMLIvarName="{var_name}"{attrs_after}></array>'
        
        return re.sub(pattern, replace_func, xml_string)
    
    def export_song(self, song_data: Dict[str, Any], sections: List[Dict[str, str]], 
                   output_path: Path) -> Tuple[bool, str]:
        """Export a single song to ProPresenter 6 format"""
        
        try:
            # Validate song has content
            title = song_data.get('title', 'Untitled')
            
            # Check if sections exist and have content
            has_content = False
            if sections:
                for section in sections:
                    if section.get('content', '').strip():
                        has_content = True
                        break
            
            if not has_content:
                error_msg = f"Song '{title}' has no lyrics data and cannot be exported (empty or corrupt song data)"
                logger.warning(error_msg)
                return False, error_msg
            
            # Create XML document
            root = self.create_pro6_document(song_data, sections)
            
            # Ensure empty arrays have proper tags
            self.ensure_proper_array_tags(root)
            
            # Create filename
            clean_title = self.sanitize_filename(title)
            filename = f"{clean_title}.pro6"
            full_path = output_path / filename
            
            # Ensure output directory exists
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Convert to string with proper formatting
            xml_str = ET.tostring(root, encoding='unicode')
            
            # Fix self-closing array tags before pretty printing
            xml_str = self.fix_self_closing_tags(xml_str)
            
            # Pretty print using minidom
            dom = xml.dom.minidom.parseString(xml_str)
            pretty_xml = dom.toprettyxml(indent="  ", encoding='utf-8')
            
            # Decode from bytes to string for final processing
            if isinstance(pretty_xml, bytes):
                pretty_xml = pretty_xml.decode('utf-8')
            
            # Apply fix again after pretty printing (in case minidom creates new self-closing tags)
            pretty_xml = self.fix_self_closing_tags(pretty_xml)
            
            # Write to file
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(pretty_xml)
            
            return True, str(full_path)
            
        except OSError as e:
            # Handle file system errors (errno 22 is invalid argument)
            if e.errno == 22:
                # Show the problematic filename in the error for debugging
                error_msg = f"Cannot export '{title}': Song title contains invalid characters (newlines, control characters, or special symbols)"
                logger.error(f"{error_msg}. Attempted filename: {full_path}", exc_info=True)
            else:
                error_msg = f"File system error for '{title}': {str(e)}"
                logger.error(error_msg, exc_info=True)
            return False, error_msg
            
        except Exception as e:
            error_msg = f"Failed to export '{title}': {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def export_songs_batch(self, songs_with_sections: List[Tuple[Dict[str, Any], List[Dict[str, str]]]],
                          output_path: Path, progress_callback=None,
                          on_duplicate: Optional[DuplicateResolver] = None,
                          cancel_event=None) -> Tuple[List[str], List[str], List[str]]:
        """Export multiple songs with progress tracking, duplicate handling, and cancellation support

        Args:
            songs_with_sections: List of tuples (song_data, sections)
            output_path: Directory to export files to
            progress_callback: Optional callback for progress updates
            on_duplicate: Optional callback asked to resolve existing target
                files when the configured action is 'ask'. Without a callback,
                duplicates are skipped.
            cancel_event: Optional threading.Event to signal cancellation

        Returns:
            Tuple of (successful_exports, failed_exports, skipped_exports)
        """

        successful_exports = []
        failed_exports = []
        skipped_exports = []
        total_songs = len(songs_with_sections)

        dup_action = self.config.get('export.duplicate_handling_action', 'ask') if self.config else 'ask'
        # Only build the duplicate map if we might need it (not overwrite mode)
        existing_files = self._build_duplicate_map(songs_with_sections, output_path) \
            if dup_action != 'overwrite' else {}

        # Pre-set the remembered action when config dictates one (not "ask")
        self.duplicate_action = dup_action if dup_action != 'ask' else None

        for i, (song_data, sections) in enumerate(songs_with_sections):
            # Check for cancellation before processing each song
            if cancel_event and cancel_event.is_set():
                logger.info(f"Export cancelled by user at song {i+1}/{total_songs}")
                failed_exports.append("Export cancelled by user")
                break

            try:
                # Update progress
                if progress_callback:
                    progress_callback(i, total_songs, song_data.get('title', 'Unknown'))

                file_path = output_path / self._generate_filename(song_data)

                if file_path.exists() and dup_action != 'overwrite':
                    # Count how many songs after this one will also hit this file
                    remaining = sum(1 for idx in existing_files.get(str(file_path), []) if idx > i)
                    decision = self._resolve_duplicate(file_path, remaining, on_duplicate)

                    if decision.action == 'skip':
                        skipped_exports.append(song_data.get('title', 'Unknown'))
                        continue
                    elif decision.action == 'cancel':
                        failed_exports.append(f"Cancelled: {song_data.get('title', 'Unknown')}")
                        break
                    elif decision.action in ('rename', 'rename_custom'):
                        file_path = self._apply_rename(file_path, decision)

                # Export song with potentially modified path
                success, result = self._export_song_to_path(song_data, sections, file_path)

                if success:
                    successful_exports.append(result)
                else:
                    failed_exports.append(result)

            except Exception as e:
                title = song_data.get('title', 'Unknown')
                error_msg = f"Unexpected error exporting '{title}': {str(e)}"
                logger.error(f"Export failed for song ID {song_data.get('rowid', '?')}: {title}", exc_info=True)
                failed_exports.append(error_msg)

        # Final progress update
        if progress_callback:
            progress_callback(total_songs, total_songs, "Export complete")

        return successful_exports, failed_exports, skipped_exports

    def _build_duplicate_map(self, songs_with_sections: List[Tuple[Dict[str, Any], List[Dict[str, str]]]],
                             output_path: Path) -> Dict[str, List[int]]:
        """Map existing target file paths to indices of songs that would write them"""
        existing_files: Dict[str, List[int]] = {}
        for idx, (song_data, _) in enumerate(songs_with_sections):
            file_path = output_path / self._generate_filename(song_data)
            if file_path.exists():
                existing_files.setdefault(str(file_path), []).append(idx)
        return existing_files

    def _resolve_duplicate(self, file_path: Path, remaining: int,
                           on_duplicate: Optional[DuplicateResolver]) -> DuplicateDecision:
        """Resolve an existing target file, honoring a remembered apply-to-all action"""
        if self.duplicate_action:
            return DuplicateDecision(self.duplicate_action)

        if on_duplicate is None:
            return DuplicateDecision('skip')

        decision = on_duplicate(file_path, remaining)
        if decision.apply_to_all:
            # A single custom name cannot apply to every file; fall back to
            # auto-numbered renaming for the remaining duplicates.
            self.duplicate_action = 'rename' if decision.action == 'rename_custom' else decision.action
        return decision

    def _apply_rename(self, file_path: Path, decision: DuplicateDecision) -> Path:
        """Compute the target path for a rename decision"""
        if decision.action == 'rename_custom' and decision.custom_name:
            # Sanitize so a name like "..\evil" cannot escape the
            # chosen export directory or introduce path separators.
            custom_name = self.sanitize_filename(decision.custom_name)
            return file_path.parent / f"{custom_name}.pro6"

        # Auto-rename with number suffix
        base = file_path.stem
        ext = file_path.suffix
        counter = 1
        while file_path.exists():
            file_path = file_path.parent / f"{base}_{counter}{ext}"
            counter += 1
        return file_path
    
    def _generate_filename(self, song_data: Dict[str, Any]) -> str:
        """Generate filename based on config settings"""
        title = self.sanitize_filename(song_data.get('title', 'Untitled'))
        
        # Add CCLI number if configured
        if self.config and self.config.get('export.include_ccli_in_filename', False):
            ccli = song_data.get('reference_number', '').strip()
            if ccli:
                title = f"{title}_{ccli}"
        
        # Add author if configured
        if self.config and self.config.get('export.include_author_in_filename', False):
            author = song_data.get('author', '').strip()
            if author:
                author = self.sanitize_filename(author)
                title = f"{title}_{author}"
        
        return f"{title}.pro6"
    
    def _export_song_to_path(self, song_data: Dict[str, Any], sections: List[Dict[str, str]], 
                             file_path: Path) -> Tuple[bool, str]:
        """Export a single song to a specific file path"""
        try:
            # Validate song has content
            title = song_data.get('title', 'Untitled')
            song_id = song_data.get('rowid', 'Unknown ID')
            
            # Check if sections exist and have content
            has_content = False
            if sections:
                for section in sections:
                    if section.get('content', '').strip():
                        has_content = True
                        break
            
            if not has_content:
                error_msg = f"Song '{title}' (ID: {song_id}) has no lyrics data and cannot be exported"
                logger.warning(error_msg)
                return False, error_msg
            
            # Ensure output directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create XML structure
            root = self.create_pro6_document(song_data, sections)
            
            # Ensure empty arrays have proper tags
            self.ensure_proper_array_tags(root)
            
            # Convert to string with proper formatting
            xml_str = ET.tostring(root, encoding='unicode')
            
            # Fix self-closing array tags before pretty printing
            xml_str = self.fix_self_closing_tags(xml_str)
            
            # Pretty print using minidom
            dom = xml.dom.minidom.parseString(xml_str)
            pretty_xml = dom.toprettyxml(indent="  ", encoding='utf-8')
            
            # Decode from bytes to string for final processing
            if isinstance(pretty_xml, bytes):
                pretty_xml = pretty_xml.decode('utf-8')
            
            # Apply fix again after pretty printing (in case minidom creates new self-closing tags)
            pretty_xml = self.fix_self_closing_tags(pretty_xml)
            
            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(pretty_xml)
            
            return True, f"Successfully exported: {song_data.get('title', 'Unknown')}"
            
        except OSError as e:
            # Handle file system errors
            title = song_data.get('title', 'Unknown')
            if e.errno == 22:  # Invalid argument error
                error_msg = f"Cannot export '{title}': Invalid filename (contains special characters)"
            else:
                error_msg = f"File system error for '{title}': {str(e)}"
            logger.error(f"{error_msg}. Path: {file_path}", exc_info=True)
            return False, error_msg
        except Exception as e:
            title = song_data.get('title', 'Unknown')
            song_id = song_data.get('rowid', 'Unknown ID')
            error_msg = f"Failed to export '{title}' (ID: {song_id}): {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
