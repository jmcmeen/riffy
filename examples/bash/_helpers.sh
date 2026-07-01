# Shared helpers for the riffy *bash* examples, sourced (not run) by each script.
#
# Files whose name starts with "_" are treated as support modules, not runnable
# examples, so run_all.sh skips them.
#
# Every example drives the `riffy` command-line interface. Set RIFFY to override
# how it is invoked; it defaults to the installed `riffy` entry point, falling
# back to `python -m riffy` when that is not on PATH.

set -euo pipefail

if [ -z "${RIFFY:-}" ]; then
  if command -v riffy >/dev/null 2>&1; then
    RIFFY="riffy"
  else
    RIFFY="python -m riffy"
  fi
fi

# banner "Title" — print a readable section header, mirroring _helpers.py.
banner() {
  printf '\n=== %s ===\n' "$1"
}

# One scratch base per example process, cleaned up on exit. The base (and its
# EXIT trap) are established here at source time — in the caller's shell — so
# that make_scratch can safely run inside a `$(...)` command substitution
# without its own subshell tearing the directory down prematurely.
_RIFFY_SCRATCH_BASE="$(mktemp -d)"
trap 'rm -rf "$_RIFFY_SCRATCH_BASE"' EXIT

# make_scratch — create a fresh working directory under the scratch base and
# echo its path for the caller to capture.
make_scratch() {
  mktemp -d "$_RIFFY_SCRATCH_BASE/ex.XXXXXX"
}

# make_pcm_wav <path> [seconds] — synthesize a minimal PCM WAV file. The CLI is
# deliberately about editing/inspecting existing files, so bootstrapping a
# sample file is done here with a short Python snippet (reusing riffy is not
# required just to lay down bytes).
make_pcm_wav() {
  local path="$1"
  local seconds="${2:-0.1}"
  python - "$path" "$seconds" <<'PY'
import struct, sys
path, seconds = sys.argv[1], float(sys.argv[2])
sample_rate, channels, bits = 44100, 1, 16
block_align = channels * bits // 8
byte_rate = sample_rate * block_align
frames = int(sample_rate * seconds)
audio = bytes(i % 256 for i in range(frames * block_align))
fmt = struct.pack("<HHIIHH", 1, channels, sample_rate, byte_rate, block_align, bits)
body = b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(audio)) + audio
with open(path, "wb") as f:
    f.write(b"RIFF" + struct.pack("<I", len(body) + 4) + b"WAVE" + body)
PY
}

# make_icmt_wav <path> <comment> — synthesize a WAV carrying a RIFF INFO ICMT
# comment, used by the AudioMoth-decode example (the decoder reads that tag).
make_icmt_wav() {
  local path="$1"
  local comment="$2"
  python - "$path" "$comment" <<'PY'
import struct, sys
path, comment = sys.argv[1], sys.argv[2]
sample_rate, channels, bits = 48000, 1, 16
block_align = channels * bits // 8
byte_rate = sample_rate * block_align
audio = bytes(64 for _ in range(block_align * 32))
fmt = struct.pack("<HHIIHH", 1, channels, sample_rate, byte_rate, block_align, bits)

payload = comment.encode("latin-1") + b"\x00"
if len(payload) % 2:
    payload += b"\x00"
info = b"INFO" + b"ICMT" + struct.pack("<I", len(payload)) + payload
list_chunk = b"LIST" + struct.pack("<I", len(info)) + info

body = (
    b"fmt " + struct.pack("<I", len(fmt)) + fmt
    + b"data" + struct.pack("<I", len(audio)) + audio
    + list_chunk
)
with open(path, "wb") as f:
    f.write(b"RIFF" + struct.pack("<I", len(body) + 4) + b"WAVE" + body)
PY
}

# make_ixml_wav <path> — synthesize a WAV carrying an iXML chunk with a small
# project/scene document, used by the iXML inspect example.
make_ixml_wav() {
  local path="$1"
  python - "$path" <<'PY'
import struct, sys
path = sys.argv[1]
sample_rate, channels, bits = 48000, 1, 16
block_align = channels * bits // 8
byte_rate = sample_rate * block_align
audio = bytes(64 for _ in range(block_align * 32))
fmt = struct.pack("<HHIIHH", 1, channels, sample_rate, byte_rate, block_align, bits)

doc = (
    b"<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
    b"<BWFXML><PROJECT>Dawn Survey</PROJECT><SCENE>Pond A</SCENE></BWFXML>"
)
if len(doc) % 2:
    doc += b" "
ixml = b"iXML" + struct.pack("<I", len(doc)) + doc

body = (
    b"fmt " + struct.pack("<I", len(fmt)) + fmt
    + b"data" + struct.pack("<I", len(audio)) + audio
    + ixml
)
with open(path, "wb") as f:
    f.write(b"RIFF" + struct.pack("<I", len(body) + 4) + b"WAVE" + body)
PY
}
