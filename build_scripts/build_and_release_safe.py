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
import argparse
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding issues
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

def _load_version_module():
    """Import the centralized version module (single source of truth)"""
    sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
    import version
    return version

def get_version():
    """Get the numeric version (e.g. '1.4.0')"""
    return _load_version_module().__version__

def get_full_version():
    """Get the full version including any pre-release suffix (e.g. '1.4.0-beta.1')"""
    return _load_version_module().get_full_version()

def get_release_tag():
    """Get the GitHub release tag (e.g. 'v1.4.0-beta.1')"""
    return _load_version_module().get_release_tag()

def is_prerelease():
    """True when this build is a pre-release (beta/rc)"""
    return _load_version_module().is_prerelease()

def get_repo_slug():
    """Resolve the GitHub repo (owner/name) from the gh-detected remote"""
    try:
        result = subprocess.run(
            ['gh', 'repo', 'view', '--json', 'nameWithOwner', '-q', '.nameWithOwner'],
            capture_output=True, text=True, check=True, encoding='utf-8', errors='replace')
        slug = result.stdout.strip()
        if slug:
            return slug
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return 'karllinder/ewexport'

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
                      capture_output=True, text=True, check=True,
                      encoding='utf-8', errors='replace')
        print("   [OK] GitHub CLI available")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("   [ERROR] GitHub CLI not found")
        print("   [INFO] Install from: https://cli.github.com/")
        return False

def build_notes(sha256, notes_file=None):
    """Build release notes: --notes-file body (if given) plus a SHA256 footer"""
    size_mb = Path('dist/ewexport.exe').stat().st_size / (1024 * 1024)
    body = None
    if notes_file and Path(notes_file).exists():
        body = Path(notes_file).read_text(encoding='utf-8').strip()
    if not body:
        body = "## EWExport Release"
    return f"""{body}

### Download & Security
- **ewexport.exe**: Windows executable ({size_mb:.2f} MB)
- **SHA256**: `{sha256}`

### Antivirus Information
This executable is built locally with antivirus-friendly settings.

If your antivirus flags this file:
1. Verify the SHA256 hash matches the one above
2. Add an exception for ewexport.exe
3. See ANTIVIRUS.md for detailed guidance"""


def create_github_release(sha256, assume_yes=False, notes_file=None):
    """Create or update the GitHub release for the current version.

    Uses the full version tag (e.g. v1.4.0-beta.1) and marks pre-releases.
    """
    print("[RELEASE] Creating GitHub release...")

    if not check_github_cli():
        return False

    tag = get_release_tag()
    prerelease = is_prerelease()
    repo = get_repo_slug()
    notes = build_notes(sha256, notes_file)
    assets = ['dist/ewexport.exe', 'dist/release_info.json']

    if prerelease:
        print("   [INFO] Pre-release build -> release will be marked as a pre-release")

    exists = subprocess.run(['gh', 'release', 'view', tag],
                            capture_output=True, text=True,
                            encoding='utf-8', errors='replace').returncode == 0

    if exists:
        print(f"   [WARNING] Release {tag} already exists")
        if not assume_yes:
            response = input("   Upload assets and update notes on the existing release? (y/n): ")
            if response.lower() != 'y':
                return False
        try:
            subprocess.run(['gh', 'release', 'upload', tag, *assets, '--clobber'],
                           check=True)
            edit_cmd = ['gh', 'release', 'edit', tag, '--notes', notes]
            if prerelease:
                edit_cmd.append('--prerelease')
            subprocess.run(edit_cmd, check=True)
            print(f"   [OK] Assets uploaded and notes updated on {tag}")
            print(f"   [INFO] View at: https://github.com/{repo}/releases/tag/{tag}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"   [ERROR] Update failed: {e}")
            return False

    create_cmd = [
        'gh', 'release', 'create', tag,
        '--title', f'Release {tag}',
        '--notes', notes,
    ]
    if prerelease:
        create_cmd.append('--prerelease')
    create_cmd += assets

    try:
        subprocess.run(create_cmd, check=True)
        print(f"   [OK] Release {tag} created successfully")
        print(f"   [INFO] View at: https://github.com/{repo}/releases/tag/{tag}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"   [ERROR] Release creation failed: {e}")
        return False

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Build ewexport.exe and (optionally) publish it to a GitHub "
                    "release. Tag/title/pre-release flag derive from src/version.py "
                    "(e.g. v1.4.0-beta.1, marked as a pre-release).")
    parser.add_argument('-y', '--yes', action='store_true',
                        help="Skip confirmation prompts (unattended)")
    parser.add_argument('--no-release', action='store_true',
                        help="Build only; do not create or update a GitHub release")
    parser.add_argument('--notes-file',
                        help="Markdown file to use as the release notes body")
    return parser.parse_args(argv)


def main():
    """Main build and release process"""
    args = parse_args()

    print("=" * 60)
    print("EWExport Local Build and Release (Windows Safe)")
    print("=" * 60)

    full_version = get_full_version()
    tag = get_release_tag()
    track = "pre-release (beta/rc)" if is_prerelease() else "stable"
    print(f"[INFO] Building version: {full_version}  ->  tag {tag}  [{track}]")

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

    # Step 4: Create release info (records the full, pre-release-aware version)
    create_release_info(full_version, sha256)

    # Step 5: GitHub release
    if args.no_release:
        print("\n[INFO] Build complete (--no-release). Files ready in dist/:")
        print("   - dist/ewexport.exe")
        print("   - dist/release_info.json")
        return True

    print("\n" + "=" * 60)
    print(f"[RELEASE] Ready to publish release {tag}")
    print("=" * 60)

    if not args.yes:
        response = input(f"Create/update GitHub release {tag}? (y/n): ")
        if response.lower() != 'y':
            print("\n[INFO] Skipped release. Files ready in dist/:")
            print("   - dist/ewexport.exe")
            print("   - dist/release_info.json")
            return True

    if create_github_release(sha256, assume_yes=args.yes, notes_file=args.notes_file):
        print("\n[SUCCESS] Release published and executable uploaded.")
    else:
        print("\n[ERROR] Release publishing failed.")
        print("[INFO] You can manually upload dist/ewexport.exe to GitHub releases")
        return False

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