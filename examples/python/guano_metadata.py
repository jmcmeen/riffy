"""Embed and read back GUANO metadata in a WAV file.

GUANO is the vendor-neutral bat/bioacoustics metadata standard (chunk ``guan``).
This example authors a ``guan`` chunk with typed and vendor-namespaced fields,
writes it, then reads it back — showing that timezone offsets, locations, lists,
and unknown vendor fields all round-trip.
"""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _helpers import banner, make_pcm_wav

from riffy import GuanoMetadata, WAVParser


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = make_pcm_wav(Path(tmp) / "bat.wav")

        # --- Author GUANO metadata ---
        g = GuanoMetadata(version="1.0")
        g.make = "Wildlife Acoustics, Inc."
        g.model = "Song Meter Mini Bat"
        g.serial = "SMU01234"
        g.timestamp = datetime(2021, 8, 14, 21, 1, 18, tzinfo=timezone(timedelta(hours=-4)))
        g.loc_position = (36.31119, -82.34027)
        g.samplerate = 256000
        g.species_manual_id = ["MYLU", "MYSO"]
        # Vendor-namespaced field (preserved verbatim on round-trip):
        g.set("WA", "Song Meter|Prefix", "FROGPOND")

        parser = WAVParser(base)
        g.write_to_parser(parser)
        tagged = parser.write_wav(Path(tmp) / "bat_tagged.wav")
        banner("Wrote GUANO chunk")
        print(f"tagged file: {tagged} bytes written")

        # --- Read it back ---
        loaded = GuanoMetadata.from_parser(WAVParser(Path(tmp) / "bat_tagged.wav"))
        assert loaded is not None
        banner("Read back typed fields")
        print(f"version:            {loaded.version}")
        print(f"make / model:       {loaded.make} / {loaded.model}")
        print(f"timestamp:          {loaded.timestamp}  (UTC offset preserved)")
        print(f"loc_position:       {loaded.loc_position}")
        print(f"samplerate:         {loaded.samplerate}")
        print(f"species_manual_id:  {loaded.species_manual_id}")
        print(f"WA|Song Meter|Prefix: {loaded.get('WA', 'Song Meter|Prefix')!r}")

        banner("All (namespace, key) fields")
        for (namespace, key), value in loaded.fields.items():
            label = f"{namespace}|{key}" if namespace else key
            print(f"  {label}: {value}")


if __name__ == "__main__":
    main()
