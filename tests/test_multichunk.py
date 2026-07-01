"""Tests for the multi-chunk-per-ID chunk store (v0.3.0 Option B).

These cover the breaking change from ``chunks: dict[str, WAVChunk]`` to
``chunks: dict[str, list[WAVChunk]]``: files with duplicate top-level chunk IDs
must preserve every occurrence in file order, the single-occurrence convenience
accessors must behave, and classic WAV output must stay byte-for-byte identical.
"""

import struct
from pathlib import Path

from riffy.wav import WAVParser


def _minimal_pcm_bytes(extra_chunks: list[tuple[bytes, bytes]] = ()) -> bytes:
    """Build raw bytes for a valid PCM WAV, with optional extra chunks appended.

    ``extra_chunks`` is a list of ``(fourcc, payload)`` tuples written verbatim
    after the mandatory ``fmt ``/``data`` chunks, each padded to even length.
    """
    fmt_payload = struct.pack("<HHIIHH", 1, 1, 8000, 8000, 1, 8)
    audio = b"\x00\x01\x02\x03"  # 4 bytes, even

    body = b""

    def _chunk(fourcc: bytes, payload: bytes) -> bytes:
        out = fourcc + struct.pack("<I", len(payload)) + payload
        if len(payload) % 2:
            out += b"\x00"
        return out

    body += _chunk(b"fmt ", fmt_payload)
    body += _chunk(b"data", audio)
    for fourcc, payload in extra_chunks:
        body += _chunk(fourcc, payload)

    riff_payload = b"WAVE" + body
    return b"RIFF" + struct.pack("<I", len(riff_payload)) + riff_payload


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


class TestDuplicateChunkIDs:
    """Duplicate top-level IDs must all be preserved in file order."""

    def test_duplicate_list_chunks_preserved(self, tmp_path):
        src = _write(
            tmp_path,
            "dup.wav",
            _minimal_pcm_bytes([(b"LIST", b"first-list"), (b"LIST", b"secondlist")]),
        )
        parser = WAVParser(src)

        lists = parser.get_chunks("LIST")
        assert len(lists) == 2
        assert lists[0].data == b"first-list"
        assert lists[1].data == b"secondlist"

    def test_write_preserves_every_occurrence_in_order(self, tmp_path):
        src = _write(
            tmp_path,
            "dup.wav",
            _minimal_pcm_bytes([(b"LIST", b"first-list"), (b"LIST", b"secondlist")]),
        )
        parser = WAVParser(src)

        out = tmp_path / "roundtrip.wav"
        parser.write_wav(out)

        reparsed = WAVParser(out)
        lists = reparsed.get_chunks("LIST")
        assert [c.data for c in lists] == [b"first-list", b"secondlist"]

    def test_get_info_reports_all_sizes(self, tmp_path):
        src = _write(
            tmp_path,
            "dup.wav",
            _minimal_pcm_bytes([(b"LIST", b"first-list"), (b"LIST", b"secondlist")]),
        )
        info = WAVParser(src).get_info()
        assert info["chunks"]["LIST"] == [len(b"first-list"), len(b"secondlist")]


class TestConvenienceAccessors:
    """get_chunk / get_chunks / get_chunk_bytes behavior."""

    def test_get_chunk_returns_first_occurrence(self, tmp_path):
        src = _write(
            tmp_path,
            "dup.wav",
            _minimal_pcm_bytes([(b"LIST", b"aaa"), (b"LIST", b"bbb")]),
        )
        parser = WAVParser(src)
        assert parser.get_chunk("LIST").data == b"aaa"
        assert parser.get_chunk_bytes("LIST") == b"aaa"

    def test_accessors_return_empty_or_none_when_absent(self, tmp_path):
        src = _write(tmp_path, "plain.wav", _minimal_pcm_bytes())
        parser = WAVParser(src)
        assert parser.get_chunks("NOPE") == []
        assert parser.get_chunk("NOPE") is None
        assert parser.get_chunk_bytes("NOPE") is None


class TestByteIdenticalRoundTrip:
    """Classic WAV output must stay byte-for-byte identical (plan §6/§8)."""

    def test_canonical_file_round_trips_byte_identical(self, valid_pcm_wav, tmp_path):
        # conftest writes canonical fmt->data order with even-sized chunks, so a
        # read/write cycle must reproduce the input bytes exactly.
        original = Path(valid_pcm_wav["filepath"]).read_bytes()

        out = tmp_path / "identical.wav"
        parser = WAVParser(valid_pcm_wav["filepath"])
        parser.write_wav(out)

        assert out.read_bytes() == original
