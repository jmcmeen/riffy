"""Tests for riffy.metadata.guano (GUANO read/write, the v0.3.0 flagship)."""

import warnings
from datetime import datetime, timedelta, timezone

import pytest

from riffy.metadata.guano import GuanoMetadata
from riffy.wav import WAVParser

# The canonical worked example reproduced verbatim from the GUANO specification
# (github.com/riggsd/guano-spec) — Pettersson D1000X with SonoBat "SB" and
# Pettersson "PET" vendor namespaces. Kept byte-exact (two-space separators,
# blank section breaks, escaped multiline Note) so the parse is validated
# against the spec's own text rather than a self-authored stand-in.
CONFORMANCE = (
    b"GUANO|Version:  1.0\n"
    b"\n"
    b"Timestamp:  2012-03-29T03:58:01+04:00\n"
    b"Species Auto ID:  MYLU\n"
    b"Species Manual ID:  Myosod\n"
    b"Tags:  hand-release, voucher, workshop\n"
    b"Note:  Hand release of male Indiana Bat caught in triple-high net at Mammoth Cave "
    b"Historic Ent.\\nReleased in low-clutter 100m diameter clearing, bat flew directly "
    b"overhead, circled once, then darted off into cluttered forest.\\n\\nRecorded by David "
    b"Riggs with Pettersson D1000X at 2014 BCM acoustic workshop.\n"
    b"TE:  1\n"
    b"Samplerate:  500000\n"
    b"Length:  6.5\n"
    b"Filter HP:  20.0\n"
    b"Make:  Pettersson\n"
    b"Model:  D1000X\n"
    b"Loc Position:  37.1878016 -86.1057312\n"
    b"Loc Accuracy:  20\n"
    b"Loc Elevation:  228.6\n"
    b"\n"
    b"SB|Version:  3.4\n"
    b"SB|Classifier:  US Northeast\n"
    b"SB|DiscrProb:  0.913\n"
    b"SB|Filter:  20kHz Anti-Katydid\n"
    b"\n"
    b"PET|Gain:  80\n"
    b"PET|Firmware:  1.0.4 (2009-11-25)\n"
)


class TestParsing:
    def test_conformance_fields(self):
        g = GuanoMetadata.from_bytes(CONFORMANCE)
        assert g.version == "1.0"
        assert g.make == "Pettersson"
        assert g.model == "D1000X"
        assert g.samplerate == 500000
        assert g.length == 6.5
        assert g.te == 1
        assert g.filter_hp == 20.0
        assert g.loc_accuracy == 20.0
        assert g.loc_elevation == 228.6

    def test_timestamp_preserves_offset(self):
        g = GuanoMetadata.from_bytes(CONFORMANCE)
        expected = datetime(2012, 3, 29, 3, 58, 1, tzinfo=timezone(timedelta(hours=4)))
        assert g.timestamp == expected
        # Offset must NOT be normalized away to UTC.
        assert g.timestamp.utcoffset() == timedelta(hours=4)

    def test_loc_position_tuple(self):
        g = GuanoMetadata.from_bytes(CONFORMANCE)
        assert g.loc_position == (37.1878016, -86.1057312)

    def test_list_fields(self):
        g = GuanoMetadata.from_bytes(CONFORMANCE)
        assert g.species_auto_id == ["MYLU"]
        assert g.species_manual_id == ["Myosod"]
        assert g.tags == ["hand-release", "voucher", "workshop"]

    def test_multiline_note_unescaped(self):
        g = GuanoMetadata.from_bytes(CONFORMANCE)
        # The Note carries three escaped newlines (one of them a blank line),
        # so the unescaped value splits into four segments.
        segments = g.note.split("\n")
        assert len(segments) == 4
        assert segments[0].startswith("Hand release of male Indiana Bat")
        assert segments[2] == ""
        assert segments[3].startswith("Recorded by David Riggs")

    def test_vendor_namespace_access(self):
        g = GuanoMetadata.from_bytes(CONFORMANCE)
        assert g.get("SB", "Classifier") == "US Northeast"
        assert g.get("SB", "DiscrProb") == "0.913"
        assert g.get("PET", "Firmware") == "1.0.4 (2009-11-25)"
        assert ("SB", "Classifier") in g.fields

    def test_te_defaults_to_one_when_absent(self):
        g = GuanoMetadata.from_bytes(b"GUANO|Version: 1.0\n")
        assert g.te == 1

    def test_empty_and_whitespace_lines_ignored(self):
        g = GuanoMetadata.from_bytes(b"GUANO|Version: 1.0\n\n   \nMake: X\n")
        assert g.make == "X"
        assert len(g.fields) == 2


class TestRoundTrip:
    def test_read_write_read_stable(self):
        first = GuanoMetadata.from_bytes(CONFORMANCE)
        serialized = first.to_chunk_bytes()
        second = GuanoMetadata.from_bytes(serialized)
        assert first.fields == second.fields

    def test_version_first_even_if_set_last(self):
        g = GuanoMetadata()
        g.make = "Foo"
        g.version = "1.0"
        out = g.to_chunk_bytes()
        assert out.split(b"\n")[0] == b"GUANO|Version: 1.0"

    def test_output_is_even_length(self):
        g = GuanoMetadata.from_bytes(CONFORMANCE)
        assert len(g.to_chunk_bytes()) % 2 == 0

    def test_unknown_fields_preserved_verbatim(self):
        raw = b"GUANO|Version: 1.0\nWA|Custom Thing: keep me\nXYZ|Other: also\n"
        g = GuanoMetadata.from_bytes(raw)
        out = GuanoMetadata.from_bytes(g.to_chunk_bytes())
        assert out.get("WA", "Custom Thing") == "keep me"
        assert out.get("XYZ", "Other") == "also"

    def test_multiline_reescaped_on_write(self):
        g = GuanoMetadata(version="1.0")
        g.note = "line1\nline2"
        out = g.to_chunk_bytes()
        # The intra-value newline is escaped; only field separators are real.
        assert b"Note: line1\\nline2" in out
        assert GuanoMetadata.from_bytes(out).note == "line1\nline2"

    def test_field_order_preserved(self):
        raw = b"GUANO|Version: 1.0\nModel: B\nMake: A\n"
        g = GuanoMetadata.from_bytes(raw)
        out = g.to_chunk_bytes()
        lines = out.rstrip().split(b"\n")
        assert lines[1] == b"Model: B"
        assert lines[2] == b"Make: A"


class TestTypedAssignment:
    def test_attribute_assignment_round_trips(self):
        g = GuanoMetadata(version="1.0")
        g.make = "Wildlife Acoustics"
        g.samplerate = 256000
        g.loc_position = (37.1878, -86.1057)
        g.species_manual_id = ["MYLU"]
        ts = datetime(2020, 5, 1, 22, 0, 0, tzinfo=timezone.utc)
        g.timestamp = ts

        out = GuanoMetadata.from_bytes(g.to_chunk_bytes())
        assert out.make == "Wildlife Acoustics"
        assert out.samplerate == 256000
        assert out.loc_position == (37.1878, -86.1057)
        assert out.species_manual_id == ["MYLU"]
        assert out.timestamp == ts

    def test_setting_none_removes_field(self):
        g = GuanoMetadata.from_bytes(CONFORMANCE)
        g.make = None
        assert g.make is None
        assert ("", "Make") not in g.fields

    def test_generic_set_get(self):
        g = GuanoMetadata(version="1.0")
        g.set("WA", "Temperature Int", "12.5")
        assert g.get("WA", "Temperature Int") == "12.5"

    def test_binary_helpers(self):
        g = GuanoMetadata(version="1.0")
        g.set_binary("User", "Blob", b"\x00\x01\x02\xff")
        assert g.get_binary("User", "Blob") == b"\x00\x01\x02\xff"


class TestAllWellKnownAttributes:
    """Exercise every typed attribute's get+set through a round-trip."""

    def test_full_attribute_round_trip(self):
        g = GuanoMetadata(version="1.0")
        g.make = "mk"
        g.model = "mdl"
        g.serial = "sn"
        g.firmware_version = "fw"
        g.hardware_version = "hw"
        g.original_filename = "orig.wav"
        g.note = "a note"
        g.length = 3.25
        g.filter_hp = 16.0
        g.filter_lp = 192.0
        g.humidity = 55.5
        g.temperature_int = 20.1
        g.temperature_ext = 18.4
        g.loc_accuracy = 5.0
        g.loc_elevation = 100.0
        g.samplerate = 384000
        g.te = 8
        g.species_auto_id = ["A", "B"]

        out = GuanoMetadata.from_bytes(g.to_chunk_bytes())
        assert out.make == "mk"
        assert out.model == "mdl"
        assert out.serial == "sn"
        assert out.firmware_version == "fw"
        assert out.hardware_version == "hw"
        assert out.original_filename == "orig.wav"
        assert out.note == "a note"
        assert out.length == 3.25
        assert out.filter_hp == 16.0
        assert out.filter_lp == 192.0
        assert out.humidity == 55.5
        assert out.temperature_int == 20.1
        assert out.temperature_ext == 18.4
        assert out.loc_accuracy == 5.0
        assert out.loc_elevation == 100.0
        assert out.samplerate == 384000
        assert out.te == 8
        assert out.species_auto_id == ["A", "B"]


class TestTimestampAndLocationEdges:
    def test_zulu_timestamp_normalized_to_utc(self):
        g = GuanoMetadata.from_bytes(b"GUANO|Version: 1.0\nTimestamp: 2020-01-02T03:04:05Z\n")
        assert g.timestamp == datetime(2020, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    def test_timestamp_set_as_string(self):
        g = GuanoMetadata(version="1.0")
        g.timestamp = "2021-07-01T12:00:00+00:00"
        assert g.timestamp == datetime(2021, 7, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_loc_position_non_numeric_parts_warns(self):
        g = GuanoMetadata.from_bytes(b"GUANO|Version: 1.0\nLoc Position: north south\n")
        with pytest.warns(UserWarning, match="non-numeric"):
            assert g.loc_position is None

    def test_nullable_fields_removed_when_set_none(self):
        g = GuanoMetadata.from_bytes(CONFORMANCE)
        g.length = None
        g.samplerate = None
        g.species_manual_id = None
        g.timestamp = None
        g.loc_position = None
        g.version = None
        for key in ("Length", "Samplerate", "Species Manual ID", "Timestamp", "Loc Position"):
            assert ("", key) not in g.fields
        assert g.version is None


class TestAbsentFields:
    def test_absent_typed_fields_return_none_or_empty(self):
        g = GuanoMetadata(version="1.0")
        assert g.length is None
        assert g.timestamp is None
        assert g.loc_position is None
        assert g.tags == []
        assert g.get_binary("User", "Blob") is None

    def test_tags_setter(self):
        g = GuanoMetadata(version="1.0")
        g.tags = ["x", "y"]
        assert GuanoMetadata.from_bytes(g.to_chunk_bytes()).tags == ["x", "y"]

    def test_empty_timestamp_value_returns_none(self):
        g = GuanoMetadata.from_bytes(b"GUANO|Version: 1.0\nTimestamp: \n")
        assert g.timestamp is None


class TestRealWorldWildlifeAcoustics:
    """Regression cases captured from a real Song Meter Micro `guan` chunk."""

    def test_unpadded_offset_hour_and_space_separator(self):
        # WA emits '2023-08-14 21:01:18-4:00': space separator + single-digit
        # offset hour, neither of which datetime.fromisoformat accepts raw.
        g = GuanoMetadata.from_bytes(b"GUANO|Version: 1.0\nTimestamp: 2023-08-14 21:01:18-4:00\n")
        assert g.timestamp == datetime(2023, 8, 14, 21, 1, 18, tzinfo=timezone(timedelta(hours=-4)))
        # The raw field is preserved verbatim for round-trip.
        assert g.get("", "Timestamp") == "2023-08-14 21:01:18-4:00"

    def test_nul_padded_trailing_line_ignored_without_warning(self):
        # The chunk is NUL-padded rather than space-padded.
        raw = b"GUANO|Version: 1.0\nSamplerate:44100\n\x00"
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # any warning fails the test
            g = GuanoMetadata.from_bytes(raw)
        assert g.samplerate == 44100
        assert len(g.fields) == 2

    def test_nested_pipe_vendor_key_round_trips(self):
        raw = b'GUANO|Version: 1.0\nWA|Song Meter|Audio settings: [{"rate":44100}]\n'
        g = GuanoMetadata.from_bytes(raw)
        assert g.get("WA", "Song Meter|Audio settings") == '[{"rate":44100}]'
        out = GuanoMetadata.from_bytes(g.to_chunk_bytes())
        assert out.get("WA", "Song Meter|Audio settings") == '[{"rate":44100}]'


class TestMappingHelpers:
    def test_remove(self):
        g = GuanoMetadata.from_bytes(CONFORMANCE)
        g.remove("SB", "Classifier")
        assert g.get("SB", "Classifier") is None
        g.remove("SB", "Classifier")  # idempotent, no error

    def test_contains_and_iter(self):
        g = GuanoMetadata.from_bytes(b"GUANO|Version: 1.0\nMake: X\n")
        assert ("", "Make") in g
        assert ("GUANO", "Version") in g
        assert ("GUANO", "Version") in list(g)

    def test_get_returns_default(self):
        g = GuanoMetadata(version="1.0")
        assert g.get("WA", "Missing", default="fallback") == "fallback"

    def test_empty_key_line_skipped(self):
        with pytest.warns(UserWarning, match="empty key"):
            g = GuanoMetadata.from_bytes(b"GUANO|Version: 1.0\n: orphan value\n")
        assert len(g.fields) == 1


class TestEncodingAndFailSoft:
    def test_non_utf8_falls_back_to_latin1_with_warning(self):
        raw = "GUANO|Version: 1.0\nNote: caf\xe9".encode("latin-1")
        with pytest.warns(UnicodeWarning):
            g = GuanoMetadata.from_bytes(raw)
        assert g.note == "caf\xe9"

    def test_malformed_line_skipped_with_warning(self):
        with pytest.warns(UserWarning, match="malformed line"):
            g = GuanoMetadata.from_bytes(b"GUANO|Version: 1.0\nno colon here\nMake: X\n")
        assert g.make == "X"

    def test_bad_float_warns_and_returns_none(self):
        g = GuanoMetadata.from_bytes(b"GUANO|Version: 1.0\nLength: not-a-number\n")
        with pytest.warns(UserWarning, match="not a valid float"):
            assert g.length is None

    def test_bad_int_warns_and_returns_none(self):
        g = GuanoMetadata.from_bytes(b"GUANO|Version: 1.0\nSamplerate: lots\n")
        with pytest.warns(UserWarning, match="not a valid int"):
            assert g.samplerate is None

    def test_bad_timestamp_warns_and_returns_none(self):
        g = GuanoMetadata.from_bytes(b"GUANO|Version: 1.0\nTimestamp: yesterday\n")
        with pytest.warns(UserWarning, match="ISO 8601"):
            assert g.timestamp is None

    def test_bad_loc_position_warns_and_returns_none(self):
        g = GuanoMetadata.from_bytes(b"GUANO|Version: 1.0\nLoc Position: 1 2 3\n")
        with pytest.warns(UserWarning, match="Loc Position"):
            assert g.loc_position is None


class TestSerializationErrors:
    def test_missing_version_raises_on_write(self):
        g = GuanoMetadata()
        g.make = "X"
        with pytest.raises(ValueError, match="GUANO.Version"):
            g.to_chunk_bytes()


class TestParserIntegration:
    def test_from_parser_none_when_absent(self, make_metadata_wav):
        path = make_metadata_wav([])
        assert GuanoMetadata.from_parser(WAVParser(path)) is None

    def test_from_parser_reads_guan_chunk(self, make_metadata_wav):
        path = make_metadata_wav([("guan", CONFORMANCE)])
        g = GuanoMetadata.from_parser(WAVParser(path))
        assert g is not None
        assert g.make == "Pettersson"

    def test_write_to_parser_round_trips_through_disk(self, make_metadata_wav, tmp_path):
        path = make_metadata_wav([])
        parser = WAVParser(path)

        g = GuanoMetadata(version="1.0")
        g.make = "Open Acoustic Devices"
        g.samplerate = 192000
        g.write_to_parser(parser)

        out = tmp_path / "with_guano.wav"
        parser.write_wav(out)

        reloaded = GuanoMetadata.from_parser(WAVParser(out))
        assert reloaded is not None
        assert reloaded.make == "Open Acoustic Devices"
        assert reloaded.samplerate == 192000
