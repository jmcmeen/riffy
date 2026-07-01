"""Run every example script in this directory and report the results.

Each example is executed as a separate subprocess (so one failure does not stop
the rest), with this directory as the working directory since the examples
create and clean up their own scratch files there.

Usage:
    python examples/run_all.py            # run all, print a summary
    python examples/run_all.py -v         # also stream each example's output

Exits non-zero if any example fails.
"""

import argparse
import subprocess
import sys
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent


def _example_scripts() -> list[Path]:
    """Return the runnable example scripts.

    Skips this runner itself and any ``_``-prefixed support module (e.g.
    ``_helpers.py``).
    """
    return sorted(
        p
        for p in EXAMPLES_DIR.glob("*.py")
        if p.name != Path(__file__).name and not p.name.startswith("_")
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run all riffy example scripts.")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Stream each example's stdout/stderr instead of capturing it",
    )
    args = parser.parse_args(argv)

    scripts = _example_scripts()
    if not scripts:
        print("No example scripts found.")
        return 0

    failures: list[str] = []
    for script in scripts:
        print(f"── Running {script.name} ".ljust(60, "─"))
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=EXAMPLES_DIR,
            capture_output=not args.verbose,
            text=True,
        )
        if result.returncode == 0:
            print(f"✓ {script.name}")
        else:
            failures.append(script.name)
            print(f"✗ {script.name} (exit {result.returncode})")
            if not args.verbose and result.stderr:
                # Show the tail of the captured error to aid debugging.
                tail = "\n".join(result.stderr.strip().splitlines()[-10:])
                print(tail)

    total = len(scripts)
    passed = total - len(failures)
    print("─" * 60)
    print(f"Examples: {passed}/{total} passed")
    if failures:
        print("Failed: " + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
