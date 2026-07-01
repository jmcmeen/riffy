# Usage

## Parsing a WAV file

The file is parsed automatically when you construct a `WAVParser`:

```python
from riffy import WAVParser

parser = WAVParser("audio.wav")

info = parser.get_info()
print(f"Sample rate: {info['format']['sample_rate']} Hz")
print(f"Channels:    {info['format']['channels']}")
print(f"Bit depth:   {info['format']['bits_per_sample']} bits")
print(f"Duration:    {info['duration_seconds']:.2f} s")
```

## Inspecting chunks

```python
# Each ID maps to a list of occurrences (a file may repeat a chunk ID).
for chunk_id, chunk_list in parser.chunks.items():
    for chunk in chunk_list:
        print(f"{chunk_id!r}: {chunk.size} bytes at offset {chunk.offset}")

# Fetch a single chunk (first occurrence) by ID, or None if absent:
fmt_chunk = parser.get_chunk("fmt ")

# Or get a lightweight summary:
print(parser.list_chunks())
```

## Exporting data

```python
parser.export_audio_data("audio.bin")     # the raw 'data' chunk
parser.export_chunk("fmt ", "format.bin")  # any chunk by ID
```

## Modifying and writing

`WAVParser` can modify chunks in memory and write a valid WAV file back out:

```python
parser = WAVParser("audio.wav")

parser.replace_chunk("data", new_audio_bytes)
parser.add_chunk("INFO", b"Artist: Example\x00")   # IDs are 4 ASCII chars
parser.set_chunk("NOTE", b"recorded 2026\x00")      # add or replace

bytes_written = parser.write_wav("modified.wav")
```

!!! note
    Calling `parse()` again re-reads the file from disk and discards any in-memory
    modifications. `write_wav` orders chunks as `fmt `, `data`, then the rest sorted
    by ID, so a parse/write round-trip is not guaranteed to be byte-identical.

## Reading recorder metadata

For field-recorder files (bat detectors, ARUs), one call surfaces every embedded
metadata standard it finds:

```python
from riffy import read_metadata

meta = read_metadata("recording.wav")
print(meta.sources)          # e.g. ('guano',) or ('info', 'audiomoth')

if meta.guano is not None:
    print(meta.guano.timestamp, meta.guano.loc_position)
```

See the [Recorder Metadata](metadata.md) guide for GUANO, RIFF INFO, Broadcast
Wave `bext`, AudioMoth, and iXML, and the [command-line interface](cli.md) for
the `riffy` tool that inspects, diffs, and edits files from the shell.

## Handling errors

```python
from riffy import WAVParser, RiffyError

try:
    parser = WAVParser("audio.wav")
except RiffyError as e:
    print(f"riffy could not handle this file: {e}")
```

See the [API Reference](api.md) for the full exception hierarchy and method
signatures. For runnable scripts, see the
[`examples/`](https://github.com/jmcmeen/riffy/tree/main/examples) directory.
