#!/usr/bin/env bash
# Demonstrate the dry-run / --apply write guard: without --apply, nothing on
# disk changes. Mirrors python/overwrite_wav.py's safety concept, via the CLI's
# shared write contract.
source "$(dirname "$0")/_helpers.sh"

scratch="$(make_scratch)"
wav="$scratch/sample.wav"
make_pcm_wav "$wav"

before="$(cksum "$wav" | awk '{print $1}')"

banner "Dry run — reports the change but writes nothing"
$RIFFY set "$wav" --guano 'GUANO|Version=1.0' --guano 'Make=Riffy'
after_dryrun="$(cksum "$wav" | awk '{print $1}')"
if [ "$before" = "$after_dryrun" ]; then
  echo "OK: file checksum unchanged after the dry run ($before)"
else
  echo "ERROR: dry run modified the file!" >&2
  exit 1
fi

banner "Apply — now the file changes"
$RIFFY set "$wav" --guano 'GUANO|Version=1.0' --guano 'Make=Riffy' --apply
after_apply="$(cksum "$wav" | awk '{print $1}')"
if [ "$before" != "$after_apply" ]; then
  echo "OK: file checksum changed after --apply ($before -> $after_apply)"
else
  echo "ERROR: --apply did not modify the file!" >&2
  exit 1
fi
