import struct
from typing import Dict, Optional, Union
from dataclasses import dataclass
from pathlib import Path

from .exceptions import WAVError, InvalidWAVFormatError, CorruptedFileError

@dataclass
class WAVFormat:
    """WAV format information."""
    audio_format: int
    channels: int
    sample_rate: int
    byte_rate: int
    block_align: int
    bits_per_sample: int
    duration_seconds: float = 0.0

    @property
    def is_pcm(self) -> bool:
        """Check if format is PCM (uncompressed)."""
        return self.audio_format == 1


@dataclass
class WAVChunk:
    """Represents a RIFF chunk in the WAV file."""
    id: str
    size: int
    data: bytes
    offset: int


class WAVParser:
    """Pure Python WAV file parser."""
    
    def __init__(self, file_path: Union[str, Path]):
        """Initialize parser with file path."""
        self.file_path = Path(file_path)
        self.format_info: Optional[WAVFormat] = None
        self.chunks: Dict[str, WAVChunk] = {}
        self.audio_data: Optional[bytes] = None
        self._file_size = 0
        
    def parse(self) -> Dict:
        """Parse the WAV file and return comprehensive information."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"WAV file not found: {self.file_path}")
        
        self._file_size = self.file_path.stat().st_size
        
        with open(self.file_path, 'rb') as f:
            self._parse_riff_header(f)
            self._parse_chunks(f)
            self._calculate_duration()
            self._validate_format()
        
        return self.get_info()
    
    def _parse_riff_header(self, f) -> None:
        """Parse the RIFF header."""
        riff_header = f.read(12)
        if len(riff_header) != 12:
            raise CorruptedFileError("File too small to be a valid WAV file")
        
        riff_id, file_size, wave_id = struct.unpack('<4sI4s', riff_header)
        
        if riff_id != b'RIFF':
            raise InvalidWAVFormatError("Not a valid RIFF file")
        
        if wave_id != b'WAVE':
            raise InvalidWAVFormatError("Not a valid WAV file")
    
    def _parse_chunks(self, f) -> None:
        """Parse all chunks in the WAV file."""
        while True:
            chunk_header = f.read(8)
            if len(chunk_header) < 8:
                break

            chunk_id, chunk_size = struct.unpack('<4sI', chunk_header)

            # Decode chunk ID with strict ASCII validation
            try:
                chunk_id = chunk_id.decode('ascii')
                if len(chunk_id) != 4:
                    raise CorruptedFileError(f"Invalid chunk ID length: {len(chunk_id)}")
            except UnicodeDecodeError as e:
                raise CorruptedFileError(f"Invalid chunk ID (non-ASCII bytes): {chunk_id!r}") from e
            
            chunk_offset = f.tell()
            chunk_data = f.read(chunk_size)
            if len(chunk_data) != chunk_size:
                raise CorruptedFileError(f"Incomplete chunk: {chunk_id}")
            
            self.chunks[chunk_id] = WAVChunk(
                id=chunk_id,
                size=chunk_size,
                data=chunk_data,
                offset=chunk_offset
            )
            
            if chunk_id == 'fmt ':
                self._parse_format_chunk(chunk_data)
            elif chunk_id == 'data':
                self.audio_data = chunk_data
            
            if chunk_size % 2:
                f.read(1)
    
    def _parse_format_chunk(self, data: bytes) -> None:
        """Parse the format chunk."""
        if len(data) < 16:
            raise InvalidWAVFormatError("Format chunk too small")

        fmt_data = struct.unpack('<HHIIHH', data[:16])
        audio_format = fmt_data[0]

        # Non-PCM formats have extra fields (cbSize + extension data)
        if audio_format != 1 and len(data) < 18:
            raise InvalidWAVFormatError(
                f"Non-PCM format (type {audio_format}) requires at least 18 bytes in format chunk"
            )

        # For non-PCM formats, read cbSize to validate extension data
        if audio_format != 1:
            cb_size = struct.unpack('<H', data[16:18])[0]
            expected_size = 18 + cb_size
            if len(data) < expected_size:
                raise InvalidWAVFormatError(
                    f"Format chunk size ({len(data)} bytes) is smaller than expected "
                    f"({expected_size} bytes) for format type {audio_format}"
                )

        self.format_info = WAVFormat(
            audio_format=audio_format,
            channels=fmt_data[1],
            sample_rate=fmt_data[2],
            byte_rate=fmt_data[3],
            block_align=fmt_data[4],
            bits_per_sample=fmt_data[5]
        )
    
    def _calculate_duration(self) -> None:
        """Calculate audio duration after all chunks are parsed."""
        if self.audio_data and self.format_info and self.format_info.byte_rate > 0:
            self.format_info.duration_seconds = len(self.audio_data) / self.format_info.byte_rate
    
    def _validate_format(self) -> None:
        """Validate the parsed format."""
        if not self.format_info:
            raise InvalidWAVFormatError("No format chunk found")
        
        if not self.format_info.is_pcm:
            raise InvalidWAVFormatError(
                f"Unsupported audio format: {self.format_info.audio_format} "
                "(only PCM is supported)"
            )
        
        if self.format_info.channels == 0:
            raise InvalidWAVFormatError("Invalid number of channels")
        
        if self.format_info.sample_rate == 0:
            raise InvalidWAVFormatError("Invalid sample rate")
        
        if self.audio_data is None:
            raise InvalidWAVFormatError("No audio data found")
    
    def get_info(self) -> Dict:
        """Get comprehensive information about the WAV file."""
        if not self.format_info:
            raise WAVError("File not parsed yet. Call parse() first.")
        
        info = {
            'file_path': str(self.file_path),
            'file_size': self._file_size,
            'format': {
                'audio_format': self.format_info.audio_format,
                'channels': self.format_info.channels,
                'sample_rate': self.format_info.sample_rate,
                'byte_rate': self.format_info.byte_rate,
                'block_align': self.format_info.block_align,
                'bits_per_sample': self.format_info.bits_per_sample,
                'is_pcm': self.format_info.is_pcm
            },
            'duration_seconds': self.format_info.duration_seconds,
            'audio_data_size': len(self.audio_data) if self.audio_data else 0,
            'sample_count': self._calculate_sample_count(),
            'chunks': {chunk_id: chunk.size for chunk_id, chunk in self.chunks.items()}
        }
        
        return info
    
    def _calculate_sample_count(self) -> int:
        """Calculate total number of samples."""
        if not self.audio_data or not self.format_info:
            return 0

        bytes_per_sample = self.format_info.bits_per_sample // 8
        return len(self.audio_data) // (bytes_per_sample * self.format_info.channels)

    def export_chunk(self, chunk_id: str, output_path: Union[str, Path]) -> int:
        """
        Export a specific chunk's data to a binary file.

        Args:
            chunk_id: The ID of the chunk to export (e.g., 'fmt ', 'data')
            output_path: Path where the chunk data will be written

        Returns:
            Number of bytes written

        Raises:
            WAVError: If file hasn't been parsed yet or file write errors occur
            KeyError: If the specified chunk doesn't exist

        Example:
            >>> parser = WAVParser("audio.wav")
            >>> parser.parse()
            >>> parser.export_chunk('data', 'audio_data.bin')
            176400
        """
        if not self.format_info:
            raise WAVError("File not parsed yet. Call parse() first.")

        if chunk_id not in self.chunks:
            available_chunks = ', '.join(self.chunks.keys())
            raise KeyError(
                f"Chunk '{chunk_id}' not found. Available chunks: {available_chunks}"
            )

        chunk = self.chunks[chunk_id]
        output_path = Path(output_path)

        try:
            with open(output_path, 'wb') as f:
                f.write(chunk.data)
        except OSError as e:
            raise WAVError(f"Failed to write chunk to {output_path}: {e}") from e

        return len(chunk.data)

    def export_audio_data(self, output_path: Union[str, Path]) -> int:
        """
        Export raw audio data to a binary file (convenience method).

        This is equivalent to export_chunk('data', output_path) but provides
        a more intuitive interface for the common use case of extracting audio.

        Args:
            output_path: Path where the audio data will be written

        Returns:
            Number of bytes written

        Raises:
            WAVError: If file hasn't been parsed yet or no audio data exists

        Example:
            >>> parser = WAVParser("audio.wav")
            >>> parser.parse()
            >>> parser.export_audio_data('raw_audio.bin')
            176400
        """
        if not self.format_info:
            raise WAVError("File not parsed yet. Call parse() first.")

        if not self.audio_data:
            raise WAVError("No audio data available to export.")

        return self.export_chunk('data', output_path)

    def list_chunks(self) -> Dict[str, Dict[str, int]]:
        """
        List all chunks in the WAV file with their sizes and offsets.

        Returns:
            Dictionary mapping chunk IDs to their metadata (size and offset)

        Raises:
            WAVError: If file hasn't been parsed yet

        Example:
            >>> parser = WAVParser("audio.wav")
            >>> parser.parse()
            >>> chunks = parser.list_chunks()
            >>> print(chunks)
            {'fmt ': {'size': 16, 'offset': 12}, 'data': {'size': 176400, 'offset': 36}}
        """
        if not self.format_info:
            raise WAVError("File not parsed yet. Call parse() first.")

        return {
            chunk_id: {
                'size': chunk.size,
                'offset': chunk.offset
            }
            for chunk_id, chunk in self.chunks.items()
        }

    def replace_chunk(self, chunk_id: str, new_data: bytes) -> None:
        """
        Replace an existing chunk's data with new data.

        Args:
            chunk_id: The ID of the chunk to replace (e.g., 'fmt ', 'data')
            new_data: The new chunk data (raw bytes)

        Raises:
            WAVError: If file hasn't been parsed yet
            KeyError: If the specified chunk doesn't exist

        Example:
            >>> parser = WAVParser("audio.wav")
            >>> parser.parse()
            >>> with open("new_data.bin", "rb") as f:
            ...     parser.replace_chunk('data', f.read())
            >>> parser.write_wav("modified.wav")
        """
        if not self.format_info:
            raise WAVError("File not parsed yet. Call parse() first.")

        if chunk_id not in self.chunks:
            available_chunks = ', '.join(self.chunks.keys())
            raise KeyError(
                f"Chunk '{chunk_id}' not found. Available chunks: {available_chunks}"
            )

        # Update the chunk data
        old_chunk = self.chunks[chunk_id]
        self.chunks[chunk_id] = WAVChunk(
            id=chunk_id,
            size=len(new_data),
            data=new_data,
            offset=old_chunk.offset  # Offset will be recalculated on write
        )

        # Update audio_data if this is the data chunk
        if chunk_id == 'data':
            self.audio_data = new_data
            self._calculate_duration()

    def add_chunk(self, chunk_id: str, chunk_data: bytes) -> None:
        """
        Add a new chunk to the WAV file.

        Args:
            chunk_id: The ID of the new chunk (must be exactly 4 ASCII characters)
            chunk_data: The chunk data (raw bytes)

        Raises:
            WAVError: If file hasn't been parsed yet
            ValueError: If chunk_id is invalid or chunk already exists

        Example:
            >>> parser = WAVParser("audio.wav")
            >>> parser.parse()
            >>> parser.add_chunk('INFO', b'Artist: Example')
            >>> parser.write_wav("modified.wav")
        """
        if not self.format_info:
            raise WAVError("File not parsed yet. Call parse() first.")

        # Validate chunk_id
        if len(chunk_id) != 4:
            raise ValueError(f"Chunk ID must be exactly 4 characters, got {len(chunk_id)}")

        try:
            chunk_id.encode('ascii')
        except UnicodeEncodeError:
            raise ValueError(f"Chunk ID must contain only ASCII characters: {chunk_id!r}")

        if chunk_id in self.chunks:
            raise ValueError(
                f"Chunk '{chunk_id}' already exists. Use replace_chunk() to modify it."
            )

        # Add the new chunk
        self.chunks[chunk_id] = WAVChunk(
            id=chunk_id,
            size=len(chunk_data),
            data=chunk_data,
            offset=0  # Will be calculated on write
        )

    def set_chunk(self, chunk_id: str, chunk_data: bytes) -> None:
        """
        Set a chunk's data, replacing it if it exists or adding it if it doesn't.

        This is a convenience method that combines add_chunk and replace_chunk.

        Args:
            chunk_id: The ID of the chunk (must be exactly 4 ASCII characters)
            chunk_data: The chunk data (raw bytes)

        Raises:
            WAVError: If file hasn't been parsed yet
            ValueError: If chunk_id is invalid

        Example:
            >>> parser = WAVParser("audio.wav")
            >>> parser.parse()
            >>> parser.set_chunk('INFO', b'Artist: Example')
            >>> parser.write_wav("modified.wav")
        """
        if not self.format_info:
            raise WAVError("File not parsed yet. Call parse() first.")

        # Validate chunk_id
        if len(chunk_id) != 4:
            raise ValueError(f"Chunk ID must be exactly 4 characters, got {len(chunk_id)}")

        try:
            chunk_id.encode('ascii')
        except UnicodeEncodeError:
            raise ValueError(f"Chunk ID must contain only ASCII characters: {chunk_id!r}")

        if chunk_id in self.chunks:
            self.replace_chunk(chunk_id, chunk_data)
        else:
            self.add_chunk(chunk_id, chunk_data)

    def copy_chunk_from_parser(self, chunk_id: str, source_parser: 'WAVParser') -> None:
        """
        Copy a chunk from another WAVParser instance.

        Args:
            chunk_id: The ID of the chunk to copy
            source_parser: The source WAVParser instance to copy from

        Raises:
            WAVError: If either file hasn't been parsed yet
            KeyError: If the chunk doesn't exist in the source parser

        Example:
            >>> parser1 = WAVParser("audio1.wav")
            >>> parser1.parse()
            >>> parser2 = WAVParser("audio2.wav")
            >>> parser2.parse()
            >>> parser2.copy_chunk_from_parser('data', parser1)
            >>> parser2.write_wav("modified.wav")
        """
        if not self.format_info:
            raise WAVError("File not parsed yet. Call parse() first.")

        if not source_parser.format_info:
            raise WAVError("Source parser hasn't been parsed yet.")

        if chunk_id not in source_parser.chunks:
            available_chunks = ', '.join(source_parser.chunks.keys())
            raise KeyError(
                f"Chunk '{chunk_id}' not found in source. Available chunks: {available_chunks}"
            )

        source_chunk = source_parser.chunks[chunk_id]
        self.set_chunk(chunk_id, source_chunk.data)

    def write_wav(self, output_path: Union[str, Path], overwrite: bool = False) -> int:
        """
        Write the WAV file with all modifications to disk.

        This method reconstructs the entire WAV file, properly updating all
        chunk offsets and the RIFF file size.

        Args:
            output_path: Path where the WAV file will be written
            overwrite: If True, allow overwriting the source file. Default is False
                      for safety.

        Returns:
            Number of bytes written

        Raises:
            WAVError: If file hasn't been parsed yet
            FileExistsError: If output_path is the same as input and overwrite=False
            InvalidWAVFormatError: If required chunks are missing

        Example:
            >>> parser = WAVParser("audio.wav")
            >>> parser.parse()
            >>> parser.replace_chunk('data', new_audio_data)
            >>> parser.write_wav("modified.wav")
            176444
        """
        if not self.format_info:
            raise WAVError("File not parsed yet. Call parse() first.")

        output_path = Path(output_path)

        # Check if we're trying to overwrite the source file
        if output_path.resolve() == self.file_path.resolve() and not overwrite:
            raise FileExistsError(
                f"Output path is the same as input file. "
                f"Set overwrite=True to allow this operation."
            )

        # Ensure required chunks exist
        if 'fmt ' not in self.chunks:
            raise InvalidWAVFormatError("Cannot write WAV file without 'fmt ' chunk")

        if 'data' not in self.chunks:
            raise InvalidWAVFormatError("Cannot write WAV file without 'data' chunk")

        # Calculate total file size
        # RIFF header: 'RIFF' (4) + size (4) + 'WAVE' (4) = 12 bytes
        # Each chunk: id (4) + size (4) + data + padding (if odd size)
        chunks_size = 4  # 'WAVE' identifier

        for chunk in self.chunks.values():
            chunks_size += 8 + chunk.size  # header + data
            if chunk.size % 2:  # Add padding for odd-sized chunks
                chunks_size += 1

        riff_size = chunks_size

        # Write the file
        bytes_written = 0
        with open(output_path, 'wb') as f:
            # Write RIFF header
            f.write(b'RIFF')
            f.write(struct.pack('<I', riff_size))
            f.write(b'WAVE')
            bytes_written += 12

            # Write chunks in a consistent order: fmt first, then data, then others
            chunk_order = []
            if 'fmt ' in self.chunks:
                chunk_order.append('fmt ')
            if 'data' in self.chunks:
                chunk_order.append('data')

            # Add remaining chunks in sorted order for consistency
            for chunk_id in sorted(self.chunks.keys()):
                if chunk_id not in chunk_order:
                    chunk_order.append(chunk_id)

            for chunk_id in chunk_order:
                chunk = self.chunks[chunk_id]

                # Write chunk header
                f.write(chunk_id.encode('ascii'))
                f.write(struct.pack('<I', chunk.size))
                bytes_written += 8

                # Write chunk data
                f.write(chunk.data)
                bytes_written += chunk.size

                # Write padding byte if needed
                if chunk.size % 2:
                    f.write(b'\x00')
                    bytes_written += 1

        return bytes_written
