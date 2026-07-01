#!/usr/bin/env bash
# Inspect a WAV carrying an iXML document. `riffy inspect` reads iXML (read-only
# in v0.3.0) and includes it among the detected metadata standards.
# Mirrors python/ixml_metadata.py (which navigates the tree via the library).
source "$(dirname "$0")/_helpers.sh"

scratch="$(make_scratch)"
wav="$scratch/ixml.wav"
make_ixml_wav "$wav"

banner "riffy inspect — iXML is one of the detected standards"
$RIFFY inspect "$wav"

banner "riffy inspect --json"
$RIFFY inspect "$wav" --json
