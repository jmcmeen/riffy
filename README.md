# riffy

[![PyPI version](https://img.shields.io/pypi/v/riffy.svg)](https://pypi.org/project/riffy/)
[![Python versions](https://img.shields.io/pypi/pyversions/riffy.svg)](https://pypi.org/project/riffy/)
[![CI](https://github.com/jmcmeen/riffy/actions/workflows/ci.yml/badge.svg)](https://github.com/jmcmeen/riffy/actions/workflows/ci.yml)
[![Docs](https://github.com/jmcmeen/riffy/actions/workflows/docs.yml/badge.svg)](https://jmcmeen.github.io/riffy/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Riffy provides a pure Python implementation for working with RIFF format files, with initial support for WAV audio files. The library is designed to have **zero external dependencies** while providing robust parsing capabilities for reading, modifying, and writing RIFF chunks.

## Features

- **Zero Dependencies**: Pure Python implementation with no external dependencies
- **WAV File Support**: Complete WAV file parsing with format validation
- **RIFF Chunk Management**: Access, add, replace, copy, and remove RIFF chunks
- **Chunk Modification & Writing**: Modify chunks in memory and write valid WAV files back to disk
- **Audio Metadata Extraction**: Extract sample rate, channels, bit depth, and duration
- **Format Validation**: Automatic validation of file format and integrity
- **Type Safety**: Full type hints (PEP 561 `py.typed`) for better IDE support and static analysis
- **Lightweight**: Minimal footprint, perfect for embedded systems or restricted environments

## Installation

### From PyPI

```bash
pip install riffy
```

### From Source

```bash
# Clone the repository
git clone https://github.com/jmcmeen/riffy.git
cd riffy

# Install in development mode
pip install -e .

# Or build and install
pip install build
python -m build
pip install dist/riffy-*.whl
```

### For Development

```bash
# Install with development dependencies
pip install -e ".[dev]"
```

## Quick Start

### Basic WAV File Parsing

```python
from riffy import WAVParser

# Parse a WAV file (parsing happens automatically on initialization)
parser = WAVParser("audio.wav")

# Access format information
info = parser.get_info()
print(f"Sample Rate: {info['format']['sample_rate']} Hz")
print(f"Channels: {info['format']['channels']}")
print(f"Bit Depth: {info['format']['bits_per_sample']} bits")
print(f"Duration: {info['duration_seconds']:.2f} seconds")
```

### Accessing RIFF Chunks

```python
from riffy import WAVParser

# Parsing happens automatically on initialization
parser = WAVParser("audio.wav")

# Access all chunks
for chunk_id, chunk in parser.chunks.items():
    print(f"Chunk: {chunk_id}, Size: {chunk.size} bytes, Offset: {chunk.offset}")

# Access specific chunk
if 'fmt ' in parser.chunks:
    fmt_chunk = parser.chunks['fmt ']
    print(f"Format chunk size: {fmt_chunk.size}")
```

### Working with Audio Data

```python
from riffy import WAVParser

# Parsing happens automatically on initialization
parser = WAVParser("audio.wav")

# Access raw audio data
audio_data = parser.audio_data
print(f"Audio data size: {len(audio_data)} bytes")

# Get sample count
info = parser.get_info()
print(f"Total samples: {info['sample_count']}")
```

### Exporting Chunks to Binary Files

```python
from riffy import WAVParser

# Parsing happens automatically on initialization
parser = WAVParser("audio.wav")

# Export raw audio data (most common use case)
bytes_written = parser.export_audio_data("raw_audio.bin")
print(f"Exported {bytes_written} bytes of audio data")

# Export specific chunks
parser.export_chunk('fmt ', "format_chunk.bin")
parser.export_chunk('data', "data_chunk.bin")

# List all available chunks before exporting
chunks = parser.list_chunks()
for chunk_id, info in chunks.items():
    print(f"Chunk '{chunk_id}': {info['size']} bytes at offset {info['offset']}")
```

### Modifying and Writing WAV Files

Riffy can modify chunks in memory and write a valid WAV file back to disk:

```python
from riffy import WAVParser

parser = WAVParser("audio.wav")

# Replace the audio data with new bytes
parser.replace_chunk('data', new_audio_bytes)

# Add a custom metadata chunk (IDs must be exactly 4 ASCII characters)
parser.add_chunk('INFO', b'Artist: Example\x00')

# set_chunk adds the chunk if missing, or replaces it if present
parser.set_chunk('NOTE', b'recorded 2026\x00')

# Copy a chunk from another file
other = WAVParser("other.wav")
parser.copy_chunk_from_parser('data', other)

# Write the modified file (overwrite=False refuses to clobber the source)
bytes_written = parser.write_wav("modified.wav")
print(f"Wrote {bytes_written} bytes")
```

> **Note:** `write_wav` always writes the `fmt ` chunk first, then `data`, then any
> remaining chunks in sorted order, so the output is not guaranteed to be byte-for-byte
> identical to the input. See [Limitations](#limitations).

### Getting Detailed File Information

```python
from riffy import WAVParser
import json

# Parsing happens automatically on initialization
parser = WAVParser("audio.wav")
info = parser.get_info()

# Pretty print all information
print(json.dumps(info, indent=2))
```

Output example:

```json
{
  "file_path": "/path/to/audio.wav",
  "file_size": 1234567,
  "format": {
    "audio_format": 1,
    "channels": 2,
    "sample_rate": 44100,
    "byte_rate": 176400,
    "block_align": 4,
    "bits_per_sample": 16,
    "is_pcm": true
  },
  "duration_seconds": 3.5,
  "audio_data_size": 617400,
  "sample_count": 154350,
  "chunks": {
    "fmt ": 16,
    "data": 617400
  }
}
```

## API Reference

> Full, auto-generated API documentation is available at
> **<https://jmcmeen.github.io/riffy/>**.

### WAVParser

The main class for parsing WAV files.

#### Constructor

```python
WAVParser(file_path: str | Path)
```

**Parameters:**

- `file_path`: Path to the WAV file (string or `pathlib.Path`)

**Note:** The file is automatically parsed during initialization.

**Raises (during initialization):**

- `FileNotFoundError`: If the file doesn't exist
- `InvalidWAVFormatError`: If the file is not a valid WAV file
- `UnsupportedFormatError`: If the audio format is not PCM
- `CorruptedFileError`: If the file is corrupted or incomplete
- `MissingChunkError`: If a required (`fmt `/`data`) chunk is absent
- `InvalidChunkError`: If a chunk ID is not valid 4-character ASCII

#### Methods

##### `get_info() -> dict`

Get comprehensive information about the parsed WAV file.

**Returns:** Dictionary with file metadata

##### `parse() -> dict`

Re-parse the WAV file and return comprehensive information. The file is parsed
automatically during initialization; calling `parse()` again re-reads the file
from disk and **discards any in-memory modifications** made with `add_chunk`,
`replace_chunk`, or `set_chunk`.

**Returns:** Dictionary containing file information, format details, and chunk data

##### `export_chunk(chunk_id: str, output_path: str | Path) -> int`

Export a specific chunk's data to a binary file.

**Returns:** Number of bytes written

**Raises:** `MissingChunkError` if the specified chunk doesn't exist

##### `export_audio_data(output_path: str | Path) -> int`

Export raw audio data (the `data` chunk) to a binary file. Convenience wrapper
around `export_chunk('data', ...)`.

**Returns:** Number of bytes written

**Raises:** `WAVError` if no audio data exists

##### `list_chunks() -> dict[str, dict[str, int]]`

List all chunks with their sizes and offsets.

**Returns:** Dictionary mapping chunk IDs to their metadata (size and offset)

##### `replace_chunk(chunk_id: str, new_data: bytes) -> None`

Replace an existing chunk's data with new data. Replacing the `data` chunk
recalculates the duration.

**Raises:** `MissingChunkError` if the chunk doesn't exist

##### `add_chunk(chunk_id: str, chunk_data: bytes) -> None`

Add a new chunk. The chunk ID must be exactly 4 ASCII characters.

**Raises:** `InvalidChunkError` if the ID is malformed; `ValueError` if the chunk already exists

##### `set_chunk(chunk_id: str, chunk_data: bytes) -> None`

Add the chunk if it doesn't exist, or replace it if it does.

**Raises:** `InvalidChunkError` if the ID is malformed

##### `copy_chunk_from_parser(chunk_id: str, source_parser: WAVParser) -> None`

Copy a chunk from another `WAVParser` instance.

**Raises:** `MissingChunkError` if the chunk doesn't exist in the source parser

##### `write_wav(output_path: str | Path, overwrite: bool = False) -> int`

Reconstruct and write the (possibly modified) WAV file to disk, updating the RIFF
size and chunk layout.

**Returns:** Number of bytes written

**Raises:** `FileExistsError` if writing over the source without `overwrite=True`;
`MissingChunkError` if the required `fmt `/`data` chunks are missing

#### Properties

- `format_info`: `WAVFormat` object containing format details
- `chunks`: Dictionary of `WAVChunk` objects keyed by chunk ID
- `audio_data`: Raw audio data as bytes

### WAVFormat

Dataclass containing WAV format information.

**Attributes:**

- `audio_format`: Audio format code (1 = PCM)
- `channels`: Number of audio channels
- `sample_rate`: Sample rate in Hz
- `byte_rate`: Bytes per second
- `block_align`: Block alignment in bytes
- `bits_per_sample`: Bits per sample
- `duration_seconds`: Audio duration in seconds (computed during parsing)

**Properties:**

- `is_pcm`: Boolean indicating if format is PCM (uncompressed)

### WAVChunk

Dataclass representing a RIFF chunk.

**Attributes:**

- `id`: Chunk identifier (e.g., "fmt ", "data")
- `size`: Chunk size in bytes
- `data`: Raw chunk data
- `offset`: Byte offset in the file

## Exception Hierarchy

```text
RiffyError (base exception)
├── WAVError
│   ├── InvalidWAVFormatError
│   ├── CorruptedFileError
│   └── UnsupportedFormatError
└── ChunkError
    ├── InvalidChunkError
    └── MissingChunkError
```

### Exception Handling

```python
from riffy import (
    WAVParser,
    InvalidWAVFormatError,
    UnsupportedFormatError,
    CorruptedFileError,
    MissingChunkError,
)

try:
    parser = WAVParser("audio.wav")
except InvalidWAVFormatError as e:
    print(f"Invalid WAV format: {e}")
except UnsupportedFormatError as e:
    print(f"Unsupported audio format: {e}")
except CorruptedFileError as e:
    print(f"File is corrupted: {e}")
except MissingChunkError as e:
    print(f"Required chunk missing: {e}")
except FileNotFoundError:
    print("File not found")
```

All riffy exceptions inherit from `RiffyError`, so `except RiffyError` catches every
library-specific error.

## Supported Formats

Currently, Riffy supports:

- **WAV Files**: PCM (uncompressed) audio only
- **RIFF Chunks**: Standard chunk parsing, modification, and writing for WAV files

### Planned Support

- AVI files
- WebP images
- Additional WAV compression formats

## Limitations

- **PCM only**: Non-PCM (compressed) WAV files are rejected with `UnsupportedFormatError`.
- **Unique chunk IDs**: `chunks` is keyed by chunk ID, so files containing multiple
  chunks with the same ID (e.g. several `LIST` chunks) keep only the last one.
- **Chunk ordering on write**: `write_wav` emits `fmt ` then `data` then remaining
  chunks sorted by ID, so a parse/write round-trip may not be byte-for-byte identical.

## Requirements

- Python 3.10 or higher
- No external dependencies!

## Development

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=riffy --cov-report=html

# Lint and format with Ruff
ruff check .
ruff format .

# Type-check with mypy
mypy
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributor guide.

### Building the Docs

```bash
pip install -e ".[docs]"
mkdocs serve   # preview locally at http://127.0.0.1:8000
```

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before
opening a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full release history.

## References

- RIFF format specification: [Microsoft RIFF Specification](https://learn.microsoft.com/en-us/windows/win32/xaudio2/resource-interchange-file-format--riff-)
- WAV format specification: [WAV Audio File Format](http://soundfile.sapp.org/doc/WaveFormat/)

## Support

For bugs, feature requests, or questions, please [open an issue](https://github.com/jmcmeen/riffy/issues).
