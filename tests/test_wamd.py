"""Tests for riffy.metadata.wamd (Wildlife Acoustics WAMD read/write)."""

import struct

import pytest

from riffy.metadata import read_metadata
from riffy.metadata.wamd import WamdMetadata
from riffy.wav import WAVParser


def entry(tag: int, value: bytes) -> bytes:
    """Build one raw WAMD entry (uint16 id, uint32 length, value) independently."""
    return struct.pack("<HI", tag, len(value)) + value


# A representative Song Meter stream: version + model + firmware + GPS (SM
# dialect) + an alignment pad + an unknown vendor entry riffy must preserve.
SAMPLE = (
    entry(0x00, struct.pack("<H", 1))
    + entry(0x01, b"Song Meter Micro")
    + entry(0x03, b"4.5")
    + entry(0x06, b"WGS84,10.31796,N,84.07411,W")
    + entry(0xFFFF, b"")
    + entry(0x42, b"vendor-blob")
)


class TestParsing:
    def test_typed_fields(self):
        w = WamdMetadata.from_bytes(SAMPLE)
        assert w.version == 1
        assert w.model == "Song Meter Micro"
        assert w.firmware == "4.5"
        assert w.loc_position == (10.31796, -84.07411)

    def test_loc_position_emtouch_signed_dialect(self):
        w = WamdMetadata.from_bytes(entry(0x06, b"WGS84,-12.5,110.25"))
        assert w.loc_position == (-12.5, 110.25)

    def test_loc_position_absent(self):
        w = WamdMetadata.from_bytes(entry(0x01, b"model only"))
        assert w.loc_position is None

    def test_loc_position_non_numeric_warns_and_returns_none(self):
        w = WamdMetadata.from_bytes(entry(0x06, b"WGS84,north,west"))
        with pytest.warns(UserWarning):
            assert w.loc_position is None

    def test_loc_position_too_few_parts_returns_none(self):
        w = WamdMetadata.from_bytes(entry(0x06, b"garbage"))
        assert w.loc_position is None

    def test_unknown_and_blob_entries_preserved(self):
        w = WamdMetadata.from_bytes(SAMPLE)
        assert w.get_raw(0x42) == b"vendor-blob"
        assert 0xFFFF in w

    def test_truncated_length_is_clamped(self):
        # Claim 100 bytes but supply only 3; parsing must not raise.
        bad = struct.pack("<HI", 0x01, 100) + b"abc"
        with pytest.warns(UserWarning):
            w = WamdMetadata.from_bytes(bad)
        assert w.model == "abc"


class TestRoundTrip:
    def test_byte_exact_when_untouched(self):
        w = WamdMetadata.from_bytes(SAMPLE)
        assert w.to_chunk_bytes() == SAMPLE

    def test_only_gps_entry_changes(self):
        w = WamdMetadata.from_bytes(SAMPLE)
        w.loc_position = (1.5, -2.5)
        reparsed = WamdMetadata.from_bytes(w.to_chunk_bytes())
        assert reparsed.loc_position == (1.5, -2.5)
        # Everything else is intact.
        assert reparsed.model == "Song Meter Micro"
        assert reparsed.version == 1
        assert reparsed.get_raw(0x42) == b"vendor-blob"
        assert 0xFFFF in reparsed

    def test_set_gps_preserves_datum_and_altitude(self):
        w = WamdMetadata.from_bytes(entry(0x06, b"WGS84,10.0,N,20.0,E,123"))
        w.loc_position = (1.0, 2.0)
        assert w.get_text(0x06) == "WGS84,1.0,2.0,123"
        assert w.loc_position == (1.0, 2.0)

    def test_set_text_replaces_in_place(self):
        w = WamdMetadata.from_bytes(SAMPLE)
        w.set_text(0x01, "New Model")
        entries = w.entries
        # Same number of entries, still at the original position (index 1).
        assert len(entries) == len(WamdMetadata.from_bytes(SAMPLE).entries)
        assert entries[1] == (0x01, b"New Model")

    def test_remove_drops_all_occurrences(self):
        w = WamdMetadata.from_bytes(SAMPLE)
        w.remove(0xFFFF)
        assert 0xFFFF not in w


class TestFromParser:
    def test_reads_wamd_chunk(self, make_metadata_wav):
        path = make_metadata_wav([("wamd", SAMPLE)])
        meta = read_metadata(path)
        assert "wamd" in meta.sources
        assert meta.wamd.loc_position == (10.31796, -84.07411)

    def test_reads_junk_variant(self, make_metadata_wav):
        path = make_metadata_wav([("junk", SAMPLE)])
        meta = read_metadata(path)
        assert "wamd" in meta.sources
        assert meta.wamd.loc_position == (10.31796, -84.07411)

    def test_plain_junk_padding_is_not_wamd(self, make_metadata_wav):
        path = make_metadata_wav([("junk", b"\x00" * 64)])
        meta = read_metadata(path)
        assert "wamd" not in meta.sources
        assert meta.wamd is None

    def test_wamd_preferred_over_junk(self, make_metadata_wav):
        junk_stream = entry(0x00, struct.pack("<H", 1)) + entry(0x06, b"WGS84,1.0,2.0")
        path = make_metadata_wav([("junk", junk_stream), ("wamd", SAMPLE)])
        meta = read_metadata(path)
        assert meta.wamd.loc_position == (10.31796, -84.07411)

    def test_absent_returns_none(self, make_metadata_wav):
        path = make_metadata_wav([])
        assert read_metadata(path).wamd is None


class TestWriteToParser:
    def test_write_and_reread(self, make_metadata_wav, tmp_path):
        path = make_metadata_wav([("wamd", SAMPLE)])
        wav = WAVParser(path)
        wamd = WamdMetadata.from_parser(wav)
        wamd.loc_position = (1.5, -2.5)
        wamd.write_to_parser(wav)
        out = tmp_path / "out.wav"
        wav.write_wav(out)
        assert read_metadata(out).wamd.loc_position == (1.5, -2.5)

    def test_write_back_to_junk_source(self, make_metadata_wav, tmp_path):
        path = make_metadata_wav([("junk", SAMPLE)])
        wav = WAVParser(path)
        wamd = WamdMetadata.from_parser(wav)
        wamd.loc_position = (3.0, 4.0)
        wamd.write_to_parser(wav)
        out = tmp_path / "out.wav"
        wav.write_wav(out)
        reread = WAVParser(out)
        # The junk chunk was updated in place; no stray wamd chunk was added.
        assert reread.get_chunk("wamd") is None
        assert read_metadata(out).wamd.loc_position == (3.0, 4.0)

    def test_fresh_metadata_appends_wamd_chunk(self, make_metadata_wav, tmp_path):
        path = make_metadata_wav([])
        wav = WAVParser(path)
        wamd = WamdMetadata()
        wamd.loc_position = (5.0, 6.0)
        wamd.write_to_parser(wav)
        out = tmp_path / "out.wav"
        wav.write_wav(out)
        assert read_metadata(out).wamd.loc_position == (5.0, 6.0)


class TestToDict:
    def test_named_and_position(self):
        d = WamdMetadata.from_bytes(SAMPLE).to_dict()
        assert d["version"] == 1
        assert d["model"] == "Song Meter Micro"
        assert d["loc_position"] == [10.31796, -84.07411]
        # Alignment padding is omitted from the inspection view.
        assert "0xffff" not in d
