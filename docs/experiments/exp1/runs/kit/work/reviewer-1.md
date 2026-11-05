FAIL

# Reviewer report: EXP1-KITC, round 1

Workbench: <workbench>. Diff reviewed: tracked changes (`__main__.py`, `server.py`) plus untracked `compare.py` and `test_compare.py`, against the working tree.

## Re-run by me
- Throwaway copy of the worktree: `tests/test_compare.py` 47 passed. `ruff check .` clean in the project.

## Rules check (CON-027..CON-052)
Implemented and with a `# rule:` test: CON-027..035, 037..051 (CON-029..031 etc. have one test each).
- F1: CON-036 has no test with `# rule: CON-036` (read-only reading of raw logs). Add a marker or a test (for example, file mtime or content unchanged after a compare). `console/tests/test_compare.py` (no marker found).
- F2: CON-052 (no new dependencies) has no test and no marker. A check is possible (requirements files unchanged), or record it as covered by review. The diff adds no dependency (verified: `compare.py` imports stdlib and package modules only).
- F3: CON-027 "no argument starts the server" has no test; the builder verified it by hand only (builder-code.md). Answer 38 allowed a check, so this is minor, but the `__main__.py` branch has no automated guard.
- F4: `compare.py:77-93` (`run_failed`) treats a `SubagentHandback` tool_use as a final reply, but CON-035 (`docs/requirements/console.md`) says a final reply is `stop_reason` end_turn only. The code goes beyond the rule (an Agent decision listed in the builder report). The map must be updated to say so (the analyst's job), or the builder must narrow the code. No test covers the handback branch (see mutation M10).

## Conventions
- `server.py` route: the `len(a) > 60` guard is not in any rule or in the console's key rules (CON-001). A small unrequested limit; answer 28 says no extra rules on keys. Either cite a rule or drop it. `server.py:~200`.
- `compare.py:cli_main` runs `Store().ingest()`, so the CLI writes the index in `AGENT_CONSOLE_HOME`. It is disclosed and read-only for logs; accepted as an Agent decision. Note: the CLI does not close or guard against a running console writing at the same time (UNVERIFIED).
- Style matches the surrounding code (docstring header, type hints). No scope creep otherwise. No new dependencies.
- `test_page_is_a_server_rendered_route_outside_the_hash_app` has a weak assertion: `"<script" not in r.text.lower() or "#/" not in r.text` passes if either part holds. Low value, not a blocker.

## Mutation check (round 1, 14 mutations, all new)
Each was applied by an exact string replace on an executable line in `/tmp` copy, one at a time, and the compare tests run with `-x`.

| # | Mutation | Location | Result |
|---|---|---|---|
| M1 | wait gap `>= WAIT_MIN_S` to `>` | compare.py main_waits | KILLED: test_wait_threshold_gaps_under_60_s_are_zero_and_long_gaps_count |
| M2 | over-2h `g > WAIT_LONG_S` to `>=` | compare.py _ticket (wait_over_2h_s) | SURVIVED (boundary of exactly 7200 s untested; CON-045) |
| M3 | repeat `n - 1` to `n` | compare.py _ticket | KILLED: test_main_session_is_not_a_role_run |
| M4 | `failed = len(denied)` to 0 | compare.py _ticket | KILLED: test_denied_spawn_counts_in_run_total_and_failed |
| M5 | cache write drops 1h part | compare.py _add_tokens | KILLED: test_tokens_are_split_per_model_by_the_messages_own_model |
| M6 | share zero guard removed | compare.py _ticket | KILLED: test_cli_compare_subcommand_gives_json |
| M7 | ratio `a != 0` guard removed | compare.py _diff | KILLED: test_cli_compare_subcommand_gives_json |
| M8 | HALF_UP to HALF_EVEN | compare.py _round | KILLED: test_page_is_a_server_rendered_route_outside_the_hash_app |
| M9 | `-0` guard `q != 0` removed | compare.py _round | SURVIVED (answer 34, CON-050: a negative difference that rounds to zero must show `0k`, not `-0k`; no test) |
| M10 | SubagentHandback name replaced | compare.py run_failed | SURVIVED (no test of the handback branch) |
| M11 | active time sum to max | compare.py _ticket | KILLED: test_active_role_time_adds_up_parallel_runs |
| M12 | `sort_keys=True` to False | compare.py to_json | KILLED: test_json_keys_are_sorted_and_the_output_is_repeatable |
| M13 | `origin.kind == "human"` to True | compare.py _typed_by_person | KILLED: test_machine_written_user_records_do_not_end_a_wait |
| M14 | per-model `unpriced_messages += 1` removed | compare.py _ticket | SURVIVED (per-model unpriced count untested; the ticket total is tested) |

The 4 survivors are findings: F5 (M2), F6 (M9, a stated rule with no test), F7 (M10, goes with F4), F8 (M14, CON-040). No EQUIVALENT mutations. Throwaway copy `/tmp/rv` and the script removed.

## Return to
- test-designer: F1, F2 (optional), F3 (optional), F5, F6, F7/F4 test, F8, and the weak assertion.
- analyst: F4 (CON-035 wording for the handback), `len > 60` (add a rule or remove).
- builder: only if the analyst chooses to narrow F4 or drop the length guard.

## UNVERIFIED
- Behaviour against live logs (only fixtures were used).
- Concurrent writes to the index by the CLI while the console runs.
