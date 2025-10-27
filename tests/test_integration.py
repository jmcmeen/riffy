"""Integration tests for complete WAV parsing workflow."""
import pytest
from riffy import WAVParser


class TestFullParsingWorkflow:
    """Test complete parsing workflows."""

    def test_parse_valid_pcm_wav_complete(self, valid_pcm_wav):
        """Test complete parsing workflow for valid PCM WAV."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        info = parser.parse()

        # Verify all expected keys are present
        assert 'file_path' in info
        assert 'file_size' in info
        assert 'format' in info
        assert 'duration_seconds' in info
        assert 'audio_data_size' in info
        assert 'sample_count' in info
        assert 'chunks' in info

        # Verify format info
        assert info['format']['audio_format'] == 1
        assert info['format']['channels'] == valid_pcm_wav['channels']
        assert info['format']['sample_rate'] == valid_pcm_wav['sample_rate']
        assert info['format']['byte_rate'] == valid_pcm_wav['byte_rate']
        assert info['format']['block_align'] == valid_pcm_wav['block_align']
        assert info['format']['bits_per_sample'] == valid_pcm_wav['bits_per_sample']
        assert info['format']['is_pcm'] is True

        # Verify data
        assert info['audio_data_size'] == valid_pcm_wav['data_size']
        assert info['sample_count'] == valid_pcm_wav['num_samples']

        # Verify chunks
        assert 'fmt ' in info['chunks']
        assert 'data' in info['chunks']
        assert info['chunks']['fmt '] == 16  # Standard PCM format chunk size
        assert info['chunks']['data'] == valid_pcm_wav['data_size']

    def test_parse_mono_wav_complete(self, valid_mono_wav):
        """Test complete parsing workflow for mono WAV."""
        parser = WAVParser(valid_mono_wav['filepath'])
        info = parser.parse()

        assert info['format']['channels'] == 1
        assert info['sample_count'] == valid_mono_wav['num_samples']
        assert abs(info['duration_seconds'] - valid_mono_wav['duration_seconds']) < 0.01

    def test_parse_8bit_wav_complete(self, valid_8bit_wav):
        """Test complete parsing workflow for 8-bit WAV."""
        parser = WAVParser(valid_8bit_wav['filepath'])
        info = parser.parse()

        assert info['format']['bits_per_sample'] == 8
        assert info['audio_data_size'] == valid_8bit_wav['data_size']

    def test_parse_48khz_wav_complete(self, valid_48khz_wav):
        """Test complete parsing workflow for 48kHz WAV."""
        parser = WAVParser(valid_48khz_wav['filepath'])
        info = parser.parse()

        assert info['format']['sample_rate'] == 48000
        assert abs(info['duration_seconds'] - valid_48khz_wav['duration_seconds']) < 0.01

    def test_parser_state_after_parse(self, valid_pcm_wav):
        """Test parser state is correctly populated after parse."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        # Verify internal state
        assert parser.format_info is not None
        assert len(parser.chunks) >= 2  # At least fmt and data
        assert parser.audio_data is not None
        assert parser._file_size > 0

    def test_multiple_parses_same_file(self, valid_pcm_wav):
        """Test parsing the same file multiple times."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        info1 = parser.parse()
        info2 = parser.parse()

        # Should get consistent results
        assert info1 == info2

    def test_get_info_after_parse(self, valid_pcm_wav):
        """Test get_info returns same data as parse."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        info1 = parser.parse()
        info2 = parser.get_info()

        assert info1 == info2

    def test_file_path_in_info(self, valid_pcm_wav):
        """Test file path is correctly included in info."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        info = parser.parse()

        assert info['file_path'] == str(valid_pcm_wav['filepath'])

    def test_file_size_in_info(self, valid_pcm_wav):
        """Test file size is correctly included in info."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        info = parser.parse()

        assert info['file_size'] > 0
        assert info['file_size'] == valid_pcm_wav['filepath'].stat().st_size


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_short_audio(self, temp_wav_dir):
        """Test parsing WAV with very short audio (1 sample)."""
        from tests.conftest import create_wav_file

        filepath = temp_wav_dir / "very_short.wav"
        wav_info = create_wav_file(filepath, num_samples=1)

        parser = WAVParser(filepath)
        info = parser.parse()

        assert info['sample_count'] == 1
        assert info['duration_seconds'] > 0

    def test_odd_chunk_size_padding(self, temp_wav_dir):
        """Test that odd-sized chunks are handled with padding."""
        from tests.conftest import create_wav_file
        import struct

        # Create a WAV with odd-sized format chunk (should be padded)
        filepath = temp_wav_dir / "odd_chunk.wav"
        # Add 1 byte of extra data to make fmt chunk size 17 (odd)
        wav_info = create_wav_file(filepath, extra_fmt_data=b'\x00')

        parser = WAVParser(filepath)
        info = parser.parse()

        # Should parse successfully despite odd chunk size
        assert 'fmt ' in info['chunks']

    def test_various_sample_rates(self, temp_wav_dir):
        """Test various common sample rates."""
        from tests.conftest import create_wav_file

        sample_rates = [8000, 11025, 16000, 22050, 32000, 44100, 48000, 96000]

        for rate in sample_rates:
            filepath = temp_wav_dir / f"rate_{rate}.wav"
            wav_info = create_wav_file(filepath, sample_rate=rate, num_samples=rate)

            parser = WAVParser(filepath)
            info = parser.parse()

            assert info['format']['sample_rate'] == rate
            assert abs(info['duration_seconds'] - 1.0) < 0.01

    def test_various_bit_depths(self, temp_wav_dir):
        """Test various bit depths."""
        from tests.conftest import create_wav_file

        bit_depths = [8, 16, 24, 32]

        for bits in bit_depths:
            filepath = temp_wav_dir / f"bits_{bits}.wav"
            wav_info = create_wav_file(
                filepath,
                bits_per_sample=bits,
                num_samples=1000
            )

            parser = WAVParser(filepath)
            info = parser.parse()

            assert info['format']['bits_per_sample'] == bits

    def test_max_channels(self, temp_wav_dir):
        """Test files with multiple channels."""
        from tests.conftest import create_wav_file

        for channels in [1, 2, 4, 6, 8]:
            filepath = temp_wav_dir / f"channels_{channels}.wav"
            wav_info = create_wav_file(filepath, channels=channels, num_samples=1000)

            parser = WAVParser(filepath)
            info = parser.parse()

            assert info['format']['channels'] == channels


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    def test_extract_audio_data(self, valid_pcm_wav):
        """Test extracting audio data for processing."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        # Access audio data directly
        audio_data = parser.audio_data
        assert audio_data is not None
        assert isinstance(audio_data, bytes)
        assert len(audio_data) == valid_pcm_wav['data_size']

    def test_access_format_info_directly(self, valid_pcm_wav):
        """Test accessing format info directly."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        # Access format info directly
        fmt = parser.format_info
        assert fmt.is_pcm is True
        assert fmt.channels == valid_pcm_wav['channels']
        assert fmt.sample_rate == valid_pcm_wav['sample_rate']

    def test_access_chunks_directly(self, valid_pcm_wav):
        """Test accessing chunks directly."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        # Access chunks
        fmt_chunk = parser.chunks['fmt ']
        data_chunk = parser.chunks['data']

        assert fmt_chunk.id == 'fmt '
        assert data_chunk.id == 'data'
        assert len(data_chunk.data) == valid_pcm_wav['data_size']

    def test_calculate_duration_manually(self, valid_pcm_wav):
        """Test manual duration calculation from format info."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        # Calculate duration manually
        manual_duration = len(parser.audio_data) / parser.format_info.byte_rate

        assert abs(manual_duration - parser.format_info.duration_seconds) < 0.001
        assert abs(manual_duration - valid_pcm_wav['duration_seconds']) < 0.01
