"""write_wav keeps the file's chunk order; ds64 sizes are per chunk."""

import struct

from riffy import WAVChunk, WAVParser
from riffy.wav import _SIZE32_MAX

FMT = struct.pack("<HHIIHH", 1, 1, 8000, 16000, 2, 16)


def _riff(path, chunks):
    """Write a classic RIFF/WAVE file with exactly ``chunks`` in this order."""
    body = b"WAVE"
    for chunk_id, payload in chunks:
        body += chunk_id.encode() + struct.pack("<I", len(payload)) + payload
        if len(payload) % 2:
            body += b"\x00"
    path.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)
    return path


def _order(path):
    """Chunk IDs in on-disk order."""
    data = path.read_bytes()
    pos, ids = 12, []
    while pos + 8 <= len(data):
        cid = data[pos : pos + 4].decode()
        size = struct.unpack_from("<I", data, pos + 4)[0]
        if size == 0xFFFFFFFF:
            break  # not needed for these files
        ids.append(cid)
        pos += 8 + size + (size % 2)
    return ids


class TestChunkOrder:
    def test_metadata_ahead_of_data_stays_there(self, tmp_path):
        src = _riff(
            tmp_path / "a.wav",
            [
                ("fmt ", FMT),
                ("bext", b"b" * 10),
                ("LIST", b"INFOxxxx"),
                ("JUNK", b"\x00" * 28),
                ("data", b"\x00\x01" * 40),
                ("guan", b"GUANO|Version: 1.0\n"),
            ],
        )
        parser = WAVParser(src)
        parser.replace_chunk("LIST", b"INFOyyyyzz")
        parser.add_chunk("iXML", b"<x/>")
        parser.write_wav(tmp_path / "out.wav")
        assert _order(tmp_path / "out.wav") == [
            "fmt ",
            "bext",
            "LIST",
            "JUNK",
            "data",
            "guan",
            "iXML",
        ]

    def test_header_only_rewrite_keeps_order(self, tmp_path):
        src = _riff(
            tmp_path / "a.wav",
            [("fmt ", FMT), ("LIST", b"INFOxxxx"), ("data", b"\x00\x01" * 40)],
        )
        parser = WAVParser(src, read_audio=False)
        parser.set_chunk("guan", b"GUANO|Version: 1.0\n")
        parser.write_wav(src, overwrite=True)
        assert _order(src) == ["fmt ", "LIST", "data", "guan"]

    def test_fmt_moved_ahead_of_data(self, tmp_path):
        src = _riff(
            tmp_path / "a.wav",
            [("LIST", b"INFOxxxx"), ("data", b"\x00\x01" * 40), ("fmt ", FMT)],
        )
        WAVParser(src).write_wav(tmp_path / "out.wav")
        assert _order(tmp_path / "out.wav") == ["LIST", "fmt ", "data"]


class TestDs64PerChunk:
    def test_same_id_sentinels_resolve_to_their_own_sizes(self, tmp_path):
        # RF64 with two 'big ' chunks and a second 'data' chunk all using the
        # 0xFFFFFFFF size sentinel; their real sizes are in the ds64 table.
        data1, big1, big2, data2 = b"\x00\x01" * 40, b"A" * 10, b"B" * 20, b"\x02\x03" * 6
        table = [("big ", len(big1)), ("big ", len(big2)), ("data", len(data2))]
        ds64 = struct.pack("<QQQI", 0, len(data1), len(data1) // 2, len(table))
        for cid, size in table:
            ds64 += cid.encode() + struct.pack("<Q", size)
        body = b"WAVE" + b"ds64" + struct.pack("<I", len(ds64)) + ds64
        body += b"fmt " + struct.pack("<I", len(FMT)) + FMT
        for cid, payload in (("data", data1), ("big ", big1), ("big ", big2), ("data", data2)):
            body += cid.encode() + struct.pack("<I", 0xFFFFFFFF) + payload
        riff_size = len(body)
        body = body[:4] + body[4:12] + struct.pack("<Q", riff_size) + body[20:]
        path = tmp_path / "rf.wav"
        path.write_bytes(b"RF64" + struct.pack("<I", 0xFFFFFFFF) + body)

        parser = WAVParser(path)
        assert [c.data for c in parser.get_chunks("big ")] == [big1, big2]
        assert [c.data for c in parser.get_chunks("data")] == [data1, data2]

    def test_table_written_per_chunk(self):
        payload = WAVParser._build_ds64_payload(
            riff_size=1, data_size=2, sample_count=1, table=[("big ", 5), ("big ", 7)]
        )
        (count,) = struct.unpack_from("<I", payload, 24)
        assert count == 2
        assert [struct.unpack_from("<Q", payload, 28 + 12 * i + 4)[0] for i in range(2)] == [5, 7]


def _rf64(path, chunks, table, data_size):
    """Hand-build an RF64 file. ``chunks`` entries are (id, payload, use_sentinel)."""
    ds64 = struct.pack("<QQQI", 0, data_size, 0, len(table))
    for cid, size in table:
        ds64 += cid.encode() + struct.pack("<Q", size)
    body = b"WAVE" + b"ds64" + struct.pack("<I", len(ds64)) + ds64
    for cid, payload, sentinel in chunks:
        size_field = 0xFFFFFFFF if sentinel else len(payload)
        body += cid.encode() + struct.pack("<I", size_field) + payload
    body = body[:12] + struct.pack("<Q", len(body)) + body[20:]
    path.write_bytes(b"RF64" + struct.pack("<I", 0xFFFFFFFF) + body)
    return path


def _ds64_table(raw: bytes) -> list[tuple[bytes, int]]:
    (count,) = struct.unpack_from("<I", raw, 20 + 24)
    return [
        (raw[48 + 12 * i : 52 + 12 * i], struct.unpack_from("<Q", raw, 52 + 12 * i)[0])
        for i in range(count)
    ]


class TestReviewEdgeCases:
    def test_well_formed_round_trip_is_byte_identical(self, tmp_path):
        src = _riff(
            tmp_path / "a.wav",
            [("fmt ", FMT), ("LIST", b"INFOabc"), ("data", b"\x00\x01" * 40), ("guan", b"G")],
        )
        WAVParser(src).write_wav(tmp_path / "out.wav")
        assert (tmp_path / "out.wav").read_bytes() == src.read_bytes()

    def test_chunk_with_a_foreign_offset_counts_as_added(self, tmp_path):
        src = _riff(
            tmp_path / "a.wav",
            [("fmt ", FMT), ("data", b"\x00\x01" * 40), ("LIST", b"INFOabc")],
        )
        parser = WAVParser(src)
        parser.chunks["bext"] = [WAVChunk(id="bext", size=2, data=b"bx", offset=13)]
        parser.write_wav(tmp_path / "out.wav")
        assert _order(tmp_path / "out.wav") == ["fmt ", "data", "LIST", "bext"]

    def test_explicit_first_data_then_sentinel_data(self, tmp_path):
        data1, data2 = b"\x00\x01" * 40, b"\x02\x03" * 6
        path = _rf64(
            tmp_path / "rf.wav",
            [("fmt ", FMT, False), ("data", data1, False), ("data", data2, True)],
            table=[("data", len(data2))],
            data_size=len(data1),
        )
        assert [c.data for c in WAVParser(path).get_chunks("data")] == [data1, data2]

    def test_rf64_table_written_in_file_order(self, tmp_path):
        src = _riff(tmp_path / "a.wav", [("fmt ", FMT), ("data", b"\x00\x01" * 40)])
        parser = WAVParser(src)
        big = _SIZE32_MAX + 1
        for cid, size in (("AAAA", big), ("BBBB", big + 2), ("AAAA", big + 4), ("data", big + 6)):
            parser.add_chunk(cid, b"\x00\x00")
            parser.chunks[cid][-1].size = size  # declare >4 GB without the bytes
        parser.write_wav(tmp_path / "out.wav")
        assert _ds64_table((tmp_path / "out.wav").read_bytes()) == [
            (b"AAAA", big),
            (b"BBBB", big + 2),
            (b"AAAA", big + 4),
            (b"data", big + 6),
        ]

    def test_reserved_junk_becomes_the_ds64_chunk(self, tmp_path):
        src = _riff(
            tmp_path / "a.wav",
            [("JUNK", b"\x00" * 28), ("fmt ", FMT), ("data", b"\x00\x01" * 40)],
        )
        WAVParser(src).write_wav(tmp_path / "out.wav", force_rf64=True)
        out = WAVParser(tmp_path / "out.wav")
        assert out.is_rf64
        assert "JUNK" not in out.chunks
        assert (tmp_path / "out.wav").stat().st_size == src.stat().st_size

    def test_other_junk_is_kept(self, tmp_path):
        src = _riff(
            tmp_path / "a.wav",
            [("fmt ", FMT), ("JUNK", b"\x00" * 28), ("data", b"\x00\x01" * 40)],
        )
        WAVParser(src).write_wav(tmp_path / "out.wav", force_rf64=True)
        assert "JUNK" in WAVParser(tmp_path / "out.wav").chunks

    def test_added_chunks_keep_the_order_they_were_added(self, tmp_path):
        src = _riff(tmp_path / "a.wav", [("fmt ", FMT), ("data", b"\x00\x01" * 40)])
        parser = WAVParser(src)
        for cid in ("bbbb", "aaaa", "bbbb"):
            parser.add_chunk(cid, b"xy")
        parser.replace_chunk("aaaa", b"zz")  # keeps its place among the added
        parser.write_wav(tmp_path / "out.wav")
        assert _order(tmp_path / "out.wav") == ["fmt ", "data", "bbbb", "aaaa", "bbbb"]
