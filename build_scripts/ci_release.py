#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CI post-sign step: emit dist/release_info.json and release_notes.txt for the
*signed* ewexport.exe.

Run this AFTER the Azure signing step so the recorded SHA256 matches the signed
binary that users actually download. Reuses the CHANGELOG parsing and hashing
helpers from build_and_release.py so the notes stay consistent with local builds.

Usage:
    python build_scripts/ci_release.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Reuse the local release helpers (CHANGELOG parsing + hashing).
sys.path.insert(0, str(Path(__file__).parent))
from build_and_release import calculate_sha256, create_release_notes  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
import version  # noqa: E402

EXE = Path('dist/ewexport.exe')
INFO = Path('dist/release_info.json')
NOTES = Path('release_notes.txt')


def build_footer(sha256: str, size_mb: float) -> str:
    """Verification / publisher footer appended to the release notes."""
    return f"""

## 🔒 File Verification
- **SHA256**: `{sha256}`
- **Size**: {size_mb:.2f} MB
- **Signed**: Digitally signed via Azure Artifact Signing (verified publisher)

## 🛡️ Antivirus & SmartScreen
This executable is **digitally signed**, so Windows shows a verified publisher and
SmartScreen no longer warns about an "unknown publisher". If your antivirus still
flags it, verify the SHA256 above and report the false positive to your vendor.

## 📥 Installation
1. Download `ewexport.exe`
2. Run directly – no installation needed
3. See `README.md` for usage instructions
"""


def main() -> int:
    if not EXE.exists():
        print(f"ERROR: {EXE} not found", file=sys.stderr)
        return 1

    sha256 = calculate_sha256(EXE)
    size_mb = EXE.stat().st_size / (1024 * 1024)
    full_version = version.get_full_version()

    release_info = {
        "version": full_version,
        "build_date": datetime.now(timezone.utc).isoformat(),
        "build_machine": "github-actions",
        "sha256": sha256,
        "signed": True,
        "signing_provider": "Azure Artifact Signing",
        "python_version": sys.version,
        "build_script": "build_scripts/build_clean.py",
    }
    INFO.write_text(json.dumps(release_info, indent=2), encoding='utf-8')
    print(f"Wrote {INFO}")

    # Prefer a CHANGELOG section for the full version; for betas (e.g.
    # 1.4.0-beta.1) that section often doesn't exist, so fall back to the
    # numeric version's section rather than a bare "Release x.y.z" line.
    body = create_release_notes(full_version)
    numeric = version.get_version()
    if body.strip() == f"Release {full_version}" and numeric != full_version:
        alt = create_release_notes(numeric)
        if alt.strip() != f"Release {numeric}":
            body = alt

    NOTES.write_text(body + build_footer(sha256, size_mb), encoding='utf-8')
    print(f"Wrote {NOTES}")

    print(f"SHA256: {sha256}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
