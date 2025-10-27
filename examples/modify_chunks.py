#!/usr/bin/env python3
"""
Example demonstrating chunk modification functionality in riffy.

This script shows how to:
1. Replace existing chunks with data from binary files
2. Add new chunks to WAV files
3. Copy chunks between WAV files
4. Write modified WAV files while maintaining integrity
"""

from pathlib import Path
from riffy.wav import WAVParser


def example_replace_chunk_from_binary():
    """Replace a chunk with data from a binary file."""
    print("=== Example 1: Replace chunk from binary file ===\n")

    # This example assumes you have a WAV file and a binary file
    # In practice, you would use actual file paths
    print("# Parse the original WAV file")
    print("parser = WAVParser('audio.wav')")
    print("parser.get_info()")
    print()

    print("# Read new chunk data from a binary file")
    print("with open('new_audio_data.bin', 'rb') as f:")
    print("    new_data = f.read()")
    print()

    print("# Replace the data chunk")
    print("parser.replace_chunk('data', new_data)")
    print()

    print("# Write the modified WAV file")
    print("parser.write_wav('modified_audio.wav')")
    print()


def example_add_metadata_chunks():
    """Add custom metadata chunks to a WAV file."""
    print("=== Example 2: Add metadata chunks ===\n")

    print("# Parse the WAV file")
    print("parser = WAVParser('audio.wav')")
    print("parser.get_info()")
    print()

    print("# Add various metadata chunks (4-character IDs)")
    print("parser.add_chunk('INFO', b'Artist: Example Artist\\x00')")
    print("parser.add_chunk('LIST', b'Album: Example Album\\x00')")
    print("parser.add_chunk('cue ', b'Cue point markers...')")
    print()

    print("# Write to a new file")
    print("parser.write_wav('audio_with_metadata.wav')")
    print()


def example_copy_chunk_between_files():
    """Copy a chunk from one WAV file to another."""
    print("=== Example 3: Copy chunk between files ===\n")

    print("# Parse both WAV files")
    print("source = WAVParser('source.wav')")
    print("source")
    print()
    print("destination = WAVParser('destination.wav')")
    print("destination")
    print()

    print("# Copy the data chunk from source to destination")
    print("destination.copy_chunk_from_parser('data', source)")
    print()

    print("# Write the modified destination file")
    print("destination.write_wav('destination_modified.wav')")
    print()


def example_set_chunk_convenience():
    """Use set_chunk to add or replace chunks."""
    print("=== Example 4: Using set_chunk (add or replace) ===\n")

    print("# Parse the WAV file")
    print("parser = WAVParser('audio.wav')")
    print("parser.get_info()")
    print()

    print("# set_chunk will add if doesn't exist, replace if it does")
    print("parser.set_chunk('INFO', b'Version 1')")
    print("print('INFO chunk added')")
    print()

    print("# Calling again will replace the existing chunk")
    print("parser.set_chunk('INFO', b'Version 2')")
    print("print('INFO chunk replaced')")
    print()

    print("# Write the file")
    print("parser.write_wav('audio_updated.wav')")
    print()


def example_overwrite_original():
    """Overwrite the original WAV file."""
    print("=== Example 5: Overwrite original file (requires flag) ===\n")

    print("# Parse the WAV file")
    print("parser = WAVParser('audio.wav')")
    print("parser.get_info()")
    print()

    print("# Make modifications")
    print("parser.add_chunk('INFO', b'Modified')")
    print()

    print("# By default, overwriting the source is not allowed")
    print("try:")
    print("    parser.write_wav('audio.wav')  # This will raise FileExistsError")
    print("except FileExistsError:")
    print("    print('Cannot overwrite source without overwrite=True flag')")
    print()

    print("# Use overwrite=True to allow overwriting the source file")
    print("parser.write_wav('audio.wav', overwrite=True)")
    print("print('Original file successfully overwritten')")
    print()


def example_complete_workflow():
    """A complete workflow showing multiple operations."""
    print("=== Example 6: Complete workflow ===\n")

    print("from pathlib import Path")
    print("from riffy.wav import WAVParser")
    print()
    print("# Parse the original file")
    print("parser = WAVParser('original.wav')")
    print("info = parser.get_info()")
    print("print(f'Loaded WAV: {info[\"file_size\"]} bytes, {info[\"duration_seconds\"]:.2f} seconds')")
    print()

    print("# Export the current audio data as backup")
    print("parser.export_audio_data('backup_audio.bin')")
    print()

    print("# Load new audio data from another source")
    print("with open('new_audio.bin', 'rb') as f:")
    print("    new_audio = f.read()")
    print()

    print("# Replace the audio data")
    print("parser.replace_chunk('data', new_audio)")
    print("print(f'Replaced audio data: {len(new_audio)} bytes')")
    print()

    print("# Add metadata")
    print("parser.add_chunk('INFO', b'Processed audio\\x00')")
    print()

    print("# Write to new file")
    print("output_path = 'processed.wav'")
    print("bytes_written = parser.write_wav(output_path)")
    print("print(f'Written {bytes_written} bytes to {output_path}')")
    print()

    print("# Verify the output")
    print("verify = WAVParser(output_path)")
    print("verify")
    print("print(f'Verification: {len(verify.audio_data)} bytes audio, {len(verify.chunks)} chunks')")
    print("print(f'Chunks: {list(verify.chunks.keys())}')")
    print()


def main():
    """Run all examples."""
    print("=" * 70)
    print("RIFFY - WAV Chunk Modification Examples")
    print("=" * 70)
    print()

    example_replace_chunk_from_binary()
    print()

    example_add_metadata_chunks()
    print()

    example_copy_chunk_between_files()
    print()

    example_set_chunk_convenience()
    print()

    example_overwrite_original()
    print()

    example_complete_workflow()
    print()

    print("=" * 70)
    print("Key Points:")
    print("=" * 70)
    print("1. Always parse() before modifying chunks")
    print("2. Chunk IDs must be exactly 4 ASCII characters")
    print("3. Use replace_chunk() for existing chunks, add_chunk() for new ones")
    print("4. set_chunk() is a convenience method that does both")
    print("5. copy_chunk_from_parser() copies chunks between WAVParser instances")
    print("6. write_wav() reconstructs the file with correct offsets and sizes")
    print("7. Use overwrite=True to allow overwriting the source file")
    print("8. All chunk offsets and RIFF size are automatically updated on write")
    print()


if __name__ == "__main__":
    main()
