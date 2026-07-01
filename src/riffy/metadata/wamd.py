"""WAMD metadata: read and write the Wildlife Acoustics ``wamd`` chunk.

WAMD (Wildlife Acoustics Metadata) is the vendor format Song Meter recorders
embed alongside — or, on older firmware, instead of — GUANO. Unlike GUANO's
line-oriented text, WAMD is a packed binary stream of length-prefixed entries::

    uint16 LE  id        # which field (see WAMD_IDS)
    uint32 LE  length    # value length in bytes
    length     value     # the field's raw bytes

Entries sit back-to-back with no inter-entry padding; odd-length values are
followed by an explicit ``0xFFFF`` alignment entry rather than an implicit pad
byte. Most values are UTF-8 text; ``version`` and ``time_expansion`` are 16-bit
integers, and a few (voice notes, program image, run-state) are opaque blobs.

Design highlights (mirroring the GUANO/bext modules):

- **Round-trip safety.** Entries are kept as an ordered ``(id, raw-bytes)`` list,
  so every untouched field — including alignment padding, duplicate ids, and
  blobs riffy does not interpret — re-serializes byte-for-byte. Only the field
  you edit changes.
- **Typed accessors.** Well-known fields are exposed by name; ``loc_position``
  decodes the GPS waypoint to a ``(lat, lon)`` tuple. Everything else stays
  reachable through :meth:`get_raw` / :meth:`set_raw`.
- **Fail soft.** A length that overruns the chunk is clamped with a warning;
  non-UTF-8 text degrades to latin-1 rather than raising.

The ``junk`` variant: older firmware wrote the same binary stream under a
``junk`` chunk id. :meth:`from_parser` treats a ``junk`` chunk as WAMD only when
it carries the unmistakable WAMD signature (a leading 2-byte ``version`` entry
that parses cleanly to the end), so ordinary ``junk`` padding is never mistaken
for metadata.
"""

import struct
import warnings

from ..wav import WAVChunk, WAVParser
from .base import decode_text

#: The Wildlife Acoustics metadata chunk ID.
CHUNK_ID = "wamd"

#: Chunk IDs to probe for the WAMD-in-``junk`` variant emitted by older firmware.
_JUNK_IDS = ("junk", "JUNK")

#: Per-entry header: a little-endian uint16 id followed by a uint32 length.
_ENTRY_HEADER = struct.Struct("<HI")
_HEADER_SIZE = _ENTRY_HEADER.size  # 6

# Well-known WAMD field ids (see Wildlife Acoustics / guano-py `wamd`).
VERSION_ID = 0x00
MODEL_ID = 0x01
SERIAL_ID = 0x02
FIRMWARE_ID = 0x03
PREFIX_ID = 0x04
TIMESTAMP_ID = 0x05
GPSFIRST_ID = 0x06
GPSTRACK_ID = 0x07
SOFTWARE_ID = 0x08
LICENSE_ID = 0x09
NOTES_ID = 0x0A
AUTO_ID_ID = 0x0B
MANUAL_ID_ID = 0x0C
VOICENOTES_ID = 0x0D
AUTO_ID_STATS_ID = 0x0E
TIME_EXPANSION_ID = 0x0F
PROGRAM_ID = 0x10
RUNSTATE_ID = 0x11
MICROPHONE_ID = 0x12
SENSITIVITY_ID = 0x13
#: Reserved id used purely for 16-bit alignment padding.
ALIGNMENT_ID = 0xFFFF

#: Field id -> friendly name.
WAMD_IDS: dict[int, str] = {
    VERSION_ID: "version",
    MODEL_ID: "model",
    SERIAL_ID: "serial",
    FIRMWARE_ID: "firmware",
    PREFIX_ID: "prefix",
    TIMESTAMP_ID: "timestamp",
    GPSFIRST_ID: "gpsfirst",
    GPSTRACK_ID: "gpstrack",
    SOFTWARE_ID: "software",
    LICENSE_ID: "license",
    NOTES_ID: "notes",
    AUTO_ID_ID: "auto_id",
    MANUAL_ID_ID: "manual_id",
    VOICENOTES_ID: "voicenotes",
    AUTO_ID_STATS_ID: "auto_id_stats",
    TIME_EXPANSION_ID: "time_expansion",
    PROGRAM_ID: "program",
    RUNSTATE_ID: "runstate",
    MICROPHONE_ID: "microphone",
    SENSITIVITY_ID: "sensitivity",
}

#: Name -> field id (for CLI/lookups).
WAMD_NAMES: dict[str, int] = {name: tag for tag, name in WAMD_IDS.items()}

#: Ids whose value is opaque binary that riffy preserves but does not decode.
_BLOB_IDS = frozenset({VOICENOTES_ID, AUTO_ID_STATS_ID, PROGRAM_ID, RUNSTATE_ID})

#: Ids whose value is a little-endian uint16 rather than text.
_UINT16_IDS = frozenset({VERSION_ID, TIME_EXPANSION_ID})

#: Ids carrying human text values that ``riffy set --wamd KEY=VAL`` may edit.
SETTABLE_TEXT_IDS = frozenset(
    {
        MODEL_ID,
        SERIAL_ID,
        FIRMWARE_ID,
        PREFIX_ID,
        TIMESTAMP_ID,
        GPSFIRST_ID,
        GPSTRACK_ID,
        SOFTWARE_ID,
        LICENSE_ID,
        NOTES_ID,
        AUTO_ID_ID,
        MANUAL_ID_ID,
        MICROPHONE_ID,
        SENSITIVITY_ID,
    }
)


class WamdMetadata:
    """Typed, round-trip-safe view of a ``wamd`` chunk's WAMD metadata.

    Construct from a file via :meth:`from_parser` / :meth:`from_bytes`, or build a
    fresh one with ``WamdMetadata()``. Well-known fields are exposed as
    attributes; every entry, known or not, is reachable via :meth:`get_raw` /
    :meth:`set_raw` and :attr:`entries`.
    """

    def __init__(self, chunk_id: str = CHUNK_ID) -> None:
        # Ordered (id, raw-value-bytes). A list — not a dict — because WAMD uses
        # repeated 0xFFFF alignment entries, and only a list preserves them (and
        # any other duplicate id) for a byte-exact round trip.
        self._entries: list[tuple[int, bytes]] = []
        #: The chunk id this metadata was read from (``"wamd"`` or a ``junk``
        #: variant); writes go back to the same chunk.
        self._chunk_id = chunk_id

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    @classmethod
    def from_bytes(cls, data: bytes, chunk_id: str = CHUNK_ID) -> "WamdMetadata":
        """Parse WAMD metadata from a raw chunk payload.

        A length field that overruns the buffer is clamped (with a warning) so a
        truncated or malformed chunk degrades rather than raising.
        """
        self = cls(chunk_id=chunk_id)
        offset = 0
        n = len(data)
        while offset + _HEADER_SIZE <= n:
            tag, length = _ENTRY_HEADER.unpack_from(data, offset)
            start = offset + _HEADER_SIZE
            if start + length > n:
                warnings.warn(
                    f"wamd: entry 0x{tag:04x} claims {length} bytes but only "
                    f"{n - start} remain; truncating",
                    stacklevel=2,
                )
                length = n - start
            self._entries.append((tag, data[start : start + length]))
            offset = start + length
        return self

    @classmethod
    def from_parser(cls, parser: WAVParser) -> "WamdMetadata | None":
        """Parse WAMD metadata from a parser's ``wamd`` (or ``junk``) chunk.

        Prefers a real ``wamd`` chunk; failing that, a ``junk`` chunk is used
        only when it carries the WAMD signature. Returns ``None`` if neither is
        present.
        """
        data = parser.get_chunk_bytes(CHUNK_ID)
        if data is not None:
            return cls.from_bytes(data, chunk_id=CHUNK_ID)
        for junk_id in _JUNK_IDS:
            for chunk in parser.get_chunks(junk_id):
                if _looks_like_wamd(chunk.data):
                    return cls.from_bytes(chunk.data, chunk_id=junk_id)
        return None

    # ------------------------------------------------------------------ #
    # Generic entry access — preserves unknown/blob/padding entries
    # ------------------------------------------------------------------ #

    def get_raw(self, tag: int) -> bytes | None:
        """Return the raw value bytes for the first entry with ``tag``, or ``None``."""
        for entry_tag, value in self._entries:
            if entry_tag == tag:
                return value
        return None

    def set_raw(self, tag: int, value: bytes) -> None:
        """Set the raw value for ``tag``, replacing the first entry in place or appending."""
        for i, (entry_tag, _) in enumerate(self._entries):
            if entry_tag == tag:
                self._entries[i] = (tag, value)
                return
        self._entries.append((tag, value))

    def remove(self, tag: int) -> None:
        """Delete every entry with ``tag`` (no error if absent)."""
        self._entries = [entry for entry in self._entries if entry[0] != tag]

    def __contains__(self, tag: object) -> bool:
        return any(entry_tag == tag for entry_tag, _ in self._entries)

    @property
    def entries(self) -> list[tuple[int, bytes]]:
        """A copy of the full ordered ``(id, raw-bytes)`` entry list."""
        return list(self._entries)

    # ------------------------------------------------------------------ #
    # Text helpers
    # ------------------------------------------------------------------ #

    def get_text(self, tag: int) -> str | None:
        """Return the UTF-8 (fail-soft latin-1) decoded value for ``tag``, or ``None``."""
        value = self.get_raw(tag)
        if value is None:
            return None
        return decode_text(value, context="wamd")

    def set_text(self, tag: int, value: str) -> None:
        """Set ``tag`` to the UTF-8 encoding of ``value``."""
        self.set_raw(tag, value.encode("utf-8"))

    # ------------------------------------------------------------------ #
    # Well-known typed attributes
    # ------------------------------------------------------------------ #

    @property
    def version(self) -> int | None:
        """The WAMD format version (a 16-bit integer), or ``None`` if absent."""
        return self._get_uint16(VERSION_ID)

    @property
    def model(self) -> str | None:
        return self.get_text(MODEL_ID)

    @model.setter
    def model(self, value: str | None) -> None:
        self._set_or_remove_text(MODEL_ID, value)

    @property
    def serial(self) -> str | None:
        return self.get_text(SERIAL_ID)

    @serial.setter
    def serial(self, value: str | None) -> None:
        self._set_or_remove_text(SERIAL_ID, value)

    @property
    def firmware(self) -> str | None:
        return self.get_text(FIRMWARE_ID)

    @firmware.setter
    def firmware(self, value: str | None) -> None:
        self._set_or_remove_text(FIRMWARE_ID, value)

    @property
    def prefix(self) -> str | None:
        return self.get_text(PREFIX_ID)

    @prefix.setter
    def prefix(self, value: str | None) -> None:
        self._set_or_remove_text(PREFIX_ID, value)

    @property
    def timestamp(self) -> str | None:
        """The recording timestamp as the recorder wrote it (raw text)."""
        return self.get_text(TIMESTAMP_ID)

    @timestamp.setter
    def timestamp(self, value: str | None) -> None:
        self._set_or_remove_text(TIMESTAMP_ID, value)

    @property
    def notes(self) -> str | None:
        return self.get_text(NOTES_ID)

    @notes.setter
    def notes(self, value: str | None) -> None:
        self._set_or_remove_text(NOTES_ID, value)

    @property
    def time_expansion(self) -> int | None:
        """The time-expansion factor (a 16-bit integer), or ``None`` if absent."""
        return self._get_uint16(TIME_EXPANSION_ID)

    @property
    def loc_position(self) -> tuple[float, float] | None:
        """``(latitude, longitude)`` WGS84 tuple decoded from the GPS waypoint.

        Handles both Wildlife Acoustics dialects: the Song Meter
        ``datum, lat, N|S, lon, E|W`` form and the EMTouch signed
        ``datum, lat, lon`` form. Altitude, if present, is preserved on write
        but not surfaced here.
        """
        raw = self.get_text(GPSFIRST_ID)
        if raw is None:
            return None
        parsed = _parse_gps(raw)
        if parsed is None:
            return None
        return parsed[1], parsed[2]

    @loc_position.setter
    def loc_position(self, value: tuple[float, float] | None) -> None:
        if value is None:
            self.remove(GPSFIRST_ID)
            return
        lat, lon = value
        # Preserve the datum and altitude of any existing waypoint; only the
        # coordinates change. Emit the canonical EMTouch signed form.
        datum, altitude = "WGS84", None
        existing = self.get_text(GPSFIRST_ID)
        if existing is not None:
            parsed = _parse_gps(existing)
            if parsed is not None:
                datum, altitude = parsed[0], parsed[3]
        waypoint = f"{datum},{lat},{lon}"
        if altitude is not None:
            waypoint += f",{altitude}"
        self.set_text(GPSFIRST_ID, waypoint)

    # ------------------------------------------------------------------ #
    # Internal typed helpers
    # ------------------------------------------------------------------ #

    def _get_uint16(self, tag: int) -> int | None:
        value = self.get_raw(tag)
        if value is None:
            return None
        if len(value) != 2:
            warnings.warn(
                f"wamd: entry 0x{tag:04x} is not a 2-byte integer: {value!r}", stacklevel=2
            )
            return None
        return struct.unpack("<H", value)[0]

    def _set_or_remove_text(self, tag: int, value: str | None) -> None:
        if value is None:
            self.remove(tag)
        else:
            self.set_text(tag, value)

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #

    def to_chunk_bytes(self) -> bytes:
        """Serialize to a ``wamd`` chunk payload (entries back-to-back, no padding).

        The chunk-level even-byte padding is left to the writer, matching ``bext``
        and ``guan``; the pad byte lives outside the declared chunk size, so a
        re-read never mistakes it for a truncated entry.
        """
        out = bytearray()
        for tag, value in self._entries:
            out += _ENTRY_HEADER.pack(tag, len(value))
            out += value
        return bytes(out)

    def write_to_parser(self, parser: WAVParser) -> None:
        """Write this metadata back into ``parser`` under its source chunk id.

        Replaces the chunk it was read from (the ``wamd`` chunk, or the specific
        WAMD-bearing ``junk`` chunk) or appends a new ``wamd`` chunk. Call
        ``parser.write_wav(...)`` afterwards to persist to disk.
        """
        payload = self.to_chunk_bytes()
        occurrences = parser.chunks.get(self._chunk_id, [])
        target: int | None = 0
        if self._chunk_id != CHUNK_ID:
            # A junk variant: replace the specific occurrence that holds WAMD.
            target = next(
                (i for i, c in enumerate(occurrences) if _looks_like_wamd(c.data)),
                None,
            )
        if occurrences and target is not None:
            existing = occurrences[target]
            occurrences[target] = WAVChunk(
                id=self._chunk_id, size=len(payload), data=payload, offset=existing.offset
            )
        else:
            parser.add_chunk(self._chunk_id, payload)

    # ------------------------------------------------------------------ #
    # Inspection
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe view: named fields decoded, blobs/unknowns as hex.

        Alignment padding is omitted. ``loc_position`` is added as a ``[lat, lon]``
        pair when the GPS waypoint parses.
        """
        out: dict[str, object] = {}
        for tag, value in self._entries:
            if tag == ALIGNMENT_ID:
                continue
            name = WAMD_IDS.get(tag, f"0x{tag:04x}")
            if tag in _UINT16_IDS and len(value) == 2:
                out[name] = struct.unpack("<H", value)[0]
            elif tag in _BLOB_IDS:
                out[name] = value.hex()
            else:
                out[name] = decode_text(value, context="wamd")
        position = self.loc_position
        if position is not None:
            out["loc_position"] = [position[0], position[1]]
        return out


# ---------------------------------------------------------------------- #
# Module-level helpers
# ---------------------------------------------------------------------- #


def _looks_like_wamd(data: bytes) -> bool:
    """Return True if ``data`` is a WAMD entry stream (a strict, low-false-positive check).

    Requires the unmistakable signature — a leading 2-byte ``version`` entry —
    and that every entry parses cleanly with the stream consumed exactly. This
    keeps ordinary ``junk`` padding (e.g. all zeros) from being read as metadata.
    """
    if len(data) < _HEADER_SIZE:
        return False
    tag, length = _ENTRY_HEADER.unpack_from(data, 0)
    if tag != VERSION_ID or length != 2:
        return False
    offset = 0
    n = len(data)
    while offset + _HEADER_SIZE <= n:
        entry_length = _ENTRY_HEADER.unpack_from(data, offset)[1]
        offset += _HEADER_SIZE + entry_length
    return offset == n


def _parse_gps(waypoint: str) -> tuple[str, float, float, str | None] | None:
    """Parse a WAMD GPS waypoint into ``(datum, lat, lon, altitude)``.

    Accepts the Song Meter ``datum, lat, N|S, lon, E|W [, alt]`` form and the
    EMTouch signed ``datum, lat, lon [, alt]`` form. ``altitude`` is returned as
    the raw string (or ``None``) so it re-emits verbatim. Returns ``None`` if the
    value does not parse.
    """
    parts = [part.strip() for part in waypoint.split(",")]
    if len(parts) < 3:
        return None
    datum, rest = parts[0], parts[1:]
    try:
        if len(rest) >= 4 and rest[1] in ("N", "S") and rest[3] in ("E", "W"):
            lat = float(rest[0])
            if rest[1] == "S":
                lat = -lat
            lon = float(rest[2])
            if rest[3] == "W":
                lon = -lon
            altitude = rest[4] if len(rest) > 4 else None
        else:
            lat = float(rest[0])
            lon = float(rest[1])
            altitude = rest[2] if len(rest) > 2 else None
    except ValueError:
        warnings.warn(f"wamd: GPS waypoint is not parseable: {waypoint!r}", stacklevel=2)
        return None
    return datum, lat, lon, altitude
