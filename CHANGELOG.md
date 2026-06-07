# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2026-06-06

A maintenance release covering documentation, examples, and CI dependencies.
No library code or API changes.

### Added
- Focused, single-operation example scripts: `add_chunk.py`, `replace_chunk.py`,
  `set_chunk.py`, `copy_chunk.py`, `overwrite_wav.py`, and `complete_workflow.py`,
  plus an `examples/README.md` index.

### Changed
- Trimmed the inline API Reference from `README.md` in favor of the hosted
  documentation site (<https://jmcmeen.github.io/riffy/>).
- Bumped GitHub Actions versions: `actions/setup-python` 5→6,
  `actions/configure-pages` 5→6, `actions/checkout` 4→6,
  `actions/upload-pages-artifact` 3→5, and `actions/deploy-pages` 4→5.

### Removed
- The monolithic `examples/modify_chunks.py` script (split into the focused
  examples above).

## [0.2.0] - 2026-06-06

This release modernizes the project's tooling and packaging and includes a few
small, intentional **breaking changes** to the exception API and supported
Python versions.

### Added
- PEP 561 `py.typed` marker so downstream users get riffy's type hints.
- GitHub Actions CI (lint, format, type-check, and tests on Python 3.10–3.14).
- Automated PyPI publishing via Trusted Publishing (OIDC) on GitHub Releases.
- Documentation site built with MkDocs + Material and deployed to GitHub Pages.
- Project standard files: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`,
  `CHANGELOG.md`, issue/PR templates, Dependabot, pre-commit, and EditorConfig.
- `mypy` and `docs` configuration and dependency extras.

### Changed
- **Breaking:** Non-PCM audio now raises `UnsupportedFormatError` (previously
  `InvalidWAVFormatError`). Both still subclass `WAVError`.
- **Breaking:** Missing required chunks now raise `MissingChunkError` (previously
  `InvalidWAVFormatError` for `fmt `/`data`, or `KeyError` from
  `export_chunk`/`replace_chunk`/`copy_chunk_from_parser`).
- **Breaking:** Invalid chunk IDs now raise `InvalidChunkError` (previously
  `ValueError` from `add_chunk`/`set_chunk`, or `CorruptedFileError` while parsing).
- **Breaking:** Minimum supported Python is now 3.10 (dropped 3.8 and 3.9).
- `parse()` now resets parser state, so re-parsing reflects the file on disk and
  discards any in-memory `add_chunk`/`replace_chunk`/`set_chunk` edits.
- The package version is now single-sourced from `riffy.__version__`.
- Adopted Ruff for both linting and formatting.

### Fixed
- `riffy.__version__` was out of sync with the packaged version (reported `0.1.0`).

### Removed
- Support for Python 3.8 and 3.9.
- `black` from the development dependencies (replaced by `ruff format`).

## [0.1.2] - 2025

### Added
- Chunk modification API: `add_chunk`, `replace_chunk`, `set_chunk`,
  `copy_chunk_from_parser`, and `write_wav` for writing modified WAV files.
- `modify_chunks.py` and `practical_demo.py` examples.

### Changed
- WAV files are now parsed automatically in the `WAVParser` constructor.

## [0.1.1] - 2025

### Added
- Chunk export API (`export_chunk`, `export_audio_data`, `list_chunks`).
- Usage examples and expanded documentation.

## [0.1.0] - 2025

### Added
- Initial release: pure Python WAV/RIFF parser with format validation,
  chunk access, audio metadata extraction, a custom exception hierarchy, and
  full type hints. Zero external dependencies.

[0.2.1]: https://github.com/jmcmeen/riffy/releases/tag/v0.2.1
[0.2.0]: https://github.com/jmcmeen/riffy/releases/tag/v0.2.0
[0.1.2]: https://github.com/jmcmeen/riffy/releases/tag/v0.1.2
[0.1.1]: https://github.com/jmcmeen/riffy/releases/tag/v0.1.1
[0.1.0]: https://github.com/jmcmeen/riffy/releases/tag/v0.1.0
