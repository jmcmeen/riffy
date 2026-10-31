import os
import struct
import warnings
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
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

# Format codes (wFormatTag) riffy understands. Extensible files carry the real
# format code in the first two bytes of their subformat GUID.
WAVE_FORMAT_PCM = 0x0001
WAVE_FORMAT_IEEE_FLOAT = 0x0003
WAVE_FORMAT_EXTENSIBLE = 0xFFFE
# The 14 bytes after the format code in every KSDATAFORMAT_SUBTYPE_* GUID of the
# {XXXXXXXX-0000-0010-8000-00AA00389B71} family, as stored in a fmt chunk.
_KSDATAFORMAT_GUID_TAIL = bytes.fromhex("000000001000800000aa00389b71")
# Names for describe(); unknown codes are shown by number.
_FORMAT_NAMES = {
    WAVE_FORMAT_PCM: "PCM",
    0x0002: "ADPCM",
    WAVE_FORMAT_IEEE_FLOAT: "IEEE float",
    0x0006: "A-law",
    0x0007: "mu-law",
    0x0011: "IMA ADPCM",
    0x0055: "MPEG Layer 3",
}


@dataclass
class WAVFormat:
    """WAV format information.

    For ``WAVE_FORMAT_EXTENSIBLE`` files (``audio_format == 0xFFFE``) the
    extension fields are filled in: ``subformat`` is the format code from the
    subformat GUID (``None`` if the GUID isn't a standard KSDATAFORMAT one),
    ``valid_bits_per_sample`` the bits that carry signal, and ``channel_mask``
    the speaker-position bitmask.
    """

    audio_format: int
    channels: int
    sample_rate: int
    byte_rate: int
    block_align: int
    bits_per_sample: int
    duration_seconds: float = 0.0
    subformat: int | None = None
    valid_bits_per_sample: int | None = None
    channel_mask: int | None = None

    @property
    def is_extensible(self) -> bool:
        """Whether the file uses ``WAVE_FORMAT_EXTENSIBLE``."""
        return self.audio_format == WAVE_FORMAT_EXTENSIBLE

    @property
    def effective_format(self) -> int | None:
        """The format code that describes the samples.

        ``audio_format`` for ordinary files; the subformat for extensible ones
        (``None`` when an extensible file's subformat isn't recognized).
        """
        return self.subformat if self.is_extensible else self.audio_format

    @property
    def is_pcm(self) -> bool:
        """Whether the samples are integer PCM (plain, or extensible with a PCM subformat)."""
        return self.effective_format == WAVE_FORMAT_PCM

    @property
    def is_float(self) -> bool:
        """Whether the samples are IEEE float (format 3, or extensible with a float subformat)."""
        return self.effective_format == WAVE_FORMAT_IEEE_FLOAT

    @property
    def frame_size(self) -> int:
        """Bytes per frame (one sample for every channel): channels x whole bytes per sample."""
        return self.channels * -(-self.bits_per_sample // 8)

    def describe(self) -> str:
        """A short name for the sample format, e.g. ``"PCM"``, ``"IEEE float, extensible"``."""
        if self.is_extensible:
            if self.subformat is None:
                return "extensible (unrecognized subformat GUID)"
            return f"{_FORMAT_NAMES.get(self.subformat, f'format {self.subformat}')}, extensible"
        return _FORMAT_NAMES.get(self.audio_format, f"format {self.audio_format}")


@dataclass
class WAVChunk:
    """Represents a RIFF chunk in the WAV file.

    ``data`` is the payload, or ``None`` for a ``data`` chunk parsed with
    ``WAVParser(..., read_audio=False)``: its payload stays on disk at
    ``offset`` and is read on demand (see :meth:`WAVParser.read_chunk_data`).
    """

    id: str
    size: int
    data: bytes | None
    offset: int
    # True for chunks read from the file by the last parse, as opposed to ones
    # added or replaced in memory since; only those have a meaningful offset.
    from_file: bool = field(default=False, compare=False, repr=False)


# Block size for streaming payloads that were not read into memory.
_STREAM_BLOCK = 1 << 20


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


def _atomic_write(path: Path, write: "Callable[[Path], int]") -> int:
    """Run ``write`` on a temporary file next to ``path``, then move it into place.

    The temporary file gets ``path``'s permission bits when ``path`` exists, and
    is removed if ``write`` fails, so ``path`` is either untouched or complete.
    """
    import tempfile

    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".riffytmp")
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        written = write(tmp)
        if path.exists():
            mode = path.stat().st_mode & 0o7777
        else:  # what open(path, "w") would have created
            umask = os.umask(0)
            os.umask(umask)
            mode = 0o666 & ~umask
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return written


def _rf64_required(classic_riff_size: int, chunk_sizes: list[int]) -> bool:
    """Whether a file must use the RF64/BW64 form to represent its sizes.

    RF64 is needed when the overall RIFF size or any individual chunk size
    exceeds what a 32-bit little-endian size field can hold.
    """
    if classic_riff_size > _SIZE32_MAX:
        return True
    return any(size > _SIZE32_MAX for size in chunk_sizes)


class WAVParser:
    """Pure Python WAV file parser.

    By default the whole file, audio included, is read into memory and only PCM
    and IEEE float audio is accepted. With ``read_audio=False`` the ``data``
    payload is not read: riffy records where it is (``audio_offset``,
    ``audio_size``) and streams it when writing or exporting, so metadata work
    on a multi-GB recording costs only its headers. That mode accepts any audio
    format, since the samples are never interpreted.
    """

    def __init__(self, file_path: str | Path, *, read_audio: bool = True):
        """Initialize parser with file path and automatically parse the file.

        Args:
            file_path: WAV (RIFF, RF64 or BW64) file to parse.
            read_audio: Read the ``data`` payload into ``audio_data``. When
                False, ``audio_data`` stays ``None`` and the payload is read
                from disk only when needed.
        """
        self.file_path = Path(file_path)
        self.read_audio = read_audio
        self.format_info: WAVFormat | None = None
        # chunks maps a 4-character chunk ID to the ordered list of every chunk
        # with that ID, so files carrying duplicate IDs (e.g. multiple ``LIST``
        # chunks) preserve all occurrences in file order. See ``get_chunk`` /
        # ``get_chunks`` for ergonomic access.
        self.chunks: dict[str, list[WAVChunk]] = {}
        self.audio_data: bytes | None = None
        # Where the first data chunk's payload is, and how long, whether or not
        # it was read into audio_data.
        self.audio_offset: int | None = None
        self.audio_size = 0
        self._file_size = 0
        # (size, mtime_ns) of the file when parsed: payloads left on disk are only
        # streamed from the file they were found in.
        self._source_signature: tuple[int, int] | None = None
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
        self.audio_offset = None
        self.audio_size = 0
        self.riff_form = _CLASSIC_FORM
        self._ds64 = None

        stat = self.file_path.stat()
        self._file_size = stat.st_size
        self._source_signature = (stat.st_size, stat.st_mtime_ns)

        with open(self.file_path, "rb") as f:
            self._parse_riff_header(f)
            self._parse_chunks(f)
            self._refresh_audio_state()
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
            chunk_data: bytes | None
            if chunk_id == "data" and not self.read_audio:
                if chunk_offset + chunk_size > self._file_size:
                    raise CorruptedFileError(f"Incomplete chunk: {chunk_id}")
                chunk_data = None
                f.seek(chunk_size, os.SEEK_CUR)
            else:
                chunk_data = f.read(chunk_size)
                if len(chunk_data) != chunk_size:
                    raise CorruptedFileError(f"Incomplete chunk: {chunk_id}")

            self.chunks.setdefault(chunk_id, []).append(
                WAVChunk(
                    id=chunk_id,
                    size=chunk_size,
                    data=chunk_data,
                    offset=chunk_offset,
                    from_file=True,
                )
            )

            # Format/audio state is taken from the first occurrence of each ID.
            if chunk_id == "fmt " and self.format_info is None:
                assert chunk_data is not None
                self._parse_format_chunk(chunk_data)

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

        # Non-PCM formats have extra fields (cbSize + extension data). IEEE
        # float is exempt: plenty of writers emit a bare 16-byte fmt chunk for it.
        if audio_format not in (WAVE_FORMAT_PCM, WAVE_FORMAT_IEEE_FLOAT) and len(data) < 18:
            raise InvalidWAVFormatError(
                f"Non-PCM format (type {audio_format}) requires at least 18 bytes in format chunk"
            )

        # For non-PCM formats, read cbSize to validate extension data
        cb_size = 0
        if audio_format != WAVE_FORMAT_PCM and len(data) >= 18:
            cb_size = struct.unpack("<H", data[16:18])[0]
            expected_size = 18 + cb_size
            if len(data) < expected_size:
                raise InvalidWAVFormatError(
                    f"Format chunk size ({len(data)} bytes) is smaller than expected "
                    f"({expected_size} bytes) for format type {audio_format}"
                )

        subformat = valid_bits = channel_mask = None
        if audio_format == WAVE_FORMAT_EXTENSIBLE:
            # WAVEFORMATEXTENSIBLE: wValidBitsPerSample, dwChannelMask, SubFormat GUID.
            if cb_size < 22:
                raise InvalidWAVFormatError(
                    f"WAVE_FORMAT_EXTENSIBLE needs a 22-byte extension, got cbSize={cb_size}"
                )
            valid_bits, channel_mask = struct.unpack("<HI", data[18:24])
            guid = data[24:40]
            if guid[2:] == _KSDATAFORMAT_GUID_TAIL:
                subformat = struct.unpack("<H", guid[:2])[0]

        self.format_info = WAVFormat(
            audio_format=audio_format,
            channels=fmt_data[1],
            sample_rate=fmt_data[2],
            byte_rate=fmt_data[3],
            block_align=fmt_data[4],
            bits_per_sample=fmt_data[5],
            subformat=subformat,
            valid_bits_per_sample=valid_bits,
            channel_mask=channel_mask,
        )

    def _refresh_audio_state(self) -> None:
        """Derive audio_data/audio_size/audio_offset from the first data chunk."""
        chunk = self.get_chunk("data")
        if chunk is None:
            self.audio_data, self.audio_size, self.audio_offset = None, 0, None
        else:
            self.audio_data = chunk.data
            self.audio_size = chunk.size
            # The payload's position in the source file, while it is still the
            # chunk that was read from there.
            self.audio_offset = chunk.offset if chunk.from_file else None
        self._calculate_duration()

    def _calculate_duration(self) -> None:
        """Calculate audio duration after all chunks are parsed."""
        if self.format_info:
            byte_rate = self.format_info.byte_rate
            self.format_info.duration_seconds = (
                self.audio_size / byte_rate if self.audio_size and byte_rate > 0 else 0.0
            )

    def _validate_format(self) -> None:
        """Validate the parsed format.

        Without the audio (``read_audio=False``) any audio format is accepted,
        since riffy never interprets the samples; the structural checks still
        apply, and PCM/float files get the same bit-depth checks either way.
        """
        if not self.format_info:
            raise MissingChunkError("No 'fmt ' chunk found")

        fmt = self.format_info
        supported = fmt.is_pcm or fmt.is_float
        if not supported and self.read_audio:
            raise UnsupportedFormatError(
                f"Unsupported audio format: {fmt.describe()} "
                "(only PCM and IEEE float are supported)"
            )

        if fmt.channels == 0:
            raise InvalidWAVFormatError("Invalid number of channels")

        if fmt.sample_rate == 0:
            raise InvalidWAVFormatError("Invalid sample rate")

        if supported:
            if fmt.bits_per_sample == 0:
                raise InvalidWAVFormatError("Invalid bits per sample")

            if fmt.is_float and fmt.bits_per_sample not in (32, 64):
                raise InvalidWAVFormatError(
                    f"IEEE float samples must be 32 or 64 bits, not {fmt.bits_per_sample}"
                )

            if (
                fmt.valid_bits_per_sample is not None
                and fmt.valid_bits_per_sample > fmt.bits_per_sample
            ):
                raise InvalidWAVFormatError(
                    f"Valid bits per sample ({fmt.valid_bits_per_sample}) exceed the "
                    f"{fmt.bits_per_sample}-bit container"
                )

            if fmt.block_align != fmt.frame_size:
                warnings.warn(
                    f"fmt: block_align is {fmt.block_align} but {fmt.channels} channel(s) of "
                    f"{fmt.bits_per_sample}-bit samples need {fmt.frame_size}; "
                    f"using {fmt.frame_size}",
                    stacklevel=2,
                )

        if "data" not in self.chunks:
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
                "description": self.format_info.describe(),
                "is_pcm": self.format_info.is_pcm,
                "is_float": self.format_info.is_float,
                "is_extensible": self.format_info.is_extensible,
                "subformat": self.format_info.subformat,
                "valid_bits_per_sample": self.format_info.valid_bits_per_sample,
                "channel_mask": self.format_info.channel_mask,
            },
            "duration_seconds": self.format_info.duration_seconds,
            "audio_data_size": self.audio_size,
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
        return self.read_chunk_data(chunk) if chunk else None

    def read_chunk_data(self, chunk: WAVChunk) -> bytes:
        """Return a chunk's payload, reading it from disk if it wasn't loaded."""
        if chunk.data is not None:
            return chunk.data
        return b"".join(self.iter_chunk_data(chunk))

    def iter_chunk_data(self, chunk: WAVChunk, block_size: int = _STREAM_BLOCK) -> Iterator[bytes]:
        """Yield a chunk's payload in blocks, without holding it all in memory."""
        if chunk.data is not None:
            yield chunk.data
            return
        stat = self.file_path.stat()
        if (stat.st_size, stat.st_mtime_ns) != self._source_signature:
            raise WAVError(
                f"{self.file_path} changed since it was parsed; parse it again before "
                "reading audio that was left on disk"
            )
        with open(self.file_path, "rb") as f:
            f.seek(chunk.offset)
            remaining = chunk.size
            while remaining:
                block = f.read(min(block_size, remaining))
                if not block:
                    raise CorruptedFileError(f"Incomplete chunk: {chunk.id}")
                yield block
                remaining -= len(block)

    def _calculate_sample_count(self) -> int:
        """Calculate total number of samples."""
        fmt = self.format_info
        # Compressed formats have no fixed frame size; their count is unknown.
        if not self.audio_size or not fmt or not (fmt.is_pcm or fmt.is_float):
            return 0

        return self.audio_size // fmt.frame_size if fmt.frame_size else 0

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
                for block in self.iter_chunk_data(chunk):
                    f.write(block)
        except OSError as e:
            raise WAVError(f"Failed to write chunk to {output_path}: {e}") from e

        return chunk.size

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

        if not self.audio_size:
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

        # Keep format/audio state in step with the edited chunk
        if chunk_id == "fmt ":
            self._parse_format_chunk(self.read_chunk_data(self.chunks["fmt "][0]))
            self._calculate_duration()
        elif chunk_id == "data":
            self._refresh_audio_state()

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
        if chunk_id == "data":
            self._refresh_audio_state()

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

        self.set_chunk(chunk_id, source_parser.read_chunk_data(source_chunk))

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

        if chunk_id == "data":
            self._refresh_audio_state()

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

        # Write next to the real file (through any symlink) and swap it in, so a
        # failure never leaves a partial file and overwriting the source is safe
        # while its unread payloads are streamed from it.
        real_path = output_path.resolve()
        in_place = real_path == self.file_path.resolve()

        def write(target: Path) -> int:
            if need_rf64:
                return self._write_rf64(target, ordered)
            return self._write_classic(target, ordered, classic_riff_size)

        written = _atomic_write(real_path, write)
        if in_place and any(c.data is None for c in ordered):
            self.parse()  # payload offsets now refer to the rewritten file
        return written

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
                for block in self.iter_chunk_data(chunk):
                    f.write(block)
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

        fmt = self.format_info
        frame_size = fmt.frame_size if fmt and (fmt.is_pcm or fmt.is_float) else 0
        sample_count = data_size // frame_size if frame_size else 0

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
                for block in self.iter_chunk_data(chunk):
                    f.write(block)
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
