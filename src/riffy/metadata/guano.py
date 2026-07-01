"""GUANO metadata: read and write the ``guan`` chunk.

GUANO (Grand Unified Acoustic Notation Ontology) is the closest thing the
bioacoustics field has to a vendor-neutral metadata standard. It is embedded in
a WAV sub-chunk with ID ``guan`` holding UTF-8 text, one ``[Namespace|]Key:
Value`` field per line, with ``GUANO|Version`` required as the first field.

Design highlights (see the v0.3.0 plan §5.1):

- **Attribute-first.** Well-known fields are exposed as typed attributes
  (``timestamp`` is a ``datetime`` with its offset preserved, ``loc_position``
  is a ``(lat, lon)`` tuple, ``species_manual_id`` is a list, ...). Vendor and
  arbitrary fields remain reachable through :meth:`~GuanoMetadata.get` /
  :meth:`~GuanoMetadata.set` / :attr:`~GuanoMetadata.fields`.
- **Round-trip safety.** Unknown fields and vendor namespaces are preserved
  verbatim and in order — a hard requirement of the GUANO spec, not a nicety.
- **Fail soft.** Non-UTF-8 payloads fall back to latin-1 with a warning; a
  single malformed line is skipped with a warning rather than abandoning the
  whole chunk.
"""

import base64
import warnings
from collections.abc import Iterable, Iterator
from datetime import datetime

from ..wav import WAVParser
from .base import decode_text, pad_to_even

#: The GUANO sub-chunk ID.
CHUNK_ID = "guan"

#: The namespace GUANO uses for its own ``Version`` field. Every other
#: well-known field lives in the empty (base) namespace.
GUANO_NAMESPACE = "GUANO"

#: Field key type: ``(namespace, key)``. The base namespace is the empty string.
FieldKey = tuple[str, str]


class GuanoMetadata:
    """Typed, round-trip-safe view of a ``guan`` chunk's GUANO metadata.

    Construct from an existing file via :meth:`from_parser` / :meth:`from_bytes`,
    or build a fresh one with ``GuanoMetadata(version="1.0")``. Well-known fields
    are typed attributes; everything else is reachable via :meth:`get` /
    :meth:`set` and :attr:`fields`.
    """

    def __init__(self, version: str | None = None) -> None:
        # Ordered mapping preserves file order for round-trip fidelity. Python
        # dicts preserve insertion order, which is exactly what we need.
        self._fields: dict[FieldKey, str] = {}
        if version is not None:
            self.version = version

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    @classmethod
    def from_bytes(cls, data: bytes) -> "GuanoMetadata":
        """Parse GUANO metadata from a raw ``guan`` chunk payload.

        Args:
            data: The raw bytes of the ``guan`` chunk.

        Returns:
            A populated :class:`GuanoMetadata`.
        """
        self = cls()
        text = decode_text(data, context="guan")
        for raw_line in text.split("\n"):
            line = raw_line.strip()
            if not line:
                continue  # empty lines (and whitespace padding) are ignored
            if ":" not in line:
                warnings.warn(
                    f"guan: skipping malformed line without ':' separator: {line!r}",
                    stacklevel=2,
                )
                continue
            name_part, value_part = line.split(":", 1)
            namespace, key = _split_namespace(name_part)
            key = key.strip()
            if not key:
                warnings.warn(
                    f"guan: skipping line with empty key: {line!r}",
                    stacklevel=2,
                )
                continue
            # Values are stored unescaped (real newlines); re-escaped on write.
            value = _unescape(value_part.strip())
            self._fields[(namespace, key)] = value
        return self

    @classmethod
    def from_parser(cls, parser: WAVParser) -> "GuanoMetadata | None":
        """Parse GUANO metadata from a parser's ``guan`` chunk.

        Args:
            parser: A parsed :class:`~riffy.WAVParser`.

        Returns:
            A :class:`GuanoMetadata`, or ``None`` if the file has no ``guan``
            chunk.
        """
        data = parser.get_chunk_bytes(CHUNK_ID)
        if data is None:
            return None
        return cls.from_bytes(data)

    # ------------------------------------------------------------------ #
    # Generic (namespace, key) access — preserves unknown/vendor fields
    # ------------------------------------------------------------------ #

    def get(self, namespace: str, key: str, default: str | None = None) -> str | None:
        """Return the raw string value for ``(namespace, key)``, or ``default``.

        Use the empty string for the base (un-prefixed) namespace.
        """
        return self._fields.get((namespace, key), default)

    def set(self, namespace: str, key: str, value: str) -> None:
        """Set the raw string value for ``(namespace, key)``.

        Newlines in ``value`` are allowed and re-escaped on write.
        """
        self._fields[(namespace, key)] = value

    def remove(self, namespace: str, key: str) -> None:
        """Delete ``(namespace, key)`` if present (no error if absent)."""
        self._fields.pop((namespace, key), None)

    def __contains__(self, key: object) -> bool:
        return key in self._fields

    def __iter__(self) -> Iterator[FieldKey]:
        return iter(self._fields)

    @property
    def fields(self) -> dict[FieldKey, str]:
        """A copy of the full ``(namespace, key) -> raw string`` mapping."""
        return dict(self._fields)

    def get_binary(self, namespace: str, key: str) -> bytes | None:
        """Return a Base64-decoded (RFC 4648) value, or ``None`` if absent."""
        raw = self._fields.get((namespace, key))
        if raw is None:
            return None
        return base64.b64decode(raw)

    def set_binary(self, namespace: str, key: str, value: bytes) -> None:
        """Store ``value`` as a Base64-encoded (RFC 4648) string."""
        self._fields[(namespace, key)] = base64.b64encode(value).decode("ascii")

    # ------------------------------------------------------------------ #
    # Typed string helpers
    # ------------------------------------------------------------------ #

    def _get_str(self, key: str) -> str | None:
        return self._fields.get(("", key))

    def _set_str(self, key: str, value: str | None) -> None:
        if value is None:
            self._fields.pop(("", key), None)
        else:
            self._fields[("", key)] = value

    def _get_float(self, key: str) -> float | None:
        raw = self._fields.get(("", key))
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            warnings.warn(f"guan: {key!r} is not a valid float: {raw!r}", stacklevel=2)
            return None

    def _set_float(self, key: str, value: float | None) -> None:
        if value is None:
            self._fields.pop(("", key), None)
        else:
            self._fields[("", key)] = repr(value)

    def _get_int(self, key: str) -> int | None:
        raw = self._fields.get(("", key))
        if raw is None:
            return None
        try:
            return int(raw)
        except ValueError:
            warnings.warn(f"guan: {key!r} is not a valid int: {raw!r}", stacklevel=2)
            return None

    def _set_int(self, key: str, value: int | None) -> None:
        if value is None:
            self._fields.pop(("", key), None)
        else:
            self._fields[("", key)] = str(value)

    def _get_list(self, key: str) -> list[str]:
        raw = self._fields.get(("", key))
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]

    def _set_list(self, key: str, value: Iterable[str] | None) -> None:
        if value is None:
            self._fields.pop(("", key), None)
        else:
            self._fields[("", key)] = ", ".join(value)

    # ------------------------------------------------------------------ #
    # Well-known typed attributes
    # ------------------------------------------------------------------ #

    @property
    def version(self) -> str | None:
        """``GUANO|Version`` — the format version (required on write)."""
        return self._fields.get((GUANO_NAMESPACE, "Version"))

    @version.setter
    def version(self, value: str | None) -> None:
        if value is None:
            self._fields.pop((GUANO_NAMESPACE, "Version"), None)
        else:
            self._fields[(GUANO_NAMESPACE, "Version")] = value

    @property
    def make(self) -> str | None:
        return self._get_str("Make")

    @make.setter
    def make(self, value: str | None) -> None:
        self._set_str("Make", value)

    @property
    def model(self) -> str | None:
        return self._get_str("Model")

    @model.setter
    def model(self, value: str | None) -> None:
        self._set_str("Model", value)

    @property
    def serial(self) -> str | None:
        return self._get_str("Serial")

    @serial.setter
    def serial(self, value: str | None) -> None:
        self._set_str("Serial", value)

    @property
    def firmware_version(self) -> str | None:
        return self._get_str("Firmware Version")

    @firmware_version.setter
    def firmware_version(self, value: str | None) -> None:
        self._set_str("Firmware Version", value)

    @property
    def hardware_version(self) -> str | None:
        return self._get_str("Hardware Version")

    @hardware_version.setter
    def hardware_version(self, value: str | None) -> None:
        self._set_str("Hardware Version", value)

    @property
    def original_filename(self) -> str | None:
        return self._get_str("Original Filename")

    @original_filename.setter
    def original_filename(self, value: str | None) -> None:
        self._set_str("Original Filename", value)

    @property
    def note(self) -> str | None:
        """``Note`` — free text, may contain newlines."""
        return self._get_str("Note")

    @note.setter
    def note(self, value: str | None) -> None:
        self._set_str("Note", value)

    @property
    def length(self) -> float | None:
        return self._get_float("Length")

    @length.setter
    def length(self, value: float | None) -> None:
        self._set_float("Length", value)

    @property
    def filter_hp(self) -> float | None:
        return self._get_float("Filter HP")

    @filter_hp.setter
    def filter_hp(self, value: float | None) -> None:
        self._set_float("Filter HP", value)

    @property
    def filter_lp(self) -> float | None:
        return self._get_float("Filter LP")

    @filter_lp.setter
    def filter_lp(self, value: float | None) -> None:
        self._set_float("Filter LP", value)

    @property
    def humidity(self) -> float | None:
        return self._get_float("Humidity")

    @humidity.setter
    def humidity(self, value: float | None) -> None:
        self._set_float("Humidity", value)

    @property
    def temperature_int(self) -> float | None:
        return self._get_float("Temperature Int")

    @temperature_int.setter
    def temperature_int(self, value: float | None) -> None:
        self._set_float("Temperature Int", value)

    @property
    def temperature_ext(self) -> float | None:
        return self._get_float("Temperature Ext")

    @temperature_ext.setter
    def temperature_ext(self, value: float | None) -> None:
        self._set_float("Temperature Ext", value)

    @property
    def loc_accuracy(self) -> float | None:
        return self._get_float("Loc Accuracy")

    @loc_accuracy.setter
    def loc_accuracy(self, value: float | None) -> None:
        self._set_float("Loc Accuracy", value)

    @property
    def loc_elevation(self) -> float | None:
        return self._get_float("Loc Elevation")

    @loc_elevation.setter
    def loc_elevation(self, value: float | None) -> None:
        self._set_float("Loc Elevation", value)

    @property
    def samplerate(self) -> int | None:
        return self._get_int("Samplerate")

    @samplerate.setter
    def samplerate(self, value: int | None) -> None:
        self._set_int("Samplerate", value)

    @property
    def te(self) -> int:
        """``TE`` — time-expansion factor (defaults to 1 when absent)."""
        value = self._get_int("TE")
        return 1 if value is None else value

    @te.setter
    def te(self, value: int | None) -> None:
        self._set_int("TE", value)

    @property
    def species_auto_id(self) -> list[str]:
        return self._get_list("Species Auto ID")

    @species_auto_id.setter
    def species_auto_id(self, value: Iterable[str] | None) -> None:
        self._set_list("Species Auto ID", value)

    @property
    def species_manual_id(self) -> list[str]:
        return self._get_list("Species Manual ID")

    @species_manual_id.setter
    def species_manual_id(self, value: Iterable[str] | None) -> None:
        self._set_list("Species Manual ID", value)

    @property
    def tags(self) -> list[str]:
        return self._get_list("Tags")

    @tags.setter
    def tags(self, value: Iterable[str] | None) -> None:
        self._set_list("Tags", value)

    @property
    def timestamp(self) -> datetime | None:
        """``Timestamp`` — parsed ISO 8601 / RFC 3339, offset preserved."""
        raw = self._fields.get(("", "Timestamp"))
        if raw is None:
            return None
        return _parse_timestamp(raw)

    @timestamp.setter
    def timestamp(self, value: datetime | str | None) -> None:
        if value is None:
            self._fields.pop(("", "Timestamp"), None)
        elif isinstance(value, datetime):
            self._fields[("", "Timestamp")] = value.isoformat()
        else:
            self._fields[("", "Timestamp")] = value

    @property
    def loc_position(self) -> tuple[float, float] | None:
        """``Loc Position`` — ``(latitude, longitude)`` WGS84 float tuple."""
        raw = self._fields.get(("", "Loc Position"))
        if raw is None:
            return None
        parts = raw.split()
        if len(parts) != 2:
            warnings.warn(f"guan: 'Loc Position' is not 'lat lon': {raw!r}", stacklevel=2)
            return None
        try:
            return (float(parts[0]), float(parts[1]))
        except ValueError:
            warnings.warn(f"guan: 'Loc Position' has non-numeric parts: {raw!r}", stacklevel=2)
            return None

    @loc_position.setter
    def loc_position(self, value: tuple[float, float] | None) -> None:
        if value is None:
            self._fields.pop(("", "Loc Position"), None)
        else:
            lat, lon = value
            self._fields[("", "Loc Position")] = f"{lat} {lon}"

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #

    def to_chunk_bytes(self) -> bytes:
        """Serialize to a ``guan`` chunk payload (UTF-8, Version-first, even).

        Raises:
            ValueError: If ``GUANO|Version`` has not been set. The spec requires
                it as the mandatory first field.
        """
        version_key = (GUANO_NAMESPACE, "Version")
        if version_key not in self._fields:
            raise ValueError("GUANO requires 'GUANO|Version'; set .version before serializing")

        # GUANO|Version must come first; everything else keeps insertion order.
        ordered: list[FieldKey] = [version_key]
        ordered += [key for key in self._fields if key != version_key]

        lines = []
        for namespace, key in ordered:
            prefix = f"{namespace}|{key}" if namespace else key
            lines.append(f"{prefix}: {_escape(self._fields[(namespace, key)])}")

        encoded = "\n".join(lines).encode("utf-8")
        # Even-byte padding with a space, per the GUANO whitespace convention;
        # the trailing space is stripped on read.
        return pad_to_even(encoded, pad_byte=0x20)

    def write_to_parser(self, parser: WAVParser) -> None:
        """Write this metadata into ``parser`` as the ``guan`` chunk.

        Replaces any existing ``guan`` chunk. Call ``parser.write_wav(...)``
        afterwards to persist to disk.
        """
        parser.set_chunk(CHUNK_ID, self.to_chunk_bytes())


# ---------------------------------------------------------------------- #
# Module-level parsing helpers
# ---------------------------------------------------------------------- #


def _split_namespace(name_part: str) -> FieldKey:
    """Split a field name into ``(namespace, key)`` on the first ``|``."""
    if "|" in name_part:
        namespace, key = name_part.split("|", 1)
        return (namespace.strip(), key)
    return ("", name_part)


def _unescape(value: str) -> str:
    r"""Expand the 2-character ``\n`` sequence into a real newline."""
    return value.replace("\\n", "\n")


def _escape(value: str) -> str:
    r"""Re-escape real newlines as the 2-character ``\n`` sequence."""
    return value.replace("\n", "\\n")


def _parse_timestamp(value: str) -> datetime | None:
    """Parse an ISO 8601 / RFC 3339 timestamp, preserving any UTC offset."""
    text = value.strip()
    if not text:
        return None
    # Normalize a trailing 'Z' (Zulu/UTC) to +00:00 so datetime.fromisoformat
    # accepts it on Python 3.10 (native 'Z' support only landed in 3.11).
    if text[-1] in ("Z", "z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        warnings.warn(f"guan: 'Timestamp' is not a valid ISO 8601 value: {value!r}", stacklevel=2)
        return None
