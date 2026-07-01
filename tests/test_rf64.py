"""Tests for RF64 / BW64 large-file support (v0.3.0 Phase 6).

Real >4 GB assets are unnecessary: RF64 reading is validated with small crafted
files that use the 0xFFFFFFFF size sentinel, the RF64/BW64 write path is exercised
via ``force_rf64=True``, and the 4 GB decision threshold is unit-tested directly
against :func:`_rf64_required` with large size numbers (no real data).
"""

import struct
from pathlib import Path

import pytest

from riffy.exceptions import CorruptedFileError, InvalidWAVFormatError
from riffy.wav import _SIZE32_MAX, WAVChunk, WAVParser, _rf64_required

FMT_PAYLOAD = struct.pack("<HHIIHH", 1, 1, 8000, 8000, 1, 8)


def _chunk(fourcc: bytes, payload: bytes, size_field: int | None = None) -> bytes:
    size = len(payload) if size_field is None else size_field
    out = fourcc + struct.pack("<I", size) + payload
    if len(payload) % 2:
        out += b"\x00"
    return out


def make_rf64_bytes(
    *,
    form: bytes = b"RF64",
    audio: bytes = bytes(range(16)),
    table_chunks: list[tuple[bytes, bytes]] | None = None,
    omit_ds64: bool = False,
) -> bytes:
    """Craft a small but valid RF64/BW64 file using the size sentinel.

    ``table_chunks`` are extra chunks written with a 0xFFFFFFFF sentinel and
    listed (with their real sizes) in the ds64 size table.
    """
    table_chunks = table_chunks or []
    body = _chunk(b"fmt ", FMT_PAYLOAD) + _chunk(b"data", audio, size_field=_SIZE32_MAX)
    table: dict[bytes, int] = {}
    for fourcc, payload in table_chunks:
        body += _chunk(fourcc, payload, size_field=_SIZE32_MAX)
        table[fourcc] = len(payload)

    ds64_payload = struct.pack("<QQQI", 0, len(audio), len(audio), len(table))
    for fourcc, size in table.items():
        ds64_payload += fourcc + struct.pack("<Q", size)

    riff_body = b"WAVE"
    if not omit_ds64:
        riff_body += b"ds64" + struct.pack("<I", len(ds64_payload)) + ds64_payload
    riff_body += body
    return form + struct.pack("<I", _SIZE32_MAX) + riff_body


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


class TestRf64Required:
    def test_true_when_riff_size_exceeds_32_bit(self):
        assert _rf64_required(_SIZE32_MAX + 1, [10]) is True

    def test_true_when_a_chunk_exceeds_32_bit(self):
        assert _rf64_required(100, [10, _SIZE32_MAX + 1]) is True

    def test_false_when_everything_fits(self):
        assert _rf64_required(_SIZE32_MAX, [_SIZE32_MAX, 20]) is False


class TestReadRf64:
    def test_recognizes_rf64_and_resolves_data_sentinel(self, tmp_path):
        audio = bytes(range(64))
        path = _write(tmp_path, "in.wav", make_rf64_bytes(audio=audio))
        parser = WAVParser(path)
        assert parser.is_rf64
        assert parser.riff_form == "RF64"
        assert parser.get_chunk("data").size == 64
        assert parser.audio_data == audio

    def test_recognizes_bw64(self, tmp_path):
        path = _write(tmp_path, "in.wav", make_rf64_bytes(form=b"BW64"))
        parser = WAVParser(path)
        assert parser.is_rf64
        assert parser.riff_form == "BW64"

    def test_classic_file_is_not_rf64(self, make_metadata_wav):
        parser = WAVParser(make_metadata_wav([]))
        assert parser.is_rf64 is False
        assert parser.riff_form == "RIFF"

    def test_resolves_table_sentinel_for_non_data_chunk(self, tmp_path):
        path = _write(
            tmp_path,
            "in.wav",
            make_rf64_bytes(table_chunks=[(b"big ", b"payload-bytes!!!")]),
        )
        parser = WAVParser(path)
        assert parser.get_chunk("big ").data == b"payload-bytes!!!"

    def test_missing_ds64_raises(self, tmp_path):
        path = _write(tmp_path, "in.wav", make_rf64_bytes(omit_ds64=True))
        with pytest.raises(InvalidWAVFormatError, match="ds64"):
            WAVParser(path)

    def _rf64_with_ds64(self, ds64_payload: bytes) -> bytes:
        body = _chunk(b"fmt ", FMT_PAYLOAD) + _chunk(b"data", b"\x00\x00\x00\x00")
        ds64_chunk = b"ds64" + struct.pack("<I", len(ds64_payload)) + ds64_payload
        if len(ds64_payload) % 2:  # even-byte padding, as required for any chunk
            ds64_chunk += b"\x00"
        return b"RF64" + struct.pack("<I", _SIZE32_MAX) + b"WAVE" + ds64_chunk + body

    def test_undersized_ds64_raises(self, tmp_path):
        # ds64 payload shorter than the mandatory 28-byte header.
        path = _write(tmp_path, "in.wav", self._rf64_with_ds64(b"\x00" * 20))
        with pytest.raises(CorruptedFileError, match="undersized"):
            WAVParser(path)

    def test_truncated_ds64_table_raises(self, tmp_path):
        # Declares one table entry but provides no entry bytes.
        ds64 = struct.pack("<QQQI", 0, 4, 4, 1)
        path = _write(tmp_path, "in.wav", self._rf64_with_ds64(ds64))
        with pytest.raises(CorruptedFileError, match="Truncated 'ds64' size table"):
            WAVParser(path)

    def test_odd_length_ds64_is_padded(self, tmp_path):
        # A non-standard odd-length ds64 (28 + 1 junk byte) must skip its pad
        # byte so the following chunks still parse.
        ds64 = struct.pack("<QQQI", 0, 4, 4, 0) + b"\x00"
        assert len(ds64) % 2 == 1
        path = _write(tmp_path, "in.wav", self._rf64_with_ds64(ds64))
        parser = WAVParser(path)
        assert parser.is_rf64
        assert parser.get_chunk("data").size == 4

    def test_unknown_sentinel_chunk_raises(self, tmp_path):
        # A chunk marked with the sentinel but absent from the ds64 table.
        body = (
            _chunk(b"fmt ", FMT_PAYLOAD)
            + _chunk(b"data", b"\x00\x00\x00\x00", size_field=len(b"\x00\x00\x00\x00"))
            + _chunk(b"orph", b"data", size_field=_SIZE32_MAX)
        )
        ds64 = struct.pack("<QQQI", 0, 4, 4, 0)  # empty table
        raw = (
            b"RF64"
            + struct.pack("<I", _SIZE32_MAX)
            + b"WAVE"
            + b"ds64"
            + struct.pack("<I", len(ds64))
            + ds64
            + body
        )
        path = _write(tmp_path, "in.wav", raw)
        with pytest.raises(CorruptedFileError, match="no ds64 table entry"):
            WAVParser(path)


class TestWriteRf64:
    def test_small_file_writes_classic_by_default(self, make_metadata_wav, tmp_path):
        parser = WAVParser(make_metadata_wav([]))
        out = tmp_path / "out.wav"
        parser.write_wav(out)
        assert out.read_bytes()[:4] == b"RIFF"

    def test_force_rf64_emits_rf64_form(self, make_metadata_wav, tmp_path):
        parser = WAVParser(make_metadata_wav([]))
        out = tmp_path / "out.wav"
        parser.write_wav(out, force_rf64=True)
        raw = out.read_bytes()
        assert raw[:4] == b"RF64"
        assert struct.unpack("<I", raw[4:8])[0] == _SIZE32_MAX  # size sentinel
        assert raw[12:16] == b"ds64"  # ds64 is the first chunk

    def test_forced_rf64_round_trips(self, tmp_path):
        audio = bytes(range(200))
        src = _write(tmp_path, "src.wav", make_rf64_bytes(audio=audio))
        parser = WAVParser(src)

        out = tmp_path / "out.wav"
        parser.write_wav(out, force_rf64=True)

        reparsed = WAVParser(out)
        assert reparsed.is_rf64
        assert reparsed.audio_data == audio
        assert reparsed.format_info.sample_rate == 8000

    def test_bw64_form_preserved_on_forced_write(self, tmp_path):
        src = _write(tmp_path, "src.wav", make_rf64_bytes(form=b"BW64"))
        parser = WAVParser(src)
        out = tmp_path / "out.wav"
        parser.write_wav(out, force_rf64=True)
        assert out.read_bytes()[:4] == b"BW64"

    def test_small_rf64_source_downgrades_to_classic(self, tmp_path):
        # Reading RF64 then writing (auto) yields classic WAV when sizes fit,
        # preserving the audio — the intended size-gated behavior.
        audio = bytes(range(32))
        src = _write(tmp_path, "src.wav", make_rf64_bytes(audio=audio))
        parser = WAVParser(src)

        out = tmp_path / "out.wav"
        parser.write_wav(out)
        assert out.read_bytes()[:4] == b"RIFF"
        assert WAVParser(out).audio_data == audio

    def test_odd_sized_chunk_padded_in_rf64_output(self, make_metadata_wav, tmp_path):
        # An odd-length chunk written in RF64 form must be padded to even.
        parser = WAVParser(make_metadata_wav([("guan", b"odd")]))  # 3-byte payload
        out = tmp_path / "out.wav"
        parser.write_wav(out, force_rf64=True)
        reparsed = WAVParser(out)
        assert reparsed.is_rf64
        assert reparsed.get_chunk_bytes("guan") == b"odd"

    def test_oversized_non_data_chunk_goes_in_ds64_table(self, make_metadata_wav, tmp_path):
        # Inject a chunk whose declared size exceeds 4 GB (without real data) to
        # exercise the write-side ds64 table classification and size sentinel.
        parser = WAVParser(make_metadata_wav([]))
        parser.chunks["big "] = [
            WAVChunk(id="big ", size=_SIZE32_MAX + 1, data=b"\x00\x00", offset=0)
        ]

        out = tmp_path / "out.wav"
        parser.write_wav(out)  # need_rf64 is forced by the >4 GB chunk size
        raw = out.read_bytes()

        assert raw[:4] == b"RF64"
        (ds64_size,) = struct.unpack("<I", raw[16:20])
        ds64 = raw[20 : 20 + ds64_size]
        (table_len,) = struct.unpack("<I", ds64[24:28])
        assert table_len == 1
        assert ds64[28:32] == b"big "
        assert struct.unpack("<Q", ds64[32:40])[0] == _SIZE32_MAX + 1

    def test_ds64_table_emitted_for_oversized_non_data_chunk(self, tmp_path, monkeypatch):
        # Without a real >4 GB payload, assert the ds64 payload builder emits a
        # table entry for a chunk whose declared size exceeds 32 bits.
        payload = WAVParser._build_ds64_payload(
            riff_size=10, data_size=20, sample_count=5, table={"big ": _SIZE32_MAX + 1}
        )
        riff_size, data_size, sample_count, table_len = struct.unpack("<QQQI", payload[:28])
        assert (data_size, sample_count, table_len) == (20, 5, 1)
        entry_id = payload[28:32]
        (entry_size,) = struct.unpack("<Q", payload[32:40])
        assert entry_id == b"big "
        assert entry_size == _SIZE32_MAX + 1
