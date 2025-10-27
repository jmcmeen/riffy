"""Pytest configuration and fixtures for riffy tests."""
import struct
import pytest
from pathlib import Path
from typing import Dict, Any


@pytest.fixture
def temp_wav_dir(tmp_path):
    """Create a temporary directory for WAV files."""
    wav_dir = tmp_path / "wav_files"
    wav_dir.mkdir()
    return wav_dir


def create_wav_file(
    filepath: Path,
    audio_format: int = 1,  # 1 = PCM
    channels: int = 2,
    sample_rate: int = 44100,
    bits_per_sample: int = 16,
    num_samples: int = 44100,  # 1 second at 44.1kHz
    extra_fmt_data: bytes = b"",
    include_data_chunk: bool = True,
    corrupt_riff: bool = False,
    corrupt_wave: bool = False,
    invalid_chunk_id: bytes = None,
    truncate_chunk: bool = False,
) -> Dict[str, Any]:
    """
    Create a WAV file with specified parameters for testing.

    Returns a dict with file metadata for verification.
    """
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8

    # Calculate data size
    data_size = num_samples * channels * bits_per_sample // 8

    # Create audio data (simple sine-like pattern)
    audio_data = bytes([i % 256 for i in range(data_size)])

    # Build format chunk
    fmt_chunk_data = struct.pack(
        '<HHIIHH',
        audio_format,
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample
    )
    fmt_chunk_data += extra_fmt_data
    fmt_chunk_size = len(fmt_chunk_data)

    # Calculate total file size
    chunks_size = 4  # "WAVE"
    chunks_size += 8 + fmt_chunk_size  # fmt chunk
    if fmt_chunk_size % 2:
        chunks_size += 1  # padding

    if include_data_chunk:
        chunks_size += 8 + data_size  # data chunk
        if data_size % 2:
            chunks_size += 1  # padding

    riff_size = chunks_size

    # Write the WAV file
    with open(filepath, 'wb') as f:
        # RIFF header
        riff_id = b'JUNK' if corrupt_riff else b'RIFF'
        f.write(riff_id)
        f.write(struct.pack('<I', riff_size))

        wave_id = b'JUNK' if corrupt_wave else b'WAVE'
        f.write(wave_id)

        # Format chunk
        chunk_id = invalid_chunk_id if invalid_chunk_id else b'fmt '
        f.write(chunk_id)
        f.write(struct.pack('<I', fmt_chunk_size))

        if truncate_chunk:
            # Write incomplete chunk data
            f.write(fmt_chunk_data[:8])
        else:
            f.write(fmt_chunk_data)
            # Padding if odd size
            if fmt_chunk_size % 2:
                f.write(b'\x00')

        # Data chunk
        if include_data_chunk and not truncate_chunk:
            f.write(b'data')
            f.write(struct.pack('<I', data_size))
            f.write(audio_data)
            # Padding if odd size
            if data_size % 2:
                f.write(b'\x00')

    return {
        'filepath': filepath,
        'audio_format': audio_format,
        'channels': channels,
        'sample_rate': sample_rate,
        'byte_rate': byte_rate,
        'block_align': block_align,
        'bits_per_sample': bits_per_sample,
        'data_size': data_size,
        'num_samples': num_samples,
        'duration_seconds': num_samples / sample_rate if sample_rate > 0 else 0.0,
    }


@pytest.fixture
def valid_pcm_wav(temp_wav_dir):
    """Create a valid PCM WAV file."""
    filepath = temp_wav_dir / "valid_pcm.wav"
    return create_wav_file(filepath)


@pytest.fixture
def valid_mono_wav(temp_wav_dir):
    """Create a valid mono WAV file."""
    filepath = temp_wav_dir / "valid_mono.wav"
    return create_wav_file(filepath, channels=1, num_samples=22050)


@pytest.fixture
def valid_8bit_wav(temp_wav_dir):
    """Create a valid 8-bit WAV file."""
    filepath = temp_wav_dir / "valid_8bit.wav"
    return create_wav_file(filepath, bits_per_sample=8, num_samples=8000)


@pytest.fixture
def valid_48khz_wav(temp_wav_dir):
    """Create a valid 48kHz WAV file."""
    filepath = temp_wav_dir / "valid_48khz.wav"
    return create_wav_file(filepath, sample_rate=48000, num_samples=48000)


@pytest.fixture
def non_pcm_wav_incomplete(temp_wav_dir):
    """Create a non-PCM WAV file with incomplete extended format data."""
    filepath = temp_wav_dir / "non_pcm_incomplete.wav"
    # Format 6 (A-law) without cbSize field
    return create_wav_file(filepath, audio_format=6)


@pytest.fixture
def non_pcm_wav_valid(temp_wav_dir):
    """Create a non-PCM WAV file with valid extended format data."""
    filepath = temp_wav_dir / "non_pcm_valid.wav"
    # Format 7 (mu-law) with cbSize=0
    extra_data = struct.pack('<H', 0)  # cbSize = 0
    return create_wav_file(filepath, audio_format=7, extra_fmt_data=extra_data)


@pytest.fixture
def corrupt_riff_wav(temp_wav_dir):
    """Create a WAV file with invalid RIFF header."""
    filepath = temp_wav_dir / "corrupt_riff.wav"
    return create_wav_file(filepath, corrupt_riff=True)


@pytest.fixture
def corrupt_wave_wav(temp_wav_dir):
    """Create a WAV file with invalid WAVE header."""
    filepath = temp_wav_dir / "corrupt_wave.wav"
    return create_wav_file(filepath, corrupt_wave=True)


@pytest.fixture
def no_data_chunk_wav(temp_wav_dir):
    """Create a WAV file without a data chunk."""
    filepath = temp_wav_dir / "no_data_chunk.wav"
    return create_wav_file(filepath, include_data_chunk=False)


@pytest.fixture
def invalid_chunk_id_wav(temp_wav_dir):
    """Create a WAV file with non-ASCII chunk ID."""
    filepath = temp_wav_dir / "invalid_chunk_id.wav"
    return create_wav_file(filepath, invalid_chunk_id=b'\xff\xff\xff\xff')


@pytest.fixture
def truncated_chunk_wav(temp_wav_dir):
    """Create a WAV file with truncated chunk data."""
    filepath = temp_wav_dir / "truncated_chunk.wav"
    return create_wav_file(filepath, truncate_chunk=True)


@pytest.fixture
def tiny_wav(temp_wav_dir):
    """Create a WAV file that's too small to be valid."""
    filepath = temp_wav_dir / "tiny.wav"
    with open(filepath, 'wb') as f:
        f.write(b'RIFF\x00\x00')  # Only 6 bytes
    return {'filepath': filepath}


@pytest.fixture
def zero_channel_wav(temp_wav_dir):
    """Create a WAV file with zero channels (invalid)."""
    filepath = temp_wav_dir / "zero_channel.wav"
    return create_wav_file(filepath, channels=0)


@pytest.fixture
def zero_sample_rate_wav(temp_wav_dir):
    """Create a WAV file with zero sample rate (invalid)."""
    filepath = temp_wav_dir / "zero_sample_rate.wav"
    return create_wav_file(filepath, sample_rate=0)
