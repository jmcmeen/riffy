#!/usr/bin/env bash
# Write RIFF INFO tags by FOURCC.
# Mirrors python/info_metadata.py, via `riffy set --info`.
source "$(dirname "$0")/_helpers.sh"

scratch="$(make_scratch)"
wav="$scratch/sample.wav"
make_pcm_wav "$wav"

banner "Set several INFO tags"
$RIFFY set "$wav" \
  --info 'INAM=Dawn Chorus' \
  --info 'IART=Field Team' \
  --info 'ICMT=Recorded at the pond' \
  --info 'ISFT=riffy' \
  --apply

banner "Read it back"
$RIFFY inspect "$wav"

banner "Remove one tag"
$RIFFY set "$wav" --remove-info ICMT --apply
$RIFFY inspect "$wav"
