#!/usr/bin/env python3
"""
Practical demonstration of chunk modification.

This script creates test WAV files and demonstrates real modifications.
"""

import struct
from pathlib import Path
import tempfile
from riffy.wav import WAVParser


def create_test_wav(filepath: Path, duration_seconds: float = 1.0) -> None:
    """Create a simple test WAV file."""
    # Standard PCM format
    audio_format = 1
    channels = 2
    sample_rate = 44100
    bits_per_sample = 16

    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    num_samples = int(sample_rate * duration_seconds)
    data_size = num_samples * channels * bits_per_sample // 8

    # Create simple audio data (silence)
    audio_data = b'\x00' * data_size

    # Build format chunk
    fmt_chunk_data = struct.pack(
        '<HHIIHH',
        audio_format, channels, sample_rate,
        byte_rate, block_align, bits_per_sample
    )

    # Calculate total size
    riff_size = 4 + 8 + len(fmt_chunk_data) + 8 + data_size

    # Write the file
    with open(filepath, 'wb') as f:
        f.write(b'RIFF')
        f.write(struct.pack('<I', riff_size))
        f.write(b'WAVE')
        f.write(b'fmt ')
        f.write(struct.pack('<I', len(fmt_chunk_data)))
        f.write(fmt_chunk_data)
        f.write(b'data')
        f.write(struct.pack('<I', data_size))
        f.write(audio_data)

    print(f"Created test WAV file: {filepath} ({duration_seconds}s)")


def demo_replace_with_binary():
    """Demo: Replace audio data with binary file content."""
    print("\n" + "=" * 70)
    print("DEMO 1: Replace audio data from binary file")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create test files
        wav_path = tmpdir / "original.wav"
        binary_path = tmpdir / "new_audio.bin"
        output_path = tmpdir / "modified.wav"

        create_test_wav(wav_path, duration_seconds=1.0)

        # Create binary file with new audio data
        new_audio_data = b'\x01\x02' * 5000  # 10000 bytes
        with open(binary_path, 'wb') as f:
            f.write(new_audio_data)
        print(f"Created binary file: {binary_path} ({len(new_audio_data)} bytes)")

        # Parse and modify
        parser = WAVParser(wav_path)
        parser.parse()
        print(f"Original audio size: {len(parser.audio_data)} bytes")

        # Replace with binary data
        with open(binary_path, 'rb') as f:
            parser.replace_chunk('data', f.read())

        print(f"New audio size: {len(parser.audio_data)} bytes")

        # Write modified file
        bytes_written = parser.write_wav(output_path)
        print(f"Written to {output_path}: {bytes_written} bytes")

        # Verify
        verify = WAVParser(output_path)
        verify.parse()
        print(f"Verification: Audio data matches = {verify.audio_data == new_audio_data}")
        print("✓ Success!")


def demo_add_metadata():
    """Demo: Add metadata chunks to a WAV file."""
    print("\n" + "=" * 70)
    print("DEMO 2: Add metadata chunks")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        wav_path = tmpdir / "original.wav"
        output_path = tmpdir / "with_metadata.wav"

        create_test_wav(wav_path, duration_seconds=0.5)

        # Parse and add metadata
        parser = WAVParser(wav_path)
        parser.parse()

        print(f"Original chunks: {list(parser.chunks.keys())}")

        # Add various metadata chunks
        parser.add_chunk('INFO', b'Artist: Demo Artist\x00')
        parser.add_chunk('ICMT', b'This is a comment\x00')
        parser.add_chunk('ICOP', b'Copyright 2024\x00')

        print(f"After adding chunks: {list(parser.chunks.keys())}")

        # Write to new file
        parser.write_wav(output_path)
        print(f"Written to {output_path}")

        # Verify
        verify = WAVParser(output_path)
        verify.parse()
        print(f"Verified chunks: {list(verify.chunks.keys())}")
        print(f"INFO chunk content: {verify.chunks['INFO'].data}")
        print("✓ Success!")


def demo_copy_between_files():
    """Demo: Copy chunks between WAV files."""
    print("\n" + "=" * 70)
    print("DEMO 3: Copy chunks between files")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        source_path = tmpdir / "source.wav"
        dest_path = tmpdir / "destination.wav"
        output_path = tmpdir / "destination_modified.wav"

        # Create two different WAV files
        create_test_wav(source_path, duration_seconds=0.3)
        create_test_wav(dest_path, duration_seconds=0.5)

        # Parse both
        source = WAVParser(source_path)
        source.parse()
        source.add_chunk('INFO', b'Source metadata\x00')

        destination = WAVParser(dest_path)
        destination.parse()

        print(f"Source audio size: {len(source.audio_data)} bytes")
        print(f"Destination audio size: {len(destination.audio_data)} bytes")

        # Copy audio from source to destination
        destination.copy_chunk_from_parser('data', source)
        print(f"After copy, destination audio size: {len(destination.audio_data)} bytes")

        # Also copy the metadata chunk
        destination.copy_chunk_from_parser('INFO', source)

        # Write modified destination
        destination.write_wav(output_path)
        print(f"Written to {output_path}")

        # Verify
        verify = WAVParser(output_path)
        verify.parse()
        print(f"Verified audio matches source: {verify.audio_data == source.audio_data}")
        print(f"Verified INFO chunk: {verify.chunks['INFO'].data}")
        print("✓ Success!")


def demo_overwrite_original():
    """Demo: Safely overwrite the original file."""
    print("\n" + "=" * 70)
    print("DEMO 4: Overwrite original file")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        wav_path = tmpdir / "audio.wav"

        create_test_wav(wav_path, duration_seconds=0.2)

        # Parse
        parser = WAVParser(wav_path)
        parser.parse()

        original_size = wav_path.stat().st_size
        print(f"Original file size: {original_size} bytes")

        # Add metadata
        parser.add_chunk('INFO', b'Modified\x00')

        # Try to overwrite without flag (should fail)
        try:
            parser.write_wav(wav_path)
            print("ERROR: Should have raised FileExistsError")
        except FileExistsError:
            print("✓ Correctly prevented overwrite without flag")

        # Now overwrite with flag
        parser.write_wav(wav_path, overwrite=True)
        new_size = wav_path.stat().st_size
        print(f"New file size: {new_size} bytes")
        print(f"Size increased by: {new_size - original_size} bytes (new chunk)")

        # Verify
        verify = WAVParser(wav_path)
        verify.parse()
        print(f"Verified INFO chunk exists: {'INFO' in verify.chunks}")
        print("✓ Success!")


def demo_complete_workflow():
    """Demo: Complete real-world workflow."""
    print("\n" + "=" * 70)
    print("DEMO 5: Complete workflow")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        original_path = tmpdir / "original.wav"
        backup_path = tmpdir / "backup.bin"
        new_audio_path = tmpdir / "new_audio.bin"
        output_path = tmpdir / "processed.wav"

        # Create original
        create_test_wav(original_path, duration_seconds=1.0)

        # Parse
        parser = WAVParser(original_path)
        info = parser.parse()

        print(f"\nOriginal file info:")
        print(f"  Size: {info['file_size']} bytes")
        print(f"  Duration: {info['duration_seconds']:.2f} seconds")
        print(f"  Channels: {info['format']['channels']}")
        print(f"  Sample rate: {info['format']['sample_rate']} Hz")

        # Backup audio data
        parser.export_audio_data(backup_path)
        print(f"\nBacked up audio data to {backup_path}")

        # Create new audio data (shorter)
        new_audio = b'\xFF\xFE' * 2000  # 4000 bytes
        with open(new_audio_path, 'wb') as f:
            f.write(new_audio)

        # Replace audio
        with open(new_audio_path, 'rb') as f:
            parser.replace_chunk('data', f.read())

        print(f"\nReplaced audio: {len(parser.audio_data)} bytes")
        print(f"New duration: {parser.format_info.duration_seconds:.2f} seconds")

        # Add metadata
        parser.add_chunk('INFO', b'Processed audio\x00')
        parser.add_chunk('ISFT', b'riffy library\x00')

        # Write output
        bytes_written = parser.write_wav(output_path)
        print(f"\nWritten {bytes_written} bytes to {output_path}")

        # Verify
        verify = WAVParser(output_path)
        verify_info = verify.parse()

        print(f"\nOutput file verification:")
        print(f"  Chunks: {list(verify.chunks.keys())}")
        print(f"  Audio matches: {verify.audio_data == new_audio}")
        print(f"  Duration: {verify_info['duration_seconds']:.2f} seconds")
        print(f"  INFO chunk: {verify.chunks['INFO'].data}")
        print(f"  ISFT chunk: {verify.chunks['ISFT'].data}")
        print("\n✓ Complete workflow successful!")


def main():
    """Run all demos."""
    print("=" * 70)
    print("RIFFY - Practical Chunk Modification Demonstrations")
    print("=" * 70)

    demo_replace_with_binary()
    demo_add_metadata()
    demo_copy_between_files()
    demo_overwrite_original()
    demo_complete_workflow()

    print("\n" + "=" * 70)
    print("All demonstrations completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
