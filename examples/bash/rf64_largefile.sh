#!/usr/bin/env bash
# Emit the RF64/BW64 large-file form on demand with --force-rf64, without needing
# an actual >4 GB file. Mirrors python/rf64_largefile.py, via the CLI's write path.
source "$(dirname "$0")/_helpers.sh"

scratch="$(make_scratch)"
wav="$scratch/sample.wav"
make_pcm_wav "$wav"

banner "Before — a classic RIFF file"
$RIFFY info "$wav" | grep 'RIFF form'

banner "Rewrite in RF64 form (forced) while adding metadata"
$RIFFY set "$wav" --guano 'GUANO|Version=1.0' --guano 'Make=Riffy' --apply --force-rf64

banner "After — the file is now RF64, and still parses"
$RIFFY info "$wav" | grep 'RIFF form'
$RIFFY inspect "$wav"
