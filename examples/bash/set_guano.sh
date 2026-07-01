#!/usr/bin/env bash
# Write GUANO metadata fields, including a vendor-namespaced one.
# Mirrors python/guano_metadata.py, via `riffy set --guano`.
source "$(dirname "$0")/_helpers.sh"

scratch="$(make_scratch)"
wav="$scratch/bat.wav"
make_pcm_wav "$wav"

banner "Dry run (default — nothing is written)"
$RIFFY set "$wav" \
  --guano 'GUANO|Version=1.0' \
  --guano 'Make=Wildlife Acoustics, Inc.' \
  --guano 'Model=Song Meter Micro' \
  --guano 'Loc Position=36.31119 -82.34027' \
  --guano 'WA|Song Meter|Prefix=SITE7'

banner "Apply the changes"
$RIFFY set "$wav" \
  --guano 'GUANO|Version=1.0' \
  --guano 'Make=Wildlife Acoustics, Inc.' \
  --guano 'Model=Song Meter Micro' \
  --guano 'Loc Position=36.31119 -82.34027' \
  --guano 'WA|Song Meter|Prefix=SITE7' \
  --apply

banner "Read it back"
$RIFFY inspect "$wav"
