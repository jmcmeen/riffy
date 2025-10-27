# Riffy Test Suite

Comprehensive test suite for the riffy RIFF/WAV parser library.

## Test Coverage

Current test coverage: **98%**

- Total tests: **87**
- All tests passing ✓

## Test Structure

```
tests/
├── conftest.py              # Pytest fixtures and WAV file generators
├── test_dataclasses.py      # Tests for WAVFormat and WAVChunk dataclasses
├── test_exceptions.py       # Tests for exception hierarchy and handling
├── test_parser.py           # Tests for WAVParser functionality
├── test_integration.py      # Integration tests for complete workflows
└── test_edge_cases.py       # Edge cases and coverage completion tests
```

## Running Tests

### Run all tests
```bash
pytest tests/
```

### Run with verbose output
```bash
pytest tests/ -v
```

### Run with coverage report
```bash
pytest tests/ --cov=src/riffy --cov-report=term-missing
```

### Run with HTML coverage report
```bash
pytest tests/ --cov=src/riffy --cov-report=html
# Open htmlcov/index.html in your browser
```

### Run specific test file
```bash
pytest tests/test_parser.py
```

### Run specific test class
```bash
pytest tests/test_parser.py::TestWAVParserInitialization
```

### Run specific test
```bash
pytest tests/test_parser.py::TestWAVParserInitialization::test_init_with_string_path
```

## Test Categories

### 1. Dataclass Tests (`test_dataclasses.py`)
- **WAVFormat**: Initialization, properties (is_pcm), various audio formats
- **WAVChunk**: Initialization, data handling, custom chunks

**13 tests** covering all dataclass functionality.

### 2. Exception Tests (`test_exceptions.py`)
- Exception hierarchy validation
- Exception message handling
- Exception catching patterns
- Inheritance verification

**16 tests** ensuring proper exception handling.

### 3. Parser Tests (`test_parser.py`)
- Parser initialization (string/Path objects)
- RIFF header parsing
- Chunk parsing
- Format chunk parsing (PCM and non-PCM)
- Duration calculation
- Validation methods
- Sample count calculation

**30 tests** covering core parsing functionality.

### 4. Integration Tests (`test_integration.py`)
- Complete parsing workflows
- Parser state verification
- Multiple parses
- Edge cases (various sample rates, bit depths, channels)
- Real-world usage scenarios

**18 tests** ensuring end-to-end functionality.

### 5. Edge Case Tests (`test_edge_cases.py`)
- Non-PCM format validation
- Missing chunks
- Invalid chunk IDs
- Empty audio data
- Large audio files
- Byte rate calculations

**9 tests** for edge cases and additional coverage.

## Test Fixtures

The test suite includes comprehensive fixtures in `conftest.py`:

### File Generation Fixtures
- `valid_pcm_wav` - Standard PCM WAV file
- `valid_mono_wav` - Mono audio
- `valid_8bit_wav` - 8-bit audio
- `valid_48khz_wav` - 48kHz sample rate
- `non_pcm_wav_incomplete` - Non-PCM without cbSize
- `non_pcm_wav_valid` - Non-PCM with valid cbSize
- `corrupt_riff_wav` - Invalid RIFF header
- `corrupt_wave_wav` - Invalid WAVE header
- `no_data_chunk_wav` - Missing data chunk
- `invalid_chunk_id_wav` - Non-ASCII chunk ID
- `truncated_chunk_wav` - Truncated chunk data
- `tiny_wav` - File too small
- `zero_channel_wav` - Invalid channel count
- `zero_sample_rate_wav` - Invalid sample rate

### Utility Fixtures
- `temp_wav_dir` - Temporary directory for test files
- `create_wav_file()` - Flexible WAV file generator

## Code Coverage Details

### Covered Modules
| Module | Statements | Missing | Coverage |
|--------|-----------|---------|----------|
| `src/riffy/__init__.py` | 5 | 0 | 100% |
| `src/riffy/exceptions.py` | 16 | 0 | 100% |
| `src/riffy/wav.py` | 109 | 2 | 98% |
| **TOTAL** | **130** | **2** | **98%** |

### Uncovered Lines
Two defensive checks that are difficult to trigger in practice:
- Line 87: Chunk ID length validation (struct always returns 4 bytes)
- Line 114: Non-PCM format cbSize check (covered by other validation)

## Test Categories by Functionality

### Parsing Success Cases
- Valid PCM files (various formats)
- Different sample rates (8kHz - 96kHz)
- Different bit depths (8, 16, 24, 32 bits)
- Different channel counts (1-8 channels)
- Empty audio data
- Large audio files

### Error Cases
- Corrupt RIFF/WAVE headers
- Missing chunks (fmt, data)
- Invalid chunk IDs (non-ASCII)
- Truncated chunks
- Zero channels/sample rate
- Non-PCM formats
- Files too small

### Edge Cases
- Odd-sized chunks (padding)
- Very short audio (1 sample)
- Multiple parses of same file
- Direct access to parser internals

## Adding New Tests

To add new tests:

1. Choose appropriate test file based on category
2. Create test class if needed
3. Write descriptive test name starting with `test_`
4. Use fixtures from `conftest.py` or create new ones
5. Add assertions with clear error messages
6. Run tests to verify

Example:
```python
def test_new_feature(valid_pcm_wav):
    """Test description."""
    parser = WAVParser(valid_pcm_wav['filepath'])
    info = parser.parse()
    assert info['new_field'] == expected_value
```

## Continuous Integration

Tests are designed to:
- Run fast (< 1 second for full suite)
- Be deterministic (no random failures)
- Clean up temporary files
- Work on all platforms (Linux, macOS, Windows)
- Require no external dependencies

## Maintenance

When modifying the library:
1. Run full test suite before committing
2. Add tests for new features
3. Update tests for changed behavior
4. Maintain coverage above 95%
5. Update this README if test structure changes
