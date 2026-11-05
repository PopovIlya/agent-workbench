"""SQLite index of session logs: incremental ingest, derived runs, flags.

Main goal: remember what was read (byte offsets) so a restart only reads new lines.
Keeps metadata and counts only; text is re-read from the source file on request (see textview).
The DB lives in ~/.agent-console/, never in the repo, mode 0600.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from . import config, flags as flagmod, parser, tickets, timing
from .roles import Role, load_roles
from .scope import ScopeProvider, refresh_claims

SCHEMA_VERSION = 10  # bump when tables change: the DB is only a cache, it is rebuilt from the logs
SCHEMA = """
CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, kind TEXT, project_dir TEXT, session_id TEXT,
  agent_id TEXT, run_id TEXT, size INT, off INT, first_ts TEXT, last_ts TEXT, first_cwd TEXT, first_branch TEXT,
  first_prompt_off INT, last_text_off INT, prompt_ticket TEXT, meta_mtime REAL, prompt_lead TEXT, head_hash TEXT, tail_hash TEXT,
  prev_ts TEXT, model_s REAL DEFAULT 0, agent_setting TEXT, prompt_chars INT DEFAULT 0);
-- One row per (file, API message). The same message can appear in several files (a resumed session copies earlier
-- turns), so totals are NEVER summed from here: they come from `usage`, one row per msg_key = message id + requestId.
CREATE TABLE IF NOT EXISTS messages(run_id TEXT, msg_key TEXT, msg_id TEXT, request_id TEXT, ts TEXT, day TEXT, model TEXT,
  requested_model TEXT, input INT, output INT, cache_read INT, cache_w5m INT, cache_w1h INT, text_chars INT,
  says_reject INT, has_text INT, off INT, verdict TEXT, PRIMARY KEY(run_id, msg_key));
CREATE TABLE IF NOT EXISTS usage(msg_key TEXT PRIMARY KEY, run_id TEXT, ts TEXT, day TEXT, model TEXT, requested_model TEXT,
  input INT, output INT, cache_read INT, cache_w5m INT, cache_w1h INT, text_chars INT, says_reject INT, has_text INT, verdict TEXT);
CREATE INDEX IF NOT EXISTS usage_run ON usage(run_id); CREATE INDEX IF NOT EXISTS usage_day ON usage(day);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
-- origin remote of git checkouts seen while their directory still existed (temp checkouts are deleted later)
CREATE TABLE IF NOT EXISTS repo_remote(root TEXT PRIMARY KEY, remote TEXT, seen_at TEXT);
CREATE TABLE IF NOT EXISTS tool_calls(run_id TEXT, id TEXT, ts TEXT, name TEXT, path TEXT, via_bash INT,
  subagent_type TEXT, spawn_model TEXT, background INT, ticket TEXT, is_error INT DEFAULT 0, off INT, ticket_src TEXT,
  end_ts TEXT, dur_s REAL, cmd_class TEXT, timed_out INT, blocked INT DEFAULT 0, in_chars INT DEFAULT 0, out_chars INT,
  PRIMARY KEY(run_id, id));
CREATE INDEX IF NOT EXISTS tc_id ON tool_calls(id);
CREATE TABLE IF NOT EXISTS errors(run_id TEXT, ts TEXT, category TEXT, status INT, off INT,
  PRIMARY KEY(run_id, ts, category));
CREATE TABLE IF NOT EXISTS cost_state(run_id TEXT PRIMARY KEY, usd REAL);
CREATE TABLE IF NOT EXISTS sub_meta(run_id TEXT PRIMARY KEY, role TEXT, tool_use_id TEXT, parent_agent_id TEXT,
  model_hint TEXT, spawn_depth INT, is_fork INT, finished INT);
CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, session_id TEXT, agent_id TEXT, kind TEXT, role TEXT,
  project_dir TEXT, cwd TEXT, branch TEXT, start_ts TEXT, end_ts TEXT, ticket TEXT, ticket_src TEXT,
  background INT, parent_run_id TEXT, rounds INT, input INT, output INT, cache_read INT, cache_w5m INT,
  cache_w1h INT, tool_count INT, edit_count INT, error_count INT, reject_count INT, models TEXT,
  requested_models TEXT, cli_cost_usd REAL, scope TEXT, scope_reason TEXT, ticket_via TEXT,
  ticket_eff TEXT, ticket_eff_via TEXT, eff_children INT, eff_share_n INT,
  model_s REAL, tool_s REAL, test_s REAL, test_n INT, test_fail INT, test_timeouts INT, test_bg_n INT,
  human_wait_s REAL, parked_s REAL, blocked_s REAL, notif_wait_s REAL, unattributed_s REAL, agent_setting TEXT,
  stalled_s REAL, prompt_chars INT, relay_chars INT, total_chars INT, handback_chars INT, verdict TEXT);
CREATE INDEX IF NOT EXISTS runs_role ON runs(role); CREATE INDEX IF NOT EXISTS runs_ticket ON runs(ticket);
CREATE TABLE IF NOT EXISTS flags(run_id TEXT, flag TEXT, severity TEXT, evidence TEXT, PRIMARY KEY(run_id, flag));
CREATE TABLE IF NOT EXISTS flag_checks(run_id TEXT, flag TEXT, checked_at TEXT, PRIMARY KEY(run_id, flag));
CREATE TABLE IF NOT EXISTS worklog_req(start TEXT, end TEXT, ticket TEXT);
-- Raw idle gaps before a user record (the previous kept record -> the prompt). `origin` = the log's own origin.kind, NULL when unmarked.
CREATE TABLE IF NOT EXISTS gaps(run_id TEXT, start_ts TEXT, end_ts TEXT, origin TEXT, PRIMARY KEY(run_id, start_ts, end_ts));
-- Derived at every rebuild from gaps + tool_calls: kind = human | ask | notification | parked | blocked (see rebuild_waits).
CREATE TABLE IF NOT EXISTS waits(run_id TEXT, start_ts TEXT, end_ts TEXT, dur_s REAL, kind TEXT);
CREATE INDEX IF NOT EXISTS waits_run ON waits(run_id);
-- Long silent gaps between two records of a sub-agent run (>= IDLE_STORE_S). `to_kind` = what ended the gap: assistant | error | result | prompt.
-- tool_ids = the tool calls whose results ended it (ids only). Stalled runs are derived from this at every rebuild.
CREATE TABLE IF NOT EXISTS idle(run_id TEXT, start_ts TEXT, end_ts TEXT, to_kind TEXT, origin TEXT, tool_ids TEXT, PRIMARY KEY(run_id, start_ts, end_ts));
-- Runs whose log file is gone (Claude Code deletes old logs, see cleanupPeriodDays). Their raw rows stay in the index, also across a
-- schema rebuild; refreshed at every rebuild.
CREATE TABLE IF NOT EXISTS log_deleted(run_id TEXT PRIMARY KEY, path TEXT, noted_at TEXT);
"""
# Raw tables (filled from the log files, per run). A schema rebuild re-reads the logs; rows of runs whose log is gone cannot be
# re-read, so they are carried over (see Store._reset_derived). repo_remote is carried over whole: it remembers deleted checkouts.
RAW_TABLES = ("files", "messages", "tool_calls", "errors", "cost_state", "sub_meta", "gaps", "idle")
KEEP_WHOLE = ("repo_remote", "log_deleted")


class Store:
    def __init__(self, db_path: Path | None = None, repo: Path | None = None, scope: ScopeProvider | None = None):
        self.generation = 0
        self._dirty = True
        self.after_scan = None   # optional callable run after every finished rescan (the auto-scorer)
        self.db_path = db_path or (config.home() / "index.sqlite")
        self.repo = repo or config.repo_root()
        claims = config.claims_repo()
        self.scope = scope or (ScopeProvider(claims) if claims else ScopeProvider(self.repo, claim_loader=lambda _t: None))
        self.lock = threading.RLock()
        self.progress: dict[str, Any] = {"state": "idle", "files_done": 0, "files_total": 0, "last_ingest": None,
                                         "last_scan_ok": None, "scans": 0, "error": None}
        self._scan_thread: threading.Thread | None = None
        self.db = sqlite3.connect(self.db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)  # idempotent; also creates `meta` for a fresh file
        stored_tz = self.db.execute("SELECT v FROM meta WHERE k='tz'").fetchone()
        stored_keys = self.db.execute("SELECT v FROM meta WHERE k='key_patterns'").fetchone()
        key_sig = "\n".join(config.key_patterns())
        if (self.db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION or (stored_tz and stored_tz[0] != config.tz_name())
                or (stored_keys and stored_keys[0] != key_sig)):
            # new schema, another time zone (every stored `day` would be wrong), or other key patterns (the stored
            # spawn / prompt keys were derived with the old ones): rebuild every derived row from the logs
            self._reset_derived()
            self.db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        self.db.execute("INSERT OR REPLACE INTO meta VALUES('tz', ?)", (config.tz_name(),))
        self.db.execute("INSERT OR REPLACE INTO meta VALUES('key_patterns', ?)", (key_sig,))
        # Only recorded (never compared here): `compare` reads them to refuse an index built for another home or checkout.
        self.db.execute("INSERT OR REPLACE INTO meta VALUES('home', ?)", (str(self.db_path.parent.resolve()),))
        self.db.execute("INSERT OR REPLACE INTO meta VALUES('repo_root', ?)", (str(Path(self.repo).resolve()),))
        self.db.commit()
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:
            pass

    def _reset_derived(self) -> None:
        """New schema (or zone, or key patterns): drop everything derived and re-read the logs. The raw rows of runs whose log file is
        gone are kept (they cannot be re-read) and marked in `log_deleted`; columns the new schema dropped are left out, new ones stay empty."""
        keep = {"flag_checks"}  # a person's "checked" marks are not derived data
        tables = {t for (t,) in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        carried: dict[str, tuple[list[str], list[tuple]]] = {}
        gone: list[tuple[str, str]] = []
        if "files" in tables:
            gone = [(r[0], r[1]) for r in self.db.execute("SELECT run_id, path FROM files") if r[1] and not os.path.exists(r[1])]
        ids = [g[0] for g in gone]
        for t in RAW_TABLES + KEEP_WHOLE:
            if t not in tables:
                continue
            cols = [c[1] for c in self.db.execute(f'PRAGMA table_info("{t}")')]  # nosec B608 - fixed table names
            if t in KEEP_WHOLE:
                rows = self.db.execute(f'SELECT * FROM "{t}"').fetchall()  # nosec B608
            elif ids and "run_id" in cols:
                rows = []
                for i in range(0, len(ids), 500):
                    chunk = ids[i:i + 500]
                    rows += self.db.execute(f'SELECT * FROM "{t}" WHERE run_id IN ({",".join("?" * len(chunk))})', chunk).fetchall()  # nosec B608
            else:
                rows = []
            carried[t] = (cols, [tuple(r) for r in rows])
        for t in tables:
            if t not in keep:
                self.db.execute(f'DROP TABLE IF EXISTS "{t}"')  # nosec B608 - names come from sqlite_master
        self.db.executescript(SCHEMA)
        for t, (cols, rows) in carried.items():
            if not rows:
                continue
            new = [c[1] for c in self.db.execute(f'PRAGMA table_info("{t}")')]  # nosec B608
            shared = [c for c in cols if c in new]
            idx = [cols.index(c) for c in shared]
            self.db.executemany(f'INSERT OR IGNORE INTO "{t}" ({",".join(shared)}) VALUES ({",".join("?" * len(shared))})',  # nosec B608
                                [tuple(r[i] for i in idx) for r in rows])
        now = _norm_ts(None) or ""
        self.db.executemany("INSERT OR IGNORE INTO log_deleted VALUES(?,?,?)", [(rid, p, now) for rid, p in gone])

    def reader(self) -> sqlite3.Connection:
        """A fresh read connection per request (WAL lets it read while an ingest writes)."""
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    # ---------- discovery ----------
    def discover(self) -> list[parser.FileInfo]:
        """Every session file under the log root, whatever its directory is called. Which ones belong to the
        project scope is decided later from the `cwd` inside the records (see rebuild), not from directory names."""
        root = config.log_root()
        out: list[parser.FileInfo] = []
        if not root.is_dir():
            return out
        for pd in sorted(root.iterdir()):
            if not pd.is_dir():
                continue
            for f in list(pd.glob("*.jsonl")) + list(pd.glob("*/subagents/agent-*.jsonl")):
                fi = parser.classify(f)
                if fi:
                    out.append(fi)
        return out

    # ---------- ingest ----------
    def rescan(self, wait: bool = False, min_interval: float = 5.0) -> bool:
        """Start a background rescan unless one is running or the last one just finished. Used by every page
        load and by the 30 s loop; `wait=True` (tests, scripts) joins the thread. Returns True if one was started."""
        import time
        t = self._scan_thread
        if t and t.is_alive():
            if wait:
                t.join()
            return False
        last = self.progress.get("_finished_at") or 0
        if time.time() - last < min_interval:
            return False
        self._scan_thread = threading.Thread(target=self._scan_safely, daemon=True, name="rescan")
        self._scan_thread.start()
        if wait:
            self._scan_thread.join()
        return True

    def _scan_safely(self) -> None:
        import time
        try:
            self.ingest()
            self.progress["error"] = None
        except Exception as e:  # noqa: BLE001 - keep the loop alive; shown in the UI banner, no details leak
            self.progress.update(state="error", error=type(e).__name__)
        finally:
            self.progress["_finished_at"] = time.time()
        cb = self.after_scan
        if cb:
            try:
                cb()
            except Exception:  # noqa: BLE001 - a hook must never break the rescan loop
                pass

    def ingest(self) -> dict[str, int]:
        with self.lock:
            from datetime import datetime, timezone
            # scan marker (CON-010 v3): committed before any raw row of this scan, removed in the commit of the final rebuild
            self.db.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (f"scan:{os.getpid()}", datetime.now(timezone.utc).isoformat()))
            self.db.commit()
            if config.claims_repo():
                refresh_claims(config.claims_repo())
            files = self.discover()
            initial = self.db.execute("SELECT count(*) FROM runs").fetchone()[0] == 0
            self.progress.update(state="indexing", files_done=0, files_total=len(files), initial=initial)
            stats = Counter()
            for i, fi in enumerate(files):
                try:
                    self._ingest_file(fi, stats)
                except OSError:
                    stats["errors"] += 1
                if i % 20 == 0:
                    self.db.commit()
                if initial and i and i % 250 == 0:
                    self._load_worklogs()
                    self.rebuild()  # partial numbers appear early; the page says "incomplete" while indexing
                    self.db.commit()
                self.progress["files_done"] = i + 1
            self._load_worklogs()
            self.rebuild()
            _clear_scan_markers(self.db)
            self.db.commit()
            now = datetime.now(timezone.utc).isoformat()
            self.progress.update(state="idle", initial=False, last_ingest=now, last_scan_ok=now, scans=self.progress["scans"] + 1)
            return dict(stats)

    def _ingest_file(self, fi: parser.FileInfo, stats: Counter) -> None:
        st = fi.path.stat()
        row = self.db.execute("SELECT * FROM files WHERE path=?", (str(fi.path),)).fetchone()
        off = row["off"] if row else 0
        head = _head_hash(fi.path)
        if row and (st.st_size < off or row["head_hash"] != head or row["tail_hash"] != _tail_hash(fi.path, off)):
            # Truncated, compacted, rewritten or replaced (resume): read it again from the start. Messages already
            # indexed are KEPT (that spend happened) and counted once, because totals come from `usage`
            # (one row per message id + requestId). Rows derived from byte offsets are rebuilt.
            self.db.execute("DELETE FROM tool_calls WHERE run_id=?", (fi.run_id,))
            self.db.execute("DELETE FROM errors WHERE run_id=?", (fi.run_id,))
            self.db.execute("DELETE FROM gaps WHERE run_id=?", (fi.run_id,))
            self.db.execute("DELETE FROM idle WHERE run_id=?", (fi.run_id,))
            row, off = None, 0
            stats["rewritten"] += 1
        meta_mtime = self._ingest_meta(fi, row)
        if row and st.st_size == off:
            if meta_mtime != row["meta_mtime"]:
                self.db.execute("UPDATE files SET meta_mtime=? WHERE path=?", (meta_mtime, str(fi.path)))
            return
        pstate = {"prev_ts": row["prev_ts"] if row else None}
        events, new_off = parser.parse_file(fi.path, off, pstate)
        d = {"model_s": (row["model_s"] or 0.0) if row else 0.0, "agent_setting": row["agent_setting"] if row else None, "prompt_chars": (row["prompt_chars"] or 0) if row else 0,"first_ts": row["first_ts"] if row else None, "last_ts": row["last_ts"] if row else None,
             "first_cwd": row["first_cwd"] if row else None, "first_branch": row["first_branch"] if row else None,
             "first_prompt_off": row["first_prompt_off"] if row else None,
             "last_text_off": row["last_text_off"] if row else None,
             "prompt_ticket": row["prompt_ticket"] if row else None,
             "prompt_lead": row["prompt_lead"] if row else None}
        run_id = fi.run_id
        local_day = _local_day_fn()
        for e in events:
            if e.ts:
                d["first_ts"] = min(d["first_ts"], e.ts) if d["first_ts"] else e.ts
                d["last_ts"] = max(d["last_ts"], e.ts) if d["last_ts"] else e.ts
            k, x = e.kind, e.data
            if k == "record":
                d["first_cwd"] = d["first_cwd"] or x.get("cwd")
                d["first_branch"] = d["first_branch"] or x.get("branch")
            elif k == "message":
                key = f"{x['msg_id']}|{x['request_id'] or ''}"
                self.db.execute(
                    """INSERT INTO messages VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(run_id,msg_key) DO UPDATE SET
                         input=max(input,excluded.input), output=max(output,excluded.output),
                         cache_read=max(cache_read,excluded.cache_read), cache_w5m=max(cache_w5m,excluded.cache_w5m),
                         cache_w1h=max(cache_w1h,excluded.cache_w1h), text_chars=max(text_chars,excluded.text_chars),
                         says_reject=max(says_reject,excluded.says_reject), has_text=max(has_text,excluded.has_text),
                         off=excluded.off, verdict=coalesce(excluded.verdict,verdict)""",
                    (run_id, key, x["msg_id"], x["request_id"], e.ts, local_day(e.ts), x["model"], x["requested_model"],
                     x["input"], x["output"], x["cache_read"], x["cache_w5m"], x["cache_w1h"], x["text_chars"],
                     x["says_reject"], x["has_text"], e.off, x.get("verdict")))
                if x["has_text"]:
                    d["last_text_off"] = e.off
                d["model_s"] += x.get("gap_s") or 0.0
                stats["messages"] += 1
            elif k == "tool_use":
                self.db.execute(
                    "INSERT OR IGNORE INTO tool_calls(run_id,id,ts,name,path,via_bash,subagent_type,spawn_model,background,ticket,off,ticket_src,cmd_class,in_chars)"
                    " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (run_id, x["id"], e.ts, x["name"], x["path"], x["via_bash"], x["subagent_type"], x["spawn_model"],
                     x["background"], x["ticket"], e.off, x["ticket_src"], x.get("cmd_class"), x.get("in_chars", 0)))
            elif k == "tool_result":
                # end_ts = the record holding the result; dur_s / timed_out / blocked are derived in rebuild (finalize_tool_calls)
                self.db.execute("UPDATE tool_calls SET end_ts=COALESCE(end_ts, ?), is_error=MAX(is_error, ?), out_chars=COALESCE(out_chars, ?) WHERE run_id=? AND id=?",
                                (e.ts, x["is_error"], x.get("out_chars", 0), run_id, x["tool_use_id"]))
            elif k == "idle_gap":
                if fi.kind == "sub":
                    self.db.execute("INSERT OR IGNORE INTO idle VALUES(?,?,?,?,?,?)", (run_id, x["prev_ts"], e.ts, x["to"], x.get("origin"), json.dumps(x.get("tool_ids") or [])))
            elif k == "api_error":
                self.db.execute("INSERT OR IGNORE INTO errors VALUES(?,?,?,?,?)",
                                (run_id, e.ts or "", x["category"], x["status"] or 0, e.off))
            elif k == "user_prompt":
                if fi.kind == "main" and x.get("origin") in (None, "human"):
                    d["prompt_chars"] += x.get("chars") or 0     # the LENGTH of what a person typed, never the text
                if x.get("prev_ts") and e.ts and fi.kind == "main":   # a sub-agent has no human; its user records are tool plumbing
                    self.db.execute("INSERT OR IGNORE INTO gaps VALUES(?,?,?,?)", (run_id, x["prev_ts"], e.ts, x.get("origin")))
                if d["first_prompt_off"] is None:
                    d["first_prompt_off"] = e.off
                if x.get("ticket") and not d["prompt_ticket"]:
                    d["prompt_ticket"] = x["ticket"]
                if d["first_prompt_off"] == e.off and x.get("lead"):
                    d["prompt_lead"] = x["lead"]  # only the run's FIRST prompt counts as "leading"
            elif k == "agent_setting":
                d["agent_setting"] = d["agent_setting"] or x["agent"]
            elif k == "cost_state":
                if x.get("total_cost_usd") is not None:
                    self.db.execute("INSERT OR REPLACE INTO cost_state VALUES(?,?)", (run_id, x["total_cost_usd"]))
        self.db.execute(
            "INSERT OR REPLACE INTO files VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(fi.path), fi.kind, fi.project_dir, fi.session_id, fi.agent_id, run_id, st.st_size, new_off,
             d["first_ts"], d["last_ts"], d["first_cwd"], d["first_branch"], d["first_prompt_off"],
             d["last_text_off"], d["prompt_ticket"], meta_mtime, d["prompt_lead"], head, _tail_hash(fi.path, new_off),
             pstate.get("prev_ts"), d["model_s"], d["agent_setting"], d["prompt_chars"]))
        stats["files_read"] += 1
        self._dirty = True

    def _ingest_meta(self, fi: parser.FileInfo, row) -> float | None:
        if fi.kind != "sub":
            return None
        mp = fi.path.with_name(fi.path.stem + ".meta.json")
        try:
            mt = mp.stat().st_mtime
            if row and row["meta_mtime"] == mt:
                return mt
            m = json.loads(mp.read_text())
        except (OSError, ValueError):
            return None
        self.db.execute("INSERT OR REPLACE INTO sub_meta VALUES(?,?,?,?,?,?,?,?)",
                        (fi.run_id, m.get("agentType"), m.get("toolUseId"), m.get("parentAgentId"), m.get("model"),
                         m.get("spawnDepth"), 1 if m.get("isFork") else 0, 1 if m.get("finished") else 0))
        return mt

    def _forget(self, run_id: str, path: str) -> None:
        for t in ("messages", "tool_calls", "errors", "gaps", "idle"):
            self.db.execute(f"DELETE FROM {t} WHERE run_id=?", (run_id,))  # nosec B608 - t is from the fixed tuple above
        self.db.execute("DELETE FROM files WHERE path=?", (path,))

    def _load_worklogs(self) -> None:
        self.db.execute("DELETE FROM worklog_req")
        for d in config.worklog_dirs():
            for f in sorted(d.glob("*.jsonl")):
                try:
                    for line in f.read_text(errors="replace").splitlines():
                        try:
                            o = json.loads(line)
                        except ValueError:
                            continue
                        if o.get("type") == "request" and o.get("ticket") and o.get("start"):
                            self.db.execute("INSERT INTO worklog_req VALUES(?,?,?)",
                                            (_norm_ts(o["start"]), _norm_ts(o.get("end")), o["ticket"]))
                except OSError:
                    pass

    # ---------- derived ----------
    def rebuild(self) -> None:
        """Recompute runs and flags from the raw tables. Cheap (aggregates only)."""
        db = self.db
        roles = load_roles(self.repo)
        now = _norm_ts(None) or ""
        for rid, path in db.execute("SELECT run_id, path FROM files").fetchall():
            if path and not os.path.exists(path):
                db.execute("INSERT OR IGNORE INTO log_deleted VALUES(?,?,?)", (rid, path, now))
            else:
                db.execute("DELETE FROM log_deleted WHERE run_id=?", (rid,))
        # One row per API message (message id + requestId) over ALL files: a resumed session repeats earlier
        # turns, and a transcript can be copied into several subagent files. Highest token total wins, then earliest.
        db.execute("DELETE FROM usage")
        db.execute("""INSERT INTO usage SELECT msg_key, run_id, ts, day, model, requested_model, input, output, cache_read,
                             cache_w5m, cache_w1h, text_chars, says_reject, has_text, verdict
                      FROM (SELECT msg_key, run_id, ts, day, model, requested_model, input, output, cache_read, cache_w5m, cache_w1h, text_chars, says_reject, has_text, verdict, ROW_NUMBER() OVER (PARTITION BY msg_key ORDER BY
                              (input+output+cache_read+cache_w5m+cache_w1h) DESC, ts, run_id) AS rn FROM messages) WHERE rn = 1""")
        files = db.execute("SELECT * FROM files").fetchall()
        meta = {r["run_id"]: r for r in db.execute("SELECT * FROM sub_meta")}
        spawn_owner = {r["id"]: r["run_id"] for r in db.execute("SELECT id, run_id FROM tool_calls WHERE name IN ('Agent','Task')")}
        spawn_row = {r["id"]: r for r in db.execute("SELECT * FROM tool_calls WHERE name IN ('Agent','Task')")}
        agg = {r["run_id"]: r for r in db.execute(
            """SELECT run_id, count(*) n, sum(input) i, sum(output) o, sum(cache_read) cr, sum(cache_w5m) w5, sum(cache_w1h) w1,
                      sum(says_reject) rej, sum(verdict = 'FAIL') failn, min(ts) mints, max(ts) maxts FROM usage GROUP BY run_id""")}
        verdicts: dict[str, str] = {}      # last verdict word a run's replies started with (kit roles); later rows overwrite
        for r in db.execute("SELECT run_id, verdict FROM usage WHERE verdict IS NOT NULL ORDER BY ts, msg_key"):
            verdicts[r["run_id"]] = r["verdict"]
        tools = {r["run_id"]: r for r in db.execute(
            "SELECT run_id, count(*) n, sum(CASE WHEN name IN ('Edit','Write') THEN 1 ELSE 0 END) ed FROM tool_calls GROUP BY run_id")}
        errs = {r["run_id"]: r["n"] for r in db.execute("SELECT run_id, count(*) n FROM errors GROUP BY run_id")}
        models: dict[str, Counter] = defaultdict(Counter)
        reqm: dict[str, Counter] = defaultdict(Counter)
        for r in db.execute("SELECT run_id, model, requested_model, count(*) n FROM usage GROUP BY run_id, model, requested_model"):
            models[r["run_id"]][r["model"] or "?"] += r["n"]
            if r["requested_model"]:
                reqm[r["run_id"]][r["requested_model"]] += r["n"]
        path_tickets: dict[str, Counter] = defaultdict(Counter)
        change_tickets: dict[str, Counter] = defaultdict(Counter)
        for r in db.execute("SELECT run_id, path FROM tool_calls WHERE name IN ('Edit','Write') AND path IS NOT NULL"):
            cm = tickets.CHANGE_FILE_RE.search(r["path"])
            if cm:
                change_tickets[r["run_id"]][cm.group(1)] += 1
            for t in parser.TICKET_RE.findall(r["path"]):
                path_tickets[r["run_id"]][t] += 1
        git_tickets: dict[str, Counter] = defaultdict(Counter)
        for r in db.execute("SELECT run_id, ticket FROM tool_calls WHERE name='Bash' AND ticket_src='git' AND ticket IS NOT NULL"):
            git_tickets[r["run_id"]][r["ticket"]] += 1
        wts = tickets.worktree_branches(self.repo)
        evidence = key_evidence(db, files)   # dated key evidence per run (a sub-run of a long parent session takes the key in force WHEN it started)
        cli = {r["run_id"]: r["usd"] for r in db.execute("SELECT * FROM cost_state")}
        wl = db.execute("SELECT start, end, ticket FROM worklog_req ORDER BY start, ticket").fetchall()

        rows: dict[str, dict[str, Any]] = {}
        for f in files:
            rid = f["run_id"]
            a = agg.get(rid)
            if f["kind"] == "main":
                role, parent, bg = "main", None, 0
            else:
                m = meta.get(rid)
                spawn = spawn_row.get(m["tool_use_id"]) if m else None
                role = (m["role"] if m and m["role"] else None) or (spawn["subagent_type"] if spawn else None) or "general-purpose"
                parent = spawn_owner.get(m["tool_use_id"]) if m else None
                bg = (spawn["background"] if spawn else 0) or 0
            start = _norm_ts(f["first_ts"])
            spawn_t = spawn_row.get(meta[rid]["tool_use_id"]) if f["kind"] == "sub" and meta.get(rid) else None
            bm = parser.TICKET_RE.search(f["first_branch"] or "")
            ticket, src = tickets.resolve({
                "worklog": _worklog_ticket(wl, start),
                "spawn_lead": spawn_t["ticket"] if spawn_t and spawn_t["ticket_src"] == "lead" else None,
                "prompt_lead": f["prompt_lead"],
                "change_file": tickets.most_common(change_tickets.get(rid, [])),
                "git_command": tickets.most_common(git_tickets.get(rid, [])),
                "worktree_dir": tickets.dir_key(f["first_cwd"]),
                "worktree_branch": tickets.worktree_branch_key(f["first_cwd"], wts),
                "branch": bm.group(0) if bm else None,
                "path": tickets.most_common(path_tickets.get(rid, [])),
                "spawn_text": spawn_t["ticket"] if spawn_t and spawn_t["ticket_src"] == "text" else None,
                "prompt": f["prompt_ticket"],
            })
            rows[rid] = {
                "run_id": rid, "session_id": f["session_id"], "agent_id": f["agent_id"], "kind": f["kind"], "role": role,
                "project_dir": f["project_dir"], "cwd": f["first_cwd"], "branch": f["first_branch"], "start_ts": f["first_ts"],
                "end_ts": f["last_ts"], "ticket": ticket, "ticket_src": src, "background": bg, "parent_run_id": parent,
                "rounds": a["n"] if a else 0, "input": a["i"] if a else 0, "output": a["o"] if a else 0,
                "cache_read": a["cr"] if a else 0, "cache_w5m": a["w5"] if a else 0, "cache_w1h": a["w1"] if a else 0,
                "tool_count": tools[rid]["n"] if rid in tools else 0, "edit_count": tools[rid]["ed"] if rid in tools else 0,
                "error_count": errs.get(rid, 0), "reject_count": ((a["failn"] if role.startswith("kit-") else a["rej"]) or 0) if a else 0,   # kit roles reject with a first line FAIL, the 22 roles with the word REJECT
                "verdict": verdicts.get(rid),
                "models": json.dumps(dict(models.get(rid, {}))), "requested_models": json.dumps(dict(reqm.get(rid, {}))),
                "cli_cost_usd": cli.get(rid), "scope": None, "scope_reason": None, "ticket_via": None, "agent_setting": f["agent_setting"],
            }
        # A sub-run without a key of its own takes the parent's key IN FORCE WHEN IT STARTED (a parent session can run
        # for days across several tickets), else the parent's overall key.
        for r in rows.values():
            par = rows.get(r["parent_run_id"]) if r["ticket"] is None else None
            if par is not None:
                hit = tickets.latest_before(evidence.get(par["run_id"], []), _norm_ts(r["start_ts"]))
                if hit:
                    r["ticket"], r["ticket_src"], r["ticket_via"] = hit[0], "parent", hit[1]
                elif par["ticket"]:
                    r["ticket"], r["ticket_src"], r["ticket_via"] = par["ticket"], "parent", par["ticket_src"]
        self._assign_scopes(files, rows)
        timing.finalize_tool_calls(db)
        timing.rebuild_waits(db)
        self._stalls = timing.stalled_gaps(db)
        timing.split_runs(db, rows, self._stalls)
        tickets.effective_tickets(rows)
        db.execute("DELETE FROM runs")
        cols = list(next(iter(rows.values())).keys()) if rows else []
        if rows:
            db.executemany(f"INSERT INTO runs({','.join(cols)}) VALUES({','.join('?' * len(cols))})",  # nosec B608 - column names are this module's own dict keys
                           [tuple(r[c] for c in cols) for r in rows.values()])
        self._rebuild_flags(rows, roles, meta, spawn_row)
        if self._dirty:
            self.generation += 1   # read-side caches (ctq.py) key on this; a rescan that read nothing leaves it alone
            self._dirty = False

    # ---------- scope: which sessions are "project" sessions (config.tree_roots / worktree_roots / project_remote) ----------
    def _remote_of(self, cwd: str) -> str | None:
        """origin URL of the git checkout containing `cwd`. Read while the checkout exists and remembered, because
        temporary checkouts (/private/tmp/...) are deleted later."""
        p = Path(cwd)
        while True:
            if (p / ".git").exists():
                url = _git_origin(p)
                if url is not None:
                    self.db.execute("INSERT OR REPLACE INTO repo_remote VALUES(?,?,?)", (str(p), url, _norm_ts(None) or ""))
                return url
            if p.parent == p or not p.exists() and not p.parent.exists():
                break
            p = p.parent
        for root, remote in self.db.execute("SELECT root, remote FROM repo_remote ORDER BY length(root) DESC"):
            if cwd == root or cwd.startswith(root.rstrip("/") + "/"):
                return remote
        return None

    def classify_cwd(self, cwd: str | None) -> tuple[str, str]:
        hit = config.classify_path(cwd)
        if hit:
            return hit
        if cwd:
            url = self._remote_of(cwd)
            if url and config.project_remote() and config.project_remote() in url.lower():
                return "project", "repo remote"
        return "other", "other"

    def _assign_scopes(self, files, rows: dict[str, dict[str, Any]]) -> None:
        """Main sessions by their first cwd (tree / worktree / repo remote). A subagent counts with the session that
        spawned it ("parent session"), else by its own cwd. A file with no cwd at all falls back to the dir-name prefix."""
        by_run = {f["run_id"]: f for f in files}
        for rid, r in rows.items():
            if r["kind"] != "main":
                continue
            f = by_run[rid]
            if f["first_cwd"]:
                r["scope"], r["scope_reason"] = self.classify_cwd(f["first_cwd"])
            elif f["project_dir"].startswith(config.project_prefix()):
                r["scope"], r["scope_reason"] = "project", "tree"
            else:
                r["scope"], r["scope_reason"] = "other", "other"
        for rid, r in rows.items():
            if r["kind"] == "main":
                continue
            f = by_run[rid]
            parent = rows.get(f["session_id"])
            own = self.classify_cwd(f["first_cwd"]) if f["first_cwd"] else ("other", "other")
            if parent is not None and parent["scope"] == "project":
                r["scope"], r["scope_reason"] = "project", "parent session"
            elif own[0] == "project":
                r["scope"], r["scope_reason"] = own
            else:
                r["scope"], r["scope_reason"] = "other", "other"

    def _rebuild_flags(self, rows, roles: dict[str, Role], meta, spawn_row) -> None:
        db = self.db
        edits: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for r in db.execute("SELECT run_id, path, via_bash FROM tool_calls WHERE name IN ('Edit','Write','Bash-write') AND path IS NOT NULL"):
            edits[r["run_id"]].append((r["path"], r["via_bash"]))
        errors: dict[str, list[str]] = defaultdict(list)
        last_err: dict[str, str] = {}
        for r in db.execute("SELECT run_id, category, ts FROM errors"):
            errors[r["run_id"]].append(r["category"])
            last_err[r["run_id"]] = max(last_err.get(r["run_id"], ""), r["ts"])
        last_msg = {r["run_id"]: r["m"] for r in db.execute("SELECT run_id, max(ts) m FROM messages GROUP BY run_id")}
        expected = {}
        for rid, r in rows.items():
            m = meta.get(rid)
            spawn = spawn_row.get(m["tool_use_id"]) if m else None
            expected[rid] = (roles[r["role"]].model_tier if r["role"] in roles else None) \
                or (spawn["spawn_model"] if spawn else None) or (m["model_hint"] if m else None)
        found = flagmod.compute(rows, edits, errors, last_err, last_msg, roles, self.scope, expected, getattr(self, "_stalls", None))
        db.execute("DELETE FROM flags")
        db.executemany("INSERT INTO flags VALUES(?,?,?,?)", [(f.run_id, f.flag, f.severity, json.dumps(f.evidence)) for f in found])


def key_evidence(db: sqlite3.Connection, files) -> dict[str, list[tuple[str, str, str]]]:
    """Dated key evidence per run: {run_id: [(ts, key, source)]} from Edit/Write paths (change file or path key), git commands that name a
    key, and the run's first prompt (`files` rows with run_id, first_ts, prompt_lead, prompt_ticket). Used by `Store.rebuild` (the key a sub-run
    takes from its parent) and by the comparison (the key of a spawn that has no run file). `db` needs a Row factory."""
    evidence: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for r in db.execute("SELECT run_id, ts, path, ticket, name, ticket_src FROM tool_calls "
                        "WHERE (name IN ('Edit','Write') AND path IS NOT NULL) OR (name='Bash' AND ticket_src='git' AND ticket IS NOT NULL)"):
        ts = _norm_ts(r["ts"]) or ""
        if r["name"] == "Bash":
            evidence[r["run_id"]].append((ts, r["ticket"], "git_command"))
            continue
        cm = tickets.CHANGE_FILE_RE.search(r["path"])
        if cm:
            evidence[r["run_id"]].append((ts, cm.group(1), "change_file"))
        else:
            for t in parser.TICKET_RE.findall(r["path"]):
                evidence[r["run_id"]].append((ts, t, "path"))
    for f in files:
        if f["prompt_lead"] or f["prompt_ticket"]:
            evidence[f["run_id"]].append((_norm_ts(f["first_ts"]) or "", f["prompt_lead"] or f["prompt_ticket"], "prompt"))
    return evidence


INDEX_VALUES = ("schema version", "time zone", "key patterns", "console home", "checkout")


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, OverflowError, ValueError):
        return False
    return True


SCAN_MARKER_MAX_AGE = 3600      # seconds: a marker older than this counts as dead even when its pid is alive (CON-010, Q-058)


def _marker_stale(value: object) -> bool:
    """True when the stored start time is older than the age bound (an unreadable time is not stale: the pid decides)."""
    from datetime import datetime, timezone
    try:
        t = datetime.fromisoformat(str(value))
    except ValueError:
        return False
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).total_seconds() > SCAN_MARKER_MAX_AGE


def _clear_scan_markers(db: sqlite3.Connection) -> None:
    """Delete this process's scan marker and the markers of dead processes (no commit: the caller's transaction)."""
    own = f"scan:{os.getpid()}"
    for k, v in db.execute("SELECT k, v FROM meta WHERE k LIKE 'scan:%'").fetchall():
        try:
            pid = int(k[5:])
        except ValueError:
            pid = -1
        if k == own or pid <= 0 or not _pid_alive(pid) or _marker_stale(v):
            db.execute("DELETE FROM meta WHERE k=?", (k,))


def index_check(db_path: Path, repo: Path) -> tuple[list[str], list[str]]:
    """Read-only: compare the index file with the values this process would build it with. Returns (differ, missing), names in the fixed
    order INDEX_VALUES. No file -> ([], []). Opens with `?mode=ro`, runs no PRAGMA that writes and never creates `Store`, so nothing is
    reset or written. A file that cannot be read raises sqlite3.Error."""
    if not db_path.exists():
        return [], []
    resolved = db_path.resolve()
    wal = resolved.with_name(resolved.name + "-wal")
    # no -wal file: open immutable, so SQLite creates no -wal / -shm even for a WAL database (nothing written on a refusal)
    shm = resolved.with_name(resolved.name + "-shm")
    if wal.exists() and not shm.exists():
        # a -wal without a -shm: reading it in place would create the -shm; read a copy in a temporary directory instead (NEW-3)
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            shutil.copy(resolved, Path(td) / "index.sqlite")
            shutil.copy(wal, Path(td) / "index.sqlite-wal")
            return _index_values(Path(td) / "index.sqlite", "?mode=ro", db_path, repo)
    return _index_values(resolved, "?mode=ro" if wal.exists() else "?mode=ro&immutable=1", db_path, repo)


def _index_values(file: Path, query: str, db_path: Path, repo: Path) -> tuple[list[str], list[str]]:
    con = sqlite3.connect(file.as_uri() + query, uri=True)
    try:
        version = con.execute("PRAGMA user_version").fetchone()[0]
        has_meta = con.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='meta'").fetchone()[0]
        stored = dict(con.execute("SELECT k, v FROM meta").fetchall()) if has_meta else {}
    finally:
        con.close()
    want = {"time zone": ("tz", config.tz_name()), "key patterns": ("key_patterns", "\n".join(config.key_patterns())),
            "console home": ("home", str(db_path.parent.resolve())), "checkout": ("repo_root", str(Path(repo).resolve()))}
    differ, missing = [], []
    if version != SCHEMA_VERSION:
        differ.append("schema version")
    for name, (k, v) in want.items():
        if stored.get(k) is None:
            missing.append(name)
        elif stored[k] != v:
            differ.append(name)
    order = {n: i for i, n in enumerate(INDEX_VALUES)}
    return sorted(differ, key=order.get), sorted(missing, key=order.get)


def index_mismatch(db_path: Path, repo: Path) -> list[str]:
    """The merged differing and missing index values, as one list in INDEX_VALUES order.

    Kept without a product caller on purpose: it is the merged-list form of the designed
    guard interface (CON-011), for callers that need a single list. The CLI uses
    index_check instead, because its refusal message splits differing from missing.
    """
    differ, missing = index_check(db_path, repo)
    order = {n: i for i, n in enumerate(INDEX_VALUES)}
    return sorted(differ + missing, key=order.get)


def _norm_ts(ts: str | None) -> str | None:
    """Normalise to 'YYYY-MM-DDTHH:MM:SS' UTC (worklogs carry offsets; logs use Z)."""
    if not ts:
        return None
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return ts
    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _worklog_ticket(wl, start: str | None) -> str | None:
    if not start:
        return None
    s = _norm_ts(start)
    best = None
    for w in wl:
        if w["start"] <= s and w["end"] and w["end"] >= s:  # open requests (no end) are not matched
            best = w["ticket"]  # latest start wins (ordered by start)
    return best


def _tail_hash(path: Path, off: int) -> str:
    """Hash of the (up to) 256 bytes just before the stored offset. If a file was rewritten with the same first line but different
    content after it, those bytes differ and the file is read again from the start."""
    import hashlib
    if off <= 0:
        return ""
    try:
        with open(path, "rb") as fh:
            fh.seek(max(0, off - 256))
            return hashlib.sha1(fh.read(min(256, off)), usedforsecurity=False).hexdigest()
    except OSError:
        return ""


def _head_hash(path: Path) -> str:
    """Hash of the first line (at most 4 KB): a changed first line means the file was rewritten or replaced."""
    import hashlib
    try:
        with open(path, "rb") as fh:
            return hashlib.sha1(fh.readline(4096), usedforsecurity=False).hexdigest()
    except OSError:
        return ""


def _local_day_fn():
    """ts (ISO, usually ...Z) -> local calendar day in the configured zone (config.tz_name(), DST-aware)."""
    from datetime import datetime
    tz = config.tz()

    def local_day(ts: str | None) -> str | None:
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(tz).date().isoformat()
        except ValueError:
            return ts[:10]
    return local_day



def _git_origin(root: Path) -> str | None:
    """The `origin` URL from a checkout's git config, read as a file (no git process). Works for linked worktrees
    (a `.git` file pointing at the git dir, whose `commondir` holds the shared config)."""
    import re
    g = root / ".git"
    try:
        if g.is_file():
            gitdir = Path(g.read_text().split("gitdir:", 1)[1].strip())
            if not gitdir.is_absolute():
                gitdir = (root / gitdir).resolve()
            common = gitdir / "commondir"
            cfg = ((gitdir / common.read_text().strip()).resolve() if common.exists() else gitdir) / "config"
        else:
            cfg = g / "config"
        text = cfg.read_text(errors="replace")
    except (OSError, IndexError):
        return None
    m = re.search(r'\[remote "origin"\][^\[]*?\burl\s*=\s*(\S+)', text)
    return m.group(1) if m else ""
