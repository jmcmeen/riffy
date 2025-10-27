# Riffy Examples

This directory contains example scripts demonstrating how to use the riffy library.

## Available Examples

### 1. `example.py` - Basic WAV File Parsing

Comprehensive example showing basic riffy functionality.

**Features Demonstrated:**
- Creating a sample WAV file (auto-generated if not present)
- Parsing WAV files
- Accessing format information
- Accessing raw audio data
- Iterating through RIFF chunks
- Error handling
- JSON output

**Usage:**
```bash
python example.py
```

**What it does:**
1. Creates a sample WAV file if `example.wav` doesn't exist
2. Parses the WAV file
3. Displays format information (sample rate, channels, bit depth, etc.)
4. Shows file information (size, duration, sample count)
5. Lists all RIFF chunks
6. Shows raw audio data (first 16 bytes)
7. Provides detailed chunk information
8. Outputs complete information as formatted JSON

**Output Example:**
```
============================================================
Riffy - WAV File Parser Example
============================================================

Creating sample WAV file: example.wav
Sample file created successfully!

Parsing: example.wav

Format Information:
  Sample Rate: 44,100 Hz
  Channels: 2
  Bit Depth: 16 bits
  Audio Format: PCM
  Byte Rate: 176,400 bytes/sec
  Block Align: 4 bytes

File Information:
  File Size: 176,444 bytes
  Duration: 1.00 seconds
  Audio Data Size: 176,400 bytes
  Sample Count: 44,100

RIFF Chunks:
  'fmt ': 16 bytes
  'data': 176,400 bytes
```

---

### 2. `export_chunks.py` - Exporting Chunks to Binary Files

Complete example demonstrating chunk export functionality.

**Features Demonstrated:**
- Creating sample WAV files
- Listing available chunks
- Exporting specific chunks to binary files
- Exporting raw audio data
- Comparing export methods
- Batch exporting all chunks
- Error handling

**Usage:**
```bash
python export_chunks.py
```

**What it does:**

#### Part 1: Export Demonstration
1. Creates a sample WAV file (`example_audio.wav`)
2. Parses the file and displays information
3. Lists all available chunks with sizes and offsets
4. Exports format chunk to `format_chunk.bin`
5. Exports data chunk using `export_chunk()` method
6. Exports audio data using `export_audio_data()` convenience method
7. Verifies both methods produce identical output
8. Exports all chunks to `exported_chunks/` directory
9. Cleans up all generated files

#### Part 2: Error Handling Examples
1. Demonstrates error when exporting before parsing
2. Shows error when requesting non-existent chunk
3. Shows successful export

**Output Example:**
```
Created example WAV file: example_audio.wav

WAV File Information:
  Sample Rate: 44100 Hz
  Channels: 2
  Bits per Sample: 16
  Duration: 1.00 seconds
  Audio Data Size: 176,400 bytes

Available Chunks:
  'fmt ': 16 bytes at offset 20
  'data': 176,400 bytes at offset 44

Exported format chunk: 16 bytes → format_chunk.bin
Exported data chunk: 176,400 bytes → audio_data_v1.bin
Exported audio data: 176,400 bytes → audio_data_v2.bin

✓ Both export methods produced identical output

Exporting all chunks:
  fmt  → exported_chunks/fmt.bin (16 bytes)
  data → exported_chunks/data.bin (176,400 bytes)

Export complete!
```

---

## Running Examples

### Prerequisites

Ensure riffy is installed:

```bash
# From the riffy root directory
pip install -e .

# Or if installed from PyPI
pip install riffy
```

### Run All Examples

```bash
# Navigate to examples directory
cd examples

# Run basic parsing example
python example.py

# Run export example
python export_chunks.py
```

### Run from Root Directory

```bash
# Run basic example
python examples/example.py

# Run export example
python examples/export_chunks.py
```

## Example Files Generated

Both examples create temporary files during execution:

**`example.py` creates:**
- `example.wav` - Sample WAV file (kept for future runs)

**`export_chunks.py` creates and cleans up:**
- `example_audio.wav` - Temporary WAV file (deleted after run)
- `format_chunk.bin` - Exported format chunk (deleted)
- `audio_data_v1.bin` - Exported via export_chunk (deleted)
- `audio_data_v2.bin` - Exported via export_audio_data (deleted)
- `exported_chunks/` - Directory with all chunks (deleted)
- `test.wav` - Temporary file for error examples (deleted)
- `output.bin` - Temporary export file (deleted)

## Understanding the Code

### Basic Parsing Pattern

```python
from riffy import WAVParser

# Create parser
parser = WAVParser("audio.wav")

# Parse the file
info = parser.parse()

# Access information
print(f"Sample Rate: {info['format']['sample_rate']} Hz")
print(f"Duration: {info['duration_seconds']:.2f} seconds")
```

### Export Pattern

```python
from riffy import WAVParser

# Parse file
parser = WAVParser("audio.wav")
parser.parse()

# Export audio data (most common)
parser.export_audio_data("output.bin")

# Or export specific chunks
parser.export_chunk('fmt ', "format.bin")
parser.export_chunk('data', "data.bin")
```

### Error Handling Pattern

```python
from riffy import WAVParser, InvalidWAVFormatError, CorruptedFileError

try:
    parser = WAVParser("audio.wav")
    info = parser.parse()
    # Process file...
except FileNotFoundError:
    print("File not found")
except InvalidWAVFormatError as e:
    print(f"Invalid WAV format: {e}")
except CorruptedFileError as e:
    print(f"Corrupted file: {e}")
```

## Modifying Examples

Feel free to modify these examples for your own use:

### Use Your Own WAV Files

In `example.py`, change the `wav_file` variable:

```python
wav_file = "path/to/your/file.wav"
```

Then comment out or remove the auto-generation code:

```python
# Comment these lines out if using your own file
# if not Path(wav_file).exists():
#     print(f"\nCreating sample WAV file: {wav_file}")
#     create_sample_wav(wav_file)
```

### Export to Different Locations

In `export_chunks.py`, modify the output paths:

```python
# Change export directory
export_dir = Path("/path/to/your/exports")
export_dir.mkdir(exist_ok=True)

# Change individual file paths
parser.export_audio_data("/custom/path/audio.bin")
```

### Add More Processing

Both examples can be extended with additional processing:

```python
# After parsing
info = parser.parse()

# Calculate additional metrics
duration_minutes = info['duration_seconds'] / 60
file_size_mb = info['file_size'] / (1024 * 1024)

print(f"Duration: {duration_minutes:.2f} minutes")
print(f"File size: {file_size_mb:.2f} MB")

# Process audio data
audio_data = parser.audio_data
# ... your processing code here ...
```

## Troubleshooting

### "Module 'riffy' not found"

Make sure riffy is installed:
```bash
pip install riffy
# or
pip install -e .  # from riffy root directory
```

### "File not found" errors

The examples should auto-generate sample files. If you see this error:
1. Check you're running from the correct directory
2. Check file permissions
3. Try running with `python -u example.py` for unbuffered output

### Import errors

If you see import errors, ensure you're using Python 3.8+:
```bash
python --version  # Should be 3.8 or higher
```

## Additional Resources

- [Main README](../README.md) - Full riffy documentation
- [API Reference](../README.md#api-reference) - Detailed API documentation
- [Tests](../tests/) - Comprehensive test examples
- [GitHub Issues](https://github.com/jmcmeen/riffy/issues) - Report problems or ask questions

## Contributing Examples

Have a useful example? Consider contributing:

1. Create your example script
2. Add type hints and docstrings
3. Test it thoroughly
4. Add documentation to this README
5. Submit a pull request

Good example ideas:
- Working with specific audio formats
- Batch processing multiple files
- Converting between formats
- Analyzing audio properties
- Integration with audio processing libraries
