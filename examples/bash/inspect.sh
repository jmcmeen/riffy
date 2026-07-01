#!/usr/bin/env bash
# Inspect the recorder metadata in a WAV file (text and JSON).
# Mirrors python/example.py + read_metadata_unified.py, via `riffy inspect`.
source "$(dirname "$0")/_helpers.sh"

scratch="$(make_scratch)"
wav="$scratch/sample.wav"
make_pcm_wav "$wav"

# Give it some GUANO metadata to look at.
$RIFFY set "$wav" --guano 'GUANO|Version=1.0' --guano 'Make=Riffy' \
  --guano 'Loc Position=36.31119 -82.34027' --apply >/dev/null

banner "riffy inspect (human-readable)"
$RIFFY inspect "$wav"

banner "riffy inspect --json"
$RIFFY inspect "$wav" --json
