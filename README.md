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

# Access all chunks. Each ID maps to a list of occurrences, so a file may
# carry more than one chunk with the same ID (e.g. multiple LIST chunks).
for chunk_id, chunk_list in parser.chunks.items():
    for chunk in chunk_list:
        print(f"Chunk: {chunk_id}, Size: {chunk.size} bytes, Offset: {chunk.offset}")

# Access a specific chunk (first occurrence) via the convenience accessor
fmt_chunk = parser.get_chunk('fmt ')
if fmt_chunk is not None:
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

# List all available chunks before exporting. Each ID maps to a list of
# occurrences, so iterate the inner list.
chunks = parser.list_chunks()
for chunk_id, occurrences in chunks.items():
    for info in occurrences:
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
    "fmt ": [16],
    "data": [617400]
  }
}
```

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
- **Multiple chunks per ID**: `chunks` maps each chunk ID to a list of every
  occurrence in file order, so files containing multiple chunks with the same ID
  (e.g. several `LIST` chunks) preserve all of them. Use `get_chunk(id)` for the
  common single-occurrence case.
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
