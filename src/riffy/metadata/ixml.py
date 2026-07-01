"""iXML metadata: read the ``iXML`` chunk (stretch goal, read-only).

iXML is a UTF-8 XML document embedded in an ``iXML`` chunk, used by production
recorders (Sound Devices, Zoom, ...) to carry structured take/scene/track
metadata. This module parses it into a nested dict / element tree for
inspection. Authoring iXML is out of scope for v0.3.0.

Security note: parsing uses the standard library ``xml.etree.ElementTree``,
which does not fetch external entities but is not hardened against maliciously
crafted XML (e.g. entity-expansion attacks). iXML from field recorders is
effectively trusted input; do not point this at hostile XML without your own
hardening (riffy keeps the zero-dependency promise, so it does not bundle
``defusedxml``).
"""

import warnings
from xml.etree.ElementTree import Element, ParseError, fromstring

from ..wav import WAVParser
from .base import decode_text

#: The iXML sub-chunk ID.
CHUNK_ID = "iXML"


class IXmlMetadata:
    """Read-only view of an ``iXML`` chunk's XML document."""

    def __init__(self, root: Element) -> None:
        #: The parsed XML root element (``xml.etree.ElementTree.Element``).
        self.root = root

    @classmethod
    def from_bytes(cls, data: bytes) -> "IXmlMetadata":
        """Parse iXML from a raw ``iXML`` chunk payload.

        Raises:
            xml.etree.ElementTree.ParseError: If the payload is not valid XML.
        """
        # iXML is UTF-8 and commonly NUL-padded to an even length; trim padding
        # and surrounding whitespace before handing it to the XML parser.
        text = decode_text(data, context="iXML").strip("\x00 \t\r\n")
        return cls(fromstring(text))

    @classmethod
    def from_parser(cls, parser: WAVParser) -> "IXmlMetadata | None":
        """Parse the ``iXML`` chunk from a parser.

        Returns ``None`` if the file has no ``iXML`` chunk, or if the chunk is
        present but does not contain parseable XML (a warning is emitted).
        """
        raw = parser.get_chunk_bytes(CHUNK_ID)
        if raw is None:
            return None
        try:
            return cls.from_bytes(raw)
        except ParseError:
            warnings.warn("iXML: chunk does not contain valid XML; skipping", stacklevel=2)
            return None

    def find(self, path: str) -> str | None:
        """Return the text of the first element matching an ElementTree ``path``."""
        return self.root.findtext(path)

    def to_dict(self) -> dict[str, object]:
        """Return the document as a nested dict keyed by the root tag.

        Leaf elements become their stripped text; repeated child tags become a
        list of values.
        """
        return {self.root.tag: _element_to_dict(self.root)}


def _element_to_dict(element: Element) -> object:
    """Recursively convert an XML element into text (leaf) or a nested dict."""
    children = list(element)
    if not children:
        return (element.text or "").strip()

    result: dict[str, object] = {}
    for child in children:
        value = _element_to_dict(child)
        if child.tag in result:
            existing = result[child.tag]
            if isinstance(existing, list):
                existing.append(value)
            else:
                result[child.tag] = [existing, value]
        else:
            result[child.tag] = value
    return result
