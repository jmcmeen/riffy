#!/usr/bin/env bash
# Run every bash example in this directory and report the results, mirroring
# run_all.py: each example runs in its own subshell (so one failure does not stop
# the rest), from this directory, with a pass/fail summary. Exits non-zero if any
# example fails.
#
# Usage:
#   bash examples/bash/run_all.sh        # run all, print a summary
#   bash examples/bash/run_all.sh -v     # also stream each example's output
#
# Requires `riffy` on PATH, or set RIFFY="python -m riffy" (see _helpers.sh).

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

verbose=0
if [ "${1:-}" = "-v" ] || [ "${1:-}" = "--verbose" ]; then
  verbose=1
fi

self="$(basename "${BASH_SOURCE[0]}")"
failures=()
total=0

for script in *.sh; do
  # Skip this runner and any _-prefixed support module.
  case "$script" in
    "$self" | _*) continue ;;
  esac
  total=$((total + 1))
  printf '── Running %s ' "$script"
  printf '%.0s─' $(seq 1 $((48 - ${#script}))) 2>/dev/null || true
  printf '\n'

  if [ "$verbose" -eq 1 ]; then
    if bash "$script"; then
      printf '✓ %s\n' "$script"
    else
      code=$?
      failures+=("$script")
      printf '✗ %s (exit %d)\n' "$script" "$code"
    fi
  else
    if output="$(bash "$script" 2>&1)"; then
      printf '✓ %s\n' "$script"
    else
      code=$?
      failures+=("$script")
      printf '✗ %s (exit %d)\n' "$script" "$code"
      # Show the tail of the captured output to aid debugging.
      printf '%s\n' "$output" | tail -n 10
    fi
  fi
done

printf '%.0s─' $(seq 1 60); printf '\n'
passed=$((total - ${#failures[@]}))
printf 'Examples: %d/%d passed\n' "$passed" "$total"
if [ "${#failures[@]}" -gt 0 ]; then
  printf 'Failed: %s\n' "${failures[*]}"
  exit 1
fi
