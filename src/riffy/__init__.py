"""
Riffy - A low-dependency Python library for parsing and managing RIFF format files.

Riffy provides a pure Python implementation for parsing RIFF (Resource Interchange File Format)
files, with initial support for WAV audio files. The library is designed to have minimal
dependencies while providing robust parsing capabilities.

Main Features:
- Pure Python implementation with zero external dependencies
- Parse WAV files and extract format information
- Access individual RIFF chunks
- Extract audio data and metadata
- Validate file format and integrity

Basic Usage:
    >>> from riffy import WAVParser
    >>> parser = WAVParser("audio.wav")  # file is parsed on initialization
    >>> info = parser.get_info()
    >>> print(f"Sample rate: {info['format']['sample_rate']} Hz")
    >>> print(f"Duration: {info['duration_seconds']:.2f} seconds")
"""

__version__ = "0.2.1"
__author__ = "John McMeen"

# Import main classes and functions
from .exceptions import (
    ChunkError,
    CorruptedFileError,
    InvalidChunkError,
    InvalidWAVFormatError,
    MissingChunkError,
    RiffyError,
    UnsupportedFormatError,
    WAVError,
)
from .wav import WAVChunk, WAVFormat, WAVParser

__all__ = [
    # Version
    "__version__",
    "__author__",
    # WAV parsing
    "WAVParser",
    "WAVFormat",
    "WAVChunk",
    # Exceptions
    "RiffyError",
    "WAVError",
    "InvalidWAVFormatError",
    "CorruptedFileError",
    "UnsupportedFormatError",
    "ChunkError",
    "InvalidChunkError",
    "MissingChunkError",
]
