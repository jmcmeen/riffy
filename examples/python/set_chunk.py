#!/usr/bin/env python3
"""
Example: add-or-replace a chunk with set_chunk().

Demonstrates ``WAVParser.set_chunk()``, the convenience method that adds a
chunk if it does not exist and replaces it if it does. The chunk count stays
constant on the second call while the content is updated.
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
    print("RIFFY - set_chunk() add-or-replace")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        wav_path = tmpdir / "original.wav"
        output_path = tmpdir / "updated.wav"

        create_test_wav(wav_path, duration_seconds=0.5)

        parser = WAVParser(wav_path)
        print(f"\nStarting chunks: {list(parser.chunks.keys())}")

        # First call adds the chunk because it doesn't exist yet.
        parser.set_chunk("INFO", b"Version 1\x00")
        print(f"\nAfter set v1:    {list(parser.chunks.keys())}")
        print(f"INFO content:    {parser.get_chunk('INFO').data}")

        # Second call replaces it in place -- the chunk count is unchanged.
        parser.set_chunk("INFO", b"Version 2\x00")
        print(f"\nAfter set v2:    {list(parser.chunks.keys())}")
        print(f"INFO content:    {parser.get_chunk('INFO').data}")

        parser.write_wav(output_path)
        print(f"\nWrote {output_path.name}")

        verify = WAVParser(output_path)
        print(f"Verified INFO:   {verify.get_chunk('INFO').data}")
        print("\n✓ Done")


if __name__ == "__main__":
    main()
