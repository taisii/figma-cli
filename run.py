#!/usr/bin/env python

"""Backwards-compatible entrypoint that forwards to Codex CLI."""

import sys

from codex_cli import main as codex_main


def main() -> int:
    """Delegate execution to the Codex CLI."""
    return codex_main()


if __name__ == "__main__":
    sys.exit(main())
