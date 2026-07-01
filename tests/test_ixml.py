"""Tests for riffy.metadata.ixml (iXML read, stretch goal)."""

from riffy.metadata.ixml import IXmlMetadata
from riffy.wav import WAVParser

SAMPLE = (
    b"<?xml version='1.0' encoding='UTF-8'?>"
    b"<BWFXML>"
    b"<IXML_VERSION>2.10</IXML_VERSION>"
    b"<PROJECT>Riffy Test</PROJECT>"
    b"<SPEED><NOTE>example</NOTE></SPEED>"
    b"<TRACK_LIST>"
    b"<TRACK><NAME>Mic1</NAME></TRACK>"
    b"<TRACK><NAME>Mic2</NAME></TRACK>"
    b"</TRACK_LIST>"
    b"</BWFXML>"
)


class TestParsing:
    def test_to_dict_nested(self):
        ixml = IXmlMetadata.from_bytes(SAMPLE)
        data = ixml.to_dict()
        assert data["BWFXML"]["PROJECT"] == "Riffy Test"
        assert data["BWFXML"]["IXML_VERSION"] == "2.10"
        assert data["BWFXML"]["SPEED"] == {"NOTE": "example"}

    def test_repeated_tags_become_list(self):
        data = IXmlMetadata.from_bytes(SAMPLE).to_dict()
        tracks = data["BWFXML"]["TRACK_LIST"]["TRACK"]
        assert tracks == [{"NAME": "Mic1"}, {"NAME": "Mic2"}]

    def test_three_repeated_tags_all_collected(self):
        xml = b"<r><x>1</x><x>2</x><x>3</x></r>"
        data = IXmlMetadata.from_bytes(xml).to_dict()
        assert data["r"]["x"] == ["1", "2", "3"]

    def test_find(self):
        ixml = IXmlMetadata.from_bytes(SAMPLE)
        assert ixml.find("PROJECT") == "Riffy Test"
        assert ixml.find("TRACK_LIST/TRACK/NAME") == "Mic1"  # first match
        assert ixml.find("MISSING") is None

    def test_nul_padded_payload(self):
        ixml = IXmlMetadata.from_bytes(SAMPLE + b"\x00\x00")
        assert ixml.find("PROJECT") == "Riffy Test"

    def test_root_element_exposed(self):
        ixml = IXmlMetadata.from_bytes(SAMPLE)
        assert ixml.root.tag == "BWFXML"


class TestParserIntegration:
    def test_from_parser_none_when_absent(self, make_metadata_wav):
        assert IXmlMetadata.from_parser(WAVParser(make_metadata_wav([]))) is None

    def test_from_parser_reads_ixml(self, make_metadata_wav):
        path = make_metadata_wav([("iXML", SAMPLE)])
        ixml = IXmlMetadata.from_parser(WAVParser(path))
        assert ixml is not None
        assert ixml.find("PROJECT") == "Riffy Test"

    def test_malformed_xml_warns_and_returns_none(self, make_metadata_wav):
        import pytest

        path = make_metadata_wav([("iXML", b"<BWFXML><unclosed>")])
        with pytest.warns(UserWarning, match="valid XML"):
            assert IXmlMetadata.from_parser(WAVParser(path)) is None
