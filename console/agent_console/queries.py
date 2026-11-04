"""Read-side queries for the API: overview, runs, tickets, roles, tokens, cost, scores, text on demand."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from . import config, parser
from .flags import total_tokens
from .pricing import Pricing
from .redact import Redactor
from .scope import rel_path
from .store import Store

SCORE_BAR = 0.85
TEXT_LIMIT = 4000


# ---------- usage aggregation ----------
SCOPES = ("project", "all")


def scope_sql(scope: str, alias: str = "r") -> str:
    """'project' = sessions whose records' cwd is under the configured project roots (config.tree_roots); 'all' = everything."""
    return f" AND {alias}.scope = 'project'" if scope != "all" else ""


def usage_rows(db, where: str = "", params: Iterable[Any] = (), scope: str = "project") -> list[dict[str, Any]]:
    """One row per API message (de-duplicated by message id + requestId over all files, see store.rebuild)."""
    sql = ("""SELECT u.run_id, u.ts, u.day, u.model, u.requested_model, u.input, u.output, u.cache_read,
                     u.cache_w5m, u.cache_w1h, r.role, r.ticket, r.kind, r.start_ts, r.project_dir
              FROM usage u JOIN runs r ON r.run_id = u.run_id WHERE 1=1"""
           + scope_sql(scope) + (f" AND {where}" if where else ""))  # nosec B608 - `where` is a constant from this module, values are bound
    return [dict(x) for x in db.execute(sql, tuple(params))]


def aggregate(rows: list[dict[str, Any]], key: Callable[[dict[str, Any]], Any], pricing: Pricing) -> dict[Any, dict[str, Any]]:
    out: dict[Any, dict[str, Any]] = {}
    for r in rows:
        a = out.setdefault(key(r), {"messages": 0, "input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
                                    "cost_usd": 0.0, "unknown_messages": 0, "tier_priced_messages": 0, "runs": set()})
        a["messages"] += 1
        a["input"] += r["input"] or 0
        a["output"] += r["output"] or 0
        a["cache_read"] += r["cache_read"] or 0
        a["cache_write"] += (r["cache_w5m"] or 0) + (r["cache_w1h"] or 0)
        a["runs"].add(r["run_id"])
        cost, match = pricing.message_cost(r["model"], {"input": r["input"] or 0, "output": r["output"] or 0,
                                                        "cache_read": r["cache_read"] or 0, "cache_w5m": r["cache_w5m"] or 0,
                                                        "cache_w1h": r["cache_w1h"] or 0})
        if cost is None:
            a["unknown_messages"] += 1
        else:
            a["cost_usd"] += cost
            if match.how == "tier":
                a["tier_priced_messages"] += 1
    for a in out.values():
        a["runs"] = len(a["runs"])
        a["total"] = a["input"] + a["output"] + a["cache_read"] + a["cache_write"]
        if pricing.empty or a["unknown_messages"] == a["messages"]:
            a["cost_usd"] = None
        a["cost_label"] = cost_label(a, pricing)
    return out


def price_sources(pricing: Pricing) -> list[str]:
    return sorted({str(v.get("source", "unknown")) for v in pricing.models.values()}) or []


def cost_label(a: dict[str, Any], pricing: Pricing) -> str:
    if a["cost_usd"] is None:
        return "cost unknown"
    src = price_sources(pricing)
    checked = [x for x in src if x != "estimate"]
    word = "estimate" if not checked else ("partly estimate" if "estimate" in src else ("list price" if len(checked) > 1 else checked[0]))
    extra = f" + {a['unknown_messages']} msgs unpriced" if a["unknown_messages"] else ""
    extra += " (price by tier)" if a["tier_priced_messages"] else ""
    return f"≈ ${a['cost_usd']:.2f} ({word}){extra}"


def _ser(d: dict[Any, dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"key": k, **v} for k, v in sorted(d.items(), key=lambda kv: -kv[1]["total"])]


# ---------- flags ----------
SCORE_FLAGS = ("deception", "secret_suspected", "secrets_file_edited")   # flags that only the score tool can compute; carried in scores.jsonl


def _score_flag_rows(db, scope: str) -> list[dict[str, Any]]:
    """Flags from scores.jsonl that the console's own rules do not compute (deception: always 'suspected')."""
    out = []
    for line in score_lines():
        for f in SCORE_FLAGS:
            if f in (line.get("flags") or []):
                r = db.execute("SELECT role, ticket, start_ts, scope FROM runs WHERE run_id=?", (line["task_id"],)).fetchone()
                if r is None or (scope != "all" and r["scope"] != "project"):
                    continue
                c = db.execute("SELECT checked_at FROM flag_checks WHERE run_id=? AND flag=?", (line["task_id"], f)).fetchone()
                out.append({"run_id": line["task_id"], "flag": f, "severity": "warn", "evidence": (line.get("flag_evidence") or {}).get(f, {}), "role": r["role"],
                            "ticket": r["ticket"], "start_ts": r["start_ts"], "checked_at": c["checked_at"] if c else None})
    return out


def flag_rows(db, only_open: bool = True, scope: str = "project") -> list[dict[str, Any]]:
    sql = """SELECT f.run_id, f.flag, f.severity, f.evidence, r.role, r.ticket, r.start_ts, c.checked_at
             FROM flags f JOIN runs r ON r.run_id=f.run_id
             LEFT JOIN flag_checks c ON c.run_id=f.run_id AND c.flag=f.flag WHERE 1=1""" + scope_sql(scope) + " ORDER BY r.start_ts DESC"  # nosec B608 - constants
    out = []
    rows = [dict(x) for x in db.execute(sql)] + _score_flag_rows(db, scope)
    rows.sort(key=lambda d: d["start_ts"] or "", reverse=True)
    for d in rows:
        if isinstance(d["evidence"], str):
            d["evidence"] = json.loads(d["evidence"])
        d["status"] = "checked" if d["checked_at"] else "open"
        if only_open and d["checked_at"]:
            continue
        out.append(d)
    return out


def check_flag(store: Store, run_id: str, flag: str) -> bool:
    with store.lock:
        n = store.db.execute("SELECT 1 FROM flags WHERE run_id=? AND flag=?", (run_id, flag)).fetchone()
        if not n:
            n = any(line["task_id"] == run_id and flag in (line.get("flags") or []) and flag in SCORE_FLAGS for line in score_lines())
        if not n:
            return False
        store.db.execute("INSERT OR REPLACE INTO flag_checks VALUES(?,?,?)",
                         (run_id, flag, datetime.now(timezone.utc).isoformat()))
        store.db.commit()
        store.flag_epoch = getattr(store, "flag_epoch", 0) + 1     # the ctq read-side cache keys on it
    return True


# ---------- overview ----------
STALE_AFTER_S = 120


def _score_freshness(pr: dict[str, Any], now: datetime | None) -> dict[str, Any]:
    last = pr.get("last_score_ok")
    age = round(((now or datetime.now(timezone.utc)) - datetime.fromisoformat(last)).total_seconds(), 1) if last else None
    return {"last_score_ok": last, "score_age_s": age, "score_written": pr.get("score_written"), "score_error": pr.get("score_error")}


def freshness(store: Store, now: datetime | None = None) -> dict[str, Any]:
    """State of the index for the header on every page: last successful rescan and whether it is stale (> 2 min)."""
    pr = store.progress
    last = pr.get("last_scan_ok")
    age = None
    if last:
        age = round(((now or datetime.now(timezone.utc)) - datetime.fromisoformat(last)).total_seconds(), 1)
    return {"state": pr.get("state"), "files_done": pr.get("files_done"), "files_total": pr.get("files_total"),
            "initial": bool(pr.get("initial")), "last_scan_ok": last, "age_s": age, "scans": pr.get("scans", 0),
            "error": pr.get("error"), "stale": last is None or (age is not None and age > STALE_AFTER_S),
            "stale_after_s": STALE_AFTER_S, "tz": config.tz_name(), **_score_freshness(pr, now)}


def _total(a: dict[str, Any] | None, pricing: Pricing) -> dict[str, Any]:
    if a is None:
        a = {"messages": 0, "input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "total": 0, "runs": 0,
             "cost_usd": None, "unknown_messages": 0, "tier_priced_messages": 0}
        a["cost_label"] = cost_label(a, pricing) if not pricing.empty else "cost unknown"
    return a


# ---------- runs ----------
def _run_dict(r) -> dict[str, Any]:
    d = dict(r)
    d["models"] = json.loads(d["models"] or "{}")
    d["requested_models"] = json.loads(d["requested_models"] or "{}")
    d["total_tokens"] = total_tokens(d)
    d["duration_s"] = _span(d["start_ts"], d["end_ts"])
    return d


def _span(a: str | None, b: str | None) -> float | None:
    try:
        x = datetime.fromisoformat(a.replace("Z", "+00:00"))
        y = datetime.fromisoformat(b.replace("Z", "+00:00"))
        return round((y - x).total_seconds(), 1)
    except (AttributeError, ValueError):
        return None


def run_detail(store: Store, pricing: Pricing, run_id: str) -> dict[str, Any] | None:
    db = store.reader()
    try:
        r = db.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if not r:
            return None
        d = _run_dict(r)
        d["log_deleted"] = db.execute("SELECT 1 FROM log_deleted WHERE run_id=?", (run_id,)).fetchone() is not None
        tools = Counter()
        edited: Counter = Counter()
        read: Counter = Counter()
        for t in db.execute("SELECT name, path, via_bash, is_error FROM tool_calls WHERE run_id=?", (run_id,)):
            tools[t["name"]] += 1
            if t["name"] in ("Edit", "Write", "Bash-write") and t["path"]:
                edited[(rel_path(t["path"]) or t["path"], t["name"], t["via_bash"])] += 1
            elif t["name"] == "Read" and t["path"]:
                read[rel_path(t["path"]) or t["path"]] += 1
        d["tool_counts"] = dict(tools)
        d["tool_errors"] = db.execute("SELECT count(*) FROM tool_calls WHERE run_id=? AND is_error=1", (run_id,)).fetchone()[0]
        d["files_edited"] = [{"path": p, "tool": n, "from_bash_command": bool(vb), "count": c} for (p, n, vb), c in sorted(edited.items())]
        d["files_read_count"] = len(read)
        d["tests"] = [{"class": t["cmd_class"], "start": t["ts"], "dur_s": t["dur_s"], "is_error": bool(t["is_error"]), "timed_out": bool(t["timed_out"])}
                      for t in db.execute("SELECT cmd_class, ts, dur_s, is_error, timed_out FROM tool_calls WHERE run_id=? AND dur_s IS NOT NULL AND cmd_class IN "
                                          "('pytest','ruff','mypy','frontend_test','make_test') ORDER BY ts", (run_id,))]
        d["errors"] = dict(Counter(e["category"] for e in db.execute("SELECT category FROM errors WHERE run_id=?", (run_id,))))
        d["flags"] = [f for f in flag_rows(db, only_open=False, scope="all") if f["run_id"] == run_id]
        d["children"] = [dict(x) for x in db.execute("SELECT run_id, role, start_ts, total_tokens FROM (SELECT run_id, role, start_ts, "
                                                    "input+output+cache_read+cache_w5m+cache_w1h AS total_tokens FROM runs WHERE parent_run_id=?) ORDER BY start_ts", (run_id,))]
        rows = usage_rows(db, "u.run_id=?", [run_id], scope="all")
        agg = aggregate(rows, lambda x: "r", pricing).get("r")
        d["cost"] = _total(agg, pricing)
        d["cost_by_model"] = _ser(aggregate(rows, lambda x: x["model"] or "?", pricing))
        f = db.execute("SELECT first_prompt_off, last_text_off FROM files WHERE run_id=?", (run_id,)).fetchone()
        parts = []
        if f and f["first_prompt_off"] is not None:
            parts.append("prompt")
        if f and f["last_text_off"] is not None:
            parts.append("final")
        if d["parent_run_id"]:
            parts.append("description")
        d["text_parts"] = parts
        d["scores"] = [s for s in score_lines() if s.get("task_id") == run_id]
        d["findings"] = run_findings(d)
        return d
    finally:
        db.close()



# ---------- scores ----------


def score_lines() -> list[dict[str, Any]]:
    """Latest revision per task id from ~/.agent-console/scores.jsonl, oldest first. Missing/empty file -> []."""
    p = config.scores_path()
    best: dict[str, dict[str, Any]] = {}
    try:
        for line in p.read_text(errors="replace").splitlines():
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if "task_id" in o and (o["task_id"] not in best or o.get("rev", 0) >= best[o["task_id"]].get("rev", 0)):
                best[o["task_id"]] = o
    except OSError:
        return []
    return sorted(best.values(), key=lambda o: o.get("start") or o.get("ts") or "")


# ---------- text on demand (redacted) ----------
_redactor: Redactor | None = None


def redactor() -> Redactor:
    global _redactor
    if _redactor is None:
        _redactor = Redactor(config.repo_root() / ".gitleaks.toml")
    return _redactor


def _text_blocks(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text = "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
        return (text + "\n" + parser.handback_text(content)).strip()   # a subagent's report comes through SubagentHandback
    return ""


def show_text(store: Store, run_id: str, part: str) -> dict[str, Any] | None:
    db = store.reader()
    try:
        f = db.execute("SELECT path, first_prompt_off, last_text_off FROM files WHERE run_id=?", (run_id,)).fetchone()
        if not f:
            return None
        if not Path(f["path"]).exists():
            return {"part": part, "text": "", "truncated": False, "redactions": 0,
                    "note": "log deleted: the log file of this run is gone (Claude Code's cleanup); its numbers stay in the index, its texts cannot be shown."}
        raw = ""
        if part == "prompt" and f["first_prompt_off"] is not None:
            rec = parser.read_record(Path(f["path"]), f["first_prompt_off"])
            raw = _text_blocks((rec or {}).get("message", {}).get("content"))
        elif part == "final" and f["last_text_off"] is not None:
            rec = parser.read_record(Path(f["path"]), f["last_text_off"])
            raw = _text_blocks((rec or {}).get("message", {}).get("content"))
        elif part == "description":
            m = db.execute("SELECT tool_use_id FROM sub_meta WHERE run_id=?", (run_id,)).fetchone()
            tc = db.execute("SELECT run_id, off FROM tool_calls WHERE id=?", (m["tool_use_id"],)).fetchone() if m else None
            pf = db.execute("SELECT path FROM files WHERE run_id=?", (tc["run_id"],)).fetchone() if tc else None
            if tc and pf:
                rec = parser.read_record(Path(pf["path"]), tc["off"]) or {}
                for b in (rec.get("message") or {}).get("content", []):
                    if isinstance(b, dict) and b.get("id") == m["tool_use_id"]:
                        raw = str((b.get("input") or {}).get("description") or "")
        elif part.startswith("tool:"):
            tid = part[5:]
            tc = db.execute("SELECT off FROM tool_calls WHERE run_id=? AND id=?", (run_id, tid)).fetchone()
            if tc:
                rec = parser.read_record(Path(f["path"]), tc["off"]) or {}
                for b in (rec.get("message") or {}).get("content", []):
                    if isinstance(b, dict) and b.get("id") == tid:
                        raw = json.dumps(b.get("input"), ensure_ascii=False)
        else:
            return None
        text, n = redactor().redact(raw)
        return {"part": part, "text": text[:TEXT_LIMIT], "truncated": len(text) > TEXT_LIMIT, "redactions": n,
                "note": "Redacted with the repo's .gitleaks.toml rules plus a built-in subset; not every secret format is covered."}
    finally:
        db.close()


# ---------- all-roles views ----------


def run_findings(d: dict[str, Any]) -> list[str]:
    """"What stands out" for one run: each line appears only when its condition holds."""
    from . import config
    from .ctq_pages import dur, pct
    out: list[str] = []
    if d.get("log_deleted"):
        out.append("Log deleted: the log file of this run is gone (Claude Code's cleanup). Its numbers come from the index; its texts cannot be shown.")
    wall = d.get("duration_s") or 0
    stalled = [f for f in d["flags"] if f["flag"] == "stalled"]
    if stalled:
        e = stalled[0]["evidence"]
        out.append(f"The run sat silent for more than {config.STALLED_AFTER_S // 60} minutes {e.get('count', 1)} time(s), {dur(e.get('total_s'))} in total (longest {dur(e.get('longest_s'))}). "
                   "That silence is not counted as model time.")
    if d.get("blocked_s"):
        out.append(f"A tool call sat for more than {config.BLOCKED_AFTER_S // 60} minutes ({dur(d['blocked_s'])} in total), most likely a permission prompt. It is shown as blocked, not as work.")
    if d.get("parked_s"):
        out.append(f"{dur(d['parked_s'])} were parked: the session was left open for more than {config.PARKED_AFTER_S // 3600} hours.")
    if d.get("test_timeouts"):
        out.append(f"{d['test_timeouts']} test call(s) lasted {config.TEST_TIMEOUT_S} s or more: a timeout or a permission prompt, not test time.")
    if wall and (d.get("unattributed_s") or 0) / wall > 0.3:
        out.append(f"{pct((d['unattributed_s'] or 0) / wall)} of the run's time is not explained by any category, for example a main session waiting for its sub-agents.")
    if d.get("ticket_eff_via") == "children" and d.get("ticket_eff") != d.get("ticket"):
        out.append(f"This main session is filed under {d['ticket_eff']} because {d.get('eff_share_n')} of {d.get('eff_children')} of its sub-agents worked on it (its own key: {d.get('ticket') or 'none'}).")
    sc = d["scores"][-1] if d["scores"] else None
    if sc and sc.get("S") is not None:
        failed = [k for k, v in (sc.get("criteria") or {}).items() if v.get("c") is not None and v["c"] < 1]
        if failed:
            out.append(f"S is {round(sc['S'] * 100)}% because these checks did not pass: {', '.join(failed)}. See the reasons in the score table below.")
    return out
