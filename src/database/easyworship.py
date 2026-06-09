"""
EasyWorship database access layer
"""

import sqlite3
import logging
import platform
from pathlib import Path
from typing import List, Dict, Optional, Any

# Import processing modules - handle both relative and absolute imports
try:
    from ..processing import parse_rtf, detect_sections, clean_text
except ImportError:
    # Fallback for direct script execution
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from processing import parse_rtf, detect_sections, clean_text

logger = logging.getLogger(__name__)

class EasyWorshipDatabase:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.songs_db = self.db_path / "Songs.db"
        self.words_db = self.db_path / "SongWords.db"
        self.section_detector = None  # Will be initialized on first use
        
    def _get_connection(self, db_path: Path) -> sqlite3.Connection:
        """
        Create a SQLite connection with proper text encoding.
        
        This handles cross-platform encoding issues where EasyWorship databases
        created on Windows may use Windows-1252 encoding, which causes issues
        on macOS/Linux that expect UTF-8.
        
        Args:
            db_path: Path to the SQLite database file
            
        Returns:
            SQLite connection with proper text encoding configured
        """
        # Ensure db_path is a Path object and convert to string for sqlite3
        if not isinstance(db_path, Path):
            db_path = Path(db_path)
        
        conn = sqlite3.connect(str(db_path))
        
        # Set text factory to handle Windows-1252 encoded text properly
        # This is crucial for Swedish characters (å, ä, ö) to display correctly
        if platform.system() != 'Windows':
            # On non-Windows platforms, assume the data might be Windows-1252 encoded
            # Try UTF-8 first, fall back to Windows-1252 if that fails
            def text_factory(data):
                if data is None:
                    return None
                # First try UTF-8
                try:
                    return data.decode('utf-8')
                except UnicodeDecodeError:
                    # Fall back to Windows-1252 for Windows-created databases
                    try:
                        return data.decode('windows-1252')
                    except UnicodeDecodeError:
                        # Last resort: replace invalid characters
                        return data.decode('utf-8', errors='replace')
            
            conn.text_factory = text_factory
        # On Windows, use default text factory (str is already the default)
        # No need to set it explicitly
        
        return conn
        
    def validate_database(self) -> bool:
        """Check if database files exist and are valid"""
        if not self.songs_db.exists():
            return False
        if not self.words_db.exists():
            return False
        
        try:
            conn = self._get_connection(self.songs_db)
            cursor = conn.execute("SELECT COUNT(*) FROM song")
            cursor.fetchone()
            conn.close()
            
            conn = self._get_connection(self.words_db)
            cursor = conn.execute("SELECT COUNT(*) FROM word")
            cursor.fetchone()
            conn.close()
            
            return True
        except (sqlite3.Error, OSError) as e:
            logger.warning(f"Database validation failed for {self.db_path}: {e}")
            return False
    
    def get_all_songs(self) -> List[Dict[str, Any]]:
        """Retrieve all songs with metadata"""
        conn = self._get_connection(self.songs_db)
        conn.row_factory = sqlite3.Row
        
        query = """
        SELECT 
            rowid,
            title,
            COALESCE(author, '') as author,
            COALESCE(copyright, '') as copyright,
            COALESCE(administrator, '') as administrator,
            COALESCE(reference_number, '') as reference_number,
            COALESCE(tags, '') as tags,
            COALESCE(description, '') as description
        FROM song
        ORDER BY title COLLATE NOCASE
        """
        
        cursor = conn.execute(query)
        songs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return songs
    
    def get_song_lyrics(self, song_rowid: int) -> Optional[str]:
        """Get RTF lyrics for a specific song"""
        conn = self._get_connection(self.words_db)
        
        query = """
        SELECT words 
        FROM word
        WHERE song_id = ?
        """
        
        cursor = conn.execute(query, (song_rowid,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def reload_section_mappings(self):
        """Reload section mappings after they've been changed in settings"""
        # Force section detector to reload on next use
        self.section_detector = None
        logger.info("Section mappings will be reloaded on next use")
    
    def get_song_count(self) -> int:
        """Get total number of songs in database"""
        try:
            conn = self._get_connection(self.songs_db)
            cursor = conn.execute("SELECT COUNT(*) FROM song")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except (sqlite3.Error, OSError) as e:
            logger.warning(f"Could not count songs in {self.songs_db}: {e}")
            return 0
    
    def get_song_with_processed_lyrics(self, song_rowid: int, 
                                     advanced_section_detection: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get a song with fully processed lyrics including RTF parsing and section detection.
        
        Args:
            song_rowid: Row ID of the song in the database
            advanced_section_detection: Whether to use advanced section detection heuristics
            
        Returns:
            Dictionary containing song metadata and processed lyrics, or None if not found
        """
        # Get song metadata
        conn = self._get_connection(self.songs_db)
        conn.row_factory = sqlite3.Row
        
        query = """
        SELECT 
            rowid,
            title,
            COALESCE(author, '') as author,
            COALESCE(copyright, '') as copyright,
            COALESCE(administrator, '') as administrator,
            COALESCE(reference_number, '') as reference_number,
            COALESCE(tags, '') as tags,
            COALESCE(description, '') as description
        FROM song
        WHERE rowid = ?
        """
        
        cursor = conn.execute(query, (song_rowid,))
        song_row = cursor.fetchone()
        conn.close()
        
        if not song_row:
            logger.warning(f"Song with rowid {song_rowid} not found")
            return None
        
        song_data = dict(song_row)
        
        # Get RTF lyrics
        rtf_content = self.get_song_lyrics(song_rowid)
        if not rtf_content:
            logger.debug(f"No lyrics found for song '{song_data['title']}'")
            song_data.update({
                'parsed_lyrics': None,
                'sections': [],
                'has_sections': False,
                'processed_text': ''
            })
            return song_data
        
        # Parse RTF content
        parsed_rtf = parse_rtf(rtf_content)
        if not parsed_rtf or not parsed_rtf.get('has_content'):
            # Check if it's just empty content vs actual parsing failure
            if parsed_rtf is None:
                logger.warning(f"Could not parse RTF content for song '{song_data['title']}' (possible corrupt RTF data)")
            else:
                logger.debug(f"Song '{song_data['title']}' has empty lyrics content")
            
            song_data.update({
                'parsed_lyrics': None,
                'sections': [],
                'has_sections': False,
                'processed_text': ''
            })
            return song_data
        
        # Clean the text
        cleaned_text = clean_text(parsed_rtf['plain_text'], for_song=True)
        
        # Detect sections
        section_data = detect_sections(cleaned_text, advanced=advanced_section_detection)
        
        # Add processed data to song
        song_data.update({
            'parsed_lyrics': parsed_rtf,
            'sections': section_data['sections'],
            'has_sections': section_data['has_sections'],
            'processed_text': cleaned_text
        })
        
        logger.debug(f"Processed song '{song_data['title']}' with {len(section_data['sections'])} sections")
        return song_data
    
    def get_all_songs_with_processed_lyrics(self, 
                                          advanced_section_detection: bool = False) -> List[Dict[str, Any]]:
        """
        Get all songs with processed lyrics.
        
        Args:
            advanced_section_detection: Whether to use advanced section detection heuristics
            
        Returns:
            List of song dictionaries with processed lyrics
        """
        songs = self.get_all_songs()
        processed_songs = []
        
        for song in songs:
            processed_song = self.get_song_with_processed_lyrics(
                song['rowid'], 
                advanced_section_detection
            )
            if processed_song:
                processed_songs.append(processed_song)
        
        logger.info(f"Processed {len(processed_songs)} songs")
        return processed_songs