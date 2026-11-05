PASS

# Builder report, step tests, return round 1: EXP1-KITC

Only `console/tests/test_compare.py` changed. No product code touched (compare.py restored byte-identical after mutation checks).

## Result
- Run: 55 tests, 54 pass, 1 red on purpose (below). Ruff clean on the file.
- Red test (expected, until step code): `test_run_that_did_not_complete_is_failed[handback_call_is_not_a_final_reply]` (CON-035). Failure: failed count is 0, expected 1, because `run_failed` treats a `SubagentHandback` tool_use as a final reply. Right reason: missing behaviour, not a typo.

## Findings addressed
| Finding | Change |
|---|---|
| F1 CON-036 | New `test_compare_leaves_every_raw_log_file_untouched` with `# rule: CON-036`: sets old mtimes, runs CLI and page, asserts file set, bytes and mtime_ns unchanged. |
| F2 CON-052 | New `test_no_new_dependency_is_declared_or_imported`: compare.py imports only stdlib or `agent_console` (AST); pyproject dependencies equal HEAD's if a pyproject exists. Reads source, marked as a guard in a comment. |
| F3 CON-027 | New `test_no_argument_starts_the_server_and_compare_does_not`: runs `agent_console.__main__` via runpy with patched `server.main` and `cli_main`; no argument calls only the server, `compare` calls only the CLI. |
| F5 CON-045 | New `test_gap_of_exactly_two_hours_is_not_over_two_hours` (7200 s counts as wait, over-2h figure is 0). Kills M2 (checked). |
| F6 CON-050, answer 34 | New `test_negative_difference_that_rounds_to_zero_is_never_minus_zero` (cli and page): tokens, dollars, minutes all round to zero, no `-0k`, `-$0.00`, `-0 min`. Kills M9 (checked). |
| F7/F4 CON-035 | New FAILING case `handback_call_is_not_a_final_reply`. See Agent decision 1. |
| F8 CON-040 | New `test_unpriced_count_is_also_given_per_model` (count 2 under the unknown-priced model). Kills M14 (checked). |
| Weak assertion | Page test now needs no `<script` and no `/static/ctq-` in the page (was an `or`). |

## Mutation re-check (applied in place, restored)
M2 killed by the new 2 h test; M9 killed by the minus-zero cli test; M14 killed by the per-model test; M10 killed by the handback test (it fails on current code; after narrowing, a rename of the tool name no longer matters).

## Agent decision (answer 37)
1. CON-035 handback: narrowest reading is that a final reply is `stop_reason` end_turn only; a run ending on a `SubagentHandback` call with stop_reason tool_use is failed. The test asserts this. Kit roles end this way in real logs, so on live kit runs this reading counts them failed (UNVERIFIED against live logs). The analyst should put this in CON-035; the builder (step code) must drop the `handed` branch in `run_failed`.
2. CON-052 is checked by an import and pyproject comparison (no pyproject at HEAD means only the import part runs). Covered also by review.
3. Per-model unpriced test reads `data["a"]` (the JSON top-level key `a` seen in current output); field names beyond that are still found by key search. If the JSON layout is renamed this test needs the same change as the others.
4. No test for the `len(a) > 60` guard (answer 28). If the code keeps it, it stays untested; the analyst or builder should drop it.
5. Security note 1 (CLI echoes control characters in keys): no test written; low, self-inflicted, no rule.

## Return to
- builder step code: narrow `run_failed` (handback), optionally drop the length guard.
