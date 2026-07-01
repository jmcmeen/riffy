#!/usr/bin/env python3
"""
Example: replace an existing chunk with new data.

Demonstrates ``WAVParser.replace_chunk()`` by swapping the audio in a WAV
file's ``data`` chunk with bytes read from a separate binary file, then
writing and verifying the result.
"""

import struct
import tempfile
from pathlib import Path

from riffy import WAVParser


def create_test_wav(filepath: Path, duration_seconds: float = 1.0) -> None:
    """Create a simple PCM test WAV file (silence)."""
    audio_format = 1
    channels = 2
    sample_rate = 44100
    bits_per_sample = 16

    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    num_samples = int(sample_rate * duration_seconds)
    data_size = num_samples * channels * bits_per_sample // 8

    audio_data = b"\x00" * data_size
    fmt_chunk_data = struct.pack(
        "<HHIIHH", audio_format, channels, sample_rate, byte_rate, block_align, bits_per_sample
    )
    riff_size = 4 + 8 + len(fmt_chunk_data) + 8 + data_size

    with open(filepath, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", riff_size))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<I", len(fmt_chunk_data)))
        f.write(fmt_chunk_data)
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(audio_data)


def main() -> None:
    print("=" * 70)
    print("RIFFY - Replace a chunk from a binary file")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        wav_path = tmpdir / "original.wav"
        binary_path = tmpdir / "new_audio.bin"
        output_path = tmpdir / "modified.wav"

        # Create a WAV file and a binary file holding replacement audio.
        create_test_wav(wav_path, duration_seconds=1.0)
        new_audio_data = b"\x01\x02" * 5000  # 10,000 bytes
        binary_path.write_bytes(new_audio_data)
        print(f"\nCreated WAV:    {wav_path.name}")
        print(f"Created binary: {binary_path.name} ({len(new_audio_data):,} bytes)")

        # Parse and replace the 'data' chunk with the binary file's content.
        parser = WAVParser(wav_path)
        print(f"\nOriginal audio size: {len(parser.audio_data):,} bytes")
        parser.replace_chunk("data", binary_path.read_bytes())
        print(f"New audio size:      {len(parser.audio_data):,} bytes")

        # Write and verify.
        bytes_written = parser.write_wav(output_path)
        print(f"\nWrote {bytes_written:,} bytes to {output_path.name}")

        verify = WAVParser(output_path)
        print(f"Audio matches replacement: {verify.audio_data == new_audio_data}")
        print("\n✓ Done")


if __name__ == "__main__":
    main()
