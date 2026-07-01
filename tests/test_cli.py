"""Tests for dump_metadata() and the ``python -m riffy`` inspector."""

import json
import struct

from riffy import dump_metadata
from riffy.__main__ import main
from riffy.metadata import BextMetadata, GuanoMetadata, InfoMetadata


def _guano() -> bytes:
    g = GuanoMetadata(version="1.0")
    g.make = "Wildlife Acoustics, Inc."
    return g.to_chunk_bytes()


def _info_audiomoth() -> bytes:
    info = InfoMetadata()
    info.comment = (
        "Recorded at 19:10:00 06/04/2018 (UTC) by AudioMoth 0FE081F80FE081F0 "
        "at gain setting 2 while battery state was 4.5V"
    )
    return info.to_chunk_bytes()


def _bext() -> bytes:
    return BextMetadata(version=2, originator="riffy", umid=b"\xaa" * 64).to_chunk_bytes()


class TestDumpMetadata:
    def test_structure_and_sources(self, make_metadata_wav):
        path = make_metadata_wav(
            [("guan", _guano()), ("LIST", _info_audiomoth()), ("bext", _bext())]
        )
        data = dump_metadata(path)
        assert set(data["sources"]) == {"guano", "info", "bext", "audiomoth"}
        assert data["riff_form"] == "RIFF"
        assert data["guano"]["Make"] == "Wildlife Acoustics, Inc."
        assert data["audiomoth"]["device_id"] == "0FE081F80FE081F0"

    def test_output_is_json_serializable(self, make_metadata_wav):
        # bext umid (bytes) -> hex, audiomoth timestamp (datetime) -> ISO string.
        path = make_metadata_wav([("LIST", _info_audiomoth()), ("bext", _bext())])
        data = dump_metadata(path)
        encoded = json.dumps(data)  # must not raise
        roundtrip = json.loads(encoded)
        assert roundtrip["bext"]["umid"] == "aa" * 64
        assert roundtrip["audiomoth"]["timestamp"].startswith("2018-04-06T19:10:00")

    def test_plain_file_has_empty_sources(self, make_metadata_wav):
        data = dump_metadata(make_metadata_wav([]))
        assert data["sources"] == []
        assert data["guano"] is None
        assert data["ixml"] is None

    def test_ixml_included(self, make_metadata_wav):
        path = make_metadata_wav([("iXML", b"<BWFXML><PROJECT>P</PROJECT></BWFXML>")])
        data = dump_metadata(path)
        assert "ixml" in data["sources"]
        assert data["ixml"]["BWFXML"]["PROJECT"] == "P"


class TestCli:
    def test_human_output(self, make_metadata_wav, capsys):
        path = make_metadata_wav([("guan", _guano())])
        assert main([str(path)]) == 0
        out = capsys.readouterr().out
        assert "RIFF form: RIFF" in out
        assert "[guano]" in out
        assert "Wildlife Acoustics" in out

    def test_json_output(self, make_metadata_wav, capsys):
        path = make_metadata_wav([("guan", _guano())])
        assert main(["--json", str(path)]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["sources"] == ["guano"]

    def test_no_metadata_reports_none(self, make_metadata_wav, capsys):
        path = make_metadata_wav([])
        assert main([str(path)]) == 0
        assert "(none detected)" in capsys.readouterr().out

    def test_human_output_renders_nested_ixml(self, make_metadata_wav, capsys):
        path = make_metadata_wav([("iXML", b"<BWFXML><PROJECT>P</PROJECT></BWFXML>")])
        assert main([str(path)]) == 0
        out = capsys.readouterr().out
        assert "[ixml]" in out
        assert "PROJECT" in out  # nested dict rendered as JSON

    def test_empty_info_section_is_skipped(self, make_metadata_wav, capsys):
        # An INFO list with no subchunks: 'info' is detected but has no fields.
        path = make_metadata_wav([("LIST", b"INFO")])
        assert main([str(path)]) == 0
        out = capsys.readouterr().out
        assert "info" in out  # listed as a source
        assert "[info]" not in out  # but its (empty) section body is skipped

    def test_missing_file_returns_error(self, tmp_path, capsys):
        assert main([str(tmp_path / "nope.wav")]) == 1
        assert "riffy:" in capsys.readouterr().err

    def test_invalid_file_returns_error(self, tmp_path, capsys):
        bad = tmp_path / "bad.wav"
        bad.write_bytes(b"NOTAWAVE" + struct.pack("<I", 0))
        assert main([str(bad)]) == 1
        assert capsys.readouterr().err.startswith("riffy:")
