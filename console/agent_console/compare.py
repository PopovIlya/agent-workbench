"""Ticket comparison: two tickets side by side by cost, time and outcome (CON-027 to CON-052).

Main goal: one `compare()` result (plain dicts, raw values) that the CLI (`python -m agent_console compare A B [--json]`)
and the /compare page both render. A ticket is the runs whose effective key is the key, over ALL logs (no period, no scope).
Does: read the index for runs, tokens and cost; read the raw session files, read-only, for failed runs and for waits.
Does not: write anything, or output any log text (only counts, seconds and token numbers leave this module).
Example: res = compare(store, pricing, "PROJ-1", "PROJ-2")
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterator

from . import config
from .pricing import Pricing
from .timing import epoch

WAIT_MIN_S = 60            # a wait gap shorter than this counts as zero
WAIT_LONG_S = 2 * 3600     # the extra figure: the part of the wait that came from gaps longer than this
DENIAL_PREFIXES = ("Permission for this ", "The user doesn't want ")
# user records written by the harness, not typed by the person (used only when the record has no origin.kind)
MACHINE_TEXT = ("<task-notification", "<local-command-stdout", "<local-command-stderr", "<local-command-caveat",
                "[Request interrupted by user", "<system-reminder", "<user-prompt-submit-hook", "<bash-stdout", "<bash-stderr")


class UnknownKey(Exception):
    def __init__(self, keys: list[str]):
        super().__init__(", ".join(keys))
        self.keys = keys


# ---------- raw logs (read-only; only structure is looked at, no text is kept) ----------

def _records(path: str) -> Iterator[dict[str, Any]]:
    with open(path, "rb") as fh:
        for raw in fh:
            try:
                o = json.loads(raw)
            except ValueError:
                continue
            if isinstance(o, dict):
                yield o


def _blocks(o: dict[str, Any]) -> list[dict[str, Any]]:
    msg = o.get("message")
    content = msg.get("content") if isinstance(msg, dict) else None
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict) and isinstance(b.get("text"), str))
    return ""


def run_failed(path: str) -> bool:
    """A sub-agent run that did not complete: ended in an API error or a permission denial, or has no final reply (CON-035).
    A final reply is a last assistant record with stop_reason end_turn, or one that hands back with a SubagentHandback call:
    every sub-agent run in real logs ends that way (found by the post-run check on real logs; the run's own result is in the main log)."""
    bad = has_text = False
    stop = None
    handback = False
    for o in _records(path):
        t = o.get("type")
        if t == "system":
            if o.get("subtype") == "api_error":
                bad = True
        elif t == "assistant":
            if o.get("isApiErrorMessage"):
                bad = True
                continue
            msg = o.get("message") if isinstance(o.get("message"), dict) else {}
            if msg.get("model") == "<synthetic>":
                continue
            bad = False
            stop = msg.get("stop_reason")
            blocks = _blocks(o)
            handback = any(b.get("type") == "tool_use" and b.get("name") == "SubagentHandback" for b in blocks)
            if any(b.get("type") == "text" and str(b.get("text") or "").strip() for b in blocks):
                has_text = True
        elif t == "user" and isinstance(o.get("toolUseResult"), str):
            for b in _blocks(o):
                if b.get("type") == "tool_result" and b.get("is_error") and _text(b.get("content")).startswith(DENIAL_PREFIXES):
                    bad = True
    if bad:
        return True
    return not handback and (not has_text or stop != "end_turn")


def _typed_by_person(o: dict[str, Any]) -> bool:
    if o.get("isMeta") or o.get("toolUseResult") is not None:
        return False
    blocks = _blocks(o)
    if any(b.get("type") == "tool_result" for b in blocks):
        return False
    origin = o.get("origin")
    kind = origin.get("kind") if isinstance(origin, dict) else None
    if isinstance(kind, str):
        return kind == "human"
    msg = o.get("message")
    return not _text(msg.get("content") if isinstance(msg, dict) else None).lstrip().startswith(MACHINE_TEXT)


def main_waits(path: str) -> list[float]:
    """Gap lengths (seconds, 60 s or more) between an assistant turn that waits on the person and the next message the person typed
    (or the answer to the AskUserQuestion call that ended the turn). Machine-written user records do not end a gap (CON-043, CON-044)."""
    gaps: list[float] = []
    pend: tuple[float | None, set[Any]] | None = None
    for o in _records(path):
        t = o.get("type")
        if t == "assistant":
            msg = o.get("message") if isinstance(o.get("message"), dict) else {}
            if o.get("isApiErrorMessage") or msg.get("model") == "<synthetic>":
                continue
            ask = {b.get("id") for b in _blocks(o) if b.get("type") == "tool_use" and b.get("name") == "AskUserQuestion"}
            pend = (epoch(o.get("timestamp")), ask) if msg.get("stop_reason") == "end_turn" or ask else None
        elif t == "user" and pend is not None:
            ids = {b.get("tool_use_id") for b in _blocks(o) if b.get("type") == "tool_result"}
            if pend[1] & ids or _typed_by_person(o):
                end = epoch(o.get("timestamp"))
                if end is not None and pend[0] is not None and end - pend[0] >= WAIT_MIN_S:
                    gaps.append(end - pend[0])
                pend = None
    return gaps


# ---------- one ticket ----------

def _zero_tokens() -> dict[str, int]:
    return {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0, "total": 0}


def _add_tokens(into: dict[str, int], r: Any) -> None:
    into["input"] += r["input"] or 0
    into["output"] += r["output"] or 0
    into["cache_write"] += (r["cache_w5m"] or 0) + (r["cache_w1h"] or 0)
    into["cache_read"] += r["cache_read"] or 0
    into["total"] = into["input"] + into["output"] + into["cache_write"] + into["cache_read"]


def _ticket(db: Any, pricing: Pricing, key: str) -> dict[str, Any] | None:
    runs = db.execute("SELECT run_id, kind, role, start_ts, end_ts FROM runs WHERE ticket_eff=? ORDER BY start_ts, run_id", (key,)).fetchall()
    # a spawn with a tool result but no run file counts for the ticket named in the spawn input; it fails only if the result is an error (CON-037)
    denied = {r["id"]: (r["subagent_type"] or "general-purpose", r["is_error"]) for r in db.execute(
        "SELECT id, subagent_type, is_error FROM tool_calls WHERE name IN ('Agent','Task') AND end_ts IS NOT NULL AND ticket=? "
        "AND id NOT IN (SELECT tool_use_id FROM sub_meta WHERE tool_use_id IS NOT NULL)", (key,))}
    if not runs and not denied and not db.execute("SELECT 1 FROM runs WHERE ticket=? LIMIT 1", (key,)).fetchone():
        return None
    subs = [r for r in runs if r["kind"] == "sub"]
    mains = [r for r in runs if r["kind"] == "main"]
    files = {r["run_id"]: r for r in db.execute(
        "SELECT f.run_id, f.path, f.first_ts, f.last_ts FROM files f JOIN runs r ON r.run_id=f.run_id WHERE r.ticket_eff=?", (key,))}

    per_role = Counter(r["role"] for r in subs) + Counter(v[0] for v in denied.values())
    failed = sum(1 for v in denied.values() if v[1])
    for r in subs:
        f = files.get(r["run_id"])
        try:
            failed += 1 if f and run_failed(f["path"]) else 0
        except OSError:
            pass   # the log file is gone: no evidence of a failure
    active = 0.0
    for r in subs:
        a, b = epoch(r["start_ts"]), epoch(r["end_ts"])
        if a is not None and b is not None:
            active += max(0.0, b - a)
    firsts = [epoch(f["first_ts"]) for f in files.values() if f["first_ts"]]
    lasts = [epoch(f["last_ts"]) for f in files.values() if f["last_ts"]]
    wall = max(0.0, max(lasts) - min(firsts)) if firsts and lasts else 0.0

    total, main_tok = _zero_tokens(), _zero_tokens()
    by_model: dict[str, dict[str, Any]] = {}
    cost = main_cost = sub_cost = 0.0
    unpriced = 0
    for u in db.execute("SELECT u.msg_key, u.model, u.input, u.output, u.cache_read, u.cache_w5m, u.cache_w1h, r.kind FROM usage u "
                        "JOIN runs r ON r.run_id=u.run_id WHERE r.ticket_eff=? ORDER BY u.msg_key", (key,)):
        m = by_model.setdefault(u["model"] or "unknown", {**_zero_tokens(), "cost_usd": 0.0, "unpriced_messages": 0})
        c, _ = pricing.message_cost(u["model"], {"input": u["input"] or 0, "output": u["output"] or 0, "cache_read": u["cache_read"] or 0,
                                                 "cache_w5m": u["cache_w5m"] or 0, "cache_w1h": u["cache_w1h"] or 0})
        _add_tokens(m, u)
        _add_tokens(total, u)
        if c is None:
            m["unpriced_messages"] += 1
            unpriced += 1
            c = 0.0
        m["cost_usd"] += c
        cost += c
        if u["kind"] == "main":
            _add_tokens(main_tok, u)
            main_cost += c
        else:
            sub_cost += c

    main: dict[str, Any] | None = None
    if mains:
        gaps: list[float] = []
        for r in mains:
            f = files.get(r["run_id"])
            try:
                gaps += main_waits(f["path"]) if f else []
            except OSError:
                pass
        main = {"sessions": len(mains), "tokens": main_tok, "cost_usd": main_cost, "wait_s": sum(gaps),
                "wait_over_2h_s": sum(g for g in gaps if g > WAIT_LONG_S)}
    return {
        "key": key,
        "role_runs": {"total": len(subs) + len(denied), "failed": failed, "repeat": sum(max(0, n - 1) for n in per_role.values())},
        "tokens": total, "tokens_by_model": by_model, "cost_usd": cost, "unpriced_messages": unpriced,
        "wall_s": wall, "active_role_s": active,
        "main_session": main, "sub_agents_cost_usd": sub_cost,
        "main_share_of_sub_cost": main_cost / sub_cost if main is not None and sub_cost > 0 else None,
    }


# ---------- the comparison ----------

NO_MAIN, NO_SUB = "no main session", "no sub-agents"
# (id, label, unit)
ROWS = [
    ("role_runs_total", "Role runs", "count"), ("role_runs_failed", "Failed role runs", "count"), ("role_runs_repeat", "Repeat rounds", "count"),
    ("tokens_input", "Tokens: input", "tokens"), ("tokens_output", "Tokens: output", "tokens"),
    ("tokens_cache_write", "Tokens: cache write", "tokens"), ("tokens_cache_read", "Tokens: cache read", "tokens"),
    ("tokens_total", "Tokens: total", "tokens"),
    ("cost_usd", "Cost", "usd"), ("unpriced_messages", "Unpriced messages (cost 0)", "count"),
    ("wall_s", "Wall time", "time"), ("active_role_s", "Active role time", "time"),
    ("main_wait_s", "Main session: waiting on a person", "time"), ("main_wait_over_2h_s", "Main session: of that, gaps over 2 h", "time"),
    ("main_tokens_total", "Main session: tokens", "tokens"), ("main_cost_usd", "Main session: cost", "usd"),
    ("main_share_of_sub_cost", "Main session cost / sub-agent cost", "ratio"),
]
MODEL_FIELDS = [("input", "input", "tokens"), ("output", "output", "tokens"), ("cache_write", "cache write", "tokens"),
                ("cache_read", "cache read", "tokens"), ("cost_usd", "cost", "usd"), ("unpriced_messages", "unpriced messages", "count")]


def _figure(c: dict[str, Any], rid: str) -> tuple[float | None, str | None]:
    """(value, why there is none)."""
    m = c["main_session"]
    if rid.startswith("role_runs_"):
        return c["role_runs"][rid[len("role_runs_"):]], None
    if rid.startswith("tokens_"):
        return c["tokens"][rid[len("tokens_"):]], None
    if rid.startswith("main_"):
        if m is None:
            return None, NO_MAIN
        if rid == "main_share_of_sub_cost":
            return c["main_share_of_sub_cost"], (None if c["main_share_of_sub_cost"] is not None else NO_SUB)
        return {"main_wait_s": m["wait_s"], "main_wait_over_2h_s": m["wait_over_2h_s"],
                "main_tokens_total": m["tokens"]["total"], "main_cost_usd": m["cost_usd"]}[rid], None
    return c[rid], None


def _diff(a: float | None, b: float | None) -> tuple[float | None, float | None]:
    """(b - a, b / a); the difference needs both values, the ratio also a non-zero a (CON-049)."""
    if a is None or b is None:
        return None, None
    return b - a, (b / a if a != 0 else None)


def compare(store: Any, pricing: Pricing, a: str, b: str) -> dict[str, Any]:
    db = store.reader()
    try:
        cols = {k: _ticket(db, pricing, k) for k in dict.fromkeys((a, b))}
    finally:
        db.close()
    unknown = [k for k, c in cols.items() if c is None]
    if unknown:
        raise UnknownKey(unknown)
    ca, cb = cols[a], cols[b]
    assert ca is not None and cb is not None
    diff: dict[str, Any] = {}
    ratio: dict[str, Any] = {}
    for rid, _label, _unit in ROWS:
        diff[rid], ratio[rid] = _diff(_figure(ca, rid)[0], _figure(cb, rid)[0])
    dm: dict[str, Any] = {}
    rm: dict[str, Any] = {}
    for model in sorted(set(ca["tokens_by_model"]) | set(cb["tokens_by_model"])):
        ma, mb = ca["tokens_by_model"].get(model), cb["tokens_by_model"].get(model)
        dm[model], rm[model] = {}, {}
        for fid, _l, _u in MODEL_FIELDS:
            dm[model][fid], rm[model][fid] = _diff(ma[fid] if ma else None, mb[fid] if mb else None)
    diff["tokens_by_model"], ratio["tokens_by_model"] = dm, rm
    return {"a": ca, "b": cb, "difference": diff, "ratio": ratio}


# ---------- display (rounded; the JSON keeps raw values) ----------

def _round(x: float, places: int = 0, div: int = 1) -> tuple[Decimal, bool]:
    """(rounded size, negative) with a .5 tie away from zero; a result that rounds to zero is never negative."""
    q = (Decimal(repr(abs(float(x)))) / div).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return q, x < 0 and q != 0


def fmt(x: float | None, unit: str, why: str | None = None) -> str:
    if x is None:
        return why or "n/a"
    if unit == "count":
        q, neg = _round(x)
        s = f"{q}"
    elif unit == "tokens":
        q, neg = _round(x, 0, 1000)
        s = f"{q}k"
    elif unit == "usd":
        q, neg = _round(x, 2)
        s = f"${q}"
    elif unit == "time":
        q, neg = _round(x, 0, 60)
        s = f"{q} min"
    else:   # ratio
        q, neg = _round(x, 2)
        s = f"{q}"
    return ("-" if neg else "") + s


def display_rows(res: dict[str, Any]) -> list[tuple[str, str, str, str, str]]:
    """(label, a, b, difference, ratio) as text."""
    a, b, d, r = res["a"], res["b"], res["difference"], res["ratio"]
    out = []
    for rid, label, unit in ROWS:
        va, wa = _figure(a, rid)
        vb, wb = _figure(b, rid)
        out.append((label, fmt(va, unit, why=wa), fmt(vb, unit, why=wb), fmt(d[rid], unit), fmt(r[rid], "ratio")))
    for model in d["tokens_by_model"]:
        ma, mb = a["tokens_by_model"].get(model), b["tokens_by_model"].get(model)
        for fid, flabel, unit in MODEL_FIELDS:
            out.append((f"{model}: {flabel}", fmt(ma[fid], unit) if ma else "-", fmt(mb[fid], unit) if mb else "-",
                        fmt(d["tokens_by_model"][model][fid], unit), fmt(r["tokens_by_model"][model][fid], "ratio")))
    return out


HEAD = ("", "a", "b", "difference (b - a)", "ratio (b / a)")


def render_text(res: dict[str, Any]) -> str:
    rows = [(f"{HEAD[0]}", f"a: {res['a']['key']}", f"b: {res['b']['key']}", HEAD[3], HEAD[4])] + display_rows(res)
    w = [max(len(r[i]) for r in rows) for i in range(5)]
    lines = ["Ticket comparison. Tokens in thousands, dollars to cents, time in whole minutes."]
    lines += ["  ".join(c.ljust(w[i]) for i, c in enumerate(r)).rstrip() for r in rows]
    return "\n".join(lines) + "\n"


def _page(title: str, body: str) -> str:
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><title>' + html.escape(title) + '</title>'
            '<link rel="stylesheet" href="/static/style.css"></head><body><main>' + body + '</main></body></html>\n')


def render_html(res: dict[str, Any]) -> str:
    e = html.escape
    head = "".join(f"<th>{e(h)}</th>" for h in ("", f"a: {res['a']['key']}", f"b: {res['b']['key']}", HEAD[3], HEAD[4]))
    body = "".join("<tr>" + "".join(f"<td>{e(c)}</td>" for c in row) + "</tr>" for row in display_rows(res))
    return _page(f"Compare {res['a']['key']} and {res['b']['key']}",
                 f"<h1>Ticket comparison: {e(res['a']['key'])} and {e(res['b']['key'])}</h1>"
                 "<p>Tokens in thousands, dollars to cents, time in whole minutes.</p>"
                 f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")


def render_error(message: str) -> str:
    return _page("Compare", f"<h1>Ticket comparison</h1><p>{html.escape(message)}</p>")


def to_json(res: dict[str, Any]) -> str:
    return json.dumps(res, sort_keys=True, indent=2, allow_nan=False) + "\n"


def cli_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m agent_console compare", description="Compare two tickets by cost, time and outcome.")
    ap.add_argument("a", metavar="KEY_A")
    ap.add_argument("b", metavar="KEY_B")
    ap.add_argument("--json", action="store_true", help="raw values, sorted keys")
    args = ap.parse_args(argv)    # a wrong number of keys: usage on stderr, exit 2
    from .store import Store
    st = Store()
    st.ingest()
    try:
        res = compare(st, Pricing.load(config.pricing_path()), args.a, args.b)
    except UnknownKey as ex:
        print("Unknown ticket key: " + ", ".join(ex.keys), file=sys.stderr)
        return 2
    sys.stdout.write(to_json(res) if args.json else render_text(res))
    return 0

