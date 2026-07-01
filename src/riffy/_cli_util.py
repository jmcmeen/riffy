"""Internal helpers shared by the riffy command-line interface.

Kept separate from ``__main__`` so the write-path logic (atomic replace,
``FIELD=VALUE`` parsing) can be unit-tested directly without going through argv
dispatch. These helpers back the mutating subcommands (``set``, ``chunk …``),
which all share one safety contract: dry-run by default, atomic writes, optional
``.bak`` backups.
"""

import os
import shutil
from pathlib import Path

from .wav import WAVParser


def split_assignment(item: str) -> tuple[str, str]:
    """Split a ``FIELD=VALUE`` CLI argument on the first ``=``.

    Both halves are stripped of surrounding whitespace, matching the behavior of
    ``examples/batch_correct_guano.py``'s ``parse_change``.

    Raises:
        ValueError: If ``item`` contains no ``=``.
    """
    if "=" not in item:
        raise ValueError(f"expected FIELD=VALUE, got {item!r}")
    field, _, value = item.partition("=")
    return field.strip(), value.strip()


def parse_guano_field(item: str) -> tuple[str, str, str]:
    """Parse ``[NS|]KEY=VALUE`` into ``(namespace, key, value)``.

    ``KEY`` may be a plain GUANO key (``Loc Position``) or namespaced
    (``WA|Song Meter|Prefix``); the namespace is the part before the first ``|``.
    The base (un-prefixed) namespace is the empty string.
    """
    field, value = split_assignment(item)
    namespace, sep, key = field.partition("|")
    if sep:
        return namespace.strip(), key.strip(), value
    return "", field, value


def parse_guano_key(item: str) -> tuple[str, str]:
    """Parse ``[NS|]KEY`` into ``(namespace, key)`` for a field removal."""
    namespace, sep, key = item.partition("|")
    if sep:
        return namespace.strip(), key.strip()
    return "", item.strip()


def atomic_write(
    parser: WAVParser, path: Path, *, backup: bool = False, force_rf64: bool = False
) -> None:
    """Persist ``parser`` back to ``path`` atomically (temp file + ``os.replace``).

    When ``backup`` is set, a ``<name>.bak`` copy of the original is made before
    the replace, so a crash mid-write can never lose the source file.
    """
    tmp = path.with_name(path.name + ".riffytmp")
    parser.write_wav(tmp, overwrite=True, force_rf64=force_rf64)
    if backup:
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    os.replace(tmp, path)
