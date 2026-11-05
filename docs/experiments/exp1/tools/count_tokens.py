#!/usr/bin/env python3
"""EXP1 step 3: tokens, cost, time per arm from the raw session logs. One script, both arms.
Usage: count_tokens.py  -> writes ~/exp1/tokens.json and ~/exp1/tokens.md
Pricing: the console's own Pricing class and pricing.yaml of the BASE commit (main checkout is frozen at the base profile commit).
"""
import json, glob, os, sys, datetime, collections
sys.path.insert(0, "<workbench>/console")
from agent_console.pricing import Pricing
from pathlib import Path

PR = Pricing.load(Path("<workbench>/console/pricing.yaml"))
ROOT = os.path.expanduser("~/.claude/projects")
ARMS = {"kit": "-<projects>-awb-kit", "r22": "-<projects>-awb-r22"}
KEYS = ("input", "output", "cache_w5m", "cache_w1h", "cache_read")

def ts(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()

def is_person(r):
    """A message that ends a wait: typed by the person, or sent by the ops session in the person's place."""
    if r.get("type") != "user" or r.get("isSidechain") or r.get("isCompactSummary"):
        return None
    o = r.get("origin") or {}
    if o.get("kind") == "human":
        return "human"
    if o.get("kind") == "peer" and str(o.get("from", "")).startswith("uds:"):
        return "ops"
    return None

def first_key(f):
    """Leading [KEY] of the first human prompt of a main session file, or None."""
    import re
    for l in open(f):
        try: r = json.loads(l)
        except Exception: continue
        if r.get("type") == "user" and not r.get("isSidechain"):
            c = (r.get("message") or {}).get("content")
            t = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text") if isinstance(c, list) else ""
            m = re.match(r"^\W{0,4}\[([A-Za-z0-9-]{2,40})\]", t)
            if m: return m.group(1)
            if t.strip(): return None
    return None

def files_of(mains):
    out = []
    for m in mains:
        out.append(m)
        out += sorted(glob.glob(m[:-6] + "/subagents/*.jsonl"))
    return out

def arm(name, mains=None):
    d = os.path.join(ROOT, ARMS.get(name, ""))
    if mains is None:
        mains = sorted(glob.glob(d + "/*.jsonl"))
    files = files_of(mains)
    seen = {}                       # message id -> (role, model, usage-max)
    role_of = {}
    per_file = {}
    waits = []                      # (gap_s, kind)
    stops = 0
    runs = collections.Counter(); firsts = []; lasts = []
    for f in files:
        sub = "/subagents/" in f
        role = "main"
        if sub:
            mp = f[:-6] + ".meta.json"
            try: role = json.load(open(mp)).get("agentType") or "unknown"
            except Exception: role = "unknown"
            runs[role] += 1
        t0 = t1 = None
        pending_stop = None
        for l in open(f):
            try: r = json.loads(l)
            except Exception: continue
            t = r.get("timestamp")
            if t:
                x = ts(t); t0 = x if t0 is None else min(t0, x); t1 = x if t1 is None else max(t1, x)
            if r.get("type") == "assistant":
                m = r.get("message") or {}
                u = m.get("usage")
                if u and m.get("id"):
                    cc = u.get("cache_creation") or {}
                    w5 = cc.get("ephemeral_5m_input_tokens", None)
                    w1 = cc.get("ephemeral_1h_input_tokens", None)
                    if w5 is None and w1 is None:
                        w5, w1 = u.get("cache_creation_input_tokens", 0) or 0, 0
                    cur = {"input": u.get("input_tokens", 0) or 0, "output": u.get("output_tokens", 0) or 0,
                           "cache_w5m": w5 or 0, "cache_w1h": w1 or 0, "cache_read": u.get("cache_read_input_tokens", 0) or 0}
                    old = seen.get(m["id"])
                    if old:
                        cur = {k: max(cur[k], old[2][k]) for k in KEYS}
                        role_keep = old[0]
                    else:
                        role_keep = role
                    seen[m["id"]] = (role_keep, m.get("model") or "unknown", cur)
                if not sub and m.get("stop_reason") == "end_turn" and t:
                    pending_stop = ts(t); stops += 1
            elif r.get("type") == "user" and not sub:
                k = is_person(r)
                if k and pending_stop is not None and t:
                    waits.append((ts(t) - pending_stop, k)); pending_stop = None
        if t0 is not None:
            per_file[f] = (role, t0, t1, sub)
            firsts.append(t0); lasts.append(t1)
    # tokens and cost
    by_model = collections.defaultdict(lambda: dict.fromkeys(KEYS, 0) | {"msgs": 0, "cost": 0.0, "unpriced": 0})
    by_role = collections.defaultdict(lambda: dict.fromkeys(KEYS, 0) | {"msgs": 0, "cost": 0.0})
    for mid, (role, model, tok) in seen.items():
        cost, _ = PR.message_cost(model, tok)
        for dct, key in ((by_model, model), (by_role, role)):
            e = dct[key]
            for k in KEYS: e[k] += tok[k]
            e["msgs"] += 1
            if cost is None:
                if "unpriced" in e: e["unpriced"] += 1
            else:
                e["cost"] += cost
    main_cost = by_role["main"]["cost"] if "main" in by_role else 0.0
    sub_cost = sum(v["cost"] for k, v in by_role.items() if k != "main")
    tot = {k: sum(v[k] for v in by_model.values()) for k in KEYS}
    waits_c = [(g, k) for g, k in waits if g >= 60]
    active = sum(t1 - t0 for (role, t0, t1, sub) in per_file.values() if sub)
    return {
        "files": len(files), "messages": len(seen),
        "role_runs": dict(runs), "role_runs_total": sum(runs.values()),
        "repeat_rounds": sum(n - 1 for n in runs.values() if n > 1),
        "tokens": tot,
        "by_model": {k: v for k, v in by_model.items()},
        "by_role": {k: v for k, v in sorted(by_role.items())},
        "cost_total": main_cost + sub_cost, "cost_main": main_cost, "cost_sub": sub_cost,
        "main_share_of_sub": (main_cost / sub_cost) if sub_cost else None,
        "wall_s": (max(lasts) - min(firsts)) if firsts else 0,
        "active_role_s": active,
        "wait_s_total": sum(g for g, _ in waits_c), "wait_gaps": len(waits_c),
        "wait_s_over_2h": sum(g for g, _ in waits_c if g > 7200),
        "wait_by_kind": {k: sum(g for g, kk in waits_c if kk == k) for k in ("human", "ops")},
        "interventions_seen": len([1 for _, k in waits]),
        "first": datetime.datetime.fromtimestamp(min(firsts)).isoformat() if firsts else None,
        "last": datetime.datetime.fromtimestamp(max(lasts)).isoformat() if lasts else None,
    }

out = {n: arm(n) for n in ARMS}
if "--all-keys" in sys.argv:
    groups = collections.defaultdict(list)
    for f in sorted(glob.glob(ROOT + "/-<projects>-agent-workbench/*.jsonl")):
        k = first_key(f)
        if k and k.startswith("EXP1-"): groups[k].append(f)
    for k, mains in sorted(groups.items()):
        out["old:" + k] = arm(k, mains)

json.dump(out, open(os.path.expanduser("~/exp1/tokens-all.json" if "--all-keys" in sys.argv else "~/exp1/tokens.json"), "w"), indent=1, sort_keys=True, default=str)
def fm(s): return "%d min" % round(s / 60)
lines = ["# Tokens, cost and time per arm (raw logs, one script: ~/exp1-private/count_tokens.py)", ""]
for n, a in out.items():
    lines += ["## " + n, "", "files %d, deduplicated messages %d, first %s, last %s" % (a["files"], a["messages"], a["first"], a["last"]),
              "role runs %d (repeat rounds %d): %s" % (a["role_runs_total"], a["repeat_rounds"], a["role_runs"]),
              "tokens: " + ", ".join("%s %d" % (k, v) for k, v in a["tokens"].items()),
              "cost USD: total %.2f, main %.2f, sub-agents %.2f, main share of sub %s" % (a["cost_total"], a["cost_main"], a["cost_sub"], "%.2f" % a["main_share_of_sub"] if a["main_share_of_sub"] is not None else "no sub-agents"),
              "wall %s, active role time %s, wait on a person %s (%d gaps, over 2 h: %s; by kind %s)" % (fm(a["wall_s"]), fm(a["active_role_s"]), fm(a["wait_s_total"]), a["wait_gaps"], fm(a["wait_s_over_2h"]), {k: fm(v) for k, v in a["wait_by_kind"].items()}),
              "", "| model | msgs | input | output | cache write 5m | cache write 1h | cache read | cost |", "|---|---|---|---|---|---|---|---|"]
    for m, v in a["by_model"].items():
        lines.append("| %s | %d | %d | %d | %d | %d | %d | %.2f%s |" % (m, v["msgs"], v["input"], v["output"], v["cache_w5m"], v["cache_w1h"], v["cache_read"], v["cost"], " (%d unpriced)" % v["unpriced"] if v["unpriced"] else ""))
    lines += ["", "| role | msgs | input | output | cache write | cache read | cost |", "|---|---|---|---|---|---|---|"]
    for m, v in a["by_role"].items():
        lines.append("| %s | %d | %d | %d | %d | %d | %.2f |" % (m, v["msgs"], v["input"], v["output"], v["cache_w5m"] + v["cache_w1h"], v["cache_read"], v["cost"]))
    lines.append("")
open(os.path.expanduser("~/exp1/tokens-all.md" if "--all-keys" in sys.argv else "~/exp1/tokens.md"), "w").write("\n".join(lines))
print("\n".join(lines))
