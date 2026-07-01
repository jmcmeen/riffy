"""Embed and read back Broadcast Wave (bext) metadata.

Unlike GUANO/INFO, ``bext`` is a fixed binary layout (EBU Tech 3285). This
example writes a version-1 bext chunk (which includes a UMID), reads it back,
and shows that version-gated fields behave correctly (loudness is v2+, so it is
absent here).
"""

import tempfile
from pathlib import Path

from _helpers import banner, make_pcm_wav

from riffy import BextMetadata, WAVParser


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = make_pcm_wav(Path(tmp) / "bwf.wav")

        # --- Author a version-1 bext chunk ---
        bext = BextMetadata(
            version=1,
            description="Dawn chorus survey, transect 3",
            originator="riffy",
            originator_reference="RIFFY-0001",
            origination_date="2026-07-01",
            origination_time="05:42:00",
            time_reference=44100 * 60,  # one minute in, as a sample count
            umid=bytes(range(64)),
            coding_history="A=PCM,F=44100,W=16,M=mono,T=riffy\r\n",
        )

        parser = WAVParser(base)
        bext.write_to_parser(parser)
        parser.write_wav(Path(tmp) / "bwf_tagged.wav")
        banner("Wrote bext chunk (version 1)")

        # --- Read it back ---
        loaded = BextMetadata.from_parser(WAVParser(Path(tmp) / "bwf_tagged.wav"))
        assert loaded is not None
        banner("Read back bext fields")
        print(f"version:          {loaded.version}")
        print(f"description:      {loaded.description}")
        print(f"originator:       {loaded.originator}")
        print(f"origination:      {loaded.origination_date} {loaded.origination_time}")
        print(f"time_reference:   {loaded.time_reference} samples")
        print(f"umid (first 8B):  {loaded.umid[:8].hex()}")
        print(f"coding_history:   {loaded.coding_history!r}")
        print(f"loudness_value:   {loaded.loudness_value}  (None — v2+ only)")


if __name__ == "__main__":
    main()
