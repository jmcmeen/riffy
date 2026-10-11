"""Move CHANGELOG.md's [Unreleased] entries under a new version heading.

Usage: roll_changelog.py CHANGELOG TAG PREVIOUS_TAG DATE NOTES_OUT [TAG_ALREADY_AT_HEAD]

Called by release.yml. Writes the release notes to NOTES_OUT and edits the
changelog in place; touches neither when there is nothing to release:

- [Unreleased] has entries: they become ``## [X.Y.Z] - DATE`` and an empty
  [Unreleased] is left above them.
- [Unreleased] is empty but the commit already shipped as another tag (a manual
  minor/major bump after the automatic patch): a short ``## [X.Y.Z]`` entry
  points at that release, whose entries become the notes.

Keep a Changelog link references at the bottom are updated when present.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HEADING = re.compile(r"^## \[(?P<name>[^\]]+)\]", re.MULTILINE)
LINKS = re.compile(r"^\[[^\]]+\]: ", re.MULTILINE)


def section(text: str, name: str) -> tuple[int, int, int] | None:
    """(heading start, body start, body end) of the ``## [name]`` section."""
    for m in HEADING.finditer(text):
        if m.group("name") == name:
            body = text.index("\n", m.start()) + 1
            nxt = HEADING.search(text, body)
            links = LINKS.search(text, body)
            ends = [x.start() for x in (nxt, links) if x] + [len(text)]
            return m.start(), body, min(ends)
    return None


def update_links(text: str, version: str, base: str) -> str:
    """Point [Unreleased] at the new tag and add a link for the new version."""
    m = re.search(r"^\[Unreleased\]: (?P<repo>\S+)/compare/\S+\.\.\.HEAD$", text, re.M)
    if not m:
        return text
    repo, tag = m.group("repo"), f"v{version}"
    link = f"{repo}/compare/{base}...{tag}" if base else f"{repo}/releases/tag/{tag}"
    new = f"[Unreleased]: {repo}/compare/{tag}...HEAD\n[{version}]: {link}"
    return text[: m.start()] + new + text[m.end() :]


def main(path: str, tag: str, previous: str, date: str, notes_out: str, at_head: str = "") -> None:
    file = Path(path)
    text = file.read_text()
    version = tag.removeprefix("v")
    unreleased = section(text, "Unreleased")
    if unreleased is None:
        return
    _, body_start, body_end = unreleased
    body = text[body_start:body_end].strip()
    base = previous
    if body:
        notes = body
        rolled = f"\n## [{version}] - {date}\n\n{body}\n\n"
    elif at_head and (shipped := section(text, at_head.removeprefix("v"))):
        shipped_body = text[shipped[1] : shipped[2]].strip()
        base = at_head
        notes = f"Same code as {at_head}, released as {tag}.\n\n{shipped_body}".strip()
        rolled = f"\n## [{version}] - {date}\n\nSame code as {at_head}, released as {tag}.\n\n"
    else:
        return

    text = text[:body_start] + rolled + text[body_end:].lstrip("\n")
    file.write_text(update_links(text, version, base))
    Path(notes_out).write_text(notes + "\n")


if __name__ == "__main__":
    main(*sys.argv[1:])
