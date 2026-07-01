"""Tests for riffy.metadata.bext (Broadcast Wave read/write, version-gated)."""

import struct

from riffy.metadata.bext import BextMetadata
from riffy.wav import WAVParser

# Independent raw-payload builder (does not use the module's own packing), so
# the parser is validated against a separately-constructed binary layout.
_FMT = "<256s32s32s10s8sIIH64shhhhh180s"


def raw_bext(
    *,
    version=1,
    description=b"",
    originator=b"",
    originator_reference=b"",
    origination_date=b"",
    origination_time=b"",
    time_reference=0,
    umid=b"\x00" * 64,
    loudness=(0, 0, 0, 0, 0),
    coding_history=b"",
):
    fixed = struct.pack(
        _FMT,
        description,
        originator,
        originator_reference,
        origination_date,
        origination_time,
        time_reference & 0xFFFFFFFF,
        time_reference >> 32,
        version,
        umid,
        *loudness,
        b"",  # Reserved (struct zero-pads to 180)
    )
    return fixed + coding_history


class TestParsing:
    def test_parse_base_fields(self):
        payload = raw_bext(
            version=0,
            description=b"A test recording",
            originator=b"riffy",
            originator_reference=b"REF123",
            origination_date=b"2023-08-14",
            origination_time=b"21:01:18",
            time_reference=44100,
            coding_history=b"A=PCM,F=44100,W=16,M=mono\r\n",
        )
        b = BextMetadata.from_bytes(payload)
        assert b.description == "A test recording"
        assert b.originator == "riffy"
        assert b.originator_reference == "REF123"
        assert b.origination_date == "2023-08-14"
        assert b.origination_time == "21:01:18"
        assert b.time_reference == 44100
        assert b.version == 0
        assert b.coding_history == "A=PCM,F=44100,W=16,M=mono\r\n"

    def test_v0_has_no_umid_or_loudness(self):
        b = BextMetadata.from_bytes(raw_bext(version=0, umid=b"X" * 64, loudness=(1, 2, 3, 4, 5)))
        assert b.umid is None
        assert b.loudness_value is None
        assert b.max_short_term_loudness is None

    def test_v1_has_umid_but_no_loudness(self):
        umid = bytes(range(64))
        b = BextMetadata.from_bytes(raw_bext(version=1, umid=umid, loudness=(1, 2, 3, 4, 5)))
        assert b.umid == umid
        assert b.loudness_value is None

    def test_v2_has_loudness(self):
        b = BextMetadata.from_bytes(
            raw_bext(version=2, umid=b"U" * 64, loudness=(-23, 7, -1, -18, -20))
        )
        assert b.umid == b"U" * 64
        assert b.loudness_value == -23
        assert b.loudness_range == 7
        assert b.max_true_peak_level == -1
        assert b.max_momentary_loudness == -18
        assert b.max_short_term_loudness == -20

    def test_time_reference_uses_full_64_bits(self):
        # A sample count that does not fit in 32 bits exercises the high word.
        tr = 5_000_000_000
        b = BextMetadata.from_bytes(raw_bext(time_reference=tr))
        assert b.time_reference == tr

    def test_null_padded_strings_trimmed(self):
        payload = raw_bext(description=b"short" + b"\x00" * 251)
        assert BextMetadata.from_bytes(payload).description == "short"

    def test_truncated_chunk_degrades(self):
        # Only 20 bytes; must parse (zero-padded) rather than raising.
        b = BextMetadata.from_bytes(b"partial description!")
        assert b.description == "partial description!"
        assert b.version == 0


class TestRoundTrip:
    def test_v2_round_trip_preserves_all_fields(self):
        original = BextMetadata(
            description="desc",
            originator="orig",
            originator_reference="ref",
            origination_date="2023-08-14",
            origination_time="21:01:18",
            time_reference=5_000_000_000,
            version=2,
            umid=bytes(range(64)),
            loudness_value=-23,
            loudness_range=7,
            max_true_peak_level=-1,
            max_momentary_loudness=-18,
            max_short_term_loudness=-20,
            coding_history="A=PCM,F=44100\r\n",
        )
        assert BextMetadata.from_bytes(original.to_chunk_bytes()) == original

    def test_v1_round_trip_preserves_umid(self):
        original = BextMetadata(version=1, umid=b"\xaa" * 64, description="v1")
        restored = BextMetadata.from_bytes(original.to_chunk_bytes())
        assert restored.umid == b"\xaa" * 64
        assert restored.loudness_value is None

    def test_v0_write_zero_fills_versioned_regions(self):
        payload = BextMetadata(version=0, description="v0").to_chunk_bytes()
        # Fixed portion is always 602 bytes; UMID/loudness region is all zeros.
        assert len(payload) == 602
        assert payload[348:412] == b"\x00" * 64  # UMID region

    def test_short_umid_padded_on_write(self):
        b = BextMetadata(version=1, umid=b"\x01\x02")
        restored = BextMetadata.from_bytes(b.to_chunk_bytes())
        assert restored.umid == b"\x01\x02" + b"\x00" * 62


class TestParserIntegration:
    def test_from_parser_none_when_absent(self, make_metadata_wav):
        path = make_metadata_wav([])
        assert BextMetadata.from_parser(WAVParser(path)) is None

    def test_from_parser_reads_bext(self, make_metadata_wav):
        payload = raw_bext(version=2, description=b"embedded", loudness=(-23, 0, 0, 0, 0))
        path = make_metadata_wav([("bext", payload)])
        b = BextMetadata.from_parser(WAVParser(path))
        assert b is not None
        assert b.description == "embedded"
        assert b.loudness_value == -23

    def test_write_to_parser_round_trips_through_disk(self, make_metadata_wav, tmp_path):
        path = make_metadata_wav([])
        parser = WAVParser(path)

        b = BextMetadata(version=1, originator="riffy", umid=b"\x07" * 64, time_reference=88200)
        b.write_to_parser(parser)

        out = tmp_path / "with_bext.wav"
        parser.write_wav(out)

        restored = BextMetadata.from_parser(WAVParser(out))
        assert restored is not None
        assert restored.originator == "riffy"
        assert restored.umid == b"\x07" * 64
        assert restored.time_reference == 88200

    def test_write_to_parser_replaces_existing(self, make_metadata_wav, tmp_path):
        original = raw_bext(version=0, description=b"old")
        path = make_metadata_wav([("bext", original)])
        parser = WAVParser(path)

        b = BextMetadata.from_parser(parser)
        b.description = "new"
        b.write_to_parser(parser)

        out = tmp_path / "updated.wav"
        parser.write_wav(out)

        reparsed = WAVParser(out)
        assert len(reparsed.get_chunks("bext")) == 1
        assert BextMetadata.from_parser(reparsed).description == "new"
