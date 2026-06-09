# -*- coding: utf-8 -*-
"""
Section Detector Module for EasyWorship Export

This module detects and identifies song sections (verse, chorus, bridge, etc.)
from parsed text content. Section markers appear as plain text on their own lines.
"""

import re
import logging
import json
from pathlib import Path
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class SectionDetector:
    """
    Detects and structures song sections from plain text.
    
    Sections are identified by markers that appear on their own lines,
    such as 'verse', 'chorus', 'bridge', etc.
    Uses configurable mappings for Swedish to English conversion.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the section detector with configurable mappings."""
        self.last_detection_info = None
        self._load_section_mappings(config_path)
        self._create_numbered_pattern()
    
    def _load_section_mappings(self, config_path: Optional[str] = None):
        """Load section mappings from configuration file."""
        # Lazy import keeps this module importable without the src package root
        from src.utils.section_mappings import (
            get_mappings_file, DEFAULT_SECTION_MAPPINGS, DEFAULT_NUMBER_RULES)

        if config_path is None:
            config_path = get_mappings_file()

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.section_mappings = config.get('section_mappings', {})
                self.number_rules = config.get('number_mapping_rules', {})
            logger.debug(f"Loaded section mappings from {config_path}")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load section mappings: {e}. Using defaults.")
            self.section_mappings = dict(DEFAULT_SECTION_MAPPINGS)
            self.number_rules = dict(DEFAULT_NUMBER_RULES)

        # Create list of all known section markers for pattern matching
        self.section_markers = list(self.section_mappings.keys())
    
    def _create_numbered_pattern(self):
        """Create regex pattern for numbered sections based on loaded mappings."""
        # Get all base section types from mappings
        base_sections = '|'.join(self.section_markers)
        self.numbered_pattern = re.compile(
            rf'^({base_sections})\s*(\d+)?$',
            re.IGNORECASE
        )
        
    def detect_sections(self, text: str) -> Dict[str, Any]:
        """
        Detect sections in the provided text.
        
        Args:
            text: Plain text content with potential section markers
            
        Returns:
            Dictionary with:
                - sections: List of section dictionaries with 'type' and 'content'
                - has_sections: Boolean indicating if sections were found
                - plain_text: Original plain text
        """
        if not text:
            return {
                'sections': [],
                'has_sections': False,
                'plain_text': ''
            }
        
        lines = text.split('\n')
        sections = []
        current_section = None
        current_content = []
        
        for i, line in enumerate(lines):
            # Check if this line is a section marker
            section_type = self._identify_section_marker(line)
            
            if section_type:
                # Save previous section if exists
                if current_section or current_content:
                    self._save_section(sections, current_section, current_content)
                
                # Start new section
                current_section = section_type
                current_content = []
                logger.debug(f"Found section marker '{section_type}' at line {i+1}")
            else:
                # Add line to current section content
                current_content.append(line)
        
        # Save last section
        if current_section or current_content:
            self._save_section(sections, current_section, current_content)
        
        # If no sections were found, treat entire content as one verse
        if not sections and text.strip():
            sections.append({
                'type': 'verse',
                'content': text.strip()
            })
            logger.debug("No section markers found, treating as single verse")
        
        has_sections = len(sections) > 1 or (
            len(sections) == 1 and sections[0]['type'] != 'verse'
        )
        
        # Store detection info for debugging
        self.last_detection_info = {
            'total_lines': len(lines),
            'sections_found': len(sections),
            'section_types': [s['type'] for s in sections]
        }
        
        return {
            'sections': sections,
            'has_sections': has_sections,
            'plain_text': text
        }
    
    def _identify_section_marker(self, line: str) -> Optional[str]:
        """
        Check if a line is a section marker.
        
        Args:
            line: Single line of text to check
            
        Returns:
            Normalized section type with number if marker found, None otherwise
        """
        # Clean the line for comparison
        clean_line = line.strip().lower()
        
        if not clean_line:
            return None
        
        # Check for exact matches first
        for marker in self.section_markers:
            if clean_line == marker.lower():
                return self._normalize_section_type(marker)
        
        # Check for numbered sections (e.g., "verse 1", "chorus 2")
        match = self.numbered_pattern.match(clean_line)
        if match:
            section_type = match.group(1).lower()
            section_number = match.group(2)
            return self._normalize_section_type(section_type, section_number)
        
        # Check if line starts with a section marker followed by space/colon and number only
        for marker in self.section_markers:
            marker_lower = marker.lower()
            if clean_line.startswith(marker_lower + ' '):
                # Check if what follows is just a number or is empty (for "verse:", "chorus:" etc.)
                remainder = clean_line[len(marker_lower) + 1:].strip()
                if remainder.isdigit():
                    return self._normalize_section_type(marker, remainder)
                elif not remainder:
                    return self._normalize_section_type(marker)
            elif clean_line.startswith(marker_lower + ':'):
                remainder = clean_line[len(marker_lower) + 1:].strip()
                if remainder.isdigit():
                    return self._normalize_section_type(marker, remainder)
                else:
                    return self._normalize_section_type(marker)
        
        return None
    
    def _normalize_section_type(self, section_type: str, number: Optional[str] = None) -> str:
        """
        Normalize section type to standard English format with number.
        
        Args:
            section_type: Raw section type string (e.g., 'vers', 'chorus')
            number: Optional section number (e.g., '1', '2')
            
        Returns:
            Normalized section type with number (e.g., 'Verse 1', 'Chorus')
        """
        section_type_lower = section_type.lower().strip()
        
        # Map to English using configuration
        english_name = self.section_mappings.get(section_type_lower, section_type.title())
        
        # Add number if present and rules allow it
        if number and self.number_rules.get('preserve_numbers', True):
            format_template = self.number_rules.get('format', '{section_name} {number}')
            return format_template.format(section_name=english_name, number=number)
        
        return english_name
    
    def _save_section(self, sections: List[Dict], section_type: Optional[str], 
                     content_lines: List[str]):
        """
        Save a section to the sections list.
        
        Args:
            sections: List to append section to
            section_type: Type of section (verse, chorus, etc.)
            content_lines: Lines of content for this section
        """
        # Clean up content
        content = '\n'.join(content_lines).strip()
        
        if not content:
            return  # Don't save empty sections
        
        # If no section type specified, default to verse
        if not section_type:
            section_type = 'verse'
        
        sections.append({
            'type': section_type,
            'content': content
        })
    
    def get_detection_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the last detection operation."""
        return self.last_detection_info


class AdvancedSectionDetector(SectionDetector):
    """
    Advanced section detector with additional heuristics.
    
    Includes:
    - Pattern-based detection for sections without explicit markers
    - Repeated content detection for chorus identification
    - Verse numbering detection
    """
    
    def detect_sections(self, text: str) -> Dict[str, Any]:
        """
        Detect sections with advanced heuristics.
        
        First tries standard detection, then applies heuristics
        if no sections are found.
        """
        # Try standard detection first
        result = super().detect_sections(text)
        
        # If sections were found, return them
        if result['has_sections']:
            return result
        
        # Apply heuristics to detect sections without markers
        logger.debug("Applying advanced section detection heuristics")
        sections = self._detect_by_patterns(text)
        
        if sections:
            result['sections'] = sections
            result['has_sections'] = True
            logger.debug(f"Found {len(sections)} sections using heuristics")
        
        return result
    
    def _detect_by_patterns(self, text: str) -> List[Dict[str, str]]:
        """
        Detect sections based on text patterns and repetition.
        
        Args:
            text: Plain text content
            
        Returns:
            List of detected sections
        """
        sections = []
        paragraphs = text.split('\n\n')
        
        if len(paragraphs) < 2:
            return []  # Not enough structure for pattern detection
        
        # Look for repeated paragraphs (likely chorus)
        paragraph_counts = {}
        for para in paragraphs:
            para_clean = para.strip()
            if para_clean:
                paragraph_counts[para_clean] = paragraph_counts.get(para_clean, 0) + 1
        
        # Identify potential chorus (most repeated paragraph)
        chorus_text = None
        if paragraph_counts:
            chorus_text = max(paragraph_counts, key=paragraph_counts.get)
            if paragraph_counts[chorus_text] < 2:
                chorus_text = None  # Not repeated enough to be chorus
        
        # Build sections based on paragraph structure
        verse_num = 1
        for para in paragraphs:
            para_clean = para.strip()
            if not para_clean:
                continue
            
            if para_clean == chorus_text:
                sections.append({
                    'type': 'chorus',
                    'content': para_clean
                })
            else:
                sections.append({
                    'type': 'verse',
                    'content': para_clean
                })
                verse_num += 1
        
        return sections


def detect_sections(text: str, advanced: bool = False) -> Dict[str, Any]:
    """
    Convenience function to detect sections in text.
    
    Args:
        text: Plain text content
        advanced: Whether to use advanced detection heuristics
        
    Returns:
        Dictionary with detected sections
    """
    detector_class = AdvancedSectionDetector if advanced else SectionDetector
    detector = detector_class()
    return detector.detect_sections(text)