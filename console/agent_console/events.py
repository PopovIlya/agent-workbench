"""Events drawn on a role's score history as dotted vertical lines.

Main goal: a change in S can be read against what changed around it: a new ticket, a new version of the role file, a skill it uses, the shared
rules, an accepted lesson, the served model, or the SCORER itself (so a change in how S is computed is never mistaken for a change in the agent).
To add a kind of event: write one function `(ctx) -> list[event]` and add it to SOURCES. Nothing else changes.
event = {"ts": ISO, "kind": str, "label": short text for the line, "detail": text for the tooltip}
"""

from __future__ import annotations

import subprocess  # nosec B404 - read-only `git log`, fixed argv, no shell
import time
from datetime import datetime, timedelta
from typing import Any, Callable

from . import config, gold


def _git_log(repo: Any, ref: str, since: str, paths: list[str]) -> list[tuple[str, str, str]]:
    """(committer date ISO, short sha, subject) of commits on `ref` that touched `paths`, newest first. [] when git says no."""
    try:
        out = subprocess.run(["git", "-C", str(repo), "log", ref, f"--since={since}", "--format=%cI%x09%h%x09%s", "--", *paths],  # nosec B603 B607
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    rows = []
    for line in out.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            rows.append((parts[0], parts[1], parts[2]))
    return rows


class EventCtx:
    def __init__(self, role: str, per: Any, hist: list[dict[str, Any]]):
        self.role, self.per, self.hist = role, per, hist
        self.repo = config.repo_root()
        self.ref = config.roles_ref() or "HEAD"
        self.since = (datetime.fromtimestamp(per.lo, config.tz()) - timedelta(days=1)).date().isoformat()


_cache: dict[tuple, tuple[float, list[tuple[str, str, str]]]] = {}


def _commits(ctx: EventCtx, paths: list[str]) -> list[tuple[str, str, str]]:
    key = (str(ctx.repo), ctx.ref, ctx.since, tuple(paths))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < 60:
        return hit[1]
    rows = _git_log(ctx.repo, ctx.ref, ctx.since, paths)
    _cache[key] = (time.time(), rows)
    return rows


def _in_period(ctx: EventCtx, ts: str) -> bool:
    try:
        t = datetime.fromisoformat(ts).timestamp()
    except ValueError:
        return False
    return ctx.per.lo <= t <= ctx.per.hi


def _git_source(kind: str, label: str, paths: Callable[[EventCtx], list[str]]):
    def src(ctx: EventCtx) -> list[dict[str, Any]]:
        return [{"ts": ts, "kind": kind, "label": label, "detail": f"{sha} {subject[:90]}"} for ts, sha, subject in _commits(ctx, paths(ctx)) if _in_period(ctx, ts)]
    return src


def new_ticket(ctx: EventCtx) -> list[dict[str, Any]]:
    out, prev = [], None
    for h in ctx.hist:
        if prev is not None and h["ticket"] != prev:
            out.append({"ts": h["start"], "kind": "ticket", "label": h["ticket"], "detail": f"New ticket: {h['ticket']}"})
        prev = h["ticket"]
    return out


def model_change(ctx: EventCtx) -> list[dict[str, Any]]:
    out, prev = [], None
    for h in ctx.hist:
        m = max(h["models"].items(), key=lambda kv: kv[1])[0] if h.get("models") else None
        if m and prev and m != prev:
            out.append({"ts": h["start"], "kind": "model", "label": "model", "detail": f"Served model changed: {prev} → {m}"})
        prev = m or prev
    return out


def scorer_version_change(ctx: EventCtx) -> list[dict[str, Any]]:
    """Where the runs on the chart switch from one version of the scorer to another: a change in how S is computed must never look like a change in the agent."""
    out, prev = [], None
    for h in ctx.hist:
        v = h.get("scorer_version")
        if prev is not None and v is not None and v != prev:
            out.append({"ts": h["start"], "kind": "scorer version", "label": f"scorer v{v}", "detail": f"S computed by scorer v{v} from here (v{prev} before): not a change in the agent"})
        prev = v if v is not None else prev
    return out


def role_file_change(ctx: EventCtx) -> list[dict[str, Any]]:
    """The role file differs from the previous run's (the git blob recorded on each score line)."""
    out, prev = [], None
    for h in ctx.hist:
        sha = h.get("role_file_sha")
        if prev and sha and sha != prev:
            out.append({"ts": h["start"], "kind": "role file", "label": "role file", "detail": f"role file {prev} → {sha}"})
        prev = sha or prev
    return out


def bench_results(ctx: EventCtx) -> list[dict[str, Any]]:
    """Benchmark runs of this role (agent-bench, ~/.agent-console/bench.jsonl) with pass^k in the tooltip."""
    out = []
    for o in gold.read("bench.jsonl"):
        if o.get("role") == ctx.role and o.get("ts") and not o.get("dry_run"):
            t = datetime.fromisoformat(o["ts"].replace("Z", "+00:00")).timestamp() if o.get("ts") else 0
            if ctx.per.lo <= t <= ctx.per.hi:
                out.append({"ts": o["ts"], "kind": "benchmark", "label": f"bench {o.get('pass_pow_k', 0):.0%}",
                            "detail": f"benchmark: {o.get('tasks', 0)} tasks, k={o.get('k')}, pass@k {o.get('pass_at_k', 0):.0%}, pass^k {o.get('pass_pow_k', 0):.0%}"})
    return out


SOURCES: list[Callable[[EventCtx], list[dict[str, Any]]]] = [
    new_ticket,
    model_change,
    scorer_version_change,
    role_file_change,
    bench_results,
    _git_source("role file", "role file", lambda c: [f"roles-22/agents/{c.role}.md", f"kit/agents/{c.role}.md"]),
    _git_source("shared rules", "shared rules", lambda c: ["roles-22/SHARED-RULES.md", "kit/PLAYBOOK.md", "templates/PROJECT.md"]),
    _git_source("scorer", "scorer", lambda c: ["console/agent_scoring", "roles-22/criteria", "kit/criteria"]),
]


def role_events(role: str, per: Any, hist: list[dict[str, Any]], store: Any = None, pricing: Any = None) -> list[dict[str, Any]]:
    ctx = EventCtx(role, per, hist)
    out: list[dict[str, Any]] = []
    for src in SOURCES:
        try:
            out += src(ctx)
        except Exception:   # noqa: BLE001 - one broken source must not hide the others
            continue
    return sorted(out, key=lambda e: e["ts"])
