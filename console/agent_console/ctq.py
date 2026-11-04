"""Cost / time / quality read side, part 1: load the index into memory once per index generation, resolve a period, select runs,
and compute every time term in ONE place (`ticket_time`), so each page and each bucket of a chart uses the same definitions.

Time terms (all clipped to the period):
  calendar   first start to last end of the ticket's runs
  open       the UNION of the run intervals (a session is open while any of its runs runs)
  waiting    human + ask waits of the ticket's main sessions, without parked
  parked     parked waits (a session left open: nights, weekends)
  blocked    blocked waits (a tool call that most likely sat on a permission prompt)
  working    open - (waiting + parked + blocked, as a union so nothing is subtracted twice)
Cost is exact: the sum of the usage rows (one per API message) whose message time falls in the period.
"""

from __future__ import annotations

import bisect
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from . import config, queries
from .flags import GATE_ROLES
from .parser import TEST_CLASSES
from .pricing import Pricing
from .store import Store
from .timing import clip, epoch, total, union

NOKEY = "(no ticket)"
NOISE_FLAGS = ("model_downgraded",)          # fires on most runs while a tier is unavailable: never counted
ATTENTION = ("deception", "out_of_scope_edit", "overthinking", "reject", "stalled")   # critical first
CRITICAL = ("deception", "out_of_scope_edit")
STAGES = [("Analysis", "g1", ["business-analyst", "system-analyst", "qa-analyst", "requirements-reviewer", "kit-analyst"]),
          ("Tests", "g2", ["test-designer", "lead-qa", "automation-engineer", "test-manager", "test-runner", "kit-test-designer"]),
          ("Build and checks", "g3", ["builder", "reviewer", "security-engineer", "environment-checker", "verifier", "independent-auditor", "kit-builder", "kit-reviewer", "kit-security", "kit-verifier"])]
STAGE_OF = {r: g for _, g, rs in STAGES for r in rs}
ROLE_ORDER = [r for _, _, rs in STAGES for r in rs]
NOT_PIPELINE = ("main", "general-purpose", "Explore", "fork", "claude-code-guide", "claude", "Plan")
SCORE_CHECKS = ("first_pass", "outcome", "judge", "follows", "grounded")      # scorer v2: the weighted checks (the gate "delivered" is not weighted)
WEIGHTS = {"first_pass": 0.25, "outcome": 0.30, "judge": 0.25, "follows": 0.10, "grounded": 0.10}
COVERAGE_MIN = 0.5


def project_of(key: str) -> str:
    return NOKEY if key == NOKEY else key.split("-")[0]


@dataclass
class Data:
    runs: dict[str, dict[str, Any]]
    usage: dict[str, list[tuple]]            # run_id -> [(t, cost, c_in, c_out, c_read, c_write, t_in, t_out, t_read, t_write)] sorted by t
    waits: dict[str, list[tuple]]            # run_id -> [(a, b, kind)]
    tests: dict[str, list[tuple]]            # run_id -> [(a, b, cls, is_error, timed_out)]
    unpriced: int
    t0: float
    t1: float


def get_data(store: Store, pricing: Pricing) -> Data:
    """Cached per (index generation, price table, score file, flag checks); a rescan that read nothing keeps the cache."""
    sp = config.scores_path()
    try:
        st = sp.stat()
        sig = (st.st_mtime_ns, st.st_size)
    except OSError:
        sig = (0, 0)
    key = (store.generation, id(pricing), sig, getattr(store, "flag_epoch", 0))
    hit = getattr(store, "_ctq_cache", None)
    if hit and hit[0] == key:
        return hit[1]
    d = _load(store, pricing)
    store._ctq_cache = (key, d)
    return d


def _load(store: Store, pricing: Pricing) -> Data:
    db = store.reader()
    try:
        runs = {r["run_id"]: dict(r) for r in db.execute("SELECT * FROM runs")}
        for (rid,) in db.execute("SELECT run_id FROM log_deleted"):
            if rid in runs:
                runs[rid]["log_deleted"] = True
        usage_rows = db.execute("SELECT run_id, ts, model, input, output, cache_read, cache_w5m, cache_w1h FROM usage").fetchall()
        wait_rows = db.execute("SELECT run_id, start_ts, end_ts, kind FROM waits").fetchall()
        marks = ",".join(f"'{c}'" for c in TEST_CLASSES)
        test_rows = db.execute("SELECT run_id, ts, end_ts, cmd_class, is_error, timed_out FROM tool_calls WHERE end_ts IS NOT NULL AND background=0 "  # nosec B608 - constants
                               f"AND cmd_class IN ({marks})").fetchall()
        fl: dict[str, set[str]] = defaultdict(set)
        for r in db.execute("SELECT run_id, flag FROM flags"):
            fl[r["run_id"]].add(r["flag"])
        checked = {(r["run_id"], r["flag"]): r["checked_at"] for r in db.execute("SELECT run_id, flag, checked_at FROM flag_checks")}
        evidence = {(r["run_id"], r["flag"]): json.loads(r["evidence"] or "{}") for r in db.execute("SELECT run_id, flag, evidence FROM flags")}
    finally:
        db.close()
    scores = {o["task_id"]: o for o in queries.score_lines()}
    for rid, r in runs.items():
        r["start_e"], r["end_e"] = epoch(r["start_ts"]) or 0.0, epoch(r["end_ts"]) or 0.0
        r["key"] = r["ticket_eff"] or NOKEY
        r["models"] = json.loads(r["models"] or "{}")
        line = scores.get(rid) or {}
        crit = {k: v.get("c") for k, v in (line.get("criteria") or {}).items()}
        real = line.get("S") is not None and not line.get("generic_for")
        evaluated = bool(crit) and not line.get("generic_for")          # a v2 line with checks counts even when S is hidden for too little evidence
        r["S"] = line.get("S") if real else None
        r["crit"] = crit if evaluated else {}
        r["evaluated"] = evaluated
        r["scorer_version"] = (2 if line.get("scorer_version") == 2 else 1) if line else None
        r["too_little"] = bool(line.get("too_little_evidence")) and evaluated
        r["coverage"] = line.get("coverage") if evaluated else None
        r["S_partial"] = line.get("S_partial") if evaluated and line.get("scorer_version") == 2 else None
        r["delivered"] = (line.get("gate") or {}).get("delivered") if evaluated and line.get("scorer_version") == 2 else None
        for k in ("round", "step", "input_tokens", "role_file_sha"):
            r["sc_" + k] = line.get(k) if line.get("scorer_version") == 2 else None
        r["scored_model"] = line.get("model")
        sk = line.get("skipped") or ""
        r["skip_kind"] = (line.get("skip_kind") or ("spawn_failure" if sk.startswith("spawn_failure") else None)) if sk and not line.get("generic_for") else None
        r["skip_reason"] = sk if r["skip_kind"] in SKIP_KINDS else None
        r["skip_kind"] = r["skip_kind"] if r["skip_kind"] in SKIP_KINDS else None
        r["judge_needed"] = bool(line.get("judge_needed")) if real else False
        extra = set(line.get("flags") or [])
        r["flags_all"] = sorted(fl.get(rid, set()) | extra)
        r["flags"] = [f for f in r["flags_all"] if f not in NOISE_FLAGS]
        for f in r["flags_all"]:
            r.setdefault("flag_info", {})[f] = {"checked_at": checked.get((rid, f)), "evidence": evidence.get((rid, f)) or (line.get("flag_evidence") or {}).get(f, {})}
        r["rework"] = "returned" in r["flags_all"]
    usage: dict[str, list[tuple]] = defaultdict(list)
    unpriced = 0
    for u in usage_rows:
        t = epoch(u["ts"])
        if t is None or u["run_id"] not in runs:
            continue
        toks = {"input": u["input"] or 0, "output": u["output"] or 0, "cache_read": u["cache_read"] or 0, "cache_w5m": u["cache_w5m"] or 0, "cache_w1h": u["cache_w1h"] or 0}
        parts, _ = pricing.message_cost_parts(u["model"], toks)
        if parts is None:
            unpriced += 1
            parts = {"input": 0.0, "output": 0.0, "cache_read": 0.0, "cache_write": 0.0}
        usage[u["run_id"]].append((t, sum(parts.values()), parts["input"], parts["output"], parts["cache_read"], parts["cache_write"],
                                   toks["input"], toks["output"], toks["cache_read"], toks["cache_w5m"] + toks["cache_w1h"]))
    for v in usage.values():
        v.sort()
    waits: dict[str, list[tuple]] = defaultdict(list)
    for w in wait_rows:
        a, b = epoch(w["start_ts"]), epoch(w["end_ts"])
        if a is not None and b is not None and b > a:
            waits[w["run_id"]].append((a, b, w["kind"]))
    tests: dict[str, list[tuple]] = defaultdict(list)
    for t in test_rows:
        a, b = epoch(t["ts"]), epoch(t["end_ts"])
        if a is not None and b is not None:
            tests[t["run_id"]].append((a, b, t["cmd_class"], t["is_error"], t["timed_out"] or 0))
    starts = [r["start_e"] for r in runs.values() if r["start_e"]]
    ends = [r["end_e"] for r in runs.values() if r["end_e"]]
    return Data(runs, dict(usage), dict(waits), dict(tests), unpriced, min(starts, default=0.0), max(ends, default=0.0))


# ---------------- period and buckets ----------------
@dataclass
class Period:
    lo: float
    hi: float

    def iso(self) -> dict[str, str]:
        tz = config.tz()
        return {"from": datetime.fromtimestamp(self.lo, tz).isoformat(timespec="seconds"), "to": datetime.fromtimestamp(self.hi, tz).isoformat(timespec="seconds")}


def _parse_when(s: str, end_of_day: bool = False) -> float:
    s = s.strip()
    tz = config.tz()
    if len(s) == 10:
        dt = datetime.fromisoformat(s).replace(tzinfo=tz)
        return (dt + timedelta(days=1)).timestamp() - 0.001 if end_of_day else dt.timestamp()
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return (dt if dt.tzinfo else dt.replace(tzinfo=tz)).timestamp()


def resolve_period(d: Data, frm: str | None, to: str | None) -> Period:
    lo = _parse_when(frm) if frm else d.t0
    hi = _parse_when(to, True) if to else max(d.t1, lo)
    if hi < lo:
        lo, hi = hi, lo
    return Period(lo, hi)


def buckets(per: Period) -> tuple[str, list[dict[str, Any]]]:
    """hour when the period is <= 2 days, day when <= 62 days, else week (Monday). Every bucket is returned, empty ones too."""
    tz = config.tz()
    span = per.hi - per.lo
    unit = "hour" if span <= 2 * 86400 else "day" if span <= 62 * 86400 else "week"
    cur = datetime.fromtimestamp(per.lo, tz)
    if unit == "hour":
        cur = cur.replace(minute=0, second=0, microsecond=0)
    else:
        cur = cur.replace(hour=0, minute=0, second=0, microsecond=0)
        if unit == "week":
            cur -= timedelta(days=cur.weekday())
    out = []
    prev_day = None
    while not out or cur.timestamp() < per.hi:
        nxt = cur + (timedelta(hours=1) if unit == "hour" else timedelta(days=7 if unit == "week" else 1))
        if unit == "hour":
            nxt = datetime.fromtimestamp(cur.timestamp() + 3600, tz)
            day = cur.strftime("%-d %b")
            label = cur.strftime("%H:%M") if day == prev_day else f"{day} {cur.strftime('%H:%M')}"
            prev_day = day
        elif unit == "week":
            label = "w/c " + cur.strftime("%-d %b")
        else:
            label = cur.strftime("%-d %b")
        out.append({"start": cur.isoformat(timespec="seconds"), "label": label, "lo": max(cur.timestamp(), per.lo), "hi": min(nxt.timestamp(), per.hi), "raw_lo": cur.timestamp()})
        cur = nxt
    return unit, out


# ---------------- selection ----------------
def select(d: Data, per: Period, scope: str = "project", proj: str = "", q: str = "") -> list[dict[str, Any]]:
    """Runs that match the filters and overlap the period. Each is the stored run dict plus its cost and tokens INSIDE the period."""
    out = []
    ql = (q or "").lower()
    for r in d.runs.values():
        if scope != "all" and r["scope"] != "project":
            continue
        if proj and project_of(r["key"]) != proj:
            continue
        if ql and ql not in r["key"].lower():
            continue
        a, b = r["start_e"], r["end_e"]
        if b <= a:
            if not per.lo <= a <= per.hi:
                continue
        elif min(b, per.hi) <= max(a, per.lo):
            continue
        out.append(r)
    return out


def cost_in(d: Data, r: dict[str, Any], per: Period) -> dict[str, float]:
    """cost / tokens of one run inside the period, from its usage rows (exact)."""
    rows = d.usage.get(r["run_id"], [])
    c = {"cost": 0.0, "input": 0.0, "output": 0.0, "cache_read": 0.0, "cache_write": 0.0, "t_in": 0, "t_out": 0, "t_read": 0, "t_write": 0, "calls": 0}
    if not rows:
        return c
    i = bisect.bisect_left(rows, (per.lo,))
    j = bisect.bisect_right(rows, (per.hi, float("inf")))
    for t, cost, ci, co, cr, cw, ti, to, tr, tw in rows[i:j]:
        c["cost"] += cost
        c["input"] += ci
        c["output"] += co
        c["cache_read"] += cr
        c["cache_write"] += cw
        c["t_in"] += ti
        c["t_out"] += to
        c["t_read"] += tr
        c["t_write"] += tw
        c["calls"] += 1
    return c


# ---------------- time terms ----------------
def run_interval(r: dict[str, Any]) -> tuple[float, float]:
    return r["start_e"], r["end_e"]


def ticket_time(d: Data, runs: list[dict[str, Any]], lo: float, hi: float) -> dict[str, float]:
    """The one definition of every time term for a set of runs (a ticket), clipped to [lo, hi]. See the module docstring."""
    ivs = clip((run_interval(r) for r in runs if r["end_e"] > r["start_e"]), lo, hi)
    open_u = union(ivs)
    wait_iv, park_iv, block_iv, test_iv = [], [], [], []
    n = fail = tout = 0
    for r in runs:
        main = r["kind"] == "main"
        for a, b, kind in d.waits.get(r["run_id"], []):
            if kind == "blocked":
                block_iv.append((a, b))
            elif main and kind in ("human", "ask"):
                wait_iv.append((a, b))
            elif main and kind == "parked":
                park_iv.append((a, b))
        for a, b, cls, err, timed_out in d.tests.get(r["run_id"], []):
            if lo <= a <= hi:
                n += 1
                fail += 1 if err else 0
                tout += 1 if timed_out else 0
                if not timed_out:
                    test_iv.append((a, b))
    wait_c, park_c, block_c = clip(wait_iv, lo, hi), clip(park_iv, lo, hi), clip(block_iv, lo, hi)
    # waits and the open union are both clipped to the period; the waits lie inside the main sessions, which lie inside the union
    away = total(union(clip(wait_c + park_c + block_c, lo, hi)))
    op = total(open_u)
    first = min((a for a, _ in open_u), default=0.0)
    last = max((b for _, b in open_u), default=0.0)
    return {"calendar_s": max(0.0, last - first), "first": first, "last": last, "open_s": op, "waiting_s": total(wait_c), "parked_s": total(park_c),
            "blocked_s": total(block_c), "working_s": max(0.0, op - away), "test_s": total(clip(test_iv, lo, hi)),
            "test_n": n, "test_fail": fail, "test_timeouts": tout}


def pass_count(runs: list[dict[str, Any]], check: str) -> list[int] | None:
    """[passed, of] over the evaluated runs that have a value for this check (a check that is empty is not counted). Passed = 1.0."""
    vals = [r["crit"][check] for r in runs if r.get("evaluated") and r["crit"].get(check) is not None]
    return [sum(1 for v in vals if v >= 1), len(vals)] if vals else None


SKIP_KINDS = {"probe": "probe", "api_error": "ended by API error", "spawn_failure": "spawn failure"}      # skipped runs the person should see; "not a role task" lines are not shown


def mean_check(runs: list[dict[str, Any]], check: str) -> float | None:
    vals = [r["crit"][check] for r in runs if r.get("evaluated") and r["crit"].get(check) is not None]
    return sum(vals) / len(vals) if vals else None


def delivered_count(runs: list[dict[str, Any]]) -> list[int] | None:
    """[delivered, of] over the v2-evaluated runs: the gate that replaces "done"."""
    vals = [r["delivered"] for r in runs if r.get("evaluated") and r.get("delivered") is not None]
    return [sum(1 for v in vals if v), len(vals)] if vals else None


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return None
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def session_modes(runs: list[dict[str, Any]]) -> dict[str, str]:
    """run_id -> "shared" | "own". A run is shared when its parent session started SHARED_SESSION_ROLES or more different roles in the
    selection (the coordinator running the pipeline in one place). A main session started with `--agent <role>` is that role's own session."""
    roles: dict[str, set[str]] = defaultdict(set)
    for r in runs:
        if r["kind"] == "sub":
            roles[r["session_id"]].add(r["role"])
    return {r["run_id"]: ("shared" if r["kind"] == "sub" and len(roles.get(r["session_id"], ())) >= config.SHARED_SESSION_ROLES else "own") for r in runs}


def handoffs(subs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every role is started by the coordinator, so "A -> B" means B started right after A's run was the last one to finish
    (ties within 1 s). It shows the order of work, not who called whom. `sent_back` = the predecessor is a gate role and this run is rework."""
    subs = sorted(subs, key=lambda r: (r["start_e"], r["end_e"]))
    steps = []
    for j, r in enumerate(subs):
        pred, pi = None, -1
        for i in range(j):
            q = subs[i]
            if q["end_e"] <= r["start_e"] + 1.0 and (pred is None or q["end_e"] > pred["end_e"]):
                pred, pi = q, i
        parallel = any(i != j and q["start_e"] < r["end_e"] and r["start_e"] < q["end_e"] for i, q in enumerate(subs))
        sent_back = bool(pred) and pred["role"] in GATE_ROLES and r["rework"]
        how = "sent back by the gate" if sent_back else "in parallel with another role" if parallel else "same role again" if pred and pred["role"] == r["role"] else "next"
        steps.append({"n": j + 1, "run_id": r["run_id"], "from_role": pred["role"] if pred else None, "to_role": r["role"], "pred_index": pi,
                      "start": r["start_ts"], "parallel": parallel, "sent_back": sent_back, "rework": r["rework"], "how": how, "S": r["S"],
                      "duration_s": max(0.0, r["end_e"] - r["start_e"])})
    return steps
