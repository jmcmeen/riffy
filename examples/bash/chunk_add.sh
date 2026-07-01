#!/usr/bin/env bash
# Append a new chunk from a binary file.
# Mirrors python/add_chunk.py, via `riffy chunk add`.
source "$(dirname "$0")/_helpers.sh"

scratch="$(make_scratch)"
wav="$scratch/sample.wav"
make_pcm_wav "$wav"
printf 'a custom payload' > "$scratch/note.bin"

banner "Dry run (default)"
$RIFFY chunk add "$wav" NOTE "$scratch/note.bin"

banner "Apply, keeping a .bak"
$RIFFY chunk add "$wav" NOTE "$scratch/note.bin" --apply --backup

banner "Chunks now include NOTE"
$RIFFY chunks "$wav"
