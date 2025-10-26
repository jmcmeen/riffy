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
    
    @property
    def is_pcm(self) -> bool:
        """Check if format is PCM (uncompressed)."""
        return self.audio_format == 1
    
    @property
    def duration_seconds(self) -> float:
        """Calculate duration based on byte rate (requires data size)."""
        return getattr(self, '_duration', 0.0)


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
            chunk_id = chunk_id.decode('ascii', errors='ignore')
            
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
        
        self.format_info = WAVFormat(
            audio_format=fmt_data[0],
            channels=fmt_data[1],
            sample_rate=fmt_data[2],
            byte_rate=fmt_data[3],
            block_align=fmt_data[4],
            bits_per_sample=fmt_data[5]
        )
    
    def _calculate_duration(self) -> None:
        """Calculate audio duration after all chunks are parsed."""
        if self.audio_data and self.format_info and self.format_info.byte_rate > 0:
            duration = len(self.audio_data) / self.format_info.byte_rate
            self.format_info._duration = duration
    
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
