"""Tests for chunk modification functionality (replace, add, write)."""
import struct
import pytest
from pathlib import Path
from riffy.wav import WAVParser, WAVChunk
from riffy.exceptions import WAVError, InvalidWAVFormatError


class TestReplaceChunk:
    """Tests for replace_chunk method."""

    def test_replace_data_chunk(self, valid_pcm_wav, tmp_path):
        """Test replacing the data chunk with new audio data."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        # Create new audio data (different size)
        new_audio_data = b'\x00\x01' * 1000  # 2000 bytes
        original_size = len(parser.audio_data)

        parser.replace_chunk('data', new_audio_data)

        assert parser.chunks['data'].size == 2000
        assert parser.chunks['data'].data == new_audio_data
        assert parser.audio_data == new_audio_data
        assert len(parser.audio_data) != original_size

    def test_replace_fmt_chunk(self, valid_pcm_wav, tmp_path):
        """Test replacing the fmt chunk."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        # Create new format data (change to mono, 8-bit)
        new_fmt_data = struct.pack('<HHIIHH', 1, 1, 22050, 22050, 1, 8)

        parser.replace_chunk('fmt ', new_fmt_data)

        assert parser.chunks['fmt '].size == 16
        assert parser.chunks['fmt '].data == new_fmt_data

    def test_replace_nonexistent_chunk(self, valid_pcm_wav):
        """Test replacing a chunk that doesn't exist."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        with pytest.raises(KeyError, match="Chunk 'INFO' not found"):
            parser.replace_chunk('INFO', b'test data')

    def test_replace_chunk_before_parse(self, valid_pcm_wav):
        """Test replacing a chunk before parsing."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        with pytest.raises(WAVError, match="File not parsed yet"):
            parser.replace_chunk('data', b'test')

    def test_replace_chunk_updates_duration(self, valid_pcm_wav):
        """Test that replacing data chunk updates duration calculation."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        original_duration = parser.format_info.duration_seconds

        # Create new audio data (half the size)
        original_size = len(parser.audio_data)
        new_audio_data = parser.audio_data[:original_size // 2]

        parser.replace_chunk('data', new_audio_data)

        # Duration should be approximately half
        assert parser.format_info.duration_seconds < original_duration
        assert abs(parser.format_info.duration_seconds - original_duration / 2) < 0.01


class TestAddChunk:
    """Tests for add_chunk method."""

    def test_add_new_chunk(self, valid_pcm_wav):
        """Test adding a new chunk."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        chunk_data = b'Artist: Test Artist\x00'
        parser.add_chunk('INFO', chunk_data)

        assert 'INFO' in parser.chunks
        assert parser.chunks['INFO'].data == chunk_data
        assert parser.chunks['INFO'].size == len(chunk_data)

    def test_add_chunk_with_invalid_length(self, valid_pcm_wav):
        """Test adding a chunk with invalid ID length."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        with pytest.raises(ValueError, match="must be exactly 4 characters"):
            parser.add_chunk('IN', b'test')

        with pytest.raises(ValueError, match="must be exactly 4 characters"):
            parser.add_chunk('INFOO', b'test')

    def test_add_chunk_with_non_ascii(self, valid_pcm_wav):
        """Test adding a chunk with non-ASCII characters."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        with pytest.raises(ValueError, match="must contain only ASCII characters"):
            parser.add_chunk('IN\xff\xff', b'test')

    def test_add_existing_chunk(self, valid_pcm_wav):
        """Test adding a chunk that already exists."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        with pytest.raises(ValueError, match="already exists"):
            parser.add_chunk('data', b'test')

    def test_add_chunk_before_parse(self, valid_pcm_wav):
        """Test adding a chunk before parsing."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        with pytest.raises(WAVError, match="File not parsed yet"):
            parser.add_chunk('INFO', b'test')

    def test_add_multiple_chunks(self, valid_pcm_wav):
        """Test adding multiple new chunks."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        parser.add_chunk('INFO', b'Artist: Test')
        parser.add_chunk('LIST', b'Some list data')
        parser.add_chunk('cue ', b'Cue points')

        assert len(parser.chunks) == 5  # fmt, data, INFO, LIST, cue
        assert all(chunk in parser.chunks for chunk in ['INFO', 'LIST', 'cue '])


class TestSetChunk:
    """Tests for set_chunk method."""

    def test_set_new_chunk(self, valid_pcm_wav):
        """Test set_chunk with a new chunk (should add it)."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        chunk_data = b'Test metadata'
        parser.set_chunk('INFO', chunk_data)

        assert 'INFO' in parser.chunks
        assert parser.chunks['INFO'].data == chunk_data

    def test_set_existing_chunk(self, valid_pcm_wav):
        """Test set_chunk with an existing chunk (should replace it)."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        new_data = b'\x00\x01' * 500
        parser.set_chunk('data', new_data)

        assert parser.chunks['data'].data == new_data
        assert parser.audio_data == new_data

    def test_set_chunk_with_invalid_id(self, valid_pcm_wav):
        """Test set_chunk with invalid chunk ID."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        with pytest.raises(ValueError, match="must be exactly 4 characters"):
            parser.set_chunk('ID', b'test')

    def test_set_chunk_before_parse(self, valid_pcm_wav):
        """Test set_chunk before parsing."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        with pytest.raises(WAVError, match="File not parsed yet"):
            parser.set_chunk('INFO', b'test')


class TestCopyChunkFromParser:
    """Tests for copy_chunk_from_parser method."""

    def test_copy_chunk_between_parsers(self, valid_pcm_wav, valid_mono_wav):
        """Test copying a chunk from one parser to another."""
        parser1 = WAVParser(valid_pcm_wav['filepath'])
        parser1.parse()

        parser2 = WAVParser(valid_mono_wav['filepath'])
        parser2.parse()

        # Get original data chunk from parser1
        original_data = parser1.chunks['data'].data

        # Copy data chunk from parser1 to parser2
        parser2.copy_chunk_from_parser('data', parser1)

        assert parser2.chunks['data'].data == original_data
        assert parser2.audio_data == original_data

    def test_copy_custom_chunk(self, valid_pcm_wav, valid_mono_wav):
        """Test copying a custom chunk between parsers."""
        parser1 = WAVParser(valid_pcm_wav['filepath'])
        parser1.parse()
        parser1.add_chunk('INFO', b'Metadata from parser1')

        parser2 = WAVParser(valid_mono_wav['filepath'])
        parser2.parse()

        parser2.copy_chunk_from_parser('INFO', parser1)

        assert 'INFO' in parser2.chunks
        assert parser2.chunks['INFO'].data == b'Metadata from parser1'

    def test_copy_nonexistent_chunk(self, valid_pcm_wav, valid_mono_wav):
        """Test copying a chunk that doesn't exist."""
        parser1 = WAVParser(valid_pcm_wav['filepath'])
        parser1.parse()

        parser2 = WAVParser(valid_mono_wav['filepath'])
        parser2.parse()

        with pytest.raises(KeyError, match="Chunk 'INFO' not found in source"):
            parser2.copy_chunk_from_parser('INFO', parser1)

    def test_copy_from_unparsed_source(self, valid_pcm_wav, valid_mono_wav):
        """Test copying from an unparsed source parser."""
        parser1 = WAVParser(valid_pcm_wav['filepath'])
        # Don't parse parser1

        parser2 = WAVParser(valid_mono_wav['filepath'])
        parser2.parse()

        with pytest.raises(WAVError, match="Source parser hasn't been parsed yet"):
            parser2.copy_chunk_from_parser('data', parser1)

    def test_copy_to_unparsed_destination(self, valid_pcm_wav, valid_mono_wav):
        """Test copying to an unparsed destination parser."""
        parser1 = WAVParser(valid_pcm_wav['filepath'])
        parser1.parse()

        parser2 = WAVParser(valid_mono_wav['filepath'])
        # Don't parse parser2

        with pytest.raises(WAVError, match="File not parsed yet"):
            parser2.copy_chunk_from_parser('data', parser1)


class TestWriteWav:
    """Tests for write_wav method."""

    def test_write_wav_to_new_file(self, valid_pcm_wav, tmp_path):
        """Test writing a WAV file to a new location."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        output_path = tmp_path / "output.wav"
        bytes_written = parser.write_wav(output_path)

        assert output_path.exists()
        assert bytes_written > 0
        assert output_path.stat().st_size == bytes_written

    def test_write_wav_preserves_data(self, valid_pcm_wav, tmp_path):
        """Test that written WAV file can be parsed and contains same data."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        original_audio = parser.audio_data
        original_fmt = parser.chunks['fmt '].data

        output_path = tmp_path / "output.wav"
        parser.write_wav(output_path)

        # Parse the written file
        parser2 = WAVParser(output_path)
        parser2.parse()

        assert parser2.audio_data == original_audio
        assert parser2.chunks['fmt '].data == original_fmt

    def test_write_wav_with_modifications(self, valid_pcm_wav, tmp_path):
        """Test writing a WAV file after modifications."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        # Modify the audio data
        new_audio = b'\x00\x01' * 5000
        parser.replace_chunk('data', new_audio)

        # Add a custom chunk
        parser.add_chunk('INFO', b'Modified audio')

        output_path = tmp_path / "modified.wav"
        parser.write_wav(output_path)

        # Verify the written file
        parser2 = WAVParser(output_path)
        parser2.parse()

        assert parser2.audio_data == new_audio
        assert 'INFO' in parser2.chunks
        assert parser2.chunks['INFO'].data == b'Modified audio'

    def test_write_wav_chunk_ordering(self, valid_pcm_wav, tmp_path):
        """Test that chunks are written in correct order (fmt, data, others)."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        parser.add_chunk('INFO', b'metadata')
        parser.add_chunk('cue ', b'cue data')

        output_path = tmp_path / "ordered.wav"
        parser.write_wav(output_path)

        # Read file and verify chunk order
        with open(output_path, 'rb') as f:
            f.read(12)  # Skip RIFF header

            # First chunk should be fmt
            chunk_id = f.read(4)
            assert chunk_id == b'fmt '

            chunk_size = struct.unpack('<I', f.read(4))[0]
            f.read(chunk_size)
            if chunk_size % 2:
                f.read(1)

            # Second chunk should be data
            chunk_id = f.read(4)
            assert chunk_id == b'data'

    def test_write_wav_odd_sized_chunks(self, valid_pcm_wav, tmp_path):
        """Test that odd-sized chunks are padded correctly."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        # Add chunk with odd size
        odd_data = b'X' * 15  # 15 bytes (odd)
        parser.add_chunk('INFO', odd_data)

        output_path = tmp_path / "padded.wav"
        parser.write_wav(output_path)

        # Verify the file can be parsed
        parser2 = WAVParser(output_path)
        parser2.parse()

        assert parser2.chunks['INFO'].data == odd_data

    def test_write_wav_overwrite_protection(self, valid_pcm_wav):
        """Test that overwriting source file requires explicit flag."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        with pytest.raises(FileExistsError, match="Set overwrite=True"):
            parser.write_wav(valid_pcm_wav['filepath'])

    def test_write_wav_overwrite_allowed(self, valid_pcm_wav, tmp_path):
        """Test that overwriting source file works with overwrite=True."""
        # Create a copy first to avoid modifying test fixture
        test_file = tmp_path / "test.wav"
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()
        parser.write_wav(test_file)

        # Now parse and modify the copy
        parser2 = WAVParser(test_file)
        parser2.parse()
        parser2.add_chunk('INFO', b'modified')

        # Overwrite the same file
        bytes_written = parser2.write_wav(test_file, overwrite=True)
        assert bytes_written > 0

        # Verify modification persisted
        parser3 = WAVParser(test_file)
        parser3.parse()
        assert 'INFO' in parser3.chunks

    def test_write_wav_before_parse(self, valid_pcm_wav, tmp_path):
        """Test writing WAV file before parsing."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        output_path = tmp_path / "output.wav"
        with pytest.raises(WAVError, match="File not parsed yet"):
            parser.write_wav(output_path)

    def test_write_wav_missing_fmt_chunk(self, valid_pcm_wav, tmp_path):
        """Test writing WAV file without fmt chunk."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        # Remove fmt chunk (not recommended, but testing error handling)
        del parser.chunks['fmt ']

        output_path = tmp_path / "output.wav"
        with pytest.raises(InvalidWAVFormatError, match="without 'fmt ' chunk"):
            parser.write_wav(output_path)

    def test_write_wav_missing_data_chunk(self, valid_pcm_wav, tmp_path):
        """Test writing WAV file without data chunk."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        # Remove data chunk
        del parser.chunks['data']

        output_path = tmp_path / "output.wav"
        with pytest.raises(InvalidWAVFormatError, match="without 'data' chunk"):
            parser.write_wav(output_path)

    def test_write_wav_file_size_calculation(self, valid_pcm_wav, tmp_path):
        """Test that RIFF file size is calculated correctly."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        output_path = tmp_path / "output.wav"
        parser.write_wav(output_path)

        # Read and verify RIFF size
        with open(output_path, 'rb') as f:
            f.read(4)  # Skip 'RIFF'
            riff_size = struct.unpack('<I', f.read(4))[0]

            # RIFF size should be file_size - 8 (RIFF header)
            file_size = output_path.stat().st_size
            assert riff_size == file_size - 8


class TestChunkModificationIntegration:
    """Integration tests for complete workflows."""

    def test_replace_audio_from_binary_file(self, valid_pcm_wav, tmp_path):
        """Test replacing audio data from a binary file."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        # Export original audio to binary
        binary_path = tmp_path / "audio.bin"
        parser.export_audio_data(binary_path)

        # Create modified binary data
        with open(binary_path, 'rb') as f:
            original_data = f.read()

        modified_data = original_data[:len(original_data) // 2]

        modified_binary_path = tmp_path / "modified_audio.bin"
        with open(modified_binary_path, 'wb') as f:
            f.write(modified_data)

        # Replace chunk with binary file data
        with open(modified_binary_path, 'rb') as f:
            parser.replace_chunk('data', f.read())

        # Write and verify
        output_path = tmp_path / "output.wav"
        parser.write_wav(output_path)

        parser2 = WAVParser(output_path)
        parser2.parse()
        assert parser2.audio_data == modified_data

    def test_swap_audio_between_files(self, valid_pcm_wav, valid_mono_wav, tmp_path):
        """Test swapping audio data between two WAV files."""
        parser1 = WAVParser(valid_pcm_wav['filepath'])
        parser1.parse()
        audio1 = parser1.audio_data

        parser2 = WAVParser(valid_mono_wav['filepath'])
        parser2.parse()
        audio2 = parser2.audio_data

        # Swap audio data
        parser1.copy_chunk_from_parser('data', parser2)
        parser2.replace_chunk('data', audio1)

        # Write both files
        output1 = tmp_path / "swapped1.wav"
        output2 = tmp_path / "swapped2.wav"

        parser1.write_wav(output1)
        parser2.write_wav(output2)

        # Verify swap
        verify1 = WAVParser(output1)
        verify1.parse()
        assert verify1.audio_data == audio2

        verify2 = WAVParser(output2)
        verify2.parse()
        assert verify2.audio_data == audio1

    def test_add_multiple_metadata_chunks(self, valid_pcm_wav, tmp_path):
        """Test adding multiple metadata chunks and writing."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        # Add various metadata chunks
        parser.add_chunk('INFO', b'Artist: Test Artist\x00')
        parser.add_chunk('LIST', b'Album: Test Album\x00')
        parser.add_chunk('cue ', b'Cue point data')

        output_path = tmp_path / "with_metadata.wav"
        parser.write_wav(output_path)

        # Verify all chunks are present
        parser2 = WAVParser(output_path)
        parser2.parse()

        assert 'INFO' in parser2.chunks
        assert 'LIST' in parser2.chunks
        assert 'cue ' in parser2.chunks
        assert parser2.audio_data == parser.audio_data

    def test_roundtrip_without_modifications(self, valid_pcm_wav, tmp_path):
        """Test that a file written without modifications is identical."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        parser.parse()

        output_path = tmp_path / "roundtrip.wav"
        parser.write_wav(output_path)

        # Parse both files and compare
        parser2 = WAVParser(output_path)
        parser2.parse()

        assert parser.audio_data == parser2.audio_data
        assert parser.chunks.keys() == parser2.chunks.keys()
        assert parser.format_info.audio_format == parser2.format_info.audio_format
        assert parser.format_info.channels == parser2.format_info.channels
        assert parser.format_info.sample_rate == parser2.format_info.sample_rate

    def test_modify_write_parse_write_cycle(self, valid_pcm_wav, tmp_path):
        """Test multiple modification and write cycles."""
        # First cycle
        parser1 = WAVParser(valid_pcm_wav['filepath'])
        parser1.parse()
        parser1.add_chunk('INFO', b'Version 1')

        output1 = tmp_path / "cycle1.wav"
        parser1.write_wav(output1)

        # Second cycle
        parser2 = WAVParser(output1)
        parser2.parse()
        parser2.set_chunk('INFO', b'Version 2')  # Replace
        parser2.add_chunk('LIST', b'New chunk')

        output2 = tmp_path / "cycle2.wav"
        parser2.write_wav(output2)

        # Verify final state
        parser3 = WAVParser(output2)
        parser3.parse()

        assert parser3.chunks['INFO'].data == b'Version 2'
        assert parser3.chunks['LIST'].data == b'New chunk'
        assert parser3.audio_data == parser1.audio_data
