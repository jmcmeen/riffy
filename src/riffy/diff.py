"""Compare two WAV files for verification and validation.

``riffy.diff(a, b)`` reports the differences between two files at two levels:

- **Chunks** — which RIFF chunks were added, removed, or changed (by raw bytes),
  or left unchanged. Multi-occurrence IDs are compared occurrence by occurrence.
- **Metadata fields** — a decoded, per-standard diff (GUANO, RIFF INFO, Broadcast
  Wave ``bext``) so you can confirm exactly which fields changed — e.g. that a
  batch edit touched only ``Loc Position`` and left everything else intact.

Both files are read fully into memory (as the parser already does), so diffing a
pair of very large recordings uses memory for both at once.
"""

from dataclasses import dataclass, field
from pathlib import Path

from .metadata.bext import BextMetadata
from .metadata.guano import GuanoMetadata
from .metadata.info import InfoMetadata
from .wav import WAVParser

#: Difference statuses. ``unchanged`` is only emitted for chunks (and only when
#: requested); field deltas are always one of added/removed/changed.
ADDED = "added"
REMOVED = "removed"
CHANGED = "changed"
UNCHANGED = "unchanged"


@dataclass
class ChunkDelta:
    """One chunk occurrence's difference between file A and file B."""

    chunk_id: str
    index: int  # occurrence index within this chunk ID (0 for the common case)
    status: str  # added | removed | changed | unchanged
    size_a: int | None  # None when absent from A
    size_b: int | None  # None when absent from B


@dataclass
class FieldDelta:
    """One decoded metadata field's difference between file A and file B."""

    standard: str  # "guano" | "info" | "bext"
    key: str
    status: str  # added | removed | changed
    old: str | None  # value in A (None when absent)
    new: str | None  # value in B (None when absent)


@dataclass
class WavDiff:
    """The structured difference between two WAV files."""

    path_a: str
    path_b: str
    form_a: str  # RIFF | RF64 | BW64
    form_b: str
    chunks: list[ChunkDelta] = field(default_factory=list)
    fields: list[FieldDelta] = field(default_factory=list)

    @property
    def changed_chunks(self) -> list[ChunkDelta]:
        """Chunk deltas that are not ``unchanged``."""
        return [c for c in self.chunks if c.status != UNCHANGED]

    @property
    def identical(self) -> bool:
        """True when the two files have the same form and no chunk differs."""
        return self.form_a == self.form_b and not self.changed_chunks


def diff(
    a: "str | Path | WAVParser",
    b: "str | Path | WAVParser",
    *,
    include_unchanged: bool = False,
) -> WavDiff:
    """Compare two WAV files (paths or parsers) and return a :class:`WavDiff`.

    Args:
        a: The first file — a path or an already-parsed :class:`~riffy.WAVParser`.
        b: The second file.
        include_unchanged: If True, include ``unchanged`` chunk deltas too
            (default: only report chunks that differ).
    """
    pa = a if isinstance(a, WAVParser) else WAVParser(a)
    pb = b if isinstance(b, WAVParser) else WAVParser(b)
    return WavDiff(
        path_a=str(pa.file_path),
        path_b=str(pb.file_path),
        form_a=pa.riff_form,
        form_b=pb.riff_form,
        chunks=_diff_chunks(pa, pb, include_unchanged),
        fields=_diff_metadata(pa, pb),
    )


def _diff_chunks(a: WAVParser, b: WAVParser, include_unchanged: bool) -> list[ChunkDelta]:
    deltas: list[ChunkDelta] = []
    for chunk_id in sorted(set(a.chunks) | set(b.chunks)):
        list_a = a.get_chunks(chunk_id)
        list_b = b.get_chunks(chunk_id)
        for index in range(max(len(list_a), len(list_b))):
            ca = list_a[index] if index < len(list_a) else None
            cb = list_b[index] if index < len(list_b) else None
            if ca is not None and cb is not None:
                status = UNCHANGED if ca.data == cb.data else CHANGED
            elif cb is not None:
                status = ADDED
            else:
                status = REMOVED
            if status == UNCHANGED and not include_unchanged:
                continue
            deltas.append(
                ChunkDelta(
                    chunk_id=chunk_id,
                    index=index,
                    status=status,
                    size_a=ca.size if ca is not None else None,
                    size_b=cb.size if cb is not None else None,
                )
            )
    return deltas


def _diff_metadata(a: WAVParser, b: WAVParser) -> list[FieldDelta]:
    deltas: list[FieldDelta] = []
    deltas += _field_deltas(
        "guano", _guano_map(GuanoMetadata.from_parser(a)), _guano_map(GuanoMetadata.from_parser(b))
    )
    deltas += _field_deltas(
        "info", _info_map(InfoMetadata.from_parser(a)), _info_map(InfoMetadata.from_parser(b))
    )
    deltas += _field_deltas(
        "bext", _bext_map(BextMetadata.from_parser(a)), _bext_map(BextMetadata.from_parser(b))
    )
    return deltas


def _field_deltas(standard: str, old: dict[str, str], new: dict[str, str]) -> list[FieldDelta]:
    deltas = []
    for key in sorted(set(old) | set(new)):
        old_value = old.get(key)
        new_value = new.get(key)
        if old_value == new_value:
            continue
        if old_value is None:
            status = ADDED
        elif new_value is None:
            status = REMOVED
        else:
            status = CHANGED
        deltas.append(FieldDelta(standard, key, status, old_value, new_value))
    return deltas


def _guano_map(guano: GuanoMetadata | None) -> dict[str, str]:
    if guano is None:
        return {}
    return {(f"{ns}|{key}" if ns else key): value for (ns, key), value in guano.fields.items()}


def _info_map(info: InfoMetadata | None) -> dict[str, str]:
    return {} if info is None else dict(info.tags)


def _bext_map(bext: BextMetadata | None) -> dict[str, str]:
    if bext is None:
        return {}
    result: dict[str, str] = {}
    for name in (
        "description",
        "originator",
        "originator_reference",
        "origination_date",
        "origination_time",
        "time_reference",
        "version",
        "loudness_value",
        "loudness_range",
        "max_true_peak_level",
        "max_momentary_loudness",
        "max_short_term_loudness",
        "coding_history",
    ):
        value = getattr(bext, name)
        if value is not None:
            result[name] = str(value)
    if bext.umid is not None:
        result["umid"] = bext.umid.hex()
    return result
