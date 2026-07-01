#!/usr/bin/env bash
# Inspect a WAV whose RIFF INFO ICMT comment was written by AudioMoth firmware.
# `riffy inspect` decodes the comment and surfaces the AudioMoth fields.
# Mirrors python/audiomoth_comment.py (which uses the library decoder directly).
source "$(dirname "$0")/_helpers.sh"

scratch="$(make_scratch)"
wav="$scratch/audiomoth.wav"

# A representative ~1.0.1 firmware comment string.
comment="Recorded at 19:17:14 06/04/2019 (UTC) by AudioMoth 24F3190337584B39 \
at gain setting 2 while battery state was 4.5V and temperature was 22.3C."
make_icmt_wav "$wav" "$comment"

banner "riffy inspect — AudioMoth fields appear alongside RIFF INFO"
$RIFFY inspect "$wav"

banner "riffy inspect --json (machine-readable)"
$RIFFY inspect "$wav" --json
