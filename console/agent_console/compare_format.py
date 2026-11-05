"""One formatter for the comparison page and the CLI text (CON-024, CON-026, CON-029).

Main goal: the same value gives the same text on the page and in the CLI.
Does: round half away from zero on the shortest decimal text of the raw value (Decimal, never round()), show tokens as `12k`, dollars as
`$1.23` (`-$1.23`), time in whole minutes as `12 min`, ratios with 2 decimals, and never print a sign on a value that rounds to zero.
Does not: touch the JSON (it keeps raw values), read the logs or the index.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

HEADINGS = ("Figure", "Difference b - a (ratio b / a)")
KS = ("input", "output", "cache_write", "cache_read")
K_WORDS = {"input": "input", "output": "output", "cache_write": "cache write", "cache_read": "cache read"}


_CONTROL = re.compile("[\x00-\x1f\x7f-\x9f]")


def safe(text: str) -> str:
    """Text with every C0/C1 control character and DEL shown as a visible \\xNN escape (terminal output)."""
    return _CONTROL.sub(lambda m: f"\\x{ord(m.group()):02x}", text)


def _round(v: int | float, divisor: int, places: str) -> tuple[str, bool]:
    """(digits of |v| / divisor rounded half up to `places`, whether the rounded size is not zero)."""
    size = abs(Decimal(str(v))) / divisor
    q = size.quantize(Decimal(places), rounding=ROUND_HALF_UP)
    return format(q, "f"), q != 0


def _fmt(v: int | float | str, divisor: int, places: str, prefix: str = "", suffix: str = "") -> str:
    if isinstance(v, str):
        return v
    digits, nonzero = _round(v, divisor, places)
    sign = "-" if v < 0 and nonzero else ""
    return f"{sign}{prefix}{digits}{suffix}"


def tokens(v: int | float | str) -> str:
    return _fmt(v, 1000, "1", suffix="k")


def usd(v: int | float | str) -> str:
    return _fmt(v, 1, "0.01", prefix="$")


def minutes(v: int | float | str) -> str:
    return _fmt(v, 60, "1", suffix=" min")


def ratio(v: int | float | str) -> str:
    return _fmt(v, 1, "0.01")


def count(v: int | float | str) -> str:
    return _fmt(v, 1, "1")


FORMATS = {"count": count, "tokens": tokens, "usd": usd, "minutes": minutes, "ratio": ratio}


class Row(NamedTuple):
    id: str
    label: str
    a: str
    b: str
    diff: str
    ratio: str


def _walk(node, path: tuple[str, ...]):
    """The value at `path`; a label (str) met on the way is the value (a side with no main session)."""
    for part in path:
        if isinstance(node, str):
            return node
        node = node[part]
    return node


def _specs(tree: dict) -> list[tuple[tuple[str, ...], str, str]]:
    """(path, label, format) of every table row in the fixed order of the page."""
    a, b = tree["a"], tree["b"]
    models = sorted(set(a["tokens"]["by_model"]) | set(b["tokens"]["by_model"]))
    cost_models = sorted(set(a["cost_usd"]["by_model"]) | set(b["cost_usd"]["by_model"]))
    out: list[tuple[tuple[str, ...], str, str]] = [
        (("main_sessions",), "Main sessions", "count"),
        (("runs", "total"), "Role runs", "count"),
        (("runs", "failed"), "Failed runs", "count"),
        (("runs", "repeat_rounds"), "Repeat rounds", "count"),
    ]
    out += [(("tokens", "total", k), f"Tokens, {K_WORDS[k]}", "tokens") for k in KS]
    for m in models:
        out += [(("tokens", "by_model", m, k), f"Tokens, {m}, {K_WORDS[k]}", "tokens") for k in KS]
    out += [(("tokens", "main", k), f"Main-session tokens, {K_WORDS[k]}", "tokens") for k in KS]
    out += [(("cost_usd", "total"), "Cost", "usd"), (("cost_usd", "unpriced_messages"), "Unpriced messages", "count")]
    out += [(("cost_usd", "by_model", m), f"Cost, {m}", "usd") for m in cost_models]
    out += [
        (("cost_usd", "main"), "Main-session cost", "usd"),
        (("time_s", "wall"), "Wall time", "minutes"),
        (("time_s", "active_role"), "Active role time", "minutes"),
        (("time_s", "wait"), "Main-session wait time", "minutes"),
        (("time_s", "wait_over_2h"), "Main-session wait time from gaps over 2 h", "minutes"),
        (("cost_share",), "Cost share (main / sub-agents)", "ratio"),
    ]
    return out


def _side(side: dict, path: tuple[str, ...]):
    """A side's value; a model the side does not have is 0 there."""
    if len(path) >= 3 and path[0] in ("tokens", "cost_usd") and path[1] == "by_model" and path[2] not in side[path[0]]["by_model"]:
        return 0 if path[0] == "tokens" else 0.0
    return _walk(side, path)


def rows(tree: dict) -> list[Row]:
    """The table rows, already formatted, in their fixed order."""
    res = []
    for path, label, kind in _specs(tree):
        f = FORMATS[kind]
        leaf = _walk(tree["diff"], path)
        res.append(Row(".".join(path), label, f(_side(tree["a"], path)), f(_side(tree["b"], path)), f(leaf["diff"]), ratio(leaf["ratio"])))
    return res


def text_table(tree: dict) -> str:
    """The CLI text: one header line, one line per row, cells joined by ` | `, padded to the column width, trailing spaces stripped."""
    head = (HEADINGS[0], tree["a"]["key"], tree["b"]["key"], HEADINGS[1])
    lines = [tuple(safe(c) for c in line) for line in [head] + [(r.label, r.a, r.b, f"{r.diff} ({r.ratio})") for r in rows(tree)]]
    widths = [max(len(line[i]) for line in lines) for i in range(4)]
    return "\n".join(" | ".join(c.ljust(w) for c, w in zip(line, widths)).rstrip() for line in lines)
