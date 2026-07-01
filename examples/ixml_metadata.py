"""Read iXML metadata embedded in a WAV file.

iXML is a UTF-8 XML document (chunk ``iXML``) used by production recorders. riffy
reads it (authoring iXML is out of scope). This example embeds a small iXML
document as a raw chunk, then reads it back as a nested dict and via ``find()``.
"""

import tempfile
from pathlib import Path

from _helpers import banner, make_pcm_wav

from riffy import IXmlMetadata, WAVParser

IXML_DOC = (
    b"<?xml version='1.0' encoding='UTF-8'?>"
    b"<BWFXML>"
    b"<IXML_VERSION>2.10</IXML_VERSION>"
    b"<PROJECT>Wetland Survey</PROJECT>"
    b"<SCENE>12A</SCENE>"
    b"<TRACK_LIST>"
    b"<TRACK><NAME>Mic L</NAME></TRACK>"
    b"<TRACK><NAME>Mic R</NAME></TRACK>"
    b"</TRACK_LIST>"
    b"</BWFXML>"
)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = make_pcm_wav(Path(tmp) / "take.wav")

        # iXML is read-only in riffy, so embed the chunk directly.
        parser = WAVParser(base)
        parser.add_chunk("iXML", IXML_DOC)
        parser.write_wav(Path(tmp) / "take_tagged.wav")
        banner("Embedded iXML chunk")

        # --- Read it back ---
        ixml = IXmlMetadata.from_parser(WAVParser(Path(tmp) / "take_tagged.wav"))
        assert ixml is not None
        banner("find() lookups")
        print(f"PROJECT:            {ixml.find('PROJECT')}")
        print(f"SCENE:              {ixml.find('SCENE')}")
        print(f"first track name:   {ixml.find('TRACK_LIST/TRACK/NAME')}")

        banner("Full document as a nested dict")
        print(ixml.to_dict())


if __name__ == "__main__":
    main()
