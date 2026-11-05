PASS

# test-designer report: EXP1-KITC, round 3 (re-plan)

Path: `docs/agents/work/EXP1-KITC/test-designer-r3.md`. Product code not touched. Only `console/tests/test_compare.py` changed (54 tests added at the end of the file, in the section "Round 3"; the 60 earlier tests are unchanged and still pass).

## Result of the run
- `test_compare.py`: 108 passed, 1 failed (the expected red test). Console suite: 553 passed, 1 failed. Ruff clean.
- "Before the change" here means against the current working-tree code (compare.py and server.py from code round 1, which already follow most of the new rules). So most new tests are green on arrival: they pin the changed rules, and I show below that they go red when the behaviour is broken. Exactly one is red because the code lacks the behaviour.

## Red test (fails for the right reason)
| Test | Rule | Failure | Right reason? |
|---|---|---|---|
| test_non_error_spawn_without_a_run_file_counts_as_a_run_and_is_not_failed | CON-037, CON-053 (answer 35, item 44) | role run total 1, expected 2: a spawn whose tool result is not an error and that has no run file is not counted (compare.py:147-151 reads error spawns only) | yes. The CONFLICT the analyst named. The code step must fix it. |

## New tests by rule (all with `# rule:`)
- CON-035 (F11): denied result after the last normal reply with end_turn fails the run, for both wordings (2 cases); a non-denial `is_error` result (string toolUseResult) after the reply does not; a denial wording with `is_error` false does not; a normal reply after a denial clears it (final state); missing stop_reason fails; log file gone is not failed.
- CON-035 (F12): a `<synthetic>` record without `isApiErrorMessage` neither clears an earlier API error nor fails a finished run.
- CON-037/053: non-error spawn without run file (red, above); no result and no run file not counted; error spawn without run file counts and fails; spawn with a run file not counted twice; three refused spawns with their own ids (3 runs, 3 failed, 2 repeat); a refused spawn naming the key makes it known (CLI and page).
- CON-032: page 404 exactly, naming the key(s).
- CON-054: page 422 for six missing/empty combinations, one `<p>`, no form/input/swap/link/table; CLI with 0, 1, 3 keys exits 2 with usage; no key length limit (300-char and 61-char keys give the unknown-key 404 / exit 2, not a length error).
- CON-055: wrong-case key is unknown when only the other case has runs.
- CON-038: `unknown` model shown in JSON (column and difference) and on the page.
- CON-043/044: exactly 60 s counts, 59 s is zero, 7201 s is in the over-2h figure; machine records that must not end a gap (6 cases: no-origin local-command, interrupt marker, task notification, system reminder; origin task-notification, origin system); typed slash command ends a gap (origin none and human); tool result does not end a gap; rejected prompt ends at the next typed message; AskUserQuestion ends only on its own answer.
- CON-050: `12k`/tie `13.5k` to `14k`, difference `2k`; negative tie `-2k`; ratio tie 1.005 to `1.01`; whole minutes, 135 min stays minutes, `-133.5` to `-134 min`; dollars two decimals and no `-0.00`.
- CON-051: shape fixed (top keys, column keys, role_runs keys, model on one side only gives null); `main_session` null and n/a values null.

## Mutation check (run in place on compare.py, restored and compared byte for byte afterwards)
| Mutation | Result |
|---|---|
| N8: denial prefixes replaced (reviewer F11) | KILLED by the 2 new F11 tests |
| N10: synthetic skip removed (F12) | KILLED by 2 new tests |
| 60 s boundary `>=` to `>` | KILLED (2 tests) |
| 7200 s boundary `>` to `>=` | KILLED (existing test) |
| negative zero guard removed | KILLED (3 tests) |
| ROUND_HALF_UP to HALF_EVEN | KILLED (3 tests) |

## Coverage and size
Rules 032, 035, 037, 038, 043, 044, 050, 051, 053, 054, 055 each have a marked test. Size L; went over one test per rule for the edge cases the rules name and the reviewer findings.

## Findings / CONFLICT / UNVERIFIED
- CONFLICT (analyst, kept): F11 says a denial must fail an end_turn run; the code resets on every later normal reply. The tests follow the rule text: denial AFTER the last normal reply fails; `test_normal_reply_after_a_denial_clears_it` pins the other half. If the person wants any denial to fail the run, that one test and the code change.
- UNVERIFIED: denial wordings beyond the two prefixes.
- Key tests: the console only accepts keys like `ABC-1` (uppercase prefix, up to 6 digits), so a long or lower-case key cannot exist in a log. CON-054 "no length limit" and CON-055 are tested through the unknown-key path only; a known long key cannot be built with the fixtures.
- `test_a_gap_of_exactly_60_s_counts_and_59_s_is_zero` holds an `or` between two path searches (weak on the lookup form, strong on the value 60); the 59 s case has its own test.
- Not tested: CON-027 no-argument start as a check (answer 38, not a test; the earlier monkeypatch test stays).
