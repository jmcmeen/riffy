#!/usr/bin/env bash
# List every chunk in a WAV file with its size and offset.
# Mirrors part of python/example.py, via `riffy chunks`.
source "$(dirname "$0")/_helpers.sh"

scratch="$(make_scratch)"
wav="$scratch/sample.wav"
make_pcm_wav "$wav"
$RIFFY set "$wav" --guano 'GUANO|Version=1.0' --guano 'Make=Riffy' --apply >/dev/null

banner "riffy chunks (table)"
$RIFFY chunks "$wav"

banner "riffy chunks --json"
$RIFFY chunks "$wav" --json
