"""Read every metadata standard in a file at once with read_metadata().

``read_metadata`` inspects a file and surfaces whichever standards it contains,
side by side, without cross-standard reconciliation. This example builds a file
carrying GUANO, an AudioMoth INFO comment, and a bext chunk, then shows the
unified view, the JSON-serializable ``dump_metadata`` output, and the
``python -m riffy`` inspector.
"""

import json
import tempfile
from pathlib import Path

from _helpers import banner, make_pcm_wav

from riffy import (
    BextMetadata,
    GuanoMetadata,
    InfoMetadata,
    WAVParser,
    dump_metadata,
    read_metadata,
)

AUDIOMOTH_COMMENT = (
    "Recorded at 19:10:00 06/04/2018 (UTC) by AudioMoth 0FE081F80FE081F0 "
    "at gain setting 2 while battery state was 4.5V"
)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "recording.wav"
        make_pcm_wav(wav)

        # Embed three standards into the same file.
        parser = WAVParser(wav)

        g = GuanoMetadata(version="1.0")
        g.make = "Open Acoustic Devices"
        g.write_to_parser(parser)

        info = InfoMetadata()
        info.comment = AUDIOMOTH_COMMENT
        info.write_to_parser(parser)

        BextMetadata(version=1, originator="riffy").write_to_parser(parser)
        parser.write_wav(wav, overwrite=True)

        # --- Unified view ---
        meta = read_metadata(wav)
        banner("read_metadata() — standards present")
        print(f"sources: {meta.sources}")
        print(f"guano.make:          {meta.guano.make}")
        print(f"info.comment:        {meta.info.comment[:40]}...")
        print(f"bext.originator:     {meta.bext.originator}")
        print(f"audiomoth.device_id: {meta.audiomoth.device_id}")

        # --- JSON-serializable dump ---
        banner("dump_metadata() — JSON-serializable")
        data = dump_metadata(wav)
        print(json.dumps({"file": "recording.wav", "sources": data["sources"]}, indent=2))

        banner("Command-line inspector")
        print("Inspect any file from the shell with:")
        print("    python -m riffy recording.wav")
        print("    python -m riffy --json recording.wav")


if __name__ == "__main__":
    main()
