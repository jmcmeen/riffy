# Riffy Test Suite

Comprehensive test suite for the riffy RIFF/WAV parser library.

## Test Coverage

Current test coverage: **100%**

- Total tests: **144**
- All tests passing ✓

## Test Structure

```
tests/
├── conftest.py                  # Pytest fixtures and WAV file generators
├── test_dataclasses.py          # Tests for WAVFormat and WAVChunk dataclasses
├── test_exceptions.py           # Tests for exception hierarchy and handling
├── test_parser.py               # Tests for WAVParser parsing functionality
├── test_export.py               # Tests for chunk/audio export and list_chunks
├── test_chunk_modification.py   # Tests for add/replace/set/copy/write_wav
├── test_integration.py          # Integration tests for complete workflows
└── test_edge_cases.py           # Edge cases, defensive guards, coverage
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run with verbose output
```bash
pytest -v
```

### Run with coverage report
```bash
pytest --cov=riffy --cov-report=term-missing
```

### Run with HTML coverage report
```bash
pytest --cov=riffy --cov-report=html
# Open htmlcov/index.html in your browser
```

### Run specific test file / class / test
```bash
pytest tests/test_parser.py
pytest tests/test_parser.py::TestWAVParserInitialization
pytest tests/test_parser.py::TestWAVParserInitialization::test_init_with_string_path
```

## Test Categories

### Dataclass Tests (`test_dataclasses.py`) — 13 tests

- **WAVFormat**: Initialization, `is_pcm` property, various audio formats
- **WAVChunk**: Initialization, data handling, custom chunks

### Exception Tests (`test_exceptions.py`) — 16 tests

- Exception hierarchy validation, messages, catching patterns, inheritance

### Parser Tests (`test_parser.py`) — 30 tests

- Initialization (string/Path), RIFF header, chunk parsing, format chunk
  (PCM/non-PCM), duration, validation, sample count

### Export Tests (`test_export.py`) — 21 tests

- `export_chunk`, `export_audio_data`, `list_chunks`, and export workflows

### Chunk Modification Tests (`test_chunk_modification.py`) — 30 tests

- `replace_chunk`, `add_chunk`, `set_chunk`, `copy_chunk_from_parser`, `write_wav`

### Integration Tests (`test_integration.py`) — 19 tests

- End-to-end workflows, parser state, re-parse behavior, real-world scenarios

### Edge Case Tests (`test_edge_cases.py`) — 15 tests

- Missing/invalid/truncated chunks, empty/large audio, defensive guards, and
  rarely-hit error paths (export OSError wrapping, unparsed-state guards)

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

| Module | Statements | Missing | Coverage |
|--------|-----------|---------|----------|
| `src/riffy/__init__.py` | 5 | 0 | 100% |
| `src/riffy/exceptions.py` | 16 | 0 | 100% |
| `src/riffy/wav.py` | 211 | 0 | 100% |
| **TOTAL** | **232** | **0** | **100%** |

One defensive line in `wav.py` (the chunk-ID length check, unreachable because
`struct.unpack('<4s')` always yields exactly four bytes) is marked
`# pragma: no cover`.

## Continuous Integration

Tests run on every push and pull request via GitHub Actions across Python
3.10–3.14. Tests are designed to:
- Run fast (~1 second for the full suite)
- Be deterministic (no random failures)
- Clean up temporary files (via `tmp_path`)
- Work on all platforms (Linux, macOS, Windows)
- Require no external dependencies

## Adding New Tests

1. Choose the appropriate test file based on category
2. Create a test class if needed
3. Write a descriptive test name starting with `test_`
4. Use fixtures from `conftest.py` or create new ones
5. Run tests to verify

Example:
```python
def test_new_feature(valid_pcm_wav):
    """Test description."""
    parser = WAVParser(valid_pcm_wav["filepath"])
    info = parser.get_info()
    assert info["new_field"] == expected_value
```

## Maintenance

When modifying the library:
1. Run the full test suite before committing
2. Add tests for new features and changed behavior
3. Keep `ruff check`, `ruff format --check`, and `mypy` clean
4. Maintain coverage at/near 100%
5. Update this README if the test structure changes
