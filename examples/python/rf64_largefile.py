"""Write and read the RF64/BW64 large-file form.

Classic WAV caps out at 4 GB because its size fields are 32-bit. RF64/BW64 lifts
that with a ``ds64`` chunk carrying 64-bit sizes. riffy switches to RF64
automatically when a size crosses 4 GB; here we use ``force_rf64=True`` so the
demo needs no multi-gigabyte file.
"""

import tempfile
from pathlib import Path

from _helpers import banner, make_pcm_wav

from riffy import WAVParser


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = make_pcm_wav(Path(tmp) / "audio.wav")

        parser = WAVParser(base)
        banner("Source file")
        print(f"riff_form: {parser.riff_form}   is_rf64: {parser.is_rf64}")

        # Default write keeps classic WAV when the sizes fit:
        parser.write_wav(Path(tmp) / "classic.wav")
        head = (Path(tmp) / "classic.wav").read_bytes()[:4]
        banner("Default write (sizes fit)")
        print(f"leading bytes: {head!r}  -> classic RIFF")

        # Force the large-file form to see the RF64 container + ds64 chunk:
        parser.write_wav(Path(tmp) / "large.wav", force_rf64=True)
        large = WAVParser(Path(tmp) / "large.wav")
        banner("Forced RF64 write")
        print(f"leading bytes: {(Path(tmp) / 'large.wav').read_bytes()[:4]!r}")
        print(f"riff_form: {large.riff_form}   is_rf64: {large.is_rf64}")
        print(f"data samples preserved: {large.audio_data == parser.audio_data}")


if __name__ == "__main__":
    main()
