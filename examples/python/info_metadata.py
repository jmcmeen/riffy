"""Embed and read back RIFF INFO metadata in a WAV file.

RIFF INFO is a ``LIST``/``INFO`` chunk of standard tags (title, artist, comment,
software, ...). This example writes several tags, then reads them back through
both the friendly attributes and the raw FOURCC access.
"""

import tempfile
from pathlib import Path

from _helpers import banner, make_pcm_wav

from riffy import InfoMetadata, WAVParser


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = make_pcm_wav(Path(tmp) / "clip.wav")

        # --- Author INFO tags ---
        info = InfoMetadata()
        info.title = "Dawn Chorus"
        info.artist = "Field Team"
        info.comment = "Recorded at the edge of the wetland"
        info.software = "riffy"
        info.creation_date = "2026-07-01"
        info.set("IGNR", "Nature")  # raw FOURCC also works

        parser = WAVParser(base)
        info.write_to_parser(parser)
        parser.write_wav(Path(tmp) / "clip_tagged.wav")
        banner("Wrote LIST/INFO chunk")

        # --- Read it back ---
        loaded = InfoMetadata.from_parser(WAVParser(Path(tmp) / "clip_tagged.wav"))
        assert loaded is not None
        banner("Friendly attributes")
        print(f"title:         {loaded.title}")
        print(f"artist:        {loaded.artist}")
        print(f"comment:       {loaded.comment}")
        print(f"software:      {loaded.software}")
        print(f"creation_date: {loaded.creation_date}")
        print(f"genre (IGNR):  {loaded.get('IGNR')}")

        banner("Raw FOURCC tags")
        for fourcc, value in loaded.tags.items():
            print(f"  {fourcc}: {value}")


if __name__ == "__main__":
    main()
