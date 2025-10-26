# riffy

A low-dependency Python library for parsing and managing RIFF (Resource Interchange File Format) files.

Riffy provides a pure Python implementation for working with RIFF format files, with initial support for WAV audio files. The library is designed to have **zero external dependencies** while providing robust parsing capabilities for managing RIFF chunks.

## Features

- **Zero Dependencies**: Pure Python implementation with no external dependencies
- **WAV File Support**: Complete WAV file parsing with format validation
- **RIFF Chunk Management**: Access and inspect individual RIFF chunks
- **Audio Metadata Extraction**: Extract sample rate, channels, bit depth, and duration
- **Format Validation**: Automatic validation of file format and integrity
- **Type Safety**: Full type hints for better IDE support and code quality
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

# Parse a WAV file
parser = WAVParser("audio.wav")
info = parser.parse()

# Access format information
print(f"Sample Rate: {info['format']['sample_rate']} Hz")
print(f"Channels: {info['format']['channels']}")
print(f"Bit Depth: {info['format']['bits_per_sample']} bits")
print(f"Duration: {info['duration_seconds']:.2f} seconds")
```

### Accessing RIFF Chunks

```python
from riffy import WAVParser

parser = WAVParser("audio.wav")
parser.parse()

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

parser = WAVParser("audio.wav")
parser.parse()

# Access raw audio data
audio_data = parser.audio_data
print(f"Audio data size: {len(audio_data)} bytes")

# Get sample count
info = parser.get_info()
print(f"Total samples: {info['sample_count']}")
```

### Getting Detailed File Information

```python
from riffy import WAVParser
import json

parser = WAVParser("audio.wav")
info = parser.parse()

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

### WAVParser

The main class for parsing WAV files.

#### Constructor

```python
WAVParser(file_path: Union[str, Path])
```

**Parameters:**

- `file_path`: Path to the WAV file (string or `pathlib.Path`)

#### Methods

##### `parse() -> Dict`

Parse the WAV file and return comprehensive information.

**Returns:** Dictionary containing file information, format details, and chunk data

**Raises:**

- `FileNotFoundError`: If the file doesn't exist
- `InvalidWAVFormatError`: If the file is not a valid WAV file
- `CorruptedFileError`: If the file is corrupted or incomplete

##### `get_info() -> Dict`

Get comprehensive information about the parsed WAV file.

**Returns:** Dictionary with file metadata (must call `parse()` first)

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

**Properties:**

- `is_pcm`: Boolean indicating if format is PCM (uncompressed)
- `duration_seconds`: Audio duration in seconds

### WAVChunk

Dataclass representing a RIFF chunk.

**Attributes:**

- `id`: Chunk identifier (e.g., "fmt ", "data")
- `size`: Chunk size in bytes
- `data`: Raw chunk data
- `offset`: Byte offset in the file

## Exception Hierarchy

```
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
from riffy import WAVParser, InvalidWAVFormatError, CorruptedFileError

try:
    parser = WAVParser("audio.wav")
    info = parser.parse()
except InvalidWAVFormatError as e:
    print(f"Invalid WAV format: {e}")
except CorruptedFileError as e:
    print(f"File is corrupted: {e}")
except FileNotFoundError:
    print("File not found")
```

## Supported Formats

Currently, Riffy supports:

- **WAV Files**: PCM (uncompressed) audio only
- **RIFF Chunks**: Standard chunk parsing for any RIFF file

### Planned Support

- AVI files
- WebP images
- Additional WAV compression formats
- RIFF chunk writing/modification

## Requirements

- Python 3.8 or higher
- No external dependencies!

## Development

### Running Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=riffy --cov-report=html
```

### Code Formatting

```bash
# Format code with black
black src/

# Lint with ruff
ruff check src/
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

### Version 0.1.0 (Initial Release)

- Pure Python WAV file parser
- RIFF chunk management
- Zero external dependencies
- Full type hints
- Comprehensive error handling

## Acknowledgments

- RIFF format specification: [Microsoft RIFF Specification](https://learn.microsoft.com/en-us/windows/win32/xaudio2/resource-interchange-file-format--riff-)
- WAV format specification: [WAV Audio File Format](http://soundfile.sapp.org/doc/WaveFormat/)

## Support

For bugs, feature requests, or questions, please [open an issue](https://github.com/jmcmeen/riffy/issues).
