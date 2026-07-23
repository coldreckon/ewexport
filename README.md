# EasyWorship to ProPresenter Converter

A Windows desktop application that converts songs from EasyWorship 6.1 database format to ProPresenter 6 format with full Swedish and English language support.

## Features

- Read songs from EasyWorship 6.1 SQLite databases (Songs.db & SongWords.db)
- Export to ProPresenter 6 XML format (.pro6)
- Full Swedish character support (å, ä, ö)
- Automatic section detection (Verse, Chorus, Bridge, etc.)
- Configurable Swedish to English section name mapping
- Song preview panel with formatted lyrics and section headers
- Real-time search filtering across all song fields
- Custom font selection from all Windows system fonts
- Configurable slide formatting and line breaks
- Duplicate file detection and handling
- Automatic update checking

## Requirements

- Windows 10 or 11
- EasyWorship 6.1 database files

## Installation

### Download Executable (Recommended)

1. Go to the [Latest Release](https://github.com/coldreckon/ewexport/releases/latest)
2. Download `ewexport.exe`
3. Run it from anywhere - it's completely standalone

**Signed builds**: Release executables are digitally signed via Azure Artifact Signing, so Windows shows a verified publisher and SmartScreen no longer warns about an "unknown publisher". If your antivirus still reports a false positive (uncommon for PyInstaller apps once signed), verify the SHA256 hash from the release page, add an exception if needed, and report the false positive to your vendor.

### Run from Source

1. Clone the repository:
   ```bash
   git clone https://github.com/coldreckon/ewexport.git
   cd ewexport
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python run.py
   ```

## Usage

1. **Load database** - The app auto-detects your EasyWorship database location, or browse to select it manually
2. **Browse songs** - Use the search bar to filter by title, author, copyright, or CCLI number
3. **Preview** - Click any song to see its processed lyrics and detected sections in the preview panel
4. **Select songs** - Use checkboxes or the Select All/None buttons
5. **Configure** - Optionally adjust section mappings (Edit menu) and export options (font, line breaks, slides)
6. **Export** - Choose an output directory and click "Export Selected Songs"

The exported .pro6 files can be imported directly into ProPresenter 6.

## Settings

All application settings are stored in `%APPDATA%\EWExport\` and persist across sessions, including window size, sash position, export preferences, and section mappings.

## Uninstallation

1. Delete `ewexport.exe`
2. Delete the settings folder: `%APPDATA%\EWExport`

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

Based on research from [ew61-export](https://github.com/jamesinglis/ew61-export) PHP implementation.
