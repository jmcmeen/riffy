"""Tests for chunk export functionality."""
import pytest
from pathlib import Path
from riffy import WAVParser
from riffy.exceptions import WAVError


class TestExportChunk:
    """Test export_chunk method."""

    def test_export_data_chunk(self, valid_pcm_wav, tmp_path):
        """Test exporting the data chunk."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        output_file = tmp_path / "exported_data.bin"
        bytes_written = parser.export_chunk('data', output_file)

        assert bytes_written == valid_pcm_wav['data_size']
        assert output_file.exists()
        assert output_file.stat().st_size == valid_pcm_wav['data_size']

        # Verify content matches
        with open(output_file, 'rb') as f:
            exported_data = f.read()
        assert exported_data == parser.audio_data

    def test_export_fmt_chunk(self, valid_pcm_wav, tmp_path):
        """Test exporting the fmt chunk."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        output_file = tmp_path / "exported_fmt.bin"
        bytes_written = parser.export_chunk('fmt ', output_file)

        assert bytes_written == 16  # PCM format chunk is 16 bytes
        assert output_file.exists()
        assert output_file.stat().st_size == 16

        # Verify content matches
        with open(output_file, 'rb') as f:
            exported_data = f.read()
        assert exported_data == parser.chunks['fmt '].data

    def test_export_chunk_with_string_path(self, valid_pcm_wav, tmp_path):
        """Test export_chunk with string path instead of Path object."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        output_file = str(tmp_path / "exported.bin")
        bytes_written = parser.export_chunk('data', output_file)

        assert bytes_written == valid_pcm_wav['data_size']
        assert Path(output_file).exists()

    def test_export_nonexistent_chunk(self, valid_pcm_wav, tmp_path):
        """Test exporting a chunk that doesn't exist."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        output_file = tmp_path / "exported.bin"
        with pytest.raises(KeyError, match="Chunk 'JUNK' not found"):
            parser.export_chunk('JUNK', output_file)

    def test_export_chunk_error_message_shows_available(self, valid_pcm_wav, tmp_path):
        """Test that error message shows available chunks."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        output_file = tmp_path / "exported.bin"
        with pytest.raises(KeyError, match="Available chunks"):
            parser.export_chunk('INVALID', output_file)

    def test_export_chunk_overwrites_existing_file(self, valid_pcm_wav, tmp_path):
        """Test that export_chunk overwrites existing files."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        output_file = tmp_path / "exported.bin"

        # Create existing file with different content
        with open(output_file, 'wb') as f:
            f.write(b'existing content')

        # Export should overwrite
        bytes_written = parser.export_chunk('data', output_file)

        assert bytes_written == valid_pcm_wav['data_size']
        with open(output_file, 'rb') as f:
            content = f.read()
        assert content == parser.audio_data
        assert content != b'existing content'

    def test_export_multiple_chunks(self, valid_pcm_wav, tmp_path):
        """Test exporting multiple chunks."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        # Export fmt chunk
        fmt_file = tmp_path / "fmt.bin"
        fmt_bytes = parser.export_chunk('fmt ', fmt_file)

        # Export data chunk
        data_file = tmp_path / "data.bin"
        data_bytes = parser.export_chunk('data', data_file)

        assert fmt_bytes == 16
        assert data_bytes == valid_pcm_wav['data_size']
        assert fmt_file.exists()
        assert data_file.exists()

    def test_export_chunk_to_subdirectory(self, valid_pcm_wav, tmp_path):
        """Test exporting chunk to subdirectory."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        # Create subdirectory
        subdir = tmp_path / "exports"
        subdir.mkdir()

        output_file = subdir / "chunk.bin"
        bytes_written = parser.export_chunk('data', output_file)

        assert bytes_written == valid_pcm_wav['data_size']
        assert output_file.exists()


class TestExportAudioData:
    """Test export_audio_data convenience method."""

    def test_export_audio_data_basic(self, valid_pcm_wav, tmp_path):
        """Test basic audio data export."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        output_file = tmp_path / "audio.bin"
        bytes_written = parser.export_audio_data(output_file)

        assert bytes_written == valid_pcm_wav['data_size']
        assert output_file.exists()
        assert output_file.stat().st_size == valid_pcm_wav['data_size']

        # Verify content
        with open(output_file, 'rb') as f:
            exported_data = f.read()
        assert exported_data == parser.audio_data

    def test_export_audio_data_with_string_path(self, valid_pcm_wav, tmp_path):
        """Test export_audio_data with string path."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        output_file = str(tmp_path / "audio.bin")
        bytes_written = parser.export_audio_data(output_file)

        assert bytes_written == valid_pcm_wav['data_size']
        assert Path(output_file).exists()

    def test_export_audio_data_equivalent_to_export_chunk(self, valid_pcm_wav, tmp_path):
        """Test that export_audio_data is equivalent to export_chunk('data')."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        # Export using both methods
        audio_file = tmp_path / "audio.bin"
        chunk_file = tmp_path / "chunk.bin"

        audio_bytes = parser.export_audio_data(audio_file)
        chunk_bytes = parser.export_chunk('data', chunk_file)

        # Should be identical
        assert audio_bytes == chunk_bytes

        with open(audio_file, 'rb') as f:
            audio_content = f.read()
        with open(chunk_file, 'rb') as f:
            chunk_content = f.read()

        assert audio_content == chunk_content

    def test_export_audio_data_various_formats(self, tmp_path):
        """Test export_audio_data with various audio formats."""
        from tests.conftest import create_wav_file

        test_cases = [
            ('mono_8bit', {'channels': 1, 'bits_per_sample': 8, 'num_samples': 1000}),
            ('stereo_16bit', {'channels': 2, 'bits_per_sample': 16, 'num_samples': 1000}),
            ('mono_24bit', {'channels': 1, 'bits_per_sample': 24, 'num_samples': 1000}),
        ]

        for name, params in test_cases:
            wav_file = tmp_path / f"{name}.wav"
            wav_info = create_wav_file(wav_file, **params)

            parser = WAVParser(wav_file)

            output_file = tmp_path / f"{name}_audio.bin"
            bytes_written = parser.export_audio_data(output_file)

            assert bytes_written == wav_info['data_size']
            assert output_file.exists()


class TestListChunks:
    """Test list_chunks method."""

    def test_list_chunks_basic(self, valid_pcm_wav):
        """Test basic chunk listing."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        chunks = parser.list_chunks()

        assert isinstance(chunks, dict)
        assert 'fmt ' in chunks
        assert 'data' in chunks

    def test_list_chunks_structure(self, valid_pcm_wav):
        """Test structure of chunk listing."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        chunks = parser.list_chunks()

        # Check fmt chunk
        assert 'size' in chunks['fmt ']
        assert 'offset' in chunks['fmt ']
        assert chunks['fmt ']['size'] == 16  # PCM format
        assert isinstance(chunks['fmt ']['offset'], int)

        # Check data chunk
        assert 'size' in chunks['data']
        assert 'offset' in chunks['data']
        assert chunks['data']['size'] == valid_pcm_wav['data_size']
        assert isinstance(chunks['data']['offset'], int)

    def test_list_chunks_offsets(self, valid_pcm_wav):
        """Test that chunk offsets are correct."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        chunks = parser.list_chunks()

        # fmt chunk typically starts at offset 12 (after RIFF header)
        # data chunk starts after fmt chunk + padding
        assert chunks['fmt ']['offset'] > 0
        assert chunks['data']['offset'] > chunks['fmt ']['offset']

    def test_list_chunks_matches_parser_chunks(self, valid_pcm_wav):
        """Test that list_chunks matches internal chunks."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        chunks = parser.list_chunks()

        # Verify matches internal state
        for chunk_id, chunk_info in chunks.items():
            assert chunk_id in parser.chunks
            assert chunk_info['size'] == parser.chunks[chunk_id].size
            assert chunk_info['offset'] == parser.chunks[chunk_id].offset


class TestExportWorkflows:
    """Test real-world export workflows."""

    def test_parse_and_export_workflow(self, valid_pcm_wav, tmp_path):
        """Test complete workflow: parse then export."""
        parser = WAVParser(valid_pcm_wav['filepath'])
        info = parser.get_info()

        # Export audio data
        audio_file = tmp_path / "audio.bin"
        bytes_written = parser.export_audio_data(audio_file)

        assert bytes_written == info['audio_data_size']
        assert audio_file.exists()

    def test_export_all_chunks_workflow(self, valid_pcm_wav, tmp_path):
        """Test exporting all chunks from a file."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        # Get list of all chunks
        chunks = parser.list_chunks()

        # Export each chunk
        for chunk_id in chunks.keys():
            safe_id = chunk_id.strip().replace(' ', '_')
            output_file = tmp_path / f"{safe_id}.bin"
            parser.export_chunk(chunk_id, output_file)
            assert output_file.exists()

    def test_export_verify_content_workflow(self, valid_pcm_wav, tmp_path):
        """Test export and verify content matches original."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        # Export audio
        audio_file = tmp_path / "audio.bin"
        parser.export_audio_data(audio_file)

        # Read back and verify
        with open(audio_file, 'rb') as f:
            exported_content = f.read()

        assert len(exported_content) == valid_pcm_wav['data_size']
        assert exported_content == parser.audio_data

    def test_multiple_files_export_workflow(self, tmp_path):
        """Test exporting from multiple WAV files."""
        from tests.conftest import create_wav_file

        # Create multiple WAV files
        wav_files = []
        for i in range(3):
            wav_file = tmp_path / f"input_{i}.wav"
            wav_info = create_wav_file(wav_file, num_samples=1000 * (i + 1))
            wav_files.append((wav_file, wav_info))

        # Parse and export each
        for idx, (wav_file, wav_info) in enumerate(wav_files):
            parser = WAVParser(wav_file)

            output_file = tmp_path / f"output_{idx}.bin"
            bytes_written = parser.export_audio_data(output_file)

            assert bytes_written == wav_info['data_size']
            assert output_file.exists()

    def test_export_reparse_export_workflow(self, valid_pcm_wav, tmp_path):
        """Test parsing, exporting, re-parsing, re-exporting."""
        parser = WAVParser(valid_pcm_wav['filepath'])

        # First export
        first_export = tmp_path / "first.bin"
        first_bytes = parser.export_audio_data(first_export)

        # Second export (should be idempotent)
        second_export = tmp_path / "second.bin"
        second_bytes = parser.export_audio_data(second_export)

        assert first_bytes == second_bytes

        with open(first_export, 'rb') as f:
            first_content = f.read()
        with open(second_export, 'rb') as f:
            second_content = f.read()

        assert first_content == second_content
