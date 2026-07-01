"""Tests for the internal CLI helpers (FIELD=VALUE parsing, atomic write)."""

import pytest

from riffy._cli_util import atomic_write, parse_guano_field, parse_guano_key, split_assignment
from riffy.wav import WAVParser


class TestSplitAssignment:
    def test_basic(self):
        assert split_assignment("IART=Field Team") == ("IART", "Field Team")

    def test_strips_whitespace(self):
        assert split_assignment("  key = value ") == ("key", "value")

    def test_value_may_contain_equals(self):
        assert split_assignment("k=a=b") == ("k", "a=b")

    def test_missing_equals_raises(self):
        with pytest.raises(ValueError, match="expected FIELD=VALUE"):
            split_assignment("noequals")


class TestParseGuanoField:
    def test_base_namespace(self):
        assert parse_guano_field("Make=Riffy") == ("", "Make", "Riffy")

    def test_namespaced(self):
        assert parse_guano_field("WA|Song Meter|Prefix=SITE7") == (
            "WA",
            "Song Meter|Prefix",
            "SITE7",
        )

    def test_value_with_spaces(self):
        assert parse_guano_field("Loc Position=36.3 -82.3") == ("", "Loc Position", "36.3 -82.3")


class TestParseGuanoKey:
    def test_base_namespace(self):
        assert parse_guano_key("Make") == ("", "Make")

    def test_namespaced(self):
        assert parse_guano_key("WA|Prefix") == ("WA", "Prefix")


class TestAtomicWrite:
    def test_writes_in_place(self, make_metadata_wav):
        path = make_metadata_wav([])
        parser = WAVParser(path)
        parser.add_chunk("guan", b"GUANO|Version: 1.0 ")
        atomic_write(parser, path)
        assert "guan" in WAVParser(path).chunks
        assert not path.with_name(path.name + ".riffytmp").exists()  # temp cleaned up

    def test_backup_kept(self, make_metadata_wav):
        path = make_metadata_wav([])
        original = path.read_bytes()
        parser = WAVParser(path)
        parser.add_chunk("guan", b"GUANO|Version: 1.0 ")
        atomic_write(parser, path, backup=True)
        assert path.with_name(path.name + ".bak").read_bytes() == original

    def test_force_rf64(self, make_metadata_wav):
        path = make_metadata_wav([])
        parser = WAVParser(path)
        atomic_write(parser, path, force_rf64=True)
        assert WAVParser(path).riff_form in ("RF64", "BW64")
