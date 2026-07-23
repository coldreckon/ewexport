"""
Build script for creating ewexport.exe using PyInstaller
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# Add src to path so we can import the version module
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
from version import __version__, get_version_tuple, RELEASE_YEAR

def clean_build_dirs():
    """Clean previous build artifacts"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"Cleaning {dir_name}...")
            try:
                shutil.rmtree(dir_name)
            except PermissionError as e:
                print(f"Warning: Could not clean {dir_name}: {e}")
                print("Make sure the executable is not running and try again.")
    
    # Clean .spec file if exists
    spec_file = Path('ewexport.spec')
    if spec_file.exists():
        spec_file.unlink()
        print("Removed old spec file")

def build_executable():
    """Build the executable using PyInstaller"""
    
    # Ensure we're in the project root
    build_script_dir = Path(__file__).parent
    project_root = build_script_dir.parent
    os.chdir(project_root)
    
    # Check if version file exists
    version_file = build_script_dir / 'version_info.py'
    icon_file = build_script_dir.parent / 'assets' / 'ewexport.ico'

    # PyInstaller command with options
    pyinstaller_args = [
        'pyinstaller',
        '--onefile',           # Single executable file
        '--windowed',          # No console window (GUI app)
        '--name=ewexport',     # Name of the executable
        '--clean',             # Clean PyInstaller cache
        '--noconfirm',         # Overwrite output without confirmation
        '--noupx',             # Don't use UPX compression (reduces false positives)
        
        # Add version information for Windows
        f'--version-file={version_file}' if version_file.exists() else None,

        # Application icon
        f'--icon={icon_file}' if icon_file.exists() else None,

        # Add data files (use semicolon on Windows, colon on Unix)
        '--add-data=config;config',
        
        # Hidden imports that PyInstaller might miss
        '--hidden-import=tkinter',
        '--hidden-import=striprtf',
        '--hidden-import=packaging',
        '--hidden-import=customtkinter',
        '--hidden-import=darkdetect',
        '--hidden-import=PIL',
        '--hidden-import=PIL.Image',
        '--hidden-import=PIL.ImageTk',

        # Bundle customtkinter theme/asset files
        '--collect-data=customtkinter',

        # Exclude unnecessary modules to reduce size and complexity
        # (PIL must NOT be excluded - customtkinter imports PIL.Image)
        '--exclude-module=matplotlib',
        '--exclude-module=numpy',
        '--exclude-module=scipy',
        '--exclude-module=pandas',
        
        # Paths
        '--distpath=dist',
        '--workpath=build',
        '--specpath=.',
        
        # Main script
        'src/main.py'
    ]
    
    # Remove None values from args
    pyinstaller_args = [arg for arg in pyinstaller_args if arg is not None]
    
    print("Building executable with PyInstaller...")
    print(f"Command: {' '.join(pyinstaller_args)}")
    
    try:
        result = subprocess.run(pyinstaller_args, check=True)
        print("\nBuild successful!")
        
        exe_path = Path('dist/ewexport.exe')
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"Executable created: {exe_path}")
            print(f"Size: {size_mb:.2f} MB")
            return True
        else:
            print("ERROR: Executable not found after build!")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        return False
    except FileNotFoundError:
        print("ERROR: PyInstaller not found. Install it with: pip install pyinstaller")
        return False

def create_version_file():
    """Create a version info file for Windows using centralized version"""
    ver_tuple = get_version_tuple()
    major, minor, patch = ver_tuple[0], ver_tuple[1], ver_tuple[2] if len(ver_tuple) > 2 else 0

    version_content = f"""
# UTF-8
#
# For more information about the PyInstaller version file format,
# see: https://pyinstaller.readthedocs.io/en/stable/usage.html#windows
# Version auto-generated from src/version.py

VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, 0),
    prodvers=({major}, {minor}, {patch}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'EWExport'),
        StringStruct(u'FileDescription', u'EasyWorship to ProPresenter Converter'),
        StringStruct(u'FileVersion', u'{__version__}.0'),
        StringStruct(u'InternalName', u'ewexport'),
        StringStruct(u'LegalCopyright', u'Copyright (c) {RELEASE_YEAR}'),
        StringStruct(u'OriginalFilename', u'ewexport.exe'),
        StringStruct(u'ProductName', u'EasyWorship to ProPresenter Converter'),
        StringStruct(u'ProductVersion', u'{__version__}.0')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""

    with open('dist/version_info.txt', 'w') as f:
        f.write(version_content)
    print(f"Created version info file (version {__version__})")

def main():
    """Main build process"""
    print("=" * 60)
    print("EWExport Build Script")
    print("=" * 60)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("ERROR: Python 3.8 or higher is required")
        sys.exit(1)
    
    # Clean previous builds
    clean_build_dirs()
    
    # Create version file (optional, for future use)
    # create_version_file()
    
    # Build the executable
    success = build_executable()
    
    if success:
        print("\n" + "=" * 60)
        print("BUILD SUCCESSFUL!")
        print("Executable is located in: dist/ewexport.exe")
        print("You can now:")
        print("1. Test the executable locally")
        print("2. Upload it to GitHub releases")
        print("3. Distribute it to users")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("BUILD FAILED!")
        print("Check the error messages above")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()