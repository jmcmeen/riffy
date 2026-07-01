"""Tests for riffy.metadata.audiomoth (AudioMoth comment-string decoder).

Fixtures are grouped by provenance:

* REAL_* strings are verbatim from real AudioMoth recordings — one from the
  official AudioMoth sample sound files (firmware ~1.0.1/1.1.0), one from the
  metamoth project's real-recording test (firmware 1.6.0).
* The strings in TestDocumentedFormats are CONSTRUCTED from the documented
  per-firmware format (metamoth ``src/metamoth/parsing.py`` and the AudioMoth
  firmware ``setHeaderComment`` in ``src/main.c``), to exercise clauses the two
  real strings do not contain. They are labeled as such.
"""

from datetime import datetime, timedelta, timezone

from riffy.metadata.audiomoth import AudioMothMetadata
from riffy.wav import WAVParser

# Real device recording, firmware ~1.0.1/1.1.0 (numeric gain, no temperature).
# Source: official AudioMoth sample sound files.
REAL_V1_0_1 = (
    "Recorded at 19:10:00 06/04/2018 (UTC) by AudioMoth 0FE081F80FE081F0 "
    "at gain setting 2 while battery state was 4.5V"
)

# Real device recording, firmware 1.6.0 (word gain, temperature).
# Source: metamoth tests/test_with_real_recordings.py (20211112_193000.WAV).
REAL_V1_6_0 = (
    "Recorded at 19:30:00 12/11/2021 (UTC) by AudioMoth 248D9B045EC9EE79 "
    "at medium gain while battery was 4.1V and temperature was 14.0C."
)


class TestRealStrings:
    def test_v1_0_1_numeric_gain(self):
        m = AudioMothMetadata.from_comment(REAL_V1_0_1)
        assert m.timestamp == datetime(2018, 4, 6, 19, 10, 0, tzinfo=timezone.utc)
        assert m.device_id == "0FE081F80FE081F0"
        assert m.gain == "medium"  # normalized from "gain setting 2"
        assert m.battery_voltage == 4.5
        assert m.temperature_c is None  # absent in this firmware

    def test_v1_6_0_word_gain_and_temperature(self):
        m = AudioMothMetadata.from_comment(REAL_V1_6_0, artist="AudioMoth 248D9B045EC9EE79")
        assert m.timestamp == datetime(2021, 11, 12, 19, 30, 0, tzinfo=timezone.utc)
        assert m.device_id == "248D9B045EC9EE79"
        assert m.gain == "medium"
        assert m.battery_voltage == 4.1
        assert m.temperature_c == 14.0
        assert m.artist == "AudioMoth 248D9B045EC9EE79"

    def test_day_first_date_not_month_first(self):
        # 06/04/2018 is 6 April, not 4 June.
        m = AudioMothMetadata.from_comment(REAL_V1_0_1)
        assert (m.timestamp.day, m.timestamp.month) == (6, 4)


class TestTimezones:
    def _ts(self, clause: str) -> datetime:
        comment = (
            f"Recorded at 06:00:00 24/06/2020 {clause} by AudioMoth 0FE081F80FE081F8 at high gain"
        )
        return AudioMothMetadata.from_comment(comment).timestamp

    def test_utc(self):
        assert self._ts("(UTC)").utcoffset() == timedelta(0)

    def test_positive_hour_offset(self):
        assert self._ts("(UTC+2)").utcoffset() == timedelta(hours=2)

    def test_negative_hour_offset(self):
        assert self._ts("(UTC-5)").utcoffset() == timedelta(hours=-5)

    def test_offset_with_minutes(self):
        assert self._ts("(UTC+5:30)").utcoffset() == timedelta(hours=5, minutes=30)

    def test_negative_offset_with_minutes(self):
        assert self._ts("(UTC-9:30)").utcoffset() == timedelta(hours=-9, minutes=-30)

    def test_no_utc_clause_defaults_to_utc(self):
        # Firmware 1.0 omitted the timezone entirely; assume UTC.
        comment = (
            "Recorded at 19:17:30 21/02/2018 by AudioMoth 0FE081F80FE081F8 "
            "at gain setting 2 while battery state was 3.9V"
        )
        assert AudioMothMetadata.from_comment(comment).timestamp.utcoffset() == timedelta(0)


class TestGainNormalization:
    def test_numeric_settings_map_to_words(self):
        for setting, word in enumerate(["low", "low-medium", "medium", "medium-high", "high"]):
            comment = f"by AudioMoth 0FE081F80FE081F8 at gain setting {setting} while battery"
            assert AudioMothMetadata.from_comment(comment).gain == word

    def test_out_of_range_numeric_gain_kept_raw(self):
        comment = "by AudioMoth 0FE081F80FE081F8 at gain setting 9 while battery"
        assert AudioMothMetadata.from_comment(comment).gain == "9"

    def test_word_gain(self):
        comment = "by AudioMoth 0FE081F80FE081F8 at low-medium gain while battery"
        assert AudioMothMetadata.from_comment(comment).gain == "low-medium"


class TestBattery:
    def test_plain_voltage(self):
        m = AudioMothMetadata.from_comment("while battery was 4.1V and")
        assert m.battery_voltage == 4.1
        assert m.battery_state == "4.1V"

    def test_less_than_words(self):
        m = AudioMothMetadata.from_comment("while battery state was less than 2.5V and")
        assert m.battery_state == "less than 2.5V"
        assert m.battery_voltage == 2.5

    def test_greater_than_words(self):
        m = AudioMothMetadata.from_comment("while battery state was greater than 4.9V and")
        assert m.battery_state == "greater than 4.9V"

    def test_angle_bracket_form(self):
        # Firmware 1.0 used '<'/'>' rather than words.
        m = AudioMothMetadata.from_comment("while battery state was < 3.6V")
        assert m.battery_voltage == 3.6


class TestDocumentedFormats:
    """CONSTRUCTED from the documented firmware formats (see module docstring)."""

    def test_deployment_id_form(self):
        comment = (
            "Recorded at 19:30:00 12/11/2021 (UTC) during deployment 001A2B3C4D5E6F70 "
            "at low-medium gain while battery was 3.7V and temperature was 14.0C."
        )
        m = AudioMothMetadata.from_comment(comment)
        assert m.deployment_id == "001A2B3C4D5E6F70"
        assert m.device_id is None
        assert m.gain == "low-medium"

    def test_external_microphone(self):
        comment = (
            "by AudioMoth 248D9B045EC9EE79 using external microphone at high gain "
            "while battery was greater than 4.9V and temperature was 22.0C."
        )
        m = AudioMothMetadata.from_comment(comment)
        assert m.external_microphone is True
        assert m.gain == "high"

    def test_negative_temperature(self):
        comment = "while battery state was less than 2.5V and temperature was -5.0C."
        assert AudioMothMetadata.from_comment(comment).temperature_c == -5.0

    def test_amplitude_threshold_and_trigger_duration(self):
        comment = (
            "temperature was 22.0C. Amplitude threshold was 768 with 5s minimum "
            "trigger duration. Low-pass filter with frequency of 20.0kHz applied."
        )
        m = AudioMothMetadata.from_comment(comment)
        assert m.amplitude_threshold == "768"
        assert m.min_trigger_duration_s == 5

    def test_amplitude_threshold_trailing_period(self):
        comment = "temperature was 24.0C. Amplitude threshold was 512. Band-pass filter"
        assert AudioMothMetadata.from_comment(comment).amplitude_threshold == "512"

    def test_bandpass_filter_two_frequencies(self):
        comment = (
            "Amplitude threshold was 512. Band-pass filter applied with cut-off "
            "frequencies of 1.0kHz and 20.0kHz."
        )
        m = AudioMothMetadata.from_comment(comment)
        assert m.filter_type == "Band-pass"
        assert m.filter_frequencies_khz == [1.0, 20.0]

    def test_lowpass_filter_one_frequency(self):
        comment = "Low-pass filter with frequency of 20.0kHz applied."
        m = AudioMothMetadata.from_comment(comment)
        assert m.filter_type == "Low-pass"
        assert m.filter_frequencies_khz == [20.0]

    def test_recording_cancelled_reason(self):
        comment = (
            "while battery state was less than 2.5V and temperature was -5.0C. "
            "Recording cancelled before completion due to low voltage."
        )
        assert AudioMothMetadata.from_comment(comment).recording_stopped_reason == "low voltage"

    def test_recording_stopped_reason(self):
        comment = "temperature was 22.0C. Recording stopped due to switch position change."
        m = AudioMothMetadata.from_comment(comment)
        assert m.recording_stopped_reason == "switch position change"

    def test_recording_stopped_by_magnetic_switch(self):
        comment = "temperature was 22.0C. Recording stopped by magnetic switch."
        assert AudioMothMetadata.from_comment(comment).recording_stopped_reason == "magnetic switch"


class TestPartialExtraction:
    def test_unparseable_timestamp_keeps_other_fields(self):
        # Timestamp clause is corrupt, but battery/gain still parse.
        comment = (
            "Recorded at NN:NN:NN by AudioMoth 0FE081F80FE081F8 at high gain while battery was 3.9V"
        )
        m = AudioMothMetadata.from_comment(comment)
        assert m.timestamp is None
        assert m.device_id == "0FE081F80FE081F8"
        assert m.gain == "high"
        assert m.battery_voltage == 3.9

    def test_frequency_trigger_clause_not_mistaken_for_filter(self):
        # Firmware 1.8+ 'Frequency trigger (2.0kHz ...)' is not decoded, but its
        # kHz value must NOT leak into filter_frequencies_khz (no filter present).
        comment = (
            "temperature was 22.0C. Frequency trigger (2.0kHz and window length "
            "of 16 samples) threshold was 50% with 5s minimum trigger duration."
        )
        m = AudioMothMetadata.from_comment(comment)
        assert m.filter_type is None
        assert m.filter_frequencies_khz == []

    def test_garbage_string_returns_empty_object(self):
        m = AudioMothMetadata.from_comment("not an audiomoth comment at all")
        assert m.timestamp is None
        assert m.device_id is None
        assert m.gain is None


class TestDetection:
    def test_looks_like_audiomoth_via_comment(self, make_metadata_wav):
        from riffy.metadata.info import InfoMetadata

        info = InfoMetadata()
        info.comment = REAL_V1_0_1
        m = AudioMothMetadata.from_info(info)
        assert m is not None
        assert m.device_id == "0FE081F80FE081F0"

    def test_non_audiomoth_info_returns_none(self):
        from riffy.metadata.info import InfoMetadata

        info = InfoMetadata()
        info.comment = "Just a regular comment"
        info.artist = "Some Band"
        assert AudioMothMetadata.from_info(info) is None

    def test_no_info_block_returns_none(self, make_metadata_wav):
        path = make_metadata_wav([])
        assert AudioMothMetadata.from_parser(WAVParser(path)) is None


class TestGuanoMapping:
    def test_to_guano_maps_known_and_vendor_fields(self):
        m = AudioMothMetadata.from_comment(REAL_V1_6_0)
        g = m.to_guano()
        assert g.version == "1.0"
        assert g.make == "Open Acoustic Devices"
        assert g.model == "AudioMoth"
        assert g.serial == "248D9B045EC9EE79"
        assert g.timestamp == datetime(2021, 11, 12, 19, 30, 0, tzinfo=timezone.utc)
        assert g.temperature_int == 14.0
        assert g.get("AudioMoth", "Gain") == "medium"
        assert g.get("AudioMoth", "Battery Voltage") == "4.1"
        # The mapped GUANO object serializes like a native one.
        assert g.to_chunk_bytes().startswith(b"GUANO|Version: 1.0")

    def test_to_guano_deployment_id(self):
        comment = (
            "Recorded at 19:30:00 12/11/2021 (UTC) during deployment 001A2B3C4D5E6F70 at high gain"
        )
        g = AudioMothMetadata.from_comment(comment).to_guano()
        assert g.get("AudioMoth", "Deployment ID") == "001A2B3C4D5E6F70"
        assert g.serial is None


class TestParserIntegration:
    def test_from_parser_reads_icmt(self, make_metadata_wav):
        from riffy.metadata.info import InfoMetadata

        info = InfoMetadata()
        info.comment = REAL_V1_6_0
        info.artist = "AudioMoth 248D9B045EC9EE79"
        path = make_metadata_wav([("LIST", info.to_chunk_bytes())])

        m = AudioMothMetadata.from_parser(WAVParser(path))
        assert m is not None
        assert m.device_id == "248D9B045EC9EE79"
        assert m.temperature_c == 14.0
