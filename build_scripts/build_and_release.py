#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Local Build and Release Script for EWExport
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
    # Set environment variables to use UTF-8
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    # Try to set console to UTF-8 if possible
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, OSError):
        pass

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
    """True when this build is a pre-release (beta/rc) -> release marked pre-release"""
    return _load_version_module().is_prerelease()

def get_repo_slug():
    """Resolve the GitHub repo (owner/name) from the gh-detected remote.

    Avoids hardcoding the repo so the script keeps working after a transfer.
    """
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
    print("🔨 Building executable...")
    
    # Use clean build script
    build_script = Path(__file__).parent / 'build_clean.py'
    
    try:
        result = subprocess.run([
            sys.executable, str(build_script)
        ], check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
        
        print("   Build completed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"   Build failed: {e}")
        if e.stdout:
            print(f"   stdout: {e.stdout}")
        if e.stderr:
            print(f"   stderr: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"   ❌ {build_script} not found")
        return False

def verify_executable():
    """Verify the built executable"""
    exe_path = Path('dist/ewexport.exe')
    if not exe_path.exists():
        print("   ❌ Executable not found!")
        return False
    
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    sha256 = calculate_sha256(exe_path)
    
    print(f"   📁 File: {exe_path}")
    print(f"   📏 Size: {size_mb:.2f} MB")
    print(f"   🔒 SHA256: {sha256}")
    
    # Test if executable runs
    try:
        result = subprocess.run([str(exe_path), '--version'],
                              capture_output=True, text=True, timeout=10,
                              encoding='utf-8', errors='replace')
        if result.returncode == 0 or 'ewexport' in result.stderr.lower():
            print("   ✅ Executable verification passed")
            return True, sha256
    except (subprocess.SubprocessError, OSError):
        pass
    
    print("   ⚠️  Executable built but version check failed (this may be normal)")
    return True, sha256

def create_release_notes(version, notes_file=None):
    """Build the release notes body.

    Priority: explicit --notes-file, then a matching CHANGELOG.md section,
    then a minimal fallback.
    """
    if notes_file:
        notes_path = Path(notes_file)
        if notes_path.exists():
            return notes_path.read_text(encoding='utf-8').strip()
        print(f"   ⚠️  Notes file not found: {notes_path} (falling back to CHANGELOG)")

    changelog = Path('CHANGELOG.md')
    if not changelog.exists():
        return f"Release {version}"
    
    try:
        with open(changelog, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find the section for this version
        lines = content.split('\n')
        in_section = False
        notes = []
        
        for line in lines:
            if line.startswith(f'## [{version}]') or line.startswith(f'## {version}'):
                in_section = True
                continue
            elif line.startswith('## ') and in_section:
                break
            elif in_section:
                notes.append(line)
        
        if notes:
            return '\n'.join(notes).strip()
        else:
            return f"Release {version}"
            
    except Exception as e:
        print(f"   ⚠️  Could not extract release notes: {e}")
        return f"Release {version}"

def create_release_info(version, sha256):
    """Create release information file"""
    release_info = {
        "version": version,
        "build_date": datetime.now().isoformat(),
        "build_machine": "local",
        "sha256": sha256,
        "antivirus_notes": "Built with antivirus-friendly configuration. See ANTIVIRUS.md for details.",
        "python_version": sys.version,
        "build_script": "build_scripts/build_clean.py"
    }
    
    info_file = Path('dist/release_info.json')
    with open(info_file, 'w', encoding='utf-8') as f:
        json.dump(release_info, f, indent=2)
    
    print(f"   📋 Created release info: {info_file}")
    return info_file

def check_github_cli():
    """Check if GitHub CLI is available"""
    try:
        result = subprocess.run(['gh', '--version'],
                              capture_output=True, text=True, check=True,
                              encoding='utf-8', errors='replace')
        print("   ✅ GitHub CLI available")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("   ❌ GitHub CLI not found")
        print("   📥 Install from: https://cli.github.com/")
        return False

def enhance_notes(body, sha256):
    """Append the SHA256 / antivirus / install footer to the notes body"""
    size_mb = Path('dist/ewexport.exe').stat().st_size / (1024 * 1024)
    return f"""{body}

## 🔒 File Verification
- **SHA256**: `{sha256}`
- **Size**: {size_mb:.2f} MB
- **Build**: Local build with antivirus-friendly configuration

## 🛡️ Antivirus Information
This executable is built with optimized settings to reduce false positives. If your antivirus flags this file:

1. **Verify the SHA256 hash** matches the one above
2. **Add an exception** for ewexport.exe in your antivirus
3. **Check ANTIVIRUS.md** in the repository for detailed guidance
4. **Report false positives** to your antivirus vendor

## 📥 Installation
1. Download `ewexport.exe`
2. Run directly - no installation needed
3. See `README.md` for usage instructions
"""


def create_github_release(sha256, assume_yes=False, notes_file=None):
    """Create or update the GitHub release for the current version.

    Uses the full version tag (e.g. v1.4.0-beta.1) and marks pre-releases
    with --prerelease. When the release already exists, uploads the assets
    (--clobber) and refreshes the release text.
    """
    print("🚀 Creating GitHub release...")

    if not check_github_cli():
        return False

    tag = get_release_tag()
    prerelease = is_prerelease()
    repo = get_repo_slug()
    notes = enhance_notes(create_release_notes(get_full_version(), notes_file), sha256)
    assets = ['dist/ewexport.exe', 'dist/release_info.json']

    if prerelease:
        print(f"   🧪 Pre-release build -> release will be marked as a pre-release")

    # Does the release already exist?
    exists = subprocess.run(['gh', 'release', 'view', tag],
                            capture_output=True, text=True,
                            encoding='utf-8', errors='replace').returncode == 0

    if exists:
        print(f"   ⚠️  Release {tag} already exists")
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
            print(f"   ✅ Assets uploaded and notes updated on {tag}")
            print(f"   🌐 https://github.com/{repo}/releases/tag/{tag}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Update failed: {e}")
            return False

    # Create a new release
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
        print(f"   ✅ Release {tag} created successfully")
        print(f"   🌐 https://github.com/{repo}/releases/tag/{tag}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Release creation failed: {e}")
        return False

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Build ewexport.exe and (optionally) publish it to a GitHub release. "
                    "The release tag, title and pre-release flag are derived from "
                    "src/version.py (e.g. v1.4.0-beta.1, marked as a pre-release).")
    parser.add_argument('-y', '--yes', action='store_true',
                        help="Skip confirmation prompts (build and publish unattended)")
    parser.add_argument('--no-release', action='store_true',
                        help="Build only; do not create or update a GitHub release")
    parser.add_argument('--notes-file',
                        help="Markdown file to use as the release notes body "
                             "(a verification/antivirus footer is appended automatically)")
    return parser.parse_args(argv)


def main():
    """Main build and release process"""
    args = parse_args()

    print("=" * 60)
    print("EWExport Local Build and Release")
    print("=" * 60)

    full_version = get_full_version()
    tag = get_release_tag()
    track = "pre-release (beta/rc)" if is_prerelease() else "stable"
    print(f"📦 Building version: {full_version}  ->  tag {tag}  [{track}]")

    # Step 1: Clean environment
    clean_build_environment()

    # Step 2: Build executable
    if not build_executable():
        print("❌ Build failed - aborting")
        return False

    # Step 3: Verify executable
    success, sha256 = verify_executable()
    if not success:
        print("❌ Executable verification failed - aborting")
        return False

    # Step 4: Create release info (records the full, pre-release-aware version)
    create_release_info(full_version, sha256)

    # Step 5: GitHub release
    if args.no_release:
        print("\n📁 Build complete (--no-release). Files ready in dist/:")
        print("   - dist/ewexport.exe")
        print("   - dist/release_info.json")
        return True

    print("\n" + "=" * 60)
    print(f"📤 Ready to publish release {tag}")
    print("=" * 60)

    if not args.yes:
        response = input(f"Create/update GitHub release {tag}? (y/n): ")
        if response.lower() != 'y':
            print("\n📁 Skipped release. Files ready in dist/:")
            print("   - dist/ewexport.exe")
            print("   - dist/release_info.json")
            return True

    if create_github_release(sha256, assume_yes=args.yes, notes_file=args.notes_file):
        print("\n🎉 Success! Release published and executable uploaded.")
    else:
        print("\n❌ Release publishing failed.")
        print("💡 You can manually upload dist/ewexport.exe to GitHub releases")
        return False

    print("\n" + "=" * 60)
    print("🏁 Build process complete")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        ok = main()
        sys.exit(0 if ok else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Build cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        sys.exit(1)