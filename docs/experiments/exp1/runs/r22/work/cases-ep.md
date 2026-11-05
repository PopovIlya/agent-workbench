Lead QA sign-off 2026-11-05: test design APPROVED (EXP1-R22C; re-check of EP-018-01, EP-018-02, EP-018-04, EP-019-01 passed; design approval 1 notes stay open for the automation engineer).

# EXP1-R22C · draft test cases, technique EP (equivalence partitions)

Test designer EP, 2026-11-05. Head: 0891a04 (branch exp1/r22). Status of every case: draft. 136 cases = the 136 EP coverage items of qa.md, one case each.
Update pass 2 (same day): re-pointed to the current rule versions and the "Interfaces for tests" section of change.md (B1 to B8). Q-034..Q-040 applied.
Return round 1 (design-check1): real keys in EP-026; EP-029-16/-18, EP-011-17, EP-027, EP-032-02/-04, EP-033-04/-05, EP-010-01, EP-022-26 reworked; negatives split as EP-022-12b, -13b, -13c, -21b (same coverage items, so 140 case blocks for 136 items); EP-030-04 merged into EP-026-08 and EP-031-04 (page half) into EP-034-12 (with DT-034-11), each by citing all item ids.
Rule versions built to: CON-011 v5, CON-014 v7, CON-015 v8, CON-018 v2, CON-022 v11, CON-027 v6, CON-034 v4; others as in console.md (010 v2, 012 v1, 013 v1, 016 v5, 017 v2, 019 v1, 020 v2, 021 v4, 023 v1, 025 v1, 026 v4, 028 v1, 029 v7, 030 v1, 031 v2, 032 v3, 033 v1, 035 v1).
Gates: test_case_files not declared, so the cases live here. No product code is written; no test file is edited.

## Common setup (named once, used by every case)

All tests use the `env` fixture (tmp AGENT_CONSOLE_HOME, LOG_ROOT = `env.root`, REPO, NO_FETCH=1, TZ Europe/Madrid). Logs are written into `env.root` with the conftest helpers. `console/tests/fixtures` is read only. Never `~/.agent-console`, never `~/.claude`. Keys in test data are `ABC-n` (the default key pattern; `EXP1-R22C` does not match `\d{1,6}\b`).

- **PX** (tmp pricing, B6: the `env` fixture writes `models: {}` to `env.tmp/"pricing.yaml"`; a test rewrites that file before `Pricing.load(config.pricing_path())`, no conftest change; rates USD per 1M tokens):
  `regional_multiplier: 1.0` / `models:` `m-one: {input: 1.00, output: 2.00, cache_write_5m: 3.00, cache_write_1h: 4.00, cache_read: 0.50}`, `m-two: {input: 10.00, output: 20.00, cache_write_5m: 30.00, cache_write_1h: 40.00, cache_read: 5.00}` / `tier_defaults: {sonnet: m-one}`. Model id `zzz-unpriced` matches nothing and has no tier (unpriced). Every model in these cases is `m-one` unless the case says otherwise.
- **SCAN**: `st = Store(); st.ingest()` (or `st.rescan(wait=True, min_interval=0)` when a case needs the rescan path), as B1/test_server.py. **APP**: `TestClient(server.create_app(store=st, pricing=Pricing.load(config.pricing_path()), port=8790), base_url="http://127.0.0.1:8790")`. Progress (B1): `st.progress` is a plain dict read on each request; fresh Store on an empty home, no ingest: `scans == 0`, no `initial` key (503); `ingest()` ends with `initial=False`, `scans` + 1.
- **CLI(args)**: `subprocess.run([sys.executable, "-m", "agent_console", "compare", *args], cwd=<console folder>, env=os.environ.copy(), capture_output=True, text=True)` (copy taken after the `env` fixture set its variables, never `env={}`). Where a case says "in process" it calls `compare_cli.main(args)` (args = what follows `compare`) with capsys and asserts the returned int; `main` never calls `sys.exit` (argparse's SystemExit is caught, its code returned). Result = (returncode, stdout, stderr).
- **DATA(K)** = `db = st.reader()`; `compare.compare(db, pr, K, K)["a"]` with `pr = Pricing.load(config.pricing_path())`; `db.close()` in `finally`. For a pair: `compare.compare(db, pr, A, B)` gives `{"a","b","diff","version"}`; D = its `diff`. Other API: `compare.ticket(db, pr, key) -> T`, `compare.unknown_keys(db, a, b) -> list[str]` (a first, same key twice named once), `compare.to_json(tree)` (no trailing newline; the CLI prints it with `print`). JSON path `x.y` = key y inside x.
- **Formatter and page (B1, B2)**: `compare_format.rows(tree)` gives `Row(id, label, a, b, diff, ratio)` (all str) in the fixed row order; `tokens(1500) == "2k"`, `usd(2.675) == "$2.68"`, `minutes(30) == "1 min"`, `ratio(0.125) == "0.13"`. Page row selector: `tr[data-row="<id>"]` (id = JSON path, e.g. `runs.total`, `tokens.main.input`, `cost_usd.by_model.m-one`) with `td.a`, `td.b`, `td.d` (`<span class="diff">` and `<span class="ratio">`, shown as `1k (1.67)`). CLI text: header line, then one line per row, cells joined by ` | `; tests split a line on `|` and strip each part; one trailing newline.
- **CLI texts (B3, B4, CLI index)**, exact: usage (stderr, exit 2, stdout empty) is two lines `usage: python -m agent_console compare [-h] [--json] KEY_A KEY_B` and `python -m agent_console compare: error: <reason>`; reason `the following arguments are required: KEY_A, KEY_B` (none) or `... required: KEY_B` (one key), `unrecognized arguments: X-3` (three), `empty key: KEY_A` / `KEY_B` / `KEY_A, KEY_B`. Unknown key (exit 2, one line): `compare: unknown ticket key: KEY` or `compare: unknown ticket keys: KEY_A, KEY_B` (a first, keys as typed). Exit 1, one line: `compare: error: the index at <db_path> could not be opened or refreshed (<ClassName>)`, `<db_path>` = `str(env.home / "index.sqlite")`, ClassName = `type(e).__name__` or `st.progress["error"]`; the sqlite message text never appears.
- Record builders (conftest helpers plus thin local wrappers; ids unique per B5: message ids, tool_use ids, agent ids; two records with the same uuid are one record for CON-022): `MAIN(S, K)` = file `env.root/"PROJECT"/f"{S}.jsonl"` (B5) starting with `user_prompt(f"[{K}] go", t=0, session=S)` (the key comes from prompt_lead). `STOP(mid, t, S, usage)` = `assistant(mid, model="m-one", u=usage, t=t, session=S)` with `rec["message"]["stop_reason"] = "end_turn"`. `TYPED(text, t, S)` = `user_prompt(text, t, session=S)` (no origin field = typed in an old log). `SPAWN(S, tid, desc, t, role, prompt="p", name="Agent")` = `assistant(f"sp-{tid}", model="m-one", u=usage(0,0), t=t, session=S, blocks=[tool_use(tid, name, description=desc, subagent_type=role, prompt=prompt)])` (stop_reason not end_turn). `RES(tid, err, t, S)` = `tool_result(tid, err, t, S)`. `DENY(tid, text, t, S)` = `tool_result(tid, True, t, S)` with `rec["message"]["content"][0]["content"] = text`. `SUB(S, agent, role, tid, recs)` = `add_sub(env.root, S, agent, role, recs, tid)` with records `assistant(f"{agent}-n", model="m-one", u=usage(..), t=.., session=S, agent=agent)`; the run's start/end = first/last record ts of that file. `at(n)` (B7, local helper in the test module, no conftest change): `(datetime(2026,10,20,10,0,0,tzinfo=timezone.utc) + timedelta(seconds=n)).strftime("%Y-%m-%dT%H:%M:%S.000Z")`; `at(n) == ts(n)` for n < 3600, and conftest `ts()` breaks at n >= 3600, so use `at()` beyond. `assistant(..., day=at(n))` takes the full timestamp; for `user_prompt`, `tool_result`, `api_error` set `rec["timestamp"] = at(n)` after the call and keep a distinct `t` so uuids stay distinct. Records without timestamps (B8) are still indexed (NULL ts, no scan error).
- **NOMAIN(K)**: key K has a sub run and no main session. Main M (session S9) with `MAIN(S9, "ABC-9")` and three spawns with run files built by the B5 recipe (per child i: `assistant(f"m{i}", t=1+i, blocks=[tool_use(f"t{i}", "Agent", subagent_type="builder", description=..., prompt="p")])`, `tool_result(f"t{i}", t=100+i)`, `add_sub(env.root, "S9", f"ag{i}", "builder", [assistant(f"s{i}", agent=f"ag{i}", session="S9", t=10+i)], f"t{i}")`): two with description `[ABC-9] x`, one with `[K] x`. Keyed share of ABC-9 is 2/3 < 80 percent (CON-002) so M keeps ABC-9; K has 1 run, 0 main sessions.
- **CHILD3**: main M (session S1) own key ABC-1 (`MAIN(S1,"ABC-1")`) and three spawns `[ABC-2] x` with run files, built by the same B5 recipe (KA=ABC-1, KB=ABC-2, children i=0..2, `config.CHILD_SHARE = 0.8`). 3 of 3 keyed children carry ABC-2 (CON-002) so M has `ticket=ABC-1`, `ticket_eff=ABC-2`. Precondition step in every case that uses it: read the `runs` row of M and assert exactly that pair; if it differs the fixture is wrong, not the product.
- **HASH(path set)**: sha256 of each file; for the index: `index.sqlite` and `index.sqlite-wal` when present (never `-shm`), `PRAGMA user_version`, every `meta` row.
- Oracle words: "page" = status + content-type + body text; "CLI" = return code + stdout + stderr.

Open questions list is at the end (Q1 to Q8, each marked answered or open). Each case carries the marker line as it must stand above the test.

---

## CON-010 · test_compare_page.py

### EP-010-01 · CI-010-01 · CON-010 v2 · draft
# rule: CON-010
Fixture: tickets ABC-1 and ABC-2 each as NOMAIN-free simple data: `MAIN(S1,"ABC-1")` with one sub run (spawn `[ABC-1] x`, run input 1000) and `MAIN(S2,"ABC-2")` with two sub runs (input 1000 each; different roles). SCAN (finished, not initial).
Steps: `APP.get("/compare?a=ABC-1&b=ABC-2")`.
Expect: status 200; content-type `text/html; charset=utf-8`; body is the B2 skeleton with `<table class="compare">`, headings `<th scope="col">Figure</th>`, `th.a` (`<th scope="col" class="a">`) text `ABC-1`, `th.b` (`<th scope="col" class="b">`) text `ABC-2`, and `<th scope="col">Difference b - a (ratio b / a)</th>`; row `tr[data-row="runs.total"]` (label `Role runs`): `td.a` `1`, `td.b` `2`, `td.d` `span.diff` `1` and `span.ratio` `2.00`; no `Reload this page later` text, no `<p class="error">`.

### EP-010-06 · CI-010-06 · CON-010 v2 · draft
# rule: CON-010
Fixture: as EP-010-01. `monkeypatch.setattr(st, "rescan", spy)` and `monkeypatch.setattr(st, "ingest", spy2)` (call counters, delegate). HASH the index before.
Steps: `APP.get("/compare?a=ABC-1&b=ABC-2")` twice.
Expect: both 200; spy and spy2 counts 0 (counters reset after SCAN); HASH of the index after equals HASH before (sha256 of index.sqlite and -wal when present, user_version, meta rows).

## CON-011 · test_compare_cli.py, test_store_and_flags.py

### EP-011-01 · CI-011-01 · CON-011 v5 · draft
# rule: CON-011
Fixture: ABC-1: `MAIN(S1,"ABC-1")` with an assistant message input 1500 (`u=usage(1500,0)`); ABC-2: `MAIN(S2,"ABC-2")` with input 2500. SCAN so the page can answer; CLI uses the same env home.
Steps: CLI(`compare ABC-1 ABC-2`); `APP.get("/compare?a=ABC-1&b=ABC-2")`.
Expect: CLI returncode 0, stderr empty. Row `tokens.main.input` (label `Main-session tokens, input`): CLI line cells (split on `|`, stripped) `Main-session tokens, input`, `2k`, `3k`, `1k (1.67)`; page `tr[data-row="tokens.main.input"]`: `td.a` `2k`, `td.b` `3k`, `span.diff` `1k`, `span.ratio` `1.67` (1500, 2500, 1000, 2500/1500). The sets of strings matching `-?\d+k`, `-?\$\d+\.\d\d`, `\d+ min` in stdout and in the page body are equal.

### EP-011-02 · CI-011-02 · CON-011 v5 · draft
# rule: CON-011
Fixture: as EP-011-01.
Steps: CLI(`compare ABC-1 ABC-2 --json`).
Expect: returncode 0; stderr empty; `json.loads(stdout)` works; top keys exactly `{"a","b","diff","version"}`; `version == 1`; `a.key == "ABC-1"`, `b.key == "ABC-2"`; `a.tokens.main.input == 1500`, `b.tokens.main.input == 2500` (raw, no rounding, no `k`). `stdout == compare.to_json(json.loads(stdout)) + "\n"` (only the JSON, no text table).

### EP-011-03 · CI-011-03 · CON-011 v5 · draft
# rule: CON-011
Fixture: `monkeypatch.setattr(server, "main", spy)` (spy records args, returns None; `__main__` calls `server.main()` through the module, B1); `monkeypatch.setattr(compare_cli, "main", spy2)`; `sys.argv = ["agent_console"]`.
Steps: `runpy.run_module("agent_console", run_name="__main__")`.
Expect: `spy` called exactly once with no arguments; `spy2` not called; no exception (no `SystemExit`); nothing written to stdout/stderr by the dispatcher.

### EP-011-04 · CI-011-04 · CON-011 v5 · draft
# rule: CON-011
Fixture: as EP-011-03 with `sys.argv = ["agent_console", "serve"]` (any argv whose second item is not `compare`).
Steps: `runpy.run_module("agent_console", run_name="__main__")`.
Expect: `server.main` called once with no arguments (as today); `compare_cli.main` not called; no `SystemExit`.

### EP-011-17 · CI-011-17 · CON-011 v5 · draft
# rule: CON-011
Fixture: ABC-1/ABC-2 as EP-011-01, index built once by SCAN while NO_FETCH=1 is still set (the `env` default). Then: `claims = env.tmp/"claims"` made a git checkout (`git init`, `git remote add origin <any path under env.tmp>`; no network is reached, the fetch may fail, only the argv matters); `monkeypatch.setenv("AGENT_CONSOLE_CLAIMS_REPO", str(claims))` (so `config.claims_repo()` is set and `Store.ingest` calls `refresh_claims`, store.py line 214); `monkeypatch.delenv("AGENT_CONSOLE_NO_FETCH")`; `monkeypatch.setattr(scope, "_last_fetch", 0.0)` (else `refresh_claims` returns early when `time.time() - _last_fetch < 600`, FETCH_EVERY_S). Spy on `subprocess.run` recording every argv (delegating to the real one), installed on the `scope` module's `subprocess`.
Steps: (1) positive control: `scope.refresh_claims(claims)` with the spy; the spy shows an argv `["git","-C",str(claims),"fetch","-q","origin","+refs/heads/qa-claims:refs/remotes/origin/qa-claims"]`; clear the spy; `monkeypatch.setattr(scope, "_last_fetch", 0.0)` again. (2) in process `compare_cli.main(["ABC-1","ABC-2"])` (no other change: NO_FETCH still deleted, so only the CLI's own switch can stop a fetch).
Expect: step 1 recorded at least one argv containing `fetch` (proves the spy and the set-up can see a fetch; if it fails the fixture is wrong, not the product); step 2 returns `0` and no recorded argv contains `fetch`; `os.environ["AGENT_CONSOLE_NO_FETCH"] == "1"` after the call (set by the CLI itself; monkeypatch teardown restores the original env, nothing to restore by hand).

### EP-011-18 · CI-011-18 · CON-011 v5 · draft
# rule: CON-011
Fixture: env only.
Steps: `Store(env.home/"index.sqlite", env.repo)`; read `meta`.
Expect: `meta` `home` == `str((env.home).resolve())`; `repo_root` == `str(Path(env.repo).resolve())` (resolved, not the raw tmp string; on macOS `/private/var/...`). `tz` == "Europe/Madrid" row still present.

### EP-011-19 · CI-011-19 · CON-011 v5 · draft
# rule: CON-011
Fixture: ABC-1 data, SCAN (n = row count of `runs`, n >= 1). Then `UPDATE meta SET v='/other/home' WHERE k='home'` and `... v='/other/repo' WHERE k='repo_root'`; close.
Steps: `Store(env.home/"index.sqlite", env.repo)` again (console start).
Expect: `runs` count still n (no reset of derived rows); `PRAGMA user_version` == SCHEMA_VERSION; `meta` `home` and `repo_root` are the resolved current values again (overwritten); `tz` and `key_patterns` unchanged.

### EP-011-20 · CI-011-20 · CON-011 v5 · draft
# rule: CON-011
Fixture: ABC-1/ABC-2 data; index built by SCAN with the same env (guard passes). `monkeypatch.setattr(compare_cli, "Store", raiser)` where `raiser(...)` raises `sqlite3.OperationalError("database is locked")`.
Steps: in process `compare_cli.main(["ABC-1","ABC-2"])` with capsys.
Expect: `main` returns `1`; stdout empty; stderr is exactly `compare: error: the index at <env.home/"index.sqlite"> could not be opened or refreshed (OperationalError)` plus one newline; it does not contain `database is locked`; index HASH unchanged. (Lock simulated by the raiser, not a real 5 s lock, B4.)

### EP-011-21 · CI-011-21 · CON-011 v5 · draft
# rule: CON-011
Fixture: `env.home/"index.sqlite"` written with the bytes `b"this is not a sqlite file" * 10`. HASH it.
Steps: CLI(`compare ABC-1 ABC-2`).
Expect: returncode 1; stdout empty; stderr is exactly `compare: error: the index at <env.home/"index.sqlite"> could not be opened or refreshed (DatabaseError)` plus one newline (B4: the class is `sqlite3.DatabaseError`, raised by the guard's first `PRAGMA user_version` read); no `file is not a database` in it; file sha256 unchanged.

### EP-011-22 · CI-011-22 · CON-011 v5 · draft
# rule: CON-011
Fixture: env with ABC-1/ABC-2 logs; no index file yet. `monkeypatch` the scan body that `_scan_safely` calls (`Store.ingest`) to raise `ValueError("secret-detail-xyz")`, so `progress["state"] == "error"`, `progress["error"] == "ValueError"`.
Steps: in process `compare_cli.main(["ABC-1","ABC-2"])`.
Expect: `main` returns `1`; stdout empty; stderr is exactly `compare: error: the index at <env.home/"index.sqlite"> could not be opened or refreshed (ValueError)` plus one newline (ClassName = `st.progress["error"]`); no `secret-detail-xyz`; no traceback.

### EP-011-23 · CI-011-23 · CON-011 v5 · draft
# rule: CON-011
Fixture: ABC-1/ABC-2 logs with a main, a sub run and a spawn. `before = {path: sha256}` for every file under `env.root` (recursive) plus the set of paths.
Steps: CLI(`compare ABC-1 ABC-2`) then CLI(... `--json`).
Expect: both return 0; the path set and every sha256 under `env.root` equal `before`.

## CON-012 · test_compare.py

### EP-012-01 · CI-012-01 · CON-012 v1 · draft
# rule: CON-012
Fixture: `MAIN(S1,"ABC-1")` with `user_prompt(..., day="2026-03-01")` and assistant input 1000 on `day="2026-03-01"`; one sub run on the same day (spawn `[ABC-1] x`, input 2000). SCAN.
Steps: DATA("ABC-1") (and ABC-9 from NOMAIN for b).
Expect: `main_sessions == 1`; `runs.total == 1`; `tokens.total.input == 3000`; `tokens.main.input == 1000`. The run is eight months before the test date; no period edge exists (Q-039: the comparison reads no clock or period, a record of any age counts).

### EP-012-02 · CI-012-02 · CON-012 v1 · draft
# rule: CON-012
Fixture: same shape as EP-012-01 but every record has `cwd="/elsewhere/other"` (not in TREE_ROOTS `/work/app`, so out of project scope) and today's-ish day `2026-10-20`.
Steps: DATA("ABC-1").
Expect: `main_sessions == 1`; `runs.total == 1`; `tokens.total.input == 3000`.

## CON-013 · test_compare.py

### EP-013-01 · CI-013-01 · CON-013 v1 · draft
# rule: CON-013
Fixture: `MAIN(S1,"ABC-1")`, one spawn `[ABC-1] x` with run file input 700 (role builder).
Steps: DATA("ABC-1").
Expect: `runs.total == 1`; `tokens.by_model["m-one"].input == 700` (sub run included).

### EP-013-02 · CI-013-02 · CON-013 v1 · draft
# rule: CON-013
Fixture: `MAIN(S1,"ABC-1")` with an assistant message input 900; no sub run.
Steps: DATA("ABC-1").
Expect: `main_sessions == 1`; `tokens.main.input == 900`; `runs.total == 0`.

### EP-013-03 · CI-013-03 · CON-013 v1 · draft
# rule: CON-013
Fixture: CHILD3 (M own ABC-1, eff ABC-2; M has an assistant message input 400). Precondition: `ticket='ABC-1'`, `ticket_eff='ABC-2'` for M.
Steps: DATA("ABC-1") and DATA("ABC-2").
Expect: DATA(ABC-1): `main_sessions == 0`, `tokens.main == "no main session"`, `tokens.total.input == 0`. DATA(ABC-2): `main_sessions == 1`, `tokens.main.input == 400`, `runs.total == 3`. M is not in ABC-1's data.

### EP-013-04 · CI-013-04 · CON-013 v1 · draft
# rule: CON-013
Fixture: two mains for ABC-1. S1: `MAIN`, `STOP("m1a", 100, S1, usage(1_000_000,0))`, `TYPED("go", 400, S1)`. S2: `MAIN`, `STOP("m2a", 100, S2, usage(2_000_000,0))`, `TYPED("go", 260, S2)`. SCAN with PX.
Steps: DATA("ABC-1").
Expect: `main_sessions == 2`; `tokens.main.input == 3000000`; `cost_usd.main == 3.0`; `time_s.wait == 460` (300 + 160).

### EP-013-05 · CI-013-05 · CON-013 v1 · draft
# rule: CON-013
Fixture: `MAIN(S1,"ABC-1")` with a sub run; plus `MAIN(S2,"ABC-9")`.
Steps: CLI(`compare abc-1 ABC-9`).
Expect: returncode 2; stdout empty; stderr is exactly `compare: unknown ticket key: abc-1` plus one newline (not `ABC-9`); lower case is not folded into `ABC-1`, so no ABC-1 data is shown for it.

## CON-014 · test_compare.py

### EP-014-06 · CI-014-06 · CON-014 v7 · draft
# rule: CON-014
Fixture: `MAIN(S1,"ABC-1")`; `SPAWN(S1,"tu1","[ABC-2] x",t=10,"builder",prompt="please ABC-3")`; `RES("tu1", err=True, t=20, S1)`; no run file.
Steps: DATA("ABC-2"), DATA("ABC-1"); CLI(`compare ABC-3 ABC-1`).
Expect: `ABC-2`: `runs.total == 1`, `runs.failed == 1` (spawn_lead wins). `ABC-1`: `runs.total == 0`. CLI for ABC-3: returncode 2, stderr exactly `compare: unknown ticket key: ABC-3` plus a newline (spawn_text not used, ABC-3 unknown; `compare.unknown_keys(db, "ABC-3", "ABC-1") == ["ABC-3"]`).

### EP-014-07 · CI-014-07 · CON-014 v7 · draft
# rule: CON-014
Fixture: `MAIN(S1,"ABC-1")`; `SPAWN(S1,"tu1","do it",t=10,"builder",prompt="work on ABC-2 now")`; `RES("tu1", True, 20, S1)`; no run file.
Steps: DATA("ABC-2"), DATA("ABC-1").
Expect: `ABC-2`: `runs.total == 1`, `runs.failed == 1` (key from spawn_text). `ABC-1`: `runs.total == 0`.

### EP-014-09 · CI-014-09 · CON-014 v7 · draft
# rule: CON-014
Fixture: main M (S1) whose own key comes late: first prompt `user_prompt("start", 0, S1)`, an assistant `Write` tool_use with `file_path="/x/changes/ABC-1.md"` at t=500 (so `ticket=ABC-1` from change_file, evidence only after t=500). Spawns at t=10, 20, 30 with `[ABC-2] x` and run files (so `ticket_eff='ABC-2'`, B5 recipe). Spawn `tu4` at t=50, description "do it", prompt "p", error result at t=60, no run file. Precondition: M `ticket='ABC-1'`, `ticket_eff='ABC-2'`; no key evidence entry at or before t=50 (CON-014 v7: the key in force is the newest evidence at or before the spawn ts, same instant counts; here none exists, so the run's own `runs.ticket`). Q-040 does not change the result.
Steps: DATA("ABC-1"), DATA("ABC-2").
Expect: `ABC-1`: `runs.total == 1`, `runs.failed == 1` (the spawn takes the spawning run's own `runs.ticket`). `ABC-2`: `runs.total == 3`, `runs.failed == 0`. The spawn is not counted for ABC-2 (not `ticket_eff`).

### EP-014-10 · CI-014-10 · CON-014 v7 · draft
# rule: CON-014
Fixture: `MAIN(S1,"ABC-1")` plus two sub runs for ABC-1 (roles builder, tester).
Steps: DATA("ABC-1").
Expect: `main_sessions == 1`; `runs.total == 2` (not 3).

### EP-014-11 · CI-014-11 · CON-014 v7 · draft
# rule: CON-014
Fixture: S1: `MAIN(S1,"ABC-1")`, `SPAWN(S1,"tu1","[ABC-1] x",t=100,"builder")`, `RES("tu1",True,150,S1)`. S2 (resume copy): `MAIN(S2,"ABC-1")`, the same `SPAWN` record (same tool_use id `tu1`) at t=200, result at t=250. No run file. SCAN: `tool_calls` has two rows for `tu1`.
Steps: DATA("ABC-1").
Expect: `runs.total == 1`; `runs.failed == 1`; `runs.repeat_rounds == 0` (one spawn, earliest-ts row).

### EP-014-12 · CI-014-12 · CON-014 v7 · draft
# rule: CON-014
Fixture: `MAIN(S1,"ABC-1")`; `SPAWN(..,"tu1",..,role "builder", name="Agent")` and `SPAWN(..,"tu2",..,role "tester", name="Task")`, both description `[ABC-1] x`, both error results, no run files.
Steps: DATA("ABC-1").
Expect: `runs.total == 2`; `runs.failed == 2`; `runs.repeat_rounds == 0`.

## CON-015 · test_compare.py

Common for these cases: `MAIN(S1,"ABC-1")`; one spawn `[ABC-1] x` (tid `tu1`, role builder, t=10); sub run file agent `a1` whose records are given per case; DATA("ABC-1").

### EP-015-03 · CI-015-03 · CON-015 v8 · draft
# rule: CON-015
Fixture: sub records: assistant `tool_use("x1","Bash",command="ls")` at t=20; `DENY("x1","Permission to use Bash has been denied",t=30)`; nothing after.
Expect: `runs.total == 1`, `runs.failed == 1`.

### EP-015-04 · CI-015-04 · CON-015 v8 · draft
# rule: CON-015
Fixture: as EP-015-03, denial text `Permission for this action was denied by the Claude Code auto mode classifier`.
Expect: `runs.total == 1`, `runs.failed == 1`.

### EP-015-05 · CI-015-05 · CON-015 v8 · draft
# rule: CON-015
Fixture: as EP-015-03, denial text `The user doesn't want to proceed with this tool use` (is_error true).
Expect: `runs.total == 1`, `runs.failed == 1`.

### EP-015-08 · CI-015-08 · CON-015 v8 · draft
# rule: CON-015
Fixture: sub records: assistant tool_use at t=20, a tool_result (is_error false) at t=25, last assistant turn with text `done` at t=30.
Expect: `runs.total == 1`, `runs.failed == 0`.

### EP-015-09 · CI-015-09 · CON-015 v8 · draft
# rule: CON-015
Fixture: sub records: assistant with only `tool_use("h1","SubagentHandback",message="report")` as last turn at t=20.
Expect: `runs.total == 1`, `runs.failed == 0`.

### EP-015-10 · CI-015-10 · CON-015 v8 · draft
# rule: CON-015
Fixture: sub records: last record an assistant `tool_use("x1","Bash",command="ls")`, no result after.
Expect: `runs.total == 1`, `runs.failed == 1`.

### EP-015-11 · CI-015-11 · CON-015 v8 · draft
# rule: CON-015
Fixture: sub records: assistant `tool_use("x1","Bash",...)` at t=20; `RES("x1", False, 30, S1)` (ordinary result, no denial text) last.
Expect: `runs.total == 1`, `runs.failed == 1`.

### EP-015-12 · CI-015-12 · CON-015 v8 · draft
# rule: CON-015
Fixture: three sub runs of three different roles (builder, tester, reviewer; three spawns with run files); final assistant texts `FAIL: x`, `BLOCKED: y`, `REJECT: z`.
Expect: `runs.total == 3`, `runs.failed == 0`, `runs.repeat_rounds == 0` (verdicts are results).

### EP-015-16 · CI-015-16 · CON-015 v8 · draft
# rule: CON-015
Fixture: `MAIN(S1,"ABC-1")` whose last record is `api_error(t=900, session=S1)`; one sub run that ends with a text reply.
Expect: `runs.total == 1`, `runs.failed == 0` (the main is never failed; it is not in the total either).

### EP-015-17 · CI-015-17 · CON-015 v8 · draft
# rule: CON-015
Fixture: sub run (input 1_000_000) whose file ends on an unanswered Bash tool_use (failed if readable). SCAN; delete the sub file; `st.rescan(wait=True, min_interval=0)` so `log_deleted` holds its run_id.
Expect: `runs.total == 1`, `runs.failed == 0`; `tokens.total.input == 1000000` still counted; no exception.

### EP-015-18 · CI-015-18 · CON-015 v8 · draft
# rule: CON-015
Fixture: as EP-015-17, but the file is deleted after SCAN and no rescan runs (no `log_deleted` row).
Expect: `runs.total == 1`, `runs.failed == 0`; no exception; tokens from the index kept.

### EP-015-19 · CI-015-19 · CON-015 v8 · draft
# rule: CON-015
Fixture: as EP-015-17 (file would be failed if readable), then `os.chmod(file, 0o000)` after SCAN; skip when `os.geteuid() == 0`; restore the mode in teardown.
Expect: `runs.total == 1`, `runs.failed == 0`; no exception.

### EP-015-20 · CI-015-20 · CON-015 v8 · draft
# rule: CON-015
Fixture: two sub runs of different roles. Run 1 file: valid assistant tool_use at t=20, the line `{not json`, a valid `DENY(...)` at t=30, and a truncated last line `{"type":"assistant","message":{"con`. Run 2 file: the line `{not json` first, then an assistant reply with text at t=20.
Expect: `runs.total == 2`, `runs.failed == 1` (run 1: last valid turn is the denial; run 2: reply found past the bad line); no exception.

## CON-016 · test_compare.py

### EP-016-01 · CI-016-01 · CON-016 v5 · draft
# rule: CON-016
Fixture: ABC-1: three builder runs (first ts t=10, 20, 30). ABC-2: one builder run.
Expect: DATA(ABC-1) `runs.repeat_rounds == 2`; DATA(ABC-2) `runs.repeat_rounds == 0`.

### EP-016-02 · CI-016-02 · CON-016 v5 · draft
# rule: CON-016
Fixture: ABC-1: two builder runs and two tester runs.
Expect: `runs.total == 4`; `runs.repeat_rounds == 2` (numbering per role).

### EP-016-03 · CI-016-03 · CON-016 v5 · draft
# rule: CON-016
Fixture: spawn `[ABC-1] x`, role builder, t=5, error result, no run file; then a builder run with first ts t=20.
Expect: `runs.total == 2`; `runs.failed == 1`; `runs.repeat_rounds == 1` (the run is the repeat).

### EP-016-04 · CI-016-04 · CON-016 v5 · draft
# rule: CON-016
Fixture: spawn `[ABC-1] x`, role builder, t=5, non-error result, no run file; then a builder run at t=20.
Expect: `runs.total == 2`; `runs.failed == 0`; `runs.repeat_rounds == 1`.

### EP-016-05 · CI-016-05 · CON-016 v5 · draft
# rule: CON-016
Fixture: spawn `[ABC-1] x`, role builder, t=5, no tool_result, no run file; then a builder run at t=20.
Expect: `runs.total == 1`; `runs.repeat_rounds == 0`.

### EP-016-06 · CI-016-06 · CON-016 v5 · draft
# rule: CON-016
Fixture: two mains for ABC-1 (S1, S2), one builder run.
Expect: `main_sessions == 2`; `runs.total == 1`; `runs.repeat_rounds == 0`.

### EP-016-07 · CI-016-07 · CON-016 v5 · draft
# rule: CON-016
Fixture: spawn tu1 `[ABC-1] x` with `subagent_type="builder"` and spawn tu2 `[ABC-1] x` with no `subagent_type`, both error results at t=5 and t=6, no run files; later a builder run (t=20) and a run whose meta role is `general-purpose` (t=30).
Expect: `runs.total == 4`; `runs.failed == 2`; `runs.repeat_rounds == 2` (builder spawn precedes the builder run; the empty role is `general-purpose` and precedes that run).

## CON-017 · test_compare.py

### EP-017-01 · CI-017-01 · CON-017 v2 · draft
# rule: CON-017
Fixture: one sub run, one message `usage(inp=100, out=200, cr=300, cw=450, w5=400, w1=50)`.
Expect: `tokens.total == {"input":100,"output":200,"cache_write":450,"cache_read":300}`; `tokens.by_model["m-one"]` the same four values.

### EP-017-02 · CI-017-02 · CON-017 v2 · draft
# rule: CON-017
Fixture: one sub run with a `m-one` message input 100 and a `m-two` message input 300.
Expect: `tokens.by_model` keys == {"m-one","m-two"}; `m-one.input == 100`, `m-two.input == 300`; `tokens.total.input == 400`.

### EP-017-03 · CI-017-03 · CON-017 v2 · draft
# rule: CON-017
Fixture: one sub run with one message whose `message.model` is null (`assistant(model=None, u=usage(70,0))`), nothing else.
Expect: `tokens.by_model` keys == {"unknown"}; `tokens.by_model["unknown"].input == 70`; `tokens.total.input == 70`.

### EP-017-04 · CI-017-04 · CON-017 v2 · draft
# rule: CON-017
Fixture: two mains for ABC-1 with one message each: input 100 (S1) and 250 (S2); different message ids.
Expect: `tokens.main.input == 350`; `tokens.total.input == 350`.

### EP-017-05 · CI-017-05 · CON-017 v2 · draft
# rule: CON-017
Fixture: two mains for ABC-1: S1 and S2 each hold the same assistant record (`msg_id "dup"`, `rid="r1"`, input 100). SCAN.
Expect: `tokens.main.input == 100`; `tokens.total.input == 100` (one message, counted once).

## CON-018 · test_compare.py

### EP-018-01 · CI-018-01 · CON-018 v2 · draft
# rule: CON-018
Fixture: one sub run: `m-one` message `usage(1_000_000, 0)`; `m-two` message `usage(100_000, 0)` (output explicitly 0, the helper default is 20). PX.
Expect (every float with `pytest.approx`): `cost_usd.by_model == {"m-one": approx(1.0), "m-two": approx(1.0)}` (keys equal `tokens.by_model` keys, CON-018 v2); `cost_usd.total == approx(2.0)` and `== approx(sum(by_model.values()))`. Arithmetic: m-one 1_000_000 x 1.00 / 1M = 1.0; m-two 100_000 x 10.00 / 1M = 1.0; total 1.0 + 1.0 = 2.0.

### EP-018-02 · CI-018-02 · CON-018 v2 · draft
# rule: CON-018
Fixture: sub run, model id `claude-sonnet-9` (no key match, tier sonnet -> m-one), message `usage(1_000_000, 0)`. Precondition: `Pricing.message_cost("claude-sonnet-9", tokens)` returns a non-None cost with a "tier" match.
Expect (floats with `pytest.approx`): `cost_usd.total == approx(1.0)`; `cost_usd.unpriced_messages == 0`; `cost_usd.by_model == {"claude-sonnet-9": approx(1.0)}`. Arithmetic: tier sonnet -> m-one, 1_000_000 x 1.00 / 1M = 1.0.

### EP-018-03 · CI-018-03 · CON-018 v2 · draft
# rule: CON-018
Fixture: sub run, `m-one` message `usage(inp=0,out=0,cw=2_000_000,w5=1_000_000,w1=1_000_000)`.
Expect: `cost_usd.total == 7.0` (3.00 + 4.00); `tokens.total.cache_write == 2000000`.

### EP-018-04 · CI-018-04 · CON-018 v2 · draft
# rule: CON-018
Fixture: `MAIN(S1,"ABC-1")` with a message `usage(2_000_000, 0)`; one sub run with a message `usage(1_000_000, 0)`. PX.
Expect (floats with `pytest.approx`): `cost_usd.main == approx(2.0)`; `cost_usd.total == approx(3.0)`; `cost_share == approx(2.0)`. Arithmetic: main 2_000_000 x 1.00 / 1M = 2.0; sub 1_000_000 x 1.00 / 1M = 1.0; total 2.0 + 1.0 = 3.0; cost_share = main / sub = 2.0 / 1.0 = 2.0.

## CON-019 · test_compare.py

### EP-019-01 · CI-019-01 · CON-019 v1 · draft
# rule: CON-019
Fixture: one sub run: a `zzz-unpriced` message `usage(1_000_000, 0)` and a `m-one` message `usage(1_000_000, 0)`. PX.
Expect (floats with `pytest.approx`): `cost_usd.total == approx(1.0)` (unpriced adds 0; arithmetic: m-one 1_000_000 x 1.00 / 1M = 1.0, plus 0); `cost_usd.unpriced_messages == 1`; `tokens.by_model["zzz-unpriced"].input == 1000000` (still counted as tokens); `cost_usd.by_model == {"m-one": approx(1.0), "zzz-unpriced": approx(0.0)}` (CON-018 v2, Q-038: an unpriced model is listed with 0, same model set as `tokens.by_model`; value is a float `0.0`).

## CON-020 · test_compare.py

### EP-020-01 · CI-020-01 · CON-020 v2 · draft
# rule: CON-020
Fixture: `MAIN(S1,"ABC-1")` records at t=0 (prompt) and t=300; one sub run records at t=100 and t=600.
Expect: `time_s.wall == 600` (t=0 to t=600).

### EP-020-02 · CI-020-02 · CON-020 v2 · draft
# rule: CON-020
Fixture: only a main for ABC-1 (NOMAIN not needed): prompt at t=60, last record at t=360.
Expect: `time_s.wall == 300`.

### EP-020-03 · CI-020-03 · CON-020 v2 · draft
# rule: CON-020
Fixture: main t=0..100; one sub run whose records all lack the `timestamp` key. SCAN.
Expect: `time_s.wall == 100`; `runs.total == 1`.

## CON-021 · test_compare.py

### EP-021-01 · CI-021-01 · CON-021 v4 · draft
# rule: CON-021
Fixture: main t=0 and 500; run r1 records at t=0 and 300; run r2 at t=100 and 500 (overlap).
Expect: `time_s.active_role == 700`; `time_s.wall == 500` (active > wall).

### EP-021-02 · CI-021-02 · CON-021 v4 · draft
# rule: CON-021
Fixture: main t=0 and 1000; one run t=100 and 200.
Expect: `time_s.active_role == 100`; `time_s.wall == 1000`.

### EP-021-03 · CI-021-03 · CON-021 v4 · draft
# rule: CON-021
Fixture: error spawn `[ABC-1] x` with no run file plus one run t=0..200.
Expect: `runs.total == 2`; `time_s.active_role == 200`.

### EP-021-04 · CI-021-04 · CON-021 v4 · draft
# rule: CON-021
Fixture: run r1 with no timestamps in any record; run r2 t=100 and 300 (different roles).
Expect: `runs.total == 2`; `time_s.active_role == 200`.

## CON-022 · test_compare.py

Common for EP-022-06 to EP-022-16: `MAIN(S1,"ABC-1")` (typed prompt at t=0); `STOP("a1", 100, S1, usage(0,0))` (an assistant record with `message.stop_reason == "end_turn"`, the end_turn marker of Q-036; a gap starts at this record's own timestamp, Q-035); then record X at t=200 (given per case); then `TYPED("later", 500, S1)`. Expect `time_s.wait` as given. "Ends a gap" = wait 100 (stop 100 to X 200; the later typed message closes nothing). "Does not end" = wait 400 (stop 100 to typed 500).

### EP-022-06 · CI-022-06 · CON-022 v11 · draft
# rule: CON-022
X: user record, content `<command-name>/clear</command-name>`, no origin. Expect `time_s.wait == 100`.

### EP-022-07 · CI-022-07 · CON-022 v11 · draft
# rule: CON-022
X: user record, plain text `please continue`, no origin field (old log). Expect `time_s.wait == 100`.

### EP-022-08 · CI-022-08 · CON-022 v11 · draft
# rule: CON-022
X: user record with `origin: {"kind":"task-notification"}`, content `<task-notification>done</task-notification>`. Expect `time_s.wait == 400`.

### EP-022-09 · CI-022-09 · CON-022 v11 · draft
# rule: CON-022
X: user record, content `<local-command-stdout>ok</local-command-stdout>`, no origin. Expect `time_s.wait == 400`.

### EP-022-10 · CI-022-10 · CON-022 v11 · draft
# rule: CON-022
X: user record, content `[Request interrupted by user]`, no origin. Expect `time_s.wait == 400`.

### EP-022-11 · CI-022-11 · CON-022 v11 · draft
# rule: CON-022
Extra record at t=150: assistant `tool_use("x1","Bash",command="ls")` (not end_turn). X: `RES("x1", False, 200, S1)` (tool result, not an AskUserQuestion answer). Expect `time_s.wait == 400`.

### EP-022-12 · CI-022-12 · CON-022 v11 · draft
# rule: CON-022
X: user record `isMeta: true`, `origin: {"kind":"peer"}`, text `from a peer`. Expect `time_s.wait == 400`. One move only; the isMeta + human-origin negative is the separate case EP-022-12b.

### EP-022-12b · CI-022-12 · CON-022 v11 · draft
# rule: CON-022
Same coverage item as EP-022-12 (second negative, own case). X: user record `isMeta: true`, `origin: {"kind":"human"}`, text `meta but human`. Expect `time_s.wait == 400` (isMeta ends no gap whatever its origin, CON-022 v11, Q-037).

### EP-022-13 · CI-022-13 · CON-022 v11 · draft
# rule: CON-022
X: user record with `isMeta: true`, no origin, text `hook output` (Q-037: real hook output is an `attachment` record, type `hook_success`, or a `system` record, subtype `stop_hook_summary`, never a user record; any isMeta user record ends no gap, so this is the valid stand-in). Expect `time_s.wait == 400`. One move only; the two real-shape variants are the separate cases EP-022-13b and EP-022-13c.

### EP-022-13b · CI-022-13 · CON-022 v11 · draft
# rule: CON-022
Same coverage item as EP-022-13. X: an `attachment` record (`attachment.type` `hook_success`) at t=200 instead of a user record. Expect `time_s.wait == 400`.

### EP-022-13c · CI-022-13 · CON-022 v11 · draft
# rule: CON-022
Same coverage item as EP-022-13. X: a `system` record (subtype `stop_hook_summary`) at t=200. Expect `time_s.wait == 400`.

### EP-022-16 · CI-022-16 · CON-022 v11 · draft
# rule: CON-022
X: user record `origin: {"kind":"human"}` with `toolUseResult: {"x":1}` and text content `hello`. Expect `time_s.wait == 400` (not typed).

### EP-022-17 · CI-022-17 · CON-022 v11 · draft
# rule: CON-022
Fixture: main: prompt t=0, `STOP` t=100, `TYPED` t=500 (wait 400); spawn at t=20 with a run file whose own records include an `end_turn` assistant at t=150 and a plain user text at t=200.
Expect: `time_s.wait == 400` (sub-agent files add nothing).

### EP-022-18 · CI-022-18 · CON-022 v11 · draft
# rule: CON-022
Fixture: S1: prompt 0, stop 100 (id m1), typed 400 (gap 300). S2: prompt 0, stop 100 (id m2), typed 260 (gap 160). Different message ids, different uuids.
Expect: `time_s.wait == 460`.

### EP-022-19 · CI-022-19 · CON-022 v11 · draft
# rule: CON-022
Fixture: S1: prompt 0, `STOP` at 100, file ends. S2: `MAIN(S2,"ABC-1")` at t=300 (typed), last record 400.
Expect: `main_sessions == 2`; `time_s.wait == 0` (a number, 0; the stop in S1 is not closed by S2).

### EP-022-20 · CI-022-20 · CON-022 v11 · draft
# rule: CON-022
Fixture: S1 prompt 0, stop 100, typed 400 (would be 300). SCAN; delete S1; rescan so `log_deleted` holds it.
Expect: `main_sessions == 1`; `time_s.wait == 0`; `time_s.wait != "no main session"`; `tokens.main` is a K object.

### EP-022-21 · CI-022-21 · CON-022 v11 · draft
# rule: CON-022
Fixture: as EP-022-20 but no rescan after the change; delete S1 after SCAN.
Expect: `main_sessions == 1`, `time_s.wait == 0`, no exception. One move only; the unreadable-file variant is EP-022-21b.

### EP-022-21b · CI-022-21 · CON-022 v11 · draft
# rule: CON-022
Same coverage item as EP-022-21. Fixture: fresh fixture as EP-022-20 without rescan; `os.chmod(S1, 0o000)` after SCAN (skip as root; restore the mode in teardown).
Expect: `main_sessions == 1`, `time_s.wait == 0`, no exception.

### EP-022-23 · CI-022-23 · CON-022 v11 · draft
# rule: CON-022
Fixture: S1: prompt 0, stop (uuid `u1`, id ms) at 100, typed 400 (gap 300). S2 = copy of every S1 record unchanged (same uuids, timestamps), nothing more. Both mains ABC-1.
Expect: `main_sessions == 2`; `time_s.wait == 300` (once, not 600).

### EP-022-24 · CI-022-24 · CON-022 v11 · draft
# rule: CON-022
Fixture: S1: prompt 0, stop (uuid `u1`, `message.id="ms"`, `requestId="rq"`) at 100, typed 400. S2: the same records, but the stop record has a new uuid `u1b` (same `message.id="ms"`, `requestId="rq"`, same timestamp) and the typed record a different uuid.
Expect: `time_s.wait == 300` (one gap).

### EP-022-25 · CI-022-25 · CON-022 v11 · draft
# rule: CON-022
Fixture: as EP-022-24 but the S2 stop record has no `uuid` field at all (`del rec["uuid"]` on the built record; S1's stop keeps `u1`); `message.id` and `requestId` equal. Precondition: re-read the written S2 line and assert `"uuid"` is not a key.
Expect: `time_s.wait == 300`.

### EP-022-26 · CI-022-26 · CON-022 v11 · draft
# rule: CON-022
Fixture: S1 and S2 each: prompt 0, stop at 100, typed 400 (same timestamps in both files). The stop record is built with `STOP(...)` and no `rid` (so there is no `requestId`), then `del rec["uuid"]` and `del rec["message"]["id"]` before writing. Precondition: re-read a written stop line and assert none of `uuid`, `message.id`, `requestId` is a key.
Expect: `time_s.wait == 300` (same (stop ts, gap-end ts) pair, once). Precondition: the index scan completes on these records.

### EP-022-29 · CI-022-29 · CON-022 v11 · draft
# rule: CON-022
Fixture: S1: stop (uuid `u1`, id `ms1`, requestId `rq1`) at 100, typed 400. S2: stop (uuid `u2`, id `ms2`, requestId `rq2`) at 100, typed 400. Equal timestamps, no shared key.
Expect: `time_s.wait == 600` (two gaps, both counted).

## CON-023 · test_compare.py

### EP-023-03 · CI-023-03 · CON-023 v1 · draft
# rule: CON-023
Fixture: one main, every timestamp set with the `at(n)` helper (B7; n up to 16300 breaks `ts()`; use `assistant(..., day=at(n))` for stops and `rec["timestamp"] = at(n)` for typed records, distinct `t` per record): typed 0; stop 100; typed 400 (300); stop 500; typed 8000 (7500); stop 8100; typed 8200 (100); stop 9000; typed 16300 (7300).
Expect: `time_s.wait == 15200`; `time_s.wait_over_2h == 14800` (7500 + 7300; the 300 and 100 gaps are not in it).

### EP-023-04 · CI-023-04 · CON-023 v1 · draft
# rule: CON-023
Fixture: NOMAIN("ABC-1").
Expect: DATA("ABC-1") `time_s.wait == "no main session"` and `time_s.wait_over_2h == "no main session"`.

## CON-025 · test_compare.py, test_compare_page.py

### EP-025-01 · CI-025-01 · CON-025 v1 · draft
# rule: CON-025
Fixture: NOMAIN("ABC-1"); its sub run has input 1000.
Expect (JSON): `time_s.wait`, `time_s.wait_over_2h`, `tokens.main`, `cost_usd.main`, `cost_share` all equal the string `"no main session"`; `runs.total == 1`; `tokens.total.input == 1000`; `cost_usd.total` a number.

### EP-025-02 · CI-025-02 · CON-025 v1 · draft
# rule: CON-025
Fixture: `MAIN(S1,"ABC-9")`; spawn `[ABC-3] x` with error result and no run file; no other data for ABC-3.
Expect: DATA("ABC-3"): `runs.total == 1`, `runs.failed == 1`; `tokens.total == {"input":0,"output":0,"cache_write":0,"cache_read":0}` (integers); `cost_usd.total == 0`; `time_s.wall == 0`; `time_s.active_role == 0`; `main_sessions == 0`; the five main rows are `"no main session"`.

### EP-025-03 · CI-025-03 · CON-025 v1 · draft
# rule: CON-025
Fixture: NOMAIN("ABC-1") for a; a ticket with a main for b (ABC-9 from NOMAIN is such a ticket).
Steps: CLI(`compare ABC-1 ABC-9`); `APP.get("/compare?a=ABC-1&b=ABC-9")`.
Expect: a side (`ABC-1`) shows `no main session` in exactly 8 cells (B2: 4 rows `tokens.main.<k>`, `cost_usd.main`, `time_s.wait`, `time_s.wait_over_2h`, `cost_share`): page `tr[data-row=id] td.a` for those 8 ids each read `no main session`; CLI text lines for the same 8 row labels have `no main session` in the a cell; `td.b` shows numbers; `0` is not shown in place of it; the diff cell of each is `n/a (n/a)`.

## CON-026 · test_compare.py, test_compare_format.py

### EP-026-05 · CI-026-05 · CON-026 v4 · draft
# rule: CON-026
Fixture: a = ABC-1: sub run `m-two` input 100. b = ABC-2: sub run `m-one` input 1000. D from `compare.compare(db, pr, "ABC-1", "ABC-2")`.
Expect: `diff.tokens.by_model["m-two"].input == {"diff": -100, "ratio": 0.0}`; `diff.tokens.by_model["m-one"].input == {"diff": 1000, "ratio": "n/a"}`; both models present in D (union).

### EP-026-06 · CI-026-06 · CON-026 v4 · draft
# rule: CON-026
Fixture: a = ABC-1: one sub run input 1499; b = ABC-2: one sub run input 2501.
Steps: CLI(`compare ABC-1 ABC-2`) text, page (`a=ABC-1&b=ABC-2`), and CLI(`compare ABC-1 ABC-2 --json`).
Expect: JSON `diff.tokens.total.input.diff == 1002`; row `tokens.total.input` in text (line cells) and page (`tr[data-row="tokens.total.input"]`): a `1k`, b `3k`, `span.diff` `1k`; neither shows `2k` as the difference.

### EP-026-08 · CI-026-08 · CON-026 v4 · draft
# rule: CON-026
Also covers CI-030-04 (same check, one case; see EP-030-04).
Fixture: a = NOMAIN("ABC-1") (sub run input 1000 model m-one), b = ABC-9 with main (also m-one data). Reference: a run comparing two tickets that both have a main and the same model names (e.g. ABC-9 and a second keyed main ticket ABC-5).
Steps: `--json` of both pairs; collect the key-path set of `diff` of each.
Expect: set of key paths of `diff` equals the reference set (no path appears or disappears because a side is a label); `diff.tokens.main` has four leaves (`input`, `output`, `cache_write`, `cache_read`), each `{"diff":"n/a","ratio":"n/a"}`; `diff.time_s.wait == {"diff":"n/a","ratio":"n/a"}`.

## CON-027 · test_compare.py, test_compare_cli.py, test_compare_page.py

For each case b = a ticket with data (ABC-9 from NOMAIN, so unknown-key checks name only the other key; ABC-9 has 2 runs and a main session).

Body oracle OK200(a, b, runs_a, diff_cell, main): page status 200, `<table class="compare">`, `th.a` text `a`, `th.b` text `b`; `tr[data-row="runs.total"]`: `td.a` `runs_a`, `td.b` `2`, `td.d` `diff_cell`; `tr[data-row="tokens.main.input"] td.a` is `no main session` when `main` says so. CLI: returncode 0, stderr empty, stdout first line split on `|` and stripped is `Figure`, `a`, `b`, `Difference b - a (ratio b / a)`; the `Role runs` line has the same three cells `runs_a`, `2`, `diff_cell`; the `Main-session tokens, input` line shows `no main session` in the a cell when `main` says so.

### EP-027-01 · CI-027-01 · CON-027 v6 · draft
# rule: CON-027
Fixture: NOMAIN("ABC-1") (known through a sub run's effective key).
Steps: `APP.get("/compare?a=ABC-1&b=ABC-9")`; CLI(`compare ABC-1 ABC-9`).
Expect: OK200(ABC-1, ABC-9, runs_a `1`, diff_cell `1 (2.00)`, main: no main session); DATA("ABC-1") `runs.total == 1`, `main_sessions == 0`.

### EP-027-02 · CI-027-02 · CON-027 v6 · draft
# rule: CON-027
Fixture: CHILD3 (ABC-1 only the own key of M; precondition on the `runs` row).
Steps: page and CLI(`compare ABC-1 ABC-2`).
Here b = ABC-2 (3 runs), so the body oracle reads `td.b` `3`. Expect: OK200(ABC-1, ABC-2, runs_a `0`, b runs `3`, diff_cell `3 (n/a)`, main: no main session); DATA("ABC-1"): `runs.total == 0`, `main_sessions == 0`, main rows `"no main session"`.

### EP-027-03 · CI-027-03 · CON-027 v6 · draft
# rule: CON-027
Fixture: NOMAIN("ABC-1") (gives ABC-9 its 2 runs and main M in S9; here ABC-1 is only a bystander) plus, in M's session S9, one spawn `[ABC-3] x` with an error result and no run file (ABC-3 only on a counted no-file spawn, as EP-025-02; keyed share of ABC-9 is then 2/4 so M keeps ABC-9). Precondition: DATA("ABC-9") `runs.total == 2`.
Steps: page and CLI(`compare ABC-3 ABC-9`).
Expect: OK200(ABC-3, ABC-9, runs_a `1`, diff_cell `1 (2.00)`, main: no main session); `tr[data-row="time_s.wall"] td.a` `0 min` (the 0-second wall; text from `minutes(0)` as the formatter returns it); DATA("ABC-3"): `runs.total == 1`, `time_s.wall == 0`.

### EP-027-04 · CI-027-04 · CON-027 v6 · draft
# rule: CON-027
Fixture: NOMAIN("ABC-1"); SCAN; delete ABC-1's sub run file; rescan (`log_deleted` row).
Steps: page and CLI(`compare ABC-1 ABC-9`).
Expect: OK200(ABC-1, ABC-9, runs_a `1`, diff_cell `1 (2.00)`, main: no main session); DATA("ABC-1") `runs.total == 1`, `runs.failed == 0`.

### EP-027-05 · CI-027-05 · CON-027 v6 · draft
# rule: CON-027
Fixture: ABC-9 data only.
Steps: `APP.get("/compare?a=ABC-404&b=ABC-9")`.
Expect: status 404; content-type `text/html; charset=utf-8` (not JSON `{"detail"}`); body contains `<p class="error">Unknown ticket key: <code>ABC-404</code>.</p>`; no `<table`; title/heading `Ticket comparison` carry no key.

### EP-027-06 · CI-027-06 · CON-027 v6 · draft
# rule: CON-027
Fixture: as EP-027-05.
Steps: CLI(`compare ABC-404 ABC-9`); CLI(`compare ABC-404 ABC-9 --json`).
Expect: both: returncode 2; stdout empty; stderr is exactly `compare: unknown ticket key: ABC-404` plus one newline.

### EP-027-07 · CI-027-07 · CON-027 v6 · draft
# rule: CON-027
Fixture: ABC-9 data, `st.ingest()` done (so the first-index 503 does not apply, B1; same for EP-027-08).
Steps: `APP.get("/compare?a=ABC-404&b=ABC-405")`.
Expect: 404; body contains `<p class="error">Unknown ticket keys: <code>ABC-404</code>, <code>ABC-405</code>.</p>` (a first).

### EP-027-08 · CI-027-08 · CON-027 v6 · draft
# rule: CON-027
Steps: CLI(`compare ABC-404 ABC-405`).
Expect: returncode 2; stdout empty; stderr is exactly `compare: unknown ticket keys: ABC-404, ABC-405` plus one newline.

### EP-027-09 · CI-027-09 · CON-027 v6 · draft
# rule: CON-027
Steps: `APP.get("/compare?a=ABC-404&b=ABC-404")` and CLI(`compare ABC-404 ABC-404`).
Expect: page 404, body contains `Unknown ticket key: <code>ABC-404</code>.` (singular) and `body.count("ABC-404") == 1`; CLI returncode 2, stderr exactly `compare: unknown ticket key: ABC-404` plus a newline, stdout empty; `compare.unknown_keys(db, "ABC-404", "ABC-404") == ["ABC-404"]`.

### EP-027-10 · CI-027-10 · CON-027 v6 · draft
# rule: CON-027
Fixture: ABC-1 and ABC-9 data.
Steps: `APP.get("/compare?a=abc-1&b=ABC-9")`; CLI(`compare abc-1 ABC-9`).
Expect: page 404, body contains `Unknown ticket key: <code>abc-1</code>.`; CLI returncode 2, stderr exactly `compare: unknown ticket key: abc-1` plus a newline, stdout empty.

### EP-027-11 · CI-027-11 · CON-027 v6 · draft
# rule: CON-027
Fixture: `MAIN(S1,"ABC-9")`; spawn `[ABC-7] x`, no tool_result, no run file; no other ABC-7 data.
Steps: page `a=ABC-7&b=ABC-9`; CLI(`compare ABC-7 ABC-9`).
Expect: page 404 with `Unknown ticket key: <code>ABC-7</code>.`; CLI returncode 2, stderr exactly `compare: unknown ticket key: ABC-7` plus a newline.

### EP-027-12 · CI-027-12 · CON-027 v6 · draft
# rule: CON-027
Fixture: NOMAIN("ABC-8") with all its records on `day="2026-03-01"` (outside the default period).
Steps: page `a=ABC-8&b=ABC-9`; CLI(`compare ABC-8 ABC-9`).
Expect: OK200(ABC-8, ABC-9, runs_a `1`, diff_cell `1 (2.00)`, main: no main session); DATA("ABC-8") `runs.total == 1`.

## CON-028 · test_compare.py

### EP-028-01 · CI-028-01 · CON-028 v1 · draft
# rule: CON-028
Fixture: `MAIN(S1,"ABC-1")` with a sub run input 1000, main input 500.
Steps: CLI(`compare ABC-1 ABC-1 --json`); page.
Expect: returncode 0, page 200; `a == b` except nothing differs; every numeric leaf of D has `diff == 0`; for leaves with a nonzero value `ratio == 1.0` (e.g. `diff.runs.total == {"diff":0,"ratio":1.0}`, `diff.tokens.total.input == {"diff":0,"ratio":1.0}`).

## CON-029 · test_compare_format.py

### EP-029-16 · CI-029-16 · CON-029 v7 · draft
# rule: CON-029
Fixture (PX, m-one: input 1.00, output 2.00 per 1M), one fixed row per figure, nothing else in the logs: a = ABC-1: `MAIN(S1,"ABC-1")` (prompt at t=0) plus one assistant `m-one` at t=100 with `usage(1500, 616_000)`. b = ABC-2: `MAIN(S2,"ABC-2")` (prompt t=0) plus one assistant `m-one` at t=400 with `usage(2500, 1_250_000)`. No sub runs. Wall time comes from the record timestamps: a 100 s (t=0 to t=100), b 400 s (t=0 to t=400). Cost: a = 1500 x 1.00/1M + 616000 x 2.00/1M = 1.2335; b = 2500 x 1.00/1M + 1250000 x 2.00/1M = 2.5025; difference 1.269 (no .xx5 tie).
Steps: page `a=ABC-1&b=ABC-2` body and CLI text (`compare ABC-1 ABC-2`) for the same pair.
Expect: the sets of matches of `-?\d+k`, `-?\$\d+\.\d\d` and `\d+ min` are equal in both and not empty; they include `2k`, `3k`, `1k`, `616k`, `1250k`, `634k`, `$1.23`, `$2.50`, `$1.27`, `2 min`, `7 min`, `5 min`. Row oracles (page `tr[data-row=...]` and the CLI line cells): `tokens.main.input` a `2k`, b `3k`, diff `1k` (ratio `1.67`); `tokens.main.output` a `616k`, b `1250k`, diff `634k` (ratio `2.03`); `cost_usd.total` a `$1.23`, b `$2.50`, diff `$1.27` (ratio `2.03`); `time_s.wall` a `2 min`, b `7 min`, diff `5 min` (ratio `4.00`).

### EP-029-18 · CI-029-18 · CON-029 v7 · draft
# rule: CON-029
Fixture (PX, m-one input 1.00 per 1M): ABC-1: `MAIN(S1,"ABC-1")` (prompt t=0) plus one assistant `m-one` at t=29 with `usage(1499, 0)` (output given explicitly 0; the helper default is 20); ABC-9 as b.
Steps: CLI(`compare ABC-1 ABC-9 --json`).
Expect: `a.tokens.main.input == 1499` (int); `a.cost_usd.main == pytest.approx(0.001499)` (float, the raw `message_cost`, 1499 x 1.00 / 1M; no rounding to cents); `a.time_s.wall == 29`; no `k`, `$` or `min` text in any value.

## CON-030 · test_compare.py

### EP-030-01 · CI-030-01 · CON-030 v1 · draft
# rule: CON-030
Fixture: ABC-1 and ABC-9 data.
Steps: CLI(`compare ABC-1 ABC-9 --json`).
Expect: `json.dumps(json.loads(stdout), sort_keys=True, indent=2) == stdout.rstrip("\n")`; top keys `{"a","b","diff","version"}`; `version == 1`.

### EP-030-02 · CI-030-02 · CON-030 v1 · draft
# rule: CON-030
Fixture: as EP-030-01; no log changes between runs.
Steps: CLI(`compare ABC-1 ABC-9 --json`) twice.
Expect: both stdout strings are byte-identical; both returncode 0.

### EP-030-03 · CI-030-03 · CON-030 v1 · draft
# rule: CON-030
Fixture: a = NOMAIN("ABC-1") (a priced `m-one` run, plus one unpriced message), b = ABC-9 with a main.
Expect (types after `json.loads`): `key` str; `main_sessions` int; `runs.total/failed/repeat_rounds` int; every K leaf int; `tokens.main` is the str `"no main session"` for a and a K object for b; `cost_usd.total` and every `cost_usd.by_model.*` float; `cost_usd.unpriced_messages` int; `time_s.wall`, `time_s.active_role` float; `time_s.wait` str for a, float for b; `cost_share` str for a, float for b. No value is rounded.

### EP-030-04 · CI-030-04 · CON-030 v1 · draft
# rule: CON-030
Same check as EP-026-08 (item CI-026-08); no separate test. The one test is written under EP-026-08 and carries both item ids (CI-026-08, CI-030-04) in its marker/trace. Fixture, steps and expectation: see EP-026-08 (key-path set of `diff` identical with a label side and with two main sides).

### EP-030-05 · CI-030-05 · CON-030 v1 · draft
# rule: CON-030
Fixture: a with main and one model `m-one`, b with main and one model `m-one`.
Steps: collect the leaf key paths of the `--json` output.
Expect (snapshot, exact): top `a`, `b`, `diff`, `version`. Under `a` and `b`: `key`, `main_sessions`, `runs.{total,failed,repeat_rounds}`, `tokens.total.{input,output,cache_write,cache_read}`, `tokens.by_model.m-one.{input,output,cache_write,cache_read}`, `tokens.main.{input,output,cache_write,cache_read}`, `cost_usd.{total,main,unpriced_messages}`, `cost_usd.by_model.m-one`, `time_s.{wall,active_role,wait,wait_over_2h}`, `cost_share`. Under `diff`: the same paths without `key`, each leaf an object with exactly `diff` and `ratio`.

## CON-031 · test_compare_cli.py, test_compare_page.py

### EP-031-02 · CI-031-02 · CON-031 v2 · draft
# rule: CON-031
Fixture: logs for ABC-1/ABC-9; `before` = sha256 of every file and the path set under `env.root`.
Steps: `APP.get("/compare?a=ABC-1&b=ABC-9")` twice.
Expect: both 200; path set and every sha256 unchanged.

### EP-031-03 · CI-031-03 · CON-031 v2 · draft
# rule: CON-031
Steps: `flat_routes(app)`; `APP.get("/compare?a=ABC-1&b=ABC-9")`.
Expect: no route whose path contains `compare` has a method other than GET/HEAD; the set of POST paths is a subset of the literal set asserted in `console/tests/test_server.py` (`test_no_write_endpoint_beyond_local_state_changes`, `/api/show/{run_id:path}`, `/api/flags/check`, `/api/rescan`, `/api/verdict`, `/api/defect`, `/api/flags/decide`); 200 body has no `<form`, `<input`, `<button` and no `method="post"`.

### EP-031-04 · CI-031-04 · CI-034-11 · DT-034-11 · CON-031 v2 · draft
# rule: CON-031
Merge note: the page half of CI-031-04 (a third parameter is ignored) is written once, under EP-034-12 (trace CI-034-12 + page half of CI-031-04). This case holds the CLI three-key check and carries CI-031-04 (CLI half), CI-034-11 and DT-034-11 in its trace; it is the only case with the USAGE-HEAD expectation for three keys.
Fixture: ABC-1, ABC-9 and one more key ABC-77 with data.
Steps: CLI(`compare ABC-1 ABC-9 ABC-77`).
Expect: CLI returncode 2, stdout empty, stderr exactly the two lines `usage: python -m agent_console compare [-h] [--json] KEY_A KEY_B` and `python -m agent_console compare: error: unrecognized arguments: ABC-77` (B3).

## CON-032 · existing suites, test_store_and_flags.py

### EP-032-02 · CI-032-02 · CON-032 v3 · draft
# rule: CON-032
Fixture: the `env` fixture with a copy of `console/tests/fixtures` (read only source) as LOG_ROOT. Golden, written once: `git archive 0891a04 console | tar -x -C <new empty tmp folder G>`; with that archived code (script kept in another folder, run as a subprocess with `cwd` and `PYTHONPATH` set to `G/console`, same env variables, own `AGENT_CONSOLE_HOME`) build an index and write `(run_id, ticket, ticket_src, ticket_eff)` ordered by run_id to `G/golden.json`. The golden is not recomputed per run.
Steps: build the index from the same log copy with the changed code (`Store().ingest()`); dump the same four columns ordered by run_id.
Expect: the two dumps are equal row by row (same count, same values); the golden has at least one row (precondition). The existing ticket test files are not run here (CI-032-01 runs them).

### EP-032-03 · CI-032-03 · CON-032 v3 · draft
# rule: CON-032
Fixture: SCAN with ABC-1 data; then `DELETE FROM meta WHERE k IN ('home','repo_root')`; record the `runs` count, `user_version`, the `tz` and `key_patterns` rows.
Steps: `Store(env.home/"index.sqlite", env.repo)`.
Expect: `home` and `repo_root` rows exist with the resolved values; `runs` count, `user_version`, `tz`, `key_patterns` equal what was recorded (derived rows kept).

### EP-032-04 · CI-032-04 · CON-032 v3 · draft
# rule: CON-032
Steps: collect `(path, method)` for every POST route of `create_app` with `flat_routes`.
Expect: `posts - LITERAL == set()` with LITERAL the literal set asserted in `console/tests/test_server.py` `test_no_write_endpoint_beyond_local_state_changes` (about line 51): `{"/api/show/{run_id:path}", "/api/flags/check", "/api/rescan", "/api/verdict", "/api/defect", "/api/flags/decide"}`; no PUT/PATCH/DELETE; no new POST route.

## CON-033 · test_compare_page.py

Common: header check HDR(resp) = every `SECURITY_HEADERS` key/value from `server.py` equals the response header (CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Cache-Control).

### EP-033-01 · CI-033-01 · CON-033 v1 · draft
# rule: CON-033
Steps: `APP.get("/compare?a=ABC-1&b=ABC-9", headers={"host":"evil.example.com"})`; `APP.get("/health", headers={"host":"evil.example.com"})`.
Expect: status 404 and content-type JSON; body is the middleware's `{"detail": "Not found."}`, equal in status, content-type and body bytes to the `/health` answer; body does not contain `ABC-1`.

### EP-033-02 · CI-033-02 · CON-033 v1 · draft
# rule: CON-033
Fixture: ABC-1 and ABC-9 data.
Steps: `APP.get(url, headers={"host":"127.0.0.1:8790"})` and with `"localhost:8790"`.
Expect: both status 200, text/html body naming `ABC-1`.

### EP-033-04 · CI-033-04 · CON-033 v1 · draft
# rule: CON-033
Fixture: NOMAIN("ABC-1") (ABC-9 gets data from it).
Steps: 200 answer (`a=ABC-1&b=ABC-9`). Expect: status 200, content-type `text/html; charset=utf-8`, body contains `<table class="compare">`, and HDR holds.

### EP-033-05 · CI-033-05 · CON-033 v1 · draft
# rule: CON-033
Fixture: as EP-033-04.
Steps: `a=ABC-404&b=ABC-9`. Expect: status 404, content-type `text/html; charset=utf-8`, body contains `<p class="error">Unknown ticket key: <code>ABC-404</code>.</p>`, no `<table`, and HDR holds.

### EP-033-06 · CI-033-06 · CON-033 v1 · draft
# rule: CON-033
Steps: `?a=ABC-1` (b missing). Expect: status 422, body has `Missing parameter: <code>b</code>.`, and HDR holds.

### EP-033-07 · CI-033-07 · CON-033 v1 · draft
# rule: CON-033
Fixture: `st.progress["initial"] = True`.
Steps: `a=ABC-1&b=ABC-9`. Expect: status 503, body has `<p class="error">The console is building its first index. Reload this page later.</p>`, and HDR holds.

### EP-033-08 · CI-033-08 · CON-033 v1 · draft
# rule: CON-033
Steps: run the existing `test_server.py::test_main_refuses_non_loopback_bind` unchanged, plus a spy on `uvicorn.run` while `server.main()` runs with a loopback setting.
Expect: the existing test passes; the spy sees `host == "127.0.0.1"`.

### EP-033-09 · CI-033-09 · CON-033 v1 · draft
# rule: CON-033
Fixture: bodies of the 200, 404, 422 and 503 answers (503 via `st.progress["initial"] = True`).
Expect for each: body is a complete HTML document (starts with `<!doctype html`, ends with `</html>`); no `<style`; no `style=`; every `<script` has a `src` starting with `/static/` (no inline script); no `http://`, `https://` or `//host` in any `src`, `href`, `action`.

### EP-033-10 · CI-033-10 · CON-033 v1 · draft
# rule: CON-033
Steps: `APP.get("/static/compare.css")`; the 200 body; run `test_static.py`.
Expect: status 200, content-type `text/css`; the 200 compare body links `/static/compare.css`; the CSS has no `@import` and no `url(http`; `test_static.py` passes.

## CON-034 · test_compare_page.py, test_compare_cli.py

### EP-034-06 · CI-034-06 · CON-034 v4 · draft
# rule: CON-034
Fixture: ABC-1/ABC-9 data.
Steps: `APP.get("/compare?a=%20ABC-1&b=ABC-9")`.
Expect: status 404 (not 422, not 200); body contains `Unknown ticket key: <code> ABC-1</code>.` (key as written, leading space kept, not trimmed).

### EP-034-12 · CI-034-12 · CON-034 v4 · draft
# rule: CON-034
Also covers the page half of CI-031-04 (see EP-031-04): one test, trace CI-034-12 + page half of CI-031-04. The CLI three-key check (CI-034-11, DT-034-11) is in EP-031-04.
Fixture: ABC-1, ABC-9 and ABC-77 with data.
Steps: `r1 = APP.get("/compare?a=ABC-1&b=ABC-9&c=X")`; `r2 = APP.get("/compare?a=ABC-1&b=ABC-9")`; `r3 = APP.get("/compare?a=ABC-1&b=ABC-9&c=ABC-77")`.
Expect: all 200; `r1.text == r2.text == r3.text`; `X` is not echoed; `ABC-77` not in `r3.text` (body names `ABC-1`, `ABC-9` only).

### EP-034-13 · CI-034-13 · CON-034 v4 · draft
# rule: CON-034
Steps: `r1 = get("/compare?a=ABC-404&a=ABC-1&b=ABC-9")`; `r2 = get("/compare?a=ABC-1&b=ABC-9")`; `r3 = get("/compare?a=ABC-1&a=ABC-404&b=ABC-9")`.
Expect: `r1` 200 and `r1.text == r2.text` (last value wins); `r3` 404 naming `ABC-404`.

### EP-034-14 · CI-034-14 · CON-034 v4 · draft
# rule: CON-034
Steps: 200 body for `a=ABC-1&b=ABC-9`.
Expect: no `<form`, `<input`, `<button`; case-insensitive no `compare with` and no `swap`; no link whose `href` contains `/compare?`.

### EP-034-15 · CI-034-15 · CON-034 v4 · draft
# rule: CON-034
Steps: `APP.get("/compare?b=ABC-9")` (a missing).
Expect: status 422; content-type `text/html; charset=utf-8`; `json.loads(body)` raises; `'"detail"'` not in the body; body contains `<p class="error">Missing parameter: <code>a</code>.</p>` (visible text `Missing parameter: a.`) and `<code>b</code>` is not in the body.

## CON-035 · test_compare.py, test_compare_cli.py, test_compare_page.py

Common sentinel fixture SENT: ABC-1 main with first prompt `[ABC-1] go SENT-USER-9f3a`, an assistant text `SENT-ASSIST-9f3a`, a Bash tool_use `command="SENT-TOOLIN-9f3a"`, its result content `SENT-TOOLRES-9f3a`; a spawn `[ABC-1] x` with `prompt="SENT-PROMPT-9f3a"` and a run file whose assistant text is `SENT-SUBTEXT-9f3a`. ABC-9 as b.

### EP-035-01 · CI-035-01 · CON-035 v1 · draft
# rule: CON-035
Steps: CLI(`compare ABC-1 ABC-9`). Expect: returncode 0; `"SENT-"` not in stdout or stderr.

### EP-035-02 · CI-035-02 · CON-035 v1 · draft
# rule: CON-035
Steps: CLI(`compare ABC-1 ABC-9 --json`). Expect: returncode 0; `"SENT-"` not in stdout or stderr.

### EP-035-03 · CI-035-03 · CON-035 v1 · draft
# rule: CON-035
Steps: `APP.get("/compare?a=ABC-1&b=ABC-9")`. Expect: 200; `"SENT-"` not in the body.

### EP-035-04 · CI-035-04 · CON-035 v1 · draft
# rule: CON-035
Fixture: run 1 ends on `DENY(.., "Permission to use Bash has been denied SENT-DENY-9f3a")`; run 2 (other role) ends on `api_error(message="SENT-APIERR-9f3a arn:aws:sts::000000000000:assumed-role/x")`; both under ABC-1.
Steps: CLI text, CLI `--json`, page 200, page 404 (`a=ABC-404`), page 422 (`a` only).
Expect: in every output `SENT-`, `Permission to use`, `The user doesn't want to proceed` and `arn:aws` are absent; `runs.failed == 2` in the JSON.

### EP-035-05 · CI-035-05 · CON-035 v1 · draft
# rule: CON-035
Steps: `APP.get("/compare", params={"a": "<script>x</script>", "b": "ABC-9"})`.
Expect: status 404; body contains `Unknown ticket key: <code>&lt;script&gt;x&lt;/script&gt;</code>.`; body does not contain `<script>x</script>`.

### EP-035-06 · CI-035-06 · CON-035 v1 · draft
# rule: CON-035
Fixture: ABC-1 sub run with `message.model = "mod<b>RAW9f</b>"` (unpriced) and a run role from meta `agentType = "role<b>RAW9f</b>"`; ABC-9 as b.
Steps: `APP.get("/compare?a=ABC-1&b=ABC-9")`.
Expect: 200; the model row ids/labels and the `data-row` attributes escape the model too (`data-row="tokens.by_model.mod&lt;b&gt;RAW9f&lt;/b&gt;.input"`, label `Tokens, mod&lt;b&gt;RAW9f&lt;/b&gt;, input`, `html.escape(..., quote=True)` also in attributes); body contains `mod&lt;b&gt;RAW9f&lt;/b&gt;`; `<b>RAW9f` not in the body (neither model nor role as markup).

---

## Questions list (status after update pass 2)

Result: 8 answered, 0 still open. Original text kept below, each with its status line.

1. Entry point names of `compare.py` / `compare_format.py` / `compare_cli.main` are not fixed anywhere (no builder code yet). Cases use DATA(K) (= the `--json` tree), the CLI and the page. The builder or lead QA gives the real function names when the cases become tests.
   ANSWERED: change.md "Interfaces for tests" B1 (`compare.compare/ticket/unknown_keys/to_json`, `compare_format.*`, `compare_cli.main(argv) -> int`, `__main__` dispatch, `compare_page.render/missing_page/building_page/unknown_page`). DATA(K), CLI and the setup block now use them.
2. Page markup is not fixed: column heading text, row labels, how difference and ratio share a cell. Cases assert on values and strings in the body (and counts such as at least 4 `no main session`), not on selectors. If the page layout is fixed in a later step, EP-010-01, EP-025-03, EP-029-16 can be tightened.
   ANSWERED: change.md B2 (headings, `tr[data-row=id]`, `td.a/.b/.d`, `span.diff/.ratio`, 8 `no main session` cells, error `<p class="error">` texts). EP-010-01, EP-011-01, EP-025-03, EP-026-06, EP-029-16 and the error-page cases were tightened.
3. CON-022 (EP-022-13): the log marker of hook output in a user record is not named in the rule (only task notifications, peers, local command output, interrupt marker). The case uses an `isMeta` machine record; confirm what a hook-output record looks like or accept this.
   ANSWERED: Q-037 (hook output is an `attachment`/`system` record; any isMeta user record ends no gap; the isMeta stand-in is valid). EP-022-13 now states it.
4. CON-011 v5, EP-011-21: for a file that is not a database, `sqlite3` raises `DatabaseError`, while change.md says `OperationalError`. The case takes the real class name from a direct call. Confirm the line should name whatever class is raised. Also the wording and prefix of the exit-1 line is not fixed (cases check one line, class name present, details absent).
   ANSWERED: change.md B4 (`DatabaseError` for a non-database file, `OperationalError` for a lock; exact exit-1 line). EP-011-20, 021, 022 assert the exact line.
5. CON-019: whether an unpriced model appears in `cost_usd.by_model` (with 0) is not stated; EP-019-01 asserts only the total, the unpriced count and the tokens.
   ANSWERED: Q-038 / CON-018 v2 (listed with 0). EP-019-01 asserts `by_model == {"m-one": 1.0, "zzz-unpriced": 0.0}`.
6. CON-034 v4: the 422 page text is not fixed; EP-034-15 checks that the missing parameter is named and the body is HTML, not the exact words.
   ANSWERED: change.md B2 error texts (`Missing parameter: <code>a</code>.`). EP-034-15 and EP-033-06 assert them.
7. CON-022 lead QA note rr9 N1 (two gaps in one file whose stop records share message.id + requestId): no EP item exists for it. It needs a new coverage item (suggest EP, CI-022-30: one gap, counted once); the QA analyst should add it. Not written here to keep one case per existing item.
   ANSWERED: Q-034 / CON-022 v11 (one gap, 300 s not 900 s). The case is CI-022-30, written as TC-ST-11 in cases-st-cl.md (state-transition designer); no EP case added here.
8. `conftest.ts()` supports at most 3599 s; EP-023-03 and any longer test needs `at(n)` (a local helper, no change to conftest requested).
   ANSWERED: change.md B7 gives the `at(n)` helper; defined in the setup block, used by EP-023-03.
