#!/usr/bin/env python3
"""
Example usage of the riffy library for parsing WAV files.
"""

from riffy import WAVParser, InvalidWAVFormatError, CorruptedFileError
import json


def main():
    """Example demonstrating riffy usage."""

    # Example 1: Basic parsing
    print("=" * 60)
    print("Riffy - WAV File Parser Example")
    print("=" * 60)

    wav_file = "example.wav"  # Replace with your WAV file path

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
