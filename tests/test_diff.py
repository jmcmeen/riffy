"""Tests for riffy.diff (per-chunk and per-metadata-field diffing)."""

import struct

from riffy import BextMetadata, GuanoMetadata, InfoMetadata, WAVParser, diff
from riffy.diff import WavDiff


def _guano(**fields) -> bytes:
    g = GuanoMetadata(version="1.0")
    for key, value in fields.items():
        g.set("", key, value)
    return g.to_chunk_bytes()


def _build(make_metadata_wav, chunks, name="f.wav"):
    return make_metadata_wav(chunks, name=name)


class TestChunkDiff:
    def test_identical_files(self, make_metadata_wav):
        a = _build(make_metadata_wav, [("guan", _guano(Make="X"))], "a.wav")
        b = _build(make_metadata_wav, [("guan", _guano(Make="X"))], "b.wav")
        d = diff(a, b)
        assert d.identical
        assert d.changed_chunks == []
        assert d.fields == []

    def test_changed_chunk(self, make_metadata_wav):
        a = _build(make_metadata_wav, [("guan", _guano(Make="A"))], "a.wav")
        b = _build(make_metadata_wav, [("guan", _guano(Make="B"))], "b.wav")
        d = diff(a, b)
        assert not d.identical
        changed = d.changed_chunks
        assert [c.chunk_id for c in changed] == ["guan"]
        assert changed[0].status == "changed"

    def test_added_and_removed_chunk(self, make_metadata_wav):
        a = _build(make_metadata_wav, [], "a.wav")  # no guan
        b = _build(make_metadata_wav, [("guan", _guano(Make="X"))], "b.wav")
        added = {(c.chunk_id, c.status) for c in diff(a, b).chunks}
        removed = {(c.chunk_id, c.status) for c in diff(b, a).chunks}
        assert ("guan", "added") in added
        assert ("guan", "removed") in removed

    def test_unchanged_hidden_by_default_shown_with_flag(self, make_metadata_wav):
        a = _build(make_metadata_wav, [("guan", _guano(Make="X"))], "a.wav")
        b = _build(make_metadata_wav, [("guan", _guano(Make="X"))], "b.wav")
        assert diff(a, b).chunks == []
        statuses = {c.status for c in diff(a, b, include_unchanged=True).chunks}
        assert statuses == {"unchanged"}

    def test_multiple_occurrences_compared_by_index(self, make_metadata_wav):
        a = _build(make_metadata_wav, [("LIST", b"INFOaaaa"), ("LIST", b"INFObbbb")], "a.wav")
        b = _build(make_metadata_wav, [("LIST", b"INFOaaaa"), ("LIST", b"INFOcccc")], "b.wav")
        d = diff(a, b)
        list_deltas = [c for c in d.chunks if c.chunk_id == "LIST"]
        assert len(list_deltas) == 1  # only the second occurrence differs
        assert list_deltas[0].index == 1
        assert list_deltas[0].status == "changed"

    def test_chunk_reordering_is_not_a_change(self, make_metadata_wav, tmp_path):
        # Writing normalizes chunk order; a re-written copy must still diff clean
        # against the original for chunks whose bytes are unchanged.
        src = _build(
            make_metadata_wav, [("guan", _guano(Make="X")), ("junk", b"padding!")], "s.wav"
        )
        parser = WAVParser(src)
        out = tmp_path / "rewritten.wav"
        parser.write_wav(out)
        d = diff(src, out)
        assert d.changed_chunks == []


class TestMetadataDiff:
    def test_guano_field_change(self, make_metadata_wav):
        a = _build(make_metadata_wav, [("guan", _guano(**{"Loc Position": "35.9 -83.9"}))], "a.wav")
        b = _build(make_metadata_wav, [("guan", _guano(**{"Loc Position": "36.3 -82.3"}))], "b.wav")
        fields = diff(a, b).fields
        assert len(fields) == 1
        f = fields[0]
        assert (f.standard, f.key, f.status) == ("guano", "Loc Position", "changed")
        assert (f.old, f.new) == ("35.9 -83.9", "36.3 -82.3")

    def test_guano_added_and_removed_fields(self, make_metadata_wav):
        a = _build(make_metadata_wav, [("guan", _guano(Make="X"))], "a.wav")
        b = _build(make_metadata_wav, [("guan", _guano(Make="X", Model="Y"))], "b.wav")
        d = diff(a, b)
        assert any(f.key == "Model" and f.status == "added" and f.new == "Y" for f in d.fields)
        assert any(f.key == "Model" and f.status == "removed" for f in diff(b, a).fields)

    def test_info_tag_change(self, make_metadata_wav):
        def info(comment):
            i = InfoMetadata()
            i.comment = comment
            return i.to_chunk_bytes()

        a = _build(make_metadata_wav, [("LIST", info("old"))], "a.wav")
        b = _build(make_metadata_wav, [("LIST", info("new"))], "b.wav")
        fields = [f for f in diff(a, b).fields if f.standard == "info"]
        assert fields == fields  # sanity
        assert any(f.key == "ICMT" and f.old == "old" and f.new == "new" for f in fields)

    def test_bext_field_change(self, make_metadata_wav):
        def bext(**kw):
            return BextMetadata(**kw).to_chunk_bytes()

        a = _build(make_metadata_wav, [("bext", bext(originator="A"))], "a.wav")
        b = _build(make_metadata_wav, [("bext", bext(originator="B"))], "b.wav")
        fields = [f for f in diff(a, b).fields if f.standard == "bext"]
        assert any(f.key == "originator" and f.old == "A" and f.new == "B" for f in fields)

    def test_bext_umid_change(self, make_metadata_wav):
        def bext(umid):
            return BextMetadata(version=1, umid=umid).to_chunk_bytes()

        a = _build(make_metadata_wav, [("bext", bext(b"\x01" * 64))], "a.wav")
        b = _build(make_metadata_wav, [("bext", bext(b"\x02" * 64))], "b.wav")
        fields = [f for f in diff(a, b).fields if f.key == "umid"]
        assert fields and fields[0].old == "01" * 64 and fields[0].new == "02" * 64

    def test_no_metadata_no_field_deltas(self, make_metadata_wav):
        a = _build(make_metadata_wav, [], "a.wav")
        b = _build(make_metadata_wav, [], "b.wav")
        assert diff(a, b).fields == []


class TestApi:
    def test_accepts_paths_and_parsers(self, make_metadata_wav):
        a = _build(make_metadata_wav, [("guan", _guano(Make="X"))], "a.wav")
        b = _build(make_metadata_wav, [("guan", _guano(Make="X"))], "b.wav")
        from_paths = diff(a, b)
        from_parsers = diff(WAVParser(a), WAVParser(b))
        assert isinstance(from_paths, WavDiff)
        assert from_paths.identical == from_parsers.identical

    def test_form_recorded(self, make_metadata_wav):
        a = _build(make_metadata_wav, [], "a.wav")
        d = diff(a, a)
        assert d.form_a == d.form_b == "RIFF"


class TestCliDiff:
    def _pair(self, make_metadata_wav):
        a = _build(make_metadata_wav, [("guan", _guano(**{"Loc Position": "35.9 -83.9"}))], "a.wav")
        b = _build(make_metadata_wav, [("guan", _guano(**{"Loc Position": "36.3 -82.3"}))], "b.wav")
        return a, b

    def test_diff_human(self, make_metadata_wav, capsys):
        from riffy.__main__ import main

        a, b = self._pair(make_metadata_wav)
        assert main(["diff", str(a), str(b)]) == 0
        out = capsys.readouterr().out
        assert "Loc Position" in out
        assert "Files differ." in out

    def test_diff_identical(self, make_metadata_wav, capsys):
        from riffy.__main__ import main

        a = _build(make_metadata_wav, [("guan", _guano(Make="X"))], "a.wav")
        assert main(["diff", str(a), str(a)]) == 0
        assert "Files are identical." in capsys.readouterr().out

    def test_diff_json(self, make_metadata_wav, capsys):
        import json

        from riffy.__main__ import main

        a, b = self._pair(make_metadata_wav)
        assert main(["diff", "--json", str(a), str(b)]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["form_a"] == "RIFF"
        assert any(f["key"] == "Loc Position" for f in data["fields"])

    def test_diff_all_shows_unchanged(self, make_metadata_wav, capsys):
        from riffy.__main__ import main

        a = _build(make_metadata_wav, [("guan", _guano(Make="X"))], "a.wav")
        assert main(["diff", "--all", str(a), str(a)]) == 0
        out = capsys.readouterr().out
        assert "unchanged" in out

    def test_diff_reports_form_change(self, make_metadata_wav, tmp_path, capsys):
        from riffy.__main__ import main

        classic = _build(make_metadata_wav, [("guan", _guano(Make="X"))], "classic.wav")
        rf64 = tmp_path / "large.wav"
        WAVParser(classic).write_wav(rf64, force_rf64=True)
        assert main(["diff", str(classic), str(rf64)]) == 0
        out = capsys.readouterr().out
        assert "RIFF form changed: RIFF -> RF64" in out

    def test_diff_missing_file_errors(self, tmp_path, capsys):
        from riffy.__main__ import main

        assert main(["diff", str(tmp_path / "no.wav"), str(tmp_path / "no.wav")]) == 1
        assert capsys.readouterr().err.startswith("riffy:")

    def test_inspect_still_default(self, make_metadata_wav, capsys):
        # Backward compatibility: no subcommand -> inspect.
        from riffy.__main__ import main

        a = _build(make_metadata_wav, [("guan", _guano(Make="X"))], "a.wav")
        assert main([str(a)]) == 0
        assert "RIFF form:" in capsys.readouterr().out

    def test_inspect_subcommand_explicit(self, make_metadata_wav, capsys):
        from riffy.__main__ import main

        a = _build(make_metadata_wav, [("guan", _guano(Make="X"))], "a.wav")
        assert main(["inspect", str(a)]) == 0
        assert "RIFF form:" in capsys.readouterr().out

    def test_top_level_help_lists_diff(self, capsys):
        from riffy.__main__ import main

        assert main(["--help"]) == 0
        out = capsys.readouterr().out
        assert "diff" in out and "inspect" in out

    def test_no_args_shows_help(self, capsys):
        from riffy.__main__ import main

        assert main([]) == 0
        assert "diff" in capsys.readouterr().out


def test_added_chunk_size_fields(make_metadata_wav):
    # Cover size_a/size_b for added chunks (None on the absent side).
    a = _build(make_metadata_wav, [], "a.wav")
    payload = b"INFO" + struct.pack("<I", 0)
    b = _build(make_metadata_wav, [("LIST", payload)], "b.wav")
    (delta,) = [c for c in diff(a, b).chunks if c.chunk_id == "LIST"]
    assert delta.size_a is None
    assert delta.size_b == len(payload)
