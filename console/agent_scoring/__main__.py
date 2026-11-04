"""Command line of the scorer: `python -m agent_scoring agent-score [...]`, run from console/.

Main goal: rescore runs by hand (the console also scores on its own, see agent_console/autoscore.py).
Example: `cd console && .venv/bin/python -m agent_scoring agent-score --since 2026-01-01`
"""

from __future__ import annotations

import argparse
import sys

from . import agent_score


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="agent_scoring")
    sub = ap.add_subparsers(dest="cmd", required=True)
    agent_score.add_parser(sub)
    a = ap.parse_args(argv)
    return int(a.fn(a) or 0)


if __name__ == "__main__":
    sys.exit(main())
