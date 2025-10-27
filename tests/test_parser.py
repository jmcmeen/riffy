"""Tests for WAVParser class methods."""
import pytest
from pathlib import Path
from riffy import WAVParser, WAVFormat, WAVChunk
from riffy.exceptions import (
    WAVError,
    InvalidWAVFormatError,
    CorruptedFileError,
)


class TestWAVParserInitialization:
    """Test WAVParser initialization."""

    def test_init_with_string_path(self, valid_pcm_wav):
        """Test initialization with string path."""
        parser = WAVParser(str(valid_pcm_wav['filepath']))
        assert parser.file_path == Path(valid_pcm_wav['filepath'])
        # After auto-parse, these should be populated
        assert parser.format_info is not None
        assert parser.chunks != {}
        assert parser.audio_data is not None
        assert parser._file_size > 0

    def test_init_with_path_object(self, valid_pcm_wav):
        """Test initialization with Path object."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        assert parser.file_path == valid_pcm_wav['filepath']

    def test_init_nonexistent_file(self, temp_wav_dir):
        """Test initialization with nonexistent file."""
        # Now that auto-parse happens, initialization should raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            parser = WAVParser(temp_wav_dir / "nonexistent.wav")


class TestRIFFHeaderParsing:
    """Test RIFF header parsing."""

    def test_parse_valid_riff_header(self, valid_pcm_wav):
        """Test parsing valid RIFF header."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        info = parser.get_info()
        assert info is not None

    def test_parse_corrupt_riff_header(self, corrupt_riff_wav):
        """Test parsing with corrupt RIFF header."""
        with pytest.raises(InvalidWAVFormatError, match="Not a valid RIFF file"):
            parser = WAVParser(corrupt_riff_wav['filepath'])

    def test_parse_corrupt_wave_header(self, corrupt_wave_wav):
        """Test parsing with corrupt WAVE header."""
        with pytest.raises(InvalidWAVFormatError, match="Not a valid WAV file"):
            parser = WAVParser(corrupt_wave_wav['filepath'])

    def test_parse_tiny_file(self, tiny_wav):
        """Test parsing file that's too small."""
        with pytest.raises(CorruptedFileError, match="File too small"):
            parser = WAVParser(tiny_wav['filepath'])

    def test_parse_nonexistent_file(self, temp_wav_dir):
        """Test parsing nonexistent file."""
        with pytest.raises(FileNotFoundError):
            parser = WAVParser(temp_wav_dir / "nonexistent.wav")


class TestChunkParsing:
    """Test chunk parsing functionality."""

    def test_parse_fmt_chunk(self, valid_pcm_wav):
        """Test that fmt chunk is parsed correctly."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        assert 'fmt ' in parser.chunks
        fmt_chunk = parser.chunks['fmt ']
        assert isinstance(fmt_chunk, WAVChunk)
        assert fmt_chunk.id == 'fmt '
        assert fmt_chunk.size == 16  # PCM format chunk size

    def test_parse_data_chunk(self, valid_pcm_wav):
        """Test that data chunk is parsed correctly."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        assert 'data' in parser.chunks
        data_chunk = parser.chunks['data']
        assert isinstance(data_chunk, WAVChunk)
        assert data_chunk.id == 'data'
        assert data_chunk.size == valid_pcm_wav['data_size']

    def test_audio_data_extracted(self, valid_pcm_wav):
        """Test that audio data is extracted."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        assert parser.audio_data is not None
        assert len(parser.audio_data) == valid_pcm_wav['data_size']

    def test_invalid_chunk_id(self, invalid_chunk_id_wav):
        """Test parsing file with invalid (non-ASCII) chunk ID."""
        with pytest.raises(CorruptedFileError, match="Invalid chunk ID.*non-ASCII"):
            parser = WAVParser(invalid_chunk_id_wav['filepath'])

    def test_truncated_chunk(self, truncated_chunk_wav):
        """Test parsing file with truncated chunk data."""
        with pytest.raises(CorruptedFileError, match="Incomplete chunk"):
            parser = WAVParser(truncated_chunk_wav['filepath'])


class TestFormatChunkParsing:
    """Test format chunk parsing."""

    def test_parse_pcm_format(self, valid_pcm_wav):
        """Test parsing PCM format chunk."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        fmt = parser.format_info
        assert isinstance(fmt, WAVFormat)
        assert fmt.audio_format == 1
        assert fmt.channels == valid_pcm_wav['channels']
        assert fmt.sample_rate == valid_pcm_wav['sample_rate']
        assert fmt.byte_rate == valid_pcm_wav['byte_rate']
        assert fmt.block_align == valid_pcm_wav['block_align']
        assert fmt.bits_per_sample == valid_pcm_wav['bits_per_sample']
        assert fmt.is_pcm is True

    def test_parse_mono_format(self, valid_mono_wav):
        """Test parsing mono WAV format."""
        parser = WAVParser(valid_mono_wav['filepath'])

        fmt = parser.format_info
        assert fmt.channels == 1

    def test_parse_8bit_format(self, valid_8bit_wav):
        """Test parsing 8-bit WAV format."""
        parser = WAVParser(valid_8bit_wav['filepath'])

        fmt = parser.format_info
        assert fmt.bits_per_sample == 8

    def test_parse_48khz_format(self, valid_48khz_wav):
        """Test parsing 48kHz WAV format."""
        parser = WAVParser(valid_48khz_wav['filepath'])

        fmt = parser.format_info
        assert fmt.sample_rate == 48000

    def test_non_pcm_format_incomplete(self, non_pcm_wav_incomplete):
        """Test parsing non-PCM format without cbSize field."""
        with pytest.raises(InvalidWAVFormatError, match="requires at least 18 bytes"):
            parser = WAVParser(non_pcm_wav_incomplete['filepath'])

    def test_non_pcm_format_valid(self, non_pcm_wav_valid):
        """Test parsing non-PCM format with valid cbSize field."""
        # Should parse successfully but fail validation (non-PCM not supported)
        with pytest.raises(InvalidWAVFormatError, match="Unsupported audio format"):
            parser = WAVParser(non_pcm_wav_valid['filepath'])


class TestDurationCalculation:
    """Test duration calculation."""

    def test_duration_calculation_1_second(self, valid_pcm_wav):
        """Test duration calculation for 1-second file."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        expected_duration = valid_pcm_wav['duration_seconds']
        assert abs(parser.format_info.duration_seconds - expected_duration) < 0.01

    def test_duration_calculation_mono(self, valid_mono_wav):
        """Test duration calculation for mono file."""
        parser = WAVParser(valid_mono_wav['filepath'])

        expected_duration = valid_mono_wav['duration_seconds']
        assert abs(parser.format_info.duration_seconds - expected_duration) < 0.01

    def test_duration_calculation_8bit(self, valid_8bit_wav):
        """Test duration calculation for 8-bit file."""
        parser = WAVParser(valid_8bit_wav['filepath'])

        expected_duration = valid_8bit_wav['duration_seconds']
        assert abs(parser.format_info.duration_seconds - expected_duration) < 0.01

    def test_duration_in_get_info(self, valid_pcm_wav):
        """Test that duration is included in get_info output."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        info = parser.get_info()

        assert 'duration_seconds' in info
        expected_duration = valid_pcm_wav['duration_seconds']
        assert abs(info['duration_seconds'] - expected_duration) < 0.01


class TestValidation:
    """Test format validation."""

    def test_validation_no_fmt_chunk(self, no_data_chunk_wav):
        """Test validation with missing data chunk."""
        with pytest.raises(InvalidWAVFormatError, match="No audio data found"):
            parser = WAVParser(no_data_chunk_wav['filepath'])

    def test_validation_zero_channels(self, zero_channel_wav):
        """Test validation with zero channels."""
        with pytest.raises(InvalidWAVFormatError, match="Invalid number of channels"):
            parser = WAVParser(zero_channel_wav['filepath'])

    def test_validation_zero_sample_rate(self, zero_sample_rate_wav):
        """Test validation with zero sample rate."""
        with pytest.raises(InvalidWAVFormatError, match="Invalid sample rate"):
            parser = WAVParser(zero_sample_rate_wav['filepath'])

    def test_validation_non_pcm_format(self, non_pcm_wav_valid):
        """Test validation rejects non-PCM formats."""
        with pytest.raises(InvalidWAVFormatError, match="Unsupported audio format"):
            parser = WAVParser(non_pcm_wav_valid['filepath'])


class TestSampleCount:
    """Test sample count calculation."""

    def test_sample_count_stereo_16bit(self, valid_pcm_wav):
        """Test sample count for stereo 16-bit audio."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        info = parser.get_info()

        expected_samples = valid_pcm_wav['num_samples']
        assert info['sample_count'] == expected_samples

    def test_sample_count_mono(self, valid_mono_wav):
        """Test sample count for mono audio."""
        parser = WAVParser(valid_mono_wav['filepath'])
        info = parser.get_info()

        expected_samples = valid_mono_wav['num_samples']
        assert info['sample_count'] == expected_samples

    def test_sample_count_8bit(self, valid_8bit_wav):
        """Test sample count for 8-bit audio."""
        parser = WAVParser(valid_8bit_wav['filepath'])
        info = parser.get_info()

        expected_samples = valid_8bit_wav['num_samples']
        assert info['sample_count'] == expected_samples
