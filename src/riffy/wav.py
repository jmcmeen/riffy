import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from .exceptions import (
    CorruptedFileError,
    InvalidChunkError,
    InvalidWAVFormatError,
    MissingChunkError,
    UnsupportedFormatError,
    WAVError,
)


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


# The largest value a 32-bit little-endian size field can hold. In RF64/BW64
# files, a size field set to this value is a sentinel meaning "the real 64-bit
# size lives in the ds64 chunk."
_SIZE32_MAX = 0xFFFFFFFF

# RIFF form identifiers. RF64 (EBU Tech 3306) and BW64 (ITU-R BS.2088) are the
# 64-bit large-file variants; both carry sizes in a leading ds64 chunk.
_CLASSIC_FORM = "RIFF"
_RF64_FORMS = ("RF64", "BW64")


@dataclass
class _Ds64:
    """Parsed contents of a ``ds64`` chunk (64-bit sizes for an RF64/BW64 file)."""

    riff_size: int
    data_size: int
    sample_count: int
    # Per-chunk 64-bit sizes for non-``data`` chunks that exceed 4 GB, keyed by ID.
    table: dict[str, int]


def _rf64_required(classic_riff_size: int, chunk_sizes: list[int]) -> bool:
    """Whether a file must use the RF64/BW64 form to represent its sizes.

    RF64 is needed when the overall RIFF size or any individual chunk size
    exceeds what a 32-bit little-endian size field can hold.
    """
    if classic_riff_size > _SIZE32_MAX:
        return True
    return any(size > _SIZE32_MAX for size in chunk_sizes)


class WAVParser:
    """Pure Python WAV file parser."""

    def __init__(self, file_path: str | Path):
        """Initialize parser with file path and automatically parse the file."""
        self.file_path = Path(file_path)
        self.format_info: WAVFormat | None = None
        # chunks maps a 4-character chunk ID to the ordered list of every chunk
        # with that ID, so files carrying duplicate IDs (e.g. multiple ``LIST``
        # chunks) preserve all occurrences in file order. See ``get_chunk`` /
        # ``get_chunks`` for ergonomic access.
        self.chunks: dict[str, list[WAVChunk]] = {}
        self.audio_data: bytes | None = None
        self._file_size = 0
        # RIFF form of the file on disk: "RIFF" (classic), or "RF64"/"BW64" for
        # the 64-bit large-file variants.
        self.riff_form: str = _CLASSIC_FORM
        self._ds64: _Ds64 | None = None

        # Automatically parse the file on initialization
        self.parse()

    @property
    def is_rf64(self) -> bool:
        """Whether the file on disk uses the RF64/BW64 (64-bit) large-file form."""
        return self.riff_form in _RF64_FORMS

    def parse(self) -> dict:
        """Parse the WAV file and return comprehensive information.

        Re-parsing re-reads the file from disk and discards any in-memory
        modifications previously made via ``add_chunk``, ``replace_chunk``,
        or ``set_chunk``.
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"WAV file not found: {self.file_path}")

        # Reset state so re-parsing reflects the file on disk, not prior edits.
        self.format_info = None
        self.chunks = {}
        self.audio_data = None
        self.riff_form = _CLASSIC_FORM
        self._ds64 = None

        self._file_size = self.file_path.stat().st_size

        with open(self.file_path, "rb") as f:
            self._parse_riff_header(f)
            self._parse_chunks(f)
            self._calculate_duration()
            self._validate_format()

        return self.get_info()

    def _parse_riff_header(self, f: BinaryIO) -> None:
        """Parse the RIFF/RF64/BW64 header."""
        riff_header = f.read(12)
        if len(riff_header) != 12:
            raise CorruptedFileError("File too small to be a valid WAV file")

        riff_id, file_size, wave_id = struct.unpack("<4sI4s", riff_header)

        form = riff_id.decode("latin-1")
        if form != _CLASSIC_FORM and form not in _RF64_FORMS:
            raise InvalidWAVFormatError("Not a valid RIFF file")
        self.riff_form = form

        if wave_id != b"WAVE":
            raise InvalidWAVFormatError("Not a valid WAV file")

    def _parse_chunks(self, f: BinaryIO) -> None:
        """Parse all chunks in the WAV file."""
        # An RF64/BW64 file must lead with a ds64 chunk carrying the 64-bit sizes.
        if self.is_rf64:
            self._parse_ds64(f)

        while True:
            chunk_header = f.read(8)
            if len(chunk_header) < 8:
                break

            chunk_id, chunk_size = struct.unpack("<4sI", chunk_header)

            # Decode chunk ID with strict ASCII validation
            try:
                chunk_id = chunk_id.decode("ascii")
            except UnicodeDecodeError as e:
                raise InvalidChunkError(f"Invalid chunk ID (non-ASCII bytes): {chunk_id!r}") from e
            if len(chunk_id) != 4:  # pragma: no cover - defensive; 4 bytes always decode to 4 chars
                raise InvalidChunkError(f"Invalid chunk ID length: {len(chunk_id)}")

            # In RF64/BW64, a 0xFFFFFFFF size is a sentinel: the real 64-bit size
            # comes from the ds64 chunk (dedicated field for 'data', table for
            # other chunks).
            if self.is_rf64 and chunk_size == _SIZE32_MAX:
                chunk_size = self._resolve_ds64_size(chunk_id)

            chunk_offset = f.tell()
            chunk_data = f.read(chunk_size)
            if len(chunk_data) != chunk_size:
                raise CorruptedFileError(f"Incomplete chunk: {chunk_id}")

            self.chunks.setdefault(chunk_id, []).append(
                WAVChunk(id=chunk_id, size=chunk_size, data=chunk_data, offset=chunk_offset)
            )

            # Format/audio state is taken from the first occurrence of each ID.
            if chunk_id == "fmt " and self.format_info is None:
                self._parse_format_chunk(chunk_data)
            elif chunk_id == "data" and self.audio_data is None:
                self.audio_data = chunk_data

            if chunk_size % 2:
                f.read(1)

    def _parse_ds64(self, f: BinaryIO) -> None:
        """Parse the mandatory leading ds64 chunk of an RF64/BW64 file."""
        header = f.read(8)
        if len(header) < 8 or header[:4] != b"ds64":
            raise InvalidWAVFormatError(f"{self.riff_form} file must begin with a 'ds64' chunk")
        (ds64_size,) = struct.unpack("<I", header[4:8])
        data = f.read(ds64_size)
        if len(data) != ds64_size or ds64_size < 28:
            raise CorruptedFileError("Incomplete or undersized 'ds64' chunk")

        riff_size, data_size, sample_count, table_length = struct.unpack("<QQQI", data[:28])
        table: dict[str, int] = {}
        offset = 28
        for _ in range(table_length):
            if offset + 12 > len(data):
                raise CorruptedFileError("Truncated 'ds64' size table")
            entry_id = data[offset : offset + 4].decode("latin-1")
            (entry_size,) = struct.unpack("<Q", data[offset + 4 : offset + 12])
            table[entry_id] = entry_size
            offset += 12

        self._ds64 = _Ds64(
            riff_size=riff_size,
            data_size=data_size,
            sample_count=sample_count,
            table=table,
        )
        if ds64_size % 2:  # honor even-byte padding like any other chunk
            f.read(1)

    def _resolve_ds64_size(self, chunk_id: str) -> int:
        """Resolve a 0xFFFFFFFF sentinel size to its real 64-bit value from ds64."""
        if self._ds64 is None:  # pragma: no cover - guarded by is_rf64 caller
            raise CorruptedFileError("Size sentinel encountered without a ds64 chunk")
        if chunk_id == "data":
            return self._ds64.data_size
        if chunk_id in self._ds64.table:
            return self._ds64.table[chunk_id]
        raise CorruptedFileError(
            f"Chunk '{chunk_id}' uses the 64-bit size sentinel but has no ds64 table entry"
        )

    def _parse_format_chunk(self, data: bytes) -> None:
        """Parse the format chunk."""
        if len(data) < 16:
            raise InvalidWAVFormatError("Format chunk too small")

        fmt_data = struct.unpack("<HHIIHH", data[:16])
        audio_format = fmt_data[0]

        # Non-PCM formats have extra fields (cbSize + extension data)
        if audio_format != 1 and len(data) < 18:
            raise InvalidWAVFormatError(
                f"Non-PCM format (type {audio_format}) requires at least 18 bytes in format chunk"
            )

        # For non-PCM formats, read cbSize to validate extension data
        if audio_format != 1:
            cb_size = struct.unpack("<H", data[16:18])[0]
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
            bits_per_sample=fmt_data[5],
        )

    def _calculate_duration(self) -> None:
        """Calculate audio duration after all chunks are parsed."""
        if self.audio_data and self.format_info and self.format_info.byte_rate > 0:
            self.format_info.duration_seconds = len(self.audio_data) / self.format_info.byte_rate

    def _validate_format(self) -> None:
        """Validate the parsed format."""
        if not self.format_info:
            raise MissingChunkError("No 'fmt ' chunk found")

        if not self.format_info.is_pcm:
            raise UnsupportedFormatError(
                f"Unsupported audio format: {self.format_info.audio_format} (only PCM is supported)"
            )

        if self.format_info.channels == 0:
            raise InvalidWAVFormatError("Invalid number of channels")

        if self.format_info.sample_rate == 0:
            raise InvalidWAVFormatError("Invalid sample rate")

        if self.audio_data is None:
            raise MissingChunkError("No 'data' chunk found")

    def get_info(self) -> dict:
        """Get comprehensive information about the WAV file."""
        if not self.format_info:
            raise WAVError("File not parsed yet. Call parse() first.")

        info = {
            "file_path": str(self.file_path),
            "file_size": self._file_size,
            "format": {
                "audio_format": self.format_info.audio_format,
                "channels": self.format_info.channels,
                "sample_rate": self.format_info.sample_rate,
                "byte_rate": self.format_info.byte_rate,
                "block_align": self.format_info.block_align,
                "bits_per_sample": self.format_info.bits_per_sample,
                "is_pcm": self.format_info.is_pcm,
            },
            "duration_seconds": self.format_info.duration_seconds,
            "audio_data_size": len(self.audio_data) if self.audio_data else 0,
            "sample_count": self._calculate_sample_count(),
            "chunks": {
                chunk_id: [chunk.size for chunk in chunk_list]
                for chunk_id, chunk_list in self.chunks.items()
            },
        }

        return info

    def get_chunks(self, chunk_id: str) -> list[WAVChunk]:
        """Return every chunk with the given ID, in file order (empty if none)."""
        return self.chunks.get(chunk_id, [])

    def get_chunk(self, chunk_id: str) -> WAVChunk | None:
        """Return the first chunk with the given ID, or ``None`` if absent.

        Convenience accessor for the common single-occurrence case, so callers
        do not have to index into the per-ID list returned by ``chunks``.
        """
        chunk_list = self.chunks.get(chunk_id)
        return chunk_list[0] if chunk_list else None

    def get_chunk_bytes(self, chunk_id: str) -> bytes | None:
        """Return the raw payload of the first chunk with the given ID, or ``None``.

        This is the raw-bytes accessor the metadata layer decodes from.
        """
        chunk = self.get_chunk(chunk_id)
        return chunk.data if chunk else None

    def _calculate_sample_count(self) -> int:
        """Calculate total number of samples."""
        if not self.audio_data or not self.format_info:
            return 0

        bytes_per_sample = self.format_info.bits_per_sample // 8
        return len(self.audio_data) // (bytes_per_sample * self.format_info.channels)

    def export_chunk(self, chunk_id: str, output_path: str | Path) -> int:
        """
        Export a specific chunk's data to a binary file.

        Args:
            chunk_id: The ID of the chunk to export (e.g., 'fmt ', 'data')
            output_path: Path where the chunk data will be written

        Returns:
            Number of bytes written

        Raises:
            WAVError: If file hasn't been parsed yet or file write errors occur
            MissingChunkError: If the specified chunk doesn't exist

        Example:
            >>> parser = WAVParser("audio.wav")
            >>> parser.export_chunk('data', 'audio_data.bin')
            176400
        """
        if not self.format_info:
            raise WAVError("File not parsed yet. Call parse() first.")

        chunk = self.get_chunk(chunk_id)
        if chunk is None:
            available_chunks = ", ".join(self.chunks.keys())
            raise MissingChunkError(
                f"Chunk '{chunk_id}' not found. Available chunks: {available_chunks}"
            )

        output_path = Path(output_path)

        try:
            with open(output_path, "wb") as f:
                f.write(chunk.data)
        except OSError as e:
            raise WAVError(f"Failed to write chunk to {output_path}: {e}") from e

        return len(chunk.data)

    def export_audio_data(self, output_path: str | Path) -> int:
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
            >>> parser.export_audio_data('raw_audio.bin')
            176400
        """
        if not self.format_info:
            raise WAVError("File not parsed yet. Call parse() first.")

        if not self.audio_data:
            raise WAVError("No audio data available to export.")

        return self.export_chunk("data", output_path)

    def list_chunks(self) -> dict[str, list[dict[str, int]]]:
        """
        List all chunks in the WAV file with their sizes and offsets.

        Because a WAV file may contain multiple chunks with the same ID, each ID
        maps to a list of ``{"size", "offset"}`` entries in file order.

        Returns:
            Dictionary mapping chunk IDs to a list of their occurrences' metadata

        Raises:
            WAVError: If file hasn't been parsed yet

        Example:
            >>> parser = WAVParser("audio.wav")
            >>> chunks = parser.list_chunks()
            >>> print(chunks)
            {'fmt ': [{'size': 16, 'offset': 12}], 'data': [{'size': 176400, 'offset': 36}]}
        """
        if not self.format_info:
            raise WAVError("File not parsed yet. Call parse() first.")

        return {
            chunk_id: [{"size": chunk.size, "offset": chunk.offset} for chunk in chunk_list]
            for chunk_id, chunk_list in self.chunks.items()
        }

    def replace_chunk(self, chunk_id: str, new_data: bytes) -> None:
        """
        Replace an existing chunk's data with new data.

        When a file contains multiple chunks with the same ID, this replaces the
        first occurrence and leaves the others untouched.

        Args:
            chunk_id: The ID of the chunk to replace (e.g., 'fmt ', 'data')
            new_data: The new chunk data (raw bytes)

        Raises:
            WAVError: If file hasn't been parsed yet
            MissingChunkError: If the specified chunk doesn't exist

        Example:
            >>> parser = WAVParser("audio.wav")
            >>> with open("new_data.bin", "rb") as f:
            ...     parser.replace_chunk('data', f.read())
            >>> parser.write_wav("modified.wav")
        """
        if not self.format_info:
            raise WAVError("File not parsed yet. Call parse() first.")

        chunk_list = self.chunks.get(chunk_id)
        if not chunk_list:
            available_chunks = ", ".join(self.chunks.keys())
            raise MissingChunkError(
                f"Chunk '{chunk_id}' not found. Available chunks: {available_chunks}"
            )

        # Update the first occurrence's data, preserving its offset.
        old_chunk = chunk_list[0]
        chunk_list[0] = WAVChunk(
            id=chunk_id,
            size=len(new_data),
            data=new_data,
            offset=old_chunk.offset,  # Offset will be recalculated on write
        )

        # Update audio_data if this is the data chunk
        if chunk_id == "data":
            self.audio_data = new_data
            self._calculate_duration()

    def add_chunk(self, chunk_id: str, chunk_data: bytes) -> None:
        """
        Add a chunk to the WAV file, appending it after any existing chunks with
        the same ID.

        Unlike v0.2.x, adding a chunk whose ID already exists is allowed and
        appends a new occurrence (the chunk store now keeps every occurrence).
        Use ``replace_chunk`` to overwrite an existing occurrence instead.

        Args:
            chunk_id: The ID of the new chunk (must be exactly 4 ASCII characters)
            chunk_data: The chunk data (raw bytes)

        Raises:
            WAVError: If file hasn't been parsed yet
            InvalidChunkError: If chunk_id is not exactly 4 ASCII characters

        Example:
            >>> parser = WAVParser("audio.wav")
            >>> parser.add_chunk('INFO', b'Artist: Example')
            >>> parser.write_wav("modified.wav")
        """
        if not self.format_info:
            raise WAVError("File not parsed yet. Call parse() first.")

        # Validate chunk_id
        if len(chunk_id) != 4:
            raise InvalidChunkError(f"Chunk ID must be exactly 4 characters, got {len(chunk_id)}")

        try:
            chunk_id.encode("ascii")
        except UnicodeEncodeError as e:
            raise InvalidChunkError(
                f"Chunk ID must contain only ASCII characters: {chunk_id!r}"
            ) from e

        # Append a new occurrence, preserving any existing chunks with this ID.
        self.chunks.setdefault(chunk_id, []).append(
            WAVChunk(
                id=chunk_id,
                size=len(chunk_data),
                data=chunk_data,
                offset=0,  # Will be calculated on write
            )
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
            InvalidChunkError: If chunk_id is not exactly 4 ASCII characters

        Example:
            >>> parser = WAVParser("audio.wav")
            >>> parser.set_chunk('INFO', b'Artist: Example')
            >>> parser.write_wav("modified.wav")
        """
        if not self.format_info:
            raise WAVError("File not parsed yet. Call parse() first.")

        # Validate chunk_id
        if len(chunk_id) != 4:
            raise InvalidChunkError(f"Chunk ID must be exactly 4 characters, got {len(chunk_id)}")

        try:
            chunk_id.encode("ascii")
        except UnicodeEncodeError as e:
            raise InvalidChunkError(
                f"Chunk ID must contain only ASCII characters: {chunk_id!r}"
            ) from e

        if chunk_id in self.chunks:
            self.replace_chunk(chunk_id, chunk_data)
        else:
            self.add_chunk(chunk_id, chunk_data)

    def copy_chunk_from_parser(self, chunk_id: str, source_parser: "WAVParser") -> None:
        """
        Copy a chunk from another WAVParser instance.

        Args:
            chunk_id: The ID of the chunk to copy
            source_parser: The source WAVParser instance to copy from

        Raises:
            WAVError: If either file hasn't been parsed yet
            MissingChunkError: If the chunk doesn't exist in the source parser

        Example:
            >>> parser1 = WAVParser("audio1.wav")
            >>> parser2 = WAVParser("audio2.wav")
            >>> parser2.copy_chunk_from_parser('data', parser1)
            >>> parser2.write_wav("modified.wav")
        """
        if not self.format_info:
            raise WAVError("File not parsed yet. Call parse() first.")

        if not source_parser.format_info:
            raise WAVError("Source parser hasn't been parsed yet.")

        source_chunk = source_parser.get_chunk(chunk_id)
        if source_chunk is None:
            available_chunks = ", ".join(source_parser.chunks.keys())
            raise MissingChunkError(
                f"Chunk '{chunk_id}' not found in source. Available chunks: {available_chunks}"
            )

        self.set_chunk(chunk_id, source_chunk.data)

    def remove_chunk(self, chunk_id: str, index: int | None = None) -> None:
        """
        Remove a chunk from the in-memory chunk store.

        When the file carries multiple chunks with the same ID, ``index`` selects
        which occurrence to remove (in file order); with the default
        ``index=None`` every occurrence of ``chunk_id`` is removed. Call
        ``write_wav(...)`` afterwards to persist the change to disk.

        Removing the ``fmt `` or ``data`` chunk is allowed but leaves the file
        un-writable until it is restored, since ``write_wav`` requires both.

        Args:
            chunk_id: The ID of the chunk to remove (e.g., 'guan', 'LIST')
            index: The occurrence to remove, or ``None`` to remove all of them

        Raises:
            WAVError: If file hasn't been parsed yet
            MissingChunkError: If the chunk ID (or the given index) is absent

        Example:
            >>> parser = WAVParser("audio.wav")
            >>> parser.remove_chunk('guan')
            >>> parser.write_wav("stripped.wav")
        """
        if not self.format_info:
            raise WAVError("File not parsed yet. Call parse() first.")

        chunk_list = self.chunks.get(chunk_id)
        if not chunk_list:
            available_chunks = ", ".join(self.chunks.keys())
            raise MissingChunkError(
                f"Chunk '{chunk_id}' not found. Available chunks: {available_chunks}"
            )

        if index is None:
            del self.chunks[chunk_id]
        else:
            if index < 0 or index >= len(chunk_list):
                raise MissingChunkError(
                    f"Chunk '{chunk_id}' has no occurrence at index {index} "
                    f"(found {len(chunk_list)})"
                )
            del chunk_list[index]
            if not chunk_list:
                del self.chunks[chunk_id]

        # Keep audio_data consistent if the data chunk is now gone entirely.
        if chunk_id == "data" and "data" not in self.chunks:
            self.audio_data = None

    def write_wav(
        self,
        output_path: str | Path,
        overwrite: bool = False,
        force_rf64: bool = False,
    ) -> int:
        """
        Write the WAV file with all modifications to disk.

        This method reconstructs the entire WAV file, properly updating all
        chunk offsets and the RIFF file size.

        Classic 32-bit WAV output is used whenever the file fits, byte-for-byte
        identical to prior versions. The RF64/BW64 large-file form (with a
        ``ds64`` chunk carrying 64-bit sizes) is emitted only when a size crosses
        the 4 GB 32-bit limit, or when ``force_rf64`` is set.

        Args:
            output_path: Path where the WAV file will be written
            overwrite: If True, allow overwriting the source file. Default is False
                      for safety.
            force_rf64: If True, always emit the RF64/BW64 form even when the
                      sizes would fit in classic WAV. Useful for workflows that
                      require BW64 output.

        Returns:
            Number of bytes written

        Raises:
            WAVError: If file hasn't been parsed yet
            FileExistsError: If output_path is the same as input and overwrite=False
            MissingChunkError: If required chunks are missing

        Example:
            >>> parser = WAVParser("audio.wav")
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
                "Output path is the same as input file. Set overwrite=True to allow this operation."
            )

        # Ensure required chunks exist
        if "fmt " not in self.chunks:
            raise MissingChunkError("Cannot write WAV file without 'fmt ' chunk")

        if "data" not in self.chunks:
            raise MissingChunkError("Cannot write WAV file without 'data' chunk")

        ordered = self._write_order()

        # Classic RIFF size (excludes the ds64 chunk, which only exists in RF64).
        classic_riff_size = 4 + sum(8 + c.size + (c.size % 2) for c in ordered)
        need_rf64 = force_rf64 or _rf64_required(classic_riff_size, [c.size for c in ordered])

        if need_rf64:
            return self._write_rf64(output_path, ordered)
        return self._write_classic(output_path, ordered, classic_riff_size)

    def _write_order(self) -> list[WAVChunk]:
        """Return every chunk in write order: ``fmt `` first, ``data`` next, then
        remaining IDs sorted, with each ID's occurrences in file order."""
        order_ids: list[str] = []
        if "fmt " in self.chunks:
            order_ids.append("fmt ")
        if "data" in self.chunks:
            order_ids.append("data")
        for chunk_id in sorted(self.chunks.keys()):
            if chunk_id not in order_ids:
                order_ids.append(chunk_id)

        ordered: list[WAVChunk] = []
        for chunk_id in order_ids:
            ordered.extend(self.chunks[chunk_id])
        return ordered

    def _write_classic(self, output_path: Path, ordered: list[WAVChunk], riff_size: int) -> int:
        """Write a classic 32-bit RIFF/WAVE file (byte-for-byte stable output)."""
        bytes_written = 0
        with open(output_path, "wb") as f:
            f.write(b"RIFF")
            f.write(struct.pack("<I", riff_size))
            f.write(b"WAVE")
            bytes_written += 12

            for chunk in ordered:
                f.write(chunk.id.encode("ascii"))
                f.write(struct.pack("<I", chunk.size))
                f.write(chunk.data)
                bytes_written += 8 + chunk.size
                if chunk.size % 2:
                    f.write(b"\x00")
                    bytes_written += 1

        return bytes_written

    def _write_rf64(self, output_path: Path, ordered: list[WAVChunk]) -> int:
        """Write an RF64/BW64 file, moving 64-bit sizes into a leading ds64 chunk."""
        # Classify sizes: the first 'data' chunk gets the dedicated ds64 field;
        # any non-'data' chunk over 4 GB goes in the ds64 size table.
        data_size = 0
        first_data_seen = False
        table: dict[str, int] = {}
        for chunk in ordered:
            if chunk.id == "data" and not first_data_seen:
                data_size = chunk.size
                first_data_seen = True
            elif chunk.size > _SIZE32_MAX:
                table[chunk.id] = chunk.size

        block_align = self.format_info.block_align if self.format_info else 0
        sample_count = data_size // block_align if block_align else 0

        ds64_payload = self._build_ds64_payload(0, data_size, sample_count, table)
        ds64_chunk_len = len(ds64_payload)  # 28 + 12*len(table); always even
        riff_size = (
            4  # 'WAVE'
            + (8 + ds64_chunk_len)  # the ds64 chunk
            + sum(8 + c.size + (c.size % 2) for c in ordered)
        )
        ds64_payload = self._build_ds64_payload(riff_size, data_size, sample_count, table)

        form = self.riff_form if self.riff_form in _RF64_FORMS else "RF64"

        bytes_written = 0
        with open(output_path, "wb") as f:
            f.write(form.encode("ascii"))
            f.write(struct.pack("<I", _SIZE32_MAX))  # size sentinel; real size in ds64
            f.write(b"WAVE")
            f.write(b"ds64")
            f.write(struct.pack("<I", ds64_chunk_len))
            f.write(ds64_payload)
            bytes_written += 12 + 8 + ds64_chunk_len

            first_data_written = False
            for chunk in ordered:
                if chunk.id == "data" and not first_data_written:
                    size_field = _SIZE32_MAX
                    first_data_written = True
                elif chunk.size > _SIZE32_MAX:
                    size_field = _SIZE32_MAX
                else:
                    size_field = chunk.size

                f.write(chunk.id.encode("ascii"))
                f.write(struct.pack("<I", size_field))
                f.write(chunk.data)
                bytes_written += 8 + chunk.size
                if chunk.size % 2:
                    f.write(b"\x00")
                    bytes_written += 1

        return bytes_written

    @staticmethod
    def _build_ds64_payload(
        riff_size: int, data_size: int, sample_count: int, table: dict[str, int]
    ) -> bytes:
        """Build a ds64 chunk payload from 64-bit sizes and an optional size table."""
        payload = struct.pack("<QQQI", riff_size, data_size, sample_count, len(table))
        for chunk_id, size in table.items():
            payload += chunk_id.encode("latin-1") + struct.pack("<Q", size)
        return payload
