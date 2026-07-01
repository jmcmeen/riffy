#!/usr/bin/env bash
# Add-or-replace a chunk with `set`, then overwrite it with `replace`.
# Mirrors python/set_chunk.py + replace_chunk.py, via `riffy chunk set/replace`.
source "$(dirname "$0")/_helpers.sh"

scratch="$(make_scratch)"
wav="$scratch/sample.wav"
make_pcm_wav "$wav"

printf 'first version' > "$scratch/v1.bin"
printf 'second, longer version' > "$scratch/v2.bin"

banner "chunk set — adds NOTE the first time"
$RIFFY chunk set "$wav" NOTE "$scratch/v1.bin" --apply
$RIFFY chunks "$wav"

banner "chunk replace — overwrites the existing NOTE in place"
$RIFFY chunk replace "$wav" NOTE "$scratch/v2.bin" --apply
$RIFFY chunks "$wav"
