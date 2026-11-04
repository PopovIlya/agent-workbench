#!/usr/bin/env python3
"""Ground truth for the Agent console's token numbers. Standalone: stdlib only, shares NO code with the console.

Walks ALL <root>/**/*.jsonl (default ~/.claude/projects), keeps one record per API message (message id + requestId; the
record with the highest token total, earliest first), and sums input / output / cache-write / cache-read tokens per
LOCAL day (--tz, default UTC), per project directory and per model, for today and the last N local days.

Usage:  python3 ground_truth.py [--root DIR] [--days 7] [--tz Area/City] [--scope project|all] [--roots A:B] [--remote TEXT] [--json]
"""
import argparse
import collections
import datetime
import glob
import json
import os
import zoneinfo

FIELDS = ("input", "output", "cache_write", "cache_read")


def first_cwd_of(path):
    for line in open(path, errors="replace"):
        if '"cwd"' in line:
            try:
                return json.loads(line).get("cwd")
            except ValueError:
                pass
    return None


def load(root):
    """-> (files, records). One record per message id + requestId across all files. Each record carries the first `cwd`
    of the MAIN session file it belongs to (a subagent file counts with the session that spawned it)."""
    files = glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)
    best = {}
    main_cwd = {}
    for f in files:
        if os.sep + "subagents" + os.sep not in f:
            main_cwd[f] = first_cwd_of(f)
    for f in files:
        proj = os.path.relpath(f, root).split(os.sep)[0]
        if os.sep + "subagents" + os.sep in f:
            session_dir = os.path.dirname(os.path.dirname(f))  # <proj>/<session>/subagents/agent-x.jsonl -> <proj>/<session>
            first_cwd = main_cwd.get(session_dir + ".jsonl") or first_cwd_of(f)
        else:
            first_cwd = main_cwd[f]
        recs = []
        for line in open(f, errors="replace"):
            if '"type":"assistant"' not in line and '"type": "assistant"' not in line:
                continue
            try:
                o = json.loads(line)
            except ValueError:
                continue
            m = o.get("message") or {}
            u = m.get("usage")
            if o.get("type") != "assistant" or not isinstance(u, dict) or m.get("model") == "<synthetic>" or not o.get("timestamp"):
                continue
            cc = u.get("cache_creation") or {}
            cw = u.get("cache_creation_input_tokens") or (cc.get("ephemeral_5m_input_tokens", 0) + cc.get("ephemeral_1h_input_tokens", 0))
            rec = dict(ts=o["timestamp"], proj=proj, model=m.get("model"), input=u.get("input_tokens") or 0,
                       output=u.get("output_tokens") or 0, cache_write=cw or 0, cache_read=u.get("cache_read_input_tokens") or 0)
            recs.append(((m.get("id") or o.get("uuid"), o.get("requestId")), rec))
        for key, rec in recs:
            rec["cwd"] = first_cwd
            total = sum(rec[k] for k in FIELDS)
            if key not in best or total > best[key][0]:
                best[key] = (total, rec)
    return files, [r for _, r in best.values()]


def local_day(ts, tz):
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(tz).date().isoformat()


def in_project(cwd, roots, remote=""):
    """Under a root (the project trees, the worktrees folder), or inside a git checkout whose origin URL contains `remote` (if given)."""
    c = (cwd or "").rstrip("/")
    if any(c == r or c.startswith(r + "/") for r in roots):
        return True
    d = c
    while d and os.path.isdir(d):  # checkouts that still exist; deleted temp checkouts cannot be seen from outside
        if os.path.exists(os.path.join(d, ".git")):
            import subprocess
            url = subprocess.run(["git", "-C", d, "config", "--get", "remote.origin.url"], capture_output=True, text=True).stdout
            return bool(remote) and remote in url.lower()
        d = os.path.dirname(d) if os.path.dirname(d) != d else ""
    return False


def summarize(recs, days=7, tz_name="UTC", now=None, scope="all", project_roots=(), remote=""):
    tz = zoneinfo.ZoneInfo(tz_name)
    today = (now or datetime.datetime.now(datetime.timezone.utc)).astimezone(tz).date()
    want = {(today - datetime.timedelta(days=i)).isoformat() for i in range(days)}
    out = {k: collections.defaultdict(collections.Counter) for k in ("day", "project", "model")}
    for r in recs:
        if scope == "project" and not in_project(r["cwd"], project_roots, remote):
            continue
        d = local_day(r["ts"], tz)
        if d not in want:
            continue
        for kind, name in (("day", d), ("project", r["proj"]), ("model", r["model"])):
            for k in FIELDS:
                out[kind][name][k] += r[k]
            out[kind][name]["messages"] += 1
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--tz", default=os.environ.get("AGENT_CONSOLE_TZ", "UTC"))
    ap.add_argument("--scope", choices=("project", "all"), default="all")
    ap.add_argument("--roots", default=os.environ.get("AGENT_CONSOLE_TREE_ROOTS", os.path.expanduser("~")), help="colon-separated project roots")
    ap.add_argument("--remote", default=os.environ.get("AGENT_CONSOLE_PROJECT_REMOTE", ""), help="origin URL text that marks a project checkout")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    files, recs = load(a.root)
    s = summarize(recs, a.days, a.tz, scope=a.scope, project_roots=[r for r in a.roots.split(":") if r], remote=a.remote)
    if a.json:
        print(json.dumps({k: {n: dict(c) for n, c in v.items()} for k, v in s.items()}, indent=1, sort_keys=True))
        return
    print(f"files: {len(files)}  unique messages: {len(recs)}  tz: {a.tz}  days: {a.days}  scope: {a.scope}")
    for kind in ("day", "project", "model"):
        print(f"== per {kind}")
        for name, c in sorted(s[kind].items(), key=lambda kv: str(kv[0])):
            print(f"{str(name)[-62:]:62} in={c['input']:>10,} out={c['output']:>10,} cw={c['cache_write']:>12,} cr={c['cache_read']:>14,} msgs={c['messages']}")


if __name__ == "__main__":
    main()
