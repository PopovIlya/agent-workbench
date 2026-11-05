"""Ticket comparison data (EXP1-R22C): the figures of two tickets and their difference, from the console's index and the raw logs.

Main goal: for a ticket key, count role runs, tokens, cost, times and wait time, and put two tickets side by side.
Does: read the index (`runs`, `usage`, `tool_calls`, `sub_meta`, `files`) and, read-only line by line, the raw logs of the ticket's runs, for the failed-run
markers (CON-015) and the wait gaps (CON-022). No period, no scope (CON-012). Every read has an ORDER BY, so the same data gives the same bytes (CON-030).
Does not: write anything, call a clock, or keep log text: markers are matched inside the readers and only counts and timestamps leave them (CON-035).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Iterator

from . import tickets
from .pricing import Pricing
from .store import _norm_ts, key_evidence
from .timing import epoch

NO_MAIN = "no main session"
NO_SUB = "no sub-agents"
NA = "n/a"
VERSION = 1
KS = ("input", "output", "cache_write", "cache_read")
MIN_GAP_S = 60.0           # a gap under 60 s counts as zero (brief)
OVER_S = 7200.0            # "over 2 hours": longer than 7200 s, as CON-006
REJECTED = "The user doesn't want to proceed with this tool use"


# ---------------------------------------------------------------- reading the raw logs (read-only)

def _records(path: str) -> Iterator[dict[str, Any]]:
    """The JSON records of a log file, line by line; a line that is not a JSON object is skipped."""
    with open(path, "rb") as fh:
        for raw in fh:
            try:
                o = json.loads(raw)
            except (ValueError, RecursionError):
                continue
            if isinstance(o, dict):
                yield o


def _s(v: Any) -> str | None:
    """The value only when it is a string (ids, uuids and timestamps of a malformed record are ignored)."""
    return v if isinstance(v, str) else None


def _blocks(o: dict[str, Any]) -> list[dict[str, Any]]:
    msg = o.get("message")
    content = msg.get("content") if isinstance(msg, dict) else None
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _text(content: Any) -> str:
    """Plain text of a message content or a tool_result content (string, or text blocks). Used for matching only; never returned to an output."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(b.get("text", "")) for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def run_failed(path: str | None) -> bool:
    """CON-015: a sub-agent run did not complete when its last turn is an API error, or is not a final reply (a SubagentHandback call, or text with no other tool call).
    A denial, an ordinary tool result or an open tool_use as the last turn all leave no final reply. A file that is gone or cannot be read: not failed."""
    if not path:
        return False
    state = "none"                      # error | reply | tool | result | none
    turn_id: Any = None
    turn_text = turn_hb = turn_other = False   # of the merged last turn: text, a handback call, any other tool_use
    hb_ids: set[Any] = set()            # SubagentHandback tool_use ids of the last assistant turn
    try:
        for o in _records(path):
            t = o.get("type")
            if t == "system":
                if o.get("subtype") == "api_error":
                    state, turn_id = "error", None
            elif t == "assistant":
                msg = o.get("message") if isinstance(o.get("message"), dict) else {}
                if o.get("isApiErrorMessage"):
                    state, turn_id = "error", None
                    continue
                blocks = _blocks(o)
                text = any(b.get("type") == "text" and str(b.get("text", "")).strip() for b in blocks)
                hb = any(b.get("type") == "tool_use" and b.get("name") == "SubagentHandback" for b in blocks)
                other = any(b.get("type") == "tool_use" and b.get("name") != "SubagentHandback" for b in blocks)
                mid = _s(msg.get("id"))
                same = mid is not None and mid == turn_id       # one turn is written as several records
                turn_text, turn_hb, turn_other = ((turn_text or text, turn_hb or hb, turn_other or other) if same else (text, hb, other))
                hb_ids = (hb_ids if same else set()) | {_s(b.get("id")) for b in blocks
                                                        if b.get("type") == "tool_use" and b.get("name") == "SubagentHandback"
                                                        and _s(b.get("id")) is not None}
                turn_id = mid
                state = "reply" if turn_hb or (turn_text and not turn_other) else "tool"
            elif t == "user" and any(b.get("type") == "tool_result" for b in _blocks(o)):
                results = [b for b in _blocks(o) if b.get("type") == "tool_result"]
                # after a final reply with handback calls, only the handback's own error result fails the run (CON-015)
                if state == "reply" and turn_hb and not any(_s(b.get("tool_use_id")) is not None and _s(b.get("tool_use_id")) in hb_ids and b.get("is_error") is True for b in results):
                    continue
                state, turn_id, hb_ids = "result", None, set()
    except OSError:
        return False
    return state != "reply"


class _Gap:
    __slots__ = ("uuid", "reply", "start", "end", "plain")

    def __init__(self, uuid: Any, reply: tuple[str, str] | None, start: float, end: float):
        self.uuid, self.reply, self.start, self.end = uuid, reply, start, end
        self.plain = uuid is None and reply is None


def _typed(o: dict[str, Any]) -> bool:
    """A user record the person typed (CON-022 log markers)."""
    if o.get("isMeta") or o.get("toolUseResult") or any(b.get("type") == "tool_result" for b in _blocks(o)):
        return False
    origin = o.get("origin")
    kind = origin.get("kind") if isinstance(origin, dict) else None
    if origin is not None and kind is not None:
        return kind == "human"
    if o.get("isCompactSummary") is True or o.get("isVisibleInTranscriptOnly") is True:
        return False
    msg = o.get("message") if isinstance(o.get("message"), dict) else {}
    text = _text(msg.get("content")).strip()
    return not (text.startswith("<local-command-") or text.startswith("[Request interrupted by user") or text.startswith("<task-notification"))


def file_gaps(path: str | None) -> list[_Gap] | None:
    """CON-022 for one main-session file: the gaps from a stop for the person to the next gap end. None when the file is gone or unreadable."""
    if not path:
        return None
    items: list[tuple] = []             # in file order: ("a", info, stops_by_itself, [tool ids]) | ("end", ts) | ("res", tool id, is_error, ts)
    asks: set[str] = set()              # AskUserQuestion tool_use ids
    rejected: set[str] = set()          # tool_use ids whose permission prompt was rejected or dismissed
    try:
        for o in _records(path):
            t = o.get("type")
            ts = epoch(_s(o.get("timestamp")))
            if t == "assistant":
                msg = o.get("message") if isinstance(o.get("message"), dict) else {}
                rid = _s(o.get("requestId"))
                mid = _s(msg.get("id"))
                info = (_s(o.get("uuid")), (mid, rid) if mid and rid else None, ts)
                tool_ids, ask = [], False
                for b in _blocks(o):
                    if b.get("type") == "tool_use":
                        tool_ids.append(_s(b.get("id")))
                        if b.get("name") == "AskUserQuestion":
                            ask = True
                            if _s(b.get("id")) is not None:
                                asks.add(_s(b.get("id")))
                items.append(("a", info, msg.get("stop_reason") == "end_turn" or ask, tool_ids))
            elif t == "user":
                results = [b for b in _blocks(o) if b.get("type") == "tool_result"]
                for b in results:
                    err = b.get("is_error") is True
                    if err and REJECTED in _text(b.get("content")) and _s(b.get("tool_use_id")) is not None:
                        rejected.add(_s(b.get("tool_use_id")))
                    items.append(("res", _s(b.get("tool_use_id")), err, ts))
                if not results and _typed(o):
                    items.append(("end", ts))
    except OSError:
        return None
    gaps: list[_Gap] = []
    stop = None                          # the latest stop since the previous gap end; an earlier stop in the same stretch adds nothing
    for it in items:
        if it[0] == "a":
            if it[2] or any(i in rejected for i in it[3]):
                stop = it[1]
            continue
        if it[0] == "end":
            end_ts = it[1]
        elif it[1] in asks and not it[2]:
            end_ts = it[3]               # the person's answer to an AskUserQuestion
        else:
            continue                     # an ordinary tool result (or a dismissed question) ends no gap
        if stop is not None:
            if stop[2] is not None and end_ts is not None:
                gaps.append(_Gap(stop[0], stop[1], stop[2], end_ts))
            stop = None
    return gaps


def _wait(gap_lists: list[list[_Gap]]) -> tuple[float, float]:
    """(wait, wait over 2 h) over the ticket's main-session files. The same gap in several files (or twice in one) counts once:
    stop records that share a uuid or share message id + requestId; a stop with neither matches by (stop ts, gap end ts) among such stops;
    of the same gaps the one with the earliest gap end counts."""
    gaps = [g for lst in gap_lists for g in lst]
    parent = list(range(len(gaps)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    seen: dict[tuple, int] = {}
    for i, g in enumerate(gaps):
        keys = []
        if g.uuid is not None:
            keys.append(("uuid", g.uuid))
        if g.reply is not None:
            keys.append(("reply", g.reply))
        if g.plain:
            keys.append(("pair", g.start, g.end))
        for k in keys:
            if k in seen:
                parent[find(i)] = find(seen[k])
            else:
                seen[k] = i
    best: dict[int, int] = {}
    for i, g in enumerate(gaps):
        r = find(i)
        if r not in best or g.end < gaps[best[r]].end:
            best[r] = i
    wait = over = 0.0
    for i in sorted(best.values()):
        d = gaps[i].end - gaps[i].start
        if d >= MIN_GAP_S:
            wait += d
            if d > OVER_S:
                over += d
    return wait, over


# ---------------------------------------------------------------- the index

class _Ctx:
    """What one comparison reads from the index once: the spawns that have no run file, with their key."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        if db.row_factory is not sqlite3.Row:
            db.row_factory = sqlite3.Row
        self._spawns: list[dict[str, Any]] | None = None
        self.fb_role: dict[str, str] = {}       # sub run_id -> subagent_type of the spawn paired by the CON-014 fallback

    @property
    def spawns(self) -> list[dict[str, Any]]:
        """CON-014: each Agent/Task spawn once (the row with the earliest ts, then the smallest run_id), with no run file (no sub_meta.tool_use_id equal to
        its id), whose tool_result exists (out_chars is set), and a key: spawn_lead, else spawn_text, else the spawning run's key in force at the spawn, else its own key."""
        if self._spawns is not None:
            return self._spawns
        db = self.db
        linked = {r[0] for r in db.execute("SELECT tool_use_id FROM sub_meta WHERE tool_use_id IS NOT NULL ORDER BY tool_use_id")}
        first: dict[str, Any] = {}
        has_result: set[str] = set()
        failed_ids: set[str] = set()
        for r in db.execute("SELECT id, run_id, ts, ticket, is_error, out_chars, subagent_type FROM tool_calls WHERE name IN ('Agent','Task') ORDER BY ts, run_id, id"):
            if r["id"] not in first:
                first[r["id"]] = r
            if r["out_chars"] is not None:          # a result in any copy counts; an error in a copy with a result fails it
                has_result.add(r["id"])
                if r["is_error"]:
                    failed_ids.add(r["id"])
        self._pair_unlinked(first, linked)
        pending = [r for i, r in sorted(first.items()) if i not in linked and i in has_result]
        evidence = None
        own: dict[str, str | None] = {}
        out = []
        for r in sorted(pending, key=lambda r: (r["ts"] or "", r["run_id"], r["id"])):
            key = r["ticket"]
            if not key:
                if evidence is None:
                    files = db.execute("SELECT run_id, first_ts, prompt_lead, prompt_ticket FROM files ORDER BY run_id").fetchall()
                    evidence = key_evidence(db, files)
                    own = {x["run_id"]: x["ticket"] for x in db.execute("SELECT run_id, ticket FROM runs ORDER BY run_id")}
                hit = tickets.latest_before(evidence.get(r["run_id"], []), _norm_ts(r["ts"]))
                key = hit[0] if hit else own.get(r["run_id"])
            if key:
                out.append({"key": key, "role": r["subagent_type"] or "general-purpose", "failed": r["id"] in failed_ids})
        self._spawns = out
        return out


    def _pair_unlinked(self, first: dict[str, Any], linked: set[str]) -> None:
        """CON-014 fallback: a sub-agent file with no sub_meta.tool_use_id takes the earliest unlinked spawn of its session whose window
        (call ts <= file first_ts <= result end_ts) holds its start; one to one. Adds the paired spawn ids to `linked`."""
        db = self.db
        session = {r["run_id"]: r["session_id"] for r in db.execute("SELECT run_id, session_id FROM files ORDER BY run_id")}
        end: dict[str, str] = {}
        for r in db.execute("SELECT id, end_ts FROM tool_calls WHERE name IN ('Agent','Task') AND end_ts IS NOT NULL ORDER BY ts, run_id, id"):
            end.setdefault(r["id"], r["end_ts"])
        files = db.execute(
            "SELECT f.run_id, f.session_id, f.first_ts FROM files f LEFT JOIN sub_meta m ON m.run_id = f.run_id "
            "WHERE f.kind = 'sub' AND m.tool_use_id IS NULL ORDER BY f.first_ts, f.run_id").fetchall()
        free = sorted((r for i, r in first.items() if i not in linked), key=lambda r: (r["ts"] or "", r["run_id"], r["id"]))
        for f in files:
            start = _norm_ts(f["first_ts"])
            if not start:
                continue
            for r in free:
                if r["id"] in linked or session.get(r["run_id"]) != f["session_id"]:
                    continue
                s, e = _norm_ts(r["ts"]), _norm_ts(end.get(r["id"]))
                if s and e and s <= start <= e:
                    linked.add(r["id"])
                    self.fb_role[f["run_id"]] = r["subagent_type"] or "general-purpose"
                    break


def unknown_keys(db: sqlite3.Connection, a: str, b: str) -> list[str]:
    """CON-027: the keys with no run, no main session and no counted spawn, a first; the same key twice once."""
    ctx = _Ctx(db)
    res: list[str] = []
    for k in (a, b):
        if k in res:
            continue
        if db.execute("SELECT 1 FROM runs WHERE ticket=? OR ticket_eff=? LIMIT 1", (k, k)).fetchone():
            continue
        if any(s["key"] == k for s in ctx.spawns):
            continue
        res.append(k)
    return res


def _k(inp: int = 0, out: int = 0, cw: int = 0, cr: int = 0) -> dict[str, int]:
    return {"input": inp, "output": out, "cache_write": cw, "cache_read": cr}


def _ticket(ctx: _Ctx, pricing: Pricing, key: str) -> dict[str, Any]:
    db = ctx.db
    ctx.spawns          # fills ctx.fb_role
    runs = db.execute("SELECT run_id, kind, role, start_ts, end_ts FROM runs WHERE ticket_eff=? ORDER BY start_ts, run_id", (key,)).fetchall()
    kind = {r["run_id"]: r["kind"] for r in runs}
    mains = [r for r in runs if r["kind"] == "main"]
    subs = [r for r in runs if r["kind"] == "sub"]
    spawns = [s for s in ctx.spawns if s["key"] == key]

    # role runs: runs with a file + counted spawns without one
    paths = {r["run_id"]: r["path"] for r in db.execute(
        "SELECT f.run_id, f.path FROM files f JOIN runs r ON r.run_id = f.run_id WHERE r.ticket_eff=? ORDER BY f.run_id", (key,))}
    failed = sum(1 for r in subs if run_failed(paths.get(r["run_id"]))) + sum(1 for s in spawns if s["failed"])
    meta_role = {r["run_id"] for r in db.execute("SELECT run_id FROM sub_meta WHERE role IS NOT NULL ORDER BY run_id")}
    roles = [ctx.fb_role[r["run_id"]] if r["run_id"] in ctx.fb_role and r["run_id"] not in meta_role else r["role"] for r in subs] + [s["role"] for s in spawns]
    repeat = len(roles) - len(set(roles))

    # tokens and cost, one pass over `usage` (one row per API message), in a fixed order
    tok_total, tok_main = _k(), _k()
    by_model: dict[str, dict[str, int]] = {}
    cost_by_model: dict[str, float] = {}
    cost_total = cost_main = cost_sub = 0.0
    unpriced = 0
    for u in db.execute("SELECT u.run_id, u.model, u.input, u.output, u.cache_read, u.cache_w5m, u.cache_w1h FROM usage u "
                        "JOIN runs r ON r.run_id = u.run_id WHERE r.ticket_eff=? ORDER BY u.run_id, u.ts, u.msg_key", (key,)):
        n = {"input": u["input"] or 0, "output": u["output"] or 0, "cache_read": u["cache_read"] or 0,
             "cache_w5m": u["cache_w5m"] or 0, "cache_w1h": u["cache_w1h"] or 0}
        model = u["model"] or "unknown"
        k = _k(n["input"], n["output"], n["cache_w5m"] + n["cache_w1h"], n["cache_read"])
        bm = by_model.setdefault(model, _k())
        is_main = kind.get(u["run_id"]) == "main"
        for f in KS:
            tok_total[f] += k[f]
            bm[f] += k[f]
            if is_main:
                tok_main[f] += k[f]
        cost = pricing.message_cost(u["model"], n)[0]
        if cost is None:
            unpriced += 1
            cost = 0.0
        cost_by_model[model] = cost_by_model.get(model, 0.0) + cost
        cost_total += cost
        if is_main:
            cost_main += cost
        else:
            cost_sub += cost

    # times: wall = first start to last end over all the ticket's files; active = sum of sub-agent run durations
    starts = [e for e in (epoch(r["start_ts"]) for r in runs) if e is not None]
    ends = [e for e in (epoch(r["end_ts"]) for r in runs) if e is not None]
    wall = float(max(ends) - min(starts)) if starts and ends else 0.0
    active = 0.0
    for r in subs:
        s, e = epoch(r["start_ts"]), epoch(r["end_ts"])
        if s is not None and e is not None:
            active += e - s

    if mains:
        gap_lists = [g for g in (file_gaps(paths.get(r["run_id"])) for r in mains) if g is not None]
        wait, over = _wait(gap_lists)
        share: Any = (cost_main / cost_sub) if cost_sub != 0 else NO_SUB
        main_tokens: Any = tok_main
        main_cost: Any = cost_main
    else:
        wait = over = main_tokens = main_cost = share = NO_MAIN
    return {
        "key": key,
        "main_sessions": len(mains),
        "runs": {"total": len(subs) + len(spawns), "failed": failed, "repeat_rounds": repeat},
        "tokens": {"total": tok_total, "by_model": by_model, "main": main_tokens},
        "cost_usd": {"total": cost_total, "by_model": cost_by_model, "main": main_cost, "unpriced_messages": unpriced},
        "time_s": {"wall": wall, "active_role": float(active), "wait": wait, "wait_over_2h": over},
        "cost_share": share,
    }


def ticket(db: sqlite3.Connection, pricing: Pricing, key: str) -> dict[str, Any]:
    """The figures of one ticket (T of CON-030). An unknown key gives zeros; callers check unknown_keys first."""
    return _ticket(_Ctx(db), pricing, key)


# ---------------------------------------------------------------- the difference

def _leaf(a: Any, b: Any) -> dict[str, Any]:
    """CON-026: b - a and b / a from the raw values; "n/a" when a side has a label, and for the ratio also when a is 0."""
    if isinstance(a, str) or isinstance(b, str):
        return {"diff": NA, "ratio": NA}
    return {"diff": b - a, "ratio": (b / a) if a != 0 else NA}


def _group(a: Any, b: Any) -> Any:
    """Leaves of two same-shaped values (numbers, labels or dicts of them) -> the same shape of {diff, ratio}; a label side gives n/a for every leaf."""
    if isinstance(a, dict) or isinstance(b, dict):
        shape = a if isinstance(a, dict) else b
        return {k: _group(a[k] if isinstance(a, dict) else a, b[k] if isinstance(b, dict) else b) for k in shape}
    return _leaf(a, b)


def _main_tokens(a: Any, b: Any) -> dict[str, Any]:
    """The four token leaves of the main-session tokens; with a label on either side every leaf is n/a (the tree keeps its shape)."""
    if isinstance(a, str) or isinstance(b, str):
        return {k: {"diff": NA, "ratio": NA} for k in KS}
    return _group(a, b)


def _models(ta: dict, tb: dict, part: str, zero: Any) -> dict[str, Any]:
    names = sorted(set(ta[part]["by_model"]) | set(tb[part]["by_model"]))
    return {m: _group(ta[part]["by_model"].get(m, zero()), tb[part]["by_model"].get(m, zero())) for m in names}


def _diff(ta: dict, tb: dict) -> dict[str, Any]:
    return {
        "main_sessions": _leaf(ta["main_sessions"], tb["main_sessions"]),
        "runs": _group(ta["runs"], tb["runs"]),
        "tokens": {"total": _group(ta["tokens"]["total"], tb["tokens"]["total"]),
                   "by_model": _models(ta, tb, "tokens", _k),
                   "main": _main_tokens(ta["tokens"]["main"], tb["tokens"]["main"])},
        "cost_usd": {"total": _leaf(ta["cost_usd"]["total"], tb["cost_usd"]["total"]),
                     "by_model": _models(ta, tb, "cost_usd", float),
                     "main": _leaf(ta["cost_usd"]["main"], tb["cost_usd"]["main"]),
                     "unpriced_messages": _leaf(ta["cost_usd"]["unpriced_messages"], tb["cost_usd"]["unpriced_messages"])},
        "time_s": _group(ta["time_s"], tb["time_s"]),
        "cost_share": _leaf(ta["cost_share"], tb["cost_share"]),
    }


def compare(db: sqlite3.Connection, pricing: Pricing, a: str, b: str) -> dict[str, Any]:
    """The whole tree of CON-030: {"a": T, "b": T, "diff": D, "version": 1}. Does not check for unknown keys; callers do."""
    ctx = _Ctx(db)
    ta, tb = _ticket(ctx, pricing, a), _ticket(ctx, pricing, b)
    return {"a": ta, "b": tb, "diff": _diff(ta, tb), "version": VERSION}


def to_json(tree: dict[str, Any]) -> str:
    """Stable JSON: sorted keys, raw numbers, no trailing newline."""
    return json.dumps(tree, sort_keys=True, indent=2)


__all__ = ["NO_MAIN", "NO_SUB", "NA", "compare", "ticket", "unknown_keys", "to_json", "run_failed", "file_gaps"]
