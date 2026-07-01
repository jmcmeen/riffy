"""Unified metadata view: surface whichever standards a file contains.

:class:`RecordingMetadata` inspects a WAV file and exposes each recorder-metadata
standard it finds (GUANO, RIFF INFO, Broadcast Wave ``bext``, AudioMoth) side by
side, each kept close to its own raw parsed form.

Deliberately, this view does **not** perform cross-standard reconciliation: it
does not pick a "best-available" timestamp, location, or device by precedence
across standards. That merging is policy, and it belongs downstream (in bioamla),
which can decide precedence for its own workflows. Keeping riffy close to the raw
standards keeps its behavior predictable and avoids baking one consumer's
opinions into the library.

(The AudioMoth view is a decoded read of the same INFO block that ``info``
exposes raw, so a file may legitimately report both ``info`` and ``audiomoth`` —
that is within-standard convenience, not cross-standard merging.)
"""

from dataclasses import asdict, dataclass
from pathlib import Path

from ..wav import WAVParser
from .audiomoth import AudioMothMetadata
from .bext import BextMetadata
from .guano import GuanoMetadata
from .info import InfoMetadata
from .ixml import IXmlMetadata


@dataclass
class RecordingMetadata:
    """The recorder-metadata standards found in one WAV file, side by side.

    Each attribute is the parsed view for that standard, or ``None`` if the file
    does not contain it.
    """

    guano: GuanoMetadata | None = None
    info: InfoMetadata | None = None
    bext: BextMetadata | None = None
    audiomoth: AudioMothMetadata | None = None

    @classmethod
    def from_parser(cls, parser: WAVParser) -> "RecordingMetadata":
        """Detect and parse every supported standard from a parsed WAV file."""
        return cls(
            guano=GuanoMetadata.from_parser(parser),
            info=InfoMetadata.from_parser(parser),
            bext=BextMetadata.from_parser(parser),
            audiomoth=AudioMothMetadata.from_parser(parser),
        )

    @property
    def sources(self) -> tuple[str, ...]:
        """The names of the standards present, in a stable order."""
        present = []
        if self.guano is not None:
            present.append("guano")
        if self.info is not None:
            present.append("info")
        if self.bext is not None:
            present.append("bext")
        if self.audiomoth is not None:
            present.append("audiomoth")
        return tuple(present)


def read_metadata(path: str | Path) -> RecordingMetadata:
    """Parse a WAV file and return the recorder metadata it contains.

    Args:
        path: Path to a WAV file.

    Returns:
        A :class:`RecordingMetadata` exposing each detected standard.

    Example:
        >>> meta = read_metadata("recording.wav")
        >>> meta.sources
        ('guano',)
        >>> meta.guano.make
        'Wildlife Acoustics, Inc.'
    """
    return RecordingMetadata.from_parser(WAVParser(path))


def dump_metadata(path: str | Path) -> dict:
    """Parse a WAV file and return its recorder metadata as a plain, JSON-serializable dict.

    A convenience for inspection and tooling (it backs ``python -m riffy``). The
    returned dict has ``file``, ``riff_form``, ``format``, ``sources``, and one
    entry per standard (``guano``, ``info``, ``bext``, ``audiomoth``, ``ixml``),
    each ``None`` when absent. All values are JSON-safe: datetimes become ISO
    strings and binary fields (e.g. bext ``umid``) become hex strings.

    Args:
        path: Path to a WAV file.

    Returns:
        A JSON-serializable dict describing the file's metadata.
    """
    parser = WAVParser(path)
    meta = RecordingMetadata.from_parser(parser)
    ixml = IXmlMetadata.from_parser(parser)

    sources = list(meta.sources)
    if ixml is not None:
        sources.append("ixml")

    return {
        "file": str(path),
        "riff_form": parser.riff_form,
        "format": parser.get_info()["format"],
        "sources": sources,
        "guano": _guano_to_dict(meta.guano),
        "info": dict(meta.info.tags) if meta.info is not None else None,
        "bext": _bext_to_dict(meta.bext),
        "audiomoth": _audiomoth_to_dict(meta.audiomoth),
        "ixml": ixml.to_dict() if ixml is not None else None,
    }


def _guano_to_dict(guano: GuanoMetadata | None) -> dict[str, str] | None:
    if guano is None:
        return None
    return {(f"{ns}|{key}" if ns else key): value for (ns, key), value in guano.fields.items()}


def _bext_to_dict(bext: BextMetadata | None) -> dict | None:
    if bext is None:
        return None
    data = asdict(bext)
    if bext.umid is not None:
        data["umid"] = bext.umid.hex()
    return data


def _audiomoth_to_dict(audiomoth: AudioMothMetadata | None) -> dict | None:
    if audiomoth is None:
        return None
    data = asdict(audiomoth)
    if audiomoth.timestamp is not None:
        data["timestamp"] = audiomoth.timestamp.isoformat()
    return data
