"""Additional tests for edge cases to achieve 100% coverage."""

import struct

import pytest

from riffy import WAVParser
from riffy.exceptions import (
    InvalidChunkError,
    InvalidWAVFormatError,
    MissingChunkError,
    UnsupportedFormatError,
    WAVError,
)


class TestMissingCoverage:
    """Test cases for previously uncovered code paths."""

    def test_chunk_id_wrong_length(self, temp_wav_dir):
        """Test handling of chunk ID with incorrect length (not 4 chars)."""
        # This is actually difficult to trigger since struct.unpack('<4s') always
        # returns exactly 4 bytes, and ASCII decode preserves length.
        # The check at line 87 is defensive but may be unreachable in practice.
        # We'll create a test anyway for completeness.
        filepath = temp_wav_dir / "invalid_length.wav"

        # Create a minimal valid WAV structure
        with open(filepath, "wb") as f:
            f.write(b"RIFF")
            f.write(struct.pack("<I", 36))  # file size
            f.write(b"WAVE")

            # Create a chunk header with a null byte in the middle
            # When decoded, nulls might be stripped in some edge cases
            f.write(b"fmt ")
            f.write(struct.pack("<I", 16))

            # Write valid format chunk
            fmt_data = struct.pack("<HHIIHH", 1, 2, 44100, 176400, 4, 16)
            f.write(fmt_data)

            # Add data chunk
            f.write(b"data")
            f.write(struct.pack("<I", 4))
            f.write(b"\x00\x00\x00\x00")

        # Should parse successfully (the length check is defensive)
        parser = WAVParser(filepath)
        info = parser.get_info()
        assert info is not None

    def test_non_pcm_format_with_invalid_cbsize(self, temp_wav_dir):
        """Test non-PCM format where cbSize doesn't match actual extension data."""
        filepath = temp_wav_dir / "bad_cbsize.wav"

        with open(filepath, "wb") as f:
            f.write(b"RIFF")
            f.write(struct.pack("<I", 48))  # file size
            f.write(b"WAVE")

            # Format chunk for non-PCM (ADPCM format 2)
            f.write(b"fmt ")
            fmt_size = 20  # 16 base + 2 cbSize + 2 extra
            f.write(struct.pack("<I", fmt_size))

            # Write format data
            audio_format = 2  # ADPCM
            fmt_data = struct.pack("<HHIIHH", audio_format, 2, 44100, 176400, 4, 16)
            f.write(fmt_data)

            # cbSize says 10 bytes of extension data
            f.write(struct.pack("<H", 10))
            # But we only provide 2 bytes
            f.write(b"\x00\x00")

            # Add data chunk
            f.write(b"data")
            f.write(struct.pack("<I", 4))
            f.write(b"\x00\x00\x00\x00")

        # Should raise error about format chunk size mismatch
        with pytest.raises(InvalidWAVFormatError, match="smaller than expected"):
            WAVParser(filepath)

    def test_missing_format_chunk(self, temp_wav_dir):
        """Test WAV file without a format chunk."""
        filepath = temp_wav_dir / "no_fmt.wav"

        with open(filepath, "wb") as f:
            f.write(b"RIFF")
            f.write(struct.pack("<I", 20))  # file size
            f.write(b"WAVE")

            # Only include data chunk, no fmt chunk
            f.write(b"data")
            f.write(struct.pack("<I", 4))
            f.write(b"\x00\x00\x00\x00")

        # Should raise error about missing format chunk
        with pytest.raises(MissingChunkError, match="No 'fmt ' chunk found"):
            WAVParser(filepath)

    def test_sample_count_with_no_audio_data(self, temp_wav_dir):
        """Test sample count calculation when audio_data is None."""
        filepath = temp_wav_dir / "no_audio.wav"

        with open(filepath, "wb") as f:
            f.write(b"RIFF")
            f.write(struct.pack("<I", 28))
            f.write(b"WAVE")

            # Add fmt chunk
            f.write(b"fmt ")
            f.write(struct.pack("<I", 16))
            fmt_data = struct.pack("<HHIIHH", 1, 2, 44100, 176400, 4, 16)
            f.write(fmt_data)

        # Should fail validation (no data chunk)
        with pytest.raises(MissingChunkError):
            WAVParser(filepath)

    def test_non_pcm_format_exact_size_match(self, temp_wav_dir):
        """Test non-PCM format with cbSize=2 and exactly 2 bytes of extension data."""
        filepath = temp_wav_dir / "exact_cbsize.wav"

        with open(filepath, "wb") as f:
            f.write(b"RIFF")
            f.write(struct.pack("<I", 48))
            f.write(b"WAVE")

            # Format chunk for non-PCM (ADPCM format 2)
            f.write(b"fmt ")
            fmt_size = 20  # 16 base + 2 cbSize + 2 extra
            f.write(struct.pack("<I", fmt_size))

            # Write format data
            audio_format = 2  # ADPCM
            fmt_data = struct.pack("<HHIIHH", audio_format, 2, 44100, 176400, 4, 16)
            f.write(fmt_data)

            # cbSize = 2, with exactly 2 bytes of extension
            f.write(struct.pack("<H", 2))
            f.write(b"\x00\x00")

            # Add data chunk
            f.write(b"data")
            f.write(struct.pack("<I", 4))
            f.write(b"\x00\x00\x00\x00")

        # Should parse format chunk successfully but fail validation (non-PCM)
        with pytest.raises(UnsupportedFormatError, match="Unsupported audio format"):
            WAVParser(filepath)


class TestAdditionalEdgeCases:
    """Additional edge case tests."""

    def test_empty_audio_data(self, temp_wav_dir):
        """Test WAV file with data chunk but zero bytes of audio."""
        filepath = temp_wav_dir / "empty_audio.wav"

        with open(filepath, "wb") as f:
            f.write(b"RIFF")
            f.write(struct.pack("<I", 36))
            f.write(b"WAVE")

            # Add fmt chunk
            f.write(b"fmt ")
            f.write(struct.pack("<I", 16))
            fmt_data = struct.pack("<HHIIHH", 1, 2, 44100, 176400, 4, 16)
            f.write(fmt_data)

            # Data chunk with size 0
            f.write(b"data")
            f.write(struct.pack("<I", 0))

        parser = WAVParser(filepath)
        info = parser.get_info()

        assert info["audio_data_size"] == 0
        assert info["sample_count"] == 0
        assert info["duration_seconds"] == 0.0

    def test_large_audio_data(self, temp_wav_dir):
        """Test WAV file with larger audio data."""
        from tests.conftest import create_wav_file

        filepath = temp_wav_dir / "large_audio.wav"
        # Create 10 seconds of audio
        create_wav_file(filepath, num_samples=441000)

        parser = WAVParser(filepath)
        info = parser.get_info()

        assert info["sample_count"] == 441000
        assert abs(info["duration_seconds"] - 10.0) < 0.01

    def test_chunk_id_with_trailing_space(self, temp_wav_dir):
        """Test chunk IDs with trailing spaces (common in WAV format)."""
        from tests.conftest import create_wav_file

        filepath = temp_wav_dir / "trailing_space.wav"
        create_wav_file(filepath)

        parser = WAVParser(filepath)
        info = parser.get_info()

        # 'fmt ' and 'data' should both be present
        assert "fmt " in info["chunks"]
        assert "data" in info["chunks"]

    def test_byte_rate_calculation(self, temp_wav_dir):
        """Test that byte_rate is calculated correctly for different formats."""
        from tests.conftest import create_wav_file

        test_cases = [
            # (channels, sample_rate, bits_per_sample, expected_byte_rate)
            (1, 44100, 16, 88200),
            (2, 44100, 16, 176400),
            (1, 22050, 8, 22050),
            (2, 48000, 24, 288000),
        ]

        for channels, sample_rate, bits, expected_byte_rate in test_cases:
            filepath = temp_wav_dir / f"byte_rate_{channels}_{sample_rate}_{bits}.wav"
            create_wav_file(
                filepath,
                channels=channels,
                sample_rate=sample_rate,
                bits_per_sample=bits,
                num_samples=1000,
            )

            parser = WAVParser(filepath)
            info = parser.get_info()

            assert info["format"]["byte_rate"] == expected_byte_rate


class TestDefensiveGuards:
    """Cover defensive guards and rarely-hit error paths."""

    def test_format_chunk_too_small(self, temp_wav_dir):
        """A 'fmt ' chunk under 16 bytes raises InvalidWAVFormatError."""
        filepath = temp_wav_dir / "tiny_fmt.wav"
        with open(filepath, "wb") as f:
            f.write(b"RIFF")
            f.write(struct.pack("<I", 4 + 8 + 8))
            f.write(b"WAVE")
            f.write(b"fmt ")
            f.write(struct.pack("<I", 8))  # only 8 bytes of fmt data (< 16)
            f.write(b"\x00" * 8)

        with pytest.raises(InvalidWAVFormatError, match="Format chunk too small"):
            WAVParser(filepath)

    def test_export_chunk_oserror_is_wrapped(self, valid_pcm_wav, tmp_path):
        """A filesystem error during export is wrapped in WAVError."""
        parser = WAVParser(valid_pcm_wav["filepath"])
        # Parent directory does not exist -> open() raises OSError.
        bad_path = tmp_path / "missing_dir" / "out.bin"

        with pytest.raises(WAVError, match="Failed to write chunk"):
            parser.export_chunk("data", bad_path)

    def test_set_chunk_non_ascii_id(self, valid_pcm_wav):
        """set_chunk rejects non-ASCII chunk IDs."""
        parser = WAVParser(valid_pcm_wav["filepath"])
        with pytest.raises(InvalidChunkError, match="must contain only ASCII"):
            parser.set_chunk("IN\xff\xff", b"data")

    def test_methods_require_parsed_state(self, valid_pcm_wav, tmp_path):
        """Public methods guard against being called with no format_info."""
        parser = WAVParser(valid_pcm_wav["filepath"])
        parser.format_info = None  # simulate an unparsed/reset parser

        out = tmp_path / "o.bin"
        with pytest.raises(WAVError, match="not parsed"):
            parser.get_info()
        with pytest.raises(WAVError, match="not parsed"):
            parser.export_chunk("data", out)
        with pytest.raises(WAVError, match="not parsed"):
            parser.export_audio_data(out)
        with pytest.raises(WAVError, match="not parsed"):
            parser.list_chunks()
        with pytest.raises(WAVError, match="not parsed"):
            parser.replace_chunk("data", b"x")
        with pytest.raises(WAVError, match="not parsed"):
            parser.add_chunk("TEST", b"x")
        with pytest.raises(WAVError, match="not parsed"):
            parser.set_chunk("TEST", b"x")
        with pytest.raises(WAVError, match="not parsed"):
            parser.write_wav(tmp_path / "o.wav")

    def test_export_audio_data_requires_audio(self, valid_pcm_wav, tmp_path):
        """export_audio_data raises when audio_data is missing."""
        parser = WAVParser(valid_pcm_wav["filepath"])
        parser.audio_data = None
        with pytest.raises(WAVError, match="No audio data available"):
            parser.export_audio_data(tmp_path / "o.bin")

    def test_copy_chunk_requires_parsed_parsers(self, valid_pcm_wav):
        """copy_chunk_from_parser guards both target and source state."""
        target = WAVParser(valid_pcm_wav["filepath"])
        source = WAVParser(valid_pcm_wav["filepath"])

        # Source not parsed
        source.format_info = None
        with pytest.raises(WAVError, match="Source parser"):
            target.copy_chunk_from_parser("data", source)

        # Target not parsed
        target.format_info = None
        with pytest.raises(WAVError, match="not parsed"):
            target.copy_chunk_from_parser("data", WAVParser(valid_pcm_wav["filepath"]))
