Lead QA sign-off 2026-11-05: test design APPROVED (EXP1-R22C; re-check of EP-018-01, EP-018-02, EP-018-04, EP-019-01 passed; design approval 1 notes stay open for the automation engineer).

# EXP1-R22C · test cases, boundary values (test designer BVA, 2026-11-05)

Main goal: one draft case per BVA coverage item of qa.md (31). Status of every case: `draft`. Base 0891a04, branch exp1/r22. No product code written.
Gates: `test_case_files`, `timing_check`: not declared in PROJECT.md, skipped (cases live in this file). `test_strategy`: none.
Rule versions used (update pass 2, checked against console.md): CON-011 v5, CON-014 v7, CON-015 v8, CON-018 v2, CON-022 v11, CON-027 v6, CON-034 v4; CON-012 v1, CON-016 v5, CON-019 v1, CON-020 v2, CON-023 v1, CON-024 v2, CON-026 v4, CON-028 v1, CON-029 v7, CON-033 v1. (CON-011/015/027/034 are not the subject of a BVA case; listed for the traceability of the shared setup.)
Update pass 2: interfaces from change.md "Interfaces for tests" (B1..B8) applied; open points settled by Q-034..Q-040. Return round 1 (design-check1 items 8, 10, 11): BVA-001 DROPPED (tombstone); BVA-006 split into BVA-006 and BVA-006b (same item CI-020-04); BVA-012 merged into BVA-030 (cites CI-029-17 and CI-024-06). Live BVA cases: 29 plus 006b; 31 items, 1 dropped.
Tier proposal (no strategy declared): the whole new suite = full regression for this ticket (High risk); smoke subset = BVA-007, 008 (60 s edge), BVA-016, 019, 026 (rounding ties), BVA-031 (Host edge).

## Common setup (referred to as FX-... in the cases)
- Every test uses the `env` fixture (tmp AGENT_CONSOLE_HOME, LOG_ROOT, REPO, NO_FETCH=1, TZ Europe/Madrid). Logs are written into tmp with the conftest helpers. console/tests/fixtures is read-only. Never ~/.agent-console or ~/.claude. No live clock: every time comes from record timestamps. `compare` code reads no clock.
- FX-IDX: build the index with `Store()` then `store.ingest()` (as test_server.py). FX-JSON(K1, K2): `db = store.reader()`; `tree = compare.compare(db, pricing, K1, K2)`; `db.close()` in `finally` (`pricing = Pricing.load(config.pricing_path())`). `DATA(K) = compare.compare(db, pr, K, K)["a"]`. JSON-level assertions use the tree (raw numbers; `60` and `60.0` equal; integers stay integers); `compare.to_json(tree)` (`json.dumps(sort_keys=True, indent=2)`) is used where bytes matter. `compare` does not check unknown keys (an unknown key gives zeros); `compare.unknown_keys(db, a, b)` is the check.
- FX-PAGE: `TestClient(server.create_app(store=store, pricing=Pricing.load(config.pricing_path()), port=8790), base_url="http://127.0.0.1:8790")`. FX-CLI: `rc = compare_cli.main([a, b])` in-process with `capsys`; assert `rc` and `capsys.readouterr()`. `main` never calls `sys.exit` (Interfaces B1).
- Row selectors (Interfaces B2). Page: `tr[data-row="<id>"]`, id = JSON path (e.g. `time_s.wait`, `cost_usd.unpriced_messages`, `cost_share`, `runs.total`, `cost_usd.by_model.<m>`); cell `td.a` / `td.b`; diff cell `td.d` with `span.diff` and `span.ratio`, reading `diff (ratio)`. CLI text: `compare_format.text_table(tree)` lines; split a line on `|`, strip each part; first part = row label (Wall time, Main-session wait time, Main-session wait time from gaps over 2 h, Role runs, Unpriced messages, Cost share (main / sub-agents), Cost, ...); columns: label, a, b, `diff (ratio)`. Also `compare_format.rows(tree)` gives `Row(id, label, a, b, diff, ratio)` already formatted; one assertion may read it instead of parsing HTML.
- FX-PRICE (priced): rewrite `env.tmp/"pricing.yaml"` before `Pricing.load` with `"regional_multiplier: 1.0\nmodels:\n  sonnet-5-5: {input: 2.00, output: 10.00, cache_write_5m: 2.50, cache_write_1h: 4.00, cache_read: 0.20}\n"` (Interfaces B6). The `env` default is `models: {}` (every message unpriced). Default `assistant()` model `claude-sonnet-5-5` with `usage()` (input 10, output 20) is then priced, cost = (10*2.00 + 20*10.00)/1e6 = 0.00022 (assert `pytest.approx`). Model `claude-unpriced-x` matches no key and no tier (no `tier_defaults`): unpriced.
- FX-MAIN(key, ...): main session file `env.root/PROJECT/S1.jsonl`; first record `user_prompt("[<key>] start", t=0)` (a leading `[KEY]` is authoritative, CON-001), so `ticket_eff == key`, `main_sessions == 1`.
- FX-STOP: an assistant record (helper `assistant(id, t=...)`) whose `message["stop_reason"]` is set to `"end_turn"` after the helper returns (the helper has no argument for it). FX-TYPED: `user_prompt("continue", t=...)` with `rec["origin"] = {"kind": "human"}` added (record shape of CON-022 v11 log markers; FX-STOP = `message.stop_reason == "end_turn"`, Q-036).
- Text assertions: "the cell of that row for that side equals exactly this string" (selectors above; layout settled by Interfaces B2, so Q-B is closed). Formatter cases call `compare_format.tokens/usd/minutes/ratio/count` directly (names from Interfaces B1).
- Rounding (Interfaces B1): `Decimal(str(v))`, `ROUND_HALF_UP` on the absolute value, sign added only when the rounded size is not zero. Expected strings below follow that; no `+` on a positive difference.
- Long gaps: local helper `at(n)` in the test module (Interfaces B7): `(datetime(2026,10,20,10,0,0,tzinfo=timezone.utc)+timedelta(seconds=n)).strftime("%Y-%m-%dT%H:%M:%S.000Z")`. `assistant(..., day=at(n))`; for `user_prompt`, `tool_result`, `api_error` set `rec["timestamp"] = at(n)` after the call and keep a distinct `t`. `at(n) == ts(n)` for n < 3600. Replaces the explicit ISO strings in BVA-009/010.

## Cases

### BVA-001 · CI-012-03 · CON-012 v1 · test_compare.py  # rule: CON-012
- STATUS: DROPPED (tombstone, id kept). Reason: after Q-039 no period edge exists; the comparison reads no clock or period, so there is no value pair on either side of a boundary. "An old record still counts" is already covered by EP-012-01 (CI-012-03 is merged there). No test is written from this block; it does not count as a BVA item (BVA items now 30).

### BVA-002 · CI-014-08 · CON-014 v7 · test_compare.py  # rule: CON-014
- Boundary: the parent session's key changes at t = 60 s; spawn calls at 59 s (just before), 60 s (same instant), 61 s (just after). CON-014 v7 / Q-040: the newest evidence at or before the spawn timestamp counts, so same-instant evidence gives the new key.
- Fixture: one main session S1 with NO ticket of its own that matters (first prompt without a key). Evidence by path (store.py:433): `assistant` record at t=10 with a `Write` tool_use `tool_use("w1","Write", file_path="/work/app/docs/EXP1-201-notes.md", content="x")`; at t=60 a `Write` with `file_path="/work/app/docs/EXP1-202-notes.md"`. Three spawns, none with a run file: `tool_use("sp1","Agent", subagent_type="builder", description="x", prompt="p")` in an assistant record at t=59, `sp2` at t=60, `sp3` at t=61 (no key in description or prompt, so no spawn_lead/spawn_text). Each has a `tool_result("spN", err=True, t=...)` after it (error result = counted).
- Steps: FX-IDX; FX-JSON a = `EXP1-201`, b = `EXP1-202`.
- Expected: `a.runs.total == 1`, `a.runs.failed == 1` (sp1); `b.runs.total == 2`, `b.runs.failed == 2` (sp2, sp3). `a.runs.repeat_rounds == 0`, `b.runs.repeat_rounds == 1` (same role `builder`, second spawn by spawn ts). Not asserted: main_sessions of the two keys (the parent's own key is not the point).
- Oracle: JSON counts per ticket.
- Note: the equal-timestamp side (sp2 -> `EXP1-202`) is now rule text (Q-040, CON-014 v7), no longer an open point.

### BVA-003 · CI-016-08 · CON-016 v5 · test_compare.py  # rule: CON-016
- Boundary: two runs of one role with equal start timestamp (the order is decided by `ORDER BY start_ts, run_id`).
- Fixture: main `FX-MAIN("EXP1-100")`, assistant at t=1 with two Agent tool_uses `tA`, `tB` (`subagent_type="reviewer"`); `add_sub(env.root,"S1","a1","reviewer",[...],"tA")` and `add_sub(..."a2","reviewer",[...],"tB")`, both with records at t=5 (same first timestamp) and t=9, each with an `assistant` reply and a final text.
- Steps: FX-IDX; FX-JSON for a = b = `EXP1-100`; build the JSON twice from the same index and compare.
- Expected: `a.runs.total == 2`, `a.runs.repeat_rounds == 1` (not 0, not 2); the two JSON strings are byte-identical.
- Oracle: JSON value and byte equality.

### BVA-004 · CI-019-02 · CON-019 v1 · test_compare.py  # rule: CON-019
- Boundary: 0 unpriced messages (lower edge).
- Fixture: FX-PRICE; `FX-MAIN("EXP1-100")` plus one assistant message `m1` model `claude-sonnet-5-5`, `usage(10,20)`, t=2. Only priced messages.
- Steps: FX-IDX; FX-JSON a = b = `EXP1-100`; page and CLI text for the same pair.
- Expected: `a.cost_usd.unpriced_messages == 0` (integer 0, not missing, not `null`, not a string); `a.cost_usd.total == approx(0.00022)`. Page row `cost_usd.unpriced_messages`, `td.a` and `td.b` == `0` (`compare_format.count(0)`); CLI line "Unpriced messages" cells `0`; the row sits directly after `Cost` (Interfaces B2).
- Oracle: JSON value, page body, CLI stdout.

### BVA-005 · CI-019-03 · CON-019 v1 · test_compare.py  # rule: CON-019
- Boundary: 1 unpriced message (just above the edge).
- Fixture: as BVA-004, plus one more assistant message `m2` with model `claude-unpriced-x`, `usage(10,20)`, t=3.
- Steps: as BVA-004.
- Expected: `a.cost_usd.unpriced_messages == 1` (integer); `a.cost_usd.total == approx(0.00022)` (the unpriced message adds exactly 0); `a.tokens.total.input == 20`, `a.tokens.total.output == 40` (the unpriced message still has its tokens). Page row `cost_usd.unpriced_messages` `td.a` == `1`; CLI "Unpriced messages" cell `1`.
- Also (Q-038, CON-018 v2): `a.cost_usd.by_model["claude-unpriced-x"] == 0` (key present, number 0) and `a.cost_usd.by_model["claude-sonnet-5-5"] == approx(0.00022)`; `a.tokens.by_model` lists both models; page row `cost_usd.by_model.claude-unpriced-x` `td.a` == `$0.00`. Absence of the key is the failure.
- Oracle: JSON values, page body, CLI stdout.

### BVA-006 · CI-020-04 · CON-020 v2 · test_compare.py  # rule: CON-020
- Boundary (primary move): no timestamp at all (the lower edge of the wall span). Variant B is its own case, BVA-006b.
- Fixture: a main session file with key `EXP1-100` (`user_prompt("[EXP1-100] start")`) and one assistant record, from which the `timestamp` field is deleted (`del rec["timestamp"]`) in every record; no sub-agents.
- Steps: FX-IDX; FX-JSON for a = b = `EXP1-100`.
- Expected: `a.time_s.wall == 0`, `a.time_s.active_role == 0` (numbers, not labels).
- Oracle: JSON values (`compare.compare(...)` tree). The fixture is indexable: the Store keeps a session with no timestamps (runs row, `start_ts`/`end_ts` NULL, usage `ts` NULL; Interfaces B8), so this case runs at comparison level. The comparison must skip NULL timestamps (NULL sorts first in `ORDER BY start_ts`): a NULL leaking into wall (error or non-zero) is the failure.

### BVA-006b · CI-020-04 (same coverage item as BVA-006, second variant) · CON-020 v2 · test_compare.py  # rule: CON-020
- Boundary: no timestamp at all, for a ticket whose only evidence is a failed spawn (no run file, no session of its own).
- Fixture: a main session S2 with key `EXP1-299` (with timestamps) and an Agent spawn whose `description="EXP1-300 build"` (spawn_text key), `tool_result(..., err=True)`, no run file; the ticket `EXP1-300` has no session file of its own.
- Steps: FX-IDX; FX-JSON for a = b = `EXP1-300`.
- Expected: `a.time_s.wall == 0`, `a.time_s.active_role == 0`, `a.runs.total == 1`, `a.runs.failed == 1`, `a.main_sessions == 0`.
- Oracle: JSON values, asserted on the `compare.compare` tree only (it does not check unknown keys, B1); no page/CLI call, so whether `EXP1-300` counts as known (CON-027) does not matter here.

### BVA-007 · CI-022-14 · CON-022 v11 · test_compare.py  # rule: CON-022
- Boundary: gap of 59 s (one below the 60 s edge).
- Fixture: `FX-MAIN("EXP1-100")` (typed message at t=0); FX-STOP assistant at t=100; FX-TYPED at t=159. No other records.
- Steps: FX-IDX; FX-JSON a = b = `EXP1-100`; page/CLI text.
- Expected: `a.time_s.wait == 0` and `a.time_s.wait_over_2h == 0` (numbers, not "no main session"). Page row `time_s.wait` `td.a` == `0 min` (`minutes(0)`); row `time_s.wait_over_2h` `td.a` == `0 min`.
- Oracle: JSON, page/CLI text.

### BVA-008 · CI-022-15 · CON-022 v11 · test_compare.py  # rule: CON-022
- Boundary: gap of exactly 60 s (the edge counts).
- Fixture: as BVA-007 with FX-TYPED at t=160 (gap 60 s from the stop at t=100).
- Expected: `a.time_s.wait == 60`, `a.time_s.wait_over_2h == 0`. Page row `time_s.wait` `td.a` == `1 min`.
- Oracle: JSON, page/CLI text.

### BVA-009 · CI-023-01 · CON-023 v1 · test_compare.py  # rule: CON-023
- Boundary: gap of exactly 7200 s (not over 2 hours).
- Fixture: `FX-MAIN("EXP1-100")` (typed message at `at(0)`); FX-STOP at `at(100)` (`day=at(100)`); FX-TYPED at `at(7300)` (`rec["timestamp"] = at(7300)`, gap 7200 s).
- Expected: `a.time_s.wait == 7200`, `a.time_s.wait_over_2h == 0` (gaps over 2 hours count in full, 7200 is not over). Page: row `time_s.wait` `td.a` == `120 min`, row `time_s.wait_over_2h` `td.a` == `0 min`.
- Oracle: JSON, page/CLI text.

### BVA-010 · CI-023-02 · CON-023 v1 · test_compare.py  # rule: CON-023
- Boundary: gap of 7201 s (one over the edge).
- Fixture: as BVA-009 with FX-TYPED at `at(7301)`.
- Expected: `a.time_s.wait == 7201`, `a.time_s.wait_over_2h == 7201` (in full, not 1). Page: row `time_s.wait` `td.a` == `120 min`, row `time_s.wait_over_2h` `td.a` == `120 min` (7201 s = 120.02 min; `minutes(7201) == "120 min"`).
- Oracle: JSON, page/CLI text.

### BVA-011 · CI-024-05 · CON-024 v2 · test_compare.py  # rule: CON-024
- Boundary: main-session cost exactly 0 with sub-agent cost above 0 (a number, not a label).
- Fixture: FX-PRICE; `FX-MAIN("EXP1-100")` with one assistant message `usage(0,0)` model `claude-sonnet-5-5` (cost 0.0); one sub-agent run (key `EXP1-100` via spawn description, `add_sub`) with one message `usage(10,20)` (cost 0.00022).
- Expected: `a.cost_usd.main == 0` (number), `a.cost_usd.total == approx(0.00022)`, `a.cost_share == 0` (number, not a string, not "no sub-agents", not "no main session"). Page row `cost_share` `td.a` == `0.00` (`ratio(0)`); `td.a` is not the label `no main session`.
- Oracle: JSON, page/CLI text.

### BVA-012 · CI-024-06 · CON-024 v2, CON-029 v7 · test_compare_format.py  # rule: CON-024
- MERGED into BVA-030 (duplicate: both assert `ratio(0.125) == "0.13"`, one function for ratio and share, CON-029). The share-specific exact value `ratio(0.25) == "0.25"` (no `%`, no `25`) moved to BVA-030. Coverage item CI-024-06 is covered by BVA-030. No separate test.

### BVA-013 · CI-026-07 · CON-026 v4, CON-029 v7 · test_compare.py, test_compare_format.py  # rule: CON-026
- Boundary: ratio b/a at a .5 tie, 2 decimals, away from zero.
- Fixture (compare level): two tickets from tmp logs: `EXP1-100` with 8 sub-agent runs, `EXP1-101` with 1 run (ratio of runs.total 1/8 = 0.125); a third pair `EXP1-102` with 8 runs and `EXP1-103` with 17 runs (17/8 = 2.125). (Runs: `add_sub` with distinct agent ids and spawn ids, role `builder`.)
- Steps: FX-JSON for (`EXP1-100`,`EXP1-101`) and (`EXP1-102`,`EXP1-103`); `compare_format.ratio` on the raw ratio; page/CLI text of the same pairs.
- Expected: `diff.runs.total.ratio == 0.125` and `diff.runs.total.diff == -7`; `ratio(0.125) == "0.13"`; page row `runs.total` `td.d span.ratio` == `0.13` and `span.diff` == `-7` (`count(-7)`); CLI line "Role runs" last cell `-7 (0.13)`. Second pair: `diff.runs.total.ratio == 2.125`, `diff == 9`; `span.ratio` == `2.13`, `span.diff` == `9` (no `+`; Python `round` would give `2.12`).
- Oracle: JSON raw values; formatter and page/CLI strings.

### BVA-014 · CI-028-02 · CON-028 v1, CON-026 v4 · test_compare.py  # rule: CON-028
- Boundary: same key as a and b where a figure is 0 (ratio denominator 0), next to a figure of 1.
- Fixture: `FX-MAIN("EXP1-100")` with one sub-agent run that completed (final text), no spawn failures, no unpriced messages (FX-PRICE).
- Steps: FX-JSON a = b = `EXP1-100`.
- Expected: `diff.runs.failed == {"diff": 0, "ratio": "n/a"}` (a = 0); `diff.cost_usd.unpriced_messages == {"diff": 0, "ratio": "n/a"}`; `diff.runs.total == {"diff": 0, "ratio": 1}` (a = 1, `ratio` 1 or 1.0). Same JSON bytes for `a` and `b` objects. Page row `runs.failed`: `span.diff` == `0`, `span.ratio` == `n/a` (label returned unchanged by `compare_format.ratio("n/a")`).
- Oracle: JSON values.

### BVA-015 · CI-029-01 · CON-029 v7 · test_compare_format.py  # rule: CON-029
- Boundary: tokens 499 (one below the .5 tie). Input `499` -> `0k`.

### BVA-016 · CI-029-02 · CON-029 v7 · test_compare_format.py  # rule: CON-029
- Boundary: tokens 500 (the tie). Input `500` -> `1k` (not `0k`: `round(0.5)` gives 0).

### BVA-017 · CI-029-03 · CON-029 v7 · test_compare_format.py  # rule: CON-029
- Boundary: tokens above 1 000 000, no separator. Input `1234567` -> `1235k` (1234.567 rounded; no `1,235k`).

### BVA-018 · CI-029-04 · CON-029 v7 · test_compare_format.py  # rule: CON-029
- Boundary: negative token value that rounds to zero. Input `-400` -> `0k` (never `-0k`).

### BVA-019 · CI-029-05 · CON-029 v7 · test_compare_format.py  # rule: CON-029
- Boundary: negative token tie, sign kept. Input `-500` -> `-1k` (size rounded away from zero).

### BVA-020 · CI-029-06 · CON-029 v7 · test_compare_format.py  # rule: CON-029
- Boundary: dollars at the half-cent tie. Input `0.005` -> `$0.01`.

### BVA-021 · CI-029-07 · CON-029 v7 · test_compare_format.py  # rule: CON-029
- Boundary: negative dollars that round to zero. Input `-0.004` -> `$0.00` (no sign).

### BVA-022 · CI-029-08 · CON-029 v7 · test_compare_format.py  # rule: CON-029
- Boundary: negative dollars, sign before the dollar sign. Input `-1.234` -> `-$1.23`.

### BVA-023 · CI-029-09 · CON-029 v7 · test_compare_format.py  # rule: CON-029
- Boundary: dollars of 1000 or more, no thousands separator. Input `1234.56` -> `$1234.56`.

### BVA-024 · CI-029-10 · CON-029 v7 · test_compare_format.py  # rule: CON-029
- Boundary: negative dollar tie. Input `-0.005` -> `-$0.01`.

### BVA-025 · CI-029-11 · CON-029 v7 · test_compare_format.py  # rule: CON-029
- Boundary: time 29 s (below the 30 s tie). Input `29` -> `0 min`.

### BVA-026 · CI-029-12 · CON-029 v7 · test_compare_format.py  # rule: CON-029
- Boundary: time 30 s (the tie). Input `30` -> `1 min`.

### BVA-027 · CI-029-13 · CON-029 v7 · test_compare_format.py  # rule: CON-029
- Boundary: time 0. Input `0` -> `0 min` (never a bare `0`).

### BVA-028 · CI-029-14 · CON-029 v7 · test_compare_format.py  # rule: CON-029
- Boundary: negative time that rounds to zero. Input `-20` -> `0 min` (no sign).

### BVA-029 · CI-029-15 · CON-029 v7 · test_compare_format.py  # rule: CON-029
- Boundary: time of an hour or more stays in minutes. Input `8100` -> `135 min` (not `2.25 h`, not `2 h`).

For BVA-015 to BVA-029 (formatter cases): target `console/tests/test_compare_format.py`; fixture: none (pure function, no `env`, no files, no clock); steps: call `compare_format.tokens` (BVA-015..019), `compare_format.usd` (020..024) or `compare_format.minutes` (025..029) with the input given, in the type the compare code passes (integers for tokens, floats for dollars and seconds; the same value also tested as `float` for tokens; `int | float | str` accepted, a str label returned unchanged); expected: exactly the string given; oracle: the returned string (no page needed: one module serves page and CLI, CI-029-16). Each case carries its marker `# rule: CON-029`. Rounding as in Common setup (Decimal ROUND_HALF_UP, zero result unsigned). Interfaces B1 confirms `tokens(-400)=="0k"`, `minutes(30)=="1 min"`, `minutes(-20)=="0 min"`, `minutes(8100)=="135 min"`, `usd(0.125)=="$0.13"`, `usd(-0.004)=="$0.00"`, `usd(1234.56)=="$1234.56"`.

### BVA-030 · CI-029-17 and CI-024-06 (BVA-012 merged here) · CON-029 v7, CON-024 v2 · test_compare_format.py  # rule: CON-029
- Boundary: the ratio/share tie. `compare_format.ratio(0.125) == "0.13"` (Python `round(0.125, 2)` would give `0.12`; ROUND_HALF_UP on `Decimal(str(v))`); asserted once for both items. Fixture and oracle as BVA-015. Also `ratio(2.125) == "2.13"`, `ratio(0.005) == "0.01"`, `ratio(0.124) == "0.12"` (one below the tie), and the share exact value `ratio(0.25) == "0.25"` (no `%`, no `25`).

### BVA-031 · CI-033-03 · CON-033 v1 · test_compare_page.py  # rule: CON-033
- Boundary: right host name, port one off. App port = 8790.
- Fixture: FX-IDX with a known key `EXP1-100` (FX-MAIN) so a good request would be 200; FX-PAGE (`create_app(..., port=8790)`).
- Steps: `GET /compare?a=EXP1-100&b=EXP1-100` with headers `host` = `127.0.0.1:8789`, `127.0.0.1:8791`, `localhost:8791`, `127.0.0.1` (no port); then with `127.0.0.1:8790` and `localhost:8790` as control.
- Expected: each wrong-port request: status 404 and body JSON `{"detail": "Not found."}` (the Host guard answers, not the compare page); no `<html` in the body; the compare code is not reached (no figures). Control requests: status 200 and the HTML page.
- Oracle: status and body (status code alone is not enough, lead QA note).

## Not made exact: questions for the lead QA or the builder
Status after update pass 2:
- Q-A: ANSWERED (Interfaces B1): `compare_cli.main(argv) -> int`, never `sys.exit`; cases assert the return value with `capsys`.
- Q-B: ANSWERED (Interfaces B2): row ids `data-row`, labels, `td.a/b/d`, `span.diff/ratio`, CLI `|`-split lines, unpriced count in its own row after `Cost`.
- Q-C: ANSWERED (Q-040, CON-014 v7): same-instant evidence gives the new key; sp2 -> `EXP1-202` is exact.
- Q-D: ANSWERED (Q-038, CON-018 v2): unpriced model listed in `by_model` with 0; BVA-005 asserts it.
- Q-E: ANSWERED (Q-039, CON-012 note): no period edge exists; BVA-001 loses its boundary, PROPOSED DROP (lead QA to confirm; coverage CI-012-03 moves to the plain "old record counts" case).
- Q-F: ANSWERED (Interfaces B8): the Store keeps a session with no timestamps; BVA-006 fixture A stays at comparison level.
- Formatter names: ANSWERED (Interfaces B1): `compare_format.tokens/usd/minutes/ratio/count`.
- STILL OPEN: none blocking. One unverified assumption for the builder: BVA-006 fixture B (`EXP1-300` has only a failed spawn, no session of its own) is asserted on the `compare.compare` tree only; its "known key" status (CON-027) is not tested here. Cost labels for the CLI "Cost share (main / sub-agents)" row come from Interfaces B2 as written.
