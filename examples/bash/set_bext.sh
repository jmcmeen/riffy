#!/usr/bin/env bash
# Write Broadcast Wave (bext) attributes, with version gating.
# Mirrors python/bext_metadata.py, via `riffy set --bext`.
source "$(dirname "$0")/_helpers.sh"

scratch="$(make_scratch)"
wav="$scratch/sample.wav"
make_pcm_wav "$wav"

banner "Set bext fields (version 2 enables the loudness fields)"
$RIFFY set "$wav" \
  --bext 'description=Dawn chorus, pond A' \
  --bext 'originator=riffy' \
  --bext 'origination_date=2026-07-01' \
  --bext 'origination_time=05:14:00' \
  --bext 'time_reference=0' \
  --bext 'version=2' \
  --bext 'loudness_value=-2300' \
  --apply

banner "Read it back"
$RIFFY inspect "$wav"
