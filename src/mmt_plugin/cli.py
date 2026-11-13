"""The ``mmt-plugin`` command line.

Exit codes:

- ``0``: success (``--help``, ``--version``).
- ``2``: usage error (an unknown option, or no option at all).

Commands (``validate``, ``generate``, ``build``, ...) come in later tasks.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from mmt_plugin import __version__

PROG = "mmt-plugin"

EXIT_OK = 0
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for ``mmt-plugin``."""
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Generate, build and test mmt-dpi protocol plugins.",
        epilog=f"Exit codes: {EXIT_OK} success, {EXIT_USAGE} usage error.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{PROG} {__version__}",
        help="print the version and exit",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run ``mmt-plugin`` and return its exit code."""
    parser = build_parser()
    args = sys.argv[1:] if argv is None else list(argv)
    parser.parse_args(args)
    # --help and --version exit inside parse_args; no command exists yet.
    parser.print_usage(sys.stderr)
    print(f"{PROG}: error: no command given (try --help)", file=sys.stderr)
    return EXIT_USAGE
