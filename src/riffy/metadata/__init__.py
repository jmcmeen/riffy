"""Recorder-metadata decoding/encoding layer built on top of the core parser.

This subpackage consumes the raw chunk bytes that :class:`riffy.WAVParser`
already exposes and decodes the metadata standards embedded by bioacoustics
field recorders (GUANO, RIFF INFO, Broadcast Wave ``bext``, iXML, AudioMoth
comment strings). A user who only needs chunk access pays nothing for it.

Phase 1 ships only the shared low-level primitives in :mod:`riffy.metadata.base`
(ZSTR handling, even-byte padding, FOURCC validation, fail-soft text decoding);
the per-standard modules build on these. Those primitives are intentionally not
re-exported at the package level yet — they are reachable via
``riffy.metadata.base`` but are not committed public API. This ``__init__`` will
re-export the typed metadata classes (GUANO, INFO, bext, ...) as they land.
"""

from .audiomoth import AudioMothMetadata
from .bext import BextMetadata
from .guano import GuanoMetadata
from .info import InfoMetadata
from .recording import RecordingMetadata, read_metadata

__all__ = [
    "AudioMothMetadata",
    "BextMetadata",
    "GuanoMetadata",
    "InfoMetadata",
    "RecordingMetadata",
    "read_metadata",
]
