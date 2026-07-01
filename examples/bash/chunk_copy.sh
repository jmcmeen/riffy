#!/usr/bin/env bash
# Copy a chunk from one WAV file into another.
# Mirrors python/copy_chunk.py, via `riffy chunk copy`.
source "$(dirname "$0")/_helpers.sh"

scratch="$(make_scratch)"
src="$scratch/source.wav"
dst="$scratch/dest.wav"
make_pcm_wav "$src"
make_pcm_wav "$dst"

# Put a GUANO block on the source only.
$RIFFY set "$src" --guano 'GUANO|Version=1.0' --guano 'Make=Riffy' --apply >/dev/null

banner "Copy the 'guan' chunk from source into dest"
$RIFFY chunk copy "$dst" guan --from "$src" --apply

banner "dest now carries the copied GUANO metadata"
$RIFFY inspect "$dst"
