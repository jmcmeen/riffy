"""Header-only parsing (read_audio=False) and streamed payloads."""

import struct
import tracemalloc

import pytest

from riffy import (
    CorruptedFileError,
    GuanoMetadata,
    InvalidWAVFormatError,
    UnsupportedFormatError,
    WAVError,
    WAVParser,
    diff,
    read_metadata,
)

from .conftest import create_wav_file


def _sparse_wav(path, data_bytes: int) -> None:
    """A PCM WAV whose data chunk is a sparse hole of ``data_bytes`` (no RAM to build)."""
    fmt = struct.pack("<HHIIHH", 1, 2, 48000, 192000, 4, 16)
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 4 + 8 + len(fmt) + 8 + data_bytes) + b"WAVE")
        f.write(b"fmt " + struct.pack("<I", len(fmt)) + fmt)
        f.write(b"data" + struct.pack("<I", data_bytes))
        f.seek(data_bytes - 1, 1)
        f.write(b"\x01")


def _guano_bytes(make: str = "Wildlife Acoustics") -> bytes:
    g = GuanoMetadata(version="1.0")
    g.make = make
    return g.to_chunk_bytes()


class TestReading:
    def test_audio_left_on_disk(self, valid_pcm_wav):
        full = WAVParser(valid_pcm_wav["filepath"])
        lazy = WAVParser(valid_pcm_wav["filepath"], read_audio=False)
        assert lazy.audio_data is None
        assert lazy.get_chunk("data").data is None
        assert lazy.audio_size == len(full.audio_data)
        assert lazy.get_info()["sample_count"] == full.get_info()["sample_count"]
        assert lazy.get_info()["duration_seconds"] == full.get_info()["duration_seconds"]
        assert lazy.get_chunk_bytes("data") == full.audio_data  # read on demand

    def test_any_audio_format_for_metadata(self, non_pcm_wav_valid):
        parser = WAVParser(non_pcm_wav_valid["filepath"], read_audio=False)
        assert parser.format_info.describe() == "mu-law"
        assert read_metadata(non_pcm_wav_valid["filepath"]).sources == ()

    def test_truncated_data_chunk(self, temp_wav_dir):
        wav = create_wav_file(temp_wav_dir / "t.wav", num_samples=1000)
        path = wav["filepath"]
        path.write_bytes(path.read_bytes()[:-100])
        with pytest.raises(CorruptedFileError, match="data"):
            WAVParser(path, read_audio=False)

    def test_parsing_does_not_read_the_audio(self, tmp_path):
        path = tmp_path / "big.wav"
        _sparse_wav(path, 64 * 1024 * 1024)
        tracemalloc.start()
        parser = WAVParser(path, read_audio=False)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert parser.audio_size == 64 * 1024 * 1024
        assert peak < 1024 * 1024


class TestWriting:
    def test_streamed_write_matches_full_write(self, valid_pcm_wav, tmp_path):
        full = WAVParser(valid_pcm_wav["filepath"])
        lazy = WAVParser(valid_pcm_wav["filepath"], read_audio=False)
        for parser in (full, lazy):
            parser.set_chunk("guan", _guano_bytes())
        full.write_wav(tmp_path / "full.wav")
        lazy.write_wav(tmp_path / "lazy.wav")
        assert (tmp_path / "lazy.wav").read_bytes() == (tmp_path / "full.wav").read_bytes()

    def test_in_place_overwrite(self, valid_pcm_wav):
        path = valid_pcm_wav["filepath"]
        audio = WAVParser(path).audio_data
        parser = WAVParser(path, read_audio=False)
        parser.set_chunk("guan", _guano_bytes("Titley"))
        parser.write_wav(path, overwrite=True)

        assert not path.with_name(path.name + ".riffytmp").exists()
        assert GuanoMetadata.from_parser(WAVParser(path)).make == "Titley"
        assert WAVParser(path).audio_data == audio
        # The parser re-read the rewritten file, so its offsets are valid.
        assert parser.get_chunk_bytes("data") == audio

    def test_streamed_write_memory(self, tmp_path):
        src = tmp_path / "big.wav"
        _sparse_wav(src, 64 * 1024 * 1024)
        parser = WAVParser(src, read_audio=False)
        parser.set_chunk("guan", _guano_bytes())
        tracemalloc.start()
        parser.write_wav(tmp_path / "out.wav")
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert peak < 4 * 1024 * 1024
        assert WAVParser(tmp_path / "out.wav", read_audio=False).audio_size == 64 * 1024 * 1024

    def test_rf64_round_trip(self, valid_pcm_wav, tmp_path):
        rf64 = tmp_path / "rf.wav"
        WAVParser(valid_pcm_wav["filepath"]).write_wav(rf64, force_rf64=True)
        parser = WAVParser(rf64, read_audio=False)
        assert parser.is_rf64
        parser.set_chunk("guan", _guano_bytes())
        parser.write_wav(tmp_path / "out.wav", force_rf64=True)
        again = WAVParser(tmp_path / "out.wav")
        assert again.is_rf64
        assert again.audio_data == WAVParser(valid_pcm_wav["filepath"]).audio_data

    def test_export_streams(self, valid_pcm_wav, tmp_path):
        lazy = WAVParser(valid_pcm_wav["filepath"], read_audio=False)
        assert lazy.export_audio_data(tmp_path / "a.bin") == lazy.audio_size
        assert (tmp_path / "a.bin").read_bytes() == WAVParser(valid_pcm_wav["filepath"]).audio_data

    def test_copy_chunk_from_header_only_source(self, valid_pcm_wav, valid_8bit_wav):
        target = WAVParser(valid_8bit_wav["filepath"])
        source = WAVParser(valid_pcm_wav["filepath"], read_audio=False)
        target.copy_chunk_from_parser("data", source)
        assert target.audio_data == WAVParser(valid_pcm_wav["filepath"]).audio_data


class TestDiff:
    def test_audio_compared_by_streaming(self, temp_wav_dir):
        a = create_wav_file(temp_wav_dir / "a.wav", num_samples=2000)["filepath"]
        b = create_wav_file(temp_wav_dir / "b.wav", num_samples=2000)["filepath"]
        assert diff(a, b).identical
        raw = bytearray(b.read_bytes())
        raw[-1] ^= 0xFF
        b.write_bytes(bytes(raw))
        assert [c.chunk_id for c in diff(a, b).changed_chunks] == ["data"]


class TestReviewEdgeCases:
    def test_structural_checks_still_apply(self, temp_wav_dir):
        wav = create_wav_file(temp_wav_dir / "x.wav", channels=0)
        with pytest.raises(InvalidWAVFormatError, match="channels"):
            WAVParser(wav["filepath"], read_audio=False)

    def test_compressed_audio_has_unknown_sample_count(self, non_pcm_wav_valid):
        info = WAVParser(non_pcm_wav_valid["filepath"], read_audio=False).get_info()
        assert info["sample_count"] == 0
        assert info["audio_data_size"] > 0

    def test_unsupported_format_wins_over_missing_data(self, temp_wav_dir):
        wav = create_wav_file(
            temp_wav_dir / "x.wav",
            audio_format=7,
            extra_fmt_data=struct.pack("<H", 0),
            include_data_chunk=False,
        )
        with pytest.raises(UnsupportedFormatError):
            WAVParser(wav["filepath"])

    def test_changed_source_is_not_streamed(self, valid_pcm_wav, tmp_path):
        path = valid_pcm_wav["filepath"]
        parser = WAVParser(path, read_audio=False)
        with open(path, "ab") as f:  # someone else rewrites the file
            f.write(b"JUNK\x00\x00\x00\x00")
        with pytest.raises(WAVError, match="changed since it was parsed"):
            parser.get_chunk_bytes("data")

    def test_failed_write_leaves_target_and_no_temp(self, valid_pcm_wav, tmp_path):
        out = tmp_path / "out.wav"
        out.write_bytes(b"previous contents")
        parser = WAVParser(valid_pcm_wav["filepath"], read_audio=False)
        with open(valid_pcm_wav["filepath"], "ab") as f:
            f.write(b"\x00")  # streaming will refuse the changed source mid-write
        with pytest.raises(WAVError):
            parser.write_wav(out)
        assert out.read_bytes() == b"previous contents"
        assert not list(tmp_path.glob("*.riffytmp"))

    def test_write_through_symlink_updates_the_real_file(self, valid_pcm_wav, tmp_path):
        real = valid_pcm_wav["filepath"]
        link = tmp_path / "link.wav"
        link.symlink_to(real)
        parser = WAVParser(real, read_audio=False)
        parser.set_chunk("guan", _guano_bytes("Linked"))
        parser.write_wav(link, overwrite=True)
        assert link.is_symlink()
        assert GuanoMetadata.from_parser(WAVParser(real)).make == "Linked"

    def test_new_file_gets_default_permissions(self, valid_pcm_wav, tmp_path):
        import os

        umask = os.umask(0)
        os.umask(umask)
        out = tmp_path / "new.wav"
        WAVParser(valid_pcm_wav["filepath"]).write_wav(out)
        assert out.stat().st_mode & 0o777 == 0o666 & ~umask

    def test_existing_file_keeps_its_permissions(self, valid_pcm_wav, tmp_path):
        out = tmp_path / "out.wav"
        out.write_bytes(b"x")
        out.chmod(0o640)
        WAVParser(valid_pcm_wav["filepath"]).write_wav(out)
        assert out.stat().st_mode & 0o777 == 0o640

    def test_audio_state_follows_data_edits(self, valid_pcm_wav):
        parser = WAVParser(valid_pcm_wav["filepath"], read_audio=False)
        assert parser.audio_offset is not None
        parser.remove_chunk("data")
        assert (parser.audio_size, parser.audio_offset) == (0, None)
        parser.add_chunk("data", b"\x00\x01\x02\x03")
        assert (parser.audio_size, parser.audio_offset, parser.audio_data) == (
            4,
            None,
            b"\x00\x01\x02\x03",
        )
        parser.add_chunk("data", b"\xff" * 8)
        parser.remove_chunk("data", index=0)
        assert parser.audio_size == 8

    def test_diff_with_one_side_in_memory(self, temp_wav_dir):
        a = create_wav_file(temp_wav_dir / "a.wav", num_samples=50000)["filepath"]
        b = create_wav_file(temp_wav_dir / "b.wav", num_samples=50000)["filepath"]
        assert diff(WAVParser(a), b).identical
