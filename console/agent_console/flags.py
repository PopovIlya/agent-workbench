"""Quality flags. Each rule is exact and documented in DESIGN.md section 3.

Main goal: mark runs a person should look at. Flags carry evidence (counts, paths, ids), never text.
Does: overthinking, out_of_scope_edit, spawn_failure, model_downgraded (info), returned, reject.
Does not: "bugs found after done" (no log field for it) or scores (the scorer in agent_scoring writes scores.jsonl).
"""

from __future__ import annotations

import statistics
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from .roles import Role, tier_of
from .scope import ScopeProvider, matches, rel_path

OVERTHINK_WINDOW = 100
OVERTHINK_MIN_RUNS = 20
OVERTHINK_FACTOR = 2.0
GATE_ROLES = ("reviewer", "requirements-reviewer", "verifier", "kit-reviewer", "kit-security", "kit-verifier")
# Paths no role is judged on (bookkeeping the hooks and tools write).
IGNORED_PREFIXES = ("worklogs/", ".claude/.worklog-session-state/", "docs/agents/work/")   # docs/agents/work: the roles' own reports, excluded from git
HOME_STATE = tuple(str(Path.home() / d) + "/" for d in (".claude", ".agent-console"))
# Prefixes used only to CLASSIFY paths found in logs; nothing is created there.
SCRATCH_PREFIXES = ("/tmp/", "/private/tmp/", "/var/folders/", "/private/var/folders/")  # nosec B108
SPAWN_FAILURE_CATEGORIES = {"aws_403", "credentials_expired", "network", "server_error", "other"}


@dataclass
class Flag:
    run_id: str
    flag: str
    severity: str  # "warn" | "info"
    evidence: dict[str, Any] = field(default_factory=dict)


def total_tokens(r: dict[str, Any]) -> int:
    return (r["input"] or 0) + (r["output"] or 0) + (r["cache_read"] or 0) + (r["cache_w5m"] or 0) + (r["cache_w1h"] or 0)


def overthinking(rows: dict[str, dict[str, Any]]) -> list[Flag]:
    out: list[Flag] = []
    by_role: dict[str, list[dict[str, Any]]] = {}
    for r in rows.values():
        if r["kind"] == "sub" and r["rounds"]:
            by_role.setdefault(r["role"], []).append(r)
    for role, runs in by_role.items():
        runs.sort(key=lambda r: r["start_ts"] or "")
        window = runs[-OVERTHINK_WINDOW:]
        if len(window) < OVERTHINK_MIN_RUNS:
            continue
        for r in window:
            others = [x for x in window if x["run_id"] != r["run_id"]]
            med_t = statistics.median(total_tokens(x) for x in others)
            med_r = statistics.median(x["rounds"] for x in others)
            ev: dict[str, Any] = {}
            if med_t and total_tokens(r) > OVERTHINK_FACTOR * med_t:
                ev.update(tokens=total_tokens(r), median_tokens=med_t, window=len(window))
            if med_r and r["rounds"] > OVERTHINK_FACTOR * med_r:
                ev.update(rounds=r["rounds"], median_rounds=med_r, window=len(window))
            if ev:
                out.append(Flag(r["run_id"], "overthinking", "warn", ev))
    return out


def out_of_scope(rows, edits, roles: dict[str, Role], scope: ScopeProvider) -> list[Flag]:
    out: list[Flag] = []
    for rid, r in rows.items():
        if r["kind"] != "sub" or rid not in edits:
            continue
        role = roles.get(r["role"])
        bad: list[dict[str, Any]] = []
        role_paths = role.output_paths if role and role.output_paths else None
        globs = scope.allowed_globs(r["ticket"]) if r["ticket"] else None
        for path, via_bash in edits[rid]:
            if path.startswith(SCRATCH_PREFIXES) or path.startswith(HOME_STATE):
                continue  # scratch files and Claude's own state are not "editing what it should not"
            rp = rel_path(path)
            if rp is None:
                bad.append({"path": path, "why": "outside repo", "via_bash": via_bash})
                continue
            if rp.startswith(IGNORED_PREFIXES):
                continue
            if role_paths is not None and not matches(rp, role_paths):
                bad.append({"path": rp, "why": "outside role paths", "via_bash": via_bash})
            elif globs is not None and not matches(rp, globs):
                bad.append({"path": rp, "why": "outside ticket modules", "via_bash": via_bash})
        if bad:
            out.append(Flag(rid, "out_of_scope_edit", "warn", {
                "count": len(bad), "items": bad[:10],
                "checks": {"role_paths": role_paths is not None, "ticket_scope": globs is not None}}))
    return out


def spawn_failures(rows, errors, last_err, last_msg) -> list[Flag]:
    out: list[Flag] = []
    for rid, r in rows.items():
        if r["kind"] != "sub" or rid not in errors:
            continue
        no_reply_after = (not r["rounds"]) or last_err.get(rid, "") > (last_msg.get(rid) or "")
        if no_reply_after:
            cats = sorted(set(errors[rid]) & SPAWN_FAILURE_CATEGORIES)
            out.append(Flag(rid, "spawn_failure", "warn", {"categories": cats, "error_count": len(errors[rid])}))
    return out


def model_downgraded(rows, expected) -> list[Flag]:
    import json
    out: list[Flag] = []
    for rid, r in rows.items():
        want = tier_of(expected.get(rid))
        if r["kind"] != "sub" or not want:
            continue
        served = {tier_of(m) for m in json.loads(r["models"] or "{}") if m != "?"} - {None}
        if served and want not in served or len(served) > 1:
            out.append(Flag(rid, "model_downgraded", "info", {"expected_tier": want, "served_tiers": sorted(served)}))
    return out


def returns_and_rejects(rows) -> list[Flag]:
    """A return = role X runs again for the same ticket after a gate role ran in between."""
    out: list[Flag] = []
    by_ticket: dict[str, list[dict[str, Any]]] = {}
    for r in rows.values():
        if r["kind"] == "sub" and r["ticket"]:
            by_ticket.setdefault(r["ticket"], []).append(r)
    for runs in by_ticket.values():
        runs.sort(key=lambda r: r["start_ts"] or "")
        last_idx: dict[str, int] = {}
        gates: list[int] = []
        rounds: dict[str, int] = {}
        for i, r in enumerate(runs):
            if r["role"] in GATE_ROLES:
                gates.append(i)
                continue
            j = last_idx.get(r["role"])
            if j is not None and any(j < g < i for g in gates):
                rounds[r["role"]] = rounds.get(r["role"], 0) + 1
                out.append(Flag(r["run_id"], "returned", "warn",
                                {"role": r["role"], "ticket": r["ticket"], "round": rounds[r["role"]], "derived": True}))
            last_idx[r["role"]] = i
    for r in rows.values():
        if r["kind"] == "sub" and r["role"] in GATE_ROLES and r["reject_count"]:
            out.append(Flag(r["run_id"], "reject", "warn", {"messages": r["reject_count"], "derived": True}))
    return out


def stalled(rows, stalls) -> list[Flag]:
    """A sub-agent run silent for more than STALLED_AFTER_S between two records (test calls, background waits and child runs excluded).
    Evidence is times and lengths only."""
    from .timing import iso
    out: list[Flag] = []
    for rid, gaps in (stalls or {}).items():
        r = rows.get(rid)
        if not r or r["kind"] != "sub":
            continue
        out.append(Flag(rid, "stalled", "warn", {"count": len(gaps), "longest_s": round(max(b - a for a, b, _ in gaps)), "total_s": round(sum(b - a for a, b, _ in gaps)),
                                                 "items": [{"start": iso(a), "dur_s": round(b - a), "ended_by": to} for a, b, to in sorted(gaps)[:5]]}))
    return out


def compute(rows, edits, errors, last_err, last_msg, roles, scope, expected, stalls=None) -> list[Flag]:
    return [*stalled(rows, stalls), *overthinking(rows), *out_of_scope(rows, edits, roles, scope), *spawn_failures(rows, errors, last_err, last_msg),
            *model_downgraded(rows, expected), *returns_and_rejects(rows)]
