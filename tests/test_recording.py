"""Tests for riffy.metadata.recording (the unified metadata view)."""

import struct

from riffy import read_metadata
from riffy.metadata import BextMetadata, GuanoMetadata, InfoMetadata, RecordingMetadata
from riffy.wav import WAVParser


def guano_bytes() -> bytes:
    g = GuanoMetadata(version="1.0")
    g.make = "Wildlife Acoustics, Inc."
    return g.to_chunk_bytes()


def info_bytes(comment: str = "just a comment", artist: str | None = None) -> bytes:
    info = InfoMetadata()
    info.comment = comment
    if artist is not None:
        info.artist = artist
    return info.to_chunk_bytes()


def bext_bytes() -> bytes:
    return BextMetadata(version=1, originator="riffy").to_chunk_bytes()


AUDIOMOTH_COMMENT = (
    "Recorded at 19:10:00 06/04/2018 (UTC) by AudioMoth 0FE081F80FE081F0 "
    "at gain setting 2 while battery state was 4.5V"
)


class TestSourceDetection:
    def test_plain_wav_has_no_metadata(self, make_metadata_wav):
        meta = read_metadata(make_metadata_wav([]))
        assert meta.sources == ()
        assert meta.guano is None
        assert meta.info is None
        assert meta.bext is None
        assert meta.audiomoth is None

    def test_guano_only(self, make_metadata_wav):
        meta = read_metadata(make_metadata_wav([("guan", guano_bytes())]))
        assert meta.sources == ("guano",)
        assert meta.guano.make == "Wildlife Acoustics, Inc."

    def test_bext_only(self, make_metadata_wav):
        meta = read_metadata(make_metadata_wav([("bext", bext_bytes())]))
        assert meta.sources == ("bext",)
        assert meta.bext.originator == "riffy"

    def test_plain_info_is_not_audiomoth(self, make_metadata_wav):
        meta = read_metadata(make_metadata_wav([("LIST", info_bytes("hello"))]))
        assert meta.sources == ("info",)
        assert meta.info.comment == "hello"
        assert meta.audiomoth is None

    def test_audiomoth_info_reports_both_info_and_audiomoth(self, make_metadata_wav):
        # An AudioMoth file has a decoded view of the same INFO block it exposes
        # raw, so both standards are legitimately present.
        meta = read_metadata(make_metadata_wav([("LIST", info_bytes(AUDIOMOTH_COMMENT))]))
        assert meta.sources == ("info", "audiomoth")
        assert meta.info.comment == AUDIOMOTH_COMMENT
        assert meta.audiomoth.device_id == "0FE081F80FE081F0"

    def test_all_standards_present_in_stable_order(self, make_metadata_wav):
        path = make_metadata_wav(
            [
                ("guan", guano_bytes()),
                ("LIST", info_bytes(AUDIOMOTH_COMMENT)),
                ("bext", bext_bytes()),
            ]
        )
        meta = read_metadata(path)
        assert meta.sources == ("guano", "info", "bext", "audiomoth")
        assert meta.guano is not None
        assert meta.info is not None
        assert meta.bext is not None
        assert meta.audiomoth is not None


class TestNoCrossStandardMerging:
    def test_standards_kept_separate(self, make_metadata_wav):
        # GUANO and bext both carry a notion of "originator"/"make"; the unified
        # view exposes each raw without reconciling them.
        path = make_metadata_wav([("guan", guano_bytes()), ("bext", bext_bytes())])
        meta = read_metadata(path)
        assert meta.guano.make == "Wildlife Acoustics, Inc."
        assert meta.bext.originator == "riffy"


class TestConstruction:
    def test_from_parser_matches_read_metadata(self, make_metadata_wav):
        path = make_metadata_wav([("guan", guano_bytes())])
        via_parser = RecordingMetadata.from_parser(WAVParser(path))
        via_path = read_metadata(path)
        assert via_parser.sources == via_path.sources == ("guano",)

    def test_read_metadata_accepts_str_and_path(self, make_metadata_wav):
        path = make_metadata_wav([("guan", guano_bytes())])
        assert read_metadata(str(path)).sources == ("guano",)
        assert read_metadata(path).sources == ("guano",)

    def test_survives_unrelated_lists_and_chunks(self, make_metadata_wav):
        # A non-INFO LIST plus junk must not confuse detection.
        adtl = b"adtl" + struct.pack("<I", 0)
        path = make_metadata_wav([("LIST", adtl), ("guan", guano_bytes())])
        meta = read_metadata(path)
        assert meta.sources == ("guano",)
        assert meta.info is None
