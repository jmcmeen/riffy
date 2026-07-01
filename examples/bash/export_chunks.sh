#!/usr/bin/env bash
# Export a chunk's payload and the raw audio data to files.
# Mirrors python/export_chunks.py, via `riffy export`.
source "$(dirname "$0")/_helpers.sh"

scratch="$(make_scratch)"
wav="$scratch/sample.wav"
make_pcm_wav "$wav"

banner "Export the raw 'data' audio payload"
$RIFFY export "$wav" --audio "$scratch/audio.raw"

banner "Export the 'fmt ' chunk by ID"
$RIFFY export "$wav" --chunk 'fmt ' "$scratch/fmt.bin"

banner "Exported files"
ls -l "$scratch/audio.raw" "$scratch/fmt.bin" | awk '{print $5, $NF}'
