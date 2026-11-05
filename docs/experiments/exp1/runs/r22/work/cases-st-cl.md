Lead QA sign-off 2026-11-05: test design APPROVED (EXP1-R22C; re-check of EP-018-01, EP-018-02, EP-018-04, EP-019-01 passed; design approval 1 notes stay open for the automation engineer).

# EXP1-R22C · cases: state transition (ST) and checklist (CL) · status draft (update pass 2026-11-05)

Designer: test designer (ST + CL). Base 0891a04, branch exp1/r22. Rule versions (docs/requirements/console.md): CON-011 v5, CON-018 v2, CON-022 v11, CON-031 v2, CON-032 v3. Interfaces: change.md "Interfaces for tests" (B1-B8).
Gates not declared (test_case_files, timing_check): cases kept here, no timing case. `test_strategy`: none.

## Common setup (all cases)
- `env` fixture (console/tests/conftest.py): tmp AGENT_CONSOLE_HOME (= `env.home`), LOG_ROOT (= `env.root`), REPO, NO_FETCH=1, TZ Europe/Madrid, tmp pricing (`models: {}`, B6). Never ~/.agent-console, never ~/.claude. console/tests/fixtures are not used.
- Logs are built in tmp with the conftest helpers: `user_prompt`, `assistant`, `tool_use`, `tool_result`, `write_jsonl`, `add_sub`. Times: `ts(n)` for n < 3600 equals the local helper `at(n)` (B7, copied into the test module as given: `datetime(2026,10,20,10,0,0,tzinfo=utc)+timedelta(seconds=n)` formatted `%Y-%m-%dT%H:%M:%S.000Z`). All times below are n seconds; use `at(n)`. For `user_prompt` and `tool_result` set `rec["timestamp"] = at(n)` after the call and keep a distinct `t` so uuids stay distinct; `assistant(..., day=at(n))`. No live clock.
- Main session file: `env.root / PROJECT / "<session>.jsonl"` (as `one_main`). Key recipe (B5): own key = effective key `EXP1-WWW` (matches config.DEFAULT_KEY_PATTERN `[A-Z][A-Z0-9]+-[A-Z0-9]+`): first record `user_prompt("[EXP1-WWW] start", t=0)`, no sub-agents, so `ticket == ticket_eff == EXP1-WWW`. Keys in the compare cases: `EXP1-AAA`, `EXP1-BBB`, `EXP1-WWW`; never bare letters. Keep message ids, tool_use ids and uuids unique (B5).
- Record kinds: "Stop (end_turn)" = `assistant(...)` with an explicit unique message id and `rec["message"]["stop_reason"] = "end_turn"` (Q-036, CON-022 v11). "Typed" = `user_prompt(text, t)` with `rec["origin"] = {"kind": "human"}`, no isMeta. "Task notification" = user record with `origin = {"kind": "task-notification"}`.
- Wait oracle (B1): `store = Store(); store.ingest(); db = store.reader()` (db.close() in `finally`); `DATA(W) = compare.compare(db, Pricing.load(config.pricing_path()), "EXP1-WWW", "EXP1-WWW")["a"]`; assert `DATA(W)["time_s"]["wait"]`, also `["time_s"]["wait_over_2h"] == 0` and no exception. Same value the CLI `--json` prints under `a.time_s.wait`.
- CLI (B1, B3): call `compare_cli.main(argv)` in process, argv = what follows `compare`, e.g. `["EXP1-AAA", "EXP1-BBB"]`; assert the returned int, and stdout/stderr via `capsys.readouterr()`. `main` never calls `sys.exit`.
- Marker above each test: `# rule: <ID>`.

## ST cases (10 coverage items + 1 item now in the rule)

### TC-ST-01 · CI-011-14 · CON-011 v5
- File: console/tests/test_compare_cli.py · marker `# rule: CON-011`
- States: S0 "no index.sqlite in the console's own home" -> (CLI run) -> S1 "index built, comparison printed".
- Fixture: `env`; one sub-agent run for key `EXP1-AAA` and one for key `EXP1-BBB` (`add_sub`; parent main session carries the key, B5 recipe). Do not create `env.home/index.sqlite`.
- Steps: 1. assert `not (env.home / "index.sqlite").exists()`. 2. `rc = compare_cli.main(["EXP1-AAA", "EXP1-BBB"])`, `capsys.readouterr()`.
- Expected: `rc == 0`; stdout is `compare_format.text_table(tree)` form: header line with `Figure`, `EXP1-AAA`, `EXP1-BBB`, `Difference b - a (ratio b / a)`; stderr empty (no "refused" line); `env.home/index.sqlite` exists after; its `meta` rows `home` = resolved `env.home`, `repo_root` = resolved `env.repo`.

### TC-ST-02 · CI-011-15 · CON-011 v5
- File: console/tests/test_compare_cli.py · marker `# rule: CON-011`
- States: home A has an index (S_A); home B has none (S_B0) -> (CLI run with home B) -> S_B1 built; S_A unchanged.
- Fixture: `env` (home A = `env.home`), second tmp folder `home_b` (does not exist yet). Same logs for both runs (keys `EXP1-AAA`, `EXP1-BBB` as TC-ST-01).
- Steps: 1. `main(["EXP1-AAA","EXP1-BBB"])` under home A (rc 0, builds A's index). 2. Record sha256 of `A/index.sqlite` and `A/index.sqlite-wal` (when present), `PRAGMA user_version`, all `meta` rows. 3. `monkeypatch.setenv("AGENT_CONSOLE_HOME", str(home_b))`; assert `home_b/index.sqlite` absent. 4. `main(["EXP1-AAA","EXP1-BBB"])`. 5. Record A's values again.
- Expected: step 4 `rc == 0`, comparison on stdout, stderr empty; `home_b/index.sqlite` exists with `meta.home` = resolved `home_b`; step 5 values equal step 2 (A's index untouched). Oracle: files and meta rows, not rc alone.

### TC-ST-03 · CI-011-16 · CON-011 v5
- File: console/tests/test_compare_cli.py · marker `# rule: CON-011`
- States: S0 "old index: no `home`, `repo_root` rows" -> (CLI) refused, S0 unchanged -> (console start: `Store()`) S1 "rows written, derived rows kept" -> (CLI) rc 0.
- Fixture: `env`; logs with keys `EXP1-AAA`, `EXP1-BBB`. Build the index with `main(["EXP1-AAA","EXP1-BBB"])` once, then with `sqlite3` (tmp file only) `DELETE FROM meta WHERE k IN ('home','repo_root')`. Record the `runs` count.
- Steps: 1. Record sha256 (index.sqlite, -wal when present), `user_version`, all `meta` rows. 2. `rc = main(["EXP1-AAA","EXP1-BBB"])`. 3. Record again. 4. Open `Store()` (env-driven paths) and let it finish opening. 5. Read `meta` rows and the `runs` count. 6. `main(["EXP1-AAA","EXP1-BBB"])`.
- Expected: step 2: `rc == 2`; stdout empty; stderr exactly one line `compare: refused: the index at <db_path> does not record its console home, checkout; start the console once with this checkout, then retry (nothing written)` (db_path = `env.home/index.sqlite`; change.md "CLI index"); step 3 equals step 1. Step 5: `home` and `repo_root` present, `runs` count equal to before (no reset). Step 6: rc 0, comparison printed, stderr empty.

### TC-ST-04 · CI-022-01 · CON-022 v11
- File: console/tests/test_compare.py · marker `# rule: CON-022`
- Sequence in one main file (rule example 1): typed 0; assistant stop with AskUserQuestion tool_use (id `ask1`) at 10; AskUserQuestion answer = `tool_result("ask1", err=False)` at 310; stop (end_turn) at 400; task notification at 450; stop (end_turn) at 500; typed 1100. End.
- Transitions: stop at 10 -> gap end 310 (gap 300); stop 400, stop 500 (latest stop after previous gap end is 500); gap end 1100 (gap 600).
- Expected: `time_s.wait` = 900 (300 + 600). The 400 s stop adds nothing; the notification closes nothing.

### TC-ST-05 · CI-022-02 · CON-022 v11
- File: console/tests/test_compare.py · marker `# rule: CON-022`
- Sequence: typed 0; stop with AskUserQuestion (id `ask1`) at 10; dismissal `tool_result("ask1", err=True)` at 40 with content text "The user doesn't want to proceed with this tool use"; typed 400.
- Expected: `time_s.wait` = 390 (gap from the 10 s stop to the typed message; the dismissal at 40 ends no gap).

### TC-ST-06 · CI-022-03 · CON-022 v11
- File: console/tests/test_compare.py · marker `# rule: CON-022`
- Sequence: typed 0; assistant record at 10 with `tool_use("bash1", "Bash", command="x")`; rejection `tool_result("bash1", err=True)` at 40 with text "The user doesn't want to proceed with this tool use"; typed 400.
- Expected: `time_s.wait` = 390 (gap starts at the assistant record holding the tool_use, 10 s, not at the rejection at 40 s; Q-035; gap ends at the typed message).

### TC-ST-07 · CI-022-04 · CON-022 v11
- File: console/tests/test_compare.py · marker `# rule: CON-022`
- Sequence: typed 0; stop (end_turn) at 100; typed 400. End.
- Expected: `time_s.wait` = 300 (exactly one gap).
- Primary move only. The four variants are their own cases below (same coverage item CI-022-04, one move each).

### TC-ST-07a · CI-022-04 · CON-022 v11 (negative)
- File/marker as TC-ST-07. Sequence: typed 0; assistant record at 100 with `stop_reason` "tool_use" (not end_turn); typed 400.
- Expected: `time_s.wait` = 0 (Q-036; no stop, no gap).

### TC-ST-07b · CI-022-04 · CON-022 v11 (negative)
- File/marker as TC-ST-07. Sequence: typed 0; assistant record at 100 with `stop_reason` "stop_sequence"; typed 400.
- Expected: `time_s.wait` = 0 (Q-036).

### TC-ST-07c · CI-022-04 · CON-022 v11 (negative)
- File/marker as TC-ST-07. Sequence: typed 0; stop (end_turn) at 100; a user record with `isMeta: True`, no origin, plain text, at 400 (instead of a typed message); no further typed message.
- Expected: `time_s.wait` = 0 (Q-037: an isMeta record ends no gap).

### TC-ST-07d · CI-022-04 · CON-022 v11
- File/marker as TC-ST-07. Sequence: as 07c, then typed 700.
- Expected: `time_s.wait` = 600 (gap from 100 to 700; the isMeta record at 400 ended nothing).

### TC-ST-08 · CI-022-05 · CON-022 v11
- File: console/tests/test_compare.py · marker `# rule: CON-022`
- Sequence: typed 0; stop (end_turn) at 100; typed 400 (gap 300); stop (end_turn) at 500; file ends.
- Expected: `time_s.wait` = 300. The 500 s stop adds 0. Second variant in the same test: typed 0 and a stop at 100 only -> `time_s.wait` = 0, a number (a main session exists, so not "no main session").

### TC-ST-09 · CI-022-22 · CON-022 v11
- File: console/tests/test_compare.py · marker `# rule: CON-022`
- Fixture: two main files `S1.jsonl`, `S2.jsonl`, both carrying key `EXP1-WWW`.
- File 1: typed 0; stop `uA` (end_turn) at 100; typed 400; stop `uB` (end_turn) at 500. End.
- File 2 (resume): the same four records copied unchanged (same uuids), then typed at 2000.
- Gaps: file 1: 300 s. File 2: stop uA -> 400 = 300 s (same gap, once); stop uB -> 2000 = 1500 s.
- Expected: `time_s.wait` = 1800 (not 2100, not 600); `main_sessions` = 2. Matches the rule's resumed-session example.

### TC-ST-10 · CI-022-28 · CON-022 v11
- File: console/tests/test_compare.py · marker `# rule: CON-022`
- Fixture: files `S1.jsonl`, `S2.jsonl`, key `EXP1-WWW`.
- File 1: typed 0; stop `uA` (end_turn) at 500. Ends (no gap end).
- File 2: copies typed 0 and stop `uA` (same uuid), then typed at 2000.
- Expected: `time_s.wait` = 1500 (one gap, counted once: not 0, not 3000). The stop in file 1 is not closed by file 2; the copy in file 2 is.

### TC-ST-11 · CI-022-30 · CON-022 v11 (now in the statement; Q-034)
- File: console/tests/test_compare.py · marker `# rule: CON-022`
- Sequence in ONE main file (rule example): typed 0; stop record `uA` (end_turn, message id `M1`, `requestId` `R1`) at 100; typed 400; stop record `uB` (end_turn, same `M1` and `R1`, different uuid `uB`) at 500; typed 1100. Set `rec["message"]["id"] = "M1"` and `rec["requestId"] = "R1"` on both stops.
- Expected: `time_s.wait` = 300 (same gap, earliest gap end counts; not 900). Negative variant (one move): `uB` has a different message id/requestId (`M2`/`R2`) -> wait 900.

## CL cases (3 coverage items)

### TC-CL-01 · CI-018-05 · CON-018 v2
- File: no new test required; checklist run by the checker. Optional automated form: console/tests/test_pricing.py, marker `# rule: CON-018`.
- Check: `git diff --exit-code 0891a04 -- console/pricing.yaml` (read-only git, repo root). Optional test form compares sha256 of `console/pricing.yaml` with `git show 0891a04:console/pricing.yaml`.
- Expected: exit 0, no diff.

### TC-CL-02 · CI-031-01 · CON-031 v2
- File: console/tests/test_compare_cli.py (automated part) plus a review check · marker `# rule: CON-031`
- Check 1: `git diff --name-only 0891a04` lists no `console/requirements*.txt`, no `pyproject*`, no lockfile.
- Check 2 (automated): parse each new module (`compare.py`, `compare_format.py`, `compare_cli.py`, `compare_page.py`; B1) with `ast`; every top-level import name is in `sys.stdlib_module_names`, or is the package itself (`agent_console` / relative import) / `agent_scoring` / a package listed in `console/requirements.txt` at 0891a04.
- Expected: check 1 empty; check 2 finds no other import.

### TC-CL-03 · CI-032-01 · CON-032 v3
- File: existing suites (no new file) · marker `# rule: CON-032` on the new store/meta tests.
- Designers run no full suite. The lead QA runs the full suites once at the gate (commands from PROJECT.md: in `console/`: `.venv/bin/python -m pytest tests -q -p no:cacheprovider`; repo root: `console/.venv/bin/python -m pytest tests kit/tests -q -p no:cacheprovider`; `console/.venv/bin/python -m ruff check .`).
- Expected at the gate: console suite 0 failed and passed >= 445 (baseline 445 + new tests); install tools and kit suite 0 failed, 49 passed; ruff "All checks passed". Designer-side check, read-only: `git diff 0891a04 -- console/tests` removes or edits no existing assertion (additions only, except an explicitly listed rule change).

## Questions (closed list)
- Q1 (TC-ST-11, same gap inside one file): ANSWERED, Q-034 (CON-022 v11 statement, CI-022-30; 300 s). The "builder stops and asks" clause is dropped.
- Q2 (TC-ST-06, gap start of a rejected prompt): ANSWERED, Q-035 (gap starts at the assistant record holding the tool_use; 390 s).
- Q3 (compare data function name and CLI entry): ANSWERED, Interfaces for tests B1 (`compare.compare(db, pricing, a, b)`, `compare_cli.main(argv) -> int`, `__main__` route).
- Q4 (how end_turn shows in a record): ANSWERED, Q-036 (`message.stop_reason == "end_turn"`; `tool_use` and `stop_sequence` are not stops).
- Q5 (isMeta user records, added in this pass): ANSWERED, Q-037 (any isMeta user record ends no gap); covered by TC-ST-07c, TC-ST-07d.
- Still open: none. Residual note: exact signatures of the conftest `assistant` helper for setting message id / requestId are not in the Interfaces section; the cases set them on the record after the call (`rec["message"]["id"]`, `rec["requestId"]`). Builder confirms the field paths when writing the test; no behaviour assumed.

Total: 18 cases (10 ST coverage items + CI-022-30 + 3 CL + 4 split variants TC-ST-07a..d of CI-022-04).
