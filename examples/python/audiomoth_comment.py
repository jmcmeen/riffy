"""Decode an AudioMoth comment string embedded in a WAV file.

AudioMoth packs its metadata into the RIFF INFO ``ICMT`` comment. This example
embeds a firmware-style comment, decodes the structured fields (partial
extraction — each field is parsed independently), and normalizes the result into
GUANO shape with ``to_guano()``.

The comment string used here is a real firmware ~1.0.1 example from the official
AudioMoth sample recordings.
"""

import tempfile
from pathlib import Path

from _helpers import banner, make_pcm_wav

from riffy import AudioMothMetadata, InfoMetadata, WAVParser

COMMENT = (
    "Recorded at 19:10:00 06/04/2018 (UTC) by AudioMoth 0FE081F80FE081F0 "
    "at gain setting 2 while battery state was 4.5V"
)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = make_pcm_wav(Path(tmp) / "audiomoth.wav")

        # AudioMoth writes its comment into the INFO ICMT field.
        info = InfoMetadata()
        info.comment = COMMENT
        parser = WAVParser(base)
        info.write_to_parser(parser)
        parser.write_wav(Path(tmp) / "audiomoth_tagged.wav")
        banner("Embedded AudioMoth ICMT comment")
        print(COMMENT)

        # --- Decode it ---
        am = AudioMothMetadata.from_parser(WAVParser(Path(tmp) / "audiomoth_tagged.wav"))
        assert am is not None
        banner("Decoded fields")
        print(f"timestamp:    {am.timestamp}")
        print(f"device_id:    {am.device_id}")
        print(f"gain:         {am.gain}  (numeric 'gain setting 2' normalized)")
        print(f"battery:      {am.battery_voltage} V")
        print(f"temperature:  {am.temperature_c}  (absent in this firmware)")

        # --- Normalize into GUANO shape ---
        banner("Mapped onto GUANO keys via to_guano()")
        for (namespace, key), value in am.to_guano().fields.items():
            label = f"{namespace}|{key}" if namespace else key
            print(f"  {label}: {value}")


if __name__ == "__main__":
    main()
