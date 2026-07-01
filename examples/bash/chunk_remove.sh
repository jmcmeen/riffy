#!/usr/bin/env bash
# Remove a chunk from a WAV file.
# Exercises `riffy chunk remove` (no Python-example equivalent).
source "$(dirname "$0")/_helpers.sh"

scratch="$(make_scratch)"
wav="$scratch/sample.wav"
make_pcm_wav "$wav"
$RIFFY set "$wav" --guano 'GUANO|Version=1.0' --guano 'Make=Riffy' --apply >/dev/null

banner "Before — the file has a 'guan' chunk"
$RIFFY chunks "$wav"

banner "Remove it (dry run first, then apply)"
$RIFFY chunk remove "$wav" guan
$RIFFY chunk remove "$wav" guan --apply

banner "After — 'guan' is gone"
$RIFFY chunks "$wav"
