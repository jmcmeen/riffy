#!/usr/bin/env bash
# End-to-end workflow: start from a bare WAV, keep a backup, add metadata and a
# custom chunk, then diff the result against the backup to confirm the change.
# Mirrors python/complete_workflow.py, via the CLI.
source "$(dirname "$0")/_helpers.sh"

scratch="$(make_scratch)"
wav="$scratch/recording.wav"
make_pcm_wav "$wav" 0.2
cp "$wav" "$scratch/original.wav"
printf 'field notes: heavy rain' > "$scratch/note.bin"

banner "Step 1 — tag the recording with GUANO metadata"
$RIFFY set "$wav" \
  --guano 'GUANO|Version=1.0' \
  --guano 'Make=Riffy' \
  --guano 'Species Manual ID=Myosod' \
  --apply

banner "Step 2 — attach a custom NOTE chunk"
$RIFFY chunk add "$wav" NOTE "$scratch/note.bin" --apply

banner "Step 3 — diff against the untouched original"
$RIFFY diff "$scratch/original.wav" "$wav"

banner "Step 4 — final metadata view"
$RIFFY inspect "$wav"
