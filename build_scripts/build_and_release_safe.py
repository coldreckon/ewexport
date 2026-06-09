#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows-Safe Local Build and Release Script for EWExport
Builds the executable locally and uploads to GitHub release
"""

import os
import sys
import shutil
import subprocess
import hashlib
import json
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding issues
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

def get_version():
    """Get version from the centralized version module"""
    sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
    from version import __version__
    return __version__

def calculate_sha256(file_path):
    """Calculate SHA256 hash of file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def clean_build_environment():
    """Clean build environment"""
    print("[CLEAN] Cleaning build environment...")
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if Path(dir_name).exists():
            shutil.rmtree(dir_name)
            print(f"   Removed {dir_name}/")
    
    # Clean .pyc files
    for pyc_file in Path('.').rglob('*.pyc'):
        pyc_file.unlink()
    
    print("   [OK] Environment cleaned")

def build_executable():
    """Build the executable using clean configuration"""
    print("[BUILD] Building executable...")
    
    build_script = Path(__file__).parent / 'build_clean.py'
    
    try:
        result = subprocess.run([
            sys.executable, str(build_script)
        ], check=True, text=True, encoding='utf-8', errors='replace')
        
        print("   [OK] Build completed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"   [ERROR] Build failed: {e}")
        return False
    except FileNotFoundError:
        print(f"   [ERROR] {build_script} not found")
        return False

def verify_executable():
    """Verify the built executable"""
    exe_path = Path('dist/ewexport.exe')
    if not exe_path.exists():
        print("   [ERROR] Executable not found!")
        return False, None
    
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    sha256 = calculate_sha256(exe_path)
    
    print(f"   [INFO] File: {exe_path}")
    print(f"   [INFO] Size: {size_mb:.2f} MB")
    print(f"   [INFO] SHA256: {sha256}")
    
    print("   [OK] Executable verification passed")
    return True, sha256

def create_release_info(version, sha256):
    """Create release information file"""
    release_info = {
        "version": version,
        "build_date": datetime.now().isoformat(),
        "build_machine": "local",
        "sha256": sha256,
        "antivirus_notes": "Built with antivirus-friendly configuration.",
        "python_version": sys.version,
        "build_script": "build_scripts/build_clean.py"
    }
    
    info_file = Path('dist/release_info.json')
    with open(info_file, 'w', encoding='utf-8') as f:
        json.dump(release_info, f, indent=2)
    
    print(f"   [INFO] Created release info: {info_file}")
    return info_file

def check_github_cli():
    """Check if GitHub CLI is available"""
    try:
        subprocess.run(['gh', '--version'], 
                      capture_output=True, text=True, check=True)
        print("   [OK] GitHub CLI available")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("   [ERROR] GitHub CLI not found")
        print("   [INFO] Install from: https://cli.github.com/")
        return False

def create_github_release(version, sha256):
    """Create GitHub release and upload executable"""
    print("[RELEASE] Creating GitHub release...")
    
    if not check_github_cli():
        return False
    
    # Check if release already exists
    try:
        result = subprocess.run(['gh', 'release', 'view', f'v{version}'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"   [WARNING] Release v{version} already exists")
            
            response = input("   Do you want to upload to existing release? (y/n): ")
            if response.lower() != 'y':
                return False
            
            # Upload to existing release
            try:
                subprocess.run([
                    'gh', 'release', 'upload', f'v{version}',
                    'dist/ewexport.exe',
                    'dist/release_info.json',
                    '--clobber'  # Overwrite existing files
                ], check=True)
                
                print("   [OK] Files uploaded to existing release")
                return True
                
            except subprocess.CalledProcessError as e:
                print(f"   [ERROR] Upload failed: {e}")
                return False
    except (subprocess.SubprocessError, OSError):
        pass  # Release doesn't exist, continue to create it
    
    # Create release notes with SHA256
    release_notes = f"""## Manual Release System & Build Improvements

### Download & Security
- **ewexport.exe**: Windows executable ({Path('dist/ewexport.exe').stat().st_size / (1024 * 1024):.2f} MB)
- **SHA256**: `{sha256}`

### Antivirus Information
This executable is built locally with antivirus-friendly settings.

If your antivirus flags this file:
1. Verify the SHA256 hash matches the one above
2. Add an exception for ewexport.exe
3. See ANTIVIRUS.md for detailed guidance

See the GitHub release page for complete details."""
    
    try:
        # Create release
        subprocess.run([
            'gh', 'release', 'create', f'v{version}',
            '--title', f'Release v{version}',
            '--notes', release_notes,
            'dist/ewexport.exe',
            'dist/release_info.json'
        ], check=True)
        
        print(f"   [OK] Release v{version} created successfully")
        print(f"   [INFO] View at: https://github.com/karllinder/ewexport/releases/tag/v{version}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"   [ERROR] Release creation failed: {e}")
        return False

def main():
    """Main build and release process"""
    print("=" * 60)
    print("EWExport Local Build and Release (Windows Safe)")
    print("=" * 60)
    
    # Get version
    version = get_version()
    print(f"[INFO] Building version: {version}")
    
    # Step 1: Clean environment
    clean_build_environment()
    
    # Step 2: Build executable
    if not build_executable():
        print("[ERROR] Build failed - aborting")
        return False
    
    # Step 3: Verify executable
    success, sha256 = verify_executable()
    if not success:
        print("[ERROR] Executable verification failed - aborting")
        return False
    
    # Step 4: Create release info
    create_release_info(version, sha256)
    
    # Step 5: Ask about GitHub release
    print("\n" + "=" * 60)
    print("[RELEASE] Ready to create GitHub release")
    print("=" * 60)
    
    response = input(f"Create GitHub release for v{version}? (y/n): ")
    if response.lower() == 'y':
        if create_github_release(version, sha256):
            print("\n[SUCCESS] Release created and executable uploaded.")
        else:
            print("\n[ERROR] Release creation failed.")
            print("[INFO] You can manually upload dist/ewexport.exe to GitHub releases")
    else:
        print("\n[INFO] Build complete! Files ready in dist/ folder:")
        print("   - dist/ewexport.exe")
        print("   - dist/release_info.json")
        print("\n[INFO] You can manually upload these to GitHub releases")
    
    print("\n" + "=" * 60)
    print("[COMPLETE] Build process complete")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[CANCELLED] Build cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Unexpected error: {e}")
        sys.exit(1)