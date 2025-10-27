"""Tests for WAVFormat and WAVChunk dataclasses."""
import pytest
from riffy import WAVFormat, WAVChunk


class TestWAVFormat:
    """Test the WAVFormat dataclass."""

    def test_wav_format_initialization(self):
        """Test basic WAVFormat initialization."""
        fmt = WAVFormat(
            audio_format=1,
            channels=2,
            sample_rate=44100,
            byte_rate=176400,
            block_align=4,
            bits_per_sample=16
        )

        assert fmt.audio_format == 1
        assert fmt.channels == 2
        assert fmt.sample_rate == 44100
        assert fmt.byte_rate == 176400
        assert fmt.block_align == 4
        assert fmt.bits_per_sample == 16
        assert fmt.duration_seconds == 0.0  # default value

    def test_wav_format_with_duration(self):
        """Test WAVFormat with duration specified."""
        fmt = WAVFormat(
            audio_format=1,
            channels=2,
            sample_rate=44100,
            byte_rate=176400,
            block_align=4,
            bits_per_sample=16,
            duration_seconds=5.5
        )

        assert fmt.duration_seconds == 5.5

    def test_is_pcm_property_true(self):
        """Test is_pcm property returns True for PCM format."""
        fmt = WAVFormat(
            audio_format=1,
            channels=2,
            sample_rate=44100,
            byte_rate=176400,
            block_align=4,
            bits_per_sample=16
        )

        assert fmt.is_pcm is True

    def test_is_pcm_property_false(self):
        """Test is_pcm property returns False for non-PCM formats."""
        fmt = WAVFormat(
            audio_format=6,  # A-law
            channels=1,
            sample_rate=8000,
            byte_rate=8000,
            block_align=1,
            bits_per_sample=8
        )

        assert fmt.is_pcm is False

    def test_wav_format_various_formats(self):
        """Test WAVFormat with various audio formats."""
        formats = [
            (1, True),   # PCM
            (2, False),  # ADPCM
            (6, False),  # A-law
            (7, False),  # mu-law
            (85, False), # MPEG
        ]

        for audio_format, expected_is_pcm in formats:
            fmt = WAVFormat(
                audio_format=audio_format,
                channels=2,
                sample_rate=44100,
                byte_rate=176400,
                block_align=4,
                bits_per_sample=16
            )
            assert fmt.is_pcm == expected_is_pcm

    def test_wav_format_mono(self):
        """Test WAVFormat with mono audio."""
        fmt = WAVFormat(
            audio_format=1,
            channels=1,
            sample_rate=22050,
            byte_rate=44100,
            block_align=2,
            bits_per_sample=16
        )

        assert fmt.channels == 1
        assert fmt.byte_rate == 44100

    def test_wav_format_8bit(self):
        """Test WAVFormat with 8-bit audio."""
        fmt = WAVFormat(
            audio_format=1,
            channels=2,
            sample_rate=44100,
            byte_rate=88200,
            block_align=2,
            bits_per_sample=8
        )

        assert fmt.bits_per_sample == 8
        assert fmt.byte_rate == 88200

    def test_wav_format_48khz(self):
        """Test WAVFormat with 48kHz sample rate."""
        fmt = WAVFormat(
            audio_format=1,
            channels=2,
            sample_rate=48000,
            byte_rate=192000,
            block_align=4,
            bits_per_sample=16
        )

        assert fmt.sample_rate == 48000

    def test_wav_format_mutation(self):
        """Test that WAVFormat fields can be mutated."""
        fmt = WAVFormat(
            audio_format=1,
            channels=2,
            sample_rate=44100,
            byte_rate=176400,
            block_align=4,
            bits_per_sample=16
        )

        # Dataclasses are mutable by default
        fmt.duration_seconds = 10.5
        assert fmt.duration_seconds == 10.5


class TestWAVChunk:
    """Test the WAVChunk dataclass."""

    def test_wav_chunk_initialization(self):
        """Test basic WAVChunk initialization."""
        chunk = WAVChunk(
            id='fmt ',
            size=16,
            data=b'\x01\x00\x02\x00\x44\xac\x00\x00',
            offset=12
        )

        assert chunk.id == 'fmt '
        assert chunk.size == 16
        assert chunk.data == b'\x01\x00\x02\x00\x44\xac\x00\x00'
        assert chunk.offset == 12

    def test_wav_chunk_data_chunk(self):
        """Test WAVChunk for data chunk."""
        audio_data = b'\x00\x01\x02\x03' * 100
        chunk = WAVChunk(
            id='data',
            size=len(audio_data),
            data=audio_data,
            offset=44
        )

        assert chunk.id == 'data'
        assert chunk.size == 400
        assert len(chunk.data) == 400

    def test_wav_chunk_empty_data(self):
        """Test WAVChunk with empty data."""
        chunk = WAVChunk(
            id='JUNK',
            size=0,
            data=b'',
            offset=100
        )

        assert chunk.id == 'JUNK'
        assert chunk.size == 0
        assert chunk.data == b''

    def test_wav_chunk_custom_chunks(self):
        """Test WAVChunk with various custom chunk IDs."""
        chunk_ids = ['LIST', 'INFO', 'JUNK', 'cue ', 'plst']

        for chunk_id in chunk_ids:
            chunk = WAVChunk(
                id=chunk_id,
                size=10,
                data=b'\x00' * 10,
                offset=0
            )
            assert chunk.id == chunk_id
