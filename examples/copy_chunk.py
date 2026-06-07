#!/usr/bin/env python3
"""
Example: copy chunks between two WAV files.

Demonstrates ``WAVParser.copy_chunk_from_parser()`` by copying both the audio
('data') and a metadata ('INFO') chunk from a source file into a destination
file, then writing and verifying the result.
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
    print("RIFFY - Copy chunks between files")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        source_path = tmpdir / "source.wav"
        dest_path = tmpdir / "destination.wav"
        output_path = tmpdir / "destination_modified.wav"

        # Two files of different lengths so the copy is observable.
        create_test_wav(source_path, duration_seconds=0.3)
        create_test_wav(dest_path, duration_seconds=0.5)

        source = WAVParser(source_path)
        source.add_chunk("INFO", b"Source metadata\x00")
        destination = WAVParser(dest_path)

        print(f"\nSource audio size:      {len(source.audio_data):,} bytes")
        print(f"Destination audio size: {len(destination.audio_data):,} bytes")

        # Copy the audio and the metadata chunk from source to destination.
        destination.copy_chunk_from_parser("data", source)
        destination.copy_chunk_from_parser("INFO", source)
        print(f"After copy, dest audio: {len(destination.audio_data):,} bytes")

        destination.write_wav(output_path)
        print(f"\nWrote {output_path.name}")

        verify = WAVParser(output_path)
        print(f"Audio matches source: {verify.audio_data == source.audio_data}")
        print(f"Copied INFO chunk:    {verify.chunks['INFO'].data}")
        print("\n✓ Done")


if __name__ == "__main__":
    main()
