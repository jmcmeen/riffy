"""Command-line interface: ``riffy`` (or ``python -m riffy``).

Built on the standard-library ``argparse`` only, preserving riffy's
zero-dependency promise. The top-level dispatch is hand-rolled (rather than
using ``argparse`` sub-parsers) so a bare ``riffy <file>`` — and the historical
``riffy --json <file>`` — keep defaulting to ``inspect``.

Read-only commands:

- ``riffy inspect <file>`` — print the recorder metadata in a WAV file (default).
- ``riffy diff <a> <b>`` — chunk- and metadata-level differences between two files.
- ``riffy chunks <file>`` — list every chunk with its size and offset.
- ``riffy info <file>`` — show the audio format and file details.
- ``riffy export <file> (--chunk ID | --audio) <out>`` — write a chunk or the raw
  audio payload to a file.

Write commands (``set`` and ``chunk …``) share one safety contract: they are a
**dry run by default**, only touching the file when ``--apply`` is given; writes
are atomic (temp file + ``os.replace``); ``--backup`` keeps a ``.bak`` copy; and
``--force-rf64`` forces the RF64/BW64 large-file form.

- ``riffy set <file> [--guano NS|KEY=VAL] [--info FOURCC=VAL] [--bext ATTR=VAL] …``
- ``riffy chunk add|replace|set <file> ID <data-file>``
- ``riffy chunk copy <file> ID --from <src.wav>``
- ``riffy chunk remove <file> ID [--index N]``
"""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from ._cli_util import atomic_write, parse_guano_field, parse_guano_key, split_assignment
from .diff import diff
from .exceptions import RiffyError
from .metadata.bext import BextMetadata
from .metadata.guano import GuanoMetadata
from .metadata.info import InfoMetadata
from .metadata.recording import dump_metadata
from .wav import WAVParser


def _format_value(value: object) -> str:
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _size(value: int | None) -> str:
    return "—" if value is None else f"{value:,}B"


def _add_write_flags(parser: argparse.ArgumentParser) -> None:
    """Add the shared safety-contract flags to a mutating subcommand's parser."""
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    parser.add_argument("--backup", action="store_true", help="keep a .bak copy of the original")
    parser.add_argument(
        "--force-rf64", action="store_true", help="always emit the RF64/BW64 large-file form"
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")


def _report_write(path: Path, changes: list[str], *, applied: bool, as_json: bool) -> int:
    """Print the outcome of a write command in the shared dry-run/written format."""
    status = "written" if applied else "dry-run"
    if as_json:
        print(
            json.dumps(
                {"status": status, "path": str(path), "changes": changes},
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    print(f"[{status}] {path}")
    for change in changes:
        print(f"    {change}")
    if not applied:
        print("Re-run with --apply to write these changes (add --backup to keep a .bak).")
    return 0


# --------------------------------------------------------------------------- #
# inspect (default)
# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #
# diff
# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #
# chunks
# --------------------------------------------------------------------------- #


def _cmd_chunks(argv: Sequence[str] | None) -> int:
    parser = argparse.ArgumentParser(
        prog="riffy chunks",
        description="List every chunk in a WAV file with its size and byte offset.",
    )
    parser.add_argument("file", help="Path to a WAV file")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args(argv)

    try:
        wav = WAVParser(args.file)
        listing = wav.list_chunks()
    except (RiffyError, FileNotFoundError) as e:
        print(f"riffy: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(
            json.dumps(
                {"file": str(wav.file_path), "riff_form": wav.riff_form, "chunks": listing},
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    print(f"File:      {wav.file_path}")
    print(f"RIFF form: {wav.riff_form}")
    print(f"\n{'ID':<6} {'idx':>3} {'size':>14} {'offset':>12}")
    for chunk_id, occurrences in listing.items():
        for index, occ in enumerate(occurrences):
            print(f"{chunk_id:<6} {index:>3} {_size(occ['size']):>14} {occ['offset']:>12,}")
    return 0


# --------------------------------------------------------------------------- #
# info
# --------------------------------------------------------------------------- #


def _cmd_info(argv: Sequence[str] | None) -> int:
    parser = argparse.ArgumentParser(
        prog="riffy info",
        description="Show the audio format and file details of a WAV file.",
    )
    parser.add_argument("file", help="Path to a WAV file")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args(argv)

    try:
        wav = WAVParser(args.file)
        info = wav.get_info()
    except (RiffyError, FileNotFoundError) as e:
        print(f"riffy: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({**info, "riff_form": wav.riff_form}, indent=2, ensure_ascii=False))
        return 0

    fmt = info["format"]
    kind = "PCM" if fmt["is_pcm"] else "non-PCM"
    print(f"File:        {info['file_path']}")
    print(f"RIFF form:   {wav.riff_form}")
    print(
        f"Format:      {fmt['sample_rate']} Hz, {fmt['channels']} ch, "
        f"{fmt['bits_per_sample']}-bit ({kind})"
    )
    print(f"Byte rate:   {fmt['byte_rate']:,} B/s")
    print(f"Duration:    {info['duration_seconds']:.3f} s")
    print(f"Samples:     {info['sample_count']:,}")
    print(f"Audio data:  {info['audio_data_size']:,} B")
    print(f"File size:   {info['file_size']:,} B")
    return 0


# --------------------------------------------------------------------------- #
# export
# --------------------------------------------------------------------------- #


def _cmd_export(argv: Sequence[str] | None) -> int:
    parser = argparse.ArgumentParser(
        prog="riffy export",
        description="Export a chunk's payload, or the raw audio data, to a file.",
    )
    parser.add_argument("file", help="Path to a WAV file")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--chunk", metavar="ID", help="chunk ID to export (e.g. 'guan', 'data')")
    target.add_argument("--audio", action="store_true", help="export the raw 'data' audio payload")
    parser.add_argument("out", help="output file path")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args(argv)

    try:
        wav = WAVParser(args.file)
        if args.audio:
            written = wav.export_audio_data(args.out)
            what = "audio"
        else:
            written = wav.export_chunk(args.chunk, args.out)
            what = args.chunk
    except (RiffyError, FileNotFoundError, OSError) as e:
        print(f"riffy: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(
            json.dumps(
                {"exported": what, "bytes": written, "path": args.out},
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(f"Wrote {written:,} bytes to {args.out}")
    return 0


# --------------------------------------------------------------------------- #
# set (metadata field editing)
# --------------------------------------------------------------------------- #

# bext is a fixed C-struct, not sparse key-value text, so its attributes are set
# by name with explicit types (the ``umid`` bytes field is not settable here).
_BEXT_STR_ATTRS = frozenset(
    {
        "description",
        "originator",
        "originator_reference",
        "origination_date",
        "origination_time",
        "coding_history",
    }
)
_BEXT_INT_ATTRS = frozenset(
    {
        "time_reference",
        "version",
        "loudness_value",
        "loudness_range",
        "max_true_peak_level",
        "max_momentary_loudness",
        "max_short_term_loudness",
    }
)


def _guano_label(namespace: str, key: str) -> str:
    return f"{namespace}|{key}" if namespace else key


def _set_bext_attr(bext: BextMetadata, attr: str, value: str) -> None:
    if attr in _BEXT_STR_ATTRS:
        setattr(bext, attr, value)
    elif attr in _BEXT_INT_ATTRS:
        try:
            setattr(bext, attr, int(value))
        except ValueError as e:
            raise ValueError(f"bext {attr!r} expects an integer, got {value!r}") from e
    else:
        known = ", ".join(sorted(_BEXT_STR_ATTRS | _BEXT_INT_ATTRS))
        raise ValueError(f"unknown bext attribute {attr!r}; expected one of: {known}")


def _apply_metadata_changes(wav: WAVParser, args: argparse.Namespace) -> list[str]:
    """Apply the requested field edits to ``wav`` in memory; return a change log."""
    changes: list[str] = []

    if args.guano or args.remove_guano:
        guano = GuanoMetadata.from_parser(wav) or GuanoMetadata()
        for item in args.guano:
            namespace, key, value = parse_guano_field(item)
            guano.set(namespace, key, value)
            changes.append(f"guano {_guano_label(namespace, key)} = {value!r}")
        for item in args.remove_guano:
            namespace, key = parse_guano_key(item)
            guano.remove(namespace, key)
            changes.append(f"guano {_guano_label(namespace, key)} removed")
        guano.write_to_parser(wav)

    if args.info or args.remove_info:
        info = InfoMetadata.from_parser(wav) or InfoMetadata()
        for item in args.info:
            fourcc, value = split_assignment(item)
            info.set(fourcc, value)
            changes.append(f"info {fourcc} = {value!r}")
        for fourcc in args.remove_info:
            info.remove(fourcc)
            changes.append(f"info {fourcc} removed")
        info.write_to_parser(wav)

    if args.bext:
        bext = BextMetadata.from_parser(wav) or BextMetadata()
        for item in args.bext:
            attr, value = split_assignment(item)
            _set_bext_attr(bext, attr, value)
            changes.append(f"bext {attr} = {value!r}")
        bext.write_to_parser(wav)

    return changes


def _cmd_set(argv: Sequence[str] | None) -> int:
    parser = argparse.ArgumentParser(
        prog="riffy set",
        description="Edit recorder-metadata fields (GUANO / RIFF INFO / bext) in a WAV file.",
    )
    parser.add_argument("file", help="Path to a WAV file")
    parser.add_argument(
        "--guano",
        action="append",
        default=[],
        metavar="NS|KEY=VAL",
        help="set a GUANO field, e.g. 'Make=Riffy' or 'WA|Song Meter|Prefix=SITE7' (repeatable)",
    )
    parser.add_argument(
        "--info",
        action="append",
        default=[],
        metavar="FOURCC=VAL",
        help="set a RIFF INFO tag by FOURCC, e.g. 'IART=Field Team' (repeatable)",
    )
    parser.add_argument(
        "--bext",
        action="append",
        default=[],
        metavar="ATTR=VAL",
        help="set a bext attribute, e.g. 'description=Dawn chorus' (repeatable)",
    )
    parser.add_argument(
        "--remove-guano",
        action="append",
        default=[],
        metavar="NS|KEY",
        help="remove a GUANO field (repeatable)",
    )
    parser.add_argument(
        "--remove-info",
        action="append",
        default=[],
        metavar="FOURCC",
        help="remove a RIFF INFO tag (repeatable)",
    )
    _add_write_flags(parser)
    args = parser.parse_args(argv)

    if not (args.guano or args.info or args.bext or args.remove_guano or args.remove_info):
        parser.error("nothing to do: pass at least one --guano/--info/--bext/--remove-* option")

    file_path = Path(args.file)
    try:
        wav = WAVParser(file_path)
        changes = _apply_metadata_changes(wav, args)
        if args.apply:
            atomic_write(wav, file_path, backup=args.backup, force_rf64=args.force_rf64)
    except (RiffyError, FileNotFoundError, ValueError, OSError) as e:
        print(f"riffy: {e}", file=sys.stderr)
        return 1

    return _report_write(file_path, changes, applied=args.apply, as_json=args.json)


# --------------------------------------------------------------------------- #
# chunk add|replace|set|copy|remove
# --------------------------------------------------------------------------- #


def _cmd_chunk_write(op: str, argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog=f"riffy chunk {op}",
        description=f"{op.capitalize()} a chunk's data from a binary file.",
    )
    parser.add_argument("file", help="Path to a WAV file")
    parser.add_argument("chunk_id", metavar="ID", help="4-character chunk ID")
    parser.add_argument("data_file", metavar="data-file", help="file holding the raw chunk bytes")
    _add_write_flags(parser)
    args = parser.parse_args(argv)

    file_path = Path(args.file)
    try:
        data = Path(args.data_file).read_bytes()
        wav = WAVParser(file_path)
        method = {"add": wav.add_chunk, "replace": wav.replace_chunk, "set": wav.set_chunk}[op]
        method(args.chunk_id, data)
        if args.apply:
            atomic_write(wav, file_path, backup=args.backup, force_rf64=args.force_rf64)
    except (RiffyError, FileNotFoundError, ValueError, OSError) as e:
        print(f"riffy: {e}", file=sys.stderr)
        return 1

    change = f"chunk {op} {args.chunk_id!r} ({len(data):,} bytes from {args.data_file})"
    return _report_write(file_path, [change], applied=args.apply, as_json=args.json)


def _cmd_chunk_copy(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="riffy chunk copy",
        description="Copy a chunk from another WAV file into this one.",
    )
    parser.add_argument("file", help="Path to the destination WAV file")
    parser.add_argument("chunk_id", metavar="ID", help="4-character chunk ID to copy")
    parser.add_argument("--from", dest="source", required=True, metavar="SRC", help="source WAV")
    _add_write_flags(parser)
    args = parser.parse_args(argv)

    file_path = Path(args.file)
    try:
        wav = WAVParser(file_path)
        source = WAVParser(args.source)
        wav.copy_chunk_from_parser(args.chunk_id, source)
        if args.apply:
            atomic_write(wav, file_path, backup=args.backup, force_rf64=args.force_rf64)
    except (RiffyError, FileNotFoundError, ValueError, OSError) as e:
        print(f"riffy: {e}", file=sys.stderr)
        return 1

    change = f"chunk copy {args.chunk_id!r} from {args.source}"
    return _report_write(file_path, [change], applied=args.apply, as_json=args.json)


def _cmd_chunk_remove(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="riffy chunk remove",
        description="Remove a chunk (all occurrences, or one by index).",
    )
    parser.add_argument("file", help="Path to a WAV file")
    parser.add_argument("chunk_id", metavar="ID", help="4-character chunk ID to remove")
    parser.add_argument(
        "--index", type=int, default=None, help="occurrence to remove (default: all occurrences)"
    )
    _add_write_flags(parser)
    args = parser.parse_args(argv)

    file_path = Path(args.file)
    try:
        wav = WAVParser(file_path)
        wav.remove_chunk(args.chunk_id, args.index)
        if args.apply:
            atomic_write(wav, file_path, backup=args.backup, force_rf64=args.force_rf64)
    except (RiffyError, FileNotFoundError, ValueError, OSError) as e:
        print(f"riffy: {e}", file=sys.stderr)
        return 1

    scope = f" [{args.index}]" if args.index is not None else " (all occurrences)"
    change = f"chunk remove {args.chunk_id!r}{scope}"
    return _report_write(file_path, [change], applied=args.apply, as_json=args.json)


def _print_chunk_help() -> None:
    print("usage: riffy chunk <add|replace|set|copy|remove> <file> ID ...")
    print("\nModify the chunks of a WAV file (dry run unless --apply is given).\n")
    print("Operations:")
    print("  add <file> ID <data-file>       Append a chunk from a binary file")
    print("  replace <file> ID <data-file>   Replace an existing chunk's data")
    print("  set <file> ID <data-file>       Add the chunk, or replace it if present")
    print("  copy <file> ID --from <src>     Copy a chunk from another WAV file")
    print("  remove <file> ID [--index N]    Remove a chunk (all occurrences by default)")


def _cmd_chunk(argv: Sequence[str] | None) -> int:
    args = list(argv or [])
    if not args or args[0] in ("-h", "--help"):
        _print_chunk_help()
        return 0

    op, rest = args[0], args[1:]
    if op in ("add", "replace", "set"):
        return _cmd_chunk_write(op, rest)
    if op == "copy":
        return _cmd_chunk_copy(rest)
    if op == "remove":
        return _cmd_chunk_remove(rest)

    print(
        f"riffy: unknown chunk operation {op!r} (try add/replace/set/copy/remove)",
        file=sys.stderr,
    )
    return 1


# --------------------------------------------------------------------------- #
# top-level dispatch
# --------------------------------------------------------------------------- #

_COMMANDS = {
    "inspect": _cmd_inspect,
    "diff": _cmd_diff,
    "chunks": _cmd_chunks,
    "info": _cmd_info,
    "export": _cmd_export,
    "set": _cmd_set,
    "chunk": _cmd_chunk,
}


def _print_top_help() -> None:
    print("usage: riffy [inspect] <file> | riffy <command> ...")
    print("\nInspect, compare, and edit recorder metadata and chunks in WAV files.\n")
    print("Read commands:")
    print("  inspect <file>            Show the recorder metadata in a WAV file (default)")
    print("  diff <a> <b>              Show chunk- and metadata-level differences")
    print("  chunks <file>             List every chunk with its size and offset")
    print("  info <file>               Show the audio format and file details")
    print("  export <file> ... <out>   Write a chunk (--chunk ID) or audio (--audio) to a file")
    print("\nWrite commands (dry run unless --apply; --backup keeps a .bak):")
    print("  set <file> --guano/--info/--bext KEY=VAL   Edit recorder-metadata fields")
    print("  chunk <add|replace|set|copy|remove> ...    Modify chunks")
    print("\nRun 'riffy <command> -h' for command options.")


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        _print_top_help()
        return 0

    command = _COMMANDS.get(args[0])
    if command is not None:
        return command(args[1:])

    # Bare path (and the historical `riffy --json <file>`) defaults to inspect.
    return _cmd_inspect(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
