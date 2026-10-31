"""WAVE_FORMAT_EXTENSIBLE and IEEE float support."""

import struct

import pytest

from riffy import (
    WAVE_FORMAT_EXTENSIBLE,
    WAVE_FORMAT_IEEE_FLOAT,
    WAVE_FORMAT_PCM,
    InvalidWAVFormatError,
    UnsupportedFormatError,
    WAVParser,
)

from .conftest import create_wav_file

GUID_TAIL = bytes.fromhex("000000001000800000aa00389b71")


def extensible(subformat: int, valid_bits: int, channel_mask: int = 0, tail: bytes = GUID_TAIL):
    """The cbSize + WAVEFORMATEXTENSIBLE extension for a fmt chunk."""
    guid = struct.pack("<H", subformat) + tail
    return struct.pack("<HHI", 22, valid_bits, channel_mask) + guid


class TestExtensible:
    def test_24bit_multichannel_pcm(self, temp_wav_dir):
        wav = create_wav_file(
            temp_wav_dir / "x.wav",
            audio_format=WAVE_FORMAT_EXTENSIBLE,
            channels=4,
            sample_rate=48000,
            bits_per_sample=24,
            num_samples=4800,
            extra_fmt_data=extensible(WAVE_FORMAT_PCM, 24, channel_mask=0x33),
        )
        parser = WAVParser(wav["filepath"])
        fmt = parser.format_info
        assert fmt.is_extensible and fmt.is_pcm and not fmt.is_float
        assert (fmt.subformat, fmt.valid_bits_per_sample, fmt.channel_mask) == (1, 24, 0x33)
        assert parser.get_info()["sample_count"] == 4800
        assert parser.get_info()["duration_seconds"] == pytest.approx(0.1)

    def test_24_valid_bits_in_32bit_containers(self, temp_wav_dir):
        wav = create_wav_file(
            temp_wav_dir / "x.wav",
            audio_format=WAVE_FORMAT_EXTENSIBLE,
            channels=2,
            bits_per_sample=32,
            num_samples=1000,
            extra_fmt_data=extensible(WAVE_FORMAT_PCM, 24),
        )
        info = WAVParser(wav["filepath"]).get_info()
        assert info["sample_count"] == 1000
        assert info["format"]["valid_bits_per_sample"] == 24

    def test_float_subformat(self, temp_wav_dir):
        wav = create_wav_file(
            temp_wav_dir / "x.wav",
            audio_format=WAVE_FORMAT_EXTENSIBLE,
            bits_per_sample=32,
            num_samples=100,
            extra_fmt_data=extensible(WAVE_FORMAT_IEEE_FLOAT, 32),
        )
        fmt = WAVParser(wav["filepath"]).format_info
        assert fmt.is_float and not fmt.is_pcm

    def test_compressed_subformat_rejected(self, temp_wav_dir):
        wav = create_wav_file(
            temp_wav_dir / "x.wav",
            audio_format=WAVE_FORMAT_EXTENSIBLE,
            extra_fmt_data=extensible(0x0002, 4),  # ADPCM
        )
        with pytest.raises(UnsupportedFormatError, match="ADPCM, extensible"):
            WAVParser(wav["filepath"])

    def test_unknown_guid_rejected(self, temp_wav_dir):
        wav = create_wav_file(
            temp_wav_dir / "x.wav",
            audio_format=WAVE_FORMAT_EXTENSIBLE,
            extra_fmt_data=extensible(WAVE_FORMAT_PCM, 16, tail=b"\x11" * 14),
        )
        with pytest.raises(UnsupportedFormatError, match="unrecognized subformat GUID"):
            WAVParser(wav["filepath"])

    def test_short_extension_rejected(self, temp_wav_dir):
        wav = create_wav_file(
            temp_wav_dir / "x.wav",
            audio_format=WAVE_FORMAT_EXTENSIBLE,
            extra_fmt_data=struct.pack("<H", 0),
        )
        with pytest.raises(InvalidWAVFormatError, match="22-byte extension"):
            WAVParser(wav["filepath"])


class TestFloat:
    @pytest.mark.parametrize("extra", [b"", struct.pack("<H", 0)])
    def test_float_with_and_without_cbsize(self, temp_wav_dir, extra):
        wav = create_wav_file(
            temp_wav_dir / "f.wav",
            audio_format=WAVE_FORMAT_IEEE_FLOAT,
            bits_per_sample=32,
            num_samples=1000,
            extra_fmt_data=extra,
        )
        parser = WAVParser(wav["filepath"])
        assert parser.format_info.is_float
        assert parser.get_info()["sample_count"] == 1000

    def test_float_round_trips_through_write(self, temp_wav_dir):
        wav = create_wav_file(
            temp_wav_dir / "f.wav", audio_format=WAVE_FORMAT_IEEE_FLOAT, bits_per_sample=64
        )
        parser = WAVParser(wav["filepath"])
        parser.add_chunk("ICMT", b"note")
        out = temp_wav_dir / "out.wav"
        parser.write_wav(out)
        again = WAVParser(out)
        assert again.format_info.is_float
        assert again.audio_data == parser.audio_data


def test_alaw_still_rejected(non_pcm_wav_valid):
    with pytest.raises(UnsupportedFormatError, match="only PCM and IEEE float"):
        WAVParser(non_pcm_wav_valid["filepath"])


class TestFormatChecks:
    def test_float_needs_32_or_64_bits(self, temp_wav_dir):
        wav = create_wav_file(
            temp_wav_dir / "f.wav", audio_format=WAVE_FORMAT_IEEE_FLOAT, bits_per_sample=16
        )
        with pytest.raises(InvalidWAVFormatError, match="32 or 64 bits"):
            WAVParser(wav["filepath"])

    def test_valid_bits_cannot_exceed_container(self, temp_wav_dir):
        wav = create_wav_file(
            temp_wav_dir / "x.wav",
            audio_format=WAVE_FORMAT_EXTENSIBLE,
            bits_per_sample=24,
            extra_fmt_data=extensible(WAVE_FORMAT_PCM, 32),
        )
        with pytest.raises(InvalidWAVFormatError, match="exceed the 24-bit container"):
            WAVParser(wav["filepath"])

    def test_wrong_block_align_warns_and_counts_frames(self, temp_wav_dir):
        wav = create_wav_file(temp_wav_dir / "x.wav", channels=2, num_samples=1000)
        path = wav["filepath"]
        raw = bytearray(path.read_bytes())
        raw[32:34] = struct.pack("<H", 1)  # block_align: 1 instead of 4
        path.write_bytes(bytes(raw))
        with pytest.warns(UserWarning, match="block_align is 1"):
            parser = WAVParser(path)
        assert parser.get_info()["sample_count"] == 1000

    def test_replacing_fmt_refreshes_the_format(self, temp_wav_dir):
        wav = create_wav_file(temp_wav_dir / "x.wav", bits_per_sample=24, num_samples=10)
        parser = WAVParser(wav["filepath"])
        fmt = parser.get_chunk_bytes("fmt ")
        parser.replace_chunk(
            "fmt ",
            struct.pack("<H", WAVE_FORMAT_EXTENSIBLE) + fmt[2:16] + extensible(WAVE_FORMAT_PCM, 20),
        )
        assert parser.format_info.is_extensible
        assert parser.format_info.valid_bits_per_sample == 20

    @pytest.mark.parametrize(
        ("audio_format", "extra", "expected"),
        [
            (WAVE_FORMAT_PCM, b"", "PCM"),
            (WAVE_FORMAT_IEEE_FLOAT, b"", "IEEE float"),
            (WAVE_FORMAT_EXTENSIBLE, extensible(WAVE_FORMAT_PCM, 16), "PCM, extensible"),
        ],
    )
    def test_description(self, temp_wav_dir, audio_format, extra, expected):
        bits = 32 if audio_format == WAVE_FORMAT_IEEE_FLOAT else 16
        wav = create_wav_file(
            temp_wav_dir / "d.wav",
            audio_format=audio_format,
            bits_per_sample=bits,
            extra_fmt_data=extra,
        )
        assert WAVParser(wav["filepath"]).get_info()["format"]["description"] == expected
