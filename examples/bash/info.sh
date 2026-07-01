#!/usr/bin/env bash
# Show the audio format and file details of a WAV file.
# Mirrors part of python/example.py, via `riffy info`.
source "$(dirname "$0")/_helpers.sh"

scratch="$(make_scratch)"
wav="$scratch/sample.wav"
make_pcm_wav "$wav" 0.25

banner "riffy info (human-readable)"
$RIFFY info "$wav"

banner "riffy info --json"
$RIFFY info "$wav" --json
