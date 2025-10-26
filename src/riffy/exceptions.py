"""Custom exceptions for the riffy RIFF parser library."""


class RiffyError(Exception):
    """Base exception for all riffy errors."""
    pass


class WAVError(RiffyError):
    """Base exception for WAV-related errors."""
    pass


class InvalidWAVFormatError(WAVError):
    """Raised when a WAV file has an invalid format."""
    pass


class CorruptedFileError(WAVError):
    """Raised when a file is corrupted or incomplete."""
    pass


class UnsupportedFormatError(WAVError):
    """Raised when a WAV format is not supported."""
    pass


class ChunkError(RiffyError):
    """Base exception for RIFF chunk-related errors."""
    pass


class InvalidChunkError(ChunkError):
    """Raised when a RIFF chunk is invalid."""
    pass


class MissingChunkError(ChunkError):
    """Raised when a required RIFF chunk is missing."""
    pass
