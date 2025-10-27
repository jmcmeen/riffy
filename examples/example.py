#!/usr/bin/env python3
"""
Example usage of the riffy library for parsing WAV files.
"""

from riffy import WAVParser, InvalidWAVFormatError, CorruptedFileError
import json
import struct
from pathlib import Path


def create_sample_wav(filepath: str = "example.wav") -> str:
    """Create a sample WAV file for demonstration."""
    # Create a simple 1-second WAV file (16-bit stereo @ 44.1kHz)
    sample_rate = 44100
    channels = 2
    bits_per_sample = 16
    num_samples = sample_rate  # 1 second
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    data_size = num_samples * channels * bits_per_sample // 8

    # Generate simple audio data (sine-like pattern for demonstration)
    audio_data = bytes([i % 256 for i in range(data_size)])

    # Write WAV file
    with open(filepath, 'wb') as f:
        # RIFF header
        f.write(b'RIFF')
        chunks_size = 4 + 8 + 16 + 8 + data_size
        f.write(struct.pack('<I', chunks_size))
        f.write(b'WAVE')

        # Format chunk
        f.write(b'fmt ')
        f.write(struct.pack('<I', 16))
        fmt_data = struct.pack('<HHIIHH', 1, channels, sample_rate,
                               byte_rate, block_align, bits_per_sample)
        f.write(fmt_data)

        # Data chunk
        f.write(b'data')
        f.write(struct.pack('<I', data_size))
        f.write(audio_data)

    return filepath


def main():
    """Example demonstrating riffy usage."""

    # Example 1: Basic parsing
    print("=" * 60)
    print("Riffy - WAV File Parser Example")
    print("=" * 60)

    wav_file = "example.wav"

    # Create a sample WAV file if it doesn't exist
    if not Path(wav_file).exists():
        print(f"\nCreating sample WAV file: {wav_file}")
        create_sample_wav(wav_file)
        print("Sample file created successfully!")

    try:
        # Create parser instance
        parser = WAVParser(wav_file)

        # Parse the file
        print(f"\nParsing: {wav_file}")
        info = parser.parse()

        # Display format information
        print("\nFormat Information:")
        print(f"  Sample Rate: {info['format']['sample_rate']:,} Hz")
        print(f"  Channels: {info['format']['channels']}")
        print(f"  Bit Depth: {info['format']['bits_per_sample']} bits")
        print(f"  Audio Format: {'PCM' if info['format']['is_pcm'] else 'Compressed'}")
        print(f"  Byte Rate: {info['format']['byte_rate']:,} bytes/sec")
        print(f"  Block Align: {info['format']['block_align']} bytes")

        # Display file information
        print("\nFile Information:")
        print(f"  File Size: {info['file_size']:,} bytes")
        print(f"  Duration: {info['duration_seconds']:.2f} seconds")
        print(f"  Audio Data Size: {info['audio_data_size']:,} bytes")
        print(f"  Sample Count: {info['sample_count']:,}")

        # Display chunks
        print("\nRIFF Chunks:")
        for chunk_id, chunk_size in info['chunks'].items():
            print(f"  {chunk_id!r}: {chunk_size:,} bytes")

        # Example 2: Access raw data
        print("\nRaw Audio Data:")
        print(f"  First 16 bytes: {parser.audio_data[:16].hex()}")

        # Example 3: Iterate through chunks
        print("\nDetailed Chunk Information:")
        for chunk_id, chunk in parser.chunks.items():
            print(f"  Chunk ID: {chunk_id!r}")
            print(f"    Size: {chunk.size:,} bytes")
            print(f"    Offset: {chunk.offset:,}")
            print()

        # Example 4: Pretty print all information as JSON
        print("\nComplete Information (JSON):")
        print(json.dumps(info, indent=2))

    except FileNotFoundError:
        print(f"\nError: File '{wav_file}' not found.")
        print("Please provide a valid WAV file path.")
    except InvalidWAVFormatError as e:
        print(f"\nError: Invalid WAV format - {e}")
    except CorruptedFileError as e:
        print(f"\nError: Corrupted file - {e}")
    except Exception as e:
        print(f"\nUnexpected error: {e}")


if __name__ == "__main__":
    main()
