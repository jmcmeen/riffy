#!/usr/bin/env bash
# Compare two WAV files at the chunk and metadata level.
# Exercises `riffy diff` (the counterpart to python-side round-trip checks).
source "$(dirname "$0")/_helpers.sh"

scratch="$(make_scratch)"
a="$scratch/a.wav"
b="$scratch/b.wav"
make_pcm_wav "$a"
cp "$a" "$b"

# Change only file b, so the diff is easy to read.
$RIFFY set "$b" \
  --guano 'GUANO|Version=1.0' \
  --guano 'Make=Riffy' \
  --guano 'Loc Position=36.31119 -82.34027' \
  --apply >/dev/null

banner "riffy diff a.wav b.wav (text)"
$RIFFY diff "$a" "$b"

banner "riffy diff --json"
$RIFFY diff "$a" "$b" --json
