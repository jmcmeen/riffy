"""Batch-correct a GUANO metadata field across a folder of WAV recordings.

Real-world use case: a catalog of Wildlife Acoustics Song Meter Micro recordings
whose GUANO ``Loc Position`` was set from a phone's *stale* last-known GPS fix,
so every file has the wrong coordinates. This script points at a folder and,
for every ``.wav`` that carries a GUANO block, overwrites one or more fields
with corrected values — leaving all other chunks and fields untouched (riffy's
round-trip guarantee preserves them, including vendor ``WA`` fields and the
proprietary ``wamd`` chunk).

Safety:
  * Dry run by default — nothing is written until you pass ``--apply``.
  * Writes atomically (temp file + ``os.replace``), with an optional ``.bak``.
  * Re-reads each file after writing to verify the change actually took.
  * Files already holding the target value are left untouched (no needless
    rewrite of multi-hundred-MB files).

Examples:
    # See what would change (no files modified):
    python batch_correct_guano.py /data/frogpond \\
        --set "Loc Position=36.31119 -82.34027"

    # Apply the correction, keeping .bak backups:
    python batch_correct_guano.py /data/frogpond \\
        --set "Loc Position=36.31119 -82.34027" --apply --backup

    # Overwrite several fields at once (namespaced fields use 'NS|Key'):
    python batch_correct_guano.py /data/site7 \\
        --set "Loc Position=36.3 -82.3" --set "WA|Song Meter|Prefix=SITE7" --apply

Run with no folder to see a self-contained demo on temporary files.
"""

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

from _helpers import make_pcm_wav

from riffy import GuanoMetadata, WAVParser, diff

# A change is (namespace, key, new_value). The base GUANO namespace is "".
Change = tuple[str, str, str]


def parse_change(item: str) -> Change:
    """Parse a ``FIELD=VALUE`` argument into ``(namespace, key, value)``.

    ``FIELD`` may be a plain GUANO key (``Loc Position``) or namespaced
    (``WA|Song Meter|Prefix``) — the namespace is the part before the first ``|``.
    """
    if "=" not in item:
        raise ValueError(f"expected FIELD=VALUE, got {item!r}")
    field, _, value = item.partition("=")
    namespace, sep, key = field.partition("|")
    if sep:
        return (namespace.strip(), key.strip(), value.strip())
    return ("", field.strip(), value.strip())


def find_wavs(folder: Path, recursive: bool) -> list[Path]:
    """Return the ``.wav`` files under ``folder`` (case-insensitive extension)."""
    globber = folder.rglob if recursive else folder.glob
    return sorted(p for p in globber("*") if p.is_file() and p.suffix.lower() == ".wav")


def _diff_fields(guano: GuanoMetadata, changes: list[Change]) -> list[tuple[str, str | None, str]]:
    """Return ``(label, old_value, new_value)`` for each requested change."""
    rows = []
    for namespace, key, new in changes:
        label = f"{namespace}|{key}" if namespace else key
        rows.append((label, guano.get(namespace, key), new))
    return rows


def process_file(
    path: Path, changes: list[Change], *, apply: bool, backup: bool, verify: bool
) -> dict:
    """Inspect (and optionally correct) one file. Returns a result dict."""
    guano = GuanoMetadata.from_parser(WAVParser(path))
    if guano is None:
        return {"status": "skipped", "reason": "no GUANO block"}

    rows = _diff_fields(guano, changes)
    changed = any(old != new for _, old, new in rows)
    if not changed:
        return {"status": "ok", "diff": rows}  # already correct

    if not apply:
        return {"status": "dry-run", "diff": rows}

    # Apply the changes and write atomically: temp file -> os.replace.
    for namespace, key, value in changes:
        guano.set(namespace, key, value)
    parser = WAVParser(path)
    guano.write_to_parser(parser)

    backup_path = path.with_name(path.name + ".bak")
    tmp = path.with_name(path.name + ".riffytmp")
    parser.write_wav(tmp, overwrite=True)
    if backup or verify:  # verify diffs against the original, so it needs the backup
        shutil.copy2(path, backup_path)
    os.replace(tmp, path)

    # Re-read from disk to confirm the correction took.
    reloaded = GuanoMetadata.from_parser(WAVParser(path))
    assert reloaded is not None
    for namespace, key, value in changes:
        if reloaded.get(namespace, key) != value:
            return {"status": "error", "reason": f"verification failed for {key!r}", "diff": rows}

    # Optional diff-based validation: confirm ONLY the requested fields changed
    # and the audio data chunk is untouched.
    if verify:
        wav_diff = diff(backup_path, path)
        requested = {(f"{ns}|{k}" if ns else k) for ns, k, _ in changes}
        unexpected_fields = sorted(
            {d.key for d in wav_diff.fields if d.standard == "guano"} - requested
        )
        # The only chunk allowed to change is 'guan' (rewriting the GUANO text).
        unexpected_chunks = sorted(
            {c.chunk_id for c in wav_diff.changed_chunks if c.chunk_id != "guan"}
        )
        if unexpected_fields or unexpected_chunks:
            reason = (
                f"unexpected chunk change {unexpected_chunks}"
                if unexpected_chunks
                else f"unexpected field change {unexpected_fields}"
            )
            return {"status": "error", "reason": f"diff check failed: {reason}", "diff": rows}
        if not backup:  # verify borrowed the backup; remove it if the user didn't ask for one
            backup_path.unlink()
    return {"status": "written", "diff": rows, "verified": verify}


def _print_result(path: Path, result: dict, root: Path) -> None:
    rel = path.relative_to(root)
    status = result["status"]
    if status == "skipped":
        print(f"[skip]     {rel}  ({result['reason']})")
        return
    if status == "ok":
        print(f"[ok]       {rel}  (already correct)")
        return
    tag = {"dry-run": "[dry-run] ", "written": "[written] ", "error": "[ERROR]   "}[status]
    print(f"{tag}{rel}")
    for label, old, new in result["diff"]:
        marker = "" if old != new else "  (unchanged)"
        print(f"    {label}: {old!r} -> {new!r}{marker}")
    if result.get("verified"):
        print("    verified: audio data unchanged; only the requested field(s) changed")
    if status == "error":
        print(f"    !! {result['reason']}")


def run_batch(
    folder: Path,
    changes: list[Change],
    *,
    apply: bool,
    backup: bool,
    recursive: bool,
    verify: bool = False,
) -> dict:
    """Scan ``folder`` and correct matching files. Returns a summary dict."""
    wavs = find_wavs(folder, recursive)
    mode = "APPLY" if apply else "DRY RUN (no files will be modified)"
    print(f"Scanning {folder} ({'recursive' if recursive else 'top level'}) — {mode}")
    print(f"Found {len(wavs)} .wav file(s)\n")

    counts = {"written": 0, "dry-run": 0, "ok": 0, "skipped": 0, "error": 0}
    for path in wavs:
        try:
            result = process_file(path, changes, apply=apply, backup=backup, verify=verify)
        except Exception as e:  # keep going through the rest of the catalog
            result = {"status": "error", "reason": str(e), "diff": []}
        counts[result["status"]] += 1
        _print_result(path, result, folder)

    print(
        f"\nSummary: {len(wavs)} scanned | "
        f"{counts['written']} written, {counts['dry-run']} to change, "
        f"{counts['ok']} already correct, {counts['skipped']} skipped, "
        f"{counts['error']} error(s)"
    )
    if not apply and counts["dry-run"]:
        print("Re-run with --apply to write these changes (add --backup to keep .bak copies).")
    counts["scanned"] = len(wavs)
    return counts


def demo() -> None:
    """Self-contained demo on temporary files (used when no folder is given)."""
    print("No folder given — running a self-contained demo on temporary files.\n")
    wrong, corrected = "35.90000 -83.90000", "36.31119 -82.34027"

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        # Three Song Meter Micro-style recordings with the WRONG location...
        for i in range(1, 4):
            path = make_pcm_wav(folder / f"FROGPOND_2023081{i}_210000.wav")
            g = GuanoMetadata(version="1.0")
            g.make = "Wildlife Acoustics, Inc."
            g.model = "Song Meter Micro"
            g.set("", "Loc Position", wrong)
            g.set("WA", "Song Meter|Prefix", "FROGPOND")
            parser = WAVParser(path)
            g.write_to_parser(parser)
            parser.write_wav(path, overwrite=True)
        # ...and one file with no GUANO block, to show it is skipped.
        make_pcm_wav(folder / "no_metadata.wav")

        changes = [("", "Loc Position", corrected)]
        print("=== Step 1: dry run (the default) ===")
        run_batch(folder, changes, apply=False, backup=False, recursive=True)
        print("\n=== Step 2: apply the correction, verified via diff ===")
        run_batch(folder, changes, apply=True, backup=True, recursive=True, verify=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Batch-correct GUANO metadata fields across a folder of WAV files.",
    )
    parser.add_argument("folder", nargs="?", help="directory to scan; omit to run a demo")
    parser.add_argument(
        "--set",
        dest="changes",
        action="append",
        metavar="FIELD=VALUE",
        help="GUANO field to overwrite, e.g. 'Loc Position=36.3 -82.3' (repeatable)",
    )
    parser.add_argument(
        "--recursive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="recurse into sub-folders (default: on)",
    )
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    parser.add_argument("--backup", action="store_true", help="keep a .bak copy of each file")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="after writing, diff against the original to confirm only the "
        "requested field(s) changed and the audio is untouched",
    )
    args = parser.parse_args(argv)

    if args.folder is None:
        demo()
        return 0

    if not args.changes:
        parser.error("provide at least one --set FIELD=VALUE")
    folder = Path(args.folder)
    if not folder.is_dir():
        parser.error(f"not a directory: {folder}")

    try:
        changes = [parse_change(item) for item in args.changes]
    except ValueError as e:
        parser.error(str(e))

    summary = run_batch(
        folder,
        changes,
        apply=args.apply,
        backup=args.backup,
        recursive=args.recursive,
        verify=args.verify,
    )
    return 1 if summary["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
