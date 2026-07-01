"""Tests for riffy.metadata.base shared primitives and the fixtures harness."""

import pytest

from riffy.exceptions import InvalidChunkError
from riffy.metadata.base import (
    decode_text,
    pad_to_even,
    read_zstr,
    validate_fourcc,
    write_zstr,
)
from riffy.wav import WAVParser


class TestValidateFourcc:
    def test_valid_ids(self):
        assert validate_fourcc("guan") == b"guan"
        assert validate_fourcc("fmt ") == b"fmt "
        assert validate_fourcc("LIST") == b"LIST"

    def test_wrong_length_raises(self):
        with pytest.raises(InvalidChunkError, match="exactly 4 characters"):
            validate_fourcc("abc")
        with pytest.raises(InvalidChunkError, match="exactly 4 characters"):
            validate_fourcc("abcde")

    def test_non_ascii_raises(self):
        with pytest.raises(InvalidChunkError, match="ASCII"):
            validate_fourcc("gu\xe9n")


class TestPadToEven:
    def test_odd_length_padded_with_nul(self):
        assert pad_to_even(b"abc") == b"abc\x00"

    def test_even_length_unchanged(self):
        assert pad_to_even(b"abcd") == b"abcd"

    def test_empty_is_even(self):
        assert pad_to_even(b"") == b""

    def test_custom_pad_byte(self):
        # GUANO writers commonly reserve space with a space (0x20).
        assert pad_to_even(b"abc", pad_byte=0x20) == b"abc "


class TestReadZstr:
    def test_basic(self):
        assert read_zstr(b"hello\x00world\x00") == ("hello", 6)

    def test_offset(self):
        text, nxt = read_zstr(b"hello\x00world\x00", offset=6)
        assert text == "world"
        assert nxt == 12

    def test_missing_terminator_reads_to_end(self):
        # Recorders are sloppy; a non-terminated value still decodes.
        assert read_zstr(b"no terminator") == ("no terminator", 13)

    def test_empty_string_before_terminator(self):
        assert read_zstr(b"\x00rest") == ("", 1)

    def test_encoding(self):
        # latin-1 default round-trips arbitrary high bytes.
        assert read_zstr(b"caf\xe9\x00") == ("caf\xe9", 5)


class TestWriteZstr:
    def test_basic(self):
        assert write_zstr("hello") == b"hello\x00"

    def test_round_trips_with_read_zstr(self):
        encoded = write_zstr("Round Trip", encoding="utf-8")
        text, nxt = read_zstr(encoded, encoding="utf-8")
        assert text == "Round Trip"
        assert nxt == len(encoded)


class TestDecodeText:
    def test_valid_utf8(self):
        assert decode_text("café".encode()) == "café"

    def test_invalid_utf8_falls_back_to_latin1_with_warning(self):
        # 0xFF is not valid UTF-8; should warn and decode as latin-1.
        with pytest.warns(UnicodeWarning, match="latin-1"):
            result = decode_text(b"bad\xff", context="guan")
        assert result == "bad\xff"

    def test_context_appears_in_warning(self):
        with pytest.warns(UnicodeWarning, match="myctx"):
            decode_text(b"\xff", context="myctx")


class TestMetadataFixtureHarness:
    """The make_metadata_wav factory authors files riffy can round-trip."""

    def test_single_metadata_chunk_round_trips(self, make_metadata_wav):
        path = make_metadata_wav([("guan", b"GUANO|Version: 1.0\n")])
        parser = WAVParser(path)
        assert parser.get_chunk_bytes("guan") == b"GUANO|Version: 1.0\n"

    def test_duplicate_fourccs_preserved(self, make_metadata_wav):
        path = make_metadata_wav([("LIST", b"first"), ("LIST", b"secondlst")])
        parser = WAVParser(path)
        lists = parser.get_chunks("LIST")
        assert [c.data for c in lists] == [b"first", b"secondlst"]

    def test_odd_length_payload_is_padded_on_disk(self, make_metadata_wav):
        # "odd" is 3 bytes; the file must still parse (even-byte padding).
        path = make_metadata_wav([("guan", b"odd")])
        parser = WAVParser(path)
        assert parser.get_chunk_bytes("guan") == b"odd"
