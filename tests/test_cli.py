"""Tests for dump_metadata() and the ``python -m riffy`` inspector."""

import json
import struct

import pytest

from riffy import dump_metadata
from riffy.__main__ import main
from riffy.metadata import BextMetadata, GuanoMetadata, InfoMetadata
from riffy.wav import WAVParser


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

    def test_top_level_help(self, capsys):
        assert main([]) == 0
        assert main(["-h"]) == 0
        assert "Read commands:" in capsys.readouterr().out


class TestCliChunks:
    def test_chunks_table(self, make_metadata_wav, capsys):
        path = make_metadata_wav([("guan", _guano())])
        assert main(["chunks", str(path)]) == 0
        out = capsys.readouterr().out
        assert "fmt " in out and "data" in out and "guan" in out

    def test_chunks_json(self, make_metadata_wav, capsys):
        path = make_metadata_wav([("guan", _guano())])
        assert main(["chunks", str(path), "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["riff_form"] == "RIFF"
        assert "data" in data["chunks"]


class TestCliInfo:
    def test_info_text(self, make_metadata_wav, capsys):
        path = make_metadata_wav([])
        assert main(["info", str(path)]) == 0
        out = capsys.readouterr().out
        assert "Format:" in out and "Duration:" in out

    def test_info_json(self, make_metadata_wav, capsys):
        path = make_metadata_wav([])
        assert main(["info", str(path), "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["format"]["is_pcm"] is True


class TestCliExport:
    def test_export_audio(self, make_metadata_wav, tmp_path, capsys):
        path = make_metadata_wav([])
        out = tmp_path / "audio.raw"
        assert main(["export", str(path), "--audio", str(out)]) == 0
        assert out.exists() and out.stat().st_size > 0

    def test_export_chunk_by_id(self, make_metadata_wav, tmp_path):
        path = make_metadata_wav([("guan", _guano())])
        out = tmp_path / "guan.bin"
        assert main(["export", str(path), "--chunk", "guan", str(out)]) == 0
        assert out.read_bytes() == _guano()

    def test_export_requires_a_target(self, make_metadata_wav, tmp_path):
        path = make_metadata_wav([])
        with pytest.raises(SystemExit):  # mutually-exclusive group is required
            main(["export", str(path), str(tmp_path / "out.bin")])


class TestCliSet:
    def test_set_dry_run_writes_nothing(self, make_metadata_wav, capsys):
        path = make_metadata_wav([])
        before = path.read_bytes()
        assert main(["set", str(path), "--guano", "GUANO|Version=1.0"]) == 0
        assert path.read_bytes() == before  # untouched without --apply
        assert "[dry-run]" in capsys.readouterr().out

    def test_set_apply_guano(self, make_metadata_wav, capsys):
        path = make_metadata_wav([])
        rc = main(
            ["set", str(path), "--guano", "GUANO|Version=1.0", "--guano", "Make=Riffy", "--apply"]
        )
        assert rc == 0
        g = GuanoMetadata.from_parser(WAVParser(path))
        assert g is not None and g.make == "Riffy"

    def test_set_apply_info_and_remove(self, make_metadata_wav):
        path = make_metadata_wav([])
        main(["set", str(path), "--info", "IART=Field Team", "--apply"])
        assert InfoMetadata.from_parser(WAVParser(path)).artist == "Field Team"
        main(["set", str(path), "--remove-info", "IART", "--apply"])
        assert InfoMetadata.from_parser(WAVParser(path)).artist is None

    def test_set_apply_bext_with_int_coercion(self, make_metadata_wav):
        path = make_metadata_wav([])
        main(["set", str(path), "--bext", "originator=riffy", "--bext", "version=2", "--apply"])
        bext = BextMetadata.from_parser(WAVParser(path))
        assert bext is not None and bext.originator == "riffy" and bext.version == 2

    def test_set_bext_bad_int_errors(self, make_metadata_wav, capsys):
        path = make_metadata_wav([])
        assert main(["set", str(path), "--bext", "version=notanint", "--apply"]) == 1
        assert "expects an integer" in capsys.readouterr().err

    def test_set_unknown_bext_attr_errors(self, make_metadata_wav, capsys):
        path = make_metadata_wav([])
        assert main(["set", str(path), "--bext", "nope=1", "--apply"]) == 1
        assert "unknown bext attribute" in capsys.readouterr().err

    def test_set_with_no_options_errors(self, make_metadata_wav):
        path = make_metadata_wav([])
        with pytest.raises(SystemExit):  # parser.error -> nothing to do
            main(["set", str(path)])

    def test_set_backup_kept(self, make_metadata_wav):
        path = make_metadata_wav([])
        main(["set", str(path), "--guano", "GUANO|Version=1.0", "--apply", "--backup"])
        assert path.with_name(path.name + ".bak").exists()

    def test_set_force_rf64(self, make_metadata_wav):
        path = make_metadata_wav([])
        main(["set", str(path), "--guano", "GUANO|Version=1.0", "--apply", "--force-rf64"])
        assert WAVParser(path).riff_form in ("RF64", "BW64")


class TestCliChunk:
    def test_chunk_add_apply(self, make_metadata_wav, tmp_path):
        path = make_metadata_wav([])
        data_file = tmp_path / "note.bin"
        data_file.write_bytes(b"hello")
        assert main(["chunk", "add", str(path), "NOTE", str(data_file), "--apply"]) == 0
        assert WAVParser(path).get_chunk("NOTE").data == b"hello"

    def test_chunk_replace_requires_existing(self, make_metadata_wav, tmp_path, capsys):
        path = make_metadata_wav([])
        data_file = tmp_path / "note.bin"
        data_file.write_bytes(b"x")
        assert main(["chunk", "replace", str(path), "NOTE", str(data_file), "--apply"]) == 1
        assert "not found" in capsys.readouterr().err

    def test_chunk_copy(self, make_metadata_wav, tmp_path):
        src = make_metadata_wav([("guan", _guano())], name="src.wav")
        dst = make_metadata_wav([], name="dst.wav")
        assert main(["chunk", "copy", str(dst), "guan", "--from", str(src), "--apply"]) == 0
        assert WAVParser(dst).get_chunk("guan") is not None

    def test_chunk_remove(self, make_metadata_wav):
        path = make_metadata_wav([("guan", _guano())])
        assert main(["chunk", "remove", str(path), "guan", "--apply"]) == 0
        assert "guan" not in WAVParser(path).chunks

    def test_chunk_remove_dry_run_keeps_chunk(self, make_metadata_wav):
        path = make_metadata_wav([("guan", _guano())])
        assert main(["chunk", "remove", str(path), "guan"]) == 0
        assert "guan" in WAVParser(path).chunks

    def test_chunk_help(self, capsys):
        assert main(["chunk"]) == 0
        assert "Operations:" in capsys.readouterr().out

    def test_chunk_unknown_op_errors(self, capsys):
        assert main(["chunk", "frobnicate"]) == 1
        assert "unknown chunk operation" in capsys.readouterr().err
