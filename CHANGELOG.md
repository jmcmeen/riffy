# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Header-only parsing.** `WAVParser(path, read_audio=False)` records where
  the `data` payload is (`audio_offset`, `audio_size`) without reading it, so
  metadata work on a multi-GB recording costs only its headers, and accepts
  any audio format since the samples are never interpreted. Payloads that
  weren't read are streamed: `write_wav` copies them from the source file in
  blocks (overwriting the source goes through a temporary file),
  `export_chunk`/`export_audio_data` stream them, and the new
  `read_chunk_data`/`iter_chunk_data` read them on demand. `read_metadata`,
  `dump_metadata`, `diff` and every CLI command use this mode; `riffy info` on
  a 659 MB float WAV drops from about 720 MB to 27 MB of memory. A payload
  is only streamed from an unchanged source file; if the file was rewritten
  since it was parsed, riffy raises instead of copying the wrong bytes.
- `WAVChunk.from_file` marks chunks read from the file (their `offset` is
  meaningful), as opposed to ones added or replaced in memory.

- **`WAVE_FORMAT_EXTENSIBLE` and IEEE float WAVs.** 24-bit and multichannel
  recorder files written as extensible with a PCM subformat, and 32/64-bit
  float files (plain format 3, or extensible with the float subformat), now
  parse instead of raising `UnsupportedFormatError`. `WAVFormat` gains
  `subformat`, `valid_bits_per_sample`, `channel_mask`, `is_extensible`,
  `is_float` and `effective_format`; `is_pcm` is true for extensible PCM too.
  `get_info()["format"]` reports them, plus a `description` such as
  `"PCM, extensible"` that both `riffy` and `riffy info` print. The format
  codes are exported as `WAVE_FORMAT_PCM`, `WAVE_FORMAT_IEEE_FLOAT` and
  `WAVE_FORMAT_EXTENSIBLE`.
- `WAVFormat.frame_size` and `WAVFormat.describe()`.
- Float files must be 32 or 64 bits, and an extensible file's valid bits can't
  exceed its container; either problem raises `InvalidWAVFormatError`. A
  `block_align` that doesn't match the channels and bit depth now warns.

### Fixed

- `sample_count` rounds bit depths up to whole bytes, so 12- and 20-bit audio
  are counted correctly (it used to divide by the truncated byte count).
- Replacing the `fmt ` chunk with `replace_chunk`/`set_chunk` re-parses
  `format_info`, so it no longer reports the old format.
- Adding, replacing or removing `data` chunks keeps `audio_data`,
  `audio_size`, `audio_offset` and the duration consistent (adding a `data`
  chunk to a parser that had none used to leave them unset).
- `write_wav` is atomic: it writes a temporary file next to the target and
  moves it into place, so a failure leaves the target untouched and no partial
  file behind. Writing through a symlink updates the real file, and an
  existing file keeps its permissions.

### Changed

- `WAVChunk.data` is `bytes | None`: `None` for a `data` chunk parsed with
  `read_audio=False`. Code reading other chunks is unaffected; use
  `WAVParser.read_chunk_data(chunk)` to read any payload.

## [0.3.4] - 2026-10-27

### Added

- CI tests and PyPI classifiers cover Python 3.15.

## [0.3.1] - 2026-07-01

Wildlife Acoustics WAMD metadata support — read and write the `wamd` chunk (and
its WAMD-in-`junk` variant), closing the last location dialect riffy could not
correct on legacy Song Meter recordings.

### Added

- **Wildlife Acoustics WAMD metadata (read/write).** Parse the packed-binary
  `wamd` chunk — and the WAMD-in-`junk` variant older firmware emits — into a
  `WamdMetadata` view exposing `loc_position` as a `(lat, lon)` tuple plus
  `model`, `serial`, `firmware`, `timestamp`, and the other tags. `"wamd"` now
  appears in `read_metadata().sources`, in the `python -m riffy` inspector, and
  in `diff`. Unknown tags, binary blobs, and alignment padding round-trip
  byte-for-byte, so an edit touches only the field you change.
- **`riffy set … --wamd`.** Write WAMD fields under the same safety contract as
  GUANO/INFO/bext (dry run by default, atomic replace, `--backup`,
  `--force-rf64`): `riffy set FILE --wamd 'GPS=<lat> <lon>'` for coordinates, or
  `KEY=VAL` for the other text tags, with `--remove-wamd KEY` to delete one.

## [0.3.0] - 2026-07-01

Recorder metadata parsing (GUANO, RIFF INFO, Broadcast Wave `bext`, AudioMoth,
iXML) plus RF64/BW64 large-file support, built on a fixed multi-chunk-per-ID
core (the one breaking change — see below).

### Changed

- **BREAKING: the chunk store now keeps every occurrence of a chunk ID.**
  `WAVParser.chunks` changed from `dict[str, WAVChunk]` to
  `dict[str, list[WAVChunk]]`, so files carrying duplicate top-level IDs (for
  example multiple `LIST` chunks) preserve all occurrences in file order instead
  of silently keeping only the last one.

  Migration:
  - `parser.chunks["fmt "]` (a `WAVChunk`) → `parser.get_chunk("fmt ")` (the
    first occurrence, or `None`), or `parser.chunks["fmt "][0]`.
  - Iterating `for cid, chunk in parser.chunks.items()` → iterate the inner
    list: `for cid, chunk_list in parser.chunks.items(): for chunk in chunk_list:`.
  - `get_info()["chunks"]` values changed from `int` (a size) to `list[int]`
    (one size per occurrence).
  - `list_chunks()` values changed from `{"size", "offset"}` to a list of such
    dicts, one per occurrence.
  - `add_chunk()` no longer raises `ValueError` when the ID already exists; it
    appends a new occurrence. Use `set_chunk()` to add-or-replace the first
    occurrence, or `replace_chunk()` to overwrite it.

### Added

- **RF64 / BW64 large-file support.** `WAVParser` now recognizes the `RF64`
  (EBU Tech 3306) and `BW64` (ITU-R BS.2088) forms, parses the leading `ds64`
  chunk for 64-bit sizes, and honors the `0xFFFFFFFF` size sentinel (resolving
  `data` from the ds64 field and other oversized chunks from its size table).
  On write, output switches to the RF64/BW64 form only when a size crosses the
  4 GB 32-bit limit (or when the new `write_wav(force_rf64=True)` is set),
  emitting a `ds64` chunk and the size sentinel; otherwise classic WAV output is
  byte-for-byte unchanged. New `WAVParser.is_rf64` / `WAVParser.riff_form`
  expose the parsed form. Scoped to PCM as before.
- `WAVParser.get_chunk(id)` — the first chunk with an ID, or `None`.
- `WAVParser.get_chunks(id)` — every chunk with an ID, in file order.
- `WAVParser.get_chunk_bytes(id)` — the raw payload of the first chunk with an
  ID (the accessor the forthcoming metadata layer decodes from).
- `riffy.metadata` subpackage scaffolding with shared low-level primitives in
  `riffy.metadata.base`: `validate_fourcc`, `pad_to_even`, `read_zstr`,
  `write_zstr`, and `decode_text` (UTF-8 with fail-soft latin-1 fallback). These
  are the building blocks the per-standard metadata decoders build on.
- **GUANO read/write** (`riffy.metadata.GuanoMetadata`) — full support for the
  `guan` chunk: `from_parser` / `from_bytes` to read, `to_chunk_bytes` /
  `write_to_parser` to write. Well-known fields are typed attributes
  (`timestamp` as a timezone-aware `datetime` with its offset preserved,
  `loc_position` as a `(lat, lon)` tuple, `species_manual_id` / `tags` as lists,
  plus typed strings/ints/floats); vendor and arbitrary fields are reachable via
  `get` / `set` / `fields` and are **preserved verbatim and in order** on
  round-trip, as the spec requires. `GUANO|Version` is always serialized first,
  multiline values are `\n`-escaped, output is even-padded, and non-UTF-8
  payloads fall back to latin-1 with a warning.
- **RIFF INFO read/write** (`riffy.metadata.InfoMetadata`) — decodes the
  `LIST`/`INFO` block into friendly attributes (`title`, `artist`, `comment`,
  `software`, ...) mapped from the standard FOURCCs, with raw FOURCC access via
  `get` / `set` / `tags`. Tolerates NUL-terminated and non-terminated values,
  honors even-byte padding, and is truncation-safe. When a file has several
  `LIST` chunks, `from_parser` selects the `INFO` one and `write_to_parser`
  updates only it, leaving other lists (e.g. `adtl`) untouched. This is also the
  carrier the forthcoming AudioMoth comment decoder reads from.
- **Broadcast Wave `bext` read/write** (`riffy.metadata.BextMetadata`) — parses
  the fixed EBU Tech 3285 binary layout into typed fields (description,
  originator, origination date/time, 64-bit `time_reference`, `umid`, and the v2
  loudness fields), with version gating: `umid` requires v1+, loudness requires
  v2+. Writing is table-driven off `version`, zero-fills regions the version
  does not define, and preserves loudness values verbatim (never computed).
  Tolerates truncated chunks and NUL-padded strings.
- **AudioMoth comment decoding** (`riffy.metadata.AudioMothMetadata`) — decodes
  the free-text firmware comment string (RIFF INFO `ICMT`, device string in
  `IART`) into structured fields: recording timestamp (day-first, timezone-aware
  with UTC offset), device/deployment ID, gain (numeric settings normalized to
  the `low`…`high` word scale), battery, temperature, external-mic flag,
  amplitude threshold / trigger duration, frequency filter, and
  recording-stopped reason. Each field is parsed with its own tolerant regex, so
  extraction is **partial**: a failure in one clause never discards the others.
  A `to_guano()` helper maps the parsed fields onto GUANO-equivalent keys
  (a within-standard normalization). Format knowledge is derived from the
  `metamoth` library and the AudioMoth firmware source, and validated against
  real device recordings (firmware ~1.0.1 and 1.6.0).
- **iXML read support** (`riffy.metadata.IXmlMetadata`) — parses the `iXML`
  chunk (a UTF-8 XML document used by production recorders such as Sound Devices
  and Zoom for take/scene/track metadata) into an inspectable element tree:
  `from_parser` / `from_bytes` to read, `find(path)` for a single ElementTree
  path lookup, and `to_dict()` for a nested dict (repeated child tags collapse to
  lists). NUL padding is trimmed and non-XML payloads are skipped with a warning.
  Read-only for v0.3.0 (authoring is out of scope), and — per riffy's
  zero-dependency promise — parsing uses the standard-library XML parser, which
  is not hardened against hostile XML; iXML from field recorders is treated as
  trusted input. Surfaced in the `python -m riffy` / `dump_metadata` dict output
  under `ixml`; not part of the `RecordingMetadata` dataclass since it is
  read-only.
- **File diffing** — `riffy.diff(a, b)` returns a `WavDiff` comparing two WAV
  files at two levels: per-chunk deltas (added / removed / changed / unchanged,
  compared occurrence-by-occurrence and insensitive to chunk reordering) and a
  decoded per-standard metadata field diff (GUANO, RIFF INFO, `bext`). The CLI
  gains `python -m riffy diff A B` (with `--json` / `--all`), and the batch
  example (`examples/batch_correct_guano.py`) gains a `--verify` flag that uses
  the diff to confirm an edit changed only the intended field and left the audio
  untouched. Useful for verifying and validating bulk metadata edits.
- **Unified metadata view** — `riffy.read_metadata(path)` returns a
  `RecordingMetadata` exposing each detected standard side by side (`.guano`,
  `.info`, `.bext`, `.audiomoth`, each `None` when absent) plus `.sources`
  listing which were present. It deliberately does **no** cross-standard
  reconciliation — it surfaces each standard close to its raw parsed form and
  leaves precedence/merging policy to downstream consumers. All new metadata
  classes are also re-exported from the top-level `riffy` package.
- **Expanded command-line interface** — the `riffy` CLI grows from the
  inspect/diff pair into a full surface over the library (still argparse-only,
  zero dependencies):
  - Read commands: `chunks` (list every chunk with size/offset), `info` (audio
    format and file details), and `export` (`--chunk ID` or `--audio` to a
    file). Both `inspect` and `diff` remain, and a bare `riffy <file>` still
    defaults to `inspect`.
  - Write commands, sharing one safety contract — **dry run by default**, atomic
    writes (temp file + `os.replace`), `--apply` to commit, `--backup` to keep a
    `.bak`, `--force-rf64` for the large-file form: `set` edits GUANO / RIFF INFO
    / `bext` fields (`--guano NS|KEY=VAL`, `--info FOURCC=VAL`, `--bext ATTR=VAL`,
    plus `--remove-guano` / `--remove-info`), and `chunk add|replace|set|copy|remove`
    modify chunks.
  - Packaging: a `riffy` console entry point (`[project.scripts]`), so `riffy …`
    works alongside `python -m riffy …`.
- **`WAVParser.remove_chunk(id, index=None)`** — remove one occurrence, or every
  occurrence, of a chunk ID; backs the CLI `chunk remove` command.
- **Examples split into `examples/python/` and `examples/bash/`.** The Python
  scripts moved under `python/`; a parallel `bash/` suite drives the `riffy` CLI
  to demonstrate the same operations from the shell. The Makefile gains
  `examples-python` and `examples-bash` targets (with `examples` running both).

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

[Unreleased]: https://github.com/jmcmeen/riffy/compare/v0.3.4...HEAD
[0.3.4]: https://github.com/jmcmeen/riffy/compare/v0.3.3...v0.3.4
[0.3.1]: https://github.com/jmcmeen/riffy/releases/tag/v0.3.1
[0.3.0]: https://github.com/jmcmeen/riffy/releases/tag/v0.3.0
[0.2.1]: https://github.com/jmcmeen/riffy/releases/tag/v0.2.1
[0.2.0]: https://github.com/jmcmeen/riffy/releases/tag/v0.2.0
[0.1.2]: https://github.com/jmcmeen/riffy/releases/tag/v0.1.2
[0.1.1]: https://github.com/jmcmeen/riffy/releases/tag/v0.1.1
[0.1.0]: https://github.com/jmcmeen/riffy/releases/tag/v0.1.0
