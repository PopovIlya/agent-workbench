"""Cost / time / quality read side, part 2: the payload of each page, and the "What stands out" findings.

Findings are computed here, one list per page; a finding appears only when its condition holds. The page never writes a conclusion itself.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from . import config, events, gold
from .ctq import (SKIP_KINDS, ATTENTION, CRITICAL, NOKEY, NOT_PIPELINE, ROLE_ORDER, SCORE_CHECKS, STAGE_OF, STAGES, WEIGHTS, Data, Period, buckets, cost_in,
                  delivered_count, handoffs, mean, mean_check, median, pass_count, project_of, select, session_modes, ticket_time)
from .pricing import Pricing
from .store import Store
from .timing import total, union

BAR = 0.85
MIN_RUNS_FOR_CHANGE = 10      # a change is called a change only when both sides have at least this many runs


# ---------------- formatting for findings ----------------
def usd(v: float | None) -> str:
    if v is None:
        return "—"
    if v == 0:
        return "$0"
    if v < 0.995:
        return f"${v:.2f}"
    if v < 99.5:
        return f"${v:.1f}"
    return "$" + f"{round(v):,}"


def dur(s: float | None) -> str:
    if s is None:
        return "—"
    if s < 1:
        return "0 s"
    if s < 60:
        return f"{round(s)} s"
    if s < 3600:
        return f"{round(s / 60)} min"
    if s < 100 * 3600:
        return f"{s / 3600:.1f} h" if s < 10 * 3600 else f"{round(s / 3600)} h"
    return f"{s / 86400:.1f} d"


def pct(v: float) -> str:
    return f"{round(v * 100)}%"


def iso(t: float | None) -> str | None:
    return datetime.fromtimestamp(t, config.tz()).isoformat(timespec="seconds") if t else None


# ---------------- shared pieces ----------------
class Ctx:
    """One selection for one request: the runs, their cost in the period (computed once) and the per-ticket groups."""

    def __init__(self, store: Store, pricing: Pricing, d: Data, per: Period, scope: str, proj: str, q: str):
        self.store, self.pricing, self.d, self.per, self.scope = store, pricing, d, per, scope
        self.sel = select(d, per, scope, proj, q)
        self.ci = {r["run_id"]: cost_in(d, r, per) for r in self.sel}
        self.started = {r["run_id"]: per.lo <= r["start_e"] <= per.hi for r in self.sel}
        self.groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in self.sel:
            self.groups[r["key"]].append(r)
        self.mode = session_modes(self.sel)

    def scored(self, runs):
        return [r for r in runs if self.started[r["run_id"]] and r["S"] is not None]

    def evaluated(self, runs):
        return [r for r in runs if self.started[r["run_id"]] and r.get("evaluated")]

    def flagged(self, runs):
        return [(r, f) for r in runs if self.started[r["run_id"]] for f in r["flags"]]

    def cost(self, runs, kind: str | None = None) -> float:
        return sum(self.ci[r["run_id"]]["cost"] for r in runs if kind is None or (r["kind"] == "main") == (kind == "main"))

    def clipped(self, r) -> float:
        return max(0.0, min(r["end_e"], self.per.hi) - max(r["start_e"], self.per.lo))


def ticket_row(c: Ctx, key: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    t = ticket_time(c.d, runs, c.per.lo, c.per.hi)
    sc = c.scored(runs)
    moved = [{"run_id": r["run_id"], "own_key": r["ticket"] or NOKEY, "children": r["eff_children"], "share_n": r["eff_share_n"]}
             for r in runs if r["kind"] == "main" and r["ticket_eff_via"] == "children" and r["ticket_eff"] != r["ticket"]]
    badges = {"moved_main": moved, "umbrella": t["calendar_s"] > config.UMBRELLA_DAYS * 86400 and key != NOKEY, "tool_waits": t["blocked_s"] > 0}
    return {"ticket": key, "project": project_of(key), "cost": c.cost(runs), "cost_main": c.cost(runs, "main"), "cost_sub": c.cost(runs, "sub"),
            "first": iso(t["first"]), "last": iso(t["last"]), "calendar_s": t["calendar_s"], "working_s": t["working_s"], "waiting_s": t["waiting_s"],
            "parked_s": t["parked_s"], "blocked_s": t["blocked_s"], "test_s": t["test_s"], "test_n": t["test_n"], "test_fail": t["test_fail"],
            "test_timeouts": t["test_timeouts"], "runs": len(runs), "roles": len({r["role"] for r in runs if r["kind"] == "sub"}),
            "main_sessions": sum(1 for r in runs if r["kind"] == "main"),
            "S": mean(r["S"] for r in sc), "n_S": len(sc), "n_eval": len(c.evaluated(runs)), "n_too_little": sum(1 for r in c.evaluated(runs) if r["too_little"]),
            "flags": sum(len(r["flags"]) for r in runs if c.started[r["run_id"]]), "badges": badges}


def all_ticket_rows(c: Ctx) -> list[dict[str, Any]]:
    return [ticket_row(c, k, v) for k, v in c.groups.items()]


def period_info(c: Ctx) -> dict[str, Any]:
    unit, bk = buckets(c.per)
    pr = c.store.progress
    return {**c.per.iso(), "unit": unit, "runs": len(c.sel), "scope": c.scope, "incomplete": pr.get("state") == "indexing" and bool(pr.get("initial"))}


def run_out(c: Ctx, r: dict[str, Any]) -> dict[str, Any]:
    ci = c.ci.get(r["run_id"]) or cost_in(c.d, r, c.per)
    return {"run_id": r["run_id"], "session_id": r["session_id"], "role": r["role"], "kind": r["kind"], "ticket": r["key"], "own_ticket": r["ticket"] or NOKEY,
            "start": iso(r["start_e"]), "end": iso(r["end_e"]), "duration_s": max(0.0, r["end_e"] - r["start_e"]), "duration_in_period_s": c.clipped(r),
            "cost": ci["cost"], "rounds": ci["calls"], "S": r["S"], "criteria": r["crit"], "flags": r["flags"], "rework": r["rework"],
            "mode": c.mode.get(r["run_id"], "own"), "stage": STAGE_OF.get(r["role"]), "parent_run_id": r["parent_run_id"],
            "round": r.get("sc_round"), "step": r.get("sc_step"), "delivered": r.get("delivered"), "too_little": r.get("too_little"), "coverage": r.get("coverage"),
            "skip_kind": r.get("skip_kind"), "skip_label": SKIP_KINDS.get(r.get("skip_kind") or ""), "skip_reason": r.get("skip_reason"),
            "log_deleted": bool(r.get("log_deleted"))}


def stand_out(*items: str | None) -> list[str]:
    return [i for i in items if i]


# ---------------- overview ----------------
def overview(c: Ctx) -> dict[str, Any]:
    rows = all_ticket_rows(c)
    spend = sum(r["cost"] for r in rows)
    main = sum(r["cost_main"] for r in rows)
    parts = {k: sum(c.ci[r["run_id"]][k] for r in c.sel) for k in ("input", "output", "cache_read", "cache_write")}
    scored = c.scored(c.sel)
    delivered = delivered_count(c.evaluated(c.sel))
    evaluated = c.evaluated(c.sel)
    kp = {"spend": spend, "main_share": (main / spend) if spend else 0.0, "working_s": sum(r["working_s"] for r in rows), "waiting_s": sum(r["waiting_s"] for r in rows),
          "parked_s": sum(r["parked_s"] for r in rows), "blocked_s": sum(r["blocked_s"] for r in rows), "test_s": sum(r["test_s"] for r in rows),
          "test_n": sum(r["test_n"] for r in rows), "test_fail": sum(r["test_fail"] for r in rows), "test_timeouts": sum(r["test_timeouts"] for r in rows),
          "S": mean(r["S"] for r in scored), "n_S": len(scored), "delivered": delivered, "n_evaluated": len(evaluated),
          "n_too_little": sum(1 for r in evaluated if r["too_little"]), "runs": len(c.sel), "tickets": len(rows)}
    by_cost = sorted(rows, key=lambda r: -r["cost"])
    by_time = sorted(rows, key=lambda r: -(r["working_s"] + r["waiting_s"]))
    top = {"cost_main": sum(r["cost_main"] for r in by_cost[10:]), "cost_sub": sum(r["cost_sub"] for r in by_cost[10:]), "n": max(0, len(by_cost) - 10)}
    pick = lambda r: {k: r[k] for k in ("ticket", "cost", "cost_main", "cost_sub", "working_s", "waiting_s", "parked_s", "test_s", "calendar_s", "runs", "roles")}   # noqa: E731
    sessions = sorted((r for r in c.sel if r["kind"] == "main" and c.ci[r["run_id"]]["calls"]), key=lambda r: -c.ci[r["run_id"]]["cost"])[:3]
    top_sessions = [session_row(c, r) for r in sessions]
    needs = needs_person(c)
    series = time_series(c)
    return {"period": period_info(c), "kpis": kp, "needs_person": needs, "cost_by_ticket": [pick(r) for r in by_cost[:10]], "cost_by_ticket_more": top,
            "time_by_ticket": [pick(r) for r in by_time[:10]], "series": series, "cost_by_token_type": parts, "top_sessions": top_sessions,
            "unpriced_messages": c.d.unpriced, "findings": overview_findings(kp, parts, top_sessions, scored)}


def overview_findings(kp, parts, top_sessions, scored) -> list[str]:
    cost = kp["spend"]
    out = []
    if cost and parts["cache_read"] / cost > 0.4:
        out.append(f"{pct(parts['cache_read'] / cost)} of the spend is cache read: the model re-reading long conversations on every call.")
    big = [s for s in top_sessions if s["context_per_call"] > config.CONTEXT_RED_TOKENS]
    if top_sessions and big:
        ctx = median([s["context_per_call"] for s in top_sessions])
        n = len(top_sessions)
        out.append(f"The {'most expensive session' if n == 1 else f'{n} most expensive sessions'} cost {usd(sum(s['cost'] for s in top_sessions))}; each call re-read about "
                   f"{round(ctx / 1000)}k tokens, where a fresh session re-reads 40–100k. Restarting long sessions is the biggest saving.")
    if kp["working_s"] and kp["waiting_s"] > kp["working_s"]:
        out.append(f"Agents waited for you {dur(kp['waiting_s'])} against {dur(kp['working_s'])} of work.")
    if kp["parked_s"] >= 3600:
        out.append(f"{dur(kp['parked_s'])} more were parked: a session left open for more than {config.PARKED_AFTER_S // 3600} hours. It is not counted as waiting for you.")
    if kp["n_evaluated"] and kp["n_too_little"] / kp["n_evaluated"] >= 0.3:
        out.append(f"S is hidden for {kp['n_too_little']} of {kp['n_evaluated']} evaluated runs: the checks that have data carry less than half of the weight (too little evidence). "
                   "Most outcome checks wait for data: mutation runs, defect reports, your verdicts.")
    if kp["delivered"] and kp["delivered"][1] and kp["delivered"][0] < kp["delivered"][1]:
        out.append(f"{kp['delivered'][1] - kp['delivered'][0]} of {kp['delivered'][1]} evaluated runs did not deliver what their role is for (S = 0 for those).")
    return out


def needs_person(c: Ctx) -> dict[str, Any]:
    items = []
    checked = 0
    for r, f in c.flagged(c.sel):
        if f not in ATTENTION:
            continue
        info = (r.get("flag_info") or {}).get(f, {})
        if info.get("checked_at"):
            checked += 1
            continue
        items.append({"run_id": r["run_id"], "flag": f, "level": "crit" if f in CRITICAL else "warn", "role": r["role"], "ticket": r["key"], "start": iso(r["start_e"]),
                      "cost": c.ci[r["run_id"]]["cost"], "evidence": info.get("evidence", {}), "decidable": f == "deception", "_t": r["start_e"]})
    items.sort(key=lambda x: (0 if x['level'] == 'crit' else 1, -x['_t']))
    for x in items:
        x.pop('_t')
    return {"items": items[:100], "total": len(items), "checked": checked}


def time_series(c: Ctx) -> dict[str, Any]:
    unit, bk = buckets(c.per)
    starts = [b["raw_lo"] for b in bk]
    out = [{"start": b["start"], "label": b["label"], "cost_main": 0.0, "cost_sub": 0.0, "working_s": 0.0, "waiting_s": 0.0, "parked_s": 0.0, "S": None, "n_S": 0} for b in bk]
    import bisect
    for r in c.sel:
        for t, cost, *_ in c.d.usage.get(r["run_id"], []):
            if not c.per.lo <= t <= c.per.hi:
                continue
            i = max(0, bisect.bisect_right(starts, t) - 1)
            out[i]["cost_main" if r["kind"] == "main" else "cost_sub"] += cost
    for key, runs in c.groups.items():
        first = min(r["start_e"] for r in runs)
        last = max(r["end_e"] for r in runs)
        for i, b in enumerate(bk):
            if last <= b["lo"] or first >= b["hi"]:
                continue
            tt = ticket_time(c.d, runs, b["lo"], b["hi"])
            out[i]["working_s"] += tt["working_s"]
            out[i]["waiting_s"] += tt["waiting_s"]
            out[i]["parked_s"] += tt["parked_s"]
    sc: list[list[float]] = [[] for _ in bk]
    for r in c.scored(c.sel):
        i = max(0, bisect.bisect_right(starts, r["start_e"]) - 1)
        sc[i].append(r["S"])
    for i, xs in enumerate(sc):
        out[i]["S"], out[i]["n_S"] = mean(xs), len(xs)
    return {"unit": unit, "buckets": out}


# ---------------- tickets ----------------
SORTABLE = {"ticket", "cost", "calendar_s", "working_s", "waiting_s", "parked_s", "test_s", "runs", "roles", "S", "flags", "first", "last"}


def tickets(c: Ctx, sort: str = "cost", desc: bool = True, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    rows = all_ticket_rows(c)
    sort = sort if sort in SORTABLE else "cost"
    have = [r for r in rows if r[sort] is not None]
    none = [r for r in rows if r[sort] is None]
    have.sort(key=lambda r: r[sort], reverse=desc)       # tickets without a value (e.g. no score) always go last
    rows = have + none
    return {"period": period_info(c), "total": len(rows), "offset": offset, "rows": rows[offset:offset + max(1, min(limit, 500))],
            "findings": tickets_findings(rows)}


def tickets_findings(rows) -> list[str]:
    moved = [r for r in rows if r["badges"]["moved_main"]]
    umb = [r for r in rows if r["badges"]["umbrella"]]
    tw = [r for r in rows if r["badges"]["tool_waits"]]
    s = lambda xs: ", ".join(r["ticket"] for r in xs[:6]) + (f" and {len(xs) - 6} more" if len(xs) > 6 else "")   # noqa: E731
    return stand_out(
        f"{s(moved)}: include{'s' if len(moved) == 1 else ''} a main session that its branch name filed under another ticket; it counts here because its sub-agents worked on this one." if moved else None,
        f"{s(umb)}: span{'s' if len(umb) == 1 else ''} more than a week, probably an umbrella key for unrelated work, so the totals mix several tasks." if umb else None,
        f"{s(tw)}: a tool call sat for more than {config.BLOCKED_AFTER_S // 60} minutes, most likely a permission prompt. That time is shown as blocked, not as work." if tw else None)


# ---------------- one ticket ----------------
def ticket_detail(c: Ctx, key: str) -> dict[str, Any]:
    runs = [r for r in c.sel if r["key"] == key]
    if not runs:
        return {"period": period_info(c), "ticket": key, "empty": True}
    row = ticket_row(c, key, runs)
    subs = sorted((r for r in runs if r["kind"] == "sub"), key=lambda r: r["start_e"])
    steps = handoffs(subs)
    by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in runs:
        by_role[r["role"]].append(r)
    agents = []
    for role in sorted((x for x in by_role if x != "main"), key=lambda x: (ROLE_ORDER.index(x) if x in ROLE_ORDER else 99, x)):
        a = by_role[role]
        sc = c.scored(a)
        par = max(sum(1 for q in a if q["start_e"] < r["end_e"] and r["start_e"] < q["end_e"]) for r in a)
        agents.append({"role": role, "agents": len(a), "sessions": len({r["session_id"] for r in a}), "shared": sum(1 for r in a if c.mode[r["run_id"]] == "shared"),
                       "rework": sum(1 for r in a if r["rework"]), "max_parallel": par, "cost": c.cost(a), "run_time_s": sum(c.clipped(r) for r in a),
                       "S": mean(r["S"] for r in sc), "n_S": len(sc)})
    waits, tests = [], []
    for r in runs:
        for a, b, kind in c.d.waits.get(r["run_id"], []):
            if r["kind"] == "main" and kind != "notification" or kind == "blocked":
                if b > c.per.lo and a < c.per.hi:
                    waits.append({"run_id": r["run_id"], "start": iso(max(a, c.per.lo)), "end": iso(min(b, c.per.hi)), "kind": kind})
        for a, b, cls, err, timed_out in c.d.tests.get(r["run_id"], []):
            if c.per.lo <= a <= c.per.hi:
                tests.append({"run_id": r["run_id"], "start": iso(a), "duration_s": b - a, "class": cls, "is_error": bool(err), "timed_out": bool(timed_out)})
    roles_out = []
    for role, a in sorted(by_role.items(), key=lambda kv: -c.cost(kv[1])):
        sc = c.scored(a)
        roles_out.append({"role": role, "runs": len(a), "cost": c.cost(a), "run_time_s": sum(c.clipped(r) for r in a), "S": mean(r["S"] for r in sc), "n_S": len(sc),
                          "pass": {k: pass_count(c.evaluated(a), k) for k in SCORE_CHECKS}, "mean": {k: mean_check(c.evaluated(a), k) for k in SCORE_CHECKS}, "delivered": delivered_count(c.evaluated(a)),
                          "n_eval": len(c.evaluated(a)), "flags": dict(Counter(f for r in a if c.started[r["run_id"]] for f in r["flags"]))})
    return {"period": period_info(c), "ticket": key, "row": row, "handoffs": steps, "agents_by_role": agents, "runs": [run_out(c, r) for r in sorted(runs, key=lambda r: r["start_e"])],
            "waits": sorted(waits, key=lambda w: w["start"]), "tests": sorted(tests, key=lambda t: t["start"]), "by_role": roles_out, "findings": ticket_findings(c, key, runs, row),
            "verdict": gold.latest_verdicts().get(key), "defects": gold.defects(key)}


def ticket_findings(c: Ctx, key: str, runs, row) -> list[str]:
    moved = row["badges"]["moved_main"]
    out = []
    if moved:
        m = moved[0]
        out.append(f"The main session here ran on a branch named {m['own_key']}; it counts on {key} because {m['share_n']} of {m['children']} of its sub-agents worked on {key}.")
    if row["badges"]["tool_waits"]:
        out.append(f"A tool call sat for more than {config.BLOCKED_AFTER_S // 60} minutes ({dur(row['blocked_s'])} in total), most likely a permission prompt. It is shown as blocked, not as work.")
    if row["badges"]["umbrella"]:
        out.append("This key spans more than a week: probably an umbrella key used for unrelated work, so its totals mix several tasks.")
    if row["parked_s"] >= 3600:
        out.append(f"{dur(row['parked_s'])} were parked: a session left open for more than {config.PARKED_AFTER_S // 3600} hours. It is not counted as waiting for you.")
    if row["working_s"] and row["waiting_s"] > row["working_s"]:
        out.append(f"The agents waited for you {dur(row['waiting_s'])}, longer than they worked ({dur(row['working_s'])}).")
    ev = c.evaluated(runs)
    dl = delivered_count(ev)
    if dl and dl[0] < dl[1]:
        out.append(f"{dl[1] - dl[0]} of {dl[1]} evaluated runs did not deliver what their role is for.")
    if ev and sum(1 for r in ev if r["too_little"]) >= len(ev) / 2:
        out.append("S is hidden for most runs here: the checks that have data carry less than half of the weight.")
    return [x for x in out if x]


# ---------------- roles ----------------
def role_stats(c: Ctx, role: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    sc = c.scored(runs)
    ev = c.evaluated(runs)
    tests = [(a, b, cls, e, to) for r in runs for (a, b, cls, e, to) in c.d.tests.get(r["run_id"], []) if c.per.lo <= a <= c.per.hi]
    n_flags = sum(len(r["flags"]) for r in runs if c.started[r["run_id"]])
    covs = [r["coverage"] for r in ev if r["coverage"] is not None]
    return {"role": role, "pipeline_role": role not in NOT_PIPELINE, "stage": STAGE_OF.get(role), "runs": len(runs), "tickets": len({r["key"] for r in runs}),
            "cost": c.cost(runs), "median_cost_per_run": median([c.ci[r["run_id"]]["cost"] for r in runs]), "median_run_time_s": median([c.clipped(r) for r in runs]),
            "test_s": total(union([(a, b) for a, b, _, _, to in tests if not to])), "test_n": len(tests), "S": mean(r["S"] for r in sc), "n_S": len(sc),
            "n_eval": len(ev), "n_too_little": sum(1 for r in ev if r["too_little"]), "coverage": mean(covs), "delivered": delivered_count(ev),
            "distinct_S": len({round(r["S"], 2) for r in sc}),
            "pass": {k: pass_count(ev, k) for k in SCORE_CHECKS}, "mean": {k: mean_check(ev, k) for k in SCORE_CHECKS},
            "empty_share": {k: (sum(1 for r in ev if r["crit"].get(k) is None) / len(ev)) if ev else None for k in SCORE_CHECKS},
            "flags": n_flags, "flags_per_run": (n_flags / len(runs)) if runs else 0.0,
            "skipped": {k: sum(1 for r in runs if r.get("skip_kind") == k) for k in SKIP_KINDS if any(r.get("skip_kind") == k for r in runs)},
            "n_skipped": sum(1 for r in runs if r.get("skip_kind"))}


def rank_within_role(scored: list[dict[str, Any]]) -> dict[str, float]:
    """run_id -> the share of the SAME role's other scored runs that scored lower, ties counting half. 50% = a usual run for the role.
    A role with one scored run has no one to compare with: 0.5. It puts roles with different checks on one scale."""
    by: dict[str, list[float]] = defaultdict(list)
    for r in scored:
        by[r["role"]].append(r["S"])
    out = {}
    for r in scored:
        a = by[r["role"]]
        lower = sum(1 for v in a if v < r["S"])
        equal = sum(1 for v in a if v == r["S"]) - 1          # without the run itself
        out[r["run_id"]] = 0.5 if len(a) < 2 else (lower + 0.5 * equal) / (len(a) - 1)
    return out


def history(c: Ctx, runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every evaluated run is a point. A run whose S is hidden for too little evidence stays in the history (S null, S_partial for its place, rank null)."""
    seen = {r["run_id"] for r in c.scored(runs)}
    hs = sorted(c.scored(runs) + [r for r in c.evaluated(runs) if r["run_id"] not in seen], key=lambda r: r["start_e"])
    rk = rank_within_role([r for r in hs if r["S"] is not None])
    return [{"run_id": r["run_id"], "rank": rk.get(r["run_id"]), "S_partial": r.get("S_partial"), "too_little": r["S"] is None, "role": r["role"], "ticket": r["key"], "start": iso(r["start_e"]), "S": r["S"], "criteria": r["crit"], "flags": r["flags"],
             "rework": r["rework"], "stage": STAGE_OF.get(r["role"]), "models": r["models"], "scorer_version": r["scorer_version"], "coverage": r["coverage"],
             "round": r["sc_round"], "step": r["sc_step"], "input_tokens": r["sc_input_tokens"], "role_file_sha": r["sc_role_file_sha"], "model": r["scored_model"],
             "delivered": r["delivered"]} for r in hs]


def session_mode_table(c: Ctx, by_role: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    mains: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in c.sel:
        if r["kind"] == "main" and r.get("agent_setting") in ROLE_ORDER:
            mains[r["agent_setting"]].append(r)          # a main session started with `--agent <role>` is that role's own session
    out = []
    for role in ROLE_ORDER:
        runs = by_role.get(role, [])
        if not runs and not mains.get(role):
            continue

        def side(rs, scored):
            sc = c.scored(scored)
            return {"runs": len(rs), "n_S": len(sc), "S": mean(r["S"] for r in sc), "median_cost": median([c.ci[r["run_id"]]["cost"] for r in rs]),
                    "median_time_s": median([c.clipped(r) for r in rs])}
        sh = side([r for r in runs if c.mode[r["run_id"]] == "shared"], [r for r in runs if c.mode[r["run_id"]] == "shared"])
        own_runs = [r for r in runs if c.mode[r["run_id"]] == "own"]
        ow = side(own_runs + mains.get(role, []), own_runs)
        verdict = None
        if sh["n_S"] >= config.MIN_SCORED_FOR_VERDICT and ow["n_S"] >= config.MIN_SCORED_FOR_VERDICT:
            diff = round(abs(ow["S"] - sh["S"]) * 100)
            verdict = {"better": "own" if ow["S"] > sh["S"] else "shared", "points": diff}
        out.append({"role": role, "shared": sh, "own": ow, "verdict": verdict})
    return out


def role_matrix(c: Ctx, limit: int) -> dict[str, Any]:
    """Runs of each role per ticket (newest ticket first). Tickets with only a main session are left out. limit 0 = all."""
    subs = [r for r in c.sel if r["kind"] == "sub"]
    last: dict[str, float] = {}
    for r in subs:
        last[r["key"]] = max(last.get(r["key"], 0.0), r["start_e"])
    keys = sorted(last, key=lambda k: -last[k])
    shown = keys[:limit] if limit else keys
    cols = [x for x in ROLE_ORDER if any(r["role"] == x for r in subs)] + (["other"] if any(r["role"] not in STAGE_OF for r in subs) else [])
    rows = []
    for k in shown:
        cells: dict[str, Any] = {}
        for r in (x for x in subs if x["key"] == k):
            col = r["role"] if r["role"] in STAGE_OF else "other"
            cell = cells.setdefault(col, {"n": 0, "rework": 0, "S": [], })
            cell["n"] += 1
            cell["rework"] += 1 if r["rework"] else 0
            if c.started[r["run_id"]] and r["S"] is not None:
                cell["S"].append(r["S"])
        rows.append({"ticket": k, "total": sum(v["n"] for v in cells.values()),
                     "cells": {col: {"n": v["n"], "rework": v["rework"], "S": mean(v["S"]), "n_S": len(v["S"])} for col, v in cells.items()}})
    return {"columns": cols, "rows": rows, "total_tickets": len(keys)}


def roles(c: Ctx, matrix_limit: int = 30) -> dict[str, Any]:
    by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in c.sel:
        by_role[r["role"]].append(r)
    rows = [role_stats(c, role, rs) for role, rs in by_role.items()]
    rows.sort(key=lambda r: -r["cost"])
    pipeline_runs = [r for r in c.sel if r["role"] not in NOT_PIPELINE]
    modes = session_mode_table(c, by_role)
    return {"period": period_info(c), "stages": [{"name": n, "key": g, "roles": rs} for n, g, rs in STAGES], "rows": rows,
            "history": history(c, pipeline_runs), "session_mode": modes, "matrix": role_matrix(c, matrix_limit), "verdict_panel": verdict_panel(c),
            "findings": roles_findings(c, rows, modes)}


def roles_findings(c: Ctx, rows, modes) -> list[str]:
    pipe = [r for r in rows if r["pipeline_role"]]
    ev = c.evaluated([r for r in c.sel if r["role"] not in NOT_PIPELINE])
    dl = delivered_count(ev)
    few = [r["role"] for r in pipe if 0 < r["n_S"] < config.MIN_SCORED_FOR_VERDICT]
    hidden = [r["role"] for r in pipe if r["n_eval"] and r["n_too_little"] == r["n_eval"]]
    dear = sorted((r for r in pipe if r["runs"] >= 3), key=lambda r: -(r["median_cost_per_run"] or 0))[:1]
    main_cost = c.cost([r for r in c.sel if r["kind"] == "main"])
    sub_cost = c.cost([r for r in c.sel if r["kind"] == "sub"])
    out = []
    if ev:
        txt = f"S is shown for {sum(1 for r in ev if r['S'] is not None)} of {len(ev)} evaluated pipeline runs"
        if dl:
            txt += f"; {dl[0]} of {dl[1]} delivered what their role is for"
        out.append(txt + ".")
    if hidden:
        out.append(f"{', '.join(hidden)}: no S yet, the checks that have data carry less than half of the weight (too little evidence). Outcome checks wait for mutation runs, defect reports and your verdicts.")
    if few:
        out.append(f"{', '.join(few)}: fewer than {config.MIN_SCORED_FOR_VERDICT} scored runs, too few to judge.")
    if dear:
        out.append(f"Most expensive pipeline role per run: {dear[0]['role']}, {usd(dear[0]['median_cost_per_run'])} (median of {dear[0]['runs']} runs).")
    if c.sel:
        out.append(f"Main sessions cost {usd(main_cost)}; all sub-agents together {usd(sub_cost)}.")
    if modes and all(not m["own"]["n_S"] for m in modes) and any(m["shared"]["n_S"] for m in modes):
        out.append("All scored pipeline runs in this period came from shared coordinator sessions, so there is nothing to compare yet.")
    return out


def verdict_panel(c: Ctx) -> dict[str, Any]:
    """Score against the person's verdict, over every ticket that has both (not just this period). Shown once 20 tickets have a verdict and a score."""
    verdicts = gold.latest_verdicts()
    by_ticket: dict[str, list[float]] = defaultdict(list)
    for r in c.d.runs.values():
        if r["S"] is not None and r["key"] in verdicts and r["kind"] == "sub":
            by_ticket[r["key"]].append(r["S"])
    rows = [(k, mean(v), verdicts[k]["verdict"]) for k, v in by_ticket.items()]
    groups = {g: [s for _, s, v in rows if v == g] for g in gold.VERDICTS}
    agree = sum(1 for _, s, v in rows if (s >= 0.85) == (v == "accepted"))
    return {"n_verdicts": len(verdicts), "n": len(rows), "shown": len(rows) >= 20, "needed": 20,
            "mean_S": {g: mean(x) for g, x in groups.items()}, "count": {g: len(x) for g, x in groups.items()},
            "agree_share": (agree / len(rows)) if rows else None}


def role_detail(c: Ctx, role: str, first_only: bool = False, ticket: str = "") -> dict[str, Any]:
    all_runs = [r for r in c.sel if r["role"] == role]
    if not all_runs:
        return {"period": period_info(c), "role": role, "empty": True}
    runs = [r for r in all_runs if (not first_only or r["sc_round"] in (None, 1)) and (not ticket or r["key"] == ticket)]
    st = role_stats(c, role, runs)
    hist = history(c, runs)
    unit, bk = buckets(c.per)
    import bisect
    starts = [b["raw_lo"] for b in bk]
    per_b: list[list[float]] = [[] for _ in bk]
    for r in sorted(c.scored(runs), key=lambda r: r["start_e"]):
        per_b[max(0, bisect.bisect_right(starts, r["start_e"]) - 1)].append(r["S"])
    series = {"unit": unit, "buckets": [{"start": b["start"], "label": b["label"], "S": mean(x), "n_S": len(x)} for b, x in zip(bk, per_b)]}
    evs = events.role_events(role, c.per, hist, c.store, c.pricing)
    tickets = sorted({r["key"] for r in all_runs})
    return {"period": period_info(c), "role": role, "row": st, "history": hist, "series": series, "events": evs, "findings": role_findings(st, hist),
            "skipped_runs": [{"run_id": r["run_id"], "ticket": r["key"], "start": iso(r["start_e"]), "end": iso(r["end_e"]), "kind": r["skip_kind"], "label": SKIP_KINDS[r["skip_kind"]],
                             "reason": r["skip_reason"]} for r in sorted(runs, key=lambda r: -r["start_e"]) if r.get("skip_kind")],
            "weights": {k: WEIGHTS[k] for k in WEIGHTS}, "controls": {"first_only": first_only, "ticket": ticket, "tickets": tickets[:300], "n_all": len(all_runs), "n_shown": len(runs)}}


def role_findings(st, hist) -> list[str]:
    sc = hist
    n = len(sc)
    out = []
    used = [k for k in SCORE_CHECKS if any(h["criteria"].get(k) is not None for h in sc)]
    wsum = sum(WEIGHTS[k] for k in used) or 1.0
    half = n // 2
    if n >= 6:
        a1, a2 = sc[:half], sc[half:]
        s1, s2 = sum(1 for h in a1 if h["S"] is not None), sum(1 for h in a2 if h["S"] is not None)
        if min(s1, s2) < MIN_RUNS_FOR_CHANGE:
            out.append(f"Too few scored runs to call a change: {s1} before and {s2} after the middle of this period, at least {MIN_RUNS_FOR_CHANGE} are needed on each side.")
        else:
            share = lambda arr, k: mean([h["criteria"][k] for h in arr if h["criteria"].get(k) is not None] or [0])   # noqa: E731
            contrib = sorted(((k, WEIGHTS[k] * (share(a2, k) - share(a1, k)) / wsum) for k in used), key=lambda kv: -abs(kv[1]))
            contrib = [(k, d) for k, d in contrib if abs(d) >= 0.02]
            dS = mean(h["S"] for h in a2 if h["S"] is not None) - mean(h["S"] for h in a1 if h["S"] is not None)
            txt = f"First {half} scored runs average {pct(mean(h['S'] for h in a1 if h['S'] is not None))}; the last {n - half} average {pct(mean(h['S'] for h in a2 if h['S'] is not None))}"
            if abs(dS) >= 0.03 and contrib:
                txt += ". The change comes from: " + ", ".join(f"{k} {'+' if d > 0 else '−'}{round(abs(d) * 100)} points" for k, d in contrib) + "."
            else:
                txt += "."
            out.append(txt)
    versions = {h["scorer_version"] for h in sc}
    if len(versions) > 1:
        out.append("The runs here were scored by two versions of the scorer (see the scorer marker on the chart): a change at that line is the scorer, not the agent.")
    tickets_n = len({h["ticket"] for h in sc})
    rework = sum(1 for h in sc if h["rework"] or (h["round"] or 1) > 1)
    if tickets_n == 1 and n >= 3:
        out.append(f"All {n} scored runs are on one ticket ({sc[0]['ticket']}). The differences are between steps of one task, not learning; "
                   f"{'one of them is' if rework == 1 else f'{rework} of them are'} rework after a gate sent the work back.")
    never = [(k, WEIGHTS[k]) for k in used if st["pass"].get(k) and st["pass"][k][1] >= 3 and st["pass"][k][0] == 0 and (st["mean"].get(k) or 0) == 0]
    values = {round(h["S"] * 100) for h in sc if h["S"] is not None}
    if never:
        k, w = max(never, key=lambda kv: kv[1])
        out.append(f"\"{k}\" never passed, so S cannot exceed {pct((wsum - w) / wsum)} for this role"
                   + (f"; every run scored exactly {sorted(values)[0]}%" if len(values) == 1 else "") + ". The score shows the check, not the work.")
    elif len(values) <= 4 and n >= 8:
        lo, hi = round(0.1 / wsum * 100), round(0.3 / wsum * 100)
        out.append(f"Only {len(values)} distinct values: a check flipping moves S by {lo}–{hi} points. The jumps are that, not a swing in quality.")
    return out


# ---------------- sessions ----------------
def session_row(c: Ctx, r: dict[str, Any]) -> dict[str, Any]:
    ci = c.ci[r["run_id"]]
    calls = ci["calls"]
    ctx = (ci["t_in"] + ci["t_read"] + ci["t_write"]) / calls if calls else 0
    tt = ticket_time(c.d, [r], c.per.lo, c.per.hi)
    kids = sum(1 for x in c.sel if x["parent_run_id"] == r["run_id"])
    relay, total = r.get("relay_chars") or 0, r.get("total_chars") or 0
    hb = r.get("handback_chars") or 0
    return {"relay_chars": relay, "total_chars": total, "relay_share": (relay / total) if total else None, "handback_chars": hb, "handback_share": (hb / total) if total else None, "run_id": r["run_id"], "ticket": r["key"], "own_ticket": r["ticket"] or NOKEY, "moved": r["ticket_eff_via"] == "children" and r["ticket_eff"] != r["ticket"],
            "moved_note": {"children": r["eff_children"], "share_n": r["eff_share_n"]}, "start": iso(r["start_e"]), "length_s": c.clipped(r), "calls": calls, "cost": ci["cost"],
            "cost_per_call": (ci["cost"] / calls) if calls else 0.0, "context_per_call": ctx, "waiting_s": tt["waiting_s"], "parked_s": tt["parked_s"],
            "blocked_s": tt["blocked_s"], "sub_agents": kids, "agent_setting": r.get("agent_setting")}


def sessions(c: Ctx, sort: str = "cost", desc: bool = True, limit: int = 200) -> dict[str, Any]:
    rows = [session_row(c, r) for r in c.sel if r["kind"] == "main" and c.ci[r["run_id"]]["calls"]]
    key = sort if rows and sort in rows[0] else "cost"
    rows.sort(key=lambda r: (r[key] is None, r[key]), reverse=desc)
    big = [r for r in rows if r["context_per_call"] > config.CONTEXT_RED_TOKENS]
    small = [r for r in rows if r["context_per_call"] <= config.CONTEXT_RED_TOKENS]
    out = []
    if big:
        out.append(f"{len(big)} of {len(rows)} sessions re-read more than {config.CONTEXT_RED_TOKENS // 1000}k tokens per call; together they cost {usd(sum(r['cost'] for r in big))} of {usd(sum(r['cost'] for r in rows))}.")
    if big and small:
        out.append(f"In those sessions one call costs about {usd(median([r['cost_per_call'] for r in big]))}; in the shorter ones about {usd(median([r['cost_per_call'] for r in small]))}.")
    return {"period": period_info(c), "total": len(rows), "rows": rows[:max(1, min(limit, 500))], "context_red_tokens": config.CONTEXT_RED_TOKENS, "findings": out}


# ---------------- filters ----------------
def filters(c_all: Ctx, proj: str) -> dict[str, Any]:
    cnt = Counter(project_of(r["key"]) for r in c_all.sel)
    keys = {}
    for r in c_all.sel:
        if not proj or project_of(r["key"]) == proj:
            keys[r["key"]] = max(keys.get(r["key"], 0), r["start_e"])
    ordered = [k for k, _ in sorted(keys.items(), key=lambda kv: -kv[1])][:400]
    return {"projects": [{"name": k, "runs": v} for k, v in cnt.most_common()], "keys": ordered, "total_keys": len(keys)}
