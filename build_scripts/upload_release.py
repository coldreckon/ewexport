#!/usr/bin/env python3
"""
Upload Executable to GitHub Release
Simple script to upload pre-built executable to existing GitHub release
"""

import os
import sys
import subprocess
import hashlib
from pathlib import Path

def calculate_sha256(file_path):
    """Calculate SHA256 hash of file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def check_github_cli():
    """Check if GitHub CLI is available"""
    try:
        result = subprocess.run(['gh', '--version'], 
                              capture_output=True, text=True, check=True)
        print("✅ GitHub CLI available")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ GitHub CLI not found")
        print("📥 Install from: https://cli.github.com/")
        return False

def list_releases():
    """List recent releases"""
    try:
        result = subprocess.run(['gh', 'release', 'list', '--limit', '10'], 
                              capture_output=True, text=True, check=True)
        print("📋 Recent releases:")
        for line in result.stdout.split('\n')[:5]:  # Show top 5
            if line.strip():
                parts = line.split('\t')
                if len(parts) >= 3:
                    tag = parts[0]
                    status = parts[2]
                    print(f"   {tag} ({status})")
        return True
    except subprocess.CalledProcessError:
        print("❌ Could not list releases")
        return False

def upload_to_release(version, exe_path):
    """Upload executable to GitHub release"""
    print(f"📤 Uploading to release v{version}...")
    
    if not exe_path.exists():
        print(f"❌ Executable not found: {exe_path}")
        return False
    
    # Calculate hash
    sha256 = calculate_sha256(exe_path)
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    
    print(f"📁 File: {exe_path}")
    print(f"📏 Size: {size_mb:.2f} MB") 
    print(f"🔒 SHA256: {sha256}")
    
    try:
        # Upload to release
        subprocess.run([
            'gh', 'release', 'upload', f'v{version}',
            str(exe_path),
            '--clobber'  # Overwrite if exists
        ], check=True)
        
        print(f"✅ Successfully uploaded to release v{version}")
        print(f"🌐 View at: https://github.com/coldreckon/ewexport/releases/tag/v{version}")
        
        # Update release description with hash
        release_body = f"""SHA256: `{sha256}`

**Note**: This executable is built locally with antivirus-friendly settings to reduce false positives.

If your antivirus flags this file:
1. Verify the SHA256 hash matches the one above
2. Add an exception for ewexport.exe
3. See the project README for antivirus guidance"""
        
        # Try to update release notes (optional, don't fail if this doesn't work)
        try:
            subprocess.run([
                'gh', 'release', 'edit', f'v{version}',
                '--notes-file', '-'
            ], input=release_body, text=True, check=True)
            print("📝 Updated release notes with SHA256")
        except (subprocess.SubprocessError, OSError):
            print("⚠️  Could not update release notes (this is OK)")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Upload failed: {e}")
        return False

def main():
    """Main upload process"""
    print("=" * 50)
    print("📤 Upload Executable to GitHub Release")
    print("=" * 50)
    
    # Check prerequisites
    if not check_github_cli():
        return False
    
    # Find executable
    exe_path = Path('dist/ewexport.exe')
    if not exe_path.exists():
        print(f"❌ Executable not found: {exe_path}")
        print("💡 Run 'python build_scripts/build_clean.py' first to build it")
        return False
    
    # List releases
    print()
    list_releases()
    print()
    
    # Get version to upload to
    version = input("Enter version to upload to (e.g., 1.1.6): ").strip()
    if not version:
        print("❌ No version specified")
        return False
    
    # Remove 'v' prefix if provided
    if version.startswith('v'):
        version = version[1:]
    
    # Confirm upload
    print(f"\n📋 Ready to upload:")
    print(f"   File: {exe_path}")
    print(f"   To: Release v{version}")
    
    response = input("\nProceed with upload? (y/n): ").strip().lower()
    if response != 'y':
        print("❌ Upload cancelled")
        return False
    
    # Upload
    if upload_to_release(version, exe_path):
        print("\n🎉 Upload successful!")
        return True
    else:
        print("\n❌ Upload failed")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Upload cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        sys.exit(1)