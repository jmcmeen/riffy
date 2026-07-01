"""Command-line interface: ``python -m riffy``.

Two subcommands, built on the standard-library ``argparse`` only (preserving
riffy's zero-dependency promise):

- ``riffy inspect <file>`` — print the recorder metadata in a WAV file. This is
  the default, so ``python -m riffy <file>`` also works.
- ``riffy diff <a> <b>`` — show the chunk- and metadata-level differences between
  two WAV files.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict

from .diff import diff
from .exceptions import RiffyError
from .metadata.recording import dump_metadata


def _format_value(value: object) -> str:
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _print_inspect(data: dict) -> None:
    print(f"File:      {data['file']}")
    print(f"RIFF form: {data['riff_form']}")
    fmt = data["format"]
    print(f"Format:    {fmt['sample_rate']} Hz, {fmt['channels']} ch, {fmt['bits_per_sample']}-bit")
    sources = data["sources"]
    print(f"Metadata:  {', '.join(sources) if sources else '(none detected)'}")

    for source in sources:
        section = data.get(source)
        if not section:
            continue
        print(f"\n[{source}]")
        for key, value in section.items():
            print(f"  {key}: {_format_value(value)}")


def _cmd_inspect(argv: Sequence[str] | None) -> int:
    parser = argparse.ArgumentParser(
        prog="riffy inspect",
        description="Inspect the recorder metadata embedded in a WAV file.",
    )
    parser.add_argument("file", help="Path to a WAV file")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args(argv)

    try:
        data = dump_metadata(args.file)
    except (RiffyError, FileNotFoundError) as e:
        print(f"riffy: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        _print_inspect(data)
    return 0


def _size(value: int | None) -> str:
    return "—" if value is None else f"{value:,}B"


def _cmd_diff(argv: Sequence[str] | None) -> int:
    parser = argparse.ArgumentParser(
        prog="riffy diff",
        description="Show the chunk- and metadata-level differences between two WAV files.",
    )
    parser.add_argument("a", help="First WAV file")
    parser.add_argument("b", help="Second WAV file")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    parser.add_argument("--all", action="store_true", help="Include unchanged chunks")
    args = parser.parse_args(argv)

    try:
        result = diff(args.a, args.b, include_unchanged=args.all)
    except (RiffyError, FileNotFoundError) as e:
        print(f"riffy: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
        return 0

    print(f"A: {result.path_a} ({result.form_a})")
    print(f"B: {result.path_b} ({result.form_b})")
    if result.form_a != result.form_b:
        print(f"RIFF form changed: {result.form_a} -> {result.form_b}")

    print("\nChunks:")
    if result.chunks:
        for c in result.chunks:
            suffix = f" [{c.index}]" if c.index else ""
            print(f"  {c.chunk_id}{suffix}: {c.status}  ({_size(c.size_a)} -> {_size(c.size_b)})")
    else:
        print("  (no chunk changes)")

    print("\nMetadata fields:")
    if result.fields:
        for f in result.fields:
            print(f"  [{f.standard}] {f.key}: {f.old!r} -> {f.new!r}  ({f.status})")
    else:
        print("  (no metadata changes)")

    print("\nFiles are identical." if result.identical else "\nFiles differ.")
    return 0


def _print_top_help() -> None:
    print("usage: riffy [inspect] <file> | riffy diff <a> <b>")
    print("\nInspect and compare recorder metadata in WAV files.\n")
    print("Commands:")
    print("  inspect <file>   Show the recorder metadata in a WAV file (default)")
    print("  diff <a> <b>     Show chunk- and metadata-level differences")
    print("\nRun 'riffy <command> -h' for command options.")


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    # Subcommand dispatch. "inspect" is the default, so a bare `riffy <file>`
    # (and the historical `riffy --json <file>`) keeps working.
    if args and args[0] == "diff":
        return _cmd_diff(args[1:])
    if args and args[0] == "inspect":
        return _cmd_inspect(args[1:])
    if not args or args[0] in ("-h", "--help"):
        _print_top_help()
        return 0
    return _cmd_inspect(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
