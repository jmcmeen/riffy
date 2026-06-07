#!/usr/bin/env python3
"""
Example: overwrite the original WAV file safely.

Demonstrates the ``overwrite`` guard on ``WAVParser.write_wav()``. Writing
back to the source path is refused by default (raising ``FileExistsError``)
and only allowed when ``overwrite=True`` is passed explicitly.
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
    print("RIFFY - Overwrite the original file")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        wav_path = tmpdir / "audio.wav"

        create_test_wav(wav_path, duration_seconds=0.2)
        original_size = wav_path.stat().st_size

        parser = WAVParser(wav_path)
        parser.add_chunk("INFO", b"Modified\x00")
        print(f"\nOriginal file size: {original_size:,} bytes")

        # Writing back to the source is refused unless overwrite=True.
        try:
            parser.write_wav(wav_path)
            print("ERROR: expected FileExistsError")
        except FileExistsError:
            print("✓ Refused to overwrite source without overwrite=True")

        # Opt in explicitly to overwrite in place.
        parser.write_wav(wav_path, overwrite=True)
        new_size = wav_path.stat().st_size
        print(
            f"New file size:      {new_size:,} bytes "
            f"(+{new_size - original_size:,} for the new chunk)"
        )

        verify = WAVParser(wav_path)
        print(f"INFO chunk present: {'INFO' in verify.chunks}")
        print("\n✓ Done")


if __name__ == "__main__":
    main()
