"""
Example demonstrating how to export chunks from WAV files.

This example shows:
1. Parsing a WAV file
2. Listing all chunks
3. Exporting specific chunks
4. Exporting raw audio data
"""

from pathlib import Path
from riffy import WAVParser


def export_example():
    """Demonstrate chunk export functionality."""
    # For this example, we'll create a simple WAV file first
    # In real usage, you would have an existing WAV file
    import struct

    wav_file = Path("example_audio.wav")

    # Create a simple WAV file (1 second, 16-bit stereo @ 44.1kHz)
    sample_rate = 44100
    channels = 2
    bits_per_sample = 16
    num_samples = sample_rate  # 1 second
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    data_size = num_samples * channels * bits_per_sample // 8

    # Generate simple audio data (sine-like pattern)
    audio_data = bytes([i % 256 for i in range(data_size)])

    # Write WAV file
    with open(wav_file, 'wb') as f:
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

    print(f"Created example WAV file: {wav_file}")
    print()

    # ===== Parse the WAV file =====
    parser = WAVParser(wav_file)
    info = parser.parse()

    print("WAV File Information:")
    print(f"  Sample Rate: {info['format']['sample_rate']} Hz")
    print(f"  Channels: {info['format']['channels']}")
    print(f"  Bits per Sample: {info['format']['bits_per_sample']}")
    print(f"  Duration: {info['duration_seconds']:.2f} seconds")
    print(f"  Audio Data Size: {info['audio_data_size']:,} bytes")
    print()

    # ===== List all chunks =====
    print("Available Chunks:")
    chunks = parser.list_chunks()
    for chunk_id, chunk_info in chunks.items():
        print(f"  '{chunk_id}': {chunk_info['size']:,} bytes at offset {chunk_info['offset']}")
    print()

    # ===== Export format chunk =====
    fmt_file = Path("format_chunk.bin")
    fmt_bytes = parser.export_chunk('fmt ', fmt_file)
    print(f"Exported format chunk: {fmt_bytes} bytes → {fmt_file}")

    # ===== Export data chunk (method 1: using export_chunk) =====
    data_file_1 = Path("audio_data_v1.bin")
    data_bytes_1 = parser.export_chunk('data', data_file_1)
    print(f"Exported data chunk: {data_bytes_1:,} bytes → {data_file_1}")

    # ===== Export audio data (method 2: using convenience method) =====
    data_file_2 = Path("audio_data_v2.bin")
    data_bytes_2 = parser.export_audio_data(data_file_2)
    print(f"Exported audio data: {data_bytes_2:,} bytes → {data_file_2}")
    print()

    # ===== Verify both methods produce identical results =====
    with open(data_file_1, 'rb') as f:
        content_1 = f.read()
    with open(data_file_2, 'rb') as f:
        content_2 = f.read()

    if content_1 == content_2:
        print("✓ Both export methods produced identical output")
    print()

    # ===== Export all chunks to separate files =====
    print("Exporting all chunks:")
    export_dir = Path("exported_chunks")
    export_dir.mkdir(exist_ok=True)

    for chunk_id in chunks.keys():
        # Create safe filename from chunk ID
        safe_name = chunk_id.strip().replace(' ', '_')
        output_file = export_dir / f"{safe_name}.bin"

        bytes_written = parser.export_chunk(chunk_id, output_file)
        print(f"  {chunk_id} → {output_file} ({bytes_written:,} bytes)")

    print()
    print("Export complete!")

    # ===== Cleanup =====
    print("\nCleaning up example files...")
    wav_file.unlink()
    fmt_file.unlink()
    data_file_1.unlink()
    data_file_2.unlink()
    for file in export_dir.iterdir():
        file.unlink()
    export_dir.rmdir()
    print("Done!")


def error_handling_example():
    """Demonstrate error handling in export operations."""
    print("\n" + "="*60)
    print("Error Handling Examples")
    print("="*60 + "\n")

    # Create a simple WAV file
    import struct
    wav_file = Path("test.wav")

    with open(wav_file, 'wb') as f:
        f.write(b'RIFF')
        f.write(struct.pack('<I', 36))
        f.write(b'WAVE')
        f.write(b'fmt ')
        f.write(struct.pack('<I', 16))
        f.write(struct.pack('<HHIIHH', 1, 2, 44100, 176400, 4, 16))
        f.write(b'data')
        f.write(struct.pack('<I', 4))
        f.write(b'\x00\x00\x00\x00')

    parser = WAVParser(wav_file)

    # Example 1: Export before parsing
    print("1. Attempting to export before parsing:")
    try:
        parser.export_audio_data("output.bin")
    except Exception as e:
        print(f"   Error: {e}")
    print()

    # Parse the file
    parser.parse()

    # Example 2: Export non-existent chunk
    print("2. Attempting to export non-existent chunk:")
    try:
        parser.export_chunk('JUNK', "output.bin")
    except KeyError as e:
        print(f"   Error: {e}")
    print()

    # Example 3: Successful export
    print("3. Successful export:")
    try:
        bytes_written = parser.export_audio_data("output.bin")
        print(f"   ✓ Exported {bytes_written} bytes successfully")
        Path("output.bin").unlink()
    except Exception as e:
        print(f"   Error: {e}")

    # Cleanup
    wav_file.unlink()


if __name__ == "__main__":
    export_example()
    error_handling_example()
