# Command-line interface

riffy ships a command-line interface built entirely on the Python standard
library (`argparse`), preserving the zero-dependency promise. Installing the
package exposes a `riffy` command; `python -m riffy …` is always equivalent.

```bash
riffy --help
```

A bare `riffy <file>` (and the historical `riffy --json <file>`) defaults to
`inspect`, so the most common case stays a single word.

## Read commands

### `inspect`

Show the recorder metadata detected in a WAV file.

```bash
riffy inspect recording.wav          # human-readable (also: riffy recording.wav)
riffy inspect recording.wav --json   # JSON-serializable dump
```

### `diff`

Show the chunk- and metadata-level differences between two files.

```bash
riffy diff a.wav b.wav          # text
riffy diff a.wav b.wav --json   # machine-readable
riffy diff a.wav b.wav --all    # include unchanged chunks
```

### `chunks`

List every chunk with its size and byte offset (one row per occurrence, so
duplicate IDs are visible).

```bash
riffy chunks recording.wav
riffy chunks recording.wav --json
```

### `info`

Show the audio format and file details (sample rate, channels, bit depth,
duration, sample count, RIFF form, file size).

```bash
riffy info recording.wav
riffy info recording.wav --json
```

### `export`

Write a chunk's payload, or the raw audio data, to a file.

```bash
riffy export recording.wav --audio audio.raw        # the 'data' payload
riffy export recording.wav --chunk guan guan.bin     # any chunk by ID
```

## Write commands

The mutating commands (`set` and `chunk …`) share one safety contract:

- **Dry run by default** — without `--apply` they report what *would* change and
  touch nothing on disk.
- **`--apply`** commits the change.
- **Atomic writes** — the new file is written to a temp path and `os.replace`d
  into position, so an interrupted run can never leave a half-written file.
- **`--backup`** keeps a `<name>.bak` copy of the original.
- **`--force-rf64`** emits the RF64/BW64 large-file form even when the sizes
  would fit in a classic WAV.
- **`--json`** reports the outcome as `{"status", "path", "changes"}`.

### `set`

Edit recorder-metadata fields across the four editable standards. Selectors are
repeatable and can be mixed in one call:

```bash
# GUANO — 'KEY=VAL', or namespaced 'NS|KEY=VAL'
riffy set bat.wav \
  --guano 'GUANO|Version=1.0' \
  --guano 'Make=Wildlife Acoustics, Inc.' \
  --guano 'Loc Position=36.31119 -82.34027' \
  --guano 'WA|Song Meter|Prefix=SITE7' \
  --apply

# RIFF INFO — by FOURCC
riffy set clip.wav --info 'INAM=Dawn Chorus' --info 'IART=Field Team' --apply
riffy set clip.wav --remove-info ICMT --apply

# Broadcast Wave bext — by attribute name (ints are coerced)
riffy set clip.wav --bext 'description=Dawn chorus' --bext 'version=2' --apply

# Wildlife Acoustics WAMD — 'GPS=<lat> <lon>' for coordinates, or KEY=VAL for text tags
riffy set sm.wav --wamd 'GPS=10.31796 -84.07411' --apply
riffy set sm.wav --wamd 'notes=dawn chorus' --apply
```

Removals: `--remove-guano NS|KEY`, `--remove-info FOURCC`, and `--remove-wamd KEY`
(bext is a fixed struct, so it has no per-field removal). Creating a fresh GUANO
block requires `GUANO|Version` to be set, as the spec mandates. Setting WAMD
`GPS` preserves the existing datum and altitude and leaves every other WAMD entry
byte-stable.

### `chunk`

Modify the raw chunks of a file.

```bash
riffy chunk add clip.wav NOTE note.bin --apply          # append a chunk
riffy chunk replace clip.wav data new_audio.bin --apply # replace existing data
riffy chunk set clip.wav guan guan.bin --apply          # add-or-replace
riffy chunk copy clip.wav guan --from source.wav --apply
riffy chunk remove clip.wav guan --apply                # all occurrences
riffy chunk remove clip.wav LIST --index 0 --apply       # one occurrence
```

## Notes

- Every command accepts `--json` and returns exit code `1` on error (with a
  `riffy: <message>` line on stderr), so the CLI composes cleanly in scripts —
  see `examples/bash/` for worked pipelines.
- The write commands are the CLI face of the library's `WAVParser` write API
  (`set_chunk`, `replace_chunk`, `remove_chunk`, `write_wav`) and the metadata
  classes' `write_to_parser`. See the [API Reference](api.md).
