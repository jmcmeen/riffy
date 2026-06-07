#!/usr/bin/env python3
"""
Example: a complete chunk-modification workflow.

Ties the individual operations together into one realistic pipeline:
parse a file, back up its audio, replace the audio from another source,
attach metadata, write a new file, then re-parse and verify everything.
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
    print("RIFFY - Complete workflow")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        original_path = tmpdir / "original.wav"
        backup_path = tmpdir / "backup.bin"
        new_audio_path = tmpdir / "new_audio.bin"
        output_path = tmpdir / "processed.wav"

        create_test_wav(original_path, duration_seconds=1.0)

        # 1. Parse and inspect the original file.
        parser = WAVParser(original_path)
        info = parser.get_info()
        print("\nOriginal file:")
        print(f"  Size:        {info['file_size']:,} bytes")
        print(f"  Duration:    {info['duration_seconds']:.2f} s")
        print(f"  Channels:    {info['format']['channels']}")
        print(f"  Sample rate: {info['format']['sample_rate']:,} Hz")

        # 2. Back up the existing audio data to a binary file.
        backed_up = parser.export_audio_data(backup_path)
        print(f"\nBacked up {backed_up:,} bytes to {backup_path.name}")

        # 3. Replace the audio with new (shorter) data from another source.
        new_audio = b"\xff\xfe" * 2000  # 4,000 bytes
        new_audio_path.write_bytes(new_audio)
        parser.replace_chunk("data", new_audio_path.read_bytes())
        print(f"Replaced audio: {len(parser.audio_data):,} bytes "
              f"({parser.format_info.duration_seconds:.2f} s)")

        # 4. Attach metadata.
        parser.add_chunk("INFO", b"Processed audio\x00")
        parser.add_chunk("ISFT", b"riffy library\x00")

        # 5. Write the result.
        bytes_written = parser.write_wav(output_path)
        print(f"\nWrote {bytes_written:,} bytes to {output_path.name}")

        # 6. Re-parse and verify.
        verify = WAVParser(output_path)
        verify_info = verify.get_info()
        print("\nVerification:")
        print(f"  Chunks:       {list(verify.chunks.keys())}")
        print(f"  Audio matches: {verify.audio_data == new_audio}")
        print(f"  Duration:     {verify_info['duration_seconds']:.2f} s")
        print(f"  INFO chunk:   {verify.chunks['INFO'].data}")
        print(f"  ISFT chunk:   {verify.chunks['ISFT'].data}")
        print("\n✓ Done")


if __name__ == "__main__":
    main()
