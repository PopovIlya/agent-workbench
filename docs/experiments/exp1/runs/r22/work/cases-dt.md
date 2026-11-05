Lead QA sign-off 2026-11-05: test design APPROVED (EXP1-R22C; re-check of EP-018-01, EP-018-02, EP-018-04, EP-019-01 passed; design approval 1 notes stay open for the automation engineer).

# EXP1-R22C · cases, technique DECISION TABLE (test designer DT, update pass 2026-11-05)

Status of every case: draft. 47 cases, one per DT coverage item of qa.md (none added, none dropped). Base 0891a04, branch exp1/r22.
Gates: `test_case_files` not declared in PROJECT.md: cases live here (work_dir/cases-dt.md). `timing_check`: not declared, skipped. `test_strategy`: none.
Rule versions built to (console.md): CON-010 v2, CON-011 v5, CON-014 v7, CON-015 v8, CON-022 v11, CON-024 v2, CON-026 v4, CON-027 v6, CON-034 v4 (CON-018 v2 and CON-012 note: no DT item, see Questions).
Interfaces: change.md "Interfaces for tests" (B1-B8) = "IF" below.
Tier proposal (no strategy): all cases are selective (touched files test_compare*.py); the CON-011 refusal cases (DT-011-*) and CON-010/027 precedence cases are also in the smoke set of this ticket (risk high / shared index).
Confirmation (prove-it-first): each case must fail on the base commit (module/route/subcommand absent) and, for the guard cases, would fail on a builder bug that writes before checking. Cases are not edited to pass.

## Shared recipes (referenced by the cases; all use the `env` fixture, console/tests/conftest.py)
- ENV: `env` fixture (tmp AGENT_CONSOLE_HOME = H, `env.root` = log root, REPO, NO_FETCH=1, TZ Europe/Madrid). Never ~/.agent-console, never ~/.claude. Fixtures in console/tests/fixtures read-only. PRICING (IF B6): a test that needs a priced model first rewrites `env.tmp/"pricing.yaml"` with the B6 text (sonnet-5-5 priced; any other model id unpriced), before `Pricing.load`. Default `env` pricing is `models: {}` (all unpriced).
- KEYS: KA = `EXP1-AAA`, KB = `EXP1-BBB`, KC = `EXP1-CCC`, KU = `EXP1-NOPE` (no log carries it).
- KEYED(K, S) (IF B5): main file `env.root/PROJECT/"<S>.jsonl"` (PROJECT from conftest), first record `user_prompt("[K] start", t=0, session=S)` (own key = effective key = K, no sub-agents), then `assistant("m1", u=usage(...), blocks=[text "done"], t=10, session=S)`.
- SPAWN(S, i, tid, key, role): in the main file of S: `assistant(f"m{i}", t=1+i, session=S, blocks=[tool_use(tid, "Agent", subagent_type=role, description="[key] build", prompt="p")])`, then `tool_result(tid, t=100+i, session=S)`; for a sub run also `add_sub(env.root, S, f"ag{i}", role, [assistant(f"s{i}", agent=f"ag{i}", session=S, t=10+i)], tid)`. Message ids, tool ids, agent ids unique (IF B5). `tool_result(tid, err=True)` text is set by `rec["message"]["content"][0]["content"] = "<text>"`.
- NOMAIN(KA) (IF B5, own key vs effective key): main file with own key KC (`[KC] start`), 3 SPAWN children keyed KB and 1 keyed KA (share 0.75 < `config.CHILD_SHARE` 0.8, so the main's effective key stays KC). Setup assertion: `ticket(db, pr, KA)["main_sessions"] == 0` and `unknown_keys(db, KA, KA) == []`. (For a count-spawn-only variant the KA child has no add_sub and an error tool_result.)
- INDEX: `store = Store(); store.rescan(wait=True)` (or `store.ingest()`), page tests use `Store` + `TestClient(server.create_app(store=store, pricing=Pricing.load(config.pricing_path()), port=8790), base_url="http://127.0.0.1:8790")` (IF B1).
- DATA(K): `db = store.reader(); try: ticket(db, pr, K) ...; finally: db.close()` (`compare.ticket`), or `compare.compare(db, pr, a, b)` for the diff tree (`["diff"]`). `compare` does not check unknown keys; `compare.unknown_keys(db, a, b) -> list[str]` does.
- CLI(args, env_changes): in process, `compare_cli.main(args) -> int` with `capsys`; env changes by `monkeypatch.setenv(...)` (AGENT_CONSOLE_TZ, AGENT_CONSOLE_KEY_PATTERNS, AGENT_CONSOLE_HOME, AGENT_CONSOLE_REPO; never `HOME`). Oracle: return value, `capsys.readouterr()` out and err. The `__main__` route (IF B1) is not needed here; if a subprocess is wanted: `[sys.executable, "-m", "agent_console", "compare", ...]`, `cwd` = console folder, `env=os.environ.copy()` after the fixture (never `env={}`). "HOME=B" means AGENT_CONSOLE_HOME=B.
- BASELINE-INDEX: KEYED(KA) + SPAWN sub run + KEYED(KB) in `env.root`; CLI(["EXP1-AAA","EXP1-BBB"]) once -> returns 0, builds `H/index.sqlite` with `meta` rows `tz=Europe/Madrid`, `key_patterns`, `home`, `repo_root`, `user_version=SCHEMA_VERSION`.
- FILES-UNCHANGED (refusal evidence): before and after the CLI call compare sha256 of `H/index.sqlite` and `H/index.sqlite-wal` (if present), `PRAGMA user_version`, all `meta` rows (read through a separate read-only sqlite3 connection); index.sqlite-shm left out. Also sha256 of every log file under `env.root` unchanged.
- REFUSAL-DIFFER (exact, one stderr line + newline, IF B3/"CLI index"): `compare: refused: the index at <db_path> was built with another <names>; run compare with the console's settings (nothing written)`. `<db_path>` = `<H>/index.sqlite`.
- REFUSAL-MISSING (exact): `compare: refused: the index at <db_path> does not record its <names>; start the console once with this checkout, then retry (nothing written)`.
- names order fixed: `schema version, time zone, key patterns, console home, checkout`.
- USAGE-HEAD (IF B3, exact first stderr line): `usage: python -m agent_console compare [-h] [--json] KEY_A KEY_B`. Second line is `python -m agent_console compare: error: <detail>`. Stdout `""`, return value 2.
- PAGE(path): `client.get(path)` as in test_server.py (Host `127.0.0.1:8790`); oracle: `status_code`, `content-type == "text/html; charset=utf-8"`, body, the five security headers present. ERR(body) = text of the single `<p class="error">...</p>` (IF B2); figure/digit/`$`/`min` checks are made on ERR only (the document has `charset=utf-8`).
- ROW(body, id) = the row `<tr data-row="<id>">` (IF B2); `td.a` / `td.b` / `td.d` cells; diff cell `<span class="diff">…</span> (<span class="ratio">…</span>)`.
- Formatter (IF B1): `compare_format.ratio(v)` etc.; a str label is returned unchanged.
- tmp pricing / `at(n)` helper (IF B7) is defined locally in a test module when a gap passes 3600 s; the DT cases here use n < 3600 and `ts(n)`.

---
## CON-010 v2 · test_compare_page.py

### DT-010-02 · coverage CI-010-02 · # rule: CON-010
- Table: initial=T, scans=any, runs=any, key unknown -> 503 (initial wins).
- Test file: console/tests/test_compare_page.py
- Pre: ENV; INDEX from KEYED(KA, S1); `store.progress["initial"] = True`; spies `monkeypatch.setattr(store, "rescan", spy)` and `store.ingest`.
- Steps: PAGE(`/compare?a=EXP1-NOPE&b=EXP1-AAA`).
- Expected: status 503; `text/html; charset=utf-8`; the `<p class="error">` is exactly `The console is building its first index. Reload this page later.`; the whole body (title, heading included) does not contain `EXP1-NOPE` or `EXP1-AAA`; ERR has no digit, no `$`, no `min`, no "unknown" (case-insensitive); no `<table`; security headers present; spies not called.

### DT-010-03 · coverage CI-010-03 · # rule: CON-010
- Table: initial=F, scans==0, runs empty -> 503.
- Pre: ENV; fresh `Store()` on an empty home, no ingest: `"initial"` absent from `progress`, `progress["scans"] == 0`, `runs` table empty (assert in setup).
- Steps: PAGE(`/compare?a=EXP1-AAA&b=EXP1-BBB`).
- Expected: 503; HTML; the body is identical to the DT-010-02 body (same message text); no key in the body; no `<table`; spies (rescan, ingest) not called.

### DT-010-04 · coverage CI-010-04 · # rule: CON-010
- Table: scans==0, runs not empty (index left from an earlier start), initial=F -> not 503.
- Pre: ENV; KEYED(KA, S1) and KEYED(KB, S2); a first `Store()` runs `ingest()`, closed; a new `Store()` on the same home, no ingest; `progress["scans"] == 0`, no `"initial"` key; `SELECT count(*) FROM runs` > 0 (assert in setup).
- Steps: PAGE(`/compare?a=EXP1-AAA&b=EXP1-BBB`).
- Expected: status 200 (not 503); body has `<table class="compare">`, `<th scope="col" class="a">EXP1-AAA</th>` and `<th scope="col" class="b">EXP1-BBB</th>`; `ROW("main_sessions")` td.a and td.b are `1`; spies not called.

### DT-010-05 · coverage CI-010-05 · # rule: CON-010
- Table: scans>=1, initial=F, runs empty, unknown key -> 404 (not 503).
- Pre: ENV; empty home; `store.ingest()` once (ends with `initial=False`, `scans == 1`, runs still empty; assert).
- Steps: PAGE(`/compare?a=EXP1-NOPE&b=EXP1-NOPE2`).
- Expected: status 404 (not 503); the `<p class="error">` is exactly `Unknown ticket keys: <code>EXP1-NOPE</code>, <code>EXP1-NOPE2</code>.`; security headers present; no `<table`.

---
## CON-011 v5 · test_compare_cli.py (all: BASELINE-INDEX first, then the change in "Pre", then CLI(["EXP1-AAA","EXP1-BBB"]) with FILES-UNCHANGED)

### DT-011-05 · coverage CI-011-05 · # rule: CON-011
- Table: tz differs, others same -> refuse, exit 2, names `time zone`.
- Pre: BASELINE-INDEX built with TZ Europe/Madrid; `monkeypatch.setenv("AGENT_CONSOLE_TZ", "UTC")`.
- Expected: return 2; stdout `""`; stderr exactly REFUSAL-DIFFER with `<names>` = `time zone`; FILES-UNCHANGED holds.

### DT-011-06 · coverage CI-011-06 · # rule: CON-011
- Table: key patterns differ -> refuse, `key patterns`.
- Pre: `AGENT_CONSOLE_KEY_PATTERNS=<one extra pattern not in the baseline run>`.
- Expected: return 2; stdout `""`; stderr exactly REFUSAL-DIFFER, `<names>` = `key patterns`; FILES-UNCHANGED.

### DT-011-07 · coverage CI-011-07 · # rule: CON-011
- Table: console home differs (index copied from home A) -> refuse, `console home`.
- Pre: BASELINE-INDEX in home A (= H); second tmp folder B; copy `A/index.sqlite` (and -wal if present) to `B/index.sqlite`; `AGENT_CONSOLE_HOME=B`.
- Expected: return 2; stdout `""`; stderr exactly REFUSAL-DIFFER with `<db_path>` = `<B>/index.sqlite`, `<names>` = `console home`; FILES-UNCHANGED for B's files and A's index (sha256 of `A/index.sqlite` equal).

### DT-011-08 · coverage CI-011-08 · # rule: CON-011
- Table: checkout differs -> refuse, `checkout`.
- Pre: `AGENT_CONSOLE_REPO=<another tmp dir>`.
- Expected: return 2; stdout `""`; stderr exactly REFUSAL-DIFFER, `<names>` = `checkout`; FILES-UNCHANGED.

### DT-011-09 · coverage CI-011-09 · # rule: CON-011
- Table: user_version != SCHEMA_VERSION -> refuse, `schema version`.
- Pre: after BASELINE-INDEX, set `PRAGMA user_version = SCHEMA_VERSION - 1` through a separate sqlite3 connection (setup), close it, then take the FILES-UNCHANGED "before" snapshot.
- Expected: return 2; stdout `""`; stderr exactly REFUSAL-DIFFER, `<names>` = `schema version`; FILES-UNCHANGED incl. user_version still SCHEMA_VERSION - 1, `meta` rows `tz`, `key_patterns` not reset, `runs` row count unchanged.

### DT-011-10 · coverage CI-011-10 · # rule: CON-011
- Table: `home` and `repo_root` rows missing, nothing differs -> refuse "does not record".
- Pre: delete meta rows `home` and `repo_root` by sqlite3 (setup), snapshot.
- Expected: return 2; stdout `""`; stderr exactly REFUSAL-MISSING, `<names>` = `console home, checkout`; FILES-UNCHANGED (rows still absent).

### DT-011-11 · coverage CI-011-11 · # rule: CON-011
- Table: one differs + one missing -> "built with another" line naming both, fixed order.
- Pre: delete meta row `home`; `AGENT_CONSOLE_TZ=UTC`.
- Expected: return 2; stdout `""`; stderr exactly REFUSAL-DIFFER (the "built with another" form, not "does not record"), `<names>` = `time zone, console home`; FILES-UNCHANGED.

### DT-011-12 · coverage CI-011-12 · # rule: CON-011
- Table: two differ -> both, fixed order.
- Pre: `AGENT_CONSOLE_TZ=UTC` and `AGENT_CONSOLE_REPO=<another tmp dir>`.
- Expected: return 2; stdout `""`; stderr exactly REFUSAL-DIFFER, `<names>` = `time zone, checkout`; FILES-UNCHANGED.

### DT-011-13 · coverage CI-011-13 · # rule: CON-011
- Table: all five match -> refresh runs, no refusal, exit 0.
- Pre: BASELINE-INDEX; then write a second sub run (SPAWN child for KA, new tid and agent id) into `env.root` after the first build. Same env both calls.
- Steps: CLI(["EXP1-AAA","EXP1-BBB","--json"]); `json.loads(stdout)`.
- Expected: return 0; stderr `""`; JSON `a.runs.total` is one higher than in the baseline call (the baseline call is a `--json` call, made before the extra run: 1 -> 2); `meta` rows `home` and `repo_root` equal `str(H.resolve())` and `str(REPO.resolve())`; log files' sha256 unchanged.

---
## CON-014 v7 · test_compare.py (spawn matrix; INDEX with `store.rescan(wait=True)`; DATA(KA) = `ticket(db, pr, "EXP1-AAA")`)

Common: KEYED(KA, S1) with a SPAWN `T1` (`subagent_type="reviewer"`, description `[KA] build`, key source spawn_lead / parent). Same-timestamp key evidence (Q-040) is not a DT coverage item; no case added.

### DT-014-01 · coverage CI-014-01 · # rule: CON-014
- Table: run file = yes (any result) -> counted once as a run.
- Pre: SPAWN with add_sub linked to `T1`, `tool_result("T1", err=False)` present.
- Expected: `runs.total == 1` (not 2); `runs.failed == 0` for a sub that ends with a text reply.

### DT-014-02 · coverage CI-014-02 · # rule: CON-014
- Table: run file = no, result = error, key = yes -> counted.
- Pre: no add_sub for `T1`; `tool_result("T1", err=True)`.
- Expected: `runs.total == 1`; `runs.failed == 1`; `unknown_keys(db, KA, KA) == []`.

### DT-014-03 · coverage CI-014-03 · # rule: CON-014
- Table: run file = no, result = non-error, key = yes -> counted, not failed.
- Pre: no add_sub; `tool_result("T1", err=False)`.
- Expected: `runs.total == 1`; `runs.failed == 0`.

### DT-014-04 · coverage CI-014-04 · # rule: CON-014
- Table: run file = no, no tool_result -> not counted.
- Pre: no add_sub; no `tool_result` for `T1` (session ends first).
- Expected: `runs.total == 0`; `runs.failed == 0`; `runs.repeat_rounds == 0`; KA still known (`unknown_keys(db, KA, KA) == []`), `main_sessions == 1`.

### DT-014-05 · coverage CI-014-05 · # rule: CON-014
- Table: run file = no, result = error, key = none -> counted nowhere.
- Pre: KA has one sub run (SPAWN with add_sub) in KEYED(KA, S1); a second main session S2 carries no key (cwd outside key pattern; a first prompt, description and prompt with no key) with an `Agent` spawn `T9` (description and prompt with no key), no add_sub, `tool_result("T9", err=True)`.
- Expected: DATA(KA): `runs.total == 1` (the keyless spawn adds nothing); `runs.failed == 0`; DATA(KB) of an unrelated key stays zeros.

---
## CON-015 v8 · test_compare.py (sub run linked to spawn `T1` of KEYED(KA); expected from DATA(KA) `runs.total`, `runs.failed`)

### DT-015-01 · coverage CI-015-01 · # rule: CON-015
- Table: last turn = assistant isApiErrorMessage -> failed.
- Pre: sub records: prompt, then `assistant("s1", agent=..., session="S1", isApiErrorMessage=True, error="x", apiErrorStatus=403, t=20)` as the last record.
- Expected: `runs.total == 1`, `runs.failed == 1`.

### DT-015-02 · coverage CI-015-02 · # rule: CON-015
- Table: last turn = system subtype api_error -> failed.
- Pre: sub records end with `api_error(t=20)`.
- Expected: `runs.total == 1`, `runs.failed == 1`.

### DT-015-06 · coverage CI-015-06 · # rule: CON-015
- Table: denial, then a final text reply -> not failed.
- Pre: sub: `tool_use("U1","Bash",...)` in an assistant record, `tool_result("U1", err=True)` with content text set to `Permission to use Bash has been denied`, then `assistant("s2", blocks=[text "done"], t=30)` last.
- Expected: `runs.total == 1`, `runs.failed == 0`.

### DT-015-07 · coverage CI-015-07 · # rule: CON-015
- Table: API error, then a final text reply -> not failed.
- Pre: sub: `api_error(t=20)`, then `assistant("s2", blocks=[text "done"], t=30)` last.
- Expected: `runs.total == 1`, `runs.failed == 0`.

### DT-015-13 · coverage CI-015-13 · # rule: CON-015
- Table: spawn error result, no run file -> failed.
- Pre: no add_sub; `tool_result("T1", err=True)` with content text `Agent type 'x' not found`.
- Expected: `runs.total == 1`, `runs.failed == 1`.

### DT-015-14 · coverage CI-015-14 · # rule: CON-015
- Table: spawn non-error result, no run file -> run, not failed.
- Pre: no add_sub; `tool_result("T1", err=False)`.
- Expected: `runs.total == 1`, `runs.failed == 0`.

### DT-015-15 · coverage CI-015-15 · # rule: CON-015
- Table: spawn without result, no run file -> not counted, not failed.
- Pre: no add_sub, no tool_result for `T1`.
- Expected: `runs.total == 0`, `runs.failed == 0`.

---
## CON-022 v11 · test_compare.py

### DT-022-27 · coverage CI-022-27 · # rule: CON-022
- Table: same stop key (shared uuid), gap ends 400 s in file 1 and 450 s in file 2 -> earliest gap end counts, once.
- Pre: PRICING not needed. Two main session files under `env.root/PROJECT/`, `S1.jsonl` and `S2.jsonl`, both KEYED(KA). Set explicit uuids (the helper's `user_prompt` uuid contains the session, so copies are made by `rec["uuid"] = ...`, `rec["origin"] = {"kind": "human"}` on typed messages; stop records `rec["message"]["stop_reason"] = "end_turn"`). File 1 (`S1`): typed message at `ts(0)` (uuid u0), `assistant("m1", rid="r1", t=100)` end_turn (uuid u1), typed message at `ts(400)` (uuid u2). File 2 (`S2`, resumed): copies of u0 and u1 (same uuids, session S2), then typed message at `ts(450)` (uuid u3). All typed messages origin.kind "human". Times n < 3600, so `ts(n)` is enough (IF B7: `at(n)` otherwise).
- Steps: INDEX; DATA(KA)["time_s"].
- Expected: `time_s.wait == 300` (not 350, not 650); `main_sessions == 2`; `time_s.wait_over_2h == 0`.

---
## CON-024 v2 · test_compare.py (`cost_share` in DATA(KA); PRICING first so the model is priced; setup asserts `cost_usd.total > 0` where a cost is expected)

### DT-024-01 · coverage CI-024-01 · # rule: CON-024
- Table: main present, main cost > 0, sub cost > 0 -> number.
- Pre: KEYED(KA, S1) with one message `usage(out=1000)`; one SPAWN sub run of KA with one message of the same model `claude-sonnet-5-5`, `usage(out=1000)` (unique ids).
- Expected: `cost_share == 1.0` (a float, main cost / sub cost); `compare_format.ratio(1.0) == "1.00"`; page `ROW("cost_share")` td.a text `1.00`.

### DT-024-02 · coverage CI-024-02 · # rule: CON-024
- Table: main present, sub cost 0 -> "no sub-agents".
- Pre: KEYED(KA, S1) with a priced message; no sub run.
- Expected: `cost_share == "no sub-agents"` (string; not 0, not inf, not None); `ratio("no sub-agents") == "no sub-agents"`.

### DT-024-03 · coverage CI-024-03 · # rule: CON-024
- Table: no main, sub cost > 0 -> "no main session".
- Pre: NOMAIN(KA) with the KA child as a sub run (add_sub) with a priced message (`usage(out=1000)`); setup asserts `main_sessions == 0`.
- Expected: `cost_share == "no main session"`; `cost_usd.total > 0`.

### DT-024-04 · coverage CI-024-04 · # rule: CON-024
- Table: no main, sub cost 0 -> "no main session" (wins over "no sub-agents").
- Pre: NOMAIN(KA) count-spawn-only variant: the KA child has no add_sub and `tool_result(tid, err=True)`; no priced message tied to KA; setup asserts `main_sessions == 0`, `runs.total == 1`.
- Expected: `cost_share == "no main session"` (not "no sub-agents"); `cost_usd.total == 0`.

---
## CON-026 v4 · test_compare.py (`compare(db, pr, KA, KB)["diff"]`; PRICING set)

### DT-026-01 · coverage CI-026-01 · # rule: CON-026
- Table: both numbers, a > 0 -> diff = b - a, ratio = b / a.
- Pre: KEYED(KA, S1) one message `usage(inp=100, out=1000)`; KEYED(KB, S2) one message `usage(inp=300, out=3000)`, same model.
- Expected: `diff.tokens.total.input == {"diff": 200, "ratio": 3.0}`; `diff.tokens.total.output == {"diff": 2000, "ratio": 3.0}`; computed from raw values. JSON only (display rounding is CON-029).

### DT-026-02 · coverage CI-026-02 · # rule: CON-026
- Table: a = 0 (real value), b > 0 -> diff shown, ratio "n/a".
- Pre: KA: `usage(cr=0)`; KB: `usage(cr=500)`.
- Expected: `diff.tokens.total.cache_read == {"diff": 500, "ratio": "n/a"}`; page `ROW("tokens.total.cache_read")` td.d is `<span class="diff">1k</span> (<span class="ratio">n/a</span>)` (`tokens(500) == "1k"`, `ROW`/format by IF B1-B2).

### DT-026-03 · coverage CI-026-03 · # rule: CON-026
- Table: a is a label ("no main session"), b a number -> diff n/a, ratio n/a.
- Pre: KA from NOMAIN(KA) (sub run, setup asserts `main_sessions == 0`); KB with KEYED(KB, S2).
- Expected: for each of `tokens.main.{input,output,cache_write,cache_read}`, `cost_usd.main`, `time_s.wait`, `time_s.wait_over_2h`, `cost_share`: `{"diff": "n/a", "ratio": "n/a"}` (8 leaves, IF B2); page td.d of those rows `n/a (n/a)` and td.a the text `no main session`.

### DT-026-04 · coverage CI-026-04 · # rule: CON-026
- Table: b is a label, a a number -> diff n/a, ratio n/a.
- Pre: as DT-026-03 with sides swapped (a = ticket with main, b = NOMAIN).
- Expected: same 8 leaves `{"diff": "n/a", "ratio": "n/a"}`; td.b shows `no main session`.

---
## CON-027 v6 · test_compare_page.py, test_compare_cli.py

### DT-027-13 · coverage CI-027-13 · # rule: CON-027, CON-034
- Table (page): a missing + first index running -> 422 (422 > 503).
- Pre: ENV; `store.progress["initial"] = True`.
- Steps: PAGE(`/compare?b=EXP1-AAA`).
- Expected: 422 (not 503); the `<p class="error">` is exactly `Missing parameter: <code>a</code>.`; not the 503 text.

### DT-027-14 · coverage CI-027-14 · # rule: CON-027, CON-010
- Table (page): both present, first index running, unknown key -> 503 (503 > 404).
- Pre: `store.progress["initial"] = True`; no log carries `EXP1-NOPE`.
- Steps: PAGE(`/compare?a=EXP1-NOPE&b=EXP1-AAA`).
- Expected: 503 (not 404); the `<p class="error">` is exactly `The console is building its first index. Reload this page later.`; body does not contain `EXP1-NOPE`.

### DT-027-15 · coverage CI-027-15 · # rule: CON-027, CON-011
- Table (CLI): guard refusal + unknown key -> refusal line, exit 2.
- Pre: BASELINE-INDEX; `AGENT_CONSOLE_TZ=UTC`.
- Steps: CLI(["EXP1-NOPE","EXP1-NOPE2"]).
- Expected: return 2; stdout `""`; stderr is exactly the REFUSAL-DIFFER line with `<names>` = `time zone` (not `compare: unknown ticket keys: EXP1-NOPE, EXP1-NOPE2`); FILES-UNCHANGED.

---
## CON-034 v4 · test_compare_page.py (01-05), test_compare_cli.py (07-11)

### DT-034-01 · coverage CI-034-01 · # rule: CON-034
- Table (page): a missing, b given -> 422 naming a.
- Pre: ENV with INDEX of KEYED(KB, S1).
- Steps: PAGE(`/compare?b=EXP1-BBB`).
- Expected: 422; `text/html; charset=utf-8`; body is HTML (not `{"detail": "Invalid request."}`); the `<p class="error">` is exactly `Missing parameter: <code>a</code>.`; `"<code>b</code>"` not in body; no `<form`, no `<a `, no swap or "compare with" text; security headers present.

### DT-034-02 · coverage CI-034-02 · # rule: CON-034
- Table: b missing, a given -> 422 naming b.
- Steps: PAGE(`/compare?a=EXP1-AAA`).
- Expected: 422; HTML; the `<p class="error">` is exactly `Missing parameter: <code>b</code>.`; `"<code>a</code>"` not in body.

### DT-034-03 · coverage CI-034-03 · # rule: CON-034
- Table: both missing -> 422 naming both.
- Steps: PAGE(`/compare`).
- Expected: 422; one `<p class="error">` exactly `Missing parameters: <code>a</code>, <code>b</code>.`.

### DT-034-04 · coverage CI-034-04 · # rule: CON-034
- Table: `a=` (empty) -> missing.
- Steps: PAGE(`/compare?a=&b=EXP1-BBB`).
- Expected: 422; the `<p class="error">` exactly `Missing parameter: <code>a</code>.`; no `<table`.

### DT-034-05 · coverage CI-034-05 · # rule: CON-034
- Table: `a=%20%20` (only spaces) -> missing.
- Steps: PAGE(`/compare?a=%20%20&b=EXP1-BBB`).
- Expected: 422 (not 404); the `<p class="error">` exactly `Missing parameter: <code>a</code>.`; no `<table`.

### DT-034-07 · coverage CI-034-07 · # rule: CON-034
- Table (CLI): no keys -> usage, exit 2.
- Pre: ENV, empty H (no index).
- Steps: CLI([]).
- Expected: return 2; stdout `""`; stderr exactly two lines: USAGE-HEAD, then `python -m agent_console compare: error: the following arguments are required: KEY_A, KEY_B`; `H/index.sqlite` does not exist afterwards (argparse runs before the guard and `Store()`); `server.main` spy (monkeypatched) not called.

### DT-034-08 · coverage CI-034-08 · # rule: CON-034
- Table: one key -> usage, exit 2.
- Steps: CLI(["EXP1-AAA"]).
- Expected: return 2; stdout `""`; stderr: USAGE-HEAD, then `python -m agent_console compare: error: the following arguments are required: KEY_B`; no `H/index.sqlite`.

### DT-034-09 · coverage CI-034-09 · # rule: CON-034
- Table: one key is `""` -> usage, exit 2.
- Steps: CLI(["EXP1-AAA", ""]).
- Expected: return 2; stdout `""`; stderr: USAGE-HEAD, then `python -m agent_console compare: error: empty key: KEY_B`; no `H/index.sqlite`.

### DT-034-10 · coverage CI-034-10 · # rule: CON-034
- Table: one key is `"  "` -> usage, exit 2.
- Steps: CLI(["EXP1-AAA", "  "]).
- Expected: return 2; stdout `""`; stderr: USAGE-HEAD, then `python -m agent_console compare: error: empty key: KEY_B`; no `H/index.sqlite`.

### DT-034-11 · coverage CI-034-11 · # rule: CON-034
- Table: three keys -> usage, exit 2.
- Pointer only: tested in EP-031-04 (cases-ep.md), which carries CI-034-11 and DT-034-11 in its trace and holds the one USAGE-HEAD expectation. No steps here.

---
## Questions (update pass; each marked)
1. Wording of the 503, 422 and 404 texts and the marker for "names a, not b": ANSWERED, IF B2 (exact `<p class="error">` texts; `<code>a</code>` marker). Cases now assert them literally.
2. Exact CLI usage text: ANSWERED, IF B3 (USAGE-HEAD and the second line by case).
3. How a key is attached to a main session; setups for "no main session": ANSWERED, IF B5 (first prompt `[K] start`; effective key vs own key with CHILD_SHARE 0.8). DT-024-03/04, DT-026-03/04 use NOMAIN (3 KB + 1 KA children, own key KC), which is my reading of B5's "3 KB + 1 KC -> own" result; the setup asserts `main_sessions == 0`, so a wrong reading shows at setup, not in the product. Not a blocking question.
4. Pricing of the default model: ANSWERED, IF B6 (tmp `pricing.yaml` with `sonnet-5-5`; other models unpriced).
5. In-process names, progress setting: ANSWERED, IF B1 (`compare.compare/ticket/unknown_keys`, `compare_cli.main`, `store.progress["initial"] = True`, fresh Store has scans 0 and no "initial").
6. New from the rules (Q-034..Q-040): CON-022 v11 same-gap-in-one-file (Q-034), the stop_reason marker (Q-036), isMeta user record (Q-037), CON-018 v2 unpriced model listed with 0 (Q-038) and CON-014 v7 same-timestamp key (Q-040) have no coverage item in the DT list of qa.md. Per the brief no item is added; DT-022-27 already uses the Q-036 marker. OPEN for the caller: should another technique (EP/BVA) or a DT item cover Q-034, Q-038, Q-040? Q-035 (gap start = stop record time) and Q-039 (no period edge) are settled without a new case.
7. CLI exit 1 (CON-011 v5, IF B4: `sqlite3.Error`, `DatabaseError` for a non-database file) has no DT item here; belongs to the EP case EP-011-20 (not mine). OPEN only as a pointer, no question for the analyst.
