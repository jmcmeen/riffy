"""Tests for exception handling and error conditions."""
import pytest
from riffy.exceptions import (
    RiffyError,
    WAVError,
    InvalidWAVFormatError,
    CorruptedFileError,
    UnsupportedFormatError,
    ChunkError,
    InvalidChunkError,
    MissingChunkError,
)


class TestExceptionHierarchy:
    """Test exception class hierarchy."""

    def test_riffy_error_is_base(self):
        """Test RiffyError is the base exception."""
        assert issubclass(WAVError, RiffyError)
        assert issubclass(ChunkError, RiffyError)

    def test_wav_error_hierarchy(self):
        """Test WAVError subclass hierarchy."""
        assert issubclass(InvalidWAVFormatError, WAVError)
        assert issubclass(CorruptedFileError, WAVError)
        assert issubclass(UnsupportedFormatError, WAVError)

    def test_chunk_error_hierarchy(self):
        """Test ChunkError subclass hierarchy."""
        assert issubclass(InvalidChunkError, ChunkError)
        assert issubclass(MissingChunkError, ChunkError)

    def test_all_inherit_from_exception(self):
        """Test all custom exceptions inherit from Exception."""
        exceptions = [
            RiffyError,
            WAVError,
            InvalidWAVFormatError,
            CorruptedFileError,
            UnsupportedFormatError,
            ChunkError,
            InvalidChunkError,
            MissingChunkError,
        ]

        for exc in exceptions:
            assert issubclass(exc, Exception)


class TestExceptionMessages:
    """Test exception messages and raising."""

    def test_riffy_error_with_message(self):
        """Test RiffyError can be raised with message."""
        with pytest.raises(RiffyError, match="Test error"):
            raise RiffyError("Test error")

    def test_wav_error_with_message(self):
        """Test WAVError can be raised with message."""
        with pytest.raises(WAVError, match="WAV test error"):
            raise WAVError("WAV test error")

    def test_invalid_wav_format_error_with_message(self):
        """Test InvalidWAVFormatError can be raised with message."""
        with pytest.raises(InvalidWAVFormatError, match="Invalid format"):
            raise InvalidWAVFormatError("Invalid format")

    def test_corrupted_file_error_with_message(self):
        """Test CorruptedFileError can be raised with message."""
        with pytest.raises(CorruptedFileError, match="File corrupted"):
            raise CorruptedFileError("File corrupted")

    def test_unsupported_format_error_with_message(self):
        """Test UnsupportedFormatError can be raised with message."""
        with pytest.raises(UnsupportedFormatError, match="Format not supported"):
            raise UnsupportedFormatError("Format not supported")

    def test_chunk_error_with_message(self):
        """Test ChunkError can be raised with message."""
        with pytest.raises(ChunkError, match="Chunk error"):
            raise ChunkError("Chunk error")

    def test_invalid_chunk_error_with_message(self):
        """Test InvalidChunkError can be raised with message."""
        with pytest.raises(InvalidChunkError, match="Invalid chunk"):
            raise InvalidChunkError("Invalid chunk")

    def test_missing_chunk_error_with_message(self):
        """Test MissingChunkError can be raised with message."""
        with pytest.raises(MissingChunkError, match="Chunk missing"):
            raise MissingChunkError("Chunk missing")


class TestExceptionCatching:
    """Test exception catching patterns."""

    def test_catch_wav_error_catches_subclasses(self):
        """Test catching WAVError also catches its subclasses."""
        with pytest.raises(WAVError):
            raise InvalidWAVFormatError("Invalid")

        with pytest.raises(WAVError):
            raise CorruptedFileError("Corrupted")

        with pytest.raises(WAVError):
            raise UnsupportedFormatError("Unsupported")

    def test_catch_chunk_error_catches_subclasses(self):
        """Test catching ChunkError also catches its subclasses."""
        with pytest.raises(ChunkError):
            raise InvalidChunkError("Invalid")

        with pytest.raises(ChunkError):
            raise MissingChunkError("Missing")

    def test_catch_riffy_error_catches_all(self):
        """Test catching RiffyError catches all custom exceptions."""
        exceptions_to_test = [
            WAVError("test"),
            InvalidWAVFormatError("test"),
            CorruptedFileError("test"),
            UnsupportedFormatError("test"),
            ChunkError("test"),
            InvalidChunkError("test"),
            MissingChunkError("test"),
        ]

        for exc in exceptions_to_test:
            with pytest.raises(RiffyError):
                raise exc

    def test_specific_exception_not_caught_by_wrong_type(self):
        """Test that specific exceptions are not caught by wrong types."""
        with pytest.raises(InvalidWAVFormatError):
            try:
                raise InvalidWAVFormatError("test")
            except ChunkError:
                pytest.fail("Should not catch ChunkError")

        with pytest.raises(InvalidChunkError):
            try:
                raise InvalidChunkError("test")
            except WAVError:
                pytest.fail("Should not catch WAVError")
