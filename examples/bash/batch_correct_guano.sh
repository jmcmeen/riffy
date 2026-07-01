#!/usr/bin/env bash
# Batch-correct a GUANO field across a folder of recordings with a shell loop.
# The bash counterpart to python/batch_correct_guano.py: where the Python script
# adds re-read/diff verification, this shows the CLI is composable with find/for.
source "$(dirname "$0")/_helpers.sh"

scratch="$(make_scratch)"
folder="$scratch/frogpond"
mkdir -p "$folder"

wrong="35.90000 -83.90000"
corrected="36.31119 -82.34027"

# Three recordings with the WRONG location baked in...
for i in 1 2 3; do
  wav="$folder/FROGPOND_2023081${i}_210000.wav"
  make_pcm_wav "$wav"
  $RIFFY set "$wav" \
    --guano 'GUANO|Version=1.0' \
    --guano 'Make=Wildlife Acoustics, Inc.' \
    --guano "Loc Position=$wrong" \
    --apply >/dev/null
done

banner "Dry run — preview the correction across the folder"
find "$folder" -name '*.wav' -print | sort | while read -r wav; do
  echo "# $wav"
  $RIFFY set "$wav" --guano "Loc Position=$corrected"
done

banner "Apply the correction to every file"
find "$folder" -name '*.wav' -print | sort | while read -r wav; do
  $RIFFY set "$wav" --guano "Loc Position=$corrected" --apply
done

banner "Verify one corrected file"
$RIFFY inspect "$folder/FROGPOND_20230811_210000.wav"
