"""Broadcast Wave ``bext`` metadata: read and write the fixed binary layout.

Unlike GUANO and RIFF INFO, the ``bext`` chunk (EBU Tech 3285) is a fixed
C-struct binary layout, not key-value text, so it is parsed with :mod:`struct`.
The layout grows across versions — v0 has the base fields, v1 adds the 64-byte
``UMID``, v2 adds five loudness fields — but the fixed portion is always 602
bytes (a ``Reserved`` region absorbs the difference), with ``CodingHistory``
filling the remainder of the chunk.

This module reads and writes all three versions. The writer is table-driven off
the ``version`` field and gates the version-specific regions accordingly; the v2
loudness fields are preserved verbatim on write but never computed (per the
v0.3.0 plan §5.3).
"""

import struct
from dataclasses import dataclass

from ..wav import WAVChunk, WAVParser

#: The Broadcast Wave chunk ID.
CHUNK_ID = "bext"

#: Size of the fixed portion of a ``bext`` chunk, before ``CodingHistory``.
FIXED_SIZE = 602

# The fixed 602-byte header. Strings are fixed-length NUL-padded byte fields;
# TimeReference is split into low/high 32-bit halves of a 64-bit value.
_HEADER = struct.Struct(
    "<"
    "256s"  # Description
    "32s"  # Originator
    "32s"  # OriginatorReference
    "10s"  # OriginationDate (YYYY-MM-DD)
    "8s"  # OriginationTime (HH:MM:SS)
    "I"  # TimeReferenceLow
    "I"  # TimeReferenceHigh
    "H"  # Version
    "64s"  # UMID (v1+)
    "h"  # LoudnessValue (v2+)
    "h"  # LoudnessRange (v2+)
    "h"  # MaxTruePeakLevel (v2+)
    "h"  # MaxMomentaryLoudness (v2+)
    "h"  # MaxShortTermLoudness (v2+)
    "180s"  # Reserved
)


def _decode_fixed(raw: bytes) -> str:
    """Decode a NUL-padded fixed-length byte field, trimming at the first NUL."""
    return raw.split(b"\x00", 1)[0].decode("latin-1")


def _encode_fixed(text: str, size: int) -> bytes:
    """Encode ``text`` to exactly ``size`` NUL-padded (and truncated) bytes."""
    return text.encode("latin-1")[:size].ljust(size, b"\x00")


@dataclass
class BextMetadata:
    """Typed view of a ``bext`` (Broadcast Wave) chunk.

    Version-specific fields are ``None`` when the chunk's ``version`` does not
    include them: ``umid`` requires v1+, and the five loudness fields require
    v2+.
    """

    description: str = ""
    originator: str = ""
    originator_reference: str = ""
    origination_date: str = ""
    origination_time: str = ""
    time_reference: int = 0
    version: int = 0
    umid: bytes | None = None
    loudness_value: int | None = None
    loudness_range: int | None = None
    max_true_peak_level: int | None = None
    max_momentary_loudness: int | None = None
    max_short_term_loudness: int | None = None
    coding_history: str = ""

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    @classmethod
    def from_bytes(cls, data: bytes) -> "BextMetadata":
        """Parse a ``bext`` chunk payload.

        Tolerates a truncated fixed header (a short chunk is zero-padded to the
        602-byte layout before unpacking), so malformed producers degrade rather
        than raise.
        """
        fixed = data[:FIXED_SIZE].ljust(FIXED_SIZE, b"\x00")
        (
            description,
            originator,
            originator_reference,
            origination_date,
            origination_time,
            tr_low,
            tr_high,
            version,
            umid,
            loud_value,
            loud_range,
            max_true_peak,
            max_momentary,
            max_short_term,
            _reserved,
        ) = _HEADER.unpack(fixed)

        return cls(
            description=_decode_fixed(description),
            originator=_decode_fixed(originator),
            originator_reference=_decode_fixed(originator_reference),
            origination_date=_decode_fixed(origination_date),
            origination_time=_decode_fixed(origination_time),
            time_reference=tr_low | (tr_high << 32),
            version=version,
            # Version-gated: only interpret regions the declared version defines.
            umid=umid if version >= 1 else None,
            loudness_value=loud_value if version >= 2 else None,
            loudness_range=loud_range if version >= 2 else None,
            max_true_peak_level=max_true_peak if version >= 2 else None,
            max_momentary_loudness=max_momentary if version >= 2 else None,
            max_short_term_loudness=max_short_term if version >= 2 else None,
            coding_history=data[FIXED_SIZE:].split(b"\x00", 1)[0].decode("latin-1"),
        )

    @classmethod
    def from_parser(cls, parser: WAVParser) -> "BextMetadata | None":
        """Parse the ``bext`` chunk from a parser, or ``None`` if absent."""
        data = parser.get_chunk_bytes(CHUNK_ID)
        if data is None:
            return None
        return cls.from_bytes(data)

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #

    def to_chunk_bytes(self) -> bytes:
        """Serialize to a ``bext`` chunk payload, gated by ``version``.

        Version-specific regions are emitted only when ``version`` includes
        them; otherwise they are zero-filled. Loudness values are written
        verbatim (never computed).
        """
        umid = (self.umid or b"").ljust(64, b"\x00")[:64] if self.version >= 1 else b"\x00" * 64

        if self.version >= 2:
            loudness = (
                self.loudness_value or 0,
                self.loudness_range or 0,
                self.max_true_peak_level or 0,
                self.max_momentary_loudness or 0,
                self.max_short_term_loudness or 0,
            )
        else:
            loudness = (0, 0, 0, 0, 0)

        header = _HEADER.pack(
            _encode_fixed(self.description, 256),
            _encode_fixed(self.originator, 32),
            _encode_fixed(self.originator_reference, 32),
            _encode_fixed(self.origination_date, 10),
            _encode_fixed(self.origination_time, 8),
            self.time_reference & 0xFFFFFFFF,
            (self.time_reference >> 32) & 0xFFFFFFFF,
            self.version,
            umid,
            *loudness,
            b"\x00" * 180,
        )
        return header + self.coding_history.encode("latin-1")

    def write_to_parser(self, parser: WAVParser) -> None:
        """Write this metadata into ``parser`` as the ``bext`` chunk.

        Replaces an existing ``bext`` chunk or appends one. Call
        ``parser.write_wav(...)`` afterwards to persist to disk.
        """
        payload = self.to_chunk_bytes()
        existing = parser.chunks.get(CHUNK_ID)
        if existing:
            existing[0] = WAVChunk(
                id=CHUNK_ID, size=len(payload), data=payload, offset=existing[0].offset
            )
        else:
            parser.add_chunk(CHUNK_ID, payload)
