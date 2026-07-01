"""Command-line inspector: ``python -m riffy <file>``.

Prints the recorder-metadata standards detected in a WAV file and their parsed
fields. Built on the standard-library ``argparse`` only, preserving riffy's
zero-dependency promise.
"""

import argparse
import json
import sys
from collections.abc import Sequence

from .exceptions import RiffyError
from .metadata.recording import dump_metadata


def _format_value(value: object) -> str:
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _print_human(data: dict) -> None:
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="riffy",
        description="Inspect the recorder metadata embedded in a WAV file.",
    )
    parser.add_argument("file", help="Path to a WAV file")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the metadata as JSON instead of human-readable text",
    )
    args = parser.parse_args(argv)

    try:
        data = dump_metadata(args.file)
    except (RiffyError, FileNotFoundError) as e:
        print(f"riffy: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        _print_human(data)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
