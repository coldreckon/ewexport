# Changelog

All notable changes to **EWExport** (EasyWorship to ProPresenter Converter) are documented
in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.4.0] - 2026-07-29

First stable release of the CustomTkinter GUI, now shipped as a **digitally signed**
Windows executable. (Previewed as `1.4.0-beta.1` on 2026-06-10.)

### Added
- Reworked the entire GUI on **CustomTkinter** for a modern look: main window, settings
  window, and export dialogs, plus a theme module for appearance and `ttk` styling.
- Digitally signed Windows releases via **Azure Artifact Signing** (organization / Public
  Trust). Signed builds show the verified publisher "Saronförsamlingen i Göteborg" and no
  longer trigger the SmartScreen "unknown publisher" warning.
- Application icon embedded in `ewexport.exe`.
- CI pipeline (`.github/workflows/build-release.yml`) that builds, signs, verifies, and
  publishes the executable to the GitHub Release on a version tag.
- Beta / pre-release track support in the local release scripts (`v*-beta.N` tags marked as
  pre-releases).
- Baseline GUI unit tests.

### Fixed
- Song list pane no longer collapses to zero width.
- Decode `gh` CLI output as UTF-8 in the release scripts.

### Changed
- Releases are now built and signed by CI instead of being built locally and uploaded
  manually. The local build scripts remain for development and produce unsigned binaries.
- Bundle CustomTkinter + Pillow assets in the build; regenerate the Windows version resource
  from `src/version.py` (single source of truth).

## [1.3.2] - 2026-05

### Fixed
- Hardened update-URL handling and custom-rename path construction.

### Changed
- Repository hygiene: removed stray files, extended `.gitignore`, extracted section-mappings
  config into `src/utils/section_mappings.py`, and deduplicated exporter XML serialization.

## [1.3.1] - 2026-02-20

### Changed
- Consolidated root Markdown documentation into `README`.

## [1.3.0] - 2026-02-20

### Added
- Song preview panel showing lyrics and detected sections (#10).

## [1.2.9] - 2026-02-20

### Fixed
- Security cleanup and dead-code removal.

## [1.2.8] - 2025-11-28

### Added
- Default duplicate-handling option in Export Options (#38, #39).
- Complete English/Swedish section mappings for new users (#36, #37).

## [1.2.7] - 2025-11-28

### Fixed
- Show the correct message when files are skipped during export (#33).

## [1.2.6] - 2025-11-25

### Fixed
- Version comparison and cross-platform path handling (#28–#31).

## [1.2.5] - 2025-08-17

### Fixed
- Code-quality improvements and a centralized version module (#21, #23, #24).
- Proper thread cancellation during export (#20, #22).

## [1.2.0] - 2025-08-14

### Added
- Export-options and duplicate-handling improvements.

## [1.1.0] - 2025-08-10

### Added
- Feature and stability improvements over the initial release.

## [1.0.0] - 2025-08-09

### Added
- First stable release: convert songs from EasyWorship 6.1 to ProPresenter 6 format.

## [0.1.0] - 2025-08-07

### Added
- Initial public release.

[Unreleased]: https://github.com/coldreckon/ewexport/compare/v1.4.0...HEAD
[1.4.0]: https://github.com/coldreckon/ewexport/releases/tag/v1.4.0
[1.3.1]: https://github.com/coldreckon/ewexport/releases/tag/v1.3.1
[1.3.0]: https://github.com/coldreckon/ewexport/releases/tag/v1.3.0
[1.2.9]: https://github.com/coldreckon/ewexport/releases/tag/v1.2.9
[1.2.8]: https://github.com/coldreckon/ewexport/releases/tag/v1.2.8
[1.2.7]: https://github.com/coldreckon/ewexport/releases/tag/v1.2.7
[1.2.6]: https://github.com/coldreckon/ewexport/releases/tag/v1.2.6
[1.2.5]: https://github.com/coldreckon/ewexport/releases/tag/v1.2.5
[1.2.0]: https://github.com/coldreckon/ewexport/releases/tag/v1.2.0
[1.1.0]: https://github.com/coldreckon/ewexport/releases/tag/v1.1.0
[1.0.0]: https://github.com/coldreckon/ewexport/releases/tag/v1.0.0
[0.1.0]: https://github.com/coldreckon/ewexport/releases/tag/v0.1.0
