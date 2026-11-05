"""`python -m agent_console compare <KEY> <KEY> [--json]` (EXP1-R22C): the comparison on the command line.

Main goal: print the same comparison as the page, as a text table or as JSON.
Does: refresh the console's index first, but only when it was built with this process's time zone, key patterns, console home and checkout
(else it refuses, nothing written), and never runs the git fetch. Exit codes: 0 done, 1 the index cannot be opened or refreshed, 2 usage, refusal
or unknown key.
Does not: start the server, write the logs, or print anything but figures, keys and its own messages (CON-035).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import compare, compare_format, config
from .pricing import Pricing
from .store import INDEX_VALUES, Store, index_check


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):
        """Usage, then the message with control characters shown as text (a typed argument is echoed by argparse)."""
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {compare_format.safe(message)}\n")


def _parser() -> argparse.ArgumentParser:
    p = _Parser(prog="python -m agent_console compare", description="Compare two tickets side by side.", allow_abbrev=False)
    p.add_argument("a", metavar="KEY_A")
    p.add_argument("b", metavar="KEY_B")
    p.add_argument("--json", action="store_true", help="print the stable JSON tree instead of the text table")
    return p


def _error(db_path: Path, name: str) -> int:
    print(f"compare: error: the index at {db_path} could not be opened or refreshed ({name})", file=sys.stderr)
    return 1


def _refusal(db_path: Path, differ: list[str], missing: list[str]) -> int:
    if differ:
        names = ", ".join(sorted(differ + missing, key=INDEX_VALUES.index))
        print(f"compare: refused: the index at {db_path} was built with another {names}; run compare with the console's settings (nothing written)",
              file=sys.stderr)
    else:
        print(f"compare: refused: the index at {db_path} does not record its {', '.join(missing)}; "
              "start the console once with this checkout, then retry (nothing written)", file=sys.stderr)
    return 2


def main(argv: list[str]) -> int:
    parser = _parser()
    try:
        ns = parser.parse_args(argv)
    except SystemExit as e:                     # argparse: usage on stderr, code 2 (or 0 for -h)
        return int(e.code or 0)
    empty = [n for n, k in (("KEY_A", ns.a), ("KEY_B", ns.b)) if not k.strip()]
    if empty:
        try:
            parser.error(f"empty key: {', '.join(empty)}")
        except SystemExit as e:
            return int(e.code or 0)

    db_path = config.home() / "index.sqlite"
    repo = Path(config.repo_root())
    if os.path.islink(db_path):
        print(f"compare: refused: the index at {db_path} is a symbolic link (nothing written)", file=sys.stderr)
        return 2
    try:
        differ, missing = index_check(db_path, repo)     # read-only; runs before anything opens the index for writing
        if differ or missing:
            return _refusal(db_path, differ, missing)
        st = Store(db_path, repo)
    except Exception as e:
        return _error(db_path, type(e).__name__)
    try:
        os.environ["AGENT_CONSOLE_NO_FETCH"] = "1"        # the existing switch: ingest skips the git fetch of the claims data
        st.rescan(wait=True, min_interval=0)
        if st.progress.get("state") == "error" or st.progress.get("error"):
            return _error(db_path, str(st.progress.get("error") or "Error"))
        db = st.reader()
        try:
            db.execute("BEGIN")             # one read snapshot for the whole comparison
            try:
                unknown = compare.unknown_keys(db, ns.a, ns.b)
                if unknown:
                    print(f"compare: unknown ticket key{'s' if len(unknown) > 1 else ''}: {', '.join(compare_format.safe(k) for k in unknown)}", file=sys.stderr)
                    return 2
                tree = compare.compare(db, Pricing.load(config.pricing_path()), ns.a, ns.b)
            finally:
                db.rollback()
        finally:
            db.close()
    except Exception as e:
        return _error(db_path, type(e).__name__)
    finally:
        try:
            st.db.close()
        except Exception:
            pass
    print(compare.to_json(tree) if ns.json else compare_format.text_table(tree))
    return 0
