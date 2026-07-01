"""RIFF INFO metadata: read and write the ``LIST``/``INFO`` chunk.

A RIFF INFO block is a ``LIST`` chunk whose list-type is ``INFO``, containing
NUL-terminated (ZSTR) subchunks each keyed by a 4-character FOURCC (``INAM`` for
title, ``IART`` for artist, ``ICMT`` for comment, ...). This module decodes that
payload into friendly typed attributes while keeping raw FOURCC access, and
rebuilds it on write.

Practical details handled here (see the v0.3.0 plan §5.2):

- Each value is a NUL-terminated string, but real-world producers are sloppy —
  the reader tolerates both terminated and non-terminated values.
- Each subchunk is padded to an even length; padding is honored on read and
  emitted on write.
- A file may carry several ``LIST`` chunks (e.g. an ``adtl`` list alongside the
  ``INFO`` one); this module targets the ``INFO`` list specifically and leaves
  the others untouched.

Values are treated as latin-1, which losslessly round-trips any byte and matches
the ASCII/codepage heritage of RIFF INFO. (UTF-8 metadata belongs in GUANO.)

This module is also the carrier the AudioMoth comment decoder reads from.
"""

import struct
import warnings

from ..wav import WAVChunk, WAVParser
from .base import read_zstr, validate_fourcc

#: The chunk ID that carries an INFO block.
CHUNK_ID = "LIST"

#: The ``LIST`` list-type that marks an INFO block.
LIST_TYPE = b"INFO"

#: Well-known INFO FOURCCs mapped to friendly attribute names.
KNOWN_TAGS: dict[str, str] = {
    "INAM": "title",
    "IART": "artist",
    "ICMT": "comment",
    "ICRD": "creation_date",
    "ICOP": "copyright",
    "ISFT": "software",
    "IENG": "engineer",
    "IGNR": "genre",
    "IPRD": "product",
    "ISRC": "source",
    "ITCH": "technician",
    "IKEY": "keywords",
    "ISBJ": "subject",
}


class InfoMetadata:
    """Typed, round-trip-safe view of a ``LIST``/``INFO`` block.

    Construct from a file via :meth:`from_parser` / :meth:`from_bytes`, or build
    a fresh one with ``InfoMetadata()``. Well-known tags are exposed as friendly
    ``str | None`` attributes (``title``, ``artist``, ``comment``, ...); every
    tag, known or not, is reachable by FOURCC via :meth:`get` / :meth:`set` and
    :attr:`tags`.
    """

    def __init__(self) -> None:
        # Ordered FOURCC -> value; dict preserves insertion order for round-trip.
        self._tags: dict[str, str] = {}

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    @classmethod
    def from_bytes(cls, data: bytes) -> "InfoMetadata":
        """Parse an INFO block from a raw ``LIST`` chunk payload.

        Args:
            data: The full ``LIST`` chunk payload, including the leading 4-byte
                list-type (which must be ``INFO``).

        Returns:
            A populated :class:`InfoMetadata`.

        Raises:
            ValueError: If the payload is not an ``INFO`` list.
        """
        if data[:4] != LIST_TYPE:
            raise ValueError(f"Not an INFO list (list-type is {data[:4]!r}, expected b'INFO')")

        self = cls()
        offset = 4
        n = len(data)
        while offset + 8 <= n:
            fourcc = data[offset : offset + 4].decode("latin-1")
            size = struct.unpack_from("<I", data, offset + 4)[0]
            offset += 8
            if offset + size > n:
                warnings.warn(
                    f"INFO: subchunk {fourcc!r} claims {size} bytes but only "
                    f"{n - offset} remain; truncating",
                    stacklevel=2,
                )
                size = n - offset
            value, _ = read_zstr(data[offset : offset + size])
            self._tags[fourcc] = value
            offset += size
            if size % 2:  # skip the even-alignment pad byte
                offset += 1
        return self

    @classmethod
    def from_parser(cls, parser: WAVParser) -> "InfoMetadata | None":
        """Parse the INFO block from a parser's ``LIST`` chunks.

        Scans every ``LIST`` chunk and decodes the first one whose list-type is
        ``INFO``.

        Args:
            parser: A parsed :class:`~riffy.WAVParser`.

        Returns:
            An :class:`InfoMetadata`, or ``None`` if the file has no INFO list.
        """
        for chunk in parser.get_chunks(CHUNK_ID):
            if chunk.data[:4] == LIST_TYPE:
                return cls.from_bytes(chunk.data)
        return None

    # ------------------------------------------------------------------ #
    # Raw FOURCC access
    # ------------------------------------------------------------------ #

    def get(self, fourcc: str, default: str | None = None) -> str | None:
        """Return the value for a FOURCC tag, or ``default`` if absent."""
        return self._tags.get(fourcc, default)

    def set(self, fourcc: str, value: str | None) -> None:
        """Set (or, when ``value`` is ``None``, remove) a FOURCC tag.

        Raises:
            InvalidChunkError: If ``fourcc`` is not exactly four ASCII characters.
        """
        validate_fourcc(fourcc)
        if value is None:
            self._tags.pop(fourcc, None)
        else:
            self._tags[fourcc] = value

    def remove(self, fourcc: str) -> None:
        """Delete a FOURCC tag if present (no error if absent)."""
        self._tags.pop(fourcc, None)

    def __contains__(self, fourcc: object) -> bool:
        return fourcc in self._tags

    @property
    def tags(self) -> dict[str, str]:
        """A copy of the full ``FOURCC -> value`` mapping, in order."""
        return dict(self._tags)

    # ------------------------------------------------------------------ #
    # Friendly typed attributes
    # ------------------------------------------------------------------ #

    @property
    def title(self) -> str | None:
        return self._tags.get("INAM")

    @title.setter
    def title(self, value: str | None) -> None:
        self.set("INAM", value)

    @property
    def artist(self) -> str | None:
        return self._tags.get("IART")

    @artist.setter
    def artist(self, value: str | None) -> None:
        self.set("IART", value)

    @property
    def comment(self) -> str | None:
        return self._tags.get("ICMT")

    @comment.setter
    def comment(self, value: str | None) -> None:
        self.set("ICMT", value)

    @property
    def creation_date(self) -> str | None:
        return self._tags.get("ICRD")

    @creation_date.setter
    def creation_date(self, value: str | None) -> None:
        self.set("ICRD", value)

    @property
    def copyright(self) -> str | None:
        return self._tags.get("ICOP")

    @copyright.setter
    def copyright(self, value: str | None) -> None:
        self.set("ICOP", value)

    @property
    def software(self) -> str | None:
        return self._tags.get("ISFT")

    @software.setter
    def software(self, value: str | None) -> None:
        self.set("ISFT", value)

    @property
    def engineer(self) -> str | None:
        return self._tags.get("IENG")

    @engineer.setter
    def engineer(self, value: str | None) -> None:
        self.set("IENG", value)

    @property
    def genre(self) -> str | None:
        return self._tags.get("IGNR")

    @genre.setter
    def genre(self, value: str | None) -> None:
        self.set("IGNR", value)

    @property
    def product(self) -> str | None:
        return self._tags.get("IPRD")

    @product.setter
    def product(self, value: str | None) -> None:
        self.set("IPRD", value)

    @property
    def source(self) -> str | None:
        return self._tags.get("ISRC")

    @source.setter
    def source(self, value: str | None) -> None:
        self.set("ISRC", value)

    @property
    def technician(self) -> str | None:
        return self._tags.get("ITCH")

    @technician.setter
    def technician(self, value: str | None) -> None:
        self.set("ITCH", value)

    @property
    def keywords(self) -> str | None:
        return self._tags.get("IKEY")

    @keywords.setter
    def keywords(self, value: str | None) -> None:
        self.set("IKEY", value)

    @property
    def subject(self) -> str | None:
        return self._tags.get("ISBJ")

    @subject.setter
    def subject(self, value: str | None) -> None:
        self.set("ISBJ", value)

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #

    def to_chunk_bytes(self) -> bytes:
        """Serialize to a ``LIST`` chunk payload (``INFO`` type + subchunks).

        Each value is written NUL-terminated and padded to even length. FOURCCs
        and values are encoded as latin-1, byte-for-byte, so anything read back
        (including non-ASCII tags produced by sloppy encoders) round-trips
        without loss. New tags added via :meth:`set` are already ASCII-validated
        on the way in.
        """
        out = bytearray(LIST_TYPE)
        for fourcc, value in self._tags.items():
            payload = value.encode("latin-1") + b"\x00"
            out += fourcc.encode("latin-1")
            out += struct.pack("<I", len(payload))
            out += payload
            if len(payload) % 2:
                out += b"\x00"
        return bytes(out)

    def write_to_parser(self, parser: WAVParser) -> None:
        """Write this INFO block into ``parser`` as a ``LIST`` chunk.

        Replaces the existing ``INFO`` ``LIST`` chunk if present (leaving any
        other ``LIST`` chunks, such as ``adtl``, untouched), otherwise appends a
        new one. Call ``parser.write_wav(...)`` afterwards to persist to disk.
        """
        payload = self.to_chunk_bytes()
        occurrences = parser.chunks.get(CHUNK_ID, [])
        for i, chunk in enumerate(occurrences):
            if chunk.data[:4] == LIST_TYPE:
                occurrences[i] = WAVChunk(
                    id=CHUNK_ID, size=len(payload), data=payload, offset=chunk.offset
                )
                return
        parser.add_chunk(CHUNK_ID, payload)
