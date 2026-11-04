"""Time derived from the index at every rebuild: tool-call durations, waits, the per-run time split.

Main goal: one place that turns raw timestamps into seconds, so every page uses the same numbers.
Does: finalize_tool_calls (dur_s, timed_out, blocked), rebuild_waits (human / ask / notification / parked / blocked),
      split_runs (model / tool / test / waiting / parked / blocked / unattributed per run).
Does not: read logs (the parser did) or know about tickets.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable

from . import config
from .parser import TEST_CLASSES

NOT_TOOL_TIME = ("Agent", "Task", "AskUserQuestion")   # a spawn waits for the sub-agent run (its own run covers that time); a question is a wait


def epoch(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def iso(t: float) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(round((t % 1) * 1000)) % 1000:03d}Z"


def union(intervals: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    """Merge overlapping intervals. Parallel tool calls overlap, so time is built from the UNION, never from the sum of durations."""
    out: list[list[float]] = []
    for a, b in sorted(x for x in intervals if x[1] > x[0]):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def total(intervals: Iterable[tuple[float, float]]) -> float:
    return sum(b - a for a, b in union(intervals))


def clip(intervals: Iterable[tuple[float, float]], lo: float, hi: float) -> list[tuple[float, float]]:
    return [(max(a, lo), min(b, hi)) for a, b in intervals if min(b, hi) > max(a, lo)]


def finalize_tool_calls(db) -> None:
    """dur_s / timed_out / blocked for calls that have a result and were not yet processed (timed_out IS NULL).
    A background test call returns at once: it is not timed (dur_s stays NULL) and is counted apart (runs.test_bg_n)."""
    rows = db.execute("SELECT rowid, ts, end_ts, name, cmd_class, background FROM tool_calls WHERE end_ts IS NOT NULL AND timed_out IS NULL").fetchall()
    upd = []
    for r in rows:
        a, b = epoch(r["ts"]), epoch(r["end_ts"])
        dur = max(0.0, b - a) if a is not None and b is not None else None
        test = r["cmd_class"] in TEST_CLASSES
        if test and r["background"]:
            upd.append((None, 0, 0, r["rowid"]))
            continue
        timed_out = 1 if test and dur is not None and dur >= config.TEST_TIMEOUT_S else 0
        blocked = 1 if (not test and not r["background"] and r["name"] not in NOT_TOOL_TIME and r["name"] != "Bash-write"
                        and dur is not None and dur > config.BLOCKED_AFTER_S) else 0
        upd.append((dur, timed_out, blocked, r["rowid"]))
    db.executemany("UPDATE tool_calls SET dur_s=?, timed_out=?, blocked=? WHERE rowid=?", upd)


def rebuild_waits(db) -> None:
    """waits = human | ask | notification | parked | blocked, one row per span.
    human: idle gap before a user record whose origin.kind is "human" (or unmarked: a typed prompt of an older log).
    ask: an AskUserQuestion call, tool_use -> tool_result. notification: gap before a task-notification or other non-human record.
    parked: a human or ask wait longer than PARKED_AFTER_S (the session was left open). blocked: a long non-test tool call (see finalize)."""
    db.execute("DELETE FROM waits")
    out: list[tuple[str, str, str, float, str]] = []
    for g in db.execute("SELECT run_id, start_ts, end_ts, origin FROM gaps"):
        a, b = epoch(g["start_ts"]), epoch(g["end_ts"])
        if a is None or b is None or b <= a:
            continue
        d = b - a
        kind = "notification" if g["origin"] not in (None, "human") else ("parked" if d > config.PARKED_AFTER_S else "human")
        out.append((g["run_id"], g["start_ts"], g["end_ts"], d, kind))
    for t in db.execute("SELECT run_id, ts, end_ts, dur_s, name, blocked FROM tool_calls WHERE end_ts IS NOT NULL AND dur_s IS NOT NULL "
                        "AND (name='AskUserQuestion' OR blocked=1)"):
        if t["name"] == "AskUserQuestion":
            kind = "parked" if t["dur_s"] > config.PARKED_AFTER_S else "ask"
        else:
            kind = "blocked"
        out.append((t["run_id"], t["ts"], t["end_ts"], t["dur_s"], kind))
    db.executemany("INSERT INTO waits VALUES(?,?,?,?,?)", out)


def stalled_gaps(db) -> dict[str, list[tuple[float, float, str]]]:
    """run_id -> [(start, end, ended_by)] for sub-agent runs that sat silent for more than STALLED_AFTER_S between two records.
    Excused: a gap that ends with the result of a test-class call, of a background call or of an Agent call (the wait is a test, a background
    task or a child run), a gap ended by a task notification (a background wait), and a gap lying inside a test call."""
    calls = {(r["run_id"], r["id"]): (r["name"], r["cmd_class"], r["background"]) for r in db.execute("SELECT run_id, id, name, cmd_class, background FROM tool_calls")}
    tests: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for t in db.execute("SELECT run_id, ts, end_ts FROM tool_calls WHERE end_ts IS NOT NULL AND cmd_class IN (%s)" % ",".join(f"'{c}'" for c in TEST_CLASSES)):  # nosec B608 - constants
        a, b = epoch(t["ts"]), epoch(t["end_ts"])
        if a is not None and b is not None:
            tests[t["run_id"]].append((a, b))
    out: dict[str, list[tuple[float, float, str]]] = defaultdict(list)
    for g in db.execute("SELECT run_id, start_ts, end_ts, to_kind, origin, tool_ids FROM idle"):
        a, b = epoch(g["start_ts"]), epoch(g["end_ts"])
        if a is None or b is None or b - a <= config.STALLED_AFTER_S:
            continue
        if g["to_kind"] == "prompt" and g["origin"] not in (None, "human"):
            continue                                                   # a background wait: a task notification ended it
        if g["to_kind"] == "result":
            infos = [calls.get((g["run_id"], i)) for i in json.loads(g["tool_ids"] or "[]")]
            if any(i and (i[1] in TEST_CLASSES or i[2] or i[0] in ("Agent", "Task")) for i in infos):
                continue
        covered = total(clip(tests.get(g["run_id"], []), a, b))
        if covered >= 0.5 * (b - a):
            continue
        out[g["run_id"]].append((a, b, g["to_kind"]))
    return dict(out)


def split_runs(db, rows: dict[str, dict[str, Any]], stalls: dict[str, list[tuple[float, float, str]]] | None = None) -> None:
    """Fill the time columns of every run row (in place): model_s, tool_s, test_s, test_*, human_wait_s, parked_s, blocked_s,
    notif_wait_s, unattributed_s.  tool_s and test_s are UNIONS of call intervals (parallel calls overlap)."""
    model = {r["run_id"]: r["model_s"] or 0.0 for r in db.execute("SELECT run_id, model_s FROM files")}
    tool: dict[str, list[tuple[float, float]]] = defaultdict(list)
    test: dict[str, list[tuple[float, float]]] = defaultdict(list)
    cnt: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for t in db.execute("SELECT run_id, ts, end_ts, name, cmd_class, background, timed_out, blocked, is_error FROM tool_calls WHERE end_ts IS NOT NULL"):
        a, b = epoch(t["ts"]), epoch(t["end_ts"])
        if a is None or b is None:
            continue
        rid, is_test = t["run_id"], t["cmd_class"] in TEST_CLASSES
        if is_test and t["background"]:
            cnt[rid]["bg"] += 1
            continue
        if is_test:
            cnt[rid]["n"] += 1
            cnt[rid]["fail"] += 1 if t["is_error"] else 0
            if t["timed_out"]:
                cnt[rid]["to"] += 1
                tool[rid].append((a, b))          # a timed-out test is not test time; it stays plain tool time
            else:
                test[rid].append((a, b))
        elif t["name"] not in NOT_TOOL_TIME and not t["blocked"] and t["name"] != "Bash-write":
            tool[rid].append((a, b))
    stalls = stalls or {}
    chars = {r["run_id"]: (r["relay"] or 0, r["tot"] or 0, r["hb"] or 0) for r in db.execute(
        "SELECT run_id, sum(CASE WHEN name IN ('Agent','Task','SendMessage') THEN in_chars + coalesce(out_chars, 0) ELSE 0 END) relay, "
        "sum(CASE WHEN name IN ('Agent','Task') THEN coalesce(out_chars, 0) ELSE 0 END) hb, "
        "sum(in_chars + coalesce(out_chars, 0)) tot FROM tool_calls WHERE name != 'Bash-write' GROUP BY run_id")}
    texts = {r["run_id"]: r["t"] or 0 for r in db.execute("SELECT run_id, sum(text_chars) t FROM messages GROUP BY run_id")}
    prompts = {r["run_id"]: r["prompt_chars"] or 0 for r in db.execute("SELECT run_id, prompt_chars FROM files")}
    wsum: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for w in db.execute("SELECT run_id, kind, SUM(dur_s) s FROM waits GROUP BY run_id, kind"):
        wsum[w["run_id"]][w["kind"]] = w["s"] or 0.0
    for rid, r in rows.items():
        a, b = epoch(r["start_ts"]), epoch(r["end_ts"])
        wall = max(0.0, b - a) if a is not None and b is not None else 0.0
        w, c = wsum.get(rid, {}), cnt.get(rid, {})
        st = stalls.get(rid, [])
        r["stalled_s"] = sum(b - a for a, b, to in st if to != "result")           # a stalled tool call is already tool / blocked time
        r["model_s"] = max(0.0, model.get(rid, 0.0) - sum(b - a for a, b, to in st if to == "assistant"))   # the silence before an answer is not model time
        relay, tot, hb = chars.get(rid, (0, 0, 0))
        r["relay_chars"], r["handback_chars"], r["prompt_chars"] = relay, hb, prompts.get(rid, 0)   # hand-backs = the reports that sub-agents return
        r["total_chars"] = tot + texts.get(rid, 0) + prompts.get(rid, 0)
        r["tool_s"] = total(tool.get(rid, []))
        r["test_s"] = total(test.get(rid, []))
        r["test_n"], r["test_fail"], r["test_timeouts"], r["test_bg_n"] = c.get("n", 0), c.get("fail", 0), c.get("to", 0), c.get("bg", 0)
        r["human_wait_s"] = w.get("human", 0.0) + w.get("ask", 0.0)
        r["parked_s"], r["blocked_s"], r["notif_wait_s"] = w.get("parked", 0.0), w.get("blocked", 0.0), w.get("notification", 0.0)
        used = r["model_s"] + r["tool_s"] + r["test_s"] + r["human_wait_s"] + r["parked_s"] + r["blocked_s"] + r["notif_wait_s"] + r["stalled_s"]
        r["unattributed_s"] = max(0.0, wall - used)
