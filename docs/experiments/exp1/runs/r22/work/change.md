**EXP1: Ticket comparison report in the console**

Business need: to compare two tickets (or two runs of one ticket) side by side by cost, time and outcome, without adding numbers up by hand.

What it does:
1. A page `/compare?a=<KEY>&b=<KEY>` and a CLI `python -m agent_console compare <KEY> <KEY> [--json]`.
2. For each ticket, including its main sessions:
   - role runs: total, failed, and how many were repeat rounds;
   - tokens split into input, output, cache write and cache read, per model;
   - cost per model and in total, from `pricing.yaml`;
   - wall time from the first to the last event; active role time; time spent waiting on a person (gaps between a stop and the next human message);
   - the main session's cost as a share of the sub-agents' cost.
3. A third column with the difference (b minus a, and b divided by a).
4. An unknown key gives a clear error on the page and exit code 2 in the CLI; a ticket with no main session shows "no main session" in that row, not zero.
5. The JSON output is stable (sorted keys, fixed field names) so a script can read it.

Out of scope: charts, more than two tickets, editing data.

Decisions made in advance (so neither arm has to ask):
- Wait time = the gap between an assistant message that ends with a stop for the person and the next user message. Gaps under 60 s count as zero.
- Cost uses the prices in `pricing.yaml` as they are on the base commit.
- A session belongs to a ticket by the console's existing key rules.
- Numbers on the page are rounded: tokens to thousands, dollars to cents, time to minutes. JSON keeps raw values.
- No new dependencies.

---

## System analysis (DoR part 2, system analyst, 2026-11-05; return round 1 applied the same day)

Main goal: tell the builder which data, entry points, existing code and files this ticket touches, with the rule ids per file.
Ticket: EXP1-R22C (scope given by the person; no tracker gate). Base: 0891a04 on branch exp1/r22.
Gates: `impact_map`, `claims`, `timing_check`: not declared in PROJECT.md, skipped (modules listed by file, no timing section).

### Rule ids
- Added (status new, all key EXP1-R22C): CON-010 to CON-035.
- Changed by this step (Agent decisions under answer 37, history lines in the rules):
  - CON-027 v2 -> v3: unknown key gives HTTP 404 on the page (Q-020).
  - CON-027 v3 -> v4 (return round 1): one definition, answer 6 literally: known = any run, main session (own or effective key) or counted spawn carries the key; a known key with no data shows "no main session" and 0 runs; index rows of runs whose log is gone count (Q-021 reworked: already decided (answer 6) + Agent decision).
  - CON-034 v1 -> v2: `a=` (empty value) counts as missing -> 422 (Q-020). v2 -> v3 (return round 1): a value of only spaces counts as missing; other values not trimmed (Q-023).
  - CON-010 v1 -> v2 (return round 1): HTTP 503 with a message during the first index; the page does not rescan (Q-024).
  - CON-011 v1 -> v2 (answer 40, Q-025): the CLI refreshes the shared index with a guard; it refuses with exit 2, one line, nothing written, when its time zone, key patterns, console home or checkout differ from the index's; never runs the git fetch.
  - Return round 2 (sa-check2, review 6 notes): CON-011 v2 -> v3 (missing-values / other-schema refusal in the statement; another home = another index, Agent decision answer 37; notes say home/checkout rows are new); CON-027 v4 -> v5 (wording: run or main session whose log is gone); CON-031 v1 -> v2, CON-032 v1 -> v2 (note: the index is a cache, not data, answer 40).
  - CON-015 v6 -> v7: a run whose log file is gone is not failed (Q-022).
  - CON-022 v6 -> v7: a main session whose log file is gone adds 0 wait (Q-022).
- Relied on, unchanged (observed): CON-001 to CON-006. Retired: none.

### Data sources and fields (all read-only)
Index (SQLite cache, `Store.reader()`, `~/.agent-console/index.sqlite` or `$AGENT_CONSOLE_HOME`); no schema change, `SCHEMA_VERSION` stays 10.
- `runs`: run_id, session_id, kind (main | sub), role (CON-003), ticket, ticket_src, ticket_eff (CON-002; the ticket's key for every run, CON-013), parent_run_id, start_ts, end_ts (= first/last record ts of the file: CON-020, CON-021). No filter on `scope` or day (CON-012).
- `usage` (one row per API message, deduplicated across files): run_id, model (NULL -> "unknown", CON-017), input, output, cache_read, cache_w5m + cache_w1h (= cache write, CON-005, CON-017). Cost per row: `Pricing.message_cost(model, tokens)` returns `(float | None, Match)`; use `[0]`; `None` = unpriced -> adds 0 and counts as unpriced (CON-004, CON-018, CON-019). `tokens` is a dict with exactly the keys `input`, `output`, `cache_read`, `cache_w5m`, `cache_w1h` (the two cache-write kinds stay apart for the price; they are added only for the `cache_write` figure). Never sum from `messages` (duplicates).
- `tool_calls` where name IN ('Agent','Task'): run_id (spawning run), id, ts (spawn call time: order for CON-016), subagent_type (role of a spawn with no run file, else "general-purpose", as CON-003), ticket + ticket_src (lead -> spawn_lead, text -> spawn_text: CON-014 key sources), is_error (error tool_result, CON-014 a / CON-015), end_ts (NOT NULL = a tool_result exists; NULL = no evidence, not counted, CON-014). Duplicates: the primary key is (run_id, id) and a resumed session copies earlier turns into a new file, so one spawn can have several rows. Count each spawn once per `tool_calls.id`, using one fixed row: earliest `ts`, then smallest `run_id` (that row gives run_id, ts, key, is_error, end_ts); "has a run file" is checked on the id. Test: the same spawn id in two session files counts once.
- `sub_meta`: run_id, tool_use_id = the link from a run file to its spawn. A spawn "has no run file" when no `sub_meta.tool_use_id` equals its id. Read-only scan 2026-11-05: 670 sub-agent files in ~/.claude/projects, 0 without meta.json, so unlinked run files are not handled specially (a run file with no meta still counts as a run).
- `files`: run_id, path (raw log to read for CON-015 and CON-022), kind. `log_deleted`: run_id (file gone -> Q-022 rule).
- Determinism (CON-030): every read of `runs`, `usage`, `tool_calls`, `sub_meta`, `files` has an `ORDER BY` on its key columns (runs: start_ts, run_id; usage: run_id, ts, msg_key; tool_calls: ts, run_id, id), so float sums add up in the same order and give byte-identical JSON for the same data. Sums per model are done in Python in that order, not with SQL `SUM`.
- Raw logs (read-only, line by line, only for runs of the two tickets; answer 13, CON-035): sub-agent files for the CON-015 last-turn markers (isApiErrorMessage / system subtype "api_error"; tool_result is_error + denial texts; last assistant turn text or SubagentHandback, reuse `parser.handback_text`); main-session files for CON-022 (assistant stop_reason end_turn, AskUserQuestion tool_use + its tool_result is_error, rejected-prompt text, user record origin.kind, isMeta, toolUseResult, `<command-name>`, `<local-command-`, "[Request interrupted by user]"). Matched text never leaves the reader (CON-035).

### Ticket data (CON-013, CON-014)
- Runs and main sessions: `runs.ticket_eff == key`, exact string (CON-027: no case folding).
- Known key (CON-027 v5, one test per branch): any `runs` row with `ticket == key` or `ticket_eff == key` (main or sub, log file present or gone: rows of `log_deleted` runs count), or a counted spawn with no run file tied to the key below. A known key with no data by CON-013/CON-014 is compared: runs 0, main rows "no main session".
- Spawn with no run file and an end_ts: key = spawn_lead, else spawn_text, else parent = the spawning run's key in force at the spawn ts (`tickets.latest_before(evidence[parent], spawn_ts)`), else the spawning run's own `runs.ticket` (not ticket_eff). No key -> not counted anywhere.
- Evidence: today built inline in `Store.rebuild` (store.py:421-434 and 478-479). Extract it into one module-level function in store.py (e.g. `key_evidence(db, files)`) used by `rebuild` and by the comparison, with no change of behaviour (CON-001, CON-032); no duplicate SQL in the new module.

### APIs
- Page: `GET /compare?a=<KEY>&b=<KEY>`, registered in `server.create_app` (so the Host guard middleware, 127.0.0.1 bind and `SECURITY_HEADERS` apply as for every route, CON-033). HTML string built server-side with `html.escape` on every value (CON-035); no inline script, no inline style or `style=` attribute (CSP and test_static rules); styles in a static CSS file linked from `/static/`. Parameters declared optional (`str | None = None`) so the route, not the JSON validation handler, answers, in this order: missing, empty or only spaces -> 422 HTML naming the missing parameter(s) (CON-034 v3); first index running -> 503 HTML with one message, no figures (CON-010 v2: `st.progress.get("initial")` is true, or `st.progress["scans"] == 0` and `runs` is empty); unknown -> 404 HTML naming the key(s) (CON-027 v5); otherwise 200. The route never calls `st.rescan()`; it only reads (`st.reader()`); the console's 30 s loop and POST /api/rescan keep the index fresh. No form, no link, no swap (CON-010, CON-034). GET only: no POST route is added (test_server lists POST routes).
- CLI: `python -m agent_console compare <KEY> <KEY> [--json]` (CON-011). `__main__.py`: when `sys.argv[1] == "compare"`, run the compare CLI and `sys.exit` with its code; otherwise call `server.main()` exactly as today (no arguments, and any other argv as today: start.sh and service.sh launch it with none). argparse with `prog="python -m agent_console compare"`: missing argument, or an argument that is empty or only spaces -> usage on stderr, exit 2 (CON-034 v3); unknown key -> one line naming the key on stderr, exit 2, nothing on stdout (CON-027); success -> exit 0. Text table by default, JSON with `--json`.
- CLI index (CON-011 v3; already decided, answer 40 = Q-025 option B, guarded refresh). Order in `compare_cli.main`: argparse (usage, exit 2, CON-034) -> guard -> `Store(db_path, repo)` -> no-fetch -> `rescan(wait=True, min_interval=0)` -> progress check (exit 1) -> known-key check (exit 2, CON-027) -> output. No pid file, no AutoScorer (`after_scan` stays None), no uvicorn. Logs are never written (CON-012, CON-031).
  - "Built with" values. All four live in the existing `meta(k, v)` table (store.py:36); no new table, no new column, `SCHEMA_VERSION` stays 10.
    | Value | CLI side (today's code) | Stored today? | Key in `meta` |
    |---|---|---|---|
    | time zone | `config.tz_name()` (AGENT_CONSOLE_TZ, else system zone) | yes, `Store.__init__` store.py:106 | `tz` |
    | key patterns | `"\n".join(config.key_patterns())` (built-ins + AGENT_CONSOLE_KEY_PATTERNS), as store.py:99 | yes, store.py:107 | `key_patterns` |
    | console home | `config.home().resolve()` (AGENT_CONSOLE_HOME, else ~/.agent-console); the index is `home/index.sqlite` | no | `home` (new row) |
    | checkout | `Path(config.repo_root()).resolve()` (AGENT_CONSOLE_REPO, else the code's own checkout); this is `Store.repo` | no | `repo_root` (new row) |
    Recording (no schema change): `Store.__init__` writes two more rows next to the `tz` and `key_patterns` writes (store.py:106-107), in the same commit: `INSERT OR REPLACE INTO meta VALUES('home', str(self.db_path.parent.resolve()))` and `('repo_root', str(Path(self.repo).resolve()))`. They are only recorded, never compared by `Store.__init__`: the console's own start, reset and rescan behaviour is unchanged (CON-032). An index written before this change lacks the two rows until the console is next started with the new code.
    What the console-home check catches (Agent decision, answer 37, CON-011 v3, Q-025): only an index copied or moved from another home. A CLI with another AGENT_CONSOLE_HOME opens that home's own `home/index.sqlite` (none: `config.home()` creates the folder and the CLI builds a new index there). Harmless for the shared index: another home = another index, the console's index is never touched.
    Also compared (needed for "nothing written"): `PRAGMA user_version` vs `SCHEMA_VERSION`, because a mismatch makes `Store.__init__` run `_reset_derived` (store.py:100-105).
  - Guard: one module-level function in store.py, e.g. `index_mismatch(db_path, repo) -> list[str]`, that keeps the comparison next to the code that writes the rows. When `db_path` does not exist: returns [] (the CLI builds a new index with its own values; nothing shared exists yet). Otherwise it opens the file read-only (`sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)`, no `executescript`, no PRAGMA writes, no `Store()`), reads `user_version` and the four `meta` rows, closes, and returns the names that differ or are missing, in the fixed order `schema version, time zone, key patterns, console home, checkout`. The CLI calls it before `Store()`, so `_reset_derived` (store.py:100-105), the `meta` writes (store.py:106-108) and `os.chmod` never run on a refusal. A read-only open or read that fails (`sqlite3.Error`: a file that is not a database raises `sqlite3.DatabaseError`, a lock `sqlite3.OperationalError`, its subclass; checked, see "Interfaces for tests" B4): one line on stderr, exit 1, as "CLI errors".
  - Refusal (exit 2, stderr only, nothing on stdout, nothing written): exactly one line
    `compare: refused: the index at <db_path> was built with another <names>; run compare with the console's settings (nothing written)`
    where `<names>` is the comma-separated list of differing names (e.g. `time zone, checkout`). When values are missing (and none differ) the line is
    `compare: refused: the index at <db_path> does not record its <names>; start the console once with this checkout, then retry (nothing written)`.
    When some differ and some are missing, the "built with another" line is printed with all names. Values themselves are not printed (key patterns can be long; nothing secret, but one short line).
  - No git fetch: before `rescan`, the CLI sets `os.environ["AGENT_CONSOLE_NO_FETCH"] = "1"` in its own process, the existing switch in `scope.refresh_claims` (scope.py:122), so `ingest` (store.py:214-215) skips the fetch. No change to scope.py or `ingest`. The claims scope still reads the local ref (`git show`, scope.py:83, read-only), as the console does.
  - Not compared (answer 40 names only the four values above): AGENT_CONSOLE_TREE_ROOTS, AGENT_CONSOLE_WORKTREE_ROOTS, AGENT_CONSOLE_PROJECT_REMOTE, AGENT_CONSOLE_LOG_ROOT. With the same checkout but another value of these, the refresh rebuilds `runs` with the CLI's values and the running console serves them until its next scan (up to 30 s). Stated in README with the 'run with the console's settings' line.
  - Tests (test_compare_cli.py, `env` fixture only): one per guard branch (time zone, key patterns, console home, checkout, schema version differ; `home`/`repo_root` rows missing): exit 2, the exact line, stdout empty, and unchanged before/after: sha256 of index.sqlite and of index.sqlite-wal (when present), `PRAGMA user_version`, and every `meta` row (optionally the `runs` and usage row counts). index.sqlite-shm is left out: a `?mode=ro` read changes its bytes and may create it (checked with SQLite 3.51.0); it is SQLite's shared-memory index of the WAL, not data. Console-home test setup: build the index in home A, copy index.sqlite into home B, run the CLI with AGENT_CONSOLE_HOME=B, expect the refusal naming `console home`; matching values: refresh runs and the comparison prints, exit 0; no index file: built, exit 0; no fetch: with AGENT_CONSOLE_CLAIMS_REPO set and AGENT_CONSOLE_NO_FETCH removed from the test env, a spy on `subprocess.run` sees no `fetch` argv; Store init records `home` and `repo_root` (test_store_and_flags or test_compare_cli).
- CLI errors: `Store()` init can raise `sqlite3.OperationalError` ("database is locked") or `sqlite3.DatabaseError` ("file is not a database") -> catch `sqlite3.Error` (and `OSError`), one line on stderr, exit 1 (exact line: "Interfaces for tests" B4). `rescan(wait=True, min_interval=0)` does not raise: `_scan_safely` (store.py:195-202) catches every exception and sets `st.progress["state"] = "error"` and `st.progress["error"]` (the exception class name); after the call the CLI checks these and, when set, prints one line naming the class (no details) on stderr, nothing on stdout, exit 1.
- Reverse effect: the CLI's ingest write transactions can make the running console's own scan hit "database is locked"; the console then shows its scan-error banner until its next good scan (30 s). Stated in README.
- Tests: every CLI, page and compare test uses the `env` fixture (tmp AGENT_CONSOLE_HOME, AGENT_CONSOLE_LOG_ROOT, AGENT_CONSOLE_NO_FETCH=1); none opens ~/.agent-console or ~/.claude.
- JSON (CON-030; field names fixed here, never changed after release). `json.dumps(obj, sort_keys=True, indent=2)`, raw numbers, labels as strings:
  - top: `{"a": T, "b": T, "diff": D, "version": 1}`
  - T: `key`, `main_sessions` (count), `runs: {total, failed, repeat_rounds}`, `tokens: {total: K, by_model: {<model>: K}, main: K | "no main session"}`, `cost_usd: {total, by_model: {<model>: n}, main: n | "no main session", unpriced_messages}`, `time_s: {wall, active_role, wait: n | "no main session", wait_over_2h: n | "no main session"}`, `cost_share: n | "no main session" | "no sub-agents"`.
  - K: `{input, output, cache_write, cache_read}`.
  - JSON types in T: `key` string; `main_sessions` integer; `runs.total`, `runs.failed`, `runs.repeat_rounds` integers; every K leaf integer (tokens); `tokens.main` K object or the string "no main session"; `cost_usd.total` and every `cost_usd.by_model.<model>` number (float, raw USD); `cost_usd.main` number or the string "no main session"; `cost_usd.unpriced_messages` integer; `time_s.wall`, `time_s.active_role` numbers (float seconds); `time_s.wait`, `time_s.wait_over_2h` number or the string "no main session"; `cost_share` number or the string "no main session" or "no sub-agents". Integers stay integers, floats are never rounded.
  - D: always the full fixed tree of T without `key`, whatever the values are: every leaf of T (number or label) is replaced by `{"diff": n | "n/a", "ratio": n | "n/a"}` (CON-026). When a side's leaf is a label ("no main session", "no sub-agents"), the subtree is still complete: for `tokens.main` the four K leaves each `{"diff": "n/a", "ratio": "n/a"}`; for a scalar leaf one `{"diff": "n/a", "ratio": "n/a"}`. `by_model` over the union of both sides' models, absent = 0. So D's field set depends only on the model names, never on labels.
  - Wall time with no records: not possible for a known key with a run; a ticket whose only data is a spawn with no run file has wall time 0 (no session file of its own, CON-020) and active time 0 (CON-021).
- Rounding (CON-029, CON-024, CON-026): one formatter module used by both the page and the CLI text; half away from zero done with `decimal.Decimal(...).quantize(..., ROUND_HALF_UP)` on the absolute value (Python `round()` must not be used); never the ctq-lib.js helpers.

### Existing code to reuse (read, do not change behaviour)
- `tickets.py`: key rules, `latest_before`, `CHANGE_FILE_RE`; `effective_tickets` result is already in `runs.ticket_eff` (CON-001, CON-002).
- `pricing.py` + `console/pricing.yaml` (base-commit file, not edited): `Pricing.load(config.pricing_path())`, `message_cost` (CON-004, CON-005, CON-018, CON-019).
- `store.py`: `Store`, `reader()`, `rescan(wait=True)`, tables above; one refactor only (`key_evidence`).
- `parser.py`: `handback_text`, record shapes; read raw lines with `json.loads` per line, skip bad lines.
- `timing.epoch` for timestamps.
- `server.py`: `create_app` (route registration under the guard middleware, `SECURITY_HEADERS`), `main()` unchanged.

### Connected areas (impact)
- Every existing page and endpoint: unchanged (CON-032); the only shared code change is the `key_evidence` extraction in `Store.rebuild`, covered by the existing test_tickets, test_store_and_flags, test_scope_and_ticket_determinism.
- Server start: `__main__.py` is the entry for start.sh, service.sh (LaunchAgent) and `make start`; no-argument path must stay byte-for-byte the same behaviour (CON-011).
- Host guard, bind address and security headers: the new route must not bypass the middleware (CON-033); test with a foreign Host -> 404 JSON, and the headers on 200, 404 and 422 answers.
- The shared index `~/.agent-console/index.sqlite`: guarded refresh (answer 40, CLI index above); two new `meta` rows written by every `Store()` (console and CLI), no schema change; lock errors and the reverse effect on the console's banner: see "CLI errors" and "Reverse effect" above.
- Static files: a new CSS file is picked up by test_static (no inline style, no other origin).
- Docs: console/README.md (usage of the page and the CLI).
- Security review triggers (answer 23): new HTTP route echoing user input (escape), raw-log reading (no raw text to output).

### Modules (files) to change or add
| File | Change | Rule ids |
|---|---|---|
| console/agent_console/compare.py (new) | ticket data, counts, tokens, cost, times, share, diff, JSON tree; raw-log markers | CON-012..028, CON-030, CON-031, CON-035; uses CON-001..005 |
| console/agent_console/compare_format.py (new) | rounding and text for page and CLI (one formatter) | CON-024, CON-026, CON-029 |
| console/agent_console/compare_cli.py (new) | argparse, index refresh, text or `--json`, exit codes | CON-011, CON-012, CON-027, CON-028, CON-030, CON-034, CON-035 |
| console/agent_console/compare_page.py (new) | server-rendered HTML, escaped; error pages 404 / 422 | CON-010, CON-025, CON-027, CON-029, CON-033, CON-034, CON-035 |
| console/agent_console/__main__.py (change) | `compare` subcommand, else server as today | CON-011, CON-032 |
| console/agent_console/server.py (change) | register `GET /compare` inside `create_app` | CON-010, CON-033, CON-034, CON-027 |
| console/agent_console/store.py (change) | extract `key_evidence` used by rebuild and compare (refactor only); record `home` and `repo_root` in `meta` in `Store.__init__`; add read-only `index_mismatch` guard | CON-014 (parent key), CON-001, CON-011, CON-032 |
| console/static/compare.css (new) | page styles, no inline style | CON-033 |
| console/tests/test_compare.py (new) | figures, ticket data, failed / repeat, wait, diff, JSON (incl. full D tree with a label side, byte-identical output twice), duplicate spawn id counted once, known-key branches of CON-027 v5 | CON-013..026, CON-028, CON-030 |
| console/tests/test_compare_format.py (new) | rounding cases incl. ties, -0, `-$1.23`, `0 min` | CON-024, CON-026, CON-029 |
| console/tests/test_compare_cli.py (new) | subcommand, no-arg server path, exit codes 0 / 1 / 2; guard branches (refusal line, files unchanged), no fetch, meta rows recorded | CON-011, CON-027, CON-034 |
| console/tests/test_compare_page.py (new) | 200 / 404 / 422 / 503 (first index), Host guard, headers, escaping, no raw text; the test_static checks run on the 200, 404, 422 and 503 bodies: no `<style`, no `style=` attribute, no inline `<script>`, nothing from another origin (test_static covers only files in static/, not compare_page.py HTML) | CON-010, CON-027, CON-033..035 |
| console/README.md (change) | usage lines | CON-010, CON-011 |
Not changed: tickets.py, pricing.py, console/pricing.yaml, parser.py, timing.py, ctq*.py, static JS, index.html, config.py.
Fixture logs: new ones are written by the tests into tmp (conftest helpers `assistant`, `tool_use`, `tool_result`, `api_error`, `add_sub`, `write_jsonl`); the recorded fixtures stay as they are.

### Unknowns, closed
- Page HTTP status for an unknown key (CON-027 note): 404. Agent decision Q-020.
- Empty `a=` / `b=`: missing, 422. Agent decision Q-020.
- Key that is only a main session's own key, effective key elsewhere; key only on a counted spawn: both known (already decided, answer 6; Q-021 reworked). Index rows of runs whose log is gone count as "in any log": Agent decision Q-021.
- A value of only spaces: missing. Agent decision Q-023.
- Page during the first index: 503 with a message; the page never rescans. Agent decision Q-024.
- Duplicate spawn rows, JSON types and full D tree, ORDER BY, message_cost use: technical, fixed above.
- Log file gone: not failed, 0 wait. Agent decision Q-022.
- "Over 2 hours" part with no main session: it is part of the wait-time row, so "no main session" (CON-023 + CON-025); already covered.
- Spawn-to-run link: `sub_meta.tool_use_id` (technical; 0 unlinked files found).
- CLI and the shared index: Q-025 ANSWERED (answer 40): option B, guarded refresh, exit 2 on refusal, no git fetch; CON-011 v2, v3. Q-023 and Q-024 accepted (answer 40).
- Missing `home` / `repo_root` rows (index from before this change) and a schema-version mismatch: refuse, as "not built with the same values". Agent decision (answer 37) in CON-011 v2 (statement since v3).
- Another console home: another index, the console's index is never touched; the home check catches only a copied or moved index. Agent decision (answer 37), CON-011 v3, Q-025.
- No blocking question open.

---

## QA analysis (DoR part 3, QA analyst, 2026-11-05)
Ticket size: High · ticket risk class: High. (The size sits here, not in the header line: the header is the verbatim brief and is not edited.)
Full analysis: [qa.md](qa.md) (docs/agents/work/EXP1-R22C/qa.md): testability, 95 test conditions, 227 coverage items (EP 136, DT 47, BVA 30, ST 11, CL 3; design check 1: +CI-022-30 for CON-022 v11 / Q-034, CI-012-03 retired per Q-039), risk per rule, gap hunt.
Return round 1 (rr8-qa.md): business analyst fixed CON-022 v9 (Q-033, resumed file: a gap counts once), then v10 (same gap = shared uuid OR shared message id + requestId; closes the QA testability note) and CON-011 v5 (Q-027 exit 1 in the statement); QA added TC-022-8, 9 and CI-022-22..29 (CI-022-24 reworked for v10), CON-011 items cite v5.
Gaps closed as Agent decisions (answer 37) by the QA analyst: Q-026 (CON-011 v4: no index in the CLI's home, the console's own included -> built, exit 0; rr7-sa.md note 2), Q-027 (CON-011 v4 note: run-time index errors -> exit 1), Q-028 (CON-027 v6), Q-029 (CON-034 v4), Q-030 (CON-015 v8, CON-022 v8), Q-031 (CON-022 v8), Q-032 (CON-020 v2, CON-021 v4). Risk: CON-032 medium -> high (v3). No blocking question.
Build and tests note: the builder follows the rule versions above; the technical design in this file is unchanged by them (Q-026 = `index_mismatch` returns [] on no file; Q-027 = "CLI errors").

**Definition of Ready: READY 2026-11-05** · business analyst signed (rr4 PASS; CON-022 v10, CON-011 v5 re-checked in rr9 PASS) · system analyst signed (sa-check4 PASS, rr7 PASS) · QA analyst signed (qa.md, return round 1, aligned with CON-022 v10) · lead QA approved 2026-11-05 (sample check of the 9 high rules CON-011, 012, 013, 015, 018, 022, 032, 033, 035 against qa.md and console.md: traceability, oracles, negatives, gap hunt, test isolation) · open blocking items: 0 · open blocking questions: 0
Notes for the test designers and the builder (lead QA, 2026-11-05; rules not changed):
- rr9 N1, CON-022: two gaps in one file whose stop records share message.id + requestId (parallel stop records of one reply): the narrowest reading is one gap. Confirm at build time on the built records and add a coverage item for it (one gap, counted once); if the code cannot tell them apart, stop and ask, do not pick a reading.
- rr9 N3, change.md: the SA rule-change list above stops at CON-022 v7 / CON-011 v3; build to the current versions (CON-011 v5, CON-015 v8, CON-022 v10, CON-027 v6, CON-034 v4, see the QA analysis). The reader that collects stop keys (uuid, message.id, requestId per stop record, per main-session file) has no technical detail here: the builder adds it in compare.py, read-only, no raw text kept.
- Test isolation: CLI tests that start a subprocess pass os.environ from the env fixture (never env={}), so the default ~/.agent-console and ~/.claude/projects are never reached; CI-011-07 "HOME=B" means AGENT_CONSOLE_HOME=B, not HOME.
- Oracles: status-only items (CI-010-05, CI-033-03) also assert the body (the 404 page or JSON), not the status code alone.

---

## Interfaces for tests (system analyst, 2026-11-05; answers td-questions.md section B)

Main goal: give the test designers and the builder exact names, signatures, markup and texts, so the cases can become tests without guessing. Technical contract only; no rule changes. Rules: CON-010 v2, CON-011 v5, CON-029 v7, CON-033 v1, CON-034 v4, CON-035 v1 (and CON-024 v2, CON-026 v4, CON-027 v6 for labels). Checked on 0891a04 by reading the code and by two scratch runs in /tmp (deleted).

### B1. Names and signatures
- `compare.py` (data, no output text, no clock):
  - `compare(db: sqlite3.Connection, pricing: Pricing, a: str, b: str) -> dict`: the whole tree of CON-030, `{"a": T, "b": T, "diff": D, "version": 1}`. It does not check for unknown keys (an unknown key gives a T of zeros); callers check first. This is DATA(K) in the cases: `compare(db, pr, K, K)["a"]`.
  - `ticket(db: sqlite3.Connection, pricing: Pricing, key: str) -> dict`: one T.
  - `unknown_keys(db: sqlite3.Connection, a: str, b: str) -> list[str]`: the unknown keys of CON-027 v6, a first, the same key given twice named once; `[]` when both are known.
  - `to_json(tree: dict) -> str`: `json.dumps(tree, sort_keys=True, indent=2)` (no trailing newline; the CLI prints it with `print`).
  - The caller owns the connection: `db = store.reader()`, then `db.close()` in `finally`. Raw logs are read from the paths in `files`; no Store object is needed.
- `compare_format.py` (one formatter for page and CLI text, CON-029):
  - `tokens(v) -> str` (`12k`), `usd(v) -> str` (`$1.23`, `-$1.23`), `minutes(v) -> str` (`12 min`, value in seconds), `ratio(v) -> str` (`0.25`; ratio and cost share), `count(v) -> str` (integers: runs, main sessions, unpriced messages; `-2` for a negative difference). Each takes `int | float | str`; a str (a label: `no main session`, `no sub-agents`, `n/a`) is returned unchanged.
  - Rounding: `Decimal(str(v))` (the shortest repr, the same digits the JSON shows), `quantize(..., ROUND_HALF_UP)` on the absolute value, sign added back only when the rounded size is not zero. So `usd(2.675) == "$2.68"`, `usd(0.125) == "$0.13"`, `usd(-0.004) == "$0.00"`, `tokens(1500) == "2k"`, `tokens(-1500) == "-2k"`, `tokens(-400) == "0k"`, `minutes(30) == "1 min"`, `minutes(29.99) == "0 min"`, `minutes(-20) == "0 min"`, `minutes(8100) == "135 min"`, `ratio(0.125) == "0.13"`, `usd(1234.56) == "$1234.56"`. No `+` sign on a positive difference.
  - `rows(tree: dict) -> list[Row]`, `Row = NamedTuple(id, label, a, b, diff, ratio)` (all str): the table rows of B2 in their fixed order, already formatted. The page and the CLI text are both built from it.
  - `HEADINGS = ("Figure", "Difference b - a (ratio b / a)")`; the column headings are `Figure`, the key of a, the key of b, `Difference b - a (ratio b / a)`.
  - `text_table(tree: dict) -> str`: the CLI text (B2, CLI text).
- `compare_cli.py`: `main(argv: list[str]) -> int`; `argv` is what follows `compare` (e.g. `["EXP1-1", "EXP1-2", "--json"]`). It never calls `sys.exit` itself: argparse's `SystemExit` is caught and its code returned (`-h` returns 0). Tests call it in process with `capsys` and assert the return value. `__main__.py`:
  ```python
  import sys
  from . import server

  if len(sys.argv) > 1 and sys.argv[1] == "compare":
      from . import compare_cli
      sys.exit(compare_cli.main(sys.argv[2:]))
  server.main()
  ```
  (`server.main()` is called through the module, so a test can `monkeypatch.setattr(server, "main", spy)`, set `sys.argv = ["agent_console"]` and run `runpy.run_module("agent_console", run_name="__main__")` to check the no-argument path.) A subprocess test runs `[sys.executable, "-m", "agent_console", "compare", ...]` with `cwd` = the console folder and `env=os.environ.copy()` taken after the `env` fixture has set its variables (never `env={}`).
- `compare_page.py`: `render(tree: dict) -> str` (200), `missing_page(names: list[str]) -> str` (422), `building_page() -> str` (503), `unknown_page(keys: list[str]) -> str` (404). The route lives in `server.create_app`: `@app.get("/compare")` with `a: str | None = None, b: str | None = None`, returns `HTMLResponse(body, status_code=...)`; it uses the app's own `st` and `pr` (the `store` and `pricing` given to `create_app`).
- Page test client (as test_server.py): `store = Store(); store.ingest()`, then `TestClient(server.create_app(store=store, pricing=Pricing.load(config.pricing_path()), port=8790), base_url="http://127.0.0.1:8790")`. Write the tmp pricing (B6) before `Pricing.load`.
- Progress in a test: `store.progress` is a plain dict on the Store given to `create_app`; the route reads it on each request. Set it directly: `store.progress["initial"] = True` (503). Facts from store.py: a fresh `Store()` has `progress["scans"] == 0` and no `"initial"` key; `store.ingest()` ends with `initial=False` and `scans` + 1. So: fresh Store on an empty home, no ingest -> 503; a new Store on a home already indexed (runs not empty), no ingest -> 200; after `ingest()` with no runs -> scans 1 -> not 503 (404 for an unknown key). Spy on rescans with `monkeypatch.setattr(store, "rescan", spy)` and `monkeypatch.setattr(store, "ingest", spy)`.

### B2. Page markup and error texts
- Every page (200, 404, 422, 503) is one complete HTML document, `text/html; charset=utf-8`, with this skeleton (no inline script, no `<style`, no `style=`, nothing from another origin):
  ```html
  <!doctype html>
  <html lang="en">
  <head><meta charset="utf-8"><title>Ticket comparison</title><link rel="stylesheet" href="/static/compare.css"></head>
  <body><h1>Ticket comparison</h1>
  ... one table (200) or one <p class="error">...</p> (404, 422, 503) ...
  </body></html>
  ```
  The title and heading never contain a key (so the 503 and 422 pages name no key).
- 200 table: `<table class="compare">`, `<thead>` with one row of four `<th scope="col">`: `Figure`, key a (`class="a"`), key b (`class="b"`), `Difference b - a (ratio b / a)` (`class="d"`). Each body row:
  `<tr data-row="<id>"><th scope="row">Label</th><td class="a">…</td><td class="b">…</td><td class="d"><span class="diff">…</span> (<span class="ratio">…</span>)</td></tr>`
  so a diff cell reads e.g. `-$1.23 (0.50)`, `2 (n/a)`, `n/a (n/a)`. A side whose value is a label shows the label text in its cell. Every value, key and model name goes through `html.escape(..., quote=True)`, attributes too.
- Rows, in this order (`<m>` = every model of the union of both sides, sorted by name; `<k>` = `input`, `output`, `cache_write`, `cache_read` with the label words `input`, `output`, `cache write`, `cache read`):
  | id (= JSON path) | Label | Format |
  |---|---|---|
  | `main_sessions` | Main sessions | count |
  | `runs.total` | Role runs | count |
  | `runs.failed` | Failed runs | count |
  | `runs.repeat_rounds` | Repeat rounds | count |
  | `tokens.total.<k>` (4 rows) | Tokens, input / output / cache write / cache read | tokens |
  | `tokens.by_model.<m>.<k>` (4 rows per model) | Tokens, `<m>`, input / ... | tokens |
  | `tokens.main.<k>` (4 rows) | Main-session tokens, input / ... | tokens |
  | `cost_usd.total` | Cost | usd |
  | `cost_usd.unpriced_messages` | Unpriced messages | count |
  | `cost_usd.by_model.<m>` | Cost, `<m>` | usd |
  | `cost_usd.main` | Main-session cost | usd |
  | `time_s.wall` | Wall time | minutes |
  | `time_s.active_role` | Active role time | minutes |
  | `time_s.wait` | Main-session wait time | minutes |
  | `time_s.wait_over_2h` | Main-session wait time from gaps over 2 h | minutes |
  | `cost_share` | Cost share (main / sub-agents) | ratio |
  The unpriced count (answer 8, "next to the cost") is its own row directly after `Cost`, so it has its own difference. The diff cell formats the difference with the row's format and the ratio with `ratio`. With no main session, `no main session` shows in 8 cells of that side (4 main token rows, main cost, wait, wait over 2 h, share).
- Error texts (visible text; markup as shown; one `<p class="error">`):
  | Status | When (checked in this order) | Markup inside `<p class="error">` | Visible text |
  |---|---|---|---|
  | 422 | a or b missing, empty or only spaces (CON-034 v4) | `Missing parameter: <code>a</code>.` | `Missing parameter: a.` |
  | 422 | both | `Missing parameters: <code>a</code>, <code>b</code>.` | `Missing parameters: a, b.` |
  | 503 | any scan in progress, or no scan yet on an empty index (CON-010 v3, answer 47): read in the page's one snapshot, `st.progress.get("initial")` true, or a `meta` row with `k LIKE 'scan:%'` (written by any process's `ingest`, see "Scan in progress" below), or `st.progress.get("scans", 0) == 0` and `runs` empty | `The console is updating its index. Reload this page later.` | same |
  | 404 | one key unknown, or the same unknown key twice (CON-027 v6) | `Unknown ticket key: <code>KEY</code>.` | `Unknown ticket key: KEY.` |
  | 404 | both unknown, a first | `Unknown ticket keys: <code>KEY_A</code>, <code>KEY_B</code>.` | `Unknown ticket keys: KEY_A, KEY_B.` |
  The key is escaped (`<b>x</b>` shows as `&lt;b&gt;x&lt;/b&gt;`). The parameter name sits alone in `<code>`, so "names a, not b" is `"<code>a</code>" in body and "<code>b</code>" not in body`. The 503 text has no digit, no `$`, no `min`, no key and no "unknown". The 422 page is the route's own HTML (the app's JSON `{"detail": "Invalid request."}` handler is not reached, because both parameters are optional). A foreign Host still gets the middleware's JSON 404 `{"detail": "Not found."}` before the route.
- CLI text (`text_table`): the same rows, labels and headings; one header line, then one line per row; cells joined by ` | `, each cell padded with spaces to its column's width, trailing spaces stripped; the diff cell `diff (ratio)` as on the page. Tests split a line on `|` and strip each part. Ends with one newline (`print`).

### B3. CLI usage text (argparse, checked with Python 3.13)
`ArgumentParser(prog="python -m agent_console compare", description="Compare two tickets side by side.", allow_abbrev=False)`; positionals `a` (metavar `KEY_A`), `b` (metavar `KEY_B`); `--json` (`store_true`). An empty or only-spaces key: `parser.error("empty key: KEY_A")` (or `KEY_B`, or `KEY_A, KEY_B`). Exact stderr, exit 2, stdout empty:
```
usage: python -m agent_console compare [-h] [--json] KEY_A KEY_B
python -m agent_console compare: error: the following arguments are required: KEY_A, KEY_B
```
Second line by case: no key -> `the following arguments are required: KEY_A, KEY_B`; one key -> `... required: KEY_B`; three keys -> `unrecognized arguments: X-3`; `""` or `"  "` as a -> `empty key: KEY_A`; both -> `empty key: KEY_A, KEY_B`.
Other CLI lines (stderr, one line, stdout empty, exit 2): unknown key `compare: unknown ticket key: KEY` / both `compare: unknown ticket keys: KEY_A, KEY_B` (a first; keys printed as typed, never escaped or trimmed). Refusal lines: see "CLI index".

### B4. sqlite error class and the exit-1 line
Checked (scratch run, SQLite 3.54.1 of the console venv): a file that is not a database raises `sqlite3.DatabaseError` ("file is not a database") from `Store()` and from the read-only guard read (the `?mode=ro` connect itself is lazy and passes; the first `PRAGMA user_version` raises); a held write lock raises `sqlite3.OperationalError` ("database is locked") from `Store()` after SQLite's default 5 s wait (a read-only read still works under WAL); a folder in place of the file raises `OperationalError` ("unable to open database file"). `OperationalError` is a subclass of `DatabaseError`. So the CLI catches `sqlite3.Error` (and `OSError`) around the guard, `Store()` and the comparison read, and prints the raised class name. Exact line (stderr, nothing on stdout, exit 1):
`compare: error: the index at <db_path> could not be opened or refreshed (<ClassName>)`
`<ClassName>` = `type(e).__name__` (e.g. `DatabaseError`, `OperationalError`), or `st.progress["error"]` when `rescan(wait=True, min_interval=0)` ends with it set (e.g. `ValueError`). The sqlite message text never appears. A 0-byte file is a valid empty SQLite file (`user_version` 0, no `meta` table): the guard checks that `meta` exists (`sqlite_master`) before reading it and reports `schema version` plus the four values, so it is a refusal (exit 2, "built with another schema version, time zone, key patterns, console home, checkout"), as CON-011 v5 says for another schema version; not exit 1. Test for the lock: monkeypatch `compare_cli.Store` with a raiser (EP-011-20), not a real lock (5 s).

### B5. Test data: own key vs effective key (checked by a scratch run with the conftest helpers)
- Own key = effective key: main file `env.root/PROJECT/"S1.jsonl"`, first record `user_prompt("[KA] start", t=0)` (source `prompt_lead`), no sub-agents -> `ticket == ticket_eff == KA`.
- Effective key differs (CON-002, `config.CHILD_SHARE = 0.8`): the same main file plus, per child i, `assistant(f"m{i}", t=1+i, blocks=[tool_use(f"t{i}", "Agent", subagent_type="builder", description="[KB] build", prompt="p")])`, `tool_result(f"t{i}", t=100+i)`, and `add_sub(env.root, "S1", f"ag{i}", "builder", [assistant(f"s{i}", agent=f"ag{i}", session="S1", t=10+i)], f"t{i}")`. Results seen: 1 child KB -> main `ticket` KA, `ticket_eff` KB; 4 KB + 1 KC (0.8) -> `ticket_eff` KB; 3 KB + 1 KC (0.75) -> `ticket_eff` KA (own). With one KB child: KA is known (own key of a main session) with no data: runs 0, main rows `no main session`; KB has `main_sessions` 1 and 1 run.
- Keep ids unique: message ids (usage is deduplicated across files by message id + requestId), tool_use ids, agent ids; `user_prompt` makes its uuid from `t` and session (`up-<t>-<session>`), `assistant` from msg id and block count, `tool_result` from the tool id. Two records with the same uuid are one record for CON-022.

### B6. Pricing in tests
The `env` fixture writes `models: {}` to `env.tmp/"pricing.yaml"` (every message unpriced). A test that needs a priced model rewrites it before loading (setup only, no conftest change):
`(env.tmp / "pricing.yaml").write_text("regional_multiplier: 1.0\nmodels:\n  sonnet-5-5: {input: 2.00, output: 10.00, cache_write_5m: 2.50, cache_write_1h: 4.00, cache_read: 0.20}\n")`
Then the default `assistant()` model `claude-sonnet-5-5` with `usage()` costs 0.00022. No `tier_defaults`, so any other model id (e.g. `claude-unpriced-x`, also `claude-opus-5-5`) stays unpriced. The page gets it through `Pricing.load(config.pricing_path())` in `create_app`; the CLI loads `Pricing.load(config.pricing_path())` itself at each call. Note: `message_cost` also returns None when a needed price field is missing for a non-zero token count.

### B7. Long gaps
`conftest.ts(n)` writes `10:<n//60>:<n%60>` and breaks at n >= 3600. Local helper in the test module (no conftest change):
```python
from datetime import datetime, timedelta, timezone
def at(n: int) -> str:
    return (datetime(2026, 10, 20, 10, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=n)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
```
`at(n) == ts(n)` for n < 3600. `assistant(..., day=at(n))` uses it as is (the helper takes `day` as the full timestamp when it contains `T`); for `user_prompt`, `tool_result` and `api_error` set `rec["timestamp"] = at(n)` after the call, and still pass a distinct `t` so their uuids stay distinct.

### B8. A session with no record timestamps
Not dropped (checked: scratch run of `Store.rescan(wait=True)` on a main file whose records have no `timestamp`): it is indexed as a `runs` row (kind main, key from its first prompt, `start_ts` and `end_ts` NULL), its `files` row has `first_ts`/`last_ts` NULL, its `usage` rows exist with `ts` NULL, and the scan ends with no error. So BVA-006 fixture A works at the comparison level (wall 0, active 0, CON-020 v2, CON-021 v4); the comparison must skip NULL timestamps (SQLite sorts NULL first in `ORDER BY start_ts`).

No rule changed, no new Agent decision, no blocking question.

## Build decisions (system analyst, 2026-11-05; build-decisions.md "To the system analyst")
Checked against CON-011 v5, CON-014 v7, CON-015 v8, CON-016 v5, CON-010 v2, CON-003, CON-034 v4 and answers 2, 3, 13, 18, 25, 31, 33, 35, 37, 38, and the code (compare.py, compare_cli.py, store.py, parser.py, server.py). No blocking item. No scope, behaviour or budget change.

- D2 (CON-015, `compare.run_failed`): consistent with the rule. The last turn decides: final reply = text or a SubagentHandback call; an API error, a denial result, an ordinary tool_result or an open tool_use as the last turn = no final reply = failed. Not matching denial texts in sub-agent files gives the same result as the rule's denial marker (a denial counts only when no final reply follows it). A readable file with no assistant turn: no final reply, failed (literal reading); a missing or unreadable file: not failed (Q-022, Q-030). One part is new: consecutive assistant records with the same message.id are one turn. Agent decision (answer 37): narrowest reading. Claude Code writes one API reply as several records (one per content block), so "the last assistant turn" is the last message, not the last record. Without this, a reply whose text comes before its last tool block would count as failed.
- D3 (CON-016, repeat rounds = runs minus distinct roles): consistent. For each role with n >= 1 runs on the ticket, answer 2 gives n - 1 repeat rounds. The sum over all roles is total - distinct roles. Start order only decides which run is first, not how many repeats there are, so leaving out the sort is correct. The list `roles` holds the same items as the run total: the ticket's sub-agent runs (no main sessions, answer 19), plus the counted spawns with no run file. Those spawns are denied or other error results (answers 18, 25, 31) and non-error results (answer 35). A spawn with no tool_result (`end_ts` NULL) is left out (answer 33). A spawn's role is subagent_type, else "general-purpose", which is CON-003 for a run with no meta. Two code gaps affect which spawns are in the list (see "Code changes needed").
- D5 (CON-014, spawn key): consistent. tool_calls.ticket is the lead key, else the text key (parser.py), so the order is spawn_lead, spawn_text, parent, as in CON-001. Parent = `tickets.latest_before` over the spawning run's `key_evidence` at or before the normalised spawn ts (CON-014 v7, Q-040), else the spawning run's own `runs.ticket`, not the effective key. A spawn with no timestamp takes the newest evidence. That is not a new decision: it is what `latest_before(ts=None)` already does for a run with a file (store.py, sub-run parent key). CON-014 says "the same as for a run with a file". The shared `key_evidence` refactor has the same inputs and output as the old inline code.
- D6 (CON-011, `index_check` -> (differ, missing)): consistent. The split lets the one stderr line say "built with another ..." or "does not record ...". A mixed case (something differs and something is missing, e.g. an empty file: schema version 0 plus four missing values) prints the "another ..." line naming all of them. Agent decision (answer 37), wording only: narrowest reading. The refusal (exit 2, nothing written) is the same, and the line still names everything that differs or is missing. `index_mismatch` stays as the merged list.
- D7 (CON-011, CON-034): consistent. An empty or spaces-only key goes through `parser.error`, so usage is on stderr and the exit code is 2 (CON-034 v4: counts as missing). This runs before the index check. The Store connection is closed in `finally`. When `Store()` fails, the earlier `except` returns before the second `try`, so nothing is left open.
- Other (first index = `progress["initial"]`, or scans == 0 with no runs): consistent with the CON-010 v2 statement ("the index had no runs when the scan started, or no scan has run yet on an empty index"). It is server.py only. The CLI does not use it (CON-011: no index file means build, compare, exit 0).

### Code changes needed (small, not blocking; builder)
1. Copies of a spawn (`_Ctx.spawns`). Only the earliest row per tool_use id is used, for both `end_ts` and `is_error`. When the same spawn id is in more than one file (for example a resumed or copied session), the earliest copy may have no tool_result while a later copy has one. The spawn is then left out, against CON-014 (a)/(b) and answers 31 and 35. Change: count the spawn when any copy has a tool_result (`end_ts` not NULL). Failed = any copy with a result has is_error. Key and place in the order still come from the earliest copy. Add a test (one spawn id in two files, the result only in the second).
2. A tool_result record with no timestamp (store.py ingest, `UPDATE tool_calls SET end_ts=COALESCE(end_ts, ?)` with `e.ts` None). `end_ts` stays NULL, so a spawn whose result exists looks like "no tool_result" and is not counted (against CON-014 and answers 31 and 35; answer 33 applies only when there is no result). B8 shows that files with no timestamps exist in the test data. Change: record that a result exists even with no ts, without a schema change. For example, fall back to the call's own ts (`COALESCE(end_ts, ?, ts)`, dur 0). If both are NULL, the compare check must not rely on `end_ts` alone. The builder picks the mechanism. Add a test (a denied spawn whose tool_result has no timestamp counts in total, failed and repeat rounds).

### For the business analyst (no rule edit by the system analyst; rules are edited in parallel)
- Add the two Agent decisions above to the rules, with ticket EXP1-R22C and date 2026-11-05: CON-015 (one message.id = one turn) and CON-011 (mixed differ/missing line wording).
- An observation, not blocking and not a builder decision: under the CON-015 last-turn rule, a sub-agent run that is still running when the comparison reads it (its last turn is an open tool_use) counts as failed. The rule as written covers this ("has no final reply"). If the product owner wants running runs left out, that is a new question for the business analyst.

## Scope check: parser.py (system analyst, 2026-11-05; builder fix round D1/G1/G2)
Checked against CON-032 v3 (existing pages unchanged), CON-017 v2, CON-018 v2, CON-019, Q-042, answers header ("keep the existing behaviour"), and the code at 0891a04 (parser.py `events_from_record`, store.py ingest + usage view, queries.py `aggregate`, timing.py `finalize_tool_calls`). Verdict: **REVERT** the parser.py and store.py ingest changes. Not blocking: the existing behaviour is kept and the tests are fixed.

1. At 0891a04, an assistant record that has no usage block still produces a messages row. Only `isApiErrorMessage` and the `<synthetic>` model return early. Every other record yields a "message" event with `**_usage(msg.get("usage") or {})`, which is five zero counts, and store.py inserts it with no condition. The usage view keeps one row per msg_key, and queries.py `aggregate` counts it: `messages` +1; `unknown_messages` +1 when the model has no price (shown as "+N msgs unpriced" or "cost unknown"); and a row under its model (runs.models from usage, `model or "?"`). `last_msg` (flags) also reads messages.
2. So the change alters existing pages. A standalone record with no usage block would lose its message count, its model row, its unpriced count and its last-message time on the existing pages. Because of the max-merge, a record that shares a msg_key with a record that has usage would show no change. Against CON-032 v3, and against Q-042 (a zero-token message counts under its model and as unpriced).
3. The fix. In code: drop `has_usage` (parser.py) and the `if x.get("has_usage", True)` guard (store.py), so both match 0891a04. The cause is the test helper, not the product. `W.asst(u=None)` in console/tests/test_compare.py pops the usage block and relies on the reverted skip. Fixture fix, with no expected value changed:
   - `W.__init__(..., filler_model=M1)`. `W.asst` with `u=None` writes `usage(0, 0)` under `self.filler_model` and does not pop usage. Real Claude Code records always carry usage, and a zero block is the same as no block at 0891a04.
   - EP-017-03: `W(env, filler_model=None)`. EP-018-02: `W(env, filler_model="claude-sonnet-9")`. BVA-014: `W(env, SONNET, filler_model=SONNET_MODEL)`.
   - D1-confirm: `W(env, filler_model="zzz-unpriced")`, plus `w.sub("S1", "ABC-1")` with no steps. The spawn record is then the one zero-token message.

Deferred tool_result updates and `COALESCE(end_ts, ?, ts)` (store.py ingest, G2). These are not order-only:
- (a) In a batch where a result comes before its tool_use, the result was lost at 0891a04. Now it is applied. In real logs this order only happens in the test, where `W.flush` sorts by timestamp and a record without one sorts first.
- (b) `, ts`: a result with no timestamp now gets end_ts = the call's ts. finalize_tool_calls then sets dur_s 0, timed_out 0 and blocked 0, and the run page "tests" list shows that call (it lists `dur_s IS NOT NULL`). At 0891a04 the call had no duration and was not listed.

This revises my "Code changes needed" item 2 (it named `, ts` only as an example). REVERT both, back to the 0891a04 UPDATE in record order. Do G2 in compare.py instead (planned module). In `_Ctx.spawns`, select `out_chars` and use `r["out_chars"] is not None` as the sign that a result exists. Every tool_result UPDATE sets it (`COALESCE(out_chars, ?)` with default 0), with or without a ts, and a tool_use row starts with NULL. In the G2-confirm test, `w.flush()` first, then rewrite the main file in the same order with the result record's `timestamp` removed (`write_jsonl`), then `data(scan(), "ABC-1")`.

Evidence: a scratch copy (deleted after) with parser.py and the store.py ingest exactly as at 0891a04, plus the compare.py and test changes above. Result: test_compare.py 149 passed; the console suite 686 passed. The 21 failures are scratch-layout only (missing roles-22/, kit/, hooks/ files); none are in compare, store, server or static. Ruff is clean. Still in scope (planned): the store.py meta rows `home`/`repo_root`, `key_evidence`, `index_check`/`index_mismatch`.

## Build decisions B1-D1, B1-D2 (system analyst, 2026-11-05; build-decisions.md "Builder B1 fix")
Checked against CON-015 v11, Q-044, Q-046, Q-047, Q-048, answers 3, 37, 38, and compare.py `run_failed`, parser.py (user-record loop).
- B1-D1: mismatch, code change needed. A handback turn can be followed by other tool_results: parser.py loops over every tool_result block of one user record, and nothing stops a turn from holding a SubagentHandback call next to another tool_use (parallel calls); their results come in the same record or in separate records. CON-015 defines final reply by the last assistant turn (a handback call is one); a tool_result is not a turn (Q-047). v11 makes only the handback's own error result fail the run. Today a sibling's result (same or separate record) sets "result" = failed. Fix in `run_failed`: when state == "reply" and hb_ids is not empty, a user record sets "result" only if a result with tool_use_id in hb_ids has is_error true; any other tool_result is ignored (state stays "reply"). When hb_ids is empty (text + tool_use turn), keep today's behaviour (Q-046). Agent decision (answer 37, narrowest reading): a sibling tool's result after a handback turn, error or not, does not make the run failed; the handback is in the last turn and v11 names only its own result. Test: handback + Bash in one turn, Bash result after (same record, and separate record) -> not failed; handback error result alongside -> failed.
- B1-D2: consistent, no decision needed. With hb_ids reset on each new turn, a non-reply state before a handback result means a later API error or a non-reply turn is the last turn: failed by CON-015 (API error as last turn; no final reply). After the D1 fix, a sibling result no longer leaves "result" in between.

## Spawn-to-run-file link (system analyst, 2026-11-05; code review 3 finding 1)
Rules: CON-014 v7, CON-015, CON-016 v5, CON-003 v1 (answers 18, 25, 31, 33, 35). Goal: a spawn whose run file exists is never also counted as a spawn with no run file.

Fields in the index today (store.py schema, parser.py at 0891a04):
- `sub_meta.tool_use_id`: from agent-*.meta.json `toolUseId` only. No row when meta is missing or unreadable.
- `files.agent_id` / `files.session_id`: from the file name (`<session>/subagents/agent-<id>.jsonl`). `files.first_ts`: the first record timestamp.
- `tool_calls` (Agent/Task): `id`, `run_id`, `ts` (the call), `end_ts` (the result record, same file), `out_chars`, `is_error`, `subagent_type`.
- The parent's `toolUseResult.agentId` is NOT stored (parser keeps only tool_use_id, is_error, out_chars of a result).

Read-only count (answers 22 and 42; ~/.claude/projects; counts and field names only, no content):
- 765 sub-agent files, 765 meta files readable, 742 with toolUseId; 23 with no toolUseId (not forks).
- 754 Agent/Task spawns; 639 results carry `toolUseResult.agentId`. All 631 that hit a meta with a toolUseId agree with it, 0 contradict. The 8 others are `Skill` calls, not spawns. Error results never carry agentId (1356 are plain strings).
- Every one of the 742 linked files starts inside its spawn's window: spawn `ts` <= file `first_ts` <= result `end_ts` (742 of 742).
- Simulation with every meta removed: pairing each file (in first_ts order) with the EARLIEST unpaired spawn of the same session whose window holds it: 742 of 742 right (picking the latest instead: 157 wrong).
- The fallback run on the 23 real unlinked files: 0 pairings. The 12 spawns with no file (all error results) all stay counted. So the figures today do not move.

Link (fallback order):
1. `sub_meta.tool_use_id` = spawn id (as today).
2. Only for a sub file with no `sub_meta.tool_use_id` (meta missing, unreadable, or no toolUseId): take the files in (first_ts, run_id) order. Pair each one with the earliest spawn (ts, run_id, id) that is not yet linked and that was called in a file of the same `session_id`, with `ts <= first_ts <= end_ts` (timestamps normalised). One-to-one.
3. No pair: the spawn stays a "spawn with no run file" (as today).
Not chosen: the parent's `toolUseResult.agentId` -> `files.agent_id`. It is exact, but it needs a parser.py change and a new tool_calls column (a schema change; parser.py is out of scope). It also misses every error result. The window link needs no schema change.

compare.py (no schema change, not blocking):
- `_Ctx.spawns`: add the step-2 spawn ids to `linked` before `pending` is built. Compute the pairing once per `_Ctx`, and keep `fb_role = {sub run_id: first copy's subagent_type}`.
- `_ticket` roles (CON-003: the role from the meta, else the spawn's subagent_type): for a sub run with no `sub_meta.role`, use `fb_role` when it is set. store.py keeps "general-purpose" for that run, because its spawn is found only through the meta.
- failed: a paired spawn is not in spawns, so the run file decides (run_failed, CON-015). An error result alone does not fail it.
- Prototype checked in a deleted /tmp copy. The 5 cases below pass. test_compare, test_compare_cli/page/format, test_server and test_store_and_flags: 326 passed. Before the fix the cases give (2,0,0), (2,1,0) and (3,1,1).

Test fixture (test_compare.py; `# rule: CON-014` with CON-015 and CON-016 cases; helpers W, usage, scan, data):
```python
def _meta(sub):
    return sub.path.with_name(sub.path.stem + ".meta.json")

@pytest.mark.parametrize("how", ["removed", "unreadable"])
@pytest.mark.parametrize("err", [False, True])          # True = the error-result variant
def test_spawn_with_run_file_and_no_meta_counts_once(env, how, err):
    w = W(env)
    w.main("S1", "ABC-1", w.asst(5, usage(10, 0)))
    sub = w.sub("S1", "ABC-1", [w.prompt(15, "[ABC-1] build", "S1", agent="AG1"), (20, usage(1000, 0))],
                agent="AG1", spawn_n=10, res_n=40, err=err)
    w.flush()
    _meta(sub).unlink() if how == "removed" else _meta(sub).write_text("{")
    d = data(scan(), "ABC-1")
    assert (d["runs"]["total"], d["runs"]["failed"], d["runs"]["repeat_rounds"]) == (1, 0, 0)

def test_unlinked_file_does_not_take_a_denied_spawn(env):   # guard: window and role
    w = W(env)
    w.main("S1", "ABC-1", w.asst(5, usage(10, 0)))
    w.sub("S1", "ABC-1", file=False, err=True, spawn_n=10, res_n=11)            # denied builder, window 10..11
    sub = w.sub("S1", "ABC-1", [w.prompt(15, "[ABC-1] build", "S1", agent="AG1"), (20, usage(1000, 0))],
                agent="AG1", spawn_n=12, res_n=40)
    w.flush()
    _meta(sub).unlink()
    d = data(scan(), "ABC-1")
    assert (d["runs"]["total"], d["runs"]["failed"], d["runs"]["repeat_rounds"]) == (2, 1, 1)
```
The sub file's own `[ABC-1]` prompt is needed. Without it a run with no meta has no key, the run is not counted, and the old code passes by accident (it gives 1 for the wrong reason).

For the business analyst (no rule edit by the system analyst): the meaning stays the same. Propose one notes line on CON-014: "Agent decision (EXP1-R22C, system analyst, 2026-11-05, review 3 finding 1): a spawn has a run file when the file's meta names it, or, when the meta is missing, unreadable or has no toolUseId, when an unpaired sub-agent file of the same session starts between the spawn call and its result (earliest spawn first); reason: CON-014 counts a spawn with no run file only, and the meta is not the only evidence of the file; log count 742 of 742." Also propose a matching line on CON-003 (role from the paired spawn's subagent_type). This is an Agent decision entry because it changes counts (only when a meta is missing).

Build decisions B5-D1, B5-D2 (system analyst, 2026-11-05; build-decisions.md "Builder B4/B5"):
- B5-D1 consistent: the window ends at the result record (end_ts); the earliest copy with one is the same call. A spawn with no result time has no window, so it is never paired; it has no result, so it is not counted either (CON-014, answers 31, 33, 35). No Agent decision.
- B5-D2 consistent: CON-003 / Q-053 "role from the meta, else the paired spawn's subagent_type". No Agent decision.
- Code check (compare.py `_Ctx._pair_unlinked`, `_ticket`): only files with no sub_meta.tool_use_id; files by (first_ts, run_id); spawns by (ts, run_id, id), meta-linked excluded; same session_id of the spawn's first copy; normalised `ts <= first_ts <= end_ts`; one-to-one (linked set, break). Matches the design. Order sorts the raw log timestamps (same Z format, finer than the normalised seconds); not a change.

## Scan in progress (system analyst, 2026-11-05; CON-010 v3, answer 47, Q-055; hostile HV-1, case HV-P20)
Main goal: the page knows, inside its own read snapshot, that a scan by any process (the server's first index, a later rescan, a CLI refresh) has started and not finished, and then answers 503.

Design: a scan marker in the existing `meta` table (key/value; no schema change, no `user_version` change).
- At the very start of `Store.ingest` (first statement under `self.lock`, before `refresh_claims` and any raw-table write): `INSERT OR REPLACE INTO meta VALUES('scan:<os.getpid()>', <UTC ISO start time>)`, then `commit()`. One row per process (one ingest per process at a time: `self.lock`).
- At the end, in the same transaction as the final `rebuild()` (before the existing last `self.db.commit()`): `DELETE FROM meta WHERE k='scan:<own pid>'`, and delete every other `scan:<pid>` row whose pid is not alive (`os.kill(pid, 0)` raises `ProcessLookupError`; `PermissionError` = alive; a key that does not parse = dead).
- Why it is reliable: SQLite WAL gives each read transaction one snapshot. The marker is committed before the first raw row of a scan (the 20-file commits) and removed in the same commit as the rebuilt `runs`. So a snapshot that has no marker sees either the state before the scan or the complete state after it; a snapshot that has a marker answers 503. No time window, no generation compare needed.
- Crash or error: a killed CLI (or a scan that raised; `_scan_safely` keeps its row) leaves its row; the index then really holds mixed rows, so 503 is right. The row is cleared at the end of the next successful scan of any process (dead pid) - the console's 30 s loop does this; a scan that raised in the server clears its own row at its next successful scan. Not cleared in `Store.__init__` on purpose: before that scan, the data is still mixed. No timeout (a long first index must not be cut short). Residual risk: a reused pid of a dead CLI keeps 503 until that process ends and the next scan finishes (rare, safe side).
- Not chosen: a lock/marker file next to the index (not in the read snapshot, so a race between the file check and the reads; needs its own cleanup); a generation counter compared at start and end of the read (the snapshot never sees a change, so it cannot detect a scan in progress - only the marker row does); `progress["state"]` alone (only the server's own scans).

Code changes (builder):
- console/agent_console/store.py `Store.ingest`: the marker write and commit at the start; the deletes before the last commit (one small helper, e.g. `_clear_scan_markers(db)` with `_pid_alive(pid)`). Nothing else in store.py changes; `index_check` reads only its four named keys, extra `meta` rows are ignored.
- console/agent_console/server.py `compare_view`: after the 422 check, `db.execute("BEGIN")` first, then in that snapshot the 503 check: `st.progress.get("initial")` or `SELECT 1 FROM meta WHERE k LIKE 'scan:%' LIMIT 1` or (`st.progress.get("scans", 0) == 0` and `runs` empty) -> 503; then `unknown_keys` (404) and `compare` (200) in the same snapshot. Order 422 -> 503 -> 404 -> 200 unchanged. The page still only reads.
- console/agent_console/compare_page.py: `BUILDING` -> `UPDATING = "The console is updating its index. Reload this page later."`; `building_page()` returns it (name may stay; docstring "any scan").
- console/agent_console/compare_cli.py: no change (it waits for its own scan, CON-011; its scan writes and clears its own marker).
- Existing pages (CON-032): no change. No existing endpoint reads `meta` rows other than tz/key_patterns/home/repo_root; `/api/status` still shows `progress`.

Tests (console/tests/test_compare_page.py; `BUILDING` constant -> the v3 text in every existing 503 test, e.g. test_dt_010_02/03, test_dt_027_14, test_ep_033_07):
- test_hv_p20_a_later_scan_answers_only_503_or_the_settled_200 (CON-010 v3, CON-027): index with EXP1-AAA, ingest; add logs for EXP1-Y5 (main session with Agent spawns and sub-agent files, > 40 files so several 20-file commits happen); wrap `Store._ingest_file` so that after each file it GETs `/compare?a=EXP1-AAA&b=EXP1-Y5` through the TestClient; run `store.ingest()`. Every in-scan answer is 503 with the v3 text (no key, no `<table`); never 404, never 200. After the scan: 200 with the settled figures (equal to a fresh Store's ingest of the same logs).
- test_dt_010_06_a_scan_by_another_process_answers_503: a second `Store` on the same home (the CLI's path) runs ingest with the same hook calling the page of the first app (whose own `progress` is idle): 503 during, 200 after.
- test_dt_010_07_a_marker_of_a_dead_process: insert `meta('scan:<pid of a finished subprocess>')` -> 503; the server's next `ingest()` removes it -> 200 (or 404 for an unknown key).
- test_dt_010_08_a_marker_of_a_live_process_survives: `scan:<pid of a running sleep subprocess>` stays after the server's ingest -> still 503; kill the subprocess, ingest again -> 200.
- test_dt_010_09_a_failed_scan_keeps_503: `_ingest_file` raises on file N > 20 inside `rescan(wait=True)` -> 503 (not mixed figures, not 404); the next successful ingest -> 200.
- test_store_and_flags.py: after `ingest()` no `scan:%` row is left; `index_check` on an index with a `scan:` row gives ([], []).
- Unchanged and still green: test_ep_010_06 (the page never writes), test_dt_010_04 (old index, no marker, before the first scan -> 200), test_dt_010_05.

For the business analyst (proposed Agent decision, not blocking): a scan that ends in an error, or a CLI that is killed mid-scan, leaves the index with mixed rows; the page answers 503 until the next scan finishes (the console's 30 s loop). Reason: narrowest reading of CON-010 v3 "never mixed figures, never a false unknown key". Observation (no rule change): the CLI does not check other processes' markers; it compares right after its own scan, as CON-011 says.
BLOCKING: no (no schema change, no change to existing pages).

Hand-off (lead QA, 2026-11-05): NOT READY - verifier PASS (verify.md, 17:52) and step-6 feature test (344, 17:48) predate the final product changes (server.py/compare_page.py/compare_format.py 18:06, compare_cli.py/store.py 18:29, compare.py 18:31; SEC-1..4, HV-1, HV-2, NEW-2, NEW-3); route step 7 needs the verifier PASS on the final head and the verifier runs last; hostile re-check 2, security round 2, review 8 PASS hold on the final product code; full suites green (console 798, tools+kit 49, ruff clean, parser.py unchanged); Ready for QA holds (32 rules tests: filled, 0 open questions). To clear: after the docstring edit in test_compare_cli.py lands, re-run test-runner on the 7 ticket test files and the verifier on the final tree, then READY FOR THE TRAIN.

Hand-off (lead QA, 2026-11-05): READY FOR THE TRAIN - clears the earlier NOT READY. Step-6 feature test on the final version: 390 passed, 0 failed, 7 ticket test files (step6-result-final.md, 19:00). Verifier PASS on the final version, run last (verify-final.md, 19:07). Hostile re-check 2 PASS (hostile.md, 0 open bugs), security round 2 PASS (security.md, nothing above Low), review 8 PASS (review8.md, BLOCKER/HIGH/MEDIUM 0). No product file changed after these runs: last product write compare.py 18:31; last test write test_compare_cli.py 18:53 (the review-8 LOW docstring); nothing in console/ is newer than verify-final.md; git status 18 entries, unchanged. Environment check rests on the 17:46 PASS (answer 51; two later environment-checker runs returned "placeholder", no verdict). Ready for QA holds (0 open questions). Accepted known limits, to the backlog: NEW-1, one malformed log line keeps /compare on 503 (answer 48); review 7 items 5 and 6 and security NEW-5, unbounded copy of a symlinked or device -wal in index_check (answer 49). Backlog, minor: verifier observation, a difference made by float subtraction can lose a sub-cent tie (0.026 - 0.001 -> $0.02, not $0.03; answer 32). Status not moved: gate tracker not declared in PROJECT.md.
