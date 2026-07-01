"""AudioMoth comment-string decoder.

AudioMoth recorders pack their metadata into a single free-text comment stored
in the RIFF INFO ``ICMT`` field (with the device string in ``IART``), in an
undocumented format that drifts between firmware versions. A typical string::

    Recorded at 19:30:00 12/11/2021 (UTC) by AudioMoth 248D9B045EC9EE79 at
    medium gain while battery was 4.1V and temperature was 14.0C.

Rather than switch on firmware version (the clause order and wording differ
between the metamoth reference parser and the AudioMoth firmware source, and
change repeatedly across versions), this decoder extracts each field with its
own tolerant, independently-anchored regex. That makes it **partial**: if one
field (say the timestamp) fails to match, every other field that did match is
still returned, rather than discarding the whole string — a concrete pain point
reported against existing parsers.

Format knowledge here is derived from the ``metamoth`` library
(github.com/mbsantiago/metamoth, ``src/metamoth/parsing.py``) and the AudioMoth
firmware source (github.com/OpenAcousticDevices/AudioMoth-Firmware-Basic,
``setHeaderComment`` in ``src/main.c``). Parsing is best-effort and
firmware-dependent by nature.

Known limitation: the firmware 1.8+ ``Frequency trigger (...)`` clause is not
decoded into a dedicated field (no real sample was available to validate it
against). It is left in the raw ``comment`` string for downstream consumers, and
it is deliberately *not* mistaken for a frequency filter.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from ..wav import WAVParser
from .guano import GuanoMetadata
from .info import InfoMetadata

#: Numeric gain settings (firmware <= 1.3.0) map onto this word scale, which
#: later firmware uses directly.
GAIN_WORDS = ["low", "low-medium", "medium", "medium-high", "high"]

# Independently-anchored field patterns. Each is matched against the whole
# comment; a miss simply leaves that field unset (partial extraction).
_TIMESTAMP_RE = re.compile(
    r"Recorded at (\d{2}):(\d{2}):(\d{2}) (\d{2})/(\d{2})/(\d{4})"
    r"(?: \(UTC([+-]\d{1,2})?(?::(\d{2}))?\))?"
)
_DEVICE_RE = re.compile(r"by AudioMoth ([0-9A-Za-z]{16})")
_DEPLOYMENT_RE = re.compile(r"during deployment ([0-9A-Za-z]{16})")
_GAIN_WORD_RE = re.compile(r"at ([a-z][a-z-]*) gain")
_GAIN_NUM_RE = re.compile(r"at gain setting (\d+)")
_BATTERY_RE = re.compile(
    r"battery (?:state )?was ((?:less than |greater than |[<>] ?)?(\d+(?:\.\d+)?)V)"
)
_TEMPERATURE_RE = re.compile(r"temperature was (-?\d+(?:\.\d+)?)C")
_EXTERNAL_MIC_RE = re.compile(r"using external microphone")
_THRESHOLD_RE = re.compile(r"Amplitude threshold was (.+?)(?:\.| with )")
_TRIGGER_DURATION_RE = re.compile(r"with (\d+)s minimum trigger duration")
# Match the filter clause up to the sentence-ending period. A period that is
# part of a frequency (e.g. "20.0kHz") is followed by a digit, so it is kept;
# the terminating period is not.
_FILTER_RE = re.compile(r"(Low-pass|Band-pass|High-pass) filter(?:[^.]|\.\d)*")
_FILTER_FREQ_RE = re.compile(r"(\d+(?:\.\d+)?)kHz")
_STOPPED_RE = re.compile(
    r"Recording (?:cancelled before completion|stopped)"
    r"(?: due to| by)?\s*(.+?)\."
)


@dataclass
class AudioMothMetadata:
    """Structured, best-effort view of an AudioMoth comment string.

    Every field is optional: an attribute is left unset when the corresponding
    clause is absent or unparseable, so a partially-recognized comment still
    yields whatever could be extracted.
    """

    comment: str | None = None
    artist: str | None = None
    timestamp: datetime | None = None
    device_id: str | None = None
    deployment_id: str | None = None
    gain: str | None = None
    #: The numeric voltage figure mentioned in the comment. For a threshold
    #: reading ("less than 2.5V") this is the threshold, not a measurement; the
    #: full phrase is preserved in ``battery_state``.
    battery_voltage: float | None = None
    battery_state: str | None = None
    temperature_c: float | None = None
    external_microphone: bool = False
    amplitude_threshold: str | None = None
    min_trigger_duration_s: int | None = None
    filter_type: str | None = None
    filter_frequencies_khz: list[float] = field(default_factory=list)
    recording_stopped_reason: str | None = None

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    @classmethod
    def from_comment(cls, comment: str, artist: str | None = None) -> "AudioMothMetadata":
        """Decode an AudioMoth comment string (and optional artist string).

        Extraction is partial: each field is parsed independently, so a failure
        in one clause never prevents the others from being returned.
        """
        self = cls(comment=comment, artist=artist)

        self.timestamp = _parse_timestamp(comment)

        device = _DEVICE_RE.search(comment)
        if device:
            self.device_id = device.group(1)
        deployment = _DEPLOYMENT_RE.search(comment)
        if deployment:
            self.deployment_id = deployment.group(1)

        self.gain = _parse_gain(comment)

        battery = _BATTERY_RE.search(comment)
        if battery:
            self.battery_state = battery.group(1)
            self.battery_voltage = float(battery.group(2))

        temperature = _TEMPERATURE_RE.search(comment)
        if temperature:
            self.temperature_c = float(temperature.group(1))

        self.external_microphone = _EXTERNAL_MIC_RE.search(comment) is not None

        threshold = _THRESHOLD_RE.search(comment)
        if threshold:
            self.amplitude_threshold = threshold.group(1).strip()
        duration = _TRIGGER_DURATION_RE.search(comment)
        if duration:
            self.min_trigger_duration_s = int(duration.group(1))

        filter_match = _FILTER_RE.search(comment)
        if filter_match:
            self.filter_type = filter_match.group(1)
            self.filter_frequencies_khz = [
                float(f) for f in _FILTER_FREQ_RE.findall(filter_match.group(0))
            ]

        stopped = _STOPPED_RE.search(comment)
        if stopped:
            self.recording_stopped_reason = stopped.group(1).strip()

        return self

    @classmethod
    def from_info(cls, info: InfoMetadata) -> "AudioMothMetadata | None":
        """Decode from a parsed :class:`~riffy.metadata.InfoMetadata`.

        Reads the comment from ``ICMT`` and the device string from ``IART``.
        Returns ``None`` if the INFO block shows no sign of being AudioMoth's.
        """
        comment = info.comment
        artist = info.artist
        if not _looks_like_audiomoth(comment, artist):
            return None
        return cls.from_comment(comment or "", artist)

    @classmethod
    def from_parser(cls, parser: WAVParser) -> "AudioMothMetadata | None":
        """Decode from a parser's INFO block, or ``None`` if not AudioMoth."""
        info = InfoMetadata.from_parser(parser)
        if info is None:
            return None
        return cls.from_info(info)

    # ------------------------------------------------------------------ #
    # Within-standard normalization
    # ------------------------------------------------------------------ #

    def to_guano(self) -> GuanoMetadata:
        """Map the extracted fields onto GUANO-equivalent keys.

        A within-standard convenience (not cross-standard reconciliation): it
        normalizes an AudioMoth recording into the same shape as a GUANO-native
        one, so downstream code can treat them uniformly. Device-specific fields
        with no GUANO well-known equivalent go under the ``AudioMoth`` namespace.
        """
        g = GuanoMetadata(version="1.0")
        g.make = "Open Acoustic Devices"
        g.model = "AudioMoth"
        if self.device_id is not None:
            g.serial = self.device_id
        if self.timestamp is not None:
            g.timestamp = self.timestamp
        if self.temperature_c is not None:
            g.temperature_int = self.temperature_c
        if self.gain is not None:
            g.set("AudioMoth", "Gain", self.gain)
        if self.battery_voltage is not None:
            g.set("AudioMoth", "Battery Voltage", f"{self.battery_voltage}")
        if self.deployment_id is not None:
            g.set("AudioMoth", "Deployment ID", self.deployment_id)
        return g


# ---------------------------------------------------------------------- #
# Module-level parsing helpers
# ---------------------------------------------------------------------- #


def _looks_like_audiomoth(comment: str | None, artist: str | None) -> bool:
    """Heuristic: does this INFO block come from an AudioMoth?"""
    if artist and artist.startswith("AudioMoth"):
        return True
    if comment and ("AudioMoth" in comment or comment.startswith("Recorded at")):
        return True
    return False


def _parse_timestamp(comment: str) -> datetime | None:
    """Parse the 'Recorded at HH:MM:SS DD/MM/YYYY (UTC±H:MM)' clause.

    Returns a timezone-aware datetime, defaulting to UTC when the firmware
    omits an offset (older firmware records in UTC without stating it).
    """
    match = _TIMESTAMP_RE.search(comment)
    if not match:
        return None
    hh, mm, ss, day, month, year, offset_hours, offset_minutes = match.groups()
    sign = -1 if (offset_hours and offset_hours[0] == "-") else 1
    hours = abs(int(offset_hours)) if offset_hours else 0
    minutes = int(offset_minutes) if offset_minutes else 0
    tz = timezone(sign * timedelta(hours=hours, minutes=minutes))
    return datetime(int(year), int(month), int(day), int(hh), int(mm), int(ss), tzinfo=tz)


def _parse_gain(comment: str) -> str | None:
    """Parse the gain, normalizing numeric settings onto the word scale."""
    numeric = _GAIN_NUM_RE.search(comment)
    if numeric:
        value = int(numeric.group(1))
        return GAIN_WORDS[value] if 0 <= value < len(GAIN_WORDS) else numeric.group(1)
    word = _GAIN_WORD_RE.search(comment)
    if word:
        return word.group(1)
    return None
