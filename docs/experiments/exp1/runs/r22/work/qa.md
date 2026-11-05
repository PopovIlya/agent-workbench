# EXP1-R22C · QA analysis (DoR part 3, QA analyst, 2026-11-05)

Main goal: make every rule testable and list what the test designers must cover; set the risk; close the gaps.
Base: 0891a04, branch exp1/r22. Linked from change.md.
Gates: `impact_map`, `test_case_files`, `rule_guards`, `test_selection`, `coverage_report`: not declared in PROJECT.md, skipped (no area-to-set map; connected areas are in change.md "Connected areas").
`test_strategy`: none (no binding strategy; ISTQB techniques below).

## Ticket size and risk
- Ticket size: **High** (answer 23 "size L accepted"; 26 new rules, 4 new modules, shared index writes).
- Ticket risk class: **High**. Drivers: CON-011 writes the person's shared index (guard must leave it byte-identical on refusal); CON-033 / CON-035 new HTTP route echoing input and raw-log reading (security review, answer 23); CON-015 / CON-022 log-marker logic; CON-032 shared code (`Store.rebuild` refactor, `Store.__init__` meta rows, `__main__` entry of start.sh and the LaunchAgent).
- Per rule (field `risk` in docs/requirements/console.md): high: 011, 012, 013, 015, 018, 022, 032, 033, 035 · medium: 010, 014, 016, 017, 019, 020, 021, 024, 025, 026, 027, 030, 034 · low: 023, 028, 029, 031.
- Changed by QA: CON-032 medium -> high (v3; shared code reaches every page and the console start). All others confirmed as set.
- CON-001..006 (observed): no own tests (status rule); exercised through CON-013, 014, 017, 018 items.

## Test environment (all items)
- Every test uses the `env` fixture (console/tests/conftest.py: tmp AGENT_CONSOLE_HOME, LOG_ROOT, REPO, NO_FETCH=1, TZ Europe/Madrid, tmp pricing) and logs written into tmp with the conftest helpers (`assistant`, `user_prompt`, `tool_use`, `tool_result`, `api_error`, `add_sub`, `write_jsonl`); recorded logs from console/tests/fixtures are read, never changed. Never ~/.agent-console, never ~/.claude.
- "Console's own home" in a test = the env fixture's AGENT_CONSOLE_HOME. "Another home" = a second tmp folder.
- CI-011-17 removes AGENT_CONSOLE_NO_FETCH with `monkeypatch.delenv` and sets AGENT_CONSOLE_CLAIMS_REPO to a tmp path; CI-015-19 uses chmod 000 in tmp (skip when run as root).
- Files-unchanged evidence (CON-011 refusal): sha256 of index.sqlite and index.sqlite-wal (when present), `PRAGMA user_version`, every `meta` row; index.sqlite-shm left out (change.md).
- Fixture limit (PROJECT.md): no live session or live clock; no item needs one (times come from record timestamps).

## Testability
All 26 new rules are testable. Parts not testable as such, and how they are covered:
- CON-022 "a permission prompt that leaves no trace in the log is not counted": no trace = nothing to feed; covered by the closed list of stops (CI-022-01..05).
- CON-030 "field names must not change after release": a process rule; a key-path snapshot test (CI-030-05) guards it.
- CON-033 "binds 127.0.0.1": `server.main` is unchanged; existing server test plus CI-033-08.
- CON-031 "no new dependencies": checklist (CI-031-01).
- Current rule versions (docs/requirements/console.md, checked 2026-11-05, design check 1 item 9): CON-014 v7, CON-018 v2, CON-022 v11; items below cite these.
- CON-022 v11 match key: testable with tmp logs (CI-022-22..30; v11 adds the same match inside one file, Q-034, CI-022-30). The local logs hold no resumed copy, so which field survives a resume is not confirmed from real data; the items use built records. The v9 mismatch between statement and notes (QA note, round 1) is closed: v10 statement and notes agree (shared uuid OR shared message.id + requestId; timestamp pair only when a stop record has neither); CI-022-24 and CI-022-29 follow it.

## Gap hunt (High ticket) and how each gap is closed
All have a safe default (reversible before merge, consistent with the map): recorded by the QA analyst as Agent decisions (answer 37) in the rules and in QUESTIONS.md. No blocking question.
| Gap | Closed in |
|---|---|
| G1 rr7-sa.md note 2: CON-011 did not state "no index file in the console's own home -> built, exit 0" (rule gap; only in change.md tests) | Q-026, CON-011 v4 statement; CI-011-14 |
| G2 CLI run-time errors (locked, not a database, scan error) had exit 1 only in change.md, no rule | Q-027, CON-011 v4 note, in the statement since v5 (BA, rr8 finding 2); CI-011-20..22 |
| G3 CLI with both keys unknown ("one line naming the key"); same unknown key twice | Q-028, CON-027 v6; CI-027-08, 09 |
| G4 third CLI key; extra or repeated page parameters | Q-029, CON-034 v4; CI-034-11..13 |
| G5 race: a log deleted between two scans (no `log_deleted` row yet) or unreadable at read time | Q-030, CON-015 v8, CON-022 v8; CI-015-18, 19, CI-022-21 |
| G6 two main sessions: may a stop in one close at a typed message in the other | Q-031, CON-022 v8; CI-022-19 |
| G7 broken data: a session file with no record timestamp (store.py first_ts NULL) | Q-032, CON-020 v2, CON-021 v4; CI-020-03, 04, CI-021-04 |
| G8 rr8 finding 1: a resumed main file repeats earlier records, per-file gaps counted twice | Q-033, CON-022 v9, v10 (business analyst); CI-022-22..29 |
Checked, no gap: page precedence 422 > 503 > 404 (change.md APIs; CI-027-13, 14); CLI order usage > refusal > unknown (change.md; CI-027-15); bad JSON lines skipped (parser; CI-015-20); duplicate spawn rows (change.md; CI-014-11); equal start times (ORDER BY; CI-016-08); roles/states of spawns (CON-014 decision table). rr7 note 1 (Q-025 header "v2, v3"): already fixed in QUESTIONS.md.

## Test conditions and coverage items
Techniques: EP = equivalence partitions, BVA = boundary values, DT = decision table, ST = state transition, CL = checklist. One coverage item per testable condition. Test file per change.md "Modules".

### CON-010 (medium) · test_compare_page.py
TC-010-1 side by side with a diff column · TC-010-2 503 during the first index · TC-010-3 the page never rescans
- CI-010-01 EP: index ready, two known keys -> 200, columns a, b, difference.
- CI-010-02 DT: `progress["initial"]` true (even with an unknown key) -> 503, one message, no figures, no unknown-key text.
- CI-010-03 DT: scans == 0 and `runs` empty -> 503.
- CI-010-04 DT: scans == 0, `runs` not empty (index left from an earlier start) -> not 503.
- CI-010-05 DT: scans >= 1, initial false, `runs` empty, unknown key -> 404, not 503.
- CI-010-06 EP: GET /compare never calls `st.rescan` (spy) and the index bytes do not change.

### CON-011 (high) · test_compare_cli.py, test_store_and_flags.py
TC-011-1 same comparison as the page, text and `--json` · TC-011-2 no argv / other argv start the server as today · TC-011-3 guard refusal, nothing written · TC-011-4 matching values refresh · TC-011-5 no index file -> built, exit 0 (rr7 note 2) · TC-011-6 another home = another index · TC-011-7 no git fetch · TC-011-8 run-time index errors (cannot be opened or refreshed): one stderr line naming the error class, stdout empty, exit 1 (CON-011 v5 statement) · TC-011-9 meta rows recorded, not compared by the console · TC-011-10 logs never written
- CI-011-01 EP: `compare A B` -> text with the same rounded strings as the page body (one formatter), exit 0.
- CI-011-02 EP: `compare A B --json` -> JSON on stdout only, exit 0.
- CI-011-03 EP: no argv -> `server.main()` called with no arguments (spy); compare not run.
- CI-011-04 EP: argv not starting with `compare` -> `server.main()` as today.
- CI-011-05 DT: time zone differs -> exit 2, exact "built with another time zone" line, stdout empty, files unchanged.
- CI-011-06 DT: key patterns differ -> same, "key patterns".
- CI-011-07 DT: index built in home A copied to home B, CLI with HOME=B -> "console home".
- CI-011-08 DT: AGENT_CONSOLE_REPO differs -> "checkout".
- CI-011-09 DT: `user_version` != SCHEMA_VERSION -> "schema version".
- CI-011-10 DT: `home` and `repo_root` rows missing, nothing differs -> "does not record its console home, checkout; start the console once ..." line.
- CI-011-11 DT: one differs and one missing -> "built with another" line naming both, fixed order.
- CI-011-12 DT: two differ (time zone, checkout) -> `time zone, checkout` in that order.
- CI-011-13 DT: all match -> refresh runs: a log written after the first build is in the output, exit 0.
- CI-011-14 ST: no index.sqlite in the console's own home -> built there, comparison printed, exit 0 (Q-026; rule gap G1).
- CI-011-15 ST: another home with no index -> built in that home; home A's index sha256 unchanged.
- CI-011-16 ST: old index (no `home`/`repo_root`) -> refused; one `Store()` start (console) -> rows written -> CLI exit 0.
- CI-011-17 EP: CLAIMS_REPO set, NO_FETCH removed -> spy on `subprocess.run` sees no `fetch` argv; NO_FETCH back to its old value after.
- CI-011-18 EP: `Store()` writes `home` = resolved db parent and `repo_root` = resolved repo.
- CI-011-19 EP: `Store()` with other recorded `home`/`repo_root` rows -> no reset of derived rows (run count kept), rows overwritten.
- CI-011-20 EP: `Store()` raises `sqlite3.OperationalError` (locked) -> one stderr line naming the error class, stdout empty, exit 1 (Q-027, v5).
- CI-011-21 EP: index.sqlite is not a database -> read-only open fails -> one stderr line naming the error class, stdout empty, exit 1, file unchanged (v5).
- CI-011-22 EP: scan ends with `progress["state"] == "error"` -> one line naming the class only, exit 1.
- CI-011-23 EP: sha256 of every tmp log file equal before and after a CLI run.

### CON-012 (high) · test_compare.py
TC-012-1 default period ignored · TC-012-2 scope filter ignored
- CI-012-01 EP: run dated months before today counted.
- CI-012-02 EP: run outside the project scope (other cwd, not in TREE_ROOTS) counted.
- CI-012-03 RETIRED (design check 1 item 8, 2026-11-05): Q-039 (already decided, answer 6) says no period edge exists; the comparison reads no clock and no period, so there is no boundary to test. "A record of any age counts" is covered by CI-012-01 (EP-012-01, "old record counts"). Not counted in the totals.

### CON-013 (high) · test_compare.py
TC-013-1 runs and mains by effective key, exact string · TC-013-2 own key alone is no data · TC-013-3 several mains add up
- CI-013-01 EP: sub-agent runs with `ticket_eff == key` in the data.
- CI-013-02 EP: main session with `ticket_eff == key` in the data (main_sessions 1).
- CI-013-03 EP: run with `ticket == key`, `ticket_eff` other -> not in the data.
- CI-013-04 EP: two main sessions -> main_sessions 2; main tokens, cost and wait summed.
- CI-013-05 EP: `exp1-r22c` vs `EXP1-R22C` data -> not included (no case folding).

### CON-014 v7 (medium) · test_compare.py
TC-014-1 run files count · TC-014-2 spawn with no run file by result (DT) · TC-014-3 key sources of such a spawn · TC-014-4 mains excluded, duplicates once
- CI-014-01 DT: spawn with a run file -> counted once (run, not run + spawn).
- CI-014-02 DT: no run file, error result, key -> counted.
- CI-014-03 DT: no run file, non-error result, key -> counted.
- CI-014-04 DT: no run file, no tool_result -> not counted.
- CI-014-05 DT: no run file, error result, no key -> counted nowhere.
- CI-014-06 EP: spawn_lead wins over spawn_text.
- CI-014-07 EP: spawn_text when no lead.
- CI-014-08 BVA: parent key changes inside the session: spawn just before -> old key, just after -> new key (`latest_before`); evidence at the same instant as the spawn counts, same-timestamp tie = smaller key (v7, Q-040).
- CI-014-09 EP: no evidence in force -> the spawning run's own `runs.ticket`, not `ticket_eff`.
- CI-014-10 EP: main session never in the total.
- CI-014-11 EP: same spawn id in two session files (resume) -> counted once, earliest-ts row.
- CI-014-12 EP: `Agent` and `Task` tool names both count.

### CON-015 (high) · test_compare.py
TC-015-1 API error as last turn · TC-015-2 denial with no final reply · TC-015-3 final reply forms and verdicts · TC-015-4 spawns with no run file · TC-015-5 main never failed · TC-015-6 gone, missing, unreadable, broken logs
- CI-015-01 DT: last turn assistant `isApiErrorMessage` -> failed.
- CI-015-02 DT: last turn system subtype `api_error` -> failed.
- CI-015-03 EP: denial text "Permission to use ... has been denied", no reply after -> failed.
- CI-015-04 EP: "Permission for this action was denied ..." -> failed.
- CI-015-05 EP: "The user doesn't want to proceed with this tool use" -> failed.
- CI-015-06 DT: denial then a text reply -> not failed.
- CI-015-07 DT: API error then a text reply -> not failed.
- CI-015-08 EP: last assistant turn has text -> not failed.
- CI-015-09 EP: last is a SubagentHandback tool_use -> not failed.
- CI-015-10 EP: ends on another tool_use -> failed.
- CI-015-11 EP: ends on a tool_result -> failed.
- CI-015-12 EP: reply "FAIL" / "BLOCKED" / "REJECT" -> not failed.
- CI-015-13 DT: spawn error result, no run file -> failed.
- CI-015-14 DT: spawn non-error result, no run file -> run, not failed.
- CI-015-15 DT: spawn no result, no run file -> not counted, not failed.
- CI-015-16 EP: main session ending on an API error -> failed 0.
- CI-015-17 EP: run in `log_deleted` -> run, not failed; tokens still counted.
- CI-015-18 EP: file removed after the scan, no `log_deleted` row -> not failed, no exception (Q-030).
- CI-015-19 EP: file chmod 000 -> not failed, no exception (Q-030).
- CI-015-20 EP: a bad JSON line and a truncated last line are skipped; markers from the valid lines.

### CON-016 (medium) · test_compare.py
TC-016-1 numbering per role · TC-016-2 spawns take a place by spawn ts · TC-016-3 mains excluded
- CI-016-01 EP: one role, 3 runs -> 2; one run -> 0.
- CI-016-02 EP: two roles with 2 runs each -> 2.
- CI-016-03 EP: error spawn with no file of role X before a run of X -> the run is a repeat.
- CI-016-04 EP: non-error spawn with no file numbered.
- CI-016-05 EP: spawn with no result not numbered.
- CI-016-06 EP: main sessions not numbered.
- CI-016-07 EP: role of a no-file spawn = `subagent_type`; empty -> "general-purpose".
- CI-016-08 BVA: two runs of one role with equal start ts -> 1, same output twice.

### CON-017 (medium) · test_compare.py
TC-017-1 four kinds · TC-017-2 per model, total, "unknown" · TC-017-3 main tokens apart · TC-017-4 no double count
- CI-017-01 EP: input, output, cache_read, cache_write = w5m + w1h.
- CI-017-02 EP: two models -> by_model and total = their sum.
- CI-017-03 EP: model NULL -> "unknown".
- CI-017-04 EP: main tokens summed over two mains.
- CI-017-05 EP: one message present in two files (usage dedupe) counted once.

### CON-018 v2 (high) · test_compare.py
TC-018-1 existing pricing rules incl. tier · TC-018-2 main cost apart · TC-018-3 base-commit pricing.yaml
- CI-018-01 EP: priced model -> cost per model; total = sum of by_model.
- CI-018-02 EP: tier-priced message -> priced, unpriced_messages 0.
- CI-018-03 EP: w5m and w1h priced at their own rates.
- CI-018-04 EP: main cost on its own.
- CI-018-05 CL: `console/pricing.yaml` unchanged against the base commit.

### CON-019 (medium) · test_compare.py
TC-019-1 unpriced adds 0 and is counted
- CI-019-01 EP: unpriced model -> cost +0, unpriced_messages +1; the model is listed in cost_usd.by_model with 0 (CON-018 v2, Q-038).
- CI-019-02 BVA: 0 unpriced -> 0 shown.
- CI-019-03 BVA: 1 unpriced -> 1 shown.

### CON-020 (medium) · test_compare.py
TC-020-1 span across all files · TC-020-2 no timestamps (Q-032)
- CI-020-01 EP: first ts in the main session, last in a sub-agent -> span of both.
- CI-020-02 EP: one file -> last minus first.
- CI-020-03 EP: one file with no timestamps among timed ones -> ignored.
- CI-020-04 BVA: no timestamp at all, or only a no-file spawn -> 0.

### CON-021 (medium) · test_compare.py
TC-021-1 overlaps add up · TC-021-2 mains excluded · TC-021-3 no duration adds 0
- CI-021-01 EP: two overlapping runs -> sum (> wall).
- CI-021-02 EP: main session time not included.
- CI-021-03 EP: no-file spawn adds 0.
- CI-021-04 EP: run with no start or end ts adds 0, still counted in runs (Q-032).

### CON-022 v11 (high) · test_compare.py
TC-022-1 stops · TC-022-2 gap ends · TC-022-3 records that end no gap · TC-022-4 one gap per end · TC-022-5 60 s edge · TC-022-6 per session, summed · TC-022-7 gone / missing / unreadable files · TC-022-8 a gap repeated in a resumed main file counts once (v9) · TC-022-9 match keys (shared uuid OR shared message.id + requestId; timestamp pair only when a stop record has neither) and earliest-gap-end tie-break (v10), also inside one file (v11, Q-034)
- CI-022-01 ST: rule example 1 -> 900 s.
- CI-022-02 ST: dismissed AskUserQuestion example -> 390 s.
- CI-022-03 ST: rejected permission prompt is a stop; gap starts at the assistant record holding the tool_use (Q-035) and ends at the next typed message.
- CI-022-04 ST: end_turn (message.stop_reason "end_turn", Q-036) -> typed message -> one gap.
- CI-022-05 ST: stop with no gap end after it -> 0.
- CI-022-06 EP: slash command (`<command-name>`) ends a gap.
- CI-022-07 EP: no-origin plain text (old log) ends a gap.
- CI-022-08 EP: task notification does not end a gap.
- CI-022-09 EP: local command output (`<local-command-`) does not.
- CI-022-10 EP: "[Request interrupted by user]" does not.
- CI-022-11 EP: tool result other than an AskUserQuestion answer does not.
- CI-022-12 EP: peer message / isMeta does not.
- CI-022-13 EP: hook output does not (attachment / system record; a user record with isMeta true is a valid stand-in, Q-037).
- CI-022-14 BVA: gap 59 s -> 0.
- CI-022-15 BVA: gap 60 s -> 60.
- CI-022-16 EP: origin.kind "human" with toolUseResult -> not typed.
- CI-022-17 EP: sub-agent files add no wait.
- CI-022-18 EP: two mains -> sum.
- CI-022-19 EP: stop at the end of main 1, typed message in main 2 -> no gap (Q-031).
- CI-022-20 EP: main in `log_deleted` -> 0, a number, not "no main session".
- CI-022-21 EP: main file missing or unreadable at read time -> 0 (Q-030).
- CI-022-22 ST: rule's resumed-session example (file 2 repeats all of file 1 with the same uuids, then a typed message at 2000 s) -> 1800 s = file 1 alone (300 s) + the real resume gap (1500 s), not 2100 s (Q-033, v11).
- CI-022-23 EP: key 1, uuid: copied stop record keeps its uuid -> its gap counts once.
- CI-022-24 EP: key 2, OR (v10, kept in v11): copied stop record has a new uuid, same message.id + requestId -> one gap, counted once.
- CI-022-25 EP: key 2: one stop record has no uuid, both have the same message.id + requestId -> counts once.
- CI-022-26 EP: key 3, timestamp pair: stop records with no uuid and no message.id + requestId, same (stop timestamp, gap end timestamp) pair -> counts once.
- CI-022-27 DT: tie-break: same stop key, gap end at 400 s in file 1 and 450 s in file 2 -> the earliest end counts (300 s, not 350 s), once.
- CI-022-28 ST: copied stop closed only in the resumed file (file 1 ends after the stop at 500 s, file 2 copies it and the person types at 2000 s) -> one gap, 1500 s, counted once.
- CI-022-29 EP: no shared key (v10, kept in v11): stop records with different uuids and different message.id + requestId, same (stop timestamp, gap end timestamp) pair -> two gaps, both counted (the timestamp pair is used only when a stop record has neither key).
- CI-022-30 ST: one main file, two stop records with different uuids sharing message.id + requestId, each with its own typed gap end (rule example: typed 0, stop 100, typed 400, stop 500 same reply, typed 1100) -> one gap, the earliest end counts: 300 s, not 900 s (v11, Q-034; written as TC-ST-11 in cases-st-cl.md).

### CON-023 (low) · test_compare.py
TC-023-1 part over 7200 s · TC-023-2 label
- CI-023-01 BVA: gap 7200 s -> not in the part.
- CI-023-02 BVA: gap 7201 s -> in the part, in full.
- CI-023-03 EP: mixed gaps -> part = sum of gaps > 7200 s only.
- CI-023-04 EP: no main session -> "no main session".

### CON-024 (medium) · test_compare.py, test_compare_format.py
TC-024-1 label precedence · TC-024-2 zero main cost is a number · TC-024-3 display
- CI-024-01 DT: main > 0, sub > 0 -> number.
- CI-024-02 DT: main present, sub 0 -> "no sub-agents".
- CI-024-03 DT: no main, sub > 0 -> "no main session".
- CI-024-04 DT: no main, sub 0 -> "no main session".
- CI-024-05 BVA: main present with cost 0, sub > 0 -> 0, shown `0.00`.
- CI-024-06 BVA: 0.125 -> `0.13`; 0.25 -> `0.25` (no percent). Tested in BVA-030 (cases-bva.md; BVA-012 is a merge note).

### CON-025 (medium) · test_compare.py, test_compare_page.py
TC-025-1 labels in main rows · TC-025-2 totals real 0
- CI-025-01 EP: no main -> label in wait, wait_over_2h, main tokens, main cost, share (JSON).
- CI-025-02 EP: ticket of one no-file spawn -> runs 1, tokens 0, cost 0, wall 0 as numbers.
- CI-025-03 EP: page and CLI text show the label text.

### CON-026 (medium) · test_compare.py, test_compare_format.py
TC-026-1 diff and ratio by value state (DT) · TC-026-2 model on one side · TC-026-3 raw then rounded · TC-026-4 full D tree
- CI-026-01 DT: both numbers, a > 0 -> b - a, b / a.
- CI-026-02 DT: a = 0, b > 0 -> diff shown, ratio n/a.
- CI-026-03 DT: a is a label -> both n/a.
- CI-026-04 DT: b is a label -> both n/a.
- CI-026-05 EP: model only in a -> b = 0, diff -a, ratio 0; model only in b -> ratio n/a.
- CI-026-06 EP: a 1499, b 2501 tokens -> diff `1k` (raw 1002), not `2k`.
- CI-026-07 BVA: ratio shown with 2 decimals, tie away from zero.
- CI-026-08 EP: a side with no main session -> D still has every leaf; `tokens.main` has 4 K leaves of n/a.

### CON-027 (medium) · test_compare.py, test_compare_cli.py, test_compare_page.py
TC-027-1 known branches · TC-027-2 unknown on the page · TC-027-3 unknown in the CLI · TC-027-4 no folding, no uncounted spawn · TC-027-5 precedence
- CI-027-01 EP: known via a sub run's `ticket_eff`.
- CI-027-02 EP: known only as a main's own key -> compared, runs 0, main rows labels.
- CI-027-03 EP: known only via a counted no-file spawn -> runs 1, wall 0.
- CI-027-04 EP: known only via `log_deleted` run rows.
- CI-027-05 EP: unknown a -> page 404 naming the key.
- CI-027-06 EP: unknown a -> CLI one stderr line, exit 2, stdout empty (also with `--json`).
- CI-027-07 EP: both unknown -> page names both.
- CI-027-08 EP: both unknown -> CLI one line naming a then b (Q-028).
- CI-027-09 EP: same unknown key twice -> named once, page and CLI (Q-028).
- CI-027-10 EP: lower-case form of an existing key -> unknown.
- CI-027-11 EP: key only on a spawn with no result -> unknown.
- CI-027-12 EP: key only on an old run outside the default period -> known.
- CI-027-13 DT: page, a missing and first index -> 422.
- CI-027-14 DT: page, first index and unknown key -> 503.
- CI-027-15 DT: CLI, guard refusal and unknown key -> refusal line, exit 2.

### CON-028 (low) · test_compare.py
TC-028-1 a == b
- CI-028-01 EP: same known key -> diffs 0, ratios 1.
- CI-028-02 BVA: same key with a 0 figure -> ratio n/a.

### CON-029 (low) · test_compare_format.py
TC-029-1 tokens · TC-029-2 dollars · TC-029-3 time · TC-029-4 ratio tie · TC-029-5 one formatter, JSON raw
- CI-029-01 BVA: 499 -> `0k`. CI-029-02 BVA: 500 -> `1k` (round() would give 0k). CI-029-03 BVA: 1234567 -> `1235k`. CI-029-04 BVA: -400 -> `0k`. CI-029-05 BVA: -500 -> `-1k`.
- CI-029-06 BVA: 0.005 -> `$0.01`. CI-029-07 BVA: -0.004 -> `$0.00`. CI-029-08 BVA: -1.234 -> `-$1.23`. CI-029-09 BVA: 1234.56 -> `$1234.56`. CI-029-10 BVA: -0.005 -> `-$0.01`.
- CI-029-11 BVA: 29 s -> `0 min`. CI-029-12 BVA: 30 s -> `1 min`. CI-029-13 BVA: 0 -> `0 min`. CI-029-14 BVA: -20 s -> `0 min`. CI-029-15 BVA: 8100 s -> `135 min`.
- CI-029-16 EP: page and CLI text give the same string for the same value (one module).
- CI-029-17 BVA: ratio 0.125 -> `0.13`.
- CI-029-18 EP: JSON keeps raw values (no rounding).

### CON-030 (medium) · test_compare.py
TC-030-1 format · TC-030-2 same data, same bytes · TC-030-3 types and field set
- CI-030-01 EP: `sort_keys`, indent 2, top `a`, `b`, `diff`, `version: 1`.
- CI-030-02 EP: two runs on the same data -> byte-identical.
- CI-030-03 EP: integers stay integers, floats raw, labels strings (change.md types).
- CI-030-04 EP: D key set the same with a label side and a number side. Tested in EP-026-08 (cases-ep.md; EP-030-04 is a pointer).
- CI-030-05 EP: snapshot of every key path (fixed field names).

### CON-031 (low) · test_compare_cli.py, test_compare_page.py
TC-031-1 no new dependency · TC-031-2 read-only, no edits · TC-031-3 two tickets at most
- CI-031-01 CL: requirements files unchanged; no new import outside stdlib + existing packages.
- CI-031-02 EP: page request leaves every tmp log file's sha256 unchanged.
- CI-031-03 EP: no POST route added (test_server route list); 200 body has no edit action.
- CI-031-04 EP: page and CLI take two keys only (see CI-034-11, 12). Tested in: page half EP-034-12, CLI half EP-031-04 (cases-ep.md).

### CON-032 (high) · existing suites, test_store_and_flags.py
TC-032-1 existing suites pass · TC-032-2 `key_evidence` refactor is behaviour-neutral · TC-032-3 new meta rows change nothing else
- CI-032-01 CL: console suite and tools/kit suite pass as on the baseline (445 / 49 + new tests), ruff clean.
- CI-032-02 EP: rebuild on the recorded fixtures -> same `ticket`, `ticket_src`, `ticket_eff` per run before and after (test_tickets, test_scope_and_ticket_determinism).
- CI-032-03 EP: console start on an index with no `home`/`repo_root` rows -> rows added, derived rows kept.
- CI-032-04 EP: POST route list unchanged.

### CON-033 (high) · test_compare_page.py
TC-033-1 Host guard · TC-033-2 security headers · TC-033-3 complete page, no inline style or script · TC-033-4 bind
- CI-033-01 EP: foreign Host -> 404 JSON.
- CI-033-02 EP: Host `127.0.0.1:<port>` and `localhost:<port>` -> answered.
- CI-033-03 BVA: right host, other port -> 404.
- CI-033-04 EP: headers on 200. CI-033-05 EP: on 404. CI-033-06 EP: on 422. CI-033-07 EP: on 503.
- CI-033-08 EP: `server.main` binds 127.0.0.1 (existing test kept).
- CI-033-09 EP: 200, 404, 422, 503 bodies: complete HTML, no `<style`, no `style=`, no inline `<script>`, nothing from another origin.
- CI-033-10 EP: `/static/compare.css` served and passes test_static.

### CON-034 (medium) · test_compare_page.py, test_compare_cli.py
TC-034-1 page missing value (DT) · TC-034-2 CLI usage (DT) · TC-034-3 no trimming, extra parameters · TC-034-4 no form
- CI-034-01 DT: a missing -> 422 naming a. CI-034-02 DT: b missing -> 422 naming b. CI-034-03 DT: both missing -> names both. CI-034-04 DT: `a=` -> 422. CI-034-05 DT: `a=%20%20` -> 422.
- CI-034-06 EP: `a=%20KEY` -> used as written -> 404 naming " KEY".
- CI-034-07 DT: CLI no keys -> usage, exit 2. CI-034-08 DT: one key. CI-034-09 DT: `""`. CI-034-10 DT: `"  "`. CI-034-11 DT: three keys -> usage, exit 2 (Q-029); tested in EP-031-04 (CLI) (cases-ep.md; DT-034-11 in cases-dt.md is the DT trace only).
- CI-034-12 EP: extra parameter `c=X` ignored -> 200 (Q-029). Tested in EP-034-12 (cases-ep.md; also carries the page half of CI-031-04).
- CI-034-13 EP: `a=X&a=Y` -> Y used (Q-029).
- CI-034-14 EP: 200 body has no form, no swap, no "compare with" link.
- CI-034-15 EP: 422 body is HTML naming the parameter, not `{"detail": ...}`.

### CON-035 (high) · test_compare.py, test_compare_cli.py, test_compare_page.py
TC-035-1 no raw log text in any output · TC-035-2 matched markers stay inside · TC-035-3 escaping
- CI-035-01 EP: sentinel strings in user text, assistant text, tool inputs and tool results -> absent from CLI text.
- CI-035-02 EP: same -> absent from JSON.
- CI-035-03 EP: same -> absent from the page.
- CI-035-04 EP: denial and API error texts -> absent from all outputs.
- CI-035-05 EP: key `<script>x</script>` -> 404 page shows it escaped.
- CI-035-06 EP: model and role names with `<b>` from logs -> escaped on the 200 page.

## Totals
- Rules: 26 new, all testable; 95 test conditions; 227 coverage items (return round 1: +2 conditions TC-022-8, 9; +8 items CI-022-22..29; CI-022-24 reworked for v10. Design check 1, 2026-11-05: +1 ST item CI-022-30 under TC-022-9 (v11, Q-034); -1 BVA item CI-012-03 retired (Q-039); TC-012-1 kept, covered by CI-012-01).
- By technique: EP 136 · DT 47 · BVA 30 · ST 11 · CL 3.
- Map edits by QA (Agent decisions, answer 37, all 2026-11-05): CON-011 v4, CON-015 v8, CON-020 v2, CON-021 v4, CON-022 v8, CON-027 v6, CON-032 v3 (risk), CON-034 v4; QUESTIONS.md Q-026..Q-032.
- Map edits by the business analyst (return round 1, rr8): CON-011 v5 (Q-027 in the statement), CON-022 v9 (Q-033), CON-022 v10 (Q-033: uuid OR message.id + requestId). Test design questions: CON-014 v7 (Q-040), CON-018 v2 (Q-038), CON-022 v11 (Q-034..Q-037), CON-012 note only (Q-039). Items follow these versions.
