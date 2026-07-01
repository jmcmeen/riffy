"""Tests for riffy.metadata.info (RIFF LIST/INFO read/write)."""

import struct

import pytest

from riffy.exceptions import InvalidChunkError
from riffy.metadata.info import InfoMetadata
from riffy.wav import WAVParser


def info_payload(subchunks: list[tuple[str, bytes]]) -> bytes:
    """Build a raw LIST/INFO payload from ``(fourcc, data)`` subchunks."""
    out = bytearray(b"INFO")
    for fourcc, data in subchunks:
        out += fourcc.encode("latin-1") + struct.pack("<I", len(data)) + data
        if len(data) % 2:
            out += b"\x00"
    return bytes(out)


class TestParsing:
    def test_known_tags_and_friendly_attributes(self):
        info = InfoMetadata.from_bytes(
            info_payload([("INAM", b"My Title\x00"), ("IART", b"An Artist\x00")])
        )
        assert info.title == "My Title"
        assert info.artist == "An Artist"
        assert info.get("INAM") == "My Title"

    def test_null_terminated_value(self):
        info = InfoMetadata.from_bytes(info_payload([("ICMT", b"comment\x00")]))
        assert info.comment == "comment"

    def test_non_terminated_value_tolerated(self):
        # Sloppy producer: no NUL terminator (5-byte odd payload, padded).
        info = InfoMetadata.from_bytes(info_payload([("INAM", b"Title")]))
        assert info.title == "Title"

    def test_odd_padding_between_subchunks(self):
        # First value is odd-length (3 bytes incl. NUL) so a pad byte follows;
        # the second subchunk must still parse from the aligned offset.
        info = InfoMetadata.from_bytes(info_payload([("INAM", b"ab\x00"), ("IART", b"cd\x00")]))
        assert info.title == "ab"
        assert info.artist == "cd"

    def test_multiple_subchunks(self):
        info = InfoMetadata.from_bytes(
            info_payload(
                [
                    ("INAM", b"T\x00"),
                    ("IART", b"A\x00"),
                    ("ICMT", b"C\x00"),
                    ("ISFT", b"riffy\x00"),
                ]
            )
        )
        assert info.tags == {"INAM": "T", "IART": "A", "ICMT": "C", "ISFT": "riffy"}

    def test_unknown_fourcc_preserved_via_raw_access(self):
        info = InfoMetadata.from_bytes(info_payload([("IXYZ", b"custom\x00")]))
        assert info.get("IXYZ") == "custom"
        assert "IXYZ" in info

    def test_truncated_subchunk_warns_and_truncates(self):
        payload = b"INFO" + b"INAM" + struct.pack("<I", 100) + b"short"
        with pytest.warns(UserWarning, match="truncating"):
            info = InfoMetadata.from_bytes(payload)
        assert info.title == "short"

    def test_not_info_list_raises(self):
        with pytest.raises(ValueError, match="Not an INFO list"):
            InfoMetadata.from_bytes(b"adtl" + b"\x00\x00\x00\x00")


class TestRoundTrip:
    def test_read_write_read_stable(self):
        payload = info_payload([("INAM", b"Title\x00"), ("IART", b"Artist\x00")])
        first = InfoMetadata.from_bytes(payload)
        second = InfoMetadata.from_bytes(first.to_chunk_bytes())
        assert first.tags == second.tags

    def test_serialized_values_are_null_terminated_and_even(self):
        info = InfoMetadata()
        info.title = "abc"  # odd length -> value+NUL = 4 bytes (even, no pad)
        info.artist = "ab"  # even -> value+NUL = 3 bytes (odd, needs pad)
        payload = info.to_chunk_bytes()
        # Whole payload length stays even across subchunks.
        assert len(payload) % 2 == 0
        assert InfoMetadata.from_bytes(payload).tags == {"INAM": "abc", "IART": "ab"}

    def test_attribute_round_trip(self):
        info = InfoMetadata()
        info.title = "T"
        info.artist = "A"
        info.comment = "C"
        info.software = "riffy"
        out = InfoMetadata.from_bytes(info.to_chunk_bytes())
        assert (out.title, out.artist, out.comment, out.software) == ("T", "A", "C", "riffy")

    def test_non_ascii_fourcc_survives_round_trip(self):
        # Sloppy encoders emit non-ASCII FOURCCs (e.g. the 0xA9 '©' tags). These
        # parse, and must write back byte-for-byte rather than raising.
        payload = info_payload([("\xa9nam", b"Title\x00")])
        info = InfoMetadata.from_bytes(payload)
        assert info.get("\xa9nam") == "Title"
        # Round-trips without raising, preserving the exact FOURCC bytes.
        assert InfoMetadata.from_bytes(info.to_chunk_bytes()).get("\xa9nam") == "Title"
        assert info.to_chunk_bytes()[4:8] == b"\xa9nam"

    def test_order_preserved(self):
        payload = info_payload([("ISFT", b"s\x00"), ("INAM", b"t\x00"), ("IART", b"a\x00")])
        info = InfoMetadata.from_bytes(payload)
        assert list(info.tags) == ["ISFT", "INAM", "IART"]


class TestAllFriendlyAttributes:
    def test_every_known_tag_round_trips(self):
        info = InfoMetadata()
        info.title = "title"
        info.artist = "artist"
        info.comment = "comment"
        info.creation_date = "2026-07-01"
        info.copyright = "copyright"
        info.software = "software"
        info.engineer = "engineer"
        info.genre = "genre"
        info.product = "product"
        info.source = "source"
        info.technician = "technician"
        info.keywords = "keywords"
        info.subject = "subject"

        out = InfoMetadata.from_bytes(info.to_chunk_bytes())
        assert out.title == "title"
        assert out.artist == "artist"
        assert out.comment == "comment"
        assert out.creation_date == "2026-07-01"
        assert out.copyright == "copyright"
        assert out.software == "software"
        assert out.engineer == "engineer"
        assert out.genre == "genre"
        assert out.product == "product"
        assert out.source == "source"
        assert out.technician == "technician"
        assert out.keywords == "keywords"
        assert out.subject == "subject"


class TestRawAccess:
    def test_set_and_remove(self):
        info = InfoMetadata()
        info.set("ICMT", "hello")
        assert info.comment == "hello"
        info.remove("ICMT")
        assert info.comment is None

    def test_set_none_removes(self):
        info = InfoMetadata.from_bytes(info_payload([("INAM", b"T\x00")]))
        info.title = None
        assert info.title is None
        assert "INAM" not in info

    def test_set_invalid_fourcc_raises(self):
        info = InfoMetadata()
        with pytest.raises(InvalidChunkError):
            info.set("AB", "x")

    def test_get_default(self):
        info = InfoMetadata()
        assert info.get("INAM", "fallback") == "fallback"


class TestParserIntegration:
    def test_from_parser_none_when_no_list(self, make_metadata_wav):
        path = make_metadata_wav([])
        assert InfoMetadata.from_parser(WAVParser(path)) is None

    def test_from_parser_none_when_list_is_not_info(self, make_metadata_wav):
        path = make_metadata_wav([("LIST", b"adtl____")])
        assert InfoMetadata.from_parser(WAVParser(path)) is None

    def test_from_parser_selects_info_among_multiple_lists(self, make_metadata_wav):
        adtl = b"adtl" + b"opaque data!"
        info = info_payload([("INAM", b"Picked\x00")])
        path = make_metadata_wav([("LIST", adtl), ("LIST", info)])
        parsed = InfoMetadata.from_parser(WAVParser(path))
        assert parsed is not None
        assert parsed.title == "Picked"

    def test_write_preserves_other_lists(self, make_metadata_wav, tmp_path):
        adtl = b"adtl" + b"opaque data!"
        info = info_payload([("INAM", b"Old\x00")])
        path = make_metadata_wav([("LIST", adtl), ("LIST", info)])
        parser = WAVParser(path)

        meta = InfoMetadata.from_parser(parser)
        meta.title = "New"
        meta.write_to_parser(parser)

        out = tmp_path / "updated.wav"
        parser.write_wav(out)

        reparsed = WAVParser(out)
        lists = reparsed.get_chunks("LIST")
        assert len(lists) == 2
        # The adtl list is untouched; the INFO list carries the new title.
        assert any(c.data == adtl for c in lists)
        assert InfoMetadata.from_parser(reparsed).title == "New"

    def test_write_adds_info_list_when_absent(self, make_metadata_wav, tmp_path):
        path = make_metadata_wav([])
        parser = WAVParser(path)

        meta = InfoMetadata()
        meta.artist = "AudioMoth"
        meta.write_to_parser(parser)

        out = tmp_path / "with_info.wav"
        parser.write_wav(out)

        reparsed = InfoMetadata.from_parser(WAVParser(out))
        assert reparsed is not None
        assert reparsed.artist == "AudioMoth"
