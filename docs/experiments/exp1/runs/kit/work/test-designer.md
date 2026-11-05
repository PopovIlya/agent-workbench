PASS

# test-designer report: EXP1-KITC

Path: `docs/agents/work/EXP1-KITC/test-designer.md`.

## Summary
One new file, `console/tests/test_compare.py`: 47 test cases (34 test functions, 13 from parametrize) for CON-027..CON-051. All 47 fail before the change for the expected reason. CON-052 has no test (gaps below). The other 445 console tests still pass; ruff is clean on the new file.

## Rules in scope
CON-027 to CON-052 (all `new`, scope EXP1-KITC). Answers 1-29 in ~/exp1/answers.md were used where the rule text points to them (24, 25, 26, 27, 29 are marked in the test comments).

## Tests written
All in `console/tests/test_compare.py`. Each carries a `# rule:` comment.

| Rule ID | Test (name) | Fails before the change because | Right reason? |
|---|---|---|---|
| CON-027 | test_cli_compare_subcommand_gives_json | `compare` is not a subcommand: old main() tries to start the server (bind on port 1 refused, exit 1) | yes |
| CON-027 | test_page_is_a_server_rendered_route_outside_the_hash_app | GET /compare is 404 | yes |
| CON-027 | test_page_keeps_the_local_host_check | GET /compare with a valid Host is 404, not 200 (so the 404 for a bad Host cannot pass by accident) | yes |
| CON-028 | test_cli_takes_exactly_two_keys[1 key, 3 keys] | exit 1 (server start refused), not usage exit 2 | yes |
| CON-028 | test_page_without_a_or_b_is_one_422_error | 404, not 422 | yes |
| CON-028 | test_compare_is_read_only | CLI does not run; also asserts no compare route accepts more than GET/HEAD and the log tree is unchanged | yes |
| CON-029 | test_same_key_twice_compares_the_ticket_with_itself | CLI does not run | yes |
| CON-030 | test_ticket_is_the_runs_by_effective_key_across_sessions | CLI does not run | yes |
| CON-031 | test_old_log_outside_scope_is_still_compared | CLI does not run (log dated 2025, cwd outside any project scope) | yes |
| CON-032 | test_cli_unknown_key_exits_2_and_names_it[3 cases] | exit 1, not 2 | yes |
| CON-032 | test_page_unknown_key_is_a_clear_error | 404 body `Not Found`, no key named | yes |
| CON-033 | test_main_session_is_not_a_role_run | CLI does not run | yes |
| CON-034 | test_repeat_round_is_any_later_run_of_the_same_role | CLI does not run | yes |
| CON-035 | test_run_that_did_not_complete_is_failed[api_error_assistant, api_error_system, permission_denial, no_final_reply] | CLI does not run | yes |
| CON-035 | test_verdicts_and_ordinary_errors_are_not_failed_runs[fail_verdict, blocked_verdict, ordinary_tool_error] | CLI does not run | yes |
| CON-035, CON-036 | test_raw_logs_are_read_only_and_no_log_text_reaches_the_output | CLI does not run; checks no prompt, reply, error or denial text in JSON, text or page, and log files unchanged | yes |
| CON-037 | test_denied_spawn_counts_in_run_total_and_failed | CLI does not run | yes |
| CON-038 | test_tokens_are_split_per_model_by_the_messages_own_model | CLI does not run | yes |
| CON-038 | test_message_without_model_id_is_counted_as_unknown (answer 29) | CLI does not run | yes |
| CON-039 | test_cost_per_model_and_total_from_pricing_yaml | CLI does not run | yes |
| CON-040 | test_unpriced_messages_add_zero_and_are_counted | CLI does not run | yes |
| CON-041 | test_wall_time_is_first_to_last_record_over_all_files | CLI does not run | yes |
| CON-042 | test_active_role_time_adds_up_parallel_runs | CLI does not run | yes |
| CON-043 | test_wait_threshold_gaps_under_60_s_are_zero_and_long_gaps_count | CLI does not run | yes |
| CON-043 | test_machine_written_user_records_do_not_end_a_wait (answer 24) | CLI does not run | yes |
| CON-044 | test_only_end_turn_and_ask_user_question_are_stops_for_the_person | CLI does not run | yes |
| CON-045 | test_extra_figure_is_the_part_of_the_wait_over_two_hours | CLI does not run | yes |
| CON-046 | test_sub_agent_runs_give_no_waits | CLI does not run | yes |
| CON-047 | test_share_is_main_cost_over_sub_agent_cost | CLI does not run | yes |
| CON-047 | test_share_without_sub_agents_says_so | CLI does not run | yes |
| CON-048 | test_ticket_without_main_session_says_so_in_the_main_rows | CLI does not run | yes |
| CON-048 | test_ticket_totals_show_real_values_without_a_main_session | CLI does not run | yes |
| CON-048 | test_several_main_sessions_are_summed (answer 20) | CLI does not run | yes |
| CON-049 | test_difference_and_ratio_b_over_a | CLI does not run | yes |
| CON-049 | test_ratio_and_difference_are_na_when_a_value_is_missing | CLI does not run | yes |
| CON-050 | test_text_output_is_rounded_the_same_way[cli, page] | cli: CLI does not run; page: 404 body has no rounded figures | yes |
| CON-050 | test_json_keeps_raw_values | CLI does not run | yes |
| CON-051 | test_json_keys_are_sorted_and_the_output_is_repeatable | CLI does not run | yes |

"CLI does not run" means: `python -m agent_console compare ...` falls into the old `main()`, which ignores the arguments and tries to bind the server. The tests set `AGENT_CONSOLE_PORT=1`, so it exits at once with a bind error (exit 1) instead of hanging. A 40 s timeout is a second guard.

## Covered by existing test
None. No existing test covers any of these rules, so no `# rule:` comment was added to existing tests.

## Command and output
`cd console && .venv/bin/python -m pytest tests/test_compare.py -q -p no:cacheprovider` -> `47 failed, 1 warning`.
Rest of the suite: `.venv/bin/python -m pytest tests -q -p no:cacheprovider --deselect tests/test_compare.py` -> `445 passed`.
`console/.venv/bin/python -m ruff check console/tests/test_compare.py` -> clean.
Failure kinds: 34 cases at the CLI exit check (bind refused / exit 1 instead of 0 or 2); the rest on page status (404 for /compare, expected 200/422/4xx naming the key) or on the output text of the missing page. One draft test (host check) passed before the change; it was corrected to require a 200 first, and now fails.

## Size budget
Size L: one test per rule, plus rule-named edges and the risky cases flagged by the analyst. 47 cases for 25 tested rules: over one per rule on purpose. The extras are: the failed-run kinds (4 failing, 3 not failing), wait thresholds (59 s / 60 s / over 2 h), stop kinds, machine-written records, sub-agent waits, unknown models, several main sessions, page and CLI for rounding and "no main session". Fixtures are built in-test with the conftest helpers; there is no new fixture file.

## Gaps
- UNVERIFIED: CON-052 (no new dependencies) has no test. It is a negative rule and a test would pass before the change. Check it in review: `git diff` of `console/requirements*.txt` is empty and the new module imports only the standard library and existing packages.
- UNVERIFIED: CON-027, "with no arguments `python -m agent_console` starts the server as today". Unchanged behaviour, so a test would pass before the change; no existing test covers it. Review by reading the dispatch in `__main__.py`.
- UNVERIFIED: CON-051 covers key order and repeatable output only. "Fixed field names" cannot be tested because the rules do not name the fields. "The page's data" in the rule has no stated form.
- UNVERIFIED: the rules fix numbers and wording but not the JSON shape. The tests find raw numbers anywhere in the JSON, numbers under a model name, or numbers on a path that holds words (`run`+`total`, `fail`, `repeat`, `wait`, `share`, `unpriced`). A correct implementation with other field names (for example `denied` instead of `failed`) would fail those tests. Time values are assumed to be raw seconds, as in CON-026. Suggest the developer fixes names that contain those words, or the owner states the names.
- UNVERIFIED: text formats are only partly fixed. Tests assume the exact phrases "no main session", "no sub-agents", "n/a" (case-insensitive), a ratio as `2.50`, dollars as `12.35`, tokens in thousands as `123` or `123,000`, minutes as `47`, and the CLI text on stdout. Rounding at .5 (minutes) is not tested because the rule does not say round or floor.
- UNVERIFIED: a permission denial in the middle of a run that later ends with a final reply is not tested (the rule says "ended in"). A run still in progress (CON-035 note) is not tested.
- UNVERIFIED: the page for an unknown key is tested as any 4xx that names the key and says "unknown"; the status is not fixed by the rules.
- Fixtures: synthetic logs with the real field names (`stop_reason`, `isApiErrorMessage`, `apiErrorStatus`, `origin.kind`). They cannot show a live session or a live clock.

## CONFLICT / UNVERIFIED
- No CONFLICT found.
- Question for the product owner (not blocking): name the JSON field names for CON-051, so the tests can pin them. Not filed as QUESTIONS.md entry because the verdict is PASS; the caller decides.

## Round 2 helper fix
Defect: `Sess.spawn(refuse=...)` named the tool_use id from `len(self.subs)+1`, and a refused spawn adds nothing to `subs`, so several refusals shared one id (index keeps one row per tool id). Fix, helper only in `console/tests/test_compare.py`: a `self.refused` counter; a refused spawn now gets id `tu-<agent>-r<N>`. Non-refused spawns and all test bodies are unchanged; no product code touched.
Result: `cd console && .venv/bin/python -m pytest tests/test_compare.py -q -p no:cacheprovider` -> 47 passed (CON-037 test `test_denied_spawn_counts_in_run_total_and_failed` now green).
