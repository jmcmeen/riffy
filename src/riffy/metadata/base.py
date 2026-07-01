"""Shared low-level primitives for the metadata layer.

These helpers are the building blocks the per-standard modules (GUANO, RIFF
INFO, ``bext``, ...) share:

- **FOURCC validation** — every RIFF/WAV chunk (and INFO subchunk) is keyed by a
  4-character ASCII ID.
- **Even-byte padding** — RIFF requires every chunk payload to be padded to an
  even length; GUANO and INFO both rely on this.
- **ZSTR handling** — RIFF INFO stores NUL-terminated strings; real-world
  recorders are sloppy about the terminator, so the reader tolerates its
  absence.
- **Fail-soft text decoding** — field recorders emit non-UTF-8 metadata in the
  wild, so text decoding falls back to latin-1 with a warning rather than
  raising (see the "fail soft on dirty data" design principle).

Nothing here reads or writes files; these operate purely on ``bytes`` so they
compose with the raw chunk payloads :class:`riffy.WAVParser` exposes.
"""

import warnings

from ..exceptions import InvalidChunkError

# Every RIFF chunk ID / INFO subchunk FOURCC is exactly four bytes.
FOURCC_SIZE = 4


def validate_fourcc(fourcc: str) -> bytes:
    """Validate a 4-character chunk ID and return its ASCII bytes.

    Args:
        fourcc: The chunk ID (e.g. ``"guan"``, ``"LIST"``, ``"fmt "``).

    Returns:
        The 4 ASCII bytes of the ID.

    Raises:
        InvalidChunkError: If the ID is not exactly four ASCII characters.

    Example:
        >>> validate_fourcc("guan")
        b'guan'
    """
    if len(fourcc) != FOURCC_SIZE:
        raise InvalidChunkError(
            f"Chunk ID must be exactly {FOURCC_SIZE} characters, got {len(fourcc)}"
        )
    try:
        return fourcc.encode("ascii")
    except UnicodeEncodeError as e:
        raise InvalidChunkError(f"Chunk ID must contain only ASCII characters: {fourcc!r}") from e


def pad_to_even(data: bytes, pad_byte: int = 0) -> bytes:
    """Pad ``data`` to an even length as RIFF requires.

    Args:
        data: The payload to pad.
        pad_byte: The byte value to append when padding is needed. Defaults to
            ``0`` (NUL); GUANO writers commonly reserve space with a space
            (``0x20``) instead.

    Returns:
        ``data`` unchanged if already even-length, otherwise ``data`` with one
        ``pad_byte`` appended.

    Example:
        >>> pad_to_even(b"abc")
        b'abc\\x00'
        >>> pad_to_even(b"abcd")
        b'abcd'
    """
    if len(data) % 2:
        return data + bytes([pad_byte])
    return data


def read_zstr(data: bytes, offset: int = 0, encoding: str = "latin-1") -> tuple[str, int]:
    """Read a NUL-terminated string from ``data`` starting at ``offset``.

    Tolerates a missing terminator: if no NUL byte is found, the remainder of
    ``data`` is decoded and the returned offset is ``len(data)``. This matches
    the behavior needed for RIFF INFO subchunks, whose producers do not reliably
    NUL-terminate their values.

    Args:
        data: The bytes to read from.
        offset: The index to start reading at.
        encoding: The text encoding to decode with. Defaults to ``latin-1``,
            which never raises on arbitrary bytes.

    Returns:
        A ``(text, next_offset)`` tuple, where ``next_offset`` is the index just
        past the terminating NUL (or ``len(data)`` if there was none).

    Example:
        >>> read_zstr(b"hello\\x00world\\x00")
        ('hello', 6)
    """
    end = data.find(b"\x00", offset)
    if end == -1:
        return data[offset:].decode(encoding), len(data)
    return data[offset:end].decode(encoding), end + 1


def write_zstr(text: str, encoding: str = "utf-8") -> bytes:
    """Encode ``text`` as a NUL-terminated string.

    Args:
        text: The string to encode.
        encoding: The text encoding to use. Defaults to UTF-8.

    Returns:
        The encoded bytes followed by a single NUL terminator.

    Example:
        >>> write_zstr("hello")
        b'hello\\x00'
    """
    return text.encode(encoding) + b"\x00"


def decode_text(data: bytes, context: str = "metadata") -> str:
    """Decode ``data`` as UTF-8, falling back to latin-1 with a warning.

    Field recorders produce non-UTF-8 metadata in the wild. Rather than raising
    and abandoning the whole chunk, this degrades to latin-1 (which round-trips
    any byte) and warns so the caller is aware the data was dirty.

    Args:
        data: The bytes to decode.
        context: A short label included in the warning to identify the source.

    Returns:
        The decoded string.

    Example:
        >>> decode_text(b"plain ascii")
        'plain ascii'
    """
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        warnings.warn(
            f"{context}: content is not valid UTF-8; falling back to latin-1",
            UnicodeWarning,
            stacklevel=2,
        )
        return data.decode("latin-1")
